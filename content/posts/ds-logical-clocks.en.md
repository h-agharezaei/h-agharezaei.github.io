+++
date = '2027-04-29T10:00:00+03:30'
draft = false
title = 'Logical clocks: Lamport and vector clocks'
description = 'Logical clocks in Go: Lamport and vector clocks checked against a true happens-before order on 5000 simulated runs, plus conflict detection.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "logical-clocks", "lamport", "vector-clock", "go"]
cover = { image = "/images/covers/ds-logical-clocks.png", alt = "Logical clocks: Lamport and vector clocks", hiddenInSingle = true }
+++

The previous post, [Consistency models](/posts/ds-consistency-models/), left one promise open: causal consistency needs a way to say "this happened before that" without trusting a clock. This post builds that tool. It leans on the skew discussion in [why distributed systems are hard](/posts/ds-why-distributed-is-hard/) and the last-write-wins warning in [CAP and PACELC, correctly](/posts/ds-cap-pacelc/).

> Honest labelling: everything is Go 1.26 in one process. The "processes" and the message delays are a **simulation** with seeded randomness (messages are picked at random from those in flight, so they reorder). It is not a network. Numbers are counts, never timings. Tests run with `go test -race`.

## Why wall clocks fail

Give each simulated process a wall clock with a fixed offset (0, -4 and +3 ticks, my invention to model {{< term "clock-skew" "clock skew" >}}) and stamp every event. Over 5000 runs, **3537** contained a message received with a wall timestamp no later than its own send, an effect stamped before its cause. The simulated offsets are mine, but the point stands: the order of timestamps is not the order of causes.

## Happens-before, precisely

{{< term "happens-before" "Happens-before" >}} (a → b) is defined by three rules: events on one process are ordered by program order; a send happens before its receive; and the relation is transitive. If neither a → b nor b → a, the events are **concurrent**. My ground truth is computed from the recorded log alone, by closing those edges, without looking at any clock.

## Lamport clocks

A {{< term "lamport-clock" "Lamport clock" >}} is one integer per process: increment on every event, and on receive take the max of own and message value, plus one. In the simulator:

```go
lam[p]++                              // local or send
lam[p] = max(lam[p], m.lam) + 1       // receive
```

A real trace (seed 2, 10 events; `from` is the send an `R` received):

```
id proc kind  lamport  vector   from
 0  P0   L       1    [1 0 0]  -1
 1  P1   S       1    [0 1 0]  -1
 2  P1   S       2    [0 2 0]  -1
 3  P1   L       3    [0 3 0]  -1
 4  P1   S       4    [0 4 0]  -1
 5  P2   R       5    [0 4 1]  4
 6  P0   L       2    [2 0 0]  -1
 7  P0   R       3    [3 1 0]  1
 8  P0   R       4    [4 2 0]  2
 9  P0   L       5    [5 2 0]  -1
```

Over 5000 random runs (2,760,000 ordered pairs of events), the results:

```
happens-before pairs: 685631, concurrent pairs: 1388738
lamport: a->b but L(a)>=L(b): 0
lamport: concurrent but L(a)<L(b): 608758, L equal: 171222
```

So a → b implies L(a) < L(b), with zero violations. The converse is false: 608,758 concurrent pairs still have L(a) < L(b). In the trace, events 0 and 2 are concurrent, yet L is 1 and 2. A Lamport timestamp cannot detect concurrency. Breaking ties with the process id (compare `(L, pid)`) gives a **total** order consistent with causality, useful for things like a lock queue, but it invents an order between concurrent events.

## Vector clocks

A {{< term "vector-clock" "vector clock" >}} keeps one counter per process. Increment your own slot on every event; on receive take the element-wise max, then increment your slot. Comparing two vectors:

```go
case less && greater: return Concurrent
case less:            return Before
case greater:         return After
```

(`less` means some slot is smaller, `greater` some slot is larger.) In the trace, event 0 `[1 0 0]` vs event 2 `[0 2 0]`: concurrent. I asserted, for all 2,760,000 pairs, that `Compare` equals the ground truth exactly: **0 mismatches**. The cost is a vector of N counters per message. Dotted version vectors and interval tree clocks reduce that growth; I only name them and did not implement them.

## Detecting conflicting writes

Two replicas of one key, 10 random steps (put on a replica, or one replica pulls from the other), compared in the same 1000 seeded workloads (998 had a write). Each put carries a vector and a pulled value drops only versions it dominates; that is a {{< term "version-vector" "version vector" >}} per value. {{< term "last-write-wins" "Last write wins" >}} keeps the biggest wall timestamp (replica 1's clock is 5 ticks behind, again invented). One run:

```
write a v=[1 0] wall=4
write b v=[2 0] wall=5
write c v=[2 1] wall=2
write d v=[3 0] wall=8
version vectors keep: d[3 0] c[2 1]
last-write-wins keeps: d
```

c and d are concurrent. Over the workloads:

```
with a conflict 499, writes LWW dropped silently 499,
LWW winner was not a latest write 92, version vectors lost 0
```

Version vectors never lost a write (a test asserts it); they hand the application both siblings to merge. LWW silently dropped 499 writes, and in 92 runs its winner was a write that a later write had already superseded.

## Hybrid logical clocks

{{< term "hybrid-logical-clock" "Hybrid logical clocks" >}} combine a physical time with a logical counter, so timestamps stay near real time yet respect causality. I did not run one; from what I know of the published design, that is the compromise some databases use.

## A few things to watch

- Lamport order is consistent with causality, not equal to it.
- Vector size grows with participants; in a store with many clients, tracking per replica is usual.
- Detecting a conflict does not resolve it; someone has to merge.
- In my experience wall-clock LWW is fine for caches and wrong for anything you cannot lose.

## Exercise

Add a fourth process and check that the zero-mismatch result still holds. Then make `Put` stop merging siblings and see how many siblings pile up.

## What's next

The next post is “Timeouts, retries and backoff with jitter”.
