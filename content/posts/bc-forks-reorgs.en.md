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

Imagine two miners, one in Tokyo and one in Berlin, each finding a valid block 5 within the same second. Each of them sends its block to its own peers. A few seconds later half of the network has the Tokyo block as block 5, and the other half has the Berlin one. Both blocks are valid. Both point to the same block 4. Which one is "the" block 5?

The same thing can happen on a larger scale. If the network is cut in two for a while, a {{< term "network-partition" "network partition" >}}, each half keeps mining on its own and builds its own history. When the connection comes back, there are two versions of the chain, and the nodes have to agree on one of them.

The gossiping nodes of the [previous post](/posts/bc-p2p-gossip/) had no answer to this. If a block arrived at a height they already had, they wrote a line in the log and ignored it. This post gives them an answer. In the language of [CAP and PACELC, correctly](/posts/ds-cap-pacelc/), proof of work chooses availability: during a partition both sides keep producing blocks, and afterwards the losing side's history is undone.

I took a copy of the previous post's module. The big change is that `Chain` is no longer a list of blocks; it is a tree.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example and only uses loopback. The keys are derived from words like "alice", so they are public and only good for a demo.

## Two branches from one block

When two blocks point to the same parent, the chain has split into two branches. This is called a **fork**. A fork in itself is not an error; it happens naturally whenever two blocks are built at about the same time.

The core idea of this post is this: a node keeps every valid block it receives, even those that are not on its current chain. Out of all the branches, it treats the one with the most work behind it as the real chain. If another branch later gets more work, the node switches to it.

To do that, we need a tree instead of a list:

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

- Each `node` is one block in the tree, with a pointer to its parent. Several nodes can have the same parent; that is a fork.
- `work` is the total work from genesis up to this block. We keep it on every node, so we never have to add it up again.
- `index` finds any block we know by its hash, whether it is on the main branch or not.
- `active` is the branch we currently consider the real chain, the **active chain**. `active[h]` is its block at height `h`.
- `utxo` is the set of unspent outputs at the tip of the active chain. There is only one, and it always belongs to the active chain.

`undo` and `invalid` are explained further down.

## Which branch wins

In [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/) we defined {{< term "chainwork" "chainwork" >}}: the sum of `2^Bits` over the blocks of a chain, that is, how many hashes on average were needed to build it. Now that number decides which branch wins. The rule that picks one branch out of several is called the {{< term "fork-choice-rule" "fork-choice rule" >}}, and ours is: **the branch with the most work wins, not the one with the most blocks**.

`AddBlock` handles a new block in two steps.

First it checks the block's header against its own parent, not against the tip of the active chain: is the height one more than the parent's, is the timestamp after the parent's, is `Bits` the value the retarget requires on that branch, does the hash meet the difficulty, and does the Merkle root match the transactions. These checks are cheap, and each one only needs the block and its parent.

Then it compares the work of the new block's branch with the work of the active chain:

- **Less or equal:** the block is stored as a side branch. Its transactions are not checked yet, because checking them needs the UTXO state of that branch, and that branch may never become active. If the work is exactly equal, the block seen first stays active.
- **More, and its parent is the tip:** the simple case. The transactions are checked and the block is added to the end of the active chain.
- **More, but its parent is not the tip:** the branch has overtaken the active chain, and we have to switch to it. That is a reorg, which comes in the next section.

Why work and not the number of blocks? Because counting blocks is easy to cheat. Here is a concrete example.

## Longer is not heavier

`go run ./cmd/toychain forkchoice` needs no network; it builds two branches inside one chain. First there are four shared blocks. Then branch b is built from block 4 with slow timestamps, 100 seconds apart, and after it branch a from the same block 4 with fast ones, 1 second apart. Our retarget runs every 8 blocks. At height 8 it sees that branch b's blocks came much too slowly and lowers its difficulty by two bits, the maximum. For branch a it sees the opposite and raises the difficulty by two bits.

