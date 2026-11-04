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

Imagine a ledger that several other people each keep a full copy of. One night, someone quietly changes a single number on page three: "10" becomes "1000". How can anyone tell right away that the ledger was tampered with, without comparing it word by word against everybody else's copy?

A blockchain's answer is surprisingly simple: give every page a "fingerprint", and write each page's fingerprint on the next page. Now if someone changes page three, its fingerprint changes and no longer matches what page four says. The [previous post](/posts/bc-blockchain-for-programmers/) showed a bare-bones version of this idea with a few records; here I want to turn it into a real chain in Go and see where it is simpler than it sounds and where it is harder.

The trick is not unique to blockchains. In [Logging, auditing and incident response](/posts/sec-logging-audit-incident-response/) we used it to make logs tamper-evident, and Git links every commit to the previous one in exactly this way ([How Git thinks: objects and hashes](/posts/git-how-git-thinks/)).

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example, not a published repo.

## The fingerprint: a hash function

In practice that "fingerprint" is a **hash function**. A hash function takes any input, a single word or a multi-gigabyte file, and returns a number of fixed size. That number is called the **digest**, or simply the hash. We use {{< term "sha-256" "SHA-256" >}}, whose output is always 32 bytes, that is 256 bits.

Three properties matter for us:

- **It is deterministic.** The same input always gives the same hash, on any computer.
- **It is sensitive.** The smallest change to the input changes the hash completely. This is called the {{< term "avalanche-effect" "avalanche effect" >}}: one pebble, a whole avalanche.
- **Nobody can find two inputs with the same hash.** I cannot show you this with a test; it rests on years of cryptographers trying to break SHA-256 and, so far, failing.

In Go our code is just one type and one small function:

```go
type Hash [32]byte

func Sum(b []byte) Hash { return sha256.Sum256(b) }
```

To see the first two properties with our own eyes, `go run ./cmd/toychain sha` hashes a message twice. Then it changes a single bit of it (`10` becomes `11`) and counts how many output bits differ. Finally it repeats the experiment on 10,000 random 64-byte inputs:

```
same input twice:
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
  91eff314c1e123de34a8347604128c113a48f9fc48d0a854a8fd4babc12c19ea
one bit flipped: "alice -> bob: 11"
  e15286f848d3de8b06620811c49d4e31160f86ce4992e11f8833f77851a375ac
differing bits: 120 of 256
10000 trials: min 98, avg 128.1, max 161 differing bits
```

The first two lines are identical: that is determinism. The next one, after changing a single bit, looks nothing like them: 120 of the 256 bits changed. Over 10,000 trials the average is 128.1 bits, almost exactly half. That is what we expect from a good hash function: the output is so scrambled that every bit might as well have been decided by a coin flip, so the hash tells you nothing about the input.

## A block: one page of the ledger

Now that we have fingerprints, we can build the pages. Each page is a **block**, and it has two parts:

- **data** (`Data`): the actual content, for example "alice gave bob 10".
- **a {{< term "block-header" "header" >}}**: a small label with four fields that holds the page number, the time, and two hashes.

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

`Height` is the block number and `Timestamp` is when it was created. The last two fields do the real work:

- `DataHash` is the fingerprint of the data. The data itself does not go into the header, only its hash. So if the data changes, it no longer matches `DataHash`.
- `PrevHash` is the fingerprint of the previous block. This is "writing the previous page's fingerprint on the next page".

Finally the block has its own `Hash`, computed from the header alone. Because `DataHash` is inside the header, this hash covers the data indirectly too.

The consequence of this design is worth walking through slowly once. Block 3's hash depends on its `PrevHash`, which is block 2's hash, which in turn depends on block 1's hash, and so on back to the first block. So **the last block's hash depends on the whole history**: change anything in any block and the last hash changes too. A structure like this is called a {{< term "hash-chain" "hash chain" >}}.

## A hidden trap: which bytes do we hash?

So far I have said "we hash the header". But a hash function works on bytes, not on a Go struct. So first we have to turn the header into a sequence of bytes (this is called **serializing** it). This is where it is very easy to get things wrong.

In a blockchain several computers (each one is called a **node**) compute block hashes independently and must reach the same answer. If two nodes turn the same header into bytes slightly differently, they get two different hashes and can no longer agree on which chain is the right one. The first idea that comes to mind is JSON, so let's see what happens. The output of `go run ./cmd/toychain encoding`:

```
json.Marshal:        {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  9ad464a5d059
Encoder, no escape:  {"from":"alice","to":"bob","amount":10,"memo":"rent<may>"}
  1e65ec03e3fb
map via json.Marshal: {"amount":10,"from":"alice","to":"bob"}
"ab"+"c" vs "a"+"bc" same hash: true
header bytes (80): 0000000000000001000000006553f13c...
```

Let's read it line by line:

- **The first two lines:** I turned one and the same payment into JSON with two standard Go methods. By default `json.Marshal` writes `<` and `>` as `<` and `>` (for safety inside HTML), while an `Encoder` with `SetEscapeHTML(false)` writes a plain `<`. Same meaning, different bytes, so different hashes (`9ad4…` versus `1e65…`). Even two Go programs can disagree about the same data.
- **The map line:** Go sorts map keys when it encodes JSON, so in Go this output is always the same. Other languages do not necessarily do that; JavaScript's `JSON.stringify`, for example, writes keys in the order they were added. Whitespace, number formatting and Unicode escaping also differ from one library to another.
- **The fourth line:** if instead of JSON we simply glue the fields together, we hit a different problem. `"ab"` and `"c"` glued together are `"abc"`; so are `"a"` and `"bc"`. Two different pieces of data, one hash. The boundary between fields is lost.

So we need a way to turn data into bytes that leaves no room for interpretation: the same data, in any language, gives exactly the same bytes. This is called a {{< term "canonical-encoding" "canonical encoding" >}}. For our header it is easy, because all of its fields have a fixed length. We always put the fields in the same order, and we always write numbers with one fixed byte order (**big-endian**, meaning the most significant byte first):

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

8 bytes for the height, 8 for the time, 32 for each hash: always exactly 80 bytes. Because the length and position of every field are known, the gluing ambiguity cannot happen. The last line of the output above is those 80 bytes: `0000000000000001` is height 1 and `000000006553f13c` is the time.

## Building the chain and checking it

The first block of the chain has no previous block to point to. It is called the {{< term "genesis-block" "genesis block" >}}: its height is 0 and its `PrevHash` is all zeros. Every following block is built by `Append` on top of the last block of the chain. It increments the number and uses the last block's hash as the new block's `PrevHash`:

```go
func (c *Chain) Append(ts int64, data []byte) Block {
	tip := c.Tip()
	b := NewBlock(tip.Header.Height+1, tip.Hash, ts, data)
	c.blocks = append(c.blocks, b)
	return b
}
```

To check the chain, `ValidateBlocks` trusts none of the stored hashes and recomputes all of them. For each block it asks:

1. Is its number right?
2. Does the hash of its data match `DataHash`?
3. Does the hash of its header match the stored `Hash`?
4. Does its `PrevHash` equal the previous block's hash?

At the first "no" it stops and reports which block and what went wrong.

## Trying it: tampering with the ledger

Back to the opening question. `go run ./cmd/toychain chain` builds a four-block chain, then takes a copy of it and plays someone who wants to turn `10` into `1000` in block 1, getting a little smarter each time:

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

The first four lines are the healthy chain. Notice that each block's `prev` is exactly the `hash` of the block above it; that is the chain. `validate: <nil>` means no problem was found. Then come three tampering attempts:

- **First attempt (`edit data`):** only block 1's data is changed. Validation catches it immediately: the hash of the new data does not match the `DataHash` still in the header.
- **Second attempt (`rehash block 1`):** the tamperer is smarter and also recomputes block 1's `DataHash` and `Hash`. Block 1 now looks fine on its own, but the problem has moved to block 2: block 2's `PrevHash` still holds block 1's old hash.
- **Third attempt (`rebuild rest`):** the tamperer rebuilds every later block too. Now validation finds nothing.

So the tampering worked? Not quite, and this is the most important point of the post. Look at the last line: the last block's hash went from `5be1abf7508b` to `a571aac4dcd0`. The forged chain is internally consistent, but **its final fingerprint is different**. Validation alone cannot say which version is the original. What protects the original is that the other nodes already hold its last hash and recognise the forged version at once. Later in the series, proof of work adds another layer: rebuilding blocks is no longer free like it is here, it has a real cost.

`go test ./...` repeats these same scenarios as tests.

## Where it is easy to get wrong

- **Do not hash a library's default output.** Not `json.Marshal`, not `fmt.Sprintf("%v")`. As we saw, these can change without telling you or differ in another language. Define your own byte encoding and keep it fixed.
- **Do not glue variable-length fields without boundaries.** If a field such as text or a list has no fixed length, write its length before it so it is clear where it ends. Otherwise you run into the same `"ab"+"c"` problem.
- **Do not trust a stored hash.** Keeping the hash around for speed is fine, but always recompute it when you validate. A stored hash can be tampered with just like the data, as the second attempt showed.
- **A hash shows that something changed, not who changed it.** Our chain does not know who created a block. That is the job of digital signatures, which we get to later.

## Exercise

1. Add a `Version uint32` field to the header and update `Encode` and `HeaderSize`. If you forget to change `HeaderSize`, which test catches it?
2. Make `ValidateBlocks` reject a block whose time is older than its parent's.
3. Write `Decode([]byte) (Header, error)`, which reverses `Encode`, and a test showing that `Decode(h.Encode())` returns exactly the same `h`.

## What's next

The next post is "Merkle trees and inclusion proofs". Right now each block holds one piece of data, but a real block holds hundreds of transactions. There we build `DataHash` so that you can prove one particular transaction is in a block without sending all the others.
