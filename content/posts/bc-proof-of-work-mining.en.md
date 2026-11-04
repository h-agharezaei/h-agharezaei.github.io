+++
date = '2026-11-08T18:00:00+03:30'
draft = false
title = 'Proof of work, difficulty and mining'
description = 'Proof of work in Go: a nonce and difficulty bits in the header, mining, validation, hashes doubling per bit, a clamped retarget and chainwork.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "proof-of-work", "mining", "bitcoin"]
cover = { image = "/images/covers/bc-proof-of-work-mining.png", alt = "Proof of work, difficulty and mining", hiddenInSingle = true }
+++

Remember what the tamperer did in [Hashes, blocks and the chain](/posts/bc-hashes-blocks-chain/)? They changed a number in block 1 and then rebuilt every block after it. The forged chain was perfectly consistent inside, and the only thing that gave it away was that others held the last hash of the original. But now a harder question: if two consistent versions of the chain are passed around the network, which one should the nodes accept?

With the code we have so far, that question has no good answer, because building a valid block takes only a few microseconds. Anyone can build a complete, valid chain in the blink of an eye. In [Blockchain for programmers](/posts/bc-blockchain-for-programmers/) I said that a hash chain only makes tampering visible, and that making a rewrite **expensive** comes later. This is that post. After comparing the account model with UTXO in the [previous post](/posts/bc-account-model-nonce/), it is time for building a block to cost something.

The first fix that comes to mind is a vote: one vote per node, and the chain most nodes accept wins. In [Consensus and Raft](/posts/ds-consensus-raft/) we did exactly that, and it worked there, because the list of servers was known in advance. But an open network has no list. Anyone can start a thousand nodes and have a thousand votes. {{< term "proof-of-work" "Proof of work" >}} changes this: instead of "one node, one vote", it is "one unit of computation, one vote". Starting a node is free, but computation costs electricity and hardware.

The code in this post continues the `toychain` module from the previous post. I took a copy of it and extended the `chain` package. Blocks still carry UTXO transactions.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example. The machine's load average was about 3 when I ran it, so instead of run times I show hash counts, which do not depend on the machine's load.

## A puzzle: hard to solve, easy to check

The idea of proof of work is this: for a block to be accepted, its builder has to solve a puzzle. The puzzle has two properties. Solving it takes time and has no shortcut, but checking the answer is instant.

The puzzle is built from the same hash function. We know from the hash post that SHA-256 output is like a random string of bits, as if every bit had been decided by a coin flip. Now we set a condition: the hash of the block header must start with, say, 8 zero bits. That is like flipping 8 coins and wanting them all to land heads. The chance is 1 in 256. So on average you have to try about 256 times. If the condition is 9 bits, 512 times. Every extra bit doubles the work.

But if the header is fixed, its hash is fixed too. How do we "try again"? With a new header field that means nothing except that the block's builder can change it. Every time you change it, you get a completely new hash; you have flipped the coins once more. This guessing, over and over, is called {{< term "mining" "mining" >}}, and whoever does it is a miner.

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

The last two fields are new:

- **`Bits`** is the puzzle's difficulty: the hash must start with at least this many zero bits. If we read the hash as a 256-bit number, this means the hash must be smaller than `2^(256-Bits)`.
- **`Nonce`** is the field the miner changes. This is the third time this series has met the word {{< term "nonce" "nonce" >}}, and each time it has meant something different. In the keys post it was a secret number inside a signature, in the previous post a sequence number. Here it is just a number the miner keeps increasing until the hash meets the condition. What the three have in common is that each is a number used "for one occasion".

The {{< term "block-header" "header" >}} is now 96 bytes. Because `Bits` is inside the header, the hash covers it too; a miner cannot claim after mining that they solved a harder puzzle.

Mining itself is a simple loop:

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

`MeetsTarget` hashes the header and counts its leading zero bits. If there are enough, we are done. If not, `Nonce` goes up by one and we try again. There is no cleverer way; looking at a hash tells you nothing about which nonce is closer to a better hash. `maxTries` only exists so the loop can be stopped after a set number of tries; it comes in handy in the simulation later.

A note on Bitcoin: according to the Bitcoin docs, instead of a count of zero bits its header stores a full 256-bit **{{< term "difficulty-target" "target" >}}** in a compact form, and the hash must be below it. That way the difficulty can move up or down by any factor. Counting zero bits is easier to read, but it has a cost: the difficulty can only double or halve. We will see that cost in the retarget table.

## Mining one block

`go run ./cmd/toychain mine` mines a genesis block three times, at three different difficulties. Then it mines it once more at difficulty 20 and, after the answer is found, moves only the `Timestamp` forward by one second:

```
bits  8: nonce      28,      29 hashes, hash 002acbe8e52ec14be233...
bits 16: nonce   49014,   49015 hashes, hash 0000af50878911463738...
bits 20: nonce 1908273, 1908274 hashes, hash 0000084c8f5cc05e63b2...
timestamp +1 after mining: 3c89edab33b4024d79b0..., meets target: false
```

