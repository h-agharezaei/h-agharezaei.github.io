+++
date = '2026-11-10T18:00:00+03:30'
draft = false
title = 'Forks, reorgs and the heaviest-chain rule'
description = 'Forks and reorgs in Go: a block tree, fork choice by chainwork, UTXO rollback with undo data and a double spend after a loopback network partition.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "reorg", "fork-choice", "bitcoin"]
cover = { image = "/images/covers/bc-forks-reorgs.png", alt = "Forks, reorgs and the heaviest-chain rule", hiddenInSingle = true }
+++

Two miners can find a block at the same height, and a {{< term "network-partition" "network partition" >}} can let two groups build separate histories for a while. The gossiping nodes of the [previous post](/posts/bc-p2p-gossip/) logged and ignored any block that competed with the tip. In [CAP and PACELC, correctly](/posts/ds-cap-pacelc/) terms, proof of work chooses availability: both sides keep producing blocks, and the losing side's history is undone afterwards.

In [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/) every block got a `Bits` field and the chain a running total of work. Now that total decides which branch wins.

I copied last post's module; `Chain` is now a tree.

> Go 1.27 on macOS (arm64). Local example code, loopback only. The keys are derived from words like "alice": public, demo only.

## A tree, not a list

```go
type node struct {
	block   Block
	parent  *node
	work    *big.Int // chainwork: sum of Work(bits) from genesis to here
	undo    Undo     // set while the block is on the active chain
	invalid bool     // failed full validation when we tried to connect it
}

type Chain struct {
	params Params
	index  map[Hash]*node
	active []*node // active[h] is the active block at height h
	utxo   UTXOSet
}
```

`AddBlock` checks the header of every block against its own parent: link, timestamp, `Bits` for that branch, proof of work, Merkle root. Then it compares {{< term "chainwork" "chainwork" >}}. Less or equal: the block is stored as a side branch, transactions not checked yet; on a tie the first block seen stays. More: the branch becomes active.

That is the {{< term "fork-choice-rule" "fork-choice rule" >}}: most work, not most blocks.

## Longer is not heavier

`go run ./cmd/toychain forkchoice` builds both branches in one process. Four shared blocks, then branch b with slow timestamps and branch a with fast ones. At height 8 the retarget lowers b's difficulty and raises a's:

```
common    4 bits 10: extended    tip  4, tip work  5120
branch b  5 bits 10: extended    tip  5, tip work  6144
...
branch b  7 bits 10: extended    tip  7, tip work  8192
branch b  8 bits  8: extended    tip  8, tip work  8448
...
branch b 13 bits  8: extended    tip 13, tip work  9728
branch a  5 bits 10: side branch tip 13, tip work  9728
branch a  6 bits 10: side branch tip 13, tip work  9728
branch a  7 bits 10: side branch tip 13, tip work  9728
branch a  8 bits 12: reorg       tip  8, tip work 12288, disconnected 9, connected 4
branch a  9 bits 12: extended    tip  9, tip work 16384
b: height 13, work 9728; a: height 9, work 16384
known blocks: 19 active: 10 validate: <nil>
```

Block 8 of branch a is worth 4096, as much as 16 of b's blocks, and the tip went from height 13 to 8. Counting blocks would let cheap blocks with fake timestamps win.

## The reorg

A {{< term "chain-reorganization" "reorg" >}} has three steps: find the common ancestor, disconnect the old blocks from the tip down, connect the new ones from the ancestor up.

Disconnecting needs the old UTXO state. Replaying from genesis is simple but costs the whole chain each time, so each connected block keeps undo data: the outputs it spent.

```go
func (u UTXOSet) DisconnectBlock(txs []Tx, undo Undo) UTXOSet {
	prev := maps.Clone(u)
	for _, tx := range txs {
		id := tx.ID()
		for i := range tx.Outputs {
			delete(prev, OutPoint{TxID: id, Index: uint32(i)})
		}
	}
	for _, s := range undo {
		prev[s.OutPoint] = s.Out
	}
	return prev
}
```

As far as I know, Bitcoin Core stores undo data next to its block files for the same reason. If a block of the new branch fails its transactions, it and its descendants are marked invalid, the old branch is put back, and the node disconnects the peer that sent it. A test checks that the UTXO set after two reorgs equals a replay from genesis.

The non-coinbase transactions of disconnected blocks that are not in the new branch come back in `Result.Unconfirmed`. The node re-adds the ones still valid to pending.

## A partition on loopback

`go run ./cmd/toychain partition`: four nodes in a line share block 1, then split into {A,B} and {C,D}. Alice pays Bob 30 on one side and pays the same coin to Mallory on the other, a {{< term "double-spend" "double spend" >}}. The miner also pays Bob 10 on the A/B side. A mines one block, D mines two:

```
toBob ef4d0ece5dfd, minerToBob ae9aaa78f115, toMallory 2864f55b62ad
[A] mined block 2 0000b06c35d8 (bits 12, 6607 hashes, 3 txs), sent to 1 peers
[D] mined block 2 00039be25c01 (bits 12, 5012 hashes, 2 txs), sent to 1 peers
[D] mined block 3 000f3bde1876 (bits 12, 858 hashes, 1 txs), sent to 1 peers
B sees bob 40, pending 0
== heal: B connects to C
[B] connected to C (its height 3 work 16384, mine 2 work 12288)
[C] getblocks by B: fork point 1, sent 2 blocks
[B] block 2 00039be25c01 from C: side branch (work 12288, mine 12288)
[B] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
[B]   tx ae9aaa78f115 from the old branch back to pending
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B] block 3 000f3bde1876 from C: reorg, 1 txs, relayed to 1
[A] block 3 000f3bde1876 from B: parent unknown, sending locator
[B] getblocks by A: fork point 1, sent 2 blocks
[A] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
...
A: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
B: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
C: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
D: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
```

Before healing, Bob had 40 with one confirmation. After it, the miner's payment is pending again, and Alice's payment is gone for good because its coin went to Mallory. To find the fork point, a node sends a block locator: its last 10 hashes, then hashes with doubling gaps. A's block 2 is now a {{< term "stale-block" "stale block" >}}, and its coinbase vanished too. As far as I know, that is why Bitcoin makes coinbase outputs wait 100 blocks before they can be spent.

## Why exchanges wait

A block is never final in proof of work; it only gets harder to replace as work piles on top of it. That is {{< term "probabilistic-finality" "probabilistic finality" >}}. The Bitcoin whitepaper shows that an attacker with less than half the hash power falls behind exponentially, so each {{< term "confirmation" "confirmation" >}} lowers the risk. Six confirmations is a common convention for Bitcoin; exchanges set their own numbers per chain and amount. Bob just saw why one is not enough.

## Reorg traps

- Choose by chainwork, never by height.
- Validate side-branch headers immediately and their transactions when they become active; mark failures so their children are refused.
- Keep undo data, or you pay a full replay on every reorg.
- Re-check transactions returned by a reorg: some are double-spent.

## Exercise

1. Re-broadcast the transactions that went back to pending, so C and D learn about the miner's payment.
2. Add a `Confirmations(txid)` method and a wallet rule that waits for 3.
3. Prune side branches more than 100 blocks below the tip.

## What's next

Next post: **The mempool, fees and transaction selection**. Our pending map becomes a real mempool.
