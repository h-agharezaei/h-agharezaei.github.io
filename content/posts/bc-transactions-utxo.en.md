+++
date = '2026-11-06T18:00:00+03:30'
draft = false
title = 'Transactions and the UTXO model'
description = 'UTXO transactions in Go: inputs, outputs, sighash, txid, coinbase and fees, with a double spend, a forged signature and an overspend rejected.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "utxo", "transactions", "bitcoin"]
cover = { image = "/images/covers/bc-transactions-utxo.png", alt = "Transactions and the UTXO model", hiddenInSingle = true }
+++

Open your wallet. You have a 50 note and you want to pay 30. You do not tear the note in half; you hand over the whole note and get 20 back. Now a question: where is your "balance" written down? Nowhere. Your balance is simply the sum of the notes you have in your wallet right now.

Bitcoin works exactly like this, and this post is about that model. The blocks we built in [Merkle trees and inclusion proofs](/posts/bc-merkle-trees-proofs/) still hold plain strings like `"alice -> bob: 10"`, which anyone can write. In the [previous post](/posts/bc-keys-ecdsa-addresses/) we built the `wallet` package, which signs a 32-byte hash. Now it is time to put the two together and replace those strings with real transactions. We want to answer three questions: who owns each coin, who is allowed to spend it, and what a node checks before it accepts a transaction.

The model is called {{< term "utxo" "UTXO" >}}, short for Unspent Transaction Output. What that means becomes clear a few sections down. One note on the name: a "transaction" in a database, as in [Transactions and ACID](/posts/db-transactions-acid/), is a completely different thing that just shares the word.

The code in this post continues the `toychain` module from the Merkle post. I took a copy of it and also copied the `wallet` package into it, in a `wallet/` folder, so everything is one module. I added one helper to `wallet`: `AddressBytes`, which returns the address as raw 20 bytes.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example. The keys are derived from words like "alice", so they are public; they were never funded and exist only for this demo.

## Notes instead of balances

In the UTXO model there is no table called "account balances". What exists are **outputs**. Each output is like a banknote: an amount and an owner. For example "50 coins, owned by this address".

A transaction does two things:

- It **spends** some earlier outputs. These are the transaction's **inputs**. Each input says "I am spending output number such-and-such of that earlier transaction".
- It creates **new** outputs, owned by the new owners.

As long as an output has not been spent, it is "unspent": that is a UTXO. Once it is spent, it is out of the game and can never be spent again. Alice's balance is the sum of all unspent outputs whose owner is Alice.

In Go it takes this shape:

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

Reading from the bottom up:

- `TxOut` is the banknote: an amount (`Value`) and the owner's 20-byte address (`Owner`).
- `OutPoint` is the location of an output: the ID of the transaction that created it (`TxID`) and its number in that transaction's list of outputs (`Index`).
- `TxIn` is an input. `Prev` says which output it spends. `PubKey` is the public key of whoever is spending, and its hash must equal the address of the output's owner. `Sig` is their signature. Remember from the previous post that you cannot get a public key back from an address, which is why the public key travels inside the input.

Like a banknote, an output is always spent **whole**. Say Alice has a 50-coin output and wants to give Bob 30. Her transaction has one input (those 50 coins) and two outputs: 30 for Bob and 15 for herself. That second output is called **change**, just like the money you get back from a shopkeeper.

But 30 and 15 make 45, not 50. Where did the other 5 go? That is the **fee**, and it goes to whoever builds the block. The interesting part is that the fee is not written anywhere in the transaction. It is just the difference:

```
fee = sum(inputs) - sum(outputs)
```

This matters later, when we want to catch tampering.

## What is signed, and what the transaction ID is

To sign a transaction and to give it an ID, we first have to turn it into bytes. As we saw in [Hashes, blocks and the chain](/posts/bc-hashes-blocks-chain/), that conversion has to be canonical: one transaction must always give exactly the same bytes. The method is the same as there: first the number of inputs, then each input with its fields in a fixed order, then the number of outputs and the outputs themselves. Public keys and signatures do not have a fixed length, so each is preceded by its length, so that it is clear where it ends.

Two different hashes come out of those bytes:

```go
func (tx Tx) ID() Hash { return Sum(tx.Encode()) }

func (tx Tx) SigHash() Hash {
	return Sum(append([]byte{0x02}, tx.encode(false)...))
}
```

- **`ID`**, the **txid**, is the transaction's identifier, and it is built from **all** the bytes, signatures included. Inputs of later transactions point to this transaction's outputs by this ID.
- **`SigHash`** is what gets signed. It is called the {{< term "sighash" "sighash" >}}. It covers every input and output, but writes the signatures as empty (`encode(false)`). The reason is simple: a signature cannot sign itself, because until you have made the signature you do not know what its bytes are.

