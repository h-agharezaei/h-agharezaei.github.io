+++
date = '2026-11-04T18:00:00+03:30'
draft = false
title = 'Merkle trees and inclusion proofs'
description = 'Merkle trees in Go: a block header with a Merkle root, odd leaf counts, leaf and node prefixes against second preimages, and inclusion proofs measured.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "merkle-tree", "hashing", "data-structures"]
cover = { image = "/images/covers/bc-merkle-trees-proofs.png", alt = "Merkle trees and inclusion proofs", hiddenInSingle = true }
+++

In the [previous post](/posts/bc-hashes-blocks-chain/) the block header committed to the payload with a single `DataHash`. To check that one payment is in a block, you need the whole block. A {{< term "merkle-tree" "Merkle tree" >}} fixes that: the header still holds 32 bytes, but anyone can prove one transaction is in the block with a few hashes. We used one in [Replication and quorums](/posts/ds-replication-quorum/) to compare replicas; trees in general are in [Search trees and the B-tree](/posts/algo-trees-bst-btree/).

I copied last post's `toychain` module and extended it: `Header.DataHash` became `MerkleRoot`, and `Block.Data` became `Txs [][]byte`. Transactions are still opaque byte payloads; signed transactions come in the next two posts.

> Run with Go 1.27 on macOS (arm64). Local example code.

## Building the tree

Each transaction is hashed into a leaf. Each parent hashes its two children. The top is the {{< term "merkle-root" "Merkle root" >}}, which goes into the {{< term "block-header" "header" >}}:

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

Odd counts need a rule. I promote the lone last node unchanged. Bitcoin duplicates it instead. With promotion the tree has the shape defined in RFC 6962 (Certificate Transparency); a test compares my root with a direct implementation of the RFC's recursive definition for 0 to 300 transactions, and all match.

## Why the 0x00 and 0x01 prefixes

Without them a leaf and an inner node are both "SHA-256 of some bytes", and an inner node is the hash of exactly 64 bytes. So a 64-byte "transaction" equal to two child hashes glued together produces the same hash as that inner node. That is a {{< term "second-preimage-attack" "second preimage" >}} on the tree, not on SHA-256. `go run ./cmd/toychain naive` builds a tree without prefixes over 4 real transactions, then over 2 fake ones made of those glued hashes:

```
naive root, 4 real txs:  472c9838ed30
naive root, 2 fake txs:  472c9838ed30
prefixed root, real:     8e904c88352a
prefixed root, fake:     e0b533a65e8d
```

Two different transaction lists, one root. Prefixing leaves with 0x00 and inner nodes with 0x01, called {{< term "domain-separation" "domain separation" >}}, puts the two kinds of hash in different spaces, and the roots differ again. RFC 6962 uses the same prefixes.

## Duplicating the last node

Bitcoin's rule has a known trap. `go run ./cmd/toychain dup` uses a simplified version (single SHA-256, no prefixes):

```
duplicate-last [a b c]:   d31a37ef6ac1
duplicate-last [a b c c]: d31a37ef6ac1
promote-last   [a b c]:   36642e73c254
promote-last   [a b c c]: e9636069c740
```

`[a b c]` and `[a b c c]` share a root, so one header matches two transaction lists. As far as I know this was reported for Bitcoin as CVE-2012-2459: a node could be tricked into marking a valid block as invalid. I did not reproduce anything against Bitcoin itself.

## Inclusion proofs

An {{< term "inclusion-proof" "inclusion proof" >}} is the list of sibling hashes on the path from one leaf to the root:

```go
type Proof struct {
	Index    int    // position of the transaction
	TxCount  int    // number of transactions in the tree
	Siblings []Hash // bottom to top; promoted levels have no sibling
}
```

`VerifyProof(root, tx, p)` starts from `LeafHash(tx)` and combines it with each sibling. Which side the sibling goes on is derived from `Index` and `TxCount`, never taken from the prover, and every sibling must be used. `go run ./cmd/toychain merkle` with 5 transactions:

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

Transaction 4 is the lone node on two levels, so its proof is one hash. Tests check every index for 1 to 70 transactions, plus forged transactions and wrong indexes.

## How big is a proof?

`go run ./cmd/toychain sizes`, proof for transaction 0:

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

The proof grows with log2 of the count: a million transactions need 20 hashes, 640 bytes. This is what the Bitcoin whitepaper calls {{< term "spv" "simplified payment verification" >}}: a light client keeps only headers and asks for proofs.

## Back in the chain

`ValidateBlocks` now recomputes the root from `Txs`. Editing one transaction in block 1:

```
  #0 prev=-            root=7b5eabeb1bbd hash=759fc6cff9c0 txs=1
  #1 prev=759fc6cff9c0 root=63a5466f1041 hash=cedaf9a6150d txs=3
  #2 prev=cedaf9a6150d root=5850eb6c9ec8 hash=a07354280ad9 txs=1
validate: <nil>
edit one tx: block 1: merkle root does not match transactions
```

Block 2's root equals sibling 0 above: a one-transaction root is that transaction's leaf hash.

## A few things to watch

- A proof is only as good as the root. Take the root from a header you validated, never from the prover.
- Write your odd-count rule down; promote and duplicate give different roots.
- Separate leaf and node hashes. Without it the tree, not SHA-256, is what breaks.
- Our header does not commit to the transaction count. I tried: the proof for transaction 0 of 5 also verifies when it claims 6, 7 or 8 transactions. Inclusion holds, the count is unproven.
- Inclusion says "this transaction is in this block", not that it is valid or unspent.

## Exercise

1. Add a test that `[a b c]` and `[a b c c]` have different roots with `MerkleRoot`.
2. Add `TxCount` to the header and make the verifier take the count from there.
3. Write a proof for two transactions at once that shares the siblings they have in common.

## What's next

The next post is "Keys, ECDSA signatures and addresses on secp256k1": transactions stop being plain bytes and get signed.
