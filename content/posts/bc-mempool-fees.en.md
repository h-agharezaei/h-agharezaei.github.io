+++
date = '2026-11-11T18:00:00+03:30'
draft = false
title = 'The mempool, fees and transaction selection'
description = 'A mempool in Go: admission by fee rate, block templates with ancestor packages, replace-by-fee, eviction when full and re-broadcast after a reorg.'
categories = ["Blockchain"]
series = ["Blockchain"]
tags = ["blockchain", "go", "mempool", "fees", "bitcoin"]
cover = { image = "/images/covers/bc-mempool-fees.png", alt = "The mempool, fees and transaction selection", hiddenInSingle = true }
+++

In the [previous post](/posts/bc-forks-reorgs/) a reorg put a transaction back into `pending`, but nobody re-broadcast it. Also, zero fees were fine, a block took everything, nothing limited the map, and spending an unconfirmed output was rejected.

A fee is inputs minus outputs, as in [Transactions and the UTXO model](/posts/bc-transactions-utxo/), and the miner collects it in the coinbase ([Proof of work, difficulty and mining](/posts/bc-proof-of-work-mining/)). I copied last post's module and replaced the map with a {{< term "mempool" "mempool" >}} package.

> Go 1.27 on macOS (arm64). Local example code, loopback only. The keys are derived from words like "alice": public, demo only.

## Fee per byte, not fee

Block space is limited; mine is tiny (`MaxBlockBytes = 1000`, coinbase included). A miner sells bytes, so it compares the {{< term "fee-rate" "fee rate" >}}: fee divided by encoded size. A one-input, one-output transaction is 205 bytes here, so a 1-coin fee is 4.9 coins per kB.

```go
type Rate struct {
	Fee  uint64
	Size int
}

func (r Rate) Less(o Rate) bool { return r.Fee*uint64(o.Size) < o.Fee*uint64(r.Size) }
```

Cross-multiplying avoids floats. `Add` validates a transaction against the tip's UTXO set plus the outputs of other mempool transactions, then applies policy: at least 1 coin per kB, a byte limit for the pool, conflict rules. That is local policy, not consensus.

## Parents, children and packages

A child may spend an output of an unconfirmed parent. I could require the parent to be selected first and judge each transaction by its own rate, but then a cheap parent waits even if its child pays a lot. So I judge a transaction together with its unselected ancestors, which makes {{< term "child-pays-for-parent" "child pays for parent" >}} work. The core of `Template`:

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

The best set goes in parents first, and the loop repeats. Maximizing fees under a size limit is a {{< term "knapsack" "knapsack" >}} problem; this is the {{< term "greedy-algorithm" "greedy" >}} approximation from [Greedy algorithms and backtracking](/posts/algo-greedy-backtracking/). As far as I know, Bitcoin Core has long built its {{< term "block-template" "block template" >}} by ancestor package fee rate too.

## A run

`go run ./cmd/toychain mempool`: genesis splits 50 coins among seven people who pay a shop; erin pays her second key (`parent`), which pays the shop (`child`). The pool holds at most 1300 bytes:

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

Alone, `parent` would come last; with its child it beats carol. One more transaction would make 1101 bytes.

## Replace-by-fee

Two transactions spending one output conflict. With {{< term "replace-by-fee" "replace-by-fee" >}} the newcomer may replace the old one. My rule: a higher fee rate than each transaction it conflicts with, and a higher absolute fee than everything that leaves, descendants included. Otherwise erin could swap parent and child (5 coins) for a transaction paying 2:

```
== replace-by-fee
alice-2  fee 2, 205 B, 9.8/kB  ok, replaced alice
alice-2b rejected: replacement must pay a higher fee rate than each tx it conflicts with: 9.8/kB <= 9.8/kB
erin-2   rejected: replacement must pay more fee than everything it replaces: 2 <= 5
```

BIP-125 adds more: pay for its own relay, no new unconfirmed inputs, at most 100 evicted transactions, and an opt-in signal that, as far as I know, recent Bitcoin Core versions no longer require. I implemented none of that. So an unconfirmed payment is only a promise: a {{< term "double-spend" "double spend" >}} with a higher fee wins.

## A full pool

Without a limit, anyone could fill a node's memory with cheap transactions, a {{< term "denial-of-service" "denial of service" >}}. When the pool is full, the lowest-scoring transaction leaves with its descendants. The score is the better of its own rate and the rate with its descendants, protecting a cheap parent with a rich child. A newcomer must beat what it evicts:

```
== full pool: 1230 B used
grace    fee 4, 205 B, 19.5/kB ok, evicted dave (4.9/kB)
heidi    rejected: mempool full: 4.9/kB does not beat the lowest score 9.8/kB
== mine a block from the template
block 1: 5 txs, fees 12; mempool: 4 removed, 0 dropped, left: carol alice-2
```

## Blocks, reorgs and re-broadcast

After every block the node rebuilds the pool against the new tip: confirmed transactions leave, transactions from disconnected blocks are tried first, then the rest in arrival order; what is now double spent or lost its parent drops out. Bitcoin Core updates incrementally instead; rebuilding is simpler.

Re-added transactions are re-broadcast. The partition from the previous post again, with a 1-coin fee on two payments (trimmed):

```
[B] REORG: disconnect [2:000089], connect [2:0007d5 3:000b42]
[B]   tx ef4d0ece5dfd from the old branch dropped: input 0: input is unknown or already spent
[B]   tx 4eb5ab26deff from the old branch back to the mempool, re-broadcast to 2
...
[C] tx 4eb5ab26deff from B: valid, relayed to 1
...
[D] tx 4eb5ab26deff from C: valid, relayed to 0
...
C: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
D: tip 3 000b42f2e39f, bob 0, mallory 150, pending 1
```

Last time C and D ended with `pending 0`. `go test -race ./...` passes, including a reorg that returns a child before its parent.

## A few things to watch

- Sort by fee per byte, and judge a child with its unconfirmed ancestors.
- A replacement must pay for everything it removes.
- Bound the mempool; evict by package score, not own rate.
- Mempool rules are local policy; consensus only defines a valid block.

## Exercise

1. Add the BIP-125 rule against new unconfirmed inputs in a replacement, with a test.
2. After an eviction, raise the minimum rate to the evicted rate and halve it every 10 blocks.

## What's next

Next post: **Bitcoin Script: a tiny stack interpreter in Rust**.
