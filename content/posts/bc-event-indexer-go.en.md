+++
date = '2026-11-20T18:00:00+03:30'
draft = false
title = 'Events and building an indexer with Go and Postgres'
description = 'Event indexer in Go and Postgres: topics and data, header blooms, batched eth_getLogs, idempotent inserts, confirmations and a real reorg on anvil.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "indexer"]
cover = { image = "/images/covers/bc-event-indexer-go.png", alt = "Events and building an indexer with Go and Postgres", hiddenInSingle = true }
+++

In [Talking to Ethereum from Rust with alloy](/posts/bc-rust-alloy-client/) the client was Rust. This post goes back to Go: I copied the module from [Talking to Ethereum from Go with go-ethereum](/posts/bc-go-ethereum-client/), with its abigen bindings, and built an {{< term "indexer" "indexer" >}}.

A node answers "what is in block 5" well and "every DEMO transfer of this address" badly; an exchange needs the second, fast, from its own database. The pieces come from earlier posts: Postgres from [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/), the bloom from [Bloom filters and consistent hashing](/posts/algo-bloom-filter-consistent-hashing/), and reorgs from [Forks, reorgs and the heaviest-chain rule](/posts/bc-forks-reorgs/).

> Go 1.27 on macOS (arm64), go-ethereum v1.17.10, pgx v5.11.0, PostgreSQL 18.3 from the `embedded-postgres` module on a free loopback port. A fresh anvil on `127.0.0.1:8545` with the deploy script from the tokens post; the addresses are anvil's public test accounts. Temp paths are written `<tmp>`.

## Topics and data

An {{< term "event-log" "event log" >}} has up to four topics and a data blob. For `Transfer(address indexed from, address indexed to, uint256 value)` topic 0 is the signature hash `0xddf252ad...`, topics 1 and 2 are `from` and `to` padded to 32 bytes, and `value` sits in data. The node can filter on indexed parameters, not on data.

Every block header also carries a 2048-bit `logsBloom`, a {{< term "bloom-filter" "Bloom filter" >}} of the addresses and topics of its logs. A tiny program asks it about each block (run at the end of this post):

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

Block 3 is the NFT mint: it has a `Transfer` topic, but not from our token. A filter for both can skip it without reading receipts. A "true" can still be a false positive.

## Schema

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

`value` is `NUMERIC`: a `bigint` overflows at about 9.2 DEMO. `(tx_hash, log_index)` identifies a log, so inserts use `ON CONFLICT DO NOTHING` and re-running a range is {{< term "idempotency" "idempotent" >}}.

## One batch

The indexer reads `head - N` ({{< term "confirmation" "confirmations" >}}), then walks from the cursor in batches of two blocks:

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

Blocks, rows and cursor commit together, so a crash never leaves a cursor ahead of its data. Each new range must also start from a block whose parent hash equals the stored hash of the block before it; this check did not fire in my runs.

## A run, a rerun, a reorg

`$T` and `$A0`-`$A4` are the token and anvil test accounts 0-4. Account 0 sends 250 DEMO to account 1 (block 4), I take a snapshot, then 1 → 2 and 2 → 3 land in blocks 5 and 6:

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
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 2 -rewind 1
head 6, confirmations 2, safe 4, cursor 1
blocks 2-3: 0 logs, 0 new rows
blocks 4-4: 1 logs, 0 new rows
(cast send output trimmed)
```

`-rewind` moves the cursor back as if the process died after committing. The log is read again and inserted zero times. To see a {{< term "chain-reorganization" "reorg" >}} I follow the tip with `-confirmations 0`, then revert anvil to the snapshot and build a different block 5:

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
head 6, confirmations 0, safe 6, cursor 4
blocks 5-6: 2 logs, 2 new rows
$ cast rpc evm_revert 0x0
true
$ cast send $T "transfer(address,uint256)" $A4 7ether --unlocked --from $A1   # new block 5
$ cast rpc anvil_mine 2
$ go run ./cmd/indexer -pgdir <tmp>/pg -confirmations 0
reorg: block 6 stored 0x2b083812, chain 0x2eeeb0c3
reorg: block 5 stored 0xfb574c72, chain 0x92e64fc2
reorg: fork point 4, deleted 2 transfers above it
head 7, confirmations 0, safe 7, cursor 4
blocks 5-6: 1 logs, 1 new rows
blocks 7-7: 0 logs, 0 new rows
(cast output trimmed)
```

anvil does not fork on its own; the snapshot and revert are a local way to make the chain replace two blocks. On start the indexer compares its stored hash for the cursor block with the chain's, walks back until they agree, deletes everything above that block in one transaction, and indexes again, the same disconnect-then-connect as in the forks post. With `-confirmations 2` the first run had stopped at block 4, so this two-block reorg would not have touched the data.

## SQL against the contract

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

```
$ go run ./cmd/indexer -pgdir <tmp>/pg -balances
0x15d34AAf… sql 7000000000000000000       balanceOf 7000000000000000000       match
0x70997970… sql 243000000000000000000     balanceOf 243000000000000000000     match
0xf39Fd6e5… sql 999750000000000000000000  balanceOf 999750000000000000000000  match
```

Accounts 2 and 3 are gone from both sides: their DEMO only existed on the abandoned branch.

## A few things to watch

- `eth_getLogs` by block number can race with a reorg; compare each log's block hash with the header you stored.
- As far as I know, hosted RPC providers cap the block range or result count of `eth_getLogs`, each differently; batch, and shrink the batch on errors.
- Confirmations reduce reorg handling, they do not remove it. Keep the rollback path and test it.
- Store values as `NUMERIC` or text, never `float`.

## Exercise

1. Add an `approvals` table for the `Approval` event and index both events in one `FilterLogs` call.
2. Reorg three blocks and run with `-confirmations 2`. What changes?
3. Kill the process between `FilterLogs` and `COMMIT`. Which state does the next run start from?

## What's next

Next post: **HD wallets: BIP-32, BIP-39 and BIP-44 in Rust**.