```
common    1 bits 10: extended    tip  1, tip work  2048
common    2 bits 10: extended    tip  2, tip work  3072
common    3 bits 10: extended    tip  3, tip work  4096
common    4 bits 10: extended    tip  4, tip work  5120
branch b  5 bits 10: extended    tip  5, tip work  6144
branch b  6 bits 10: extended    tip  6, tip work  7168
branch b  7 bits 10: extended    tip  7, tip work  8192
branch b  8 bits  8: extended    tip  8, tip work  8448
branch b  9 bits  8: extended    tip  9, tip work  8704
branch b 10 bits  8: extended    tip 10, tip work  8960
branch b 11 bits  8: extended    tip 11, tip work  9216
branch b 12 bits  8: extended    tip 12, tip work  9472
branch b 13 bits  8: extended    tip 13, tip work  9728
branch a  5 bits 10: side branch tip 13, tip work  9728
branch a  6 bits 10: side branch tip 13, tip work  9728
branch a  7 bits 10: side branch tip 13, tip work  9728
branch a  8 bits 12: reorg       tip  8, tip work 12288, disconnected 9, connected 4
branch a  9 bits 12: extended    tip  9, tip work 16384
b: height 13, work 9728; a: height 9, work 16384
known blocks: 19 active: 10 validate: <nil>
```

Each line is one block: which branch, its height, its difficulty, what `AddBlock` did with it, and the height and work of the active chain after that.

- **Shared blocks:** with difficulty 10, each block is worth `2^10`, that is 1024. The genesis block is worth 1024 too, so at height 4 the work is 5120.
- **Branch b:** until height 7 each block adds 1024. From height 8 the difficulty drops to 8, and each block is worth only 256. Branch b reaches height 13 with work 9728. Until now it is the only branch, so every block says `extended`.
- **Branch a, heights 5 to 7:** these blocks still have difficulty 10. At height 7 branch a's work is 8192, less than b's 9728, so they are stored as `side branch` and the tip stays at 13.
- **Branch a, height 8:** after its retarget, this block has difficulty 12 and is worth 4096 on its own, as much as 16 of branch b's blocks. Branch a's work reaches 12288, more than 9728. The node switches: it disconnects the 9 blocks of branch b (heights 5 to 13) and connects the 4 blocks of branch a (heights 5 to 8). The tip goes **back** from height 13 to height 8.
- **The last lines:** branch b is longer (13 against 9), but branch a has much more work (16384 against 9728). The tree knows 19 blocks: genesis, 4 shared, 9 from b and 5 from a. The active chain has 10 of them (heights 0 to 9), and validating it again from the start finds no problem.

If nodes counted blocks, branch b would win, and it was built with fake timestamps that made its blocks cheap. With chainwork, cheap blocks cannot beat expensive ones just by being many.

## The reorg

Switching from one branch to another is called a {{< term "chain-reorganization" "reorg" >}} (short for reorganization). It has three steps:

1. **Find the common ancestor:** walk back from the new block until we reach a block that is on the active chain. In the demo above, that was block 4.
2. **Disconnect the old blocks**, from the tip down to the ancestor.
3. **Connect the new blocks**, from the ancestor up to the new tip.

Connecting is easy: it is the same as adding a block normally. Disconnecting is the hard part. When we disconnect a block, the UTXO set must go back to exactly what it was before that block. The simplest way is to build the UTXO set again from genesis. That is correct, but on every reorg we would pay for the whole chain.

There is a cheaper way. When a block is connected, it does two things to the UTXO set: it adds its new outputs, and it removes the outputs it spends. The new outputs can be found again from the block's own transactions. The spent outputs cannot, because they are gone from the set. So when we connect a block, we keep the outputs it spent, as **undo data**. That is the `undo` field. Disconnecting is then exactly the reverse of connecting:

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

First it removes every output the block created, then it puts back every output the block spent. As far as I know, Bitcoin Core also stores undo data next to its block files on disk, for the same reason.

Two details make the reorg safe:

- **A new branch may turn out to be invalid.** Its headers were checked when it arrived, but its transactions are checked only now, while connecting. If a block of the new branch fails, that block and every block built on it are marked `invalid`, the old branch and its UTXO set are put back exactly as they were, and the node disconnects the peer that sent it. A later block whose parent is marked invalid is rejected right away.
- **Transactions of the old branch must go somewhere.** A transaction that was in a disconnected block and is not in the new branch is not lost, but it is no longer confirmed. These come back in `Result.Unconfirmed`. The node checks each one again against the new UTXO set: if it is still valid, it goes back to pending; if not, it is dropped.

