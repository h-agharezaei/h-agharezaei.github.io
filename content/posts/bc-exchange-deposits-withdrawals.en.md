+++
date = '2027-07-13T10:00:00+03:30'
draft = false
title = 'Exchange engineering: deposits, withdrawals, confirmations and reorgs'
seoTitle = 'Exchange deposits, withdrawals and reorgs in Go'
description = 'Exchange deposits and withdrawals in Go and Postgres: a deposit state machine, a double-entry ledger, a real reorg, idempotency keys and fee bumps.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "postgres", "exchange"]
cover = { image = "/images/covers/bc-exchange-deposits-withdrawals.png", alt = "Exchange engineering: deposits, withdrawals, confirmations and reorgs", hiddenInSingle = true }
+++

The previous post, [Zero-knowledge proof basics in Rust](/posts/bc-zero-knowledge-rust/), was cryptography. This one is plain backend work: turning chain events into balances, and balances back into transactions.

I copied the module from [Events and building an indexer with Go and Postgres](/posts/bc-event-indexer-go/), grew its indexer into a deposit scanner and added a ledger and withdrawals. Addresses come from [HD wallets: BIP-32, BIP-39 and BIP-44 in Rust](/posts/bc-hd-wallets-rust/), signing and nonces from [Talking to Ethereum from Go with go-ethereum](/posts/bc-go-ethereum-client/). This is a teaching design, not a complete exchange, and says nothing about any real exchange's internals.

> Go 1.27 on macOS (arm64), go-ethereum v1.17.10, pgx v5.11.0, PostgreSQL 18.3 from `embedded-postgres`. A fresh anvil on `127.0.0.1:8547` with the deploy script from the tokens post. Every key and address is an anvil **public test account**. Temp paths are written `<tmp>`.

## Deposit addresses

Each user gets a {{< term "deposit-address" "deposit address" >}}. In production I would derive it as `xpub/0/index` from an {{< term "xpub" "xpub" >}}, as in BC20, so the deposit service holds no private key; here anvil accounts 1 and 2 stand in for alice and bob. The scanner asks only for transfers *to* them:

```go
Topics: [][]common.Hash{{transferTopic}, nil, topicTo}, // Transfer(any, ours)
```

## Deposit states and the ledger

A deposit is a small {{< term "state-machine" "state machine" >}}: `seen` when the log first appears, `pending` while it has fewer than N {{< term "confirmation" "confirmations" >}}, `credited` at N, and `orphaned` if a {{< term "chain-reorganization" "reorg" >}} removes it first:

```go
var allowed = map[string][]string{
	"seen":     {"pending", "credited", "orphaned"},
	"pending":  {"pending", "credited", "orphaned"},
	"orphaned": {"seen"}, // the same log came back in another block
	"credited": {},       // final; a reorg past N needs a human
}
// move(): UPDATE deposits SET status = $to WHERE tx_hash = .. AND log_index = .. AND status = $from
```

The deposit row is keyed by `(tx_hash, log_index)`, like BC19. Money lives in a {{< term "double-entry-bookkeeping" "double-entry" >}} ledger: every journal's entries sum to zero, `external` is the outside world's side, and its `ref` (`deposit:<tx>:<log index>`) is unique, so crediting twice is impossible:

```go
posted, err := post(ctx, tx, fmt.Sprintf("deposit:%s:%d", d.hash, d.idx),
	line{"external", neg(amt)},
	line{"user:" + d.user, amt})
// then move(..., "credited") in the same DB transaction
```

## A reorg before N, then N reached

`$T` is the token, `$A0` the sender, `$ALICE` her deposit address, N = 3 (confirmations = head − block + 1). As in BC19, anvil's snapshot and revert make the reorg:

```
$ cast rpc evm_snapshot
"0x0"
$ cast send $T "transfer(address,uint256)" $ALICE 100ether --unlocked --from $A0   # block 5
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 5, cursor -1, N 3
deposit alice 100 DEMO tx 0x1ee92a01 block 5: seen
deposit alice 100 DEMO: seen -> pending (1/3)
$ cast rpc anvil_mine 1
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 6, cursor 5, N 3
deposit alice 100 DEMO: pending -> pending (2/3)
$ cast rpc evm_revert 0x0
true
$ cast rpc anvil_mine 3
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
reorg: fork point 4, dropping blocks 5-6
deposit alice 100 DEMO tx 0x1ee92a01: pending -> orphaned
head 7, cursor 4, N 3
$ go run ./cmd/exchange -pgdir <tmp>/pg balances
external             0 DEMO
user:alice           0 DEMO
...
(cast output trimmed)
```

Never credited. Here the transaction vanished; in a real reorg it may return in another block, the `orphaned -> seen` edge. A second deposit of 120 DEMO lands in block 8:

```
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3
head 10, cursor 8, N 3
deposit alice 120 DEMO: pending -> credited (3/3), journal posted: true
$ go run ./cmd/exchange -pgdir <tmp>/pg scan -confirmations 3 -rewind 4
head 10, cursor 4, N 3
$ go run ./cmd/exchange -pgdir <tmp>/pg balances
external             -120 DEMO
user:alice           120 DEMO
user:bob             0 DEMO
withdrawals:pending  0 DEMO
sum of all accounts: 0
(cast send and the first scan, 1/3, trimmed)
```

The rewound scan re-read block 8 and did nothing.

## Withdrawals

A request carries an {{< term "idempotency-key" "idempotency key" >}}, unique per user. Insert, risk check (100 DEMO per request here), lock the user's account row, check the balance and move the amount to `withdrawals:pending` all happen in one DB transaction, as in [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/). Condensed:

```
INSERT INTO withdrawals (...) ... ON CONFLICT (user_id, idem_key) DO NOTHING RETURNING id
// no row: return the existing request (error if amount or address differ)
SELECT 1 FROM accounts WHERE name = $1 FOR UPDATE
post(ctx, tx, fmt.Sprintf("withdrawal:%d:reserve", id),
	line{acct, neg(amt)}, line{"withdrawals:pending", amt})
```

`send` takes the next {{< term "nonce" "nonce" >}} from a locked `hot_wallet` row (BC17's nonce manager, shared by all workers), signs from the {{< term "hot-wallet" "hot wallet" >}} and stores the signed bytes before broadcasting, so a crash means re-broadcasting the same hash. `track` settles after N confirmations, or releases the reservation on a failed receipt (coded, not triggered in this run). The same request twice at once:

```
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 30 -key w-1 -parallel 2
withdrawal #1 already exists: reserved
withdrawal #1 created: reserved
$ go run ./cmd/exchange -pgdir <tmp>/pg send
withdrawal #1 signed: nonce 0, tx 0x66fc1a20
withdrawal #1 sent: 0x66fc1a20
$ go run ./cmd/exchange -pgdir <tmp>/pg send
nothing to send
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #1: confirmed via 0x66fc1a20 (3/3)
$ cast nonce $HOT
1
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 95 -key w-3
withdrawal #5 created: rejected (insufficient balance 90)
$ go run ./cmd/exchange -pgdir <tmp>/pg withdraw -user alice -to $A3 -amount 31 -key w-1
error: idempotency key "w-1" reused with a different request
(other runs trimmed)
```

One on-chain transaction. Ids skip because conflicting inserts still consume sequence values. Compare [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/).

## A stuck withdrawal

anvil refused a fee cap below the base fee, so I simulated a stuck transaction by turning automine off. `bump` re-signs the same call with the **same nonce** and doubled fees, like {{< term "replace-by-fee" "replace-by-fee" >}} in [The mempool, fees and transaction selection](/posts/bc-mempool-fees/):

```
$ cast rpc evm_setAutomine false
$ go run ./cmd/exchange -pgdir <tmp>/pg send
withdrawal #7 signed: nonce 1, tx 0x919ab50e
withdrawal #7 sent: 0x919ab50e
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #7: no receipt for 1 attempt(s) at nonce 1
$ go run ./cmd/exchange -pgdir <tmp>/pg bump -id 7
withdrawal #7: replaced 0x919ab50e with 0xd822743e, nonce 1, tip 1 -> 2 gwei
$ cast rpc txpool_status
{"pending":"0x1","queued":"0x0"}
$ cast rpc anvil_mine 1
$ cast rpc evm_setAutomine true
$ cast rpc anvil_mine 2
$ go run ./cmd/exchange -pgdir <tmp>/pg track
withdrawal #7: confirmed via 0xd822743e (3/3)
$ cast nonce $HOT
2
(withdraw command and one track call trimmed)
```

`track` checks every stored attempt; any of them may be the one mined.

## Hot, cold and sweeping

No code for this part. {{< term "sweeping" "Sweeping" >}} moves deposits from many addresses into exchange wallets; for an ERC-20 each deposit address first needs ETH for gas. The hot wallet holds only what withdrawals need soon; a {{< term "cold-wallet" "cold wallet" >}} keeps the rest and refills it by manually approved transfers. [The Binance hack post](/posts/binance-hack-hot-wallet-2026/) shows why whatever can ask the hot wallet to sign matters as much as its key.

## A few things to watch

- Credit only at N, and still keep an alert for a reorg deeper than N; never reverse credited money automatically.
- One process owns a hot wallet's nonces. A manual `cast send` from the same key breaks the counter.
- Persist the signed transaction before broadcasting; a retry must resend, not re-sign.
- The ledger total must be zero; also reconcile it with on-chain balances.

## Exercise

1. Add a reconciliation command: hot wallet plus deposit addresses on-chain versus `user:*` plus `withdrawals:pending`.
2. Trigger the failure path: make a withdrawal revert on-chain and show the reservation released.
3. Credit large deposits only after a higher N.

## What's next

Next post: **Blockchain capstone with Go and Rust**.