There is a subtle detail here. The txid covers the signatures. In the previous post we saw that every ECDSA signature also has a valid second form. If that second form were accepted, anyone could swap the signature and change the txid without changing anything else in the transaction. That is {{< term "signature-malleability" "malleability" >}}. This design is only safe because `wallet.Verify` rejects signatures with a high `s`.

The `0x02` prefix is the same domain separation as in the Merkle post: tree leaves start with `0x00`, inner nodes with `0x01`, and the sighash with `0x02`. That way none of the three kinds of hash can be mistaken for another.

## Where new coins come from

So far every transaction only moves existing coins. But where did the first coins come from? The answer is the {{< term "coinbase-transaction" "coinbase transaction" >}}. This special transaction is always the first transaction of a block and creates new coins. The block's builder pays it to themselves; it is the reward for building the block.

A coinbase has no earlier output to spend. In our design it has one fake input: a `TxID` of all zeros, and the block height in place of `Index`. Why the height? Because if two blocks had coinbases paying the same amount to the same address, without that number their bytes would be identical and they would get the same ID. With the height, every coinbase has its own ID.

A coinbase has a cap too: it may pay at most `BlockReward` (50 coins here) plus the sum of the fees of the transactions in the same block.

## The UTXO set and checking a block

So what is the whole state of the ledger? Just a map of every unspent output:

```go
type UTXOSet map[OutPoint]TxOut
```

The map key is the output's location and the value is the output itself. Each address's balance is the sum of the outputs owned by that address.

When a new block arrives, `ApplyBlock` checks it. For each non-coinbase transaction it asks, in this order:

1. Does each input point to an output that is in the set? If not, it either never existed or has already been spent.
2. Has this output not already been spent **in this same block**?
3. Does the hash of the input's public key equal the output's owner?
4. Does the {{< term "digital-signature" "signature" >}} over the sighash verify with that key?
5. Is the sum of the inputs at least the sum of the outputs? (And does no sum overflow a `uint64`?)

If everything is fine, it removes the spent outputs from the set and adds the new ones. One important point: `ApplyBlock` does all this on a **copy** of the set. If even one transaction fails along the way, the copy is thrown away and the original set is untouched. Either the whole block is accepted, or none of it.

## A payment with change

Now let's run the banknote example. `go run ./cmd/toychain pay` builds a chain whose genesis coinbase pays Alice 50 coins. Then Alice pays Bob 30 and keeps 15 as change. We call the builder of the next block `miner`:

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

Each row of the UTXO set has the form `txid:index  amount  owner`. Line by line:

- **`after genesis`:** there is a single output: output 0 of the genesis coinbase, 50 coins, owned by Alice.
- **The `tx` line:** Alice's transaction. It is 233 bytes: 4 bytes for the input count, 169 bytes for the single input (32 bytes of txid, 4 bytes of index, and a 65-byte public key and 64-byte signature, each preceded by a 2-byte length), 4 bytes for the output count, and two 28-byte outputs (8 bytes of amount and 20 bytes of address). The fee is `5`, and `err <nil>` means the transaction is valid.
- **`block 1: 2 txs`:** block 1 has two transactions: the block builder's coinbase and Alice's transaction.
- **`after block 1`:** the 50-coin genesis output is gone; it has been spent. In its place there are three new outputs. Bob's 30 and Alice's 15 both start with the txid of Alice's transaction (`ef4d…`), numbered 0 and 1. The miner got 55: the 50-coin block reward plus the 5-coin fee.
- **`balances`:** the balances are simply sums over these outputs.
- **`validate: <nil>`:** the whole chain was checked again from the start and had no problem.

## Double spend: one coin, twice

Now the first attack. The core problem of any digital money is that data can be copied. What stops Alice from spending one coin twice, to two different people? This is called a {{< term "double-spend" "double spend" >}}.

`go run ./cmd/toychain double` builds two transactions that both spend Alice's 50 coins: one gives everything to Bob, the other everything to the miner. Both carry Alice's valid signature. Then it feeds them to the chain in several ways:

```
both valid alone: <nil> <nil>
same block: block 1: tx 2: input 0: output spent twice in one block
block 1 with one of them: <nil>
the other in block 2: block 2: tx 1: input 0: input is unknown or already spent
replay toBob in block 2: block 2: tx 1: input 0: input is unknown or already spent
chain length: 2
```

