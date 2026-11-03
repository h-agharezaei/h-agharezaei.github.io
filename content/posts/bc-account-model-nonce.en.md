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

Say Alice sends a signed message to the network: "pay Bob 30 coins from my account". The nodes check the signature, it is valid, and 30 coins move from Alice's balance to Bob's. So far so good. But that message is still out there, and its signature is still valid. What if Bob, or anyone else, sends the same message again? The signature has not changed, so it is accepted again, and Alice pays another 30. And again, and again.

This is called a {{< term "replay-attack" "replay attack" >}}: replaying an old, valid message. It is the same problem as a redelivered message in [Idempotency and exactly-once in JetStream](/posts/nats-jetstream-idempotency/), except that this time money is involved.

The {{< term "utxo" "UTXO" >}} model we built in the [previous post](/posts/bc-transactions-utxo/) did not have this problem, and without any extra effort. There, each payment spent a specific output whole. If someone sent the same transaction again, its output no longer existed and the transaction was rejected. But Ethereum uses a different model: for each address it keeps just one balance number. A balance is not spent and gone; it only goes up and down. So here we have to stop replays some other way.

The code in this post continues the `toychain` module from the previous post. I took a copy of it and added a new package called `account`. The chain's blocks still carry UTXO transactions, and the coming posts keep it that way. The account model here is a separate state that I did not wire into the blocks; it exists only so we can see the two designs side by side.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example. The keys are derived from words like "alice", so they are public; they were never funded and exist only for this demo.

## A ledger instead of banknotes

In the previous post we compared UTXO to banknotes. The account model is like a bank account: there is one row per person with a balance, and each payment subtracts from one row and adds to another. This design is called the {{< term "account-model" "account model" >}}, and the whole ledger in it is just two maps:

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

`Balances` is each address's balance. `Nonces` and `ChainID` are the two tools that stop replays; we look at them one by one in the next two sections.

A transaction is also simpler than in UTXO. It has no inputs or outputs. It just says to whom (`To`), how much (`Value`), and what fee (`Fee`). This time the fee is a real field, because there is no longer a "difference between inputs and outputs" for it to come from.

One interesting thing is missing from this struct: a `From` field. We do not write the sender down; we derive it from the public key (`PubKey`). The sender's address is that key's address, and the signature has to verify with that same key. So nobody can build a transaction in someone else's name.

According to the Ethereum docs, a real Ethereum transaction does not send the public key at all. With a slightly different kind of signature, the public key can be reconstructed from the signature and the message. My `wallet` package does not have that ability, so I send the key.

As in the previous post, what gets signed is a sighash: every field except the signature itself. That means `ChainID` and `Nonce` are signed too, and we will soon see why that is vital.

## The nonce: a sequence number per sender

Back to the main problem. How do we make "pay Bob 30 coins" run only once?

Think of a chequebook whose cheques are numbered: 0, 1, 2 and so on. Imagine a bank that only accepts the next cheque: if the last cheque it cashed from you was number 4, it only accepts number 5. Now if someone brings cheque number 4 again, the bank says "that number has already been used".

That is exactly what a {{< term "nonce" "nonce" >}} does in the account model. The network keeps one counter per sender, starting at zero. Each transaction must carry exactly the next number, and executing it increments the counter. Because `Nonce` is inside the sighash, nobody can change the number on a signed transaction.

A note on the name: we met the word nonce in the [keys post](/posts/bc-keys-ecdsa-addresses/) too, but there it was a secret random number inside an ECDSA signature. Here the nonce is a simple, public sequence number. Same name, completely different job.

Checking it takes only a few lines:

```go
switch want := s.Nonces[from]; {
case tx.Nonce < want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceUsed, tx.Nonce, want)
case tx.Nonce > want:
	return fmt.Errorf("%w: got %d, next is %d", ErrNonceGap, tx.Nonce, want)
}
```

`want` is the next expected number. If the transaction's number is lower, it has been used already. If it is higher, one or more earlier transactions have not arrived yet and there is a gap in the numbers. Only if it is exactly equal does the transaction go ahead.

`go run ./cmd/toychain account` tries this. Alice starts with 100 coins and, with nonce zero, pays Bob 30 with a fee of 1. Then she sends the same transaction again. Then she sends two payments of 5 coins, but nonce 2 first and nonce 1 after:

```
tx nonce 0: 185 bytes, apply: <nil>
  alice 69 (nonce 1), bob 30, miner 1
replay the same tx: nonce already used: got 0, next is 1
nonce 2 before 1:   nonce too high: earlier nonce missing: got 2, next is 1
nonce 1:            <nil>
nonce 2 now:        <nil>
  alice 57 (nonce 3), bob 40, miner 3
```

Line by line:

- **The first line:** the transaction is 185 bytes and ran without error.
- **The second line:** Alice went from 100 to 69 (30 for Bob and 1 in fees), Bob has 30, the miner got 1 coin in fees, and Alice's counter is now 1.
- **`replay the same tx`:** the same transaction, with the same valid signature, was rejected: nonce zero has been used and the next number is 1. The replay attack failed.
- **`nonce 2 before 1`:** the transaction with nonce 2 arrived before nonce 1 and was rejected, because there is a gap in the numbers.
- **The next two lines:** now nonce 1 runs, and after it that same nonce-2 transaction is accepted too.
- **The last line:** Alice has 57 coins (69 minus two lots of 5+1), Bob 40, the miner 3, and Alice's counter has reached 3.

