+++
date = '2026-11-11T18:00:00+03:30'
draft = false
title = 'The mempool, fees and transaction selection'
description = 'A mempool in Go: admission by fee rate, block templates with ancestor packages, replace-by-fee, eviction when full and re-broadcast after a reorg.'
contentType = 'tutorial'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "mempool", "fees", "bitcoin"]
cover = { image = "/images/covers/bc-mempool-fees.png", alt = "The mempool, fees and transaction selection", hiddenInSingle = true }
+++

Suppose a hundred transactions are waiting in the network, and the next block only has room for twenty. Which twenty go in? Who decides, and by what rule? And what happens to the eighty that are left out?

Until now our nodes had a simple answer: they did not ask the question. Valid transactions that were not in a block yet went into a map called `pending`, and every miner put all of them into its next block. That map had four problems. It accepted transactions with no fee at all. It had no size limit, so it could grow without end. A block could take everything in it. And a transaction could not spend an output of another transaction that was still pending. A fifth problem showed up in the [previous post](/posts/bc-forks-reorgs/): after the reorg, a transaction went back to `pending`, but nobody sent it to the network again, so C and D never heard of it.

This post replaces that map with a real {{< term "mempool" "mempool" >}}, short for memory pool: the waiting room where each node keeps valid transactions that are not in a block yet. The main question of this post is how a miner chooses from that waiting room.

The answer has to do with fees. As we saw in [Transactions and the UTXO model](/posts/bc-transactions-utxo/), a transaction's fee is not a separate field. It is simply its inputs minus its outputs: whatever the sender does not assign to anybody. The miner who puts the transaction in a block collects that difference in its coinbase, as in [Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/). So the miner has a reason to prefer transactions that pay more.

I took a copy of the previous post's module and replaced the `pending` map with a `mempool` package.

> Everything below was run with Go 1.27 on macOS (arm64), and the output is what I saw. The code is a local example and only uses loopback. The keys are derived from words like "alice", so they are public and only good for a demo.

## Fee per byte, not fee

A block has limited space. In my toy chain it is very small on purpose: `MaxBlockBytes = 1000`, coinbase included, so only a few transactions fit. What the miner sells is not "a place for a transaction" but bytes of space.

A concrete example makes the difference clear. Transaction X pays a fee of 4 coins and is 800 bytes. Transaction Y pays 2 coins and is 200 bytes. X pays more in total, but for the same 800 bytes the miner could take four transactions like Y and earn 8 coins. So the miner compares the {{< term "fee-rate" "fee rate" >}}: the fee divided by the transaction's size in bytes. I show it in coins per kilobyte (`/kB`). Here a simple transaction with one input and one output is 205 bytes, so a 1-coin fee means about 4.9 coins per kB.

```go
type Rate struct {
	Fee  uint64
	Size int
}

func (r Rate) Less(o Rate) bool { return r.Fee*uint64(o.Size) < o.Fee*uint64(r.Size) }
```

`Rate` keeps the fee and the size separately. To compare `a/b` with `c/d`, `Less` compares `a×d` with `c×b`. The answer is the same, but there is no division and no floating-point number, so there is no rounding. Two nodes that compare the same two rates always get the same answer.

When a transaction arrives, `Add` first checks it as before: do its inputs exist, are the signatures right, does it not spend more than it has. An input can come from the UTXO set of the tip, or from an output of another transaction in the mempool. Then the node applies its own rules: at least 1 coin per kB, a maximum total size for the pool (in bytes), and rules for conflicts, which come later.

There is an important distinction here. These rules are **local policy**, not consensus. Consensus rules decide whether a block is valid, and every node must apply them in exactly the same way. Mempool rules only decide what a node keeps in its own waiting room and passes on to others. Two nodes can have different minimum fees and both be right.

## Parents, children and packages

Now a more interesting case. Erin has 10 coins. She sends them to a second key of her own with a fee of 1 coin; call that transaction `parent`. Before `parent` is in a block, she spends its output from the second key and pays the shop, this time with a fee of 4; call that `child`. `child` spends an output that does not exist yet in any block. It exists only in the mempool. So `child` cannot go into a block unless `parent` goes into the same block before it, or into an earlier one.

`parent` pays 4.9 per kB on its own, which is cheap. `child` pays 19.5 per kB, which is expensive. How should the miner judge them?

