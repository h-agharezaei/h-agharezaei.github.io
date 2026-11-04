+++
date = '2026-12-02T18:00:00+03:30'
draft = false
title = 'Exchange engineering: deposits, withdrawals, confirmations and reorgs'
seoTitle = 'Exchange deposits, withdrawals and reorgs in Go'
description = 'Exchange deposits and withdrawals in Go and Postgres: a deposit state machine, a double-entry ledger, a real reorg, idempotency keys and fee bumps.'
contentType = 'engineering'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "exchange"]
cover = { image = "/images/covers/bc-exchange-deposits-withdrawals.png", alt = "Exchange engineering: deposits, withdrawals, confirmations and reorgs", hiddenInSingle = true }
+++

Say a user sends 100 tokens to your exchange. The transaction lands in a block. If you credit 100 tokens to their account at once, and a little later that block is dropped from the chain in a {{< term "chain-reorganization" "reorg" >}}, the user has both their tokens and 100 tokens of credit from you. Withdrawals have their own problems: one request can arrive twice at the same moment because of a double click, and a signed transaction can get stuck with a low fee and never enter a block.

After the cryptography of [Zero-knowledge proof basics in Rust](/posts/bc-zero-knowledge-rust/), this post is ordinary backend work: turning chain events into balances, and balances back into transactions. The answers are things we already know from the rest of software engineering: state machines, database transactions and idempotency.

I copied the module from [Events and building an indexer with Go and Postgres](/posts/bc-event-indexer-go/), turned its indexer into a deposit scanner, and added a ledger and withdrawals. Addresses come from [HD wallets: BIP-32, BIP-39 and BIP-44 in Rust](/posts/bc-hd-wallets-rust/), signing and nonces from [Talking to Ethereum from Go with go-ethereum](/posts/bc-go-ethereum-client/). This is a teaching design, not a complete exchange, and says nothing about any real exchange's internals.

> Go 1.27 on macOS (arm64), go-ethereum v1.17.10, pgx v5.11.0, PostgreSQL 18.3 from `embedded-postgres`. A fresh anvil on `127.0.0.1:8547` with the deploy script from the tokens post. Every key and address is an anvil **public test account**. Temp paths are written `<tmp>`. In the transcripts below `X` means the `exchange` program (built from `./cmd/exchange`) with the flag `-pgdir <tmp>/pg`. The hot wallet's key is anvil account 9. Before the start, account 0 sent it 1000 DEMO so it has tokens to pay out (that transaction is block 4).

## Deposit addresses

First we must know whose deposit is whose. The way is to give every user their own address: any token that arrives there belongs to that user. This is a {{< term "deposit-address" "deposit address" >}}. In production I would derive it as `xpub/0/index` from an {{< term "xpub" "xpub" >}}, as in the HD wallets post, so the deposit service holds no private key. In this demo anvil accounts 1 and 2 stand in for alice and bob.

The scanner wants only transfers *to* these addresses. This is the filter over the token's logs:

```go
Topics: [][]common.Hash{{transferTopic}, nil, topicTo}, // Transfer(any, ours)
```

The three slots mean, in order: the `Transfer` event, any sender (`nil`), and a receiver from our addresses.

## Deposit states and the ledger

