+++
date = '2027-04-25T10:00:00+03:30'
draft = false
title = 'Consistency models'
description = 'Consistency models explained with a Go history checker: linearizable, sequential, read-your-writes and monotonic reads, tested on 1000 simulated histories.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consistency", "linearizability", "go", "replication"]
cover = { image = "/images/covers/ds-consistency-models.png", alt = "Consistency models", hiddenInSingle = true }
+++

"Consistent" is the word I have misused most in design reviews. The previous post, [CAP and PACELC, correctly](/posts/ds-cap-pacelc/), argued that the C in CAP means one specific thing. This post is about the whole ladder of promises a store can make, and about how to **check** a promise instead of arguing about it. It builds on [why distributed systems are hard](/posts/ds-why-distributed-is-hard/) and on [replication lag in Postgres](/posts/db-replication-streaming/).

> Honest labelling: everything here is Go 1.26 code in one process. The leader and followers are a **simulation** with seeded randomness and discrete ticks, not a network. Numbers are counts of histories, never timings. The checker itself is real and tested with `go test -race`.

## A history and a register

A history lists operations on one register (initial value 0): client, read or write, value, invoke and return time. Write values increase in the order the leader applied them, so a bigger value is a newer version.

The {{< term "linearizability" "linearizability" >}} check is a brute-force search in the style of Wing and Gong: pick an operation that no remaining operation finished before it started, apply it to the register (a read must return the current value), recurse. It is exponential, fine for about ten operations. The {{< term "sequential-consistency" "sequential consistency" >}} check searches for any order that keeps each client's own order and ignores real time. {{< term "read-your-writes" "Read-your-writes" >}} and {{< term "monotonic-reads" "monotonic reads" >}} are simple per-client scans.

## Six named histories

Time flows right; `[` and `]` are invoke and return.

```
B  C1 W1 [------]
   C2   W2 [------]
   C3              R=1 [-]
   C4                      R=2 [-]

C  C1 W1 [--]
   C2          R=0 [-]          (starts after W1 returned)

E  C1 W1 [-]
   C3      W2 [-]
   C2            R=2 [-]  R=1 [-]
```

Verdicts from my checker (the tests assert exactly this table):

```
history                                linearizable sequential   RYW   MR
A concurrent writes, reads agree       yes          yes          yes   yes
B concurrent writes, reads disagree    NO           yes          yes   yes
C stale read after write returned      NO           yes          yes   yes
D own write not visible                NO           NO           NO    yes
E value goes backwards                 NO           yes          yes   NO
F plain write then read                yes          yes          yes   yes
```

B: both writes finished before the reads, so two readers cannot disagree on the last one; yet W1, R1, W2, R2 is a legal order if real time is ignored. C is the classic stale read. D breaks even sequential consistency, since one client contradicts itself. E is legal sequentially (C2's reads sit between the writes) but its reads go backwards.

## The strength ladder

| Model | One line |
|---|---|
| Linearizable | acts like one copy, respecting real time |
| Sequential | one global order, per-client order kept, real time ignored |
| {{< term "causal-consistency" "Causal" >}} | cause is seen before effect, unrelated writes may differ |
| {{< term "eventual-consistency" "Eventual" >}} | replicas converge if writes stop |

Read-your-writes and monotonic reads are session guarantees beside the ladder. Causal needs a way to track "happened before", which the next post (see the end) builds. I did not implement a causal checker.

## A leader and a lagging follower

The simulation: one leader, two followers. A write reaches the leader, which ships it to each follower with a random lag of 1 to 5 ticks, applied in order. Three clients do three operations each (40% writes), reads go to a random follower, and the same 1000 seeded workloads run in each mode:

```
mode               not-linear      not-seq    RYW     MR   (violations out of 1000)
follower reads            388          148    221      3
own-write token           276            5      0      6
session token             271            0      0      0
```

Plain follower reads break everything. The first fix is a session token: the client remembers the version it last wrote, and a follower that has applied less than that is skipped, so the read goes to the leader. Read-your-writes drops from 221 to 0. Monotonic reads (3 to 6) and sequential violations (5) do not fully go away, because the token ignores what the client **read**. Letting the token be the highest version seen, read or written, brings all three to 0.

But 271 histories are still not linearizable. Session guarantees say nothing about **other** clients' writes, and follower reads can be stale for them. Reading only from the leader fixes that in this model, at the cost of leader load; a real leader can also be partitioned away.

## What real systems use

I did not run them, but real checkers exist: Jepsen with Knossos, and Porcupine in Go, which record histories of real databases under faults. They solve my toy's problem at a scale where brute force fails. In my experience the best habit is to ask of every read path which of these properties it promises and what happens when it hits a replica. JetStream's replicated streams are in [JetStream in production](/posts/nats-jetstream-production/).

## A few things to watch

- Eventual consistency says nothing about how stale; measure lag.
- A session token needs a fallback (leader) when no replica is fresh enough.
- A checker only proves something about the histories you recorded.
- "Strongly consistent" in docs may mean linearizable or something weaker; ask which.

## Exercise

Add a third property to the checker: "writes follow reads" (a write after a read is ordered after the version read). Then change the lag range in `makePlans` and see which counts move.

## What's next

The next post is “Logical clocks: Lamport and vector clocks”.