To read the hashes, it helps to know that each hex digit is four bits:

- **Difficulty 8:** nonce 28 worked. Since we started at zero, that was 29 tries. The hash starts with `00`, two zero hex digits, so 8 bits. We got lucky this time; the average is 256.
- **Difficulty 16:** 49,015 tries, and the hash starts with `0000`: 16 bits.
- **Difficulty 20:** almost 1.9 million tries. The hash starts with `00000`, five zero digits, so 20 bits.
- **The last line:** we took the block mined at difficulty 20 and changed only its time by one second. The hash is completely new and starts with `3c`, which has only two zero bits, not twenty. All those 1.9 million tries went up in smoke.

This asymmetry is the heart of the matter. Finding the answer took 1.9 million hashes, but anyone can check it is right with **one** hash. And any change to the block, even one second in the time, throws the work away.

## Each bit doubles the work

A single block depends on luck; we saw difficulty 8 solved in 29 tries instead of 256. To see the general rule we need an average. `go run ./cmd/toychain tries` mines 256 different headers for each difficulty from 8 to 18 bits and computes the average number of tries:

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

The columns: the difficulty, the average number of hashes actually needed, the expected number `2^bits`, and the ratio of each row's average to the previous row's.

The second and third columns are very close: the real average is about `2^bits`. The last column shows that each extra bit roughly doubles the work. Individual steps are noisy, from 1.68x to 2.33x, because 256 samples do not smooth out luck completely. But the trend is clear: from 8 to 18 bits, ten extra bits, the work grew about a thousand times, that is 2 to the power of 10.

## Validation

Mining alone is not enough; nodes must check the difficulty too. `AddBlock` now checks, in this order: the block links correctly to the previous one, its time is after the previous block's, `Bits` is what the chain's rules require, the hash meets the difficulty, and then the Merkle root and every transaction.

`go run ./cmd/toychain powcheck` hands four different blocks to the chain:

```
required bits: 8
unmined block:         block 1: hash does not meet the difficulty target
own bits 2 (21 hashes): block 1: wrong difficulty bits
mined, then tx edited: block 1: merkle root does not match transactions
mined (87 hashes):    <nil>
chainwork: genesis 256, tip 512
```

- **`required bits: 8`:** the chain's rules require 8 bits of difficulty for the next block.
- **`unmined block`:** a block that was never mined is rejected: its hash does not start with 8 zero bits.
- **`own bits 2`:** a lazy miner set the difficulty to 2 themselves and mined it in 21 tries. The hash meets the 2-bit condition, but the block is rejected: the chain's rules decide the difficulty, not the block's builder.
- **`mined, then tx edited`:** the block was mined correctly, but afterwards someone changed the recipient of a transaction. The header is untouched, so the proof of work is still fine, but the Merkle root no longer matches the transactions. To tamper with a transaction you have to change the Merkle root, and then you have to mine again.
- **`mined (87 hashes)`:** the same block with the original transaction, mined in 87 tries, is accepted.
- **The last line** is chainwork, which I explain a few sections down.

## Retargeting: keeping the block rate steady

So far the difficulty has been fixed. But the network's computing power is not. New miners arrive, some leave, hardware gets faster. If the difficulty stays fixed and the network's power quadruples, blocks are built four times as fast. We want the block rate to stay steady, say one block every 10 seconds, however much power the network has.

The fix is for the difficulty to adjust itself every so often. This is called a {{< term "difficulty-adjustment" "retarget" >}}. Every `RetargetInterval` blocks, `NextBits` looks at how long the last period took and how long it **should** have taken. If blocks came too fast, it raises the difficulty; too slow, it lowers it. Because our difficulty can only double or halve, `NextBits` rounds the ratio to the nearest power of two. And so that the difficulty does not jump too far at once, the change per period is at most 2 bits, four times in either direction.

There is one more important condition: every node must reach exactly the same answer. If one node says the next block's difficulty is 13 and another says 14, they disagree on which blocks are valid and the chain splits in two. That is why this code uses integers only, no floating point:

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

`want` is how long the period should have taken and `actual` is how long it really took. The question is: which power of two is their ratio closest to? On a scale of powers of two, the boundary between "one times" and "two times" is `2^0.5`, the square root of 2. The boundary between "two times" and "four times" is `2^1.5`, the square root of 8. To avoid square roots and floating point, the code squares both sides. For example, "`want/actual` is at least the square root of 8" is the same as "`want²` is at least 8 times `actual²`". So if blocks came at least 2.83 times faster than planned, 2 bits are added; at least 1.41 times, 1 bit. The last two cases are the same rule for slowness.

As far as I know, Bitcoin does this every 2016 blocks, with the same 4x limit. My code defaults to 8 blocks to keep the demos in later posts short.