If it judged each transaction only by its own rate, `parent` would stay at the back of the queue, and `child`, however much it paid, would wait with it. Instead we judge each transaction together with its ancestors that have not been chosen yet. That group is called a **package**. The package of `child` is `parent` plus `child`: 5 coins of fee for 410 bytes, which is 12.2 per kB. So a child that pays a lot pulls its cheap parent into the block. This is called {{< term "child-pays-for-parent" "child pays for parent" >}} (CPFP): the child pays the parent's share.

The core of `Template`, the function that picks a block's transactions:

```go
for id, e := range p.txs {
	if chosen[id] {
		continue
	}
	set := map[chain.Hash]bool{}
	for a := range p.ancestorsOf(map[chain.Hash]bool{id: true}) {
		if !chosen[a] {
			set[a] = true
		}
	}
	var pkg Rate
	for a := range set {
		pkg.Fee += p.txs[a].Fee
		pkg.Size += p.txs[a].Size
	}
	if size+pkg.Size > maxBytes {
		continue
	}
	if best == nil || bestPkg.Less(pkg) || (!pkg.Less(bestPkg) && e.seq < best.seq) {
		best, bestPkg, bestSet = e, pkg, set
	}
}
```

For each transaction that has not been chosen yet:

1. It collects the transaction and all its ancestors that have not been chosen yet (`set`).
2. It adds up their fees and sizes; that is the package's rate.
3. If the package does not fit in the remaining space, it skips it.
4. It keeps the package with the best rate. If two rates are equal, the transaction that arrived earlier wins (`seq` is the arrival order).

When the loop ends, the best package goes into the block, parents before children, and the whole loop runs again on what is left. This repeats until nothing else fits.

This result is not guaranteed to be the best possible one. Choosing items with the most total value under a size limit is the classic {{< term "knapsack" "knapsack" >}} problem, and solving it exactly gets expensive fast. What we do here is the {{< term "greedy-algorithm" "greedy" >}} approach from [Greedy algorithms and backtracking](/posts/algo-greedy-backtracking/): at each step take the best item at that moment, and never go back. It is fast and usually good. As far as I know, Bitcoin Core has also for years built its {{< term "block-template" "block template" >}}, the list of transactions of the next block, by the fee rate of ancestor packages.

## Trying it: admission and the template

`go run ./cmd/toychain mempool` runs a mempool against a chain, without a network. The genesis block splits 50 coins among seven people: alice 10, bob 10, carol 8, dave 4, erin 10, grace 6, heidi 2. Each of them pays the shop with a different fee, and erin does the `parent`/`child` trick from above. The pool holds at most 1300 bytes, which is room for six transactions.

The first part is admission and building a block template:

```
== admission (min 1.0/kB, pool max 1300 B)
alice    fee 1, 205 B, 4.9/kB  ok
bob      fee 3, 205 B, 14.6/kB ok
carol    fee 2, 205 B, 9.8/kB  ok
dave-0   rejected: fee rate below the minimum: 0.0/kB < 1.0/kB
dave     fee 1, 205 B, 4.9/kB  ok
parent   fee 1, 205 B, 4.9/kB  ok
child    fee 4, 205 B, 19.5/kB ok
== template, max 1000 B incl. 76 B coinbase
1. bob     own 14.6/kB package 14.6/kB
2. parent  own 4.9/kB  package 12.2/kB
3. child   own 19.5/kB package 12.2/kB
4. carol   own 9.8/kB  package 9.8/kB
4 txs, 896 B, fees 10; left out: alice dave
```

- **Admission:** each line is one transaction: its fee, its size and its rate. All are 205 bytes, so the rate depends only on the fee. `dave-0` wanted to pay no fee at all and was rejected, because 0 is below the minimum of 1 per kB. Dave then tried again with a fee of 1 and was accepted. `child` was accepted even though its input is the output of `parent`, which is not in a block yet.
- **The template:** there is room for 1000 bytes, and 76 of them go to the coinbase. `bob` is chosen first, with 14.6. In the next round the best package is `child` with its parent, at 12.2, better than carol's 9.8. So `parent` and `child` go in together, parent first, and both are listed with the package rate 12.2. If `parent` were judged alone, at 4.9 it would have come last. Then `carol`.
- **The last line:** 4 transactions, 896 bytes with the coinbase, and 10 coins of fees for the miner (3 + 1 + 4 + 2). One more 205-byte transaction would make 1101 bytes, more than 1000. So alice and dave, the two cheapest, stay out and wait for a later block.