Think of each deposit as a small {{< term "state-machine" "state machine" >}}. When the log is first seen it is `seen`. While it has fewer than N {{< term "confirmation" "confirmations" >}} (N blocks on top of the deposit's block) it is `pending`. At N it becomes `credited` and the money goes to the account. And if a reorg removes its block before that, it becomes `orphaned`. The code writes these transitions out explicitly:

```go
var allowed = map[string][]string{
	"seen":     {"pending", "credited", "orphaned"},
	"pending":  {"pending", "credited", "orphaned"},
	"orphaned": {"seen"}, // the same log came back in another block
	"credited": {},       // final; a reorg past N needs a human
}
// move(): UPDATE deposits SET status = $to WHERE tx_hash = .. AND log_index = .. AND status = $from
```

Any transition not in this table is a program bug. `orphaned` can only go back to `seen`, for when the same transaction shows up in another block. `credited` is final: if a reorg removes a block even after N, a human must look at it, not code. Also, `move` changes the status only if the row is still in the old one (`AND status = $from`), so two concurrent processes cannot advance the same deposit twice.

A deposit row is identified by `(tx_hash, log_index)`, like in the indexer post: each log is recorded once.

Money lives in a {{< term "double-entry-bookkeeping" "double-entry" >}} ledger. The principle is simple: every financial event is a journal, and the amounts of all the entries in a journal add up to zero. When a user deposits 100 tokens, the journal has two entries: the `external` account (the outside world) gets minus 100 and the user's account gets plus 100. Money is never created from nothing and never lost. Each journal has a unique `ref` (for a deposit, `deposit:<tx>:<log index>`), so a deposit cannot be credited twice:

```go
posted, err := post(ctx, tx, fmt.Sprintf("deposit:%s:%d", d.hash, d.idx),
	line{"external", neg(amt)},
	line{"user:" + d.user, amt})
// then move(..., "credited") in the same DB transaction
```

After `post`, the change of status to `credited` happens in the same database transaction. Either both happen or neither does.

## A reorg before N, then N reached

Now let us see these pieces work. I want to build a real reorg on anvil. anvil can take a snapshot and later revert the chain to it, so blocks mined after the snapshot disappear. In the commands `$T` is the token, `$A0` the sender, `$ALICE` her deposit address, and N is 3 (confirmations = head − block number + 1).

The scenario: take a snapshot, send 100 DEMO to alice, scan, mine a block and scan again. Then revert and mine three new blocks, a different chain in which that transaction does not exist. The last scan has to notice.

```
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $ALICE 100ether --unlocked --from $A0   # block 5
$ X scan -confirmations 3
head 5, cursor -1, N 3
deposit alice 100 DEMO tx 0x1ee92a01 block 5: seen
deposit alice 100 DEMO: seen -> pending (1/3)
$ cast rpc anvil_mine 1
$ X scan -confirmations 3
head 6, cursor 5, N 3
deposit alice 100 DEMO: pending -> pending (2/3)
$ cast rpc evm_revert 0x0
true
$ cast rpc anvil_mine 3
$ X scan -confirmations 3
reorg: fork point 4, dropping blocks 5-6
deposit alice 100 DEMO tx 0x1ee92a01: pending -> orphaned
head 7, cursor 4, N 3
$ X balances
external             0 DEMO
user:alice           0 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast output trimmed)
```

Line by line:

- **First scan:** `cursor -1` means no block has been read yet, so it reads from the start. The transaction is in block 5 and the head is 5, so it has one confirmation: `1/3`. The status goes `seen` and straight to `pending`.
- **Second scan:** one more block, head 6. Now `2/3`. N is not reached, so nothing is credited.
- **The revert:** the chain goes back to the snapshot and blocks 5 and 6 are gone. We mine three new blocks (5 to 7) that do not contain the transaction.
- **Last scan:** for each block it has stored, the scanner compares the stored hash with the chain's current hash, walking from the top down until it finds a block that still matches. That is the `fork point`, here block 4. Everything above it (5 and 6) is dropped, and the deposits in those blocks become `orphaned`. They are not deleted, because they might return in another block.
- **balances:** no money moved. All accounts add up to zero.

The deposit was never credited, which was the goal. Here the transaction vanished completely. In a real reorg it may come back in another block, which is the `orphaned -> seen` edge.

Now a second deposit: 120 DEMO lands in block 8. The first scan makes it `pending (1/3)` (I trimmed that scan and the `cast send` output). We mine two blocks and scan again. Then, with `-rewind 4`, we set the scanner's cursor back to block 4 on purpose, to simulate the program crashing midway and having to re-read old blocks:

```
$ cast rpc anvil_mine 2
$ X scan -confirmations 3
head 10, cursor 8, N 3
deposit alice 120 DEMO: pending -> credited (3/3), journal posted: true
$ X scan -confirmations 3 -rewind 4
head 10, cursor 4, N 3
$ X balances
external             -120 DEMO
user:alice           120 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast send and the first scan, 1/3, trimmed)
```

- **First scan:** the deposit is in block 8 and the head is 10, so it has three confirmations (`3/3`). It became `credited` and the journal was posted (`journal posted: true`).
- **Scan with rewind:** the scanner re-read blocks 5 to 10, saw the log of block 8 again and **did nothing**. The key `(tx_hash, log_index)` and the unique journal `ref` stopped a second credit.
- **balances:** `external` is minus 120 (120 came from outside) and alice has plus 120 (the exchange owes her that much). They add up to zero.

## Withdrawals

A withdrawal has three dangers: a duplicate request, spending one balance twice, and a crash between signing and sending. There is a remedy for each.

For duplicates, each request carries an {{< term "idempotency-key" "idempotency key" >}}, unique per user. A client would generate one key per user click, for example. If the same key arrives again, no new request is created and the earlier one is returned. The insert, the risk check (100 DEMO per request here), locking the user's account row, checking the balance and moving the amount to `withdrawals:pending` all happen in one database transaction, as in [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/). The row lock is what keeps two different requests from spending the same balance at the same time. Condensed:

```
INSERT INTO withdrawals (...) ... ON CONFLICT (user_id, idem_key) DO NOTHING RETURNING id
// no row: return the existing request (error if amount or address differ)
SELECT 1 FROM accounts WHERE name = $1 FOR UPDATE
post(ctx, tx, fmt.Sprintf("withdrawal:%d:reserve", id),
	line{acct, neg(amt)}, line{"withdrawals:pending", amt})
```

The amount first moves from the user's account to `withdrawals:pending`. That is, it is "reserved" before anything touches the chain.

For signing and sending, `send` takes the next {{< term "nonce" "nonce" >}} from a locked `hot_wallet` row. This is the nonce manager from the go-ethereum post, shared by all workers. It signs from the {{< term "hot-wallet" "hot wallet" >}} (the wallet whose key is online) and stores the signed bytes **before broadcasting**. So after a crash the same bytes are re-broadcast, with the same hash, not a second transaction. `track` settles the withdrawal after N confirmations, or releases the reservation if the receipt shows a failure (that branch is in the code but did not trigger in this run).

First the same request twice at once (`-parallel 2`, like a double click). `$A3` is the destination:

```
$ X withdraw -user alice -to $A3 -amount 30 -key w-1 -parallel 2
withdrawal #1 already exists: reserved
withdrawal #1 created: reserved
$ X send
withdrawal #1 signed: nonce 0, tx 0xc295cb2f
withdrawal #1 sent: 0xc295cb2f
$ X send
nothing to send
$ cast rpc anvil_mine 2
$ X track
withdrawal #1: confirmed via 0xc295cb2f (3/3)
$ cast nonce $HOT
1
$ X withdraw -user alice -to $A3 -amount 30 -key w-1
withdrawal #1 already exists: confirmed
$ X withdraw -user alice -to $A3 -amount 150 -key w-2
withdrawal #4 created: rejected (over the per-withdrawal limit)
$ X withdraw -user alice -to $A3 -amount 95 -key w-3
withdrawal #5 created: rejected (insufficient balance 90)
$ X withdraw -user alice -to $A3 -amount 31 -key w-1
error: idempotency key "w-1" reused with a different request
$ X withdraw -user alice -to $A3 -amount 10 -key w-4
withdrawal #7 created: reserved
```

Line by line:

- **Two simultaneous requests:** one was `created` and the other found that it already existed. Which of the two prints "created" can change between runs; what matters is that only one withdrawal was made.
- **First `send`:** the withdrawal was signed with nonce 0 and sent. The transaction hash may differ in your run, because it depends on the fee at that moment. **The second `send`** had nothing to send.
- **`track`:** after two more blocks the transaction has three confirmations and the withdrawal is `confirmed`. `cast nonce $HOT` is 1: only one transaction went on chain.
- **The repeated request with the same key and amount:** returns the earlier withdrawal with its status (`confirmed`).
- **150 DEMO:** above the limit of 100, rejected.
- **95 DEMO:** after reserving 30, alice has only 90, rejected.
- **Key `w-1` with amount 31:** the same key with a different request is an error. A key must be tied to one specific request.
- **The last one:** 10 DEMO under a new key was reserved.

The withdrawal numbers have gaps (#1, then #4, #5, #7). The reason: a conflicting insert also consumes a value from the database sequence, even though no row is created. Compare [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/).

## A stuck withdrawal

Let us look at withdrawal #7. If a transaction is sent with a low fee and never enters a block, we must not leave the user waiting, and we must not throw the nonce away either, because later nonces queue up behind it. The right move is to send the same transaction again with the **same nonce** and a higher fee. This is {{< term "replace-by-fee" "replace-by-fee" >}}, as in [The mempool, fees and transaction selection](/posts/bc-mempool-fees/). Whichever of the two versions gets mined, the nonce is used once.

anvil refused a fee cap below the base fee, so I simulated a stuck transaction by turning automine off: transactions then wait in the queue until I mine a block myself. `bump` re-signs the same call with doubled fees:

```
$ cast rpc evm_setAutomine false
$ X send
withdrawal #7 signed: nonce 1, tx 0x45267a5e
withdrawal #7 sent: 0x45267a5e
$ X track
withdrawal #7: no receipt for 1 attempt(s) at nonce 1
$ X bump -id 7
withdrawal #7: replaced 0x45267a5e with 0x27b7e080, nonce 1, tip 1 -> 2 gwei
$ cast rpc txpool_status
{"pending":"0x1","queued":"0x0"}
$ cast rpc anvil_mine 1
$ cast rpc evm_setAutomine true
$ cast rpc anvil_mine 2
$ X track
withdrawal #7: confirmed via 0x27b7e080 (3/3)
$ cast nonce $HOT
2
```

- **`send`:** withdrawal #7 was signed with nonce 1 and sent, but automine is off, so it does not enter a block.
- **`track`:** there is no receipt. The withdrawal is stuck.
- **`bump`:** the same transaction with the same nonce was sent with a tip of 2 gwei (instead of 1) and took the old one's place.
- **`txpool_status`:** only one transaction is in the queue (`pending: 1`), so the new version replaced the old one; they are not two.
- **The end:** a block was mined, three confirmations arrived and `track` marked the withdrawal `confirmed`. The hot wallet's nonce is now 2: two transactions, not three.

`track` looks for the receipt of **every** stored attempt, because any of them may be the one that got mined.

## Hot, cold and sweeping

No code for this part. {{< term "sweeping" "Sweeping" >}} means gathering deposits from many user addresses into the exchange's own wallets. For an ERC-20 token each deposit address first needs ETH for gas to be able to send the token. The hot wallet holds only what the coming withdrawals need. The rest sits in a {{< term "cold-wallet" "cold wallet" >}}, which refills the hot wallet with transfers that people approve by hand. [The Binance hack post](/posts/binance-hack-hot-wallet-2026/) shows why whatever can ask the hot wallet to sign matters as much as its key.

## Rules that keep the ledger right

- Credit only at N confirmations, and still keep an alert for a reorg deeper than N. Never reverse credited money automatically.
- One process owns a hot wallet's nonces. A manual `cast send` from the same key breaks the counter.
- Persist the signed transaction before broadcasting. A retry must resend it, not sign a new one.
- The ledger total must be zero. Also reconcile it with the real on-chain balances (reconciliation): compare the wallets' balances on chain with what the ledger says the exchange owes, and investigate every difference. I did not write that comparison in the demo.

## What's next

**Blockchain capstone with Go and Rust**: it moves this backend's signing key into a separate signer.