- **The first line:** each transaction on its own is perfectly valid. Neither has a forged signature or a wrong amount.
- **`same block`:** when both are in one block, the second one (`tx 2`; transaction 0 is the coinbase) is rejected, because the same output was already spent in that block. The whole block is rejected.
- **`block 1 with one of them`:** block 1 is accepted with only the payment to Bob.
- **`the other in block 2`:** now the payment to the miner is rejected in block 2, because the output is no longer in the UTXO set.
- **`replay toBob`:** even sending **the same** confirmed transaction again is rejected, for the same reason. An output that has been spent once is gone for good.
- **`chain length: 2`:** the chain holds only genesis and block 1.

So the UTXO model catches double spending by itself. But one question remains: if two nodes see two conflicting transactions at the same time, which one wins? That is no longer a validation question, it is a consensus question, which comes in later posts.

## Forged signatures

The next attack: Mallory wants to spend Alice's coin. `go run ./cmd/toychain forge` tries four of her attempts:

```
alice's key, mallory's signature: input 0: bad signature
mallory's key on alice's coin:   input 0: public key does not match the output owner
output rewritten after signing:  input 0: bad signature
change lowered after signing:    input 0: bad signature
```

- **First attempt:** Mallory puts Alice's public key in the input so the owner check passes, but signs with her own key. The signature does not match Alice's key.
- **Second attempt:** Mallory uses her own public key and signs correctly. The signature is fine, but the hash of her key is not the address of the coin's owner.
- **Third attempt:** Alice signs a proper 10-coin payment to Bob, and someone along the way replaces Bob's address with Mallory's. Because the outputs are part of the sighash, the sighash changes and Alice's signature is no longer valid for it.
- **Fourth attempt:** this time nobody touches the addresses; someone only lowers Alice's change from 40 to 1.

The last line is the most interesting. Remember that the fee is not written anywhere and is just the difference between inputs and outputs? So lowering the change raises the fee from 0 to 39 coins, and that money goes to the block builder. If the fee were a separate field that was not signed, this attack would work. But because every output is signed, changing the change breaks the signature too, and it is caught.

## Overspending and fees

The last group checks the amounts. `go run ./cmd/toychain overspend`:

```
50 in, 60 out: outputs exceed inputs: in 50, out 60
50 in, 50 out: fee 0, err <nil>
50 in, 1 out:  fee 49, err <nil> (forgot the change)
coinbase takes 51 with 0 fees: block 1: tx 0: coinbase pays more than reward + fees or has the wrong height
```

- **The first line:** you cannot create 60 coins of outputs from 50 coins of inputs. Rejected.
- **The second line:** inputs and outputs are equal, the fee is zero, and the transaction is valid.
- **The third line:** Alice wanted to give Bob one coin and forgot to create the change output. This transaction is **valid**, and 49 coins of fee go to the block builder. The system cannot tell whether this is a mistake or a very generous fee.
- **The last line:** the block builder paid themselves 51 in the coinbase, while the reward is 50 and there are no fees. The block is rejected.

The tests also cover two more cases: spending an output created earlier in the same block (which is allowed), and tampering with a confirmed transaction. All passed:

```
ok  	toychain/chain	0.413s
?   	toychain/cmd/toychain	[no test files]
ok  	toychain/wallet	(cached)
```

I fixed one more thing at this stage. In the Merkle post we saw that the header did not commit to the number of transactions, so a proof could lie about the count. Now the {{< term "block-header" "header" >}} has a `TxCount` field, and `VerifyInclusion` takes the count from the header, not from whoever sends the proof.

## Validation traps

- **Sign everything that matters.** Anything left outside the sighash can be changed by anyone along the way, and the signature still looks valid. Mallory's third and fourth attempts failed only because the outputs were signed.
- **Compute the fee as a difference and check for overflow.** A sum of large `uint64` values can pass the maximum and wrap around to a small number. Then a transaction that spends far more than its inputs could look valid. That is why our code does every sum with `bits.Add64` and rejects an overflow.
- **Check a whole block on a copy of the state, never in place.** If the fifth transaction of a block is bad and you have already applied the first four directly to the real state, your ledger is now half-updated and no longer matches the other nodes.
- **Real Bitcoin is more complex.** As far as I know, Bitcoin locks outputs with a small script, not just an address, and signs a separate sighash for each input. I implemented neither here.

## Exercise

1. Allow the coinbase to have several outputs, and write a test showing that their sum is still capped.
2. Add a `Locktime` field: a transaction is invalid before that height. Make sure the field is signed; otherwise, who could change it?
3. Write `Select(utxo, owner, amount)`, which picks enough of one owner's outputs and builds the change output.

## What's next

The next post is "The account model, nonces and replay protection". Instead of banknotes, Ethereum keeps one balance per address. There is no output there that gets spent and disappears, so we need a different way to stop a transaction from being sent twice.