I made a design decision here that is worth stating plainly: I **reject** a transaction with a gap instead of holding it until the gap is filled. That is why nonce 2 had to be sent again after nonce 1 arrived. As far as I know, Ethereum clients are friendlier: they keep such a transaction in their waiting area (the mempool) until the gap is filled. But either way, the consensus rules apply transactions strictly in nonce order.

## Chain ID: replay on another chain

The nonce stops replays on **the same** chain. But there is another case. Sometimes two separate chains share a history; for example when a chain splits in two and each branch goes its own way. Or when someone uses the same key on both a test network and the main network. In those cases Alice's balance and nonce may be the same on both chains. So a transaction Alice signed for chain 1 looks perfectly valid on chain 2 as well, and anyone can broadcast it there too.

The fix is to give each chain an identifying number, called a {{< term "chain-id" "chain ID" >}}, and put that number inside the signed data. According to EIP-155, Ethereum does exactly that. Now Alice's signature is valid for one specific chain only.

`go run ./cmd/toychain crosschain` builds two states with exactly the same history, one with chain ID 1 and one with 2. Then it runs a transaction signed for chain 1, first on chain 1 and then on chain 2. Finally it manually changes that transaction's `ChainID` field to 2 and tries again:

```
on chain 1: <nil>
same tx on chain 2: transaction is for another chain: tx 1, this chain 2
chain ID edited to 2: bad signature
  alice 100 (nonce 0), bob 0, miner 0
```

- **The first line:** it ran on its own chain.
- **The second line:** chain 2 rejected it: this transaction belongs to chain 1.
- **The third line:** someone got clever and changed `ChainID` to 2. But `ChainID` is part of the sighash, so the {{< term "digital-signature" "signature" >}} no longer matches.
- **The last line:** chain 2's state is untouched: Alice still has 100 coins and nonce zero.

This is why I said it is vital that `ChainID` and `Nonce` are signed. If either of them were outside the sighash, an attacker would just change it and the signature would still be valid.

## The same payments, in both models

Now that we have both models, let's do the same job with each and see what each one keeps. `go run ./cmd/toychain compare` sends ten payments of 1 coin from Alice to Bob, all in one block, once in the UTXO model and once in the account model:

```
utxo block: <nil>
utxo:    12 state entries, 2330 tx bytes
account block: <nil>
account: 2 balances + 1 nonces, 1850 tx bytes
```

In the UTXO model, each payment creates a 1-coin output for Bob and a change output for Alice. The next payment spends that change. So at the end the UTXO set holds: Bob's ten outputs, Alice's last change, and the block builder's coinbase output. Twelve entries in total.

In the account model there are only three entries: Alice's balance, Bob's balance, and Alice's nonce. The block builder has no entry here, because these ten transactions paid no fee.

The sizes differ too: each account transaction is 185 bytes, and each UTXO transaction with one input and two outputs is 233. But do not read these as the real sizes of Bitcoin or Ethereum transactions. Both of our designs send the full 65-byte public key, and the real formats differ a lot from these.

## UTXO vs account

Now we can put the two models side by side. The numbers in the table come from this demo:

| | UTXO | Account |
|---|---|---|
| State | unspent outputs (12 here) | balance and nonce per address (3 here) |
| Replay protection | the spent output no longer exists | nonce, plus chain ID across chains |
| Balance lookup | sum over outputs | one map read |
| Wallet work | pick outputs, build change | none |
| Conflicts | only if two txs share an input | same-sender txs run in nonce order |
| Privacy | change can go to a fresh address | one address collects its whole history |

Two rows of this table need more explanation.

**Conflicts.** In UTXO, if two transactions share no input, they are fully independent and each can be checked on its own. A {{< term "double-spend" "double spend" >}} is visible from the inputs alone: two transactions that spend the same output. In the account model, any two transactions that touch the same balance depend on each other and must run in order, because the result of the second depends on the first.

**Wallet work.** In UTXO a wallet has to pick suitable outputs and build the change output; that is the `Select` exercise from the previous post. In the account model you just say "30 coins to Bob". This simplicity is one of the reasons Ethereum's smart contracts are built on the account model: a contract, like an account, has a state and a balance.

## Nonce pitfalls

- **Put the chain ID and the nonce inside the signed bytes.** As the `crosschain` demo showed, a field outside the sighash protects nothing; an attacker just changes it.
- **Reject nonce gaps or queue them, but never apply out of order.** If you run nonce 2 before 1, then 1 is "below the next number" and gets rejected, or worse, the payments happen in a different order from what the sender intended.
- **One stuck nonce holds up every later transaction.** If the nonce-5 transaction never runs, for example because its fee was too low, transactions 6, 7 and onward wait too. The sender has to send a new transaction with the same nonce 5.
- **Apply a block to a copy of the state.** Just like the UTXO set: if the last transaction of a block is bad, the earlier ones must not have touched the real state. `ApplyBlock` does exactly that.

## Exercise

1. Add a `MaxNonceGap` and hold transactions with a gap up to that limit, applying them when the gap closes.
2. Replace `PubKey` with a 65-byte recoverable signature (the library's `ecdsa.SignCompact`) and derive the sender from the signature.
3. Write a test showing that a signed transaction with chain ID zero is rejected by both chains.

## What's next

The next post is "Proof of work, difficulty and mining". So far building a block has been free, and anyone could build a chain; there, building a block becomes expensive, and that cost decides which one wins when there are two versions of the chain.