## Replace-by-fee

What if two transactions spend the same output? Then they conflict, and only one of them can ever go into a block. Our old `pending` map simply rejected the second one. But sometimes the sender has a good reason for the second one. Alice's transaction pays only 4.9 per kB and was left out of the template. She wants to raise its fee, so she signs the same payment again with a bigger fee.

{{< term "replace-by-fee" "Replace-by-fee" >}} (RBF) allows this: the newcomer can replace the older transaction if it pays enough. My rule has two parts:

1. Its fee **rate** must be higher than that of each transaction it directly conflicts with.
2. Its total fee must be higher than the total fee of **everything that leaves** the pool: the transactions it conflicts with, and all their descendants.

The second part matters, because replacing a transaction also removes its children: they spend an output that will no longer exist. Without that rule, a replacement could kick out transactions that paid more than it does.

```
== replace-by-fee
alice-2  fee 2, 205 B, 9.8/kB  ok, replaced alice
alice-2b rejected: replacement must pay a higher fee rate than each tx it conflicts with: 9.8/kB <= 9.8/kB
erin-2   rejected: replacement must pay more fee than everything it replaces: 2 <= 5
```

- **`alice-2`:** the same coin as alice, with a fee of 2 instead of 1. 9.8 is more than 4.9, and 2 is more than 1, so it replaces the old transaction.
- **`alice-2b`:** Alice tries once more, again with a fee of 2. Its rate is equal to that of `alice-2`, not higher, so it is rejected. If an equal fee were enough, anyone could make nodes replace and relay transactions over and over at no extra cost.
- **`erin-2`:** Erin spends the same coin as `parent` again, with a fee of 2. Its rate, 9.8, is higher than `parent`'s 4.9, so the first part of the rule passes. But replacing `parent` would also remove `child`, and those two together pay 5 coins. 2 is not more than 5, so it is rejected.

According to the Bitcoin docs, BIP-125, the document that defines replace-by-fee in Bitcoin, has more rules: the replacement must also pay for its own relay, it may not add new unconfirmed inputs, and it may replace at most 100 transactions. It also had an opt-in signal: the original transaction had to say it was replaceable. As far as I know, recent Bitcoin Core versions no longer require that signal by default. I implemented none of these extra rules.

The lesson for anyone who receives a payment: as long as a transaction is not in a block, it is only a promise. A {{< term "double-spend" "double spend" >}} with a higher fee can take its place.

## A full pool

Why does a mempool need a size limit at all? Because memory is finite. Without a limit, anyone could send a node a flood of cheap, valid transactions until its memory ran out. That is a {{< term "denial-of-service" "denial of service" >}} attack. So the pool has a maximum size, and when it is full and a new transaction arrives, either something leaves or the newcomer is turned away.

Which one leaves? The one with the lowest **score**, together with its descendants. The score is the better of two numbers: the transaction's own rate, and the rate of the transaction plus all its descendants. That protects a cheap parent with a rich child. `parent` on its own is worth 4.9, but with `child` it is worth 12.2, and it should not be the first to go. A newcomer is only accepted if its rate beats the score of what it would push out.

```
== full pool: 1230 B used
grace    fee 4, 205 B, 19.5/kB ok, evicted dave (4.9/kB)
heidi    rejected: mempool full: 4.9/kB does not beat the lowest score 9.8/kB
== mine a block from the template
block 1: 5 txs, fees 12; mempool: 4 removed, 0 dropped, left: carol alice-2
```

- **`full pool: 1230 B used`:** six transactions of 205 bytes are in the pool: alice-2, bob, carol, dave, parent and child. One more makes 1435, more than 1300.
- **`grace`:** pays 19.5 per kB. The lowest score in the pool is dave's 4.9 (parent's score is 12.2, as we saw, even though its own rate is also 4.9). 19.5 beats 4.9, so dave is evicted and grace comes in.
- **`heidi`:** pays only 4.9. The lowest score is now 9.8 (carol and alice-2), and 4.9 does not beat it, so heidi is turned away.
- **The mined block:** this time the template picks grace (19.5), bob (14.6) and the parent and child package (12.2). That is 4 transactions plus the coinbase, so 5 in total, with 12 coins of fees (4 + 3 + 1 + 4). After the block, the 4 confirmed transactions leave the pool. Nothing was dropped, and carol and alice-2 are still waiting.

