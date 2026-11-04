+++
date = '2026-11-20T18:00:00+03:30'
draft = false
title = 'Events and building an indexer with Go and Postgres'
description = 'Event indexer in Go and Postgres: topics and data, header blooms, batched eth_getLogs, idempotent inserts, confirmations and a real reorg on anvil.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "indexer"]
cover = { image = "/images/covers/bc-event-indexer-go.png", alt = "Events and building an indexer with Go and Postgres", hiddenInSingle = true }
+++

Say you run an exchange and need to know which DEMO token transfers one particular address has made. An Ethereum node answers "what happened in block 5" well, but "all DEMO transfers of this address since the beginning" badly. You would have to scan block after block. The exchange needs something else: fast answers, from its own database.

The program that does this is called an {{< term "indexer" "indexer" >}}. It reads the chain's events and copies them into our own database, so that any question can later be answered with plain SQL. It sounds simple at first, but it comes with three problems, and this post is organised around them:

1. How do we read only the blocks that matter?
2. If the program dies halfway, how do we avoid both losing and double-counting data?
3. What if the chain changes its last few blocks?

After [the alloy post](/posts/bc-rust-alloy-client/) I went back to Go, copied the module from [the go-ethereum post](/posts/bc-go-ethereum-client/) together with its abigen code, and built the indexer on top. The pieces come from earlier posts: Postgres from [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/), the bloom filter from [Bloom filters and consistent hashing](/posts/algo-bloom-filter-consistent-hashing/) and reorgs from [Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/).

> Run with Go 1.27 on macOS (arm64), go-ethereum v1.17.10, pgx v5.11.0 and PostgreSQL 18.3 from the `embedded-postgres` module on a free loopback port. A fresh anvil on `127.0.0.1:8545` with the deploy script from the tokens post; the addresses are anvil's public test accounts. Temporary paths are written as `<tmp>`.

## What an event is made of

First, what are we reading? When a contract emits an {{< term "event-log" "event" >}}, the result is a log in the transaction's receipt. A log has two kinds of places to hold information:

- **topics:** at most four 32-byte values.
- **data:** everything else, with no four-item limit.

For `Transfer(address indexed from, address indexed to, uint256 value)` the layout is this. Topic 0 is the hash of the event's signature (the `0xddf252ad...`) and says which kind of event this log is. Topics 1 and 2 are `from` and `to`, padded with zeros up to 32 bytes. `value`, which is not indexed, goes into data.

This difference matters in practice: the node can filter on indexed parameters ("only transfers whose recipient is this address"), but not on data.

## Skipping irrelevant blocks: the bloom

Every block header has a `logsBloom` field, 2048 bits wide. It is a {{< term "bloom-filter" "Bloom filter" >}}: a compact summary of the addresses and topics of all the logs in that block. A Bloom filter gives only two answers: "definitely not here" or "maybe here". "Maybe" means false positives are possible, but "not here" is always right. So when the bloom says no, you can skip the block without reading its receipts.

To see this, I wrote a small program that asks, for each block: is our token's address in the bloom? Is the `Transfer` topic in it? (I took this output at the very end, after all the experiments in this post, so it has seven blocks.)

```
$ go run ./cmd/bloom
block 1: token in bloom true  Transfer in bloom true
block 2: token in bloom false Transfer in bloom false
block 3: token in bloom false Transfer in bloom true
block 4: token in bloom true  Transfer in bloom true
block 5: token in bloom true  Transfer in bloom true
block 6: token in bloom false Transfer in bloom false
block 7: token in bloom false Transfer in bloom false
```

- **Block 1:** the token deploy, which minted 1,000,000 DEMO to account 0. Both are `true`.
- **Block 2:** the NFT contract deploy. Neither our token nor `Transfer`.
- **Block 3:** minting an NFT. This block has the `Transfer` topic, because an NFT emits an event with the same signature, but the address is not our token. A filter that wants both skips this block.
- **Blocks 4 and 5:** DEMO transfers.
- **Blocks 6 and 7:** no logs (we will see why: these are blocks I made for the reorg experiment).

Remember that `true` can still be a false positive; only `false` is certain.

## The tables

Now that we know what we want, we need somewhere to keep it. There are three tables:

```sql
CREATE TABLE blocks (number bigint PRIMARY KEY, hash text NOT NULL, parent_hash text NOT NULL);
CREATE TABLE transfers (
    block_number bigint NOT NULL, block_hash text NOT NULL,
    tx_hash text NOT NULL, log_index integer NOT NULL,
    from_addr text NOT NULL, to_addr text NOT NULL,
    value numeric(78, 0) NOT NULL, -- uint256 fits in 78 digits
    PRIMARY KEY (tx_hash, log_index)
);
CREATE TABLE cursor (id integer PRIMARY KEY CHECK (id = 1), last_block bigint NOT NULL);
-- IF NOT EXISTS and the cursor's first row (1, -1) trimmed
```

- **`blocks`:** the hash of every block we have processed. Later this tells us whether the chain changed.
- **`transfers`:** the transfers themselves, with the block they were in.
- **`cursor`:** a single row, like a bookmark: the last block fully processed. Its initial value is `-1`, meaning no block yet.

Two choices in `transfers` have reasons. `value` is `NUMERIC` because `bigint` overflows at about 9.2 DEMO (the token has 18 decimals, and amounts are stored in the smallest unit). And the primary key is `(tx_hash, log_index)`, because together they identify one log across the whole chain. As a result, inserting with `ON CONFLICT DO NOTHING` means that if we process a range twice, the second time adds nothing. An operation that is harmless to repeat is called {{< term "idempotency" "idempotent" >}}, and this is the answer to our second problem.

## Processing one batch

The indexer first works out which block is safe. It computes `head - N`, where N is the number of {{< term "confirmation" "confirmations" >}}: read only blocks that have at least N blocks on top of them, because the older a block, the less likely it is to change. Then it starts after the cursor and moves forward in batches of two blocks. (The batch size is set by the `-batch` flag and defaults to 2.)

```go
logs, err := ix.eth.FilterLogs(ctx, ethereum.FilterQuery{
	FromBlock: new(big.Int).SetUint64(from),
	ToBlock:   new(big.Int).SetUint64(to),
	Addresses: []common.Address{tokenAddr},
	Topics:    [][]common.Hash{{transferTopic}},
})
// in one DB transaction: the blocks' hashes, the transfers, the cursor
for _, l := range logs {
	if l.BlockHash != headers[l.BlockNumber].Hash() {
		return fmt.Errorf("block %d changed during the pass, rerun", l.BlockNumber)
	}
	ev, err := demo.UnpackTransferEvent(&l)
	// INSERT ... ON CONFLICT (tx_hash, log_index) DO NOTHING
}
```

`FilterLogs` asks the node for only this token's logs with the `Transfer` topic in this range. Then each log is compared with the header of its block: if the block's hash has changed, the chain moved in the middle of the pass and we stop with an error. Finally each log is decoded and inserted.

The key point is that the block hashes, the `transfers` rows and the cursor are all committed in **one database transaction**. If the program dies halfway, either all of it is recorded or none of it is, and the cursor never gets ahead of its data. Every new range must also attach to the block we stored last time: the parent hash of the range's first block has to equal the stored hash of the block before it. This check did not trigger in my runs.

## A run, a rerun, a reorg

Now let us see all three problems in action. `$T` is the token and `$A0` to `$A4` are anvil's test accounts 0 to 4. Account 0 sends account 1 250 DEMO (block 4). Then I take an anvil snapshot, that is, I save the current state so I can return to it later. Two more transfers (1 to 2 and 2 to 3) land in blocks 5 and 6. No reorg yet; first the plain run:

```
$ cast send $T "transfer(address,uint256)" $A1 250ether --unlocked --from $A0   # block 4
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $A2 40ether --unlocked --from $A1  # block 5
$ cast send $T "transfer(address,uint256)" $A3 5ether --unlocked --from $A2   # block 6
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2
head 6, confirmations 2, safe 4, cursor -1
blocks 0-1: 1 logs, 1 new rows
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 1 new rows
```

The first line: the chain tip is block 6, and with two confirmations only blocks up to 4 are safe. The cursor is still `-1`. The next three lines are the three batches: blocks 0 to 1 hold one log (the initial mint), blocks 2 and 3 hold no logs from our token, and block 4 holds one log (the 250 DEMO transfer). Blocks 5 and 6 are untouched because they do not have enough confirmations yet.

