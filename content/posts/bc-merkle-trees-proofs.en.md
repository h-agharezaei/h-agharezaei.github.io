+++
date = '2026-11-04T18:00:00+03:30'
draft = false
title = 'Merkle trees and inclusion proofs'
description = 'Merkle trees in Go: a block header with a Merkle root, odd leaf counts, leaf and node prefixes against second preimages, and inclusion proofs measured.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "merkle-tree", "hashing", "data-structures"]
cover = { image = "/images/covers/bc-merkle-trees-proofs.png", alt = "Merkle trees and inclusion proofs", hiddenInSingle = true }
+++

Say you have a wallet on your phone, and yesterday you sent someone money. Now you want to be sure your payment really made it into block 1000. Your phone does not have the space or the bandwidth to download the whole block, because a real block can hold thousands of transactions. Is there a way to fetch just a few hundred bytes and say with confidence "yes, my payment is in this block"?

With the design from the [previous post](/posts/bc-hashes-blocks-chain/) there is not. There, each block header had a `DataHash`, the hash of all the block's data. To recompute that hash and see that it matches the header, you need **all** of the data. A single hash confirms everything at once or nothing at all.

A {{< term "merkle-tree" "Merkle tree" >}} solves exactly this. The header still holds a single 32-byte hash, but now anyone can prove that one particular transaction is in the block with just a few hashes. The structure is not unique to blockchains: in [Replication and quorums](/posts/ds-replication-quorum/) we used it to compare replicas quickly. If trees in general are new to you, [Search trees and the B-tree](/posts/algo-trees-bst-btree/) is good background.

The code in this post continues the `toychain` module from the previous post. I took a copy of it and changed two things: in the header, the `DataHash` field became `MerkleRoot`, and in the block, `Data []byte` became `Txs [][]byte`, a list of transactions instead of a single piece of data. Transactions are still just raw bytes, such as `"alice -> bob: 10"`. Real signed transactions come two posts from now.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example, not a published repo.

## The idea with four transactions

Before any code, let's look at the idea with a small example. Say a block has four transactions: `a`, `b`, `c` and `d`.

First we hash each transaction on its own. Each of these hashes is a **leaf** of the tree. Then we pair the leaves up two by two and hash each pair. These are the **inner nodes**. We repeat this until only one hash is left. That last one is called the **root**, or {{< term "merkle-root" "Merkle root" >}}, and it is what goes into the block {{< term "block-header" "header" >}}:

```
            root = H(ab, cd)
           /                \
     ab = H(a, b)       cd = H(c, d)
      /       \          /       \
   H(a)      H(b)     H(c)      H(d)
```

The root still depends on every transaction. If `c` changes by a single bit, `H(c)` changes, so `cd` changes, so the root changes too. In that sense we have lost nothing compared with `DataHash`.

But we have gained something new. Say I want to prove to you that `c` is in the block, and all you have is the root from the header. I do not need to send all four transactions. Two hashes are enough: `H(d)` and `ab`. You then do this yourself:

1. Compute `H(c)`.
2. Combine it with `H(d)` to get `cd`.
3. Combine `ab` with `cd` to get a root.
4. If that root equals the root in the header, `c` must be in the block.

Those two hashes I sent are called an {{< term "inclusion-proof" "inclusion proof" >}}. Each one is the **sibling** of a node on the path from `c` to the root, meaning the other node that shares the same parent. For four transactions the proof is two hashes. Every time the number of transactions doubles, the tree gets only one level taller and the proof only one hash bigger. We will see the real numbers a little further down.

## Building the tree in Go

Now let's turn this into code. There are two functions: one computes a leaf hash, the other an inner-node hash. Ignore the two constants `leafPrefix` and `nodePrefix` for now; the next section explains why they are there.

