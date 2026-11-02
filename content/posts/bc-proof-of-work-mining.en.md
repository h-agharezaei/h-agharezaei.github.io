+++
date = '2026-11-08T18:00:00+03:30'
draft = false
title = 'Proof of work, difficulty and mining'
description = 'Proof of work in Go: a nonce and difficulty bits in the header, mining, validation, hashes doubling per bit, a clamped retarget and chainwork.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-work", "mining", "bitcoin"]
cover = { image = "/images/covers/bc-proof-of-work-mining.png", alt = "Proof of work, difficulty and mining", hiddenInSingle = true }
+++

In the [previous post](/posts/bc-account-model-nonce/) we compared the account model with UTXO. So far anyone could build a valid block in microseconds. In [Blockchain for programmers](/posts/bc-blockchain-for-programmers/) I said that a hash chain is only tamper-evident, and that making rewrites expensive comes later. This is that post.

[Consensus and Raft](/posts/ds-consensus-raft/) solved agreement among a known list of servers, each with one vote. An open network has no list: anyone can start a thousand nodes. {{< term "proof-of-work" "Proof of work" >}} replaces "one node, one vote" with "one unit of computation, one vote".

I copied last post's `toychain` module and extended `chain`; blocks still carry UTXO transactions.

> Go 1.27 on macOS (arm64). Local example code. The machine's load average was about 3, so I show hash counts, not timings.

## Two new header fields

```go
type Header struct {
	Height     uint64
	Timestamp  int64
	PrevHash   Hash
	MerkleRoot Hash
	TxCount    uint32
	Bits       uint32 // the hash must start with this many zero bits
	Nonce      uint64 // changed by the miner until it does
}
```

The {{< term "block-header" "header" >}} is now 96 bytes. A block is valid only if `SHA-256(header)` has at least `Bits` leading zero bits, that is, the hash read as a number is below `2^(256-Bits)`. There is no shortcut: {{< term "mining" "mining" >}} means trying {{< term "nonce" "nonce" >}} values one by one:

```go
func Mine(h Header, maxTries uint64) (Header, uint64, bool) {
	for tries := uint64(1); tries <= maxTries; tries++ {
		if h.MeetsTarget() {
			return h, tries, true
		}
		if tries == maxTries || h.Nonce == math.MaxUint64 {
			return h, tries, false
		}
		h.Nonce++
	}
	return h, 0, false
}
```

Why zero bits and not Bitcoin's target? According to the Bitcoin docs, its header stores a full 256-bit {{< term "difficulty-target" "target" >}} in a compact form, so difficulty can move by any factor. Counting zero bits is easier to read, but difficulty can only double or halve. We will see that cost in the retarget table.

`go run ./cmd/toychain mine` mines the same genesis block at three difficulties:

```
bits  8: nonce      28,      29 hashes, hash 002acbe8e52ec14be233...
bits 16: nonce   49014,   49015 hashes, hash 0000af50878911463738...
bits 20: nonce 1908273, 1908274 hashes, hash 0000084c8f5cc05e63b2...
timestamp +1 after mining: 3c89edab33b4024d79b0..., meets target: false
```

Mining took up to 1.9 million hashes; checking takes one. Change any field and the work is lost.

## Each bit doubles the work

One block is luck, so `go run ./cmd/toychain tries` averages 256 different headers per difficulty:

```
bits   avg hashes     2^bits    vs prev
   8          245        256          -
   9          506        512      2.07x
  10         1178       1024      2.33x
  11         2044       2048      1.73x
  12         4071       4096      1.99x
  13         8113       8192      1.99x
  14        17520      16384      2.16x
  15        29389      32768      1.68x
  16        66541      65536      2.26x
  17       145265     131072      2.18x
  18       290333     262144      2.00x
```

The expected count is `2^Bits`, and each extra bit roughly doubles it; single steps are noisy, from 1.68x to 2.33x.

## Validation

`AddBlock` now checks the link, a timestamp after the parent's, that `Bits` is what the rules require, the proof of work, then the Merkle root and every transaction. `go run ./cmd/toychain powcheck`:

```
required bits: 8
unmined block:         block 1: hash does not meet the difficulty target
own bits 2 (21 hashes): block 1: wrong difficulty bits
mined, then tx edited: block 1: merkle root does not match transactions
mined (87 hashes):    <nil>
chainwork: genesis 256, tip 512
```

A miner cannot pick an easy difficulty.

## Retargeting

Hash power changes; the block rate should not. Every `RetargetInterval` blocks, `NextBits` compares how long the last period took with how long it should have taken and moves `Bits` to the nearest power of two, at most 2 bits (4x) either way. Integer math only, so every node gets the same answer:

```go
w2, a2 := want*want, actual*actual
switch {
case w2 >= 8*a2: // at least 2^1.5 times too fast
	delta = 2
case w2 >= 2*a2:
	delta = 1
case a2 >= 8*w2:
	delta = -2
case a2 >= 2*w2:
	delta = -1
}
```

As far as I know, Bitcoin does this every 2016 blocks with the same 4x limit. I use 8 blocks by default to keep later demos short. `go run ./cmd/toychain retarget` simulates a miner: it tries `hashrate` nonces per simulated second, then bumps the timestamp. The hashes are real; only the clock is simulated. With 8-block periods the noise swamped the signal, so this demo uses 32:

```
retarget every 32 blocks, target 10s per block, genesis bits 12
  heights   hashrate  bits  avg spacing     hashes    chainwork
   1-31        400/s    12        10.8s     127388       131072
  32-63        400/s    12        10.4s     127554       262144
  64-95       1600/s    12         3.6s     156288       393216
  96-127      1600/s    13         6.2s     295686       655360
 128-159      1600/s    14         9.8s     476788      1179648
 160-191       200/s    14        67.3s     427326      1703936
 192-223       200/s    12        24.3s     152411      1835008
 224-255       200/s    11         9.9s      60120      1900544
validate: <nil>
```

Hash rate ×4 at height 64: blocks every 3.6 s instead of 10. The period was less than 2^1.5 times too fast, so the {{< term "difficulty-adjustment" "retarget" >}} added one bit, then another. When hash rate fell 8x, the clamp allowed only −2 bits, and it took two periods to recover.

## Chainwork

The last column is {{< term "chainwork" "chainwork" >}}: the sum of `2^Bits` over all blocks, the expected number of hashes behind the tip. Two posts from now, nodes choose the chain with the most work, not the most blocks.

## Why this stops Sybils

In a {{< term "sybil-attack" "Sybil attack" >}} one party pretends to be many; with a vote per node, a thousand fake nodes would win. With proof of work, a fake identity costs nothing and adds nothing; only hashes count, and hashes cost electricity and hardware. Rewriting a block means redoing its work and all the work after it, faster than everyone else extends the chain.

## A few things to watch

- Check proof of work before the expensive checks, and check `Bits` against your own rule, never the block's claim.
- Use integers in consensus code; floating point can round differently.
- Timestamps feed the retarget. I only require them to increase; as far as I know, Bitcoin also requires them to be after the median of the last 11 blocks and not too far in the future.

## Exercise

1. Replace `Bits` with a 256-bit target (`math/big`) and retarget by the exact ratio, still clamped at 4x.
2. Add a "not more than 2 hours in the future" rule and a test for it.
3. Run the retarget simulation with intervals 8, 32 and 128 and compare the spacing spread.

## What's next

Next post: **P2P networking and gossip between nodes**. Several nodes start sharing transactions and blocks over TCP.