Now the second problem: the program dies halfway. `-rewind 1` moves the cursor back to block 1, as if the process had died right after committing block 1, and runs again:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2 -rewind 1
head 6, confirmations 2, safe 4, cursor 1
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 0 new rows
```

Block 4 is read again and the log is found, but **0 new rows** are inserted: `ON CONFLICT DO NOTHING` did its job. The repeated range did no harm.

Now the third problem, the reorg. First I follow the chain tip with `-confirmations 0`, so blocks 5 and 6 land in the database too. Then I roll anvil back to the snapshot (`evm_revert`), which destroys blocks 5 and 6. I send a different transfer (account 1 to account 4, 7 DEMO), which makes a new, different block 5, and mine two more empty blocks:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
head 6, confirmations 0, safe 6, cursor 4
blocks 5-6: 2 logs, 2 new rows
$ cast rpc evm_revert 0x0
true
$ cast send $T "transfer(address,uint256)" $A4 7ether --unlocked --from $A1   # new block 5
$ cast rpc anvil_mine 2
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
reorg: block 6 stored 0xa6ef000b, chain 0xc63678e1
reorg: block 5 stored 0x68dd3f4a, chain 0x60f21742
reorg: fork point 4, deleted 2 transfers above it
head 7, confirmations 0, safe 7, cursor 4
blocks 5-6: 1 logs, 1 new rows
blocks 7-7: 0 logs, 0 new rows
```

(I trimmed the output of `cast send` and `anvil_mine`. Block hashes differ on every run, so yours will be different numbers.)

anvil does not fork by itself; snapshot and revert are just a local way to make the chain replace two blocks. The indexer's method is simple: at the start, it compares the stored hash of the cursor block with the hash of the same block on the chain. If they differ, it steps back one block and compares again, until it reaches a block both sides agree on. That is the **fork point**. Then it deletes everything above it in one transaction and indexes again from there. In the output above:

- Two `reorg: block ...` lines: blocks 6 and 5 in the database differ from the chain.
- `fork point 4, deleted 2 transfers`: block 4 is still the same. The two old transfers (40 and 5 DEMO), which lived on the abandoned branch, were deleted.
- Then it indexes again: blocks 5 to 6 hold one log (the 7 DEMO transfer) and block 7 holds none.

This is the splice from [the forks post](/posts/bc-forks-reorgs/). With `-confirmations 2` the first run had stopped at block 4, so this two-block reorg would not have touched the stored data at all. That is exactly what confirmations are for.

## SQL against the contract

Did it really work? One way to check is to compute every address's balance in two ways: with SQL from the transfers we stored, and by asking the contract itself with `balanceOf`. The SQL counts each transfer once for the recipient with a plus sign and once for the sender with a minus sign:

```sql
WITH moves AS (
    SELECT to_addr AS addr, value FROM transfers
    UNION ALL
    SELECT from_addr, -value FROM transfers
)
SELECT addr, sum(value)::text FROM moves
WHERE addr <> '0x0000000000000000000000000000000000000000'
GROUP BY addr ORDER BY addr;
```

(We leave out the zero address, since the mint comes from there and it has no real balance.)

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -balances
0x15d34AAf… sql 7000000000000000000       balanceOf 7000000000000000000       match
0x70997970… sql 243000000000000000000     balanceOf 243000000000000000000     match
0xf39Fd6e5… sql 999750000000000000000000  balanceOf 999750000000000000000000  match
```

All three addresses agree exactly. Account 4 has 7 DEMO, account 1 has 250 − 7 = 243, and account 0 has 1,000,000 − 250 = 999,750. Accounts 2 and 3 appear on neither side: their DEMO existed only on the abandoned branch, and the reorg removed it from the database as well as from the chain.

## Where indexers go wrong

- **`eth_getLogs` by block number can race with a reorg.** Between fetching the header and fetching the logs, the chain can change. Compare each log's block hash with the header you stored, as the code above does.
- **As far as I know, RPC providers limit the block range or result count of `eth_getLogs`, each in its own way.** Read in batches and shrink the batch when you get an error.
- **Confirmations reduce reorg work, they do not remove it.** Keep a rollback path and test it.
- **Store amounts as `NUMERIC` or text, never `float`.** 256-bit numbers do not fit in a `float64`.

## Exercise

1. Add an `approvals` table for the `Approval` event and index both events with a single `FilterLogs` call.
2. Reorg three blocks and run with `-confirmations 2`. What changes?
3. Kill the process between `FilterLogs` and `COMMIT`. What state does the next run start from?

## What's next

The next post is "HD wallets: BIP-32, BIP-39 and BIP-44 in Rust": this indexer watches addresses, and that post shows where the addresses themselves come from.