```go
const (
	leafPrefix = 0x00
	nodePrefix = 0x01
)

// LeafHash is SHA-256(0x00 || tx).
func LeafHash(tx []byte) Hash {
	return Sum(append([]byte{leafPrefix}, tx...))
}

// NodeHash is SHA-256(0x01 || left || right).
func NodeHash(left, right Hash) Hash { /* ... */ }

func nextLevel(level []Hash) []Hash {
	next := make([]Hash, 0, (len(level)+1)/2)
	for i := 0; i < len(level); i += 2 {
		if i+1 == len(level) {
			next = append(next, level[i]) // lone node: promoted as is
			break
		}
		next = append(next, NodeHash(level[i], level[i+1]))
	}
	return next
}
```

`nextLevel` takes one level of the tree and builds the level above it: it takes the nodes two at a time and computes `NodeHash` for each pair. `MerkleRoot` first builds all the leaves and then keeps calling `nextLevel` until only one hash is left.

Our four-transaction example was tidy. But what if a level has an odd number of nodes? With three transactions, for instance, `c` has no partner on the first level. Here we have to pick a rule, and each rule gives a different root:

- **Promote:** carry the lone node up to the next level unchanged. My code does this (the `promoted as is` line).
- **Duplicate:** pair the lone node with itself, `H(c, c)`. Bitcoin does this.

With the promote rule, our tree has the same shape that RFC 6962 defines. That RFC is the Certificate Transparency standard, a system that records HTTPS certificates in a public log. To be sure, I wrote a test that compares my root with a direct implementation of the RFC's recursive definition. For 0 to 300 transactions they all match.

## Why leaves and nodes get different prefixes

Back to those two constants. `LeafHash` puts a `0x00` byte before the transaction, and `NodeHash` puts a `0x01` byte before the two child hashes. Why?

Imagine there were no prefixes. A leaf hash would be `SHA-256(tx)` and an inner-node hash would be `SHA-256(left || right)`, the hash of its two children glued together. Every hash is 32 bytes, so the input of an inner node is always exactly 64 bytes.

The problem is that the tree cannot tell whether those 64 bytes are "two glued hashes" or "one 64-byte transaction". The hash function only sees bytes. So someone can build a fake "transaction" that is exactly those 64 bytes. The hash of that fake leaf equals the hash of the inner node. The result: a completely different list of transactions that gives the same root.

This is called a {{< term "second-preimage-attack" "second preimage" >}} attack: finding a second input that gives the same hash as the first. The important point is that SHA-256 is not broken here. Our tree, by its design, hashes two different kinds of thing in the same way.

`go run ./cmd/toychain naive` shows this. First it builds a tree without prefixes over four real transactions. Then it makes two fake 64-byte "transactions": the first is the hashes of transactions 0 and 1 glued together, the second the hashes of transactions 2 and 3. It builds a prefix-free tree over those two as well. Finally it tries the same two lists with our real, prefixed tree:

```
naive root, 4 real txs:  472c9838ed30
naive root, 2 fake txs:  472c9838ed30
prefixed root, real:     8e904c88352a
prefixed root, fake:     e0b533a65e8d
```

(For readability the demo prints only the first six bytes of each hash.)

- **The first two lines:** the prefix-free tree gives **the same root** for four real transactions and two fake ones. One header, two different contents. Someone who only has the root cannot tell which one is genuine.
- **The last two lines:** with prefixes the roots differ again. Now a leaf hash always starts from `0x00` and an inner-node hash from `0x01`, so no leaf can pass itself off as an inner node.

Separating two kinds of hash with a fixed tag like this is called {{< term "domain-separation" "domain separation" >}}. RFC 6962 uses exactly these two prefixes.

## The duplicate-last-node trap

I said Bitcoin duplicates the lone node. That rule has a well-known trap too, and this time it has nothing to do with prefixes. `go run ./cmd/toychain dup` runs a simplified version of Bitcoin's rule. Simplified means one round of SHA-256 instead of two, and no prefixes. It tries the lists `[a b c]` and `[a b c c]`, and then the same two lists with our promote rule:

```
duplicate-last [a b c]:   d31a37ef6ac1
duplicate-last [a b c c]: d31a37ef6ac1
promote-last   [a b c]:   36642e73c254
promote-last   [a b c c]: e9636069c740
```

The first two lines are equal, and the reason is simple. In `[a b c]`, the node `c` is alone and is paired with itself: `H(c, c)`. In `[a b c c]`, two real `c`s sit next to each other, which again gives `H(c, c)`. From there on the two trees are identical. So one header matches two different transaction lists.

The last two lines show that the promote rule does not have this problem: `[a b c]` and `[a b c c]` get different roots.

As far as I know, this was reported for Bitcoin as CVE-2012-2459: a node could be tricked into marking a valid block as invalid. I did not reproduce anything against Bitcoin itself; the demo only shows the shape of the problem.

## Inclusion proofs in code

Now that the tree is built correctly, back to the main goal: proving that a transaction is in a block. A proof has three parts:

```go
type Proof struct {
	Index    int    // position of the transaction
	TxCount  int    // number of transactions in the tree
	Siblings []Hash // bottom to top; promoted levels have no sibling
}
```

`Siblings` are the sibling hashes I sent in the four-transaction example, from bottom to top. `Index` is the transaction's position in the list and `TxCount` is the total number of transactions.

`VerifyProof(root, tx, p)` does the same four steps we did by hand above. It starts from `LeafHash(tx)` and combines it with its sibling level by level until it reaches the root. At each level it needs to know whether the sibling goes on the left or the right, because `H(x, y)` differs from `H(y, x)`. It works this out from `Index` and `TxCount`, instead of asking whoever sent the proof. If the sender could say "this one goes on the left", the proof would show membership but say nothing about the transaction's position. Done this way, `Index` is part of what gets checked. There is one more condition: every hash in `Siblings` must be used, so nobody can pad a proof with extra hashes.

`go run ./cmd/toychain merkle` builds a tree of five transactions, builds a proof for transaction 2, and checks it once with the right transaction and once with an edited one. Finally it does the same for transaction 4:

```
root of 5 txs: d9f7ce89020c
proof for tx 2 of 5: 3 siblings, 96 bytes
  sibling 0: 5850eb6c9ec8
  sibling 1: 408cc2b42814
  sibling 2: b0bdb971b6f9
verify real tx:    true
verify edited tx:  false
proof for tx 4 (promoted twice): 1 siblings
verify: true
```

For this output to make sense, look at the shape of the five-transaction tree. I have numbered the transactions 0 to 4:

```
                  root
                /      \
           N0123         4
          /     \        |
       N01       N23     4
      /   \     /   \    |
     0     1   2     3   4
```

Transaction 4 has no partner on the first level and moves up, the same on the second level, and only on the last level is it paired with `N0123`.

Now let's read the output:

- **The proof for transaction 2** has three hashes, 96 bytes. From bottom to top: `sibling 0` is the leaf of transaction 3, `sibling 1` is the node `N01`, and `sibling 2` is the leaf of transaction 4, which was carried all the way up to the last level.
- **`verify real tx: true`:** with those three hashes, the computed root equals the tree's root.
- **`verify edited tx: false`:** we tried the same proof with `"carol -> dave: 100"` instead of `"carol -> dave: 1"`. The leaf hash changed, so the root changed, and the proof was rejected.
- **The proof for transaction 4** has only one hash, `N0123`. The reason is what the picture shows: it has no partner on the first two levels, so there is nothing to send for them.

The tests also try every position for 1 to 70 transactions: the right proof must be accepted, and the same proof with a forged transaction or a wrong `Index` must be rejected.

## How big is a proof?

I said the proof grows very slowly. `go run ./cmd/toychain sizes` builds trees of different sizes and takes a proof for transaction 0 each time:

```
      txs siblings  proof bytes all leaf hashes
        1        0            0             32
        2        1           32             64
        3        2           64             96
        4        2           64            128
        5        3           96            160
        8        3           96            256
      100        7          224           3200
     1000       10          320          32000
     4096       12          384         131072
  1000000       20          640       32000000
```

