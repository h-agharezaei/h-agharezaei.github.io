+++
date = '2026-11-03T18:00:00+03:30'
draft = false
title = 'Hashes, blocks and the chain: a first blockchain in Go'
seoTitle = 'Hashes, blocks and the chain: a blockchain in Go'
description = 'A first blockchain in Go: SHA-256 properties, a block header with a canonical encoding, genesis, append, validation and tamper detection with real output.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "sha-256", "hashing", "serialization"]
cover = { image = "/images/covers/bc-hashes-blocks-chain.png", alt = "Hashes, blocks and the chain: a first blockchain in Go", hiddenInSingle = true }
+++

One payment hashes one way through `json.Marshal` and another way through an `Encoder` with `SetEscapeHTML(false)`; for nodes that must agree on one chain, that is a bug. This post turns the hash-linked records of the [previous post](/posts/bc-blockchain-for-programmers/) into a small Go module that part one keeps extending: what {{< term "sha-256" "SHA-256" >}} promises, what a block is, how to define the bytes you hash, and how a chain checks itself. No proof of work yet.

The same linking trick appeared in [Logging, auditing and incident response](/posts/sec-logging-audit-incident-response/), and Git names its objects by hash too ([How Git thinks: objects and hashes](/posts/git-how-git-thinks/)).

> Everything below was run with Go 1.27 on macOS (arm64). The code is a local example, not a published repo.

## The module layout

```
toychain/
  go.mod                 module toychain
  chain/hash.go          Hash, Sum
  chain/block.go         Header, Block, Genesis
  chain/chain.go         Chain, Append, ValidateBlocks
  chain/chain_test.go
  cmd/toychain/main.go   demos: go run ./cmd/toychain <name>
```

Later posts add to `chain` instead of rewriting it.

## What SHA-256 gives us

A cryptographic hash function maps any input to a fixed-size digest, 32 bytes for SHA-256. Two properties matter today: it is deterministic, and a tiny change in the input flips about half of the output bits, the {{< term "avalanche-effect" "avalanche effect" >}}. We also rely on nobody finding two inputs with the same digest; that rests on public cryptanalysis, not on anything we can test.

```go
type Hash [32]byte

func Sum(b []byte) Hash { return sha256.Sum256(b) }
```

`go run ./cmd/toychain sha` hashes a message twice, flips its last bit (`0` becomes `1`), then repeats one-bit flips on 10,000 random 64-byte inputs:

```
same input twice:
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
one bit flipped: "alice -> bob: 11"
  e15286f848d3de8b06620811c49d4e31160f86ce4992e11f8833f77851a375ac
differing bits: 120 of 256
10000 trials: min 98, avg 128.1, max 161 differing bits
```

One bit in, 120 bits out; on average 128.1, half of 256, as a random-looking function should give.

## A block and its header

A block has a small {{< term "block-header" "header" >}} and a payload. Only the header is hashed; the payload enters through its own hash, a slot the next post improves.

```go
type Header struct {
	Height    uint64 // 0 for genesis
	Timestamp int64  // unix seconds
	PrevHash  Hash   // hash of the previous block header, zero for genesis
	DataHash  Hash   // SHA-256 of the block data
}

type Block struct {
	Header Header
	Hash   Hash
	Data   []byte
}
```

`PrevHash` is the link. Each header commits to everything before it, which makes the chain a {{< term "hash-chain" "hash chain" >}}.

## The bytes you hash must be defined exactly

A hash covers bytes, not "the same object". If two nodes serialize one header differently, they compute different ids and disagree about the chain. `go run ./cmd/toychain encoding`:

```
json.Marshal:        {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  9ad464a5d059
Encoder, no escape:  {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  1e65ec03e3fb
map via json.Marshal: {"amount":10,"from":"alice","to":"bob"}
"ab"+"c" vs "a"+"bc" same hash: true
header bytes (80): 0000000000000001000000006553f13c...
```

One payment, two hashes: `json.Marshal` escapes `<` and `>` for HTML by default, an `Encoder` with `SetEscapeHTML(false)` does not. Go sorts map keys, so the map line is stable in Go, but other languages choose differently (JavaScript's `JSON.stringify` keeps insertion order for ordinary keys), and whitespace, number formats and Unicode escapes vary too. The fourth line shows that plain concatenation is ambiguous: field boundaries disappear.

So the header gets a {{< term "canonical-encoding" "canonical encoding" >}}: fixed-width big-endian fields in a fixed order. Every field has a known length, so the result is always 80 unambiguous bytes.

```go
func (h Header) Encode() []byte {
	buf := make([]byte, 0, HeaderSize)
	buf = binary.BigEndian.AppendUint64(buf, h.Height)
	buf = binary.BigEndian.AppendUint64(buf, uint64(h.Timestamp))
	buf = append(buf, h.PrevHash[:]...)
	buf = append(buf, h.DataHash[:]...)
	return buf
}

func (h Header) Hash() Hash { return Sum(h.Encode()) }
```

## Genesis, append, validate

The {{< term "genesis-block" "genesis block" >}} is the only block without a parent: height 0 and an all-zero `PrevHash`. `Append` builds on the tip:

```go
func (c *Chain) Append(ts int64, data []byte) Block {
	tip := c.Tip()
	b := NewBlock(tip.Header.Height+1, tip.Hash, ts, data)
	c.blocks = append(c.blocks, b)
	return b
}
```

`ValidateBlocks` trusts nothing stored. For each block it checks the height, recomputes the data hash and the header hash, and compares `PrevHash` with the previous block's hash. It returns the first problem as a wrapped sentinel error.

## Tampering, for real

`go run ./cmd/toychain chain` builds four blocks with fixed timestamps, then edits a copy in three steps:

```
  #0 prev=-            hash=4d7f75130edb data="genesis"
  #1 prev=4d7f75130edb hash=056ffcc052ff data="alice -> bob: 10"
  #2 prev=056ffcc052ff hash=75a7ae117b39 data="bob -> carol: 4"
  #3 prev=75a7ae117b39 hash=5be1abf7508b data="carol -> dave: 1"
validate: <nil>
edit data:       block 1: data hash does not match data
rehash block 1:  block 2: previous hash does not match
rebuild rest:    <nil>
tip before: 5be1abf7508b tip after: a571aac4dcd0
```

Editing the data is caught at block 1. Fixing block 1's hashes moves the break to block 2. Rebuilding every later block makes the copy valid again, but with a different tip hash. Validation alone cannot tell the two histories apart; what protects the real one is that others already hold its tip hash, and later, that rebuilding costs work. `go test ./...` repeats these cases as a table test.

## Encoding and validation traps

- Hash a canonical encoding you control, never `fmt.Sprintf("%v")` or a JSON library's default output.
- Give every variable-length field a length prefix or a fixed width; concatenation alone is ambiguous.
- Store the hash for convenience, but always recompute it when validating.
- A hash detects changes; it does not say who made them. Signatures come later.

## Exercise

1. Add a `Version uint32` field to the header and update `Encode` and `HeaderSize`. Which test catches a forgotten update?
2. Make `ValidateBlocks` reject a block whose timestamp is older than its parent's.
3. Write a `Decode([]byte) (Header, error)` and a test that `Decode(h.Encode())` returns `h`.

## What's next

The next post is "Merkle trees and inclusion proofs". The single `DataHash` becomes a root over a list of transactions, and we prove that one transaction is in a block without sending the others.
