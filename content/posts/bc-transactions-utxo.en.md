+++
date = '2026-11-06T18:00:00+03:30'
draft = false
title = 'Transactions and the UTXO model'
description = 'UTXO transactions in Go: inputs, outputs, sighash, txid, coinbase and fees, with a double spend, a forged signature and an overspend rejected.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "utxo", "transactions", "bitcoin"]
cover = { image = "/images/covers/bc-transactions-utxo.png", alt = "Transactions and the UTXO model", hiddenInSingle = true }
+++

In the [previous post](/posts/bc-keys-ecdsa-addresses/) we built a `wallet` package that signs a 32-byte hash. Our blocks from [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/) still carry plain byte strings like `"alice -> bob: 10"`, which anyone could write. This post replaces them with real transactions: who owns a coin, who may spend it, and what a node checks. This is Bitcoin's model, the {{< term "utxo" "UTXO" >}} model. Database transactions from [Transactions and ACID](/posts/db-transactions-acid/) are a different thing that shares the name.

I copied the `toychain` module from the Merkle post and copied the `wallet` package into it as `wallet/`, so it is one module now. I added one helper to `wallet`: `AddressBytes`, the raw 20-byte address.

> Go 1.27 on macOS (arm64). Local example code. The keys are derived from words like "alice"; they are public, never funded, and only for this demo.

## Inputs and outputs

There are no balances, only outputs: "50 coins, owned by this address". A transaction consumes earlier outputs and creates new ones:

```go
type OutPoint struct {
	TxID  Hash
	Index uint32
}

type TxIn struct {
	Prev   OutPoint
	PubKey []byte // must hash to the owner of Prev
	Sig    []byte // 64 bytes, r || s
}

type TxOut struct {
	Value uint64
	Owner Address // 20 bytes
}

type Tx struct {
	Inputs  []TxIn
	Outputs []TxOut
}
```

An output is spent whole. To pay 30 from a 50-coin output, Alice creates two outputs: 30 for Bob and 15 back to herself as change. The missing 5 is the fee: `fee = sum(inputs) - sum(outputs)`.

## What is signed, what is the ID

The encoding is canonical, like the header in [Hashes, blocks and the chain](/posts/bc-hashes-blocks-chain/): counts and fixed-width fields in order, length prefixes for keys and signatures. Two hashes come from it:

```go
func (tx Tx) ID() Hash { return Sum(tx.Encode()) }

func (tx Tx) SigHash() Hash {
	return Sum(append([]byte{0x02}, tx.encode(false)...))
}
```

The {{< term "sighash" "sighash" >}} covers every input and output but writes the signatures as empty, because a signature cannot sign itself. The txid covers everything, signatures included. That is only safe because `wallet.Verify` rejects high-S signatures; otherwise {{< term "signature-malleability" "malleability" >}} would let anyone change the ID. The `0x02` prefix keeps sighashes apart from Merkle leaves (`0x00`) and nodes (`0x01`).

## Coinbase and the UTXO set

New coins come from the {{< term "coinbase-transaction" "coinbase transaction" >}}, the first transaction of every block. It has one fake input with a zero TxID and the block height as index, so two coinbases paying the same owner still get different IDs. It may pay at most `BlockReward` (50) plus the block's fees.

The state is a map:

```go
type UTXOSet map[OutPoint]TxOut
```

`ApplyBlock` works on a copy. For each transaction it checks: every input exists in the set; no output is spent twice in the block; the public key hashes to the output's owner; the {{< term "digital-signature" "signature" >}} over the sighash verifies; `sum(in) >= sum(out)` without overflow. Then it deletes the spent outputs and adds the new ones. Any error discards the copy.

## A payment with change

`go run ./cmd/toychain pay`: genesis pays Alice 50, then she pays Bob 30 with 15 change:

```
after genesis:
  197a84d5374b:0   50  alice
tx ef4d0ece5dfd: 233 bytes, sighash 74a059145008, fee 5, err <nil>
block 1: 2 txs, err <nil>
after block 1:
  569759b941f7:0   55  miner
  ef4d0ece5dfd:0   30  bob
  ef4d0ece5dfd:1   15  alice
balances: alice 15, bob 30, miner 55
validate: <nil>
```

The genesis output is gone and the miner took 50 + 5.

## Double spend

A {{< term "double-spend" "double spend" >}} is two valid signatures over the same coin. `go run ./cmd/toychain double`:

```
both valid alone: <nil> <nil>
same block: block 1: tx 2: input 0: output spent twice in one block
block 1 with one of them: <nil>
the other in block 2: block 2: tx 1: input 0: input is unknown or already spent
replay toBob in block 2: block 2: tx 1: input 0: input is unknown or already spent
chain length: 2
```

Each payment is valid alone; together, the block is rejected. Resending a confirmed transaction fails too: its input is gone. Which of two conflicting payments wins is a consensus question for later posts.

## Forged signatures

`go run ./cmd/toychain forge`, Mallory against Alice's coin:

```
alice's key, mallory's signature: input 0: bad signature
mallory's key on alice's coin:   input 0: public key does not match the output owner
output rewritten after signing:  input 0: bad signature
change lowered after signing:    input 0: bad signature
```

The last line matters: the fee is not a field, it is whatever the outputs leave. Lowering the change raises the fee, and because the outputs are signed, that is caught.

## Overspending and fees

`go run ./cmd/toychain overspend`:

```
50 in, 60 out: outputs exceed inputs: in 50, out 60
50 in, 50 out: fee 0, err <nil>
50 in, 1 out:  fee 49, err <nil> (forgot the change)
coinbase takes 51 with 0 fees: block 1: tx 0: coinbase pays more than reward + fees or has the wrong height
```

Line three is valid: forget the change output and the miner gets it.

Tests also cover spending an output created earlier in the same block and editing a confirmed transaction. While here I also fixed the gap from the Merkle post: the {{< term "block-header" "header" >}} now commits to `TxCount`, and `VerifyInclusion` takes the count from the header, not the prover.

```
ok  	toychain/chain	0.413s
?   	toychain/cmd/toychain	[no test files]
ok  	toychain/wallet	(cached)
```

## A few things to watch

- Sign everything that matters. Anything outside the sighash can be changed by anyone.
- Compute fees as inputs minus outputs, and check for overflow.
- Validate a whole block on a copy of the state, never in place.
- Real Bitcoin differs: as far as I know, it locks outputs with scripts and signs a separate hash per input. I did not implement either.

## Exercise

1. Allow the coinbase to pay several outputs and add a test that their sum is still capped.
2. Add a `Locktime` field: a transaction is invalid before that height. Make sure it is signed.
3. Write `Select(utxo, owner, amount)` that picks outputs and builds the change output.

## What's next

Next post: **The account model, nonces and replay protection**. Ethereum keeps balances instead of outputs, which needs another defence against replays.