The columns are: the number of transactions, the number of hashes in the proof, the proof size in bytes, and in the last column the size of all the leaf hashes side by side. That last column is the minimum you would need without a tree, and that is before counting the transactions themselves.

Comparing the last two columns says it all. For a thousand transactions the proof is 320 bytes against 32,000. For a million transactions the proof is 20 hashes, 640 bytes, against 32 million. The number of hashes in a proof is roughly log2 of the number of transactions: 2 to the power of 20 is a little over a million, so 20 levels are enough.

This is the answer to the question at the top of the post. The Bitcoin whitepaper calls this approach {{< term "spv" "simplified payment verification" >}}: a light client, such as a phone wallet, keeps only the headers. Whenever it wants to know whether a transaction is in a block, it asks for an inclusion proof and checks it itself.

## Back in the chain

Now let's connect the Merkle tree to the chain from the previous post. `ValidateBlocks` used to recompute the data hash and compare it with `DataHash`. Now it rebuilds the root from `Txs` and compares it with the header's `MerkleRoot`. `go run ./cmd/toychain chain` builds a three-block chain, validates it, then changes a single transaction in block 1 (`10` becomes `1000`) and validates again:

```
  #0 prev=-            root=7b5eabeb1bbd hash=759fc6cff9c0 txs=1
  #1 prev=759fc6cff9c0 root=63a5466f1041 hash=cedaf9a6150d txs=3
  #2 prev=cedaf9a6150d root=5850eb6c9ec8 hash=a07354280ad9 txs=1
validate: <nil>
edit one tx: block 1: merkle root does not match transactions
```

The first three lines are the chain. As before, each block's `prev` is the `hash` of the block before it, and now each block also shows its `root` and its number of transactions (`txs`). `validate: <nil>` means the healthy chain has no problem. The last line catches the tampering: the root rebuilt from the new transactions does not match the root in block 1's header.

There is one small detail in this output. Block 2's root, `5850eb6c9ec8`, is the same as `sibling 0` in the previous demo. That is because block 2 has only one transaction, `"dave -> erin: 2"`, and the root of a tree with one leaf is just that leaf's hash. In the previous demo, `sibling 0` was the leaf of this same transaction.

## What a proof does not prove

An inclusion proof is a powerful tool, but it is easy to expect more from it than it gives:

- **A proof is only worth as much as its root.** If you take the root from the same party that sends the proof, they can build any tree they like and make a valid proof for it. Take the root from a header you validated yourself.
- **Write your odd-count rule down and keep it fixed.** Promote and duplicate give different roots. If two implementations disagree on this rule, they will not agree on any block with an odd number of transactions.
- **Keep leaf hashes and node hashes apart.** As the `naive` demo showed, without prefixes the tree breaks even though SHA-256 is perfectly fine.
- **Our header does not commit to the number of transactions.** `TxCount` lives in the proof, not in the header. I tried it: the proof for transaction 0 of 5 is also accepted when it claims 6, 7 or 8 transactions. That is because transaction 0's path has the same three siblings in all of those trees. So membership is proven correctly, but the count is not.
- **Inclusion means only "this transaction is in this block".** A proof does not say the transaction is valid, that it is correctly signed, or that the money it spends had not been spent already. Those are the job of other rules that we build in the coming posts.

## Exercise

1. Write a test showing that `[a b c]` and `[a b c c]` have different roots with `MerkleRoot`.
2. Add `TxCount` to the header and make the verifier take the count from the header instead of the proof. Then check again whether a proof claiming 6 transactions is still accepted.
3. Write a proof for two transactions at once that sends their shared sibling hashes only once.

## What's next

The next post is "Keys, ECDSA signatures and addresses on secp256k1". So far anyone can write `"alice -> bob: 10"`; there we see how only alice herself can create a transaction in her name.
