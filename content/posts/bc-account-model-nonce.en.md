+++
date = '2026-11-07T18:00:00+03:30'
draft = false
title = 'The account model, nonces and replay protection'
description = 'Account model in Go: balances and nonces per address, replayed and out-of-order transactions rejected, chain ID against cross-chain replay, vs UTXO.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "ethereum", "nonce", "replay-protection"]
cover = { image = "/images/covers/bc-account-model-nonce.png", alt = "The account model, nonces and replay protection", hiddenInSingle = true }
+++

In Ethereum a signed "pay Bob 30" stays valid after it runs; without extra state, anyone could submit it again. That is a {{< term "replay-attack" "replay attack" >}}, the same problem as a redelivered message in [Idempotency and exactly-once in JetStream](/posts/nats-jetstream-idempotency/), with money attached. The {{< term "utxo" "UTXO" >}} model of the [previous post](/posts/bc-transactions-utxo/) avoided it: a payment consumed whole outputs, so a resend found its input gone. Ethereum keeps per-address balances instead.

I copied last post's `toychain` module and added a package `account`. The blocks still carry UTXO transactions, and the next posts keep it that way: the account model here is a separate state I did not wire into blocks, to compare the two designs.

> Go 1.27 on macOS (arm64). Local example code. Keys are derived from words like "alice": public, never funded, demo only.

## An account transaction

In the {{< term "account-model" "account model" >}} the whole ledger is two maps:

```go
type State struct {
	ChainID  uint64
	Balances map[chain.Address]uint64
	Nonces   map[chain.Address]uint64 // next expected nonce per sender
}

type Tx struct {
	ChainID uint64
	Nonce   uint64
	To      chain.Address
	Value   uint64
	Fee     uint64
	PubKey  []byte // the sender is derived from this
	Sig     []byte
}
```

There is no `From` field; the sender is the address of `PubKey`, and the signature must verify with it. According to the Ethereum docs, real transactions omit the public key and recover it from the signature; my `wallet` package does not do recovery, so I send it. The sighash covers every field except the signature, `ChainID` and `Nonce` included.

## Nonce: no replay, no reordering

Each sender has a counter. A transaction must carry exactly the next value, and applying it increments the counter:

```go
switch want := s.Nonces[from]; {
case tx.Nonce < want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceUsed, tx.Nonce, want)
case tx.Nonce > want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceGap, tx.Nonce, want)
}
```

Here the {{< term "nonce" "nonce" >}} is a sequence number, not the random ECDSA nonce from the keys post. `go run ./cmd/toychain account`: Alice starts with 100 and pays Bob 30 with a fee of 1:

```
tx nonce 0: 185 bytes, apply: <nil>
  alice 69 (nonce 1), bob 30, miner 1
replay the same tx: nonce already used: got 0, next is 1
nonce 2 before 1:   nonce too high: earlier nonce missing: got 2, next is 1
nonce 1:            <nil>
nonce 2 now:        <nil>
  alice 57 (nonce 3), bob 40, miner 3
```

The replay fails: nonce 0 is used. I chose to reject a gap, not queue it: nonce 2 fails until nonce 1 arrives. As far as I know, Ethereum clients hold such transactions in the mempool until the gap is filled; consensus rules still apply them strictly in order.

## Chain ID: no replay on another chain

The nonce stops replays on the same chain. If a chain splits, or a test network shares keys with the main one, the same nonce is valid on both. According to EIP-155, Ethereum puts a {{< term "chain-id" "chain ID" >}} in the signed data. `go run ./cmd/toychain crosschain` runs two states with the same history and different IDs:

```
on chain 1: <nil>
same tx on chain 2: transaction is for another chain: tx 1, this chain 2
chain ID edited to 2: bad signature
  alice 100 (nonce 0), bob 0, miner 0
```

Chain 2 refuses it, and changing the field breaks the {{< term "digital-signature" "signature" >}}.

## Same payments, both models

`go run ./cmd/toychain compare` sends ten payments of 1 coin from Alice to Bob in each model, all in one block:

```
utxo block: <nil>
utxo:    12 state entries, 2330 tx bytes
account block: <nil>
account: 2 balances + 1 nonces, 1850 tx bytes
```

UTXO keeps 10 outputs for Bob, Alice's change and the miner's coinbase. The account model keeps two balances and one nonce. Each account transaction is 185 bytes against 233 for one input and two outputs; both carry a 65-byte public key, so do not read these as Bitcoin or Ethereum sizes.

## UTXO vs account

| | UTXO | Account |
|---|---|---|
| State | unspent outputs (12 here) | balance and nonce per address (3 here) |
| Replay protection | the spent output is gone | nonce, plus chain ID across chains |
| Balance lookup | sum over outputs | one map read |
| Wallet work | pick outputs, build change | none |
| Conflicts | only if two txs share an input | same-sender txs run in nonce order |
| Privacy habit | change can go to a fresh address | one address collects its history |

In UTXO a {{< term "double-spend" "double spend" >}} is visible from the inputs alone, so independent transactions can be checked separately. In the account model any two transactions touching the same balance must be applied in order. The account model is simpler for wallets, and it is what Ethereum contracts build on.

## Nonce pitfalls

- Put the chain ID and nonce inside the signed bytes; a field outside the sighash protects nothing.
- Reject or queue nonce gaps, but never apply out of order.
- A stuck low nonce blocks every later transaction of that sender.
- Apply a block on a copy, as with the UTXO set.

## Exercise

1. Add a `MaxNonceGap` and queue transactions up to it, applying them when the gap closes.
2. Replace `PubKey` with a 65-byte recoverable signature (the library's `ecdsa.SignCompact`) and derive the sender from it.
3. Add a test that one signed transaction with chain ID 0 is rejected by both chains.

## What's next

Next post: **Proof of work, difficulty and mining**. Blocks get expensive to make, and that decides which chain wins.