A test builds two branches, switches to the second and back to the first, and checks after each switch that the UTXO set is exactly what replaying the active chain from genesis gives.

## A partition on loopback

Now let's see all of this on a real network. `go run ./cmd/toychain partition` connects four nodes in a line: A to B, B to C, C to D. A mines block 1, and it reaches everybody. Then:

1. All connections are dropped, and only A-B and C-D are reconnected. The network is now cut into two halves, {A,B} and {C,D}.
2. On the A/B side, Alice pays Bob 30 coins, and the miner pays Bob 10 coins.
3. On the C/D side, Alice spends **the same coin** again, this time paying 50 to Mallory. Spending one coin twice is a {{< term "double-spend" "double spend" >}}. Each half sees only one of the two payments, so on each side it looks valid.
4. A mines one block on its side. D mines two blocks on its side, and pays the reward for both to Mallory's address.
5. Finally B connects to C, and the network is whole again.

I removed the lines from before the partition. Because the nodes run concurrently, the order of lines can change from run to run; the hashes are the same every time.

```
== partition: {A,B} and {C,D}
[B] connected to A (its height 1 work 8192, mine 1 work 8192)
[A] connected to B (its height 1 work 8192, mine 1 work 8192)
[C] connected to D (its height 1 work 8192, mine 1 work 8192)
[D] connected to C (its height 1 work 8192, mine 1 work 8192)
toBob ef4d0ece5dfd, minerToBob ae9aaa78f115, toMallory 2864f55b62ad
[B] tx ef4d0ece5dfd submitted locally, sent to 1 peers
[B] tx ae9aaa78f115 submitted locally, sent to 1 peers
[A] tx ef4d0ece5dfd from B: valid, relayed to 0
[C] tx 2864f55b62ad submitted locally, sent to 1 peers
[A] tx ae9aaa78f115 from B: valid, relayed to 0
[D] tx 2864f55b62ad from C: valid, relayed to 0
[A] mined block 2 0000b06c35d8 (bits 12, 6607 hashes, 3 txs), sent to 1 peers
[B] block 2 0000b06c35d8 from A: extended, 3 txs, relayed to 0
[D] mined block 2 00039be25c01 (bits 12, 5012 hashes, 2 txs), sent to 1 peers
[D] mined block 3 000f3bde1876 (bits 12, 858 hashes, 1 txs), sent to 1 peers
[C] block 2 00039be25c01 from D: extended, 2 txs, relayed to 0
[C] block 3 000f3bde1876 from D: extended, 1 txs, relayed to 0
B sees bob 40, pending 0
== heal: B connects to C
[C] connected to B (its height 2 work 12288, mine 3 work 16384)
[B] connected to C (its height 3 work 16384, mine 2 work 12288)
[C] getblocks by B: fork point 1, sent 2 blocks
[B] block 2 00039be25c01 from C: side branch (work 12288, mine 12288)
[B] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
[B]   tx ae9aaa78f115 from the old branch back to pending
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B] block 3 000f3bde1876 from C: reorg, 1 txs, relayed to 1
[A] block 3 000f3bde1876 from B: parent unknown, sending locator
[B] getblocks by A: fork point 1, sent 2 blocks
[A] block 2 00039be25c01 from B: side branch (work 12288, mine 12288)
[A] REORG: disconnect [2:0000b0], connect [2:00039b 3:000f3b]
[A]   tx ae9aaa78f115 from the old branch back to pending
[A]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[A] block 3 000f3bde1876 from B: reorg, 1 txs, relayed to 0
A: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
B: tip 3 000f3bde1876, bob 0, mallory 150, pending 1
C: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
D: tip 3 000f3bde1876, bob 0, mallory 150, pending 0
```

This one is worth reading slowly, in four parts.

**During the partition.** The handshake now also says how much work each side has; at height 1 both halves have 8192. The three transactions get their IDs: `toBob`, `minerToBob` and `toMallory`. The first two reach A, and the third reaches D. A mines block 2 with 3 transactions: the coinbase, and the two payments to Bob. On the other side, D mines blocks 2 and 3. Its block 2 holds the coinbase and the payment to Mallory, and its block 3 only a coinbase.