## Blocks, reorgs and re-broadcast

The mempool must stay in step with the chain. After every new block, the node rebuilds the pool against the new tip, in this order:

1. Transactions that are now in a block leave the pool.
2. Transactions of blocks that a reorg disconnected are tried first, because they are the oldest.
3. Then the rest, in the order they arrived.

Anything that no longer fits drops out: for example a transaction that was double spent in the new branch, or a child whose parent is gone. Rebuilding the pool from scratch costs a signature check for every transaction on every block. As far as I know, Bitcoin Core updates its mempool step by step instead of rebuilding it. For a toy, rebuilding is simpler, and it is obvious that it is correct.

There is one more step: transactions that come back to the pool after a reorg are sent to the peers again. That is exactly what was missing last time. Here is the same partition demo as in the previous post, this time with a fee of 1 coin on the miner's payment to Bob and on the payment to Mallory, so the IDs are different. These are the lines after the network heals; the order of lines can change from run to run:

```
== heal: B connects to C
[C] connected to B (its height 2 work 12288, mine 3 work 16384)
[B] connected to C (its height 3 work 16384, mine 2 work 12288)
[C] getblocks by B: fork point 1, sent 2 blocks
[B] block 2 0007d5a15a1f from C: side branch (work 12288, mine 12288)
[B] REORG: disconnect [2:000089], connect [2:0007d5 3:000b42]
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B]   tx 4eb5ab26deff from the old branch back to the mempool, re-broadcast to 2
[B] block 3 000b42f2e39f from C: reorg, 1 txs, relayed to 1
[A] block 3 000b42f2e39f from B: parent unknown, sending locator
[B] getblocks by A: fork point 1, sent 2 blocks
[A] block 2 0007d5a15a1f from B: side branch (work 12288, mine 12288)
[C] tx 4eb5ab26deff from B: valid, relayed to 1
[A] REORG: disconnect [2:000089], connect [2:0007d5 3:000b42]
[D] tx 4eb5ab26deff from C: valid, relayed to 0
[A]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[A]   tx 4eb5ab26deff from the old branch back to the mempool, re-broadcast to 1
[A] block 3 000b42f2e39f from B: reorg, 1 txs, relayed to 0
A: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
B: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
C: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
D: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
```

The reorg itself is the same as last time: B and A disconnect their own block 2 and switch to the branch of C and D. Alice's payment to Bob (`ef4d…`) is dropped, because its coin has gone to Mallory. The new part is the miner's payment to Bob (`4eb5…`):

- B puts it back in the mempool and sends it to its **2** peers, A and C.
- C has never seen it. It checks it, accepts it, and passes it to D.
- D accepts it too.
- A also puts it back in its own pool after its reorg and sends it to its one peer, B, which already has it.

The last four lines show the result. Last time C and D ended with `pending 0`; now all four nodes have the miner's payment waiting in their mempool, and the next block that any of them mines can include it.

`go test -race ./...` passes. The tests cover a child pulling in its parent, replace-by-fee, eviction, and a reorg that returns a child before its parent, where the pool must still accept both.

## Non-negotiable mempool rules

- **Sort by fee per byte, not by fee.** A miner sells block space, so a large transaction with a large fee can be worth less than two small ones. And judge a child together with its unconfirmed ancestors; otherwise a cheap parent can hold up its rich child forever.
- **A replacement must pay for everything it removes.** Its children leave with it. If the replacement pays less than all of them together, miners lose money, and an attacker can push out good transactions cheaply.
- **Bound the mempool, and evict by package score, not by own rate.** Without a limit, memory is open to attack. With a limit but the wrong score, a parent whose child pays well can be evicted, and the child falls out with it.
- **Mempool rules are local policy.** Consensus only defines what a valid block is. Two nodes can have different mempool rules; but if a node rejects a valid block because of its own policy, it splits itself off from the network.

## Exercise

1. Add the BIP-125 rule that forbids a replacement from adding new unconfirmed inputs, and write a test for it.
2. After an eviction, raise the minimum rate to the rate of the evicted transaction, and halve it again every 10 blocks.

## What's next

The next post is "Bitcoin Script: a tiny stack interpreter in Rust". So far "this output belongs to Alice" has simply meant "it holds Alice's address"; there we see how Bitcoin turns ownership into a small program that the spender has to satisfy.