To see a retarget in action, `go run ./cmd/toychain retarget` simulates a miner. In each "simulated second", the miner tries `hashrate` nonces. If it finds no answer, it moves the header's time forward one second and starts again from nonce zero. The hashes are real; only the clock is simulated. Halfway through we change the miner's power: first 400 hashes per second, then four times that, then an eighth of it. With 8-block periods the noise was so high that the table was unreadable, so this demo uses 32-block periods:

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

Each row is one period: the range of block heights, the miner's power, that period's difficulty, the average time between blocks, the total hashes of the period, and the chainwork up to the end of the period. The target is 10 seconds. Let's follow the story:

- **The first two periods (400/s):** at difficulty 12, about 4096 hashes per block, a miner doing 400 a second needs about 10 seconds on average. The spacings are 10.8 and 10.4 seconds, close to the target. The difficulty does not change.
- **The third period (1600/s):** the power quadrupled, but the difficulty is still 12, because a retarget only happens at the end of a period. Blocks arrive every 3.6 seconds.
- **The fourth period:** at the end of the previous period, the retarget saw that blocks had come 10 divided by 3.6, about 2.8 times, too fast. That is a little below the 2.83 boundary, so only **one** bit was added: difficulty 13. The spacing went to 6.2 seconds, still fast.
- **The fifth period:** one more bit, difficulty 14, and a spacing of 9.8 seconds. Back on target. It took two periods for the difficulty to catch up with the new power.
- **The sixth period (200/s):** the power dropped eightfold and the difficulty is still 14. Each block takes 67.3 seconds.
- **The seventh period:** the slowdown was more than 2.83 times, but the clamp allows at most 2 bits of decrease: difficulty 12. The spacing is 24.3 seconds, still slow.
- **The eighth period:** one more bit down, difficulty 11, and a spacing of 9.9 seconds.
- **`validate: <nil>`:** the whole chain, with all its difficulty changes, was checked again from the start and was valid.

The table shows both sides of the clamp. It prevents sudden jumps in difficulty, but when the network's power changes a lot all at once, the system takes several periods to catch up.

## Chainwork: the work behind a chain

The last column of the table is {{< term "chainwork" "chainwork" >}}: the sum of `2^Bits` over all blocks of the chain. Since `2^Bits` is the average number of hashes needed for one block, chainwork means "on average, how many hashes are behind this chain". We saw it in the `powcheck` output too: the genesis block at difficulty 8 has work 256, and adding one more block at the same difficulty brought the work to 512.

Compare the hashes column with the chainwork column in the table. Hashes is the real number of hashes the miner computed, which depends on luck. Chainwork is the expected number, computed from the difficulties alone, which any node can compute without trusting anyone else.

Chainwork is the answer to the question at the top of this post. Two posts from now we will see that when there are two versions of the chain, nodes pick the one with more chainwork, not necessarily the one with more blocks. A chain with more blocks but lower difficulty has less work behind it.

## Why this stops Sybil attacks

Back to the voting problem. In a {{< term "sybil-attack" "Sybil attack" >}}, one party pretends to be many. If every node had a vote, whoever started a thousand fake nodes would win, because starting nodes is free.

With proof of work, a fake identity costs nothing and gains nothing. The number of nodes does not matter; only the number of hashes counts, and computing hashes takes electricity and hardware. A thousand nodes on one laptop have the power of one laptop.

And now rewriting history is expensive too. Whoever wants to change a block has to redo the work of that block and of every block after it, and has to do it faster than the whole rest of the network, which meanwhile keeps extending the real chain.

## Consensus-code traps

- **Check proof of work before the expensive checks, and compare `Bits` with your own rule.** Checking the hash is a single hash, but checking every signature in a block is far more expensive. If you check signatures first, anyone can keep your node busy with unmined blocks full of transactions. And never accept the difficulty from the block itself; as `own bits 2` showed, the block's builder writes whatever number suits them.
- **Use integers only in consensus code.** Floating-point arithmetic may round slightly differently on different processors, compilers or languages. In most programs that difference does not matter, but here it means two nodes disagree on the next block's difficulty.
- **Block timestamps feed the retarget.** The miner writes `Timestamp` themselves. If they can write wrong times, they can fool the retarget and push the difficulty down. I only check that each block's time is later than the previous one's. As far as I know, Bitcoin is stricter: the time must be after the median time of the previous 11 blocks, and must not be too far in the future.

## Exercise

1. Replace `Bits` with a full 256-bit target (using `math/big`) and retarget by the exact ratio, still clamped at 4x.
2. Add a rule that a block's time must not be more than 2 hours ahead of the node's clock, and write a test for it.
3. Run the retarget simulation with 8, 32 and 128-block periods and see how the spread of block spacings changes.

## What's next

The next post is "P2P networking and gossip between nodes". So far everything has happened inside one program; there, several separate nodes connect over TCP and pass transactions and blocks among themselves, until we reach the point where two competing versions of the chain really appear.