**What B sees before healing.** `B sees bob 40, pending 0`: from B's point of view, Bob has received 30 from Alice and 10 from the miner, and both payments are in a block. Bob's payment has one {{< term "confirmation" "confirmation" >}}: one block contains it. If Bob trusted that and handed over the goods, he would regret it a moment later.

**Healing.** B connects to C. In the handshake C says it has work 16384, and B has 12288. C has more, so B asks it for blocks. To ask, B does not just send its height, because after a fork the height alone does not say where the two chains part ways. Instead it sends a **block locator**: a list of hashes from its own active chain, the last 10 one by one, and after that with gaps that double each time, back to genesis. C finds the highest hash in the list that is also on its own active chain. Here that is block 1, the `fork point 1` in the log, and C sends what comes after it: 2 blocks.

- Block 2 from C has the same work as B's own block 2 (12288 each). It is equal, not more, so B stores it as a side branch, and its own block stays.
- Block 3 from C takes that branch to 16384, more than 12288. B reorgs: it disconnects its own block 2 (`0000b0`) and connects C's blocks 2 and 3 (`00039b` and `000f3b`).
- Then come the transactions of the disconnected block. `minerToBob` spends the miner's coin from block 1, which is still in the shared history, so it is still valid and goes back to pending. But `toBob` spends Alice's coin, which in the new branch has already gone to Mallory, so it is dropped for good.
- B passes block 3 on to A. A does not have its parent (C's block 2), so it sends B its own locator. The same story repeats on A.

**The end.** All four nodes are on the same tip, `000f3b`. Bob has 0 coins. Mallory has 150: Alice's 50, plus two block rewards of 50, because D mined both of its blocks to her address. A and B have one pending transaction, the miner's payment to Bob. C and D have none, because they never heard of it; nobody sends a transaction that went back to pending to the network again (that is exercise 1).

A's block 2 is no longer on any active chain. A valid block that ends up off the winning chain is called a {{< term "stale-block" "stale block" >}}. Its coinbase vanished with it, so the reward A mined disappeared. As far as I know, that is why Bitcoin makes a coinbase output wait 100 blocks before it can be spent: if a reorg removes the block, nobody has passed that money on in the meantime.

## Why exchanges wait

That run explains something you may have seen on exchanges: after a deposit, they wait for several confirmations before crediting it. In proof of work, a block is never final. It just gets harder to replace as more blocks are built on top of it, because to replace it someone has to redo its work and the work of every block after it. Finality that only grows more likely with time, and never becomes certain, is called {{< term "probabilistic-finality" "probabilistic finality" >}}.

According to the Bitcoin whitepaper, for an attacker with less than half of the network's hash power, the chance of ever catching up drops exponentially with the number of blocks they are behind. So every extra confirmation lowers the risk. Six confirmations is a common convention for Bitcoin; exchanges set their own numbers for each chain and amount. Bob just saw why one confirmation is not enough.

## Reorg traps

- **Choose by chainwork, never by height.** As the `forkchoice` demo showed, a longer branch with cheap blocks can have much less work behind it. Choosing by height lets whoever can make cheap blocks win.
- **Check side-branch headers right away, and their transactions when they become active.** Checking headers is cheap and stops unmined garbage at the door. Transactions need the UTXO state of that branch, so they can only be checked during the reorg. When a block fails, mark it and everything built on it, so its children are refused right away later.
- **Keep undo data.** Without it, every reorg means rebuilding the UTXO set from genesis, and the cost grows with the length of the chain.
- **Check the transactions a reorg returns again.** Not every one of them can go back to pending; some were double-spent in the new branch, like Alice's payment to Bob.

## Exercise

1. Send the transactions that went back to pending to the network again, so C and D also learn about the miner's payment.
2. Add a `Confirmations(txid)` method, and a wallet rule that waits for 3 confirmations.
3. Delete side branches that are more than 100 blocks below the tip.

## What's next

The next post is "The mempool, fees and transaction selection". Our pending list is a simple map right now; there it becomes a real mempool, and we see how a miner chooses which transactions go into its block.
