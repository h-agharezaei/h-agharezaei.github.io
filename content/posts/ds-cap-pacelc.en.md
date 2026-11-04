+++
date = '2027-04-20T10:00:00+03:30'
draft = false
title = 'CAP and PACELC, correctly'
description = 'CAP and PACELC explained with seeded Go simulations: CP rejects, AP diverges and merges, and sync versus async replication trades latency for freshness.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cap-theorem", "pacelc", "consistency", "go"]
cover = { image = "/images/covers/ds-cap-pacelc.png", alt = "CAP and PACELC, correctly", hiddenInSingle = true }
+++

Imagine two copies of the same bank balance, A and B, kept on two servers. The cable between them is cut. A customer asks B for the balance. B has a number, but it has not heard from A for a while, and A may have received a deposit in the meantime. What should B do? It can answer with the number it has, and risk giving an old value. Or it can say "I cannot tell you right now", and be useless until the cable is fixed. There is no third option that is always correct.

That small dilemma is what the CAP theorem is about. "Pick two of three" is the slogan everyone remembers, and in my opinion it misleads more than it teaches. This post says what CAP actually claims, with a small simulation of both choices, and then adds PACELC, which covers the much longer time when nothing is broken at all.

CAP starts where the "unknown" of a timeout, from [the previous post](/posts/ds-why-distributed-is-hard/), lasts long enough that you must decide what to do. Some background on how copies are kept in sync: [replication](/posts/db-replication-streaming/) and [JetStream](/posts/nats-jetstream-production/).

> Honest labelling: everything below is a **simulation** in one Go program (seeded, deterministic). I re-ran it with Go 1.27 and the output is what I saw; the original run used Go 1.26. Time is counted in fake "ticks", and the "network" is a boolean ("connected or not") and a delay. It is not a real network and I show no timings.

## The precise statement

The setup is the one from the opening: two replicas, A and B, of one register (a register is just one value that can be read and written). A {{< term "network-partition" "network partition" >}} cuts the link between them for ticks 30 to 69 out of 100. Clients write to A and read from B.

In the formal result (Gilbert and Lynch; I hedge on the details) the three letters mean:

- **C** (consistency) is {{< term "linearizability" "linearizability" >}}: every operation looks as if it happened at one instant, and a read never returns something older than a write that already finished. In practice: clients see one up-to-date copy.
- **A** (availability): every node that has not failed answers every request.
- **P** (partition tolerance): the system keeps working when the network drops messages between nodes.

A real network does partition, so P is not something you choose. The honest statement of the {{< term "cap-theorem" "CAP theorem" >}} is: **during a partition, you give up C or A** for the operations that cannot complete. In the opening example, "answer with what you have" gives up C, and "refuse" gives up A.

## 1. CP: refuse

Let me play the "refuse" side first. A client writes to A every 2 ticks, and reads from B every tick. To keep C, a write must reach both replicas before it is acknowledged (that is a {{< term "quorum" "quorum" >}} of 2 out of 2; real systems use 3 so that one can fail). A read at B must refuse when B cannot confirm it is current. Each write sets the register to the tick number plus one.

```
CP : writes=50 rejected=20 | reads=100 rejected=40 stale=0 | diverged=false final A=99 B=99
```

The partition lasts 40 ticks. In that time 20 of the 50 writes (every second tick) could not reach B, so they were rejected, and 40 of the 100 reads (every tick) were rejected because B could not confirm anything. But `stale=0`: nothing old was ever returned, and the replicas ended equal (`final A=99 B=99`). Availability was the price.

## 2. AP: accept on both sides

Now the other choice. Both replicas keep accepting requests, even when they cannot see each other. A second client also writes to B, 4 times during the partition. Outside the partition A sends each write to B in the background (asynchronously), and it arrives 2 ticks later. When the partition ends, the two replicas compare notes and keep the value with the newest timestamp. This rule is {{< term "last-write-wins" "last write wins" >}} (LWW).

```
AP : writes accepted=49 (rejected=0, concurrent on B=4)
     stale reads at B: in partition 26/40, outside 0/60
     before heal: A=69 B=1065 | after heal with LWW: A=89 B=89
```

Line by line:

- Nothing was rejected: 49 writes were accepted, 45 on A and 4 on B. The service stayed available.
- 26 of the 40 reads at B during the partition were stale. "Stale" here means older than the newest acknowledged write, beyond the normal 2-tick lag. Outside the partition there were none.
- Before the partition healed, A held 69 and B held 1065. The two replicas disagreed about the truth.
- After healing, both hold 89. LWW compared timestamps, and B's four acknowledged writes lost against A's newer stamps. They were silently dropped, and nobody was told.

A shopping cart shows lost updates more clearly. Both sides start with `tea`. During the partition, A adds `book` and B adds `pen`. The demo then merges in two ways: treating the whole cart as one LWW register (I simply decided B's stamp is the newer one), and taking the union of the two sets:

```
cart LWW  : [pen tea] (book was added and acknowledged, now gone)
cart union: [book pen tea]
```

With LWW, the customer's `book` disappears even though A had acknowledged it. Set union keeps everything. A set union is a tiny {{< term "crdt" "CRDT" >}}, a data type designed so that replicas can update independently and still converge: merging in any order, any number of times, gives the same answer.

Numbers can do the same with a **G-counter**. It keeps one slot per node, merges by taking the larger value in each slot, and its value is the sum of the slots. Here both sides start at 100 and increment during the partition. A hand trace: A holds `{init: 100, A: 8}`, B holds `{init: 100, B: 16}`, merging gives `{init: 100, A: 8, B: 16}`, and the sum is 124. The demo (seed 42) gives +8 on A and +16 on B, and compares it to a plain LWW register (where, again, I decided B has the newer stamp):

```
counter: +8 on A, +16 on B, expected 124 | LWW register 116 (lost 8) | G-counter 124
```

The LWW register keeps B's 116 and loses A's 8 increments. The G-counter gets 124, exactly the expected value. The cost: a G-counter can only count up, and a union set cannot remove an item. CRDTs buy convergence by restricting what you are allowed to say.

## What CAP does not say

The slogan hides a lot, so here are the common misreadings:

| Common claim | What is true |
|---|---|
| "Pick any two" | P is forced; the choice is C or A, and only during a partition |
| "CA systems exist" | A single node is not distributed; a networked system cannot opt out of partitions |
| "AP means always inconsistent" | Without a partition an AP system can behave consistently |
| "CAP describes latency" | No; slow is not partitioned (see PACELC) |
| "A system is CP or AP, once" | It can differ per operation |

## PACELC: the rest of the time

CAP says nothing about the time when the network is fine, and a healthy network is how most systems spend most of their time. Daniel Abadi's {{< term "pacelc" "PACELC" >}} adds that case: **if Partition, then A or C; Else, Latency or Consistency.** Even without a partition, copying data takes time, and you choose between answering fast and answering with fresh data.

The simulation uses the same two replicas but a healthy link, whose one-way delay is seeded between 2 and 4 ticks. It compares two ways of acknowledging a write:

- **Synchronous:** the leader acknowledges only after the follower has applied the write and answered (as with {{< term "synchronous-commit" "synchronous commit" >}} in PostgreSQL). The wait is the trip there plus the trip back, 4 to 8 ticks.
- **Asynchronous:** the leader acknowledges as soon as it has written locally, and sends the write to the follower in the background.

There are 45 writes, and a client reads from the follower every tick (100 reads). A read counts as stale when the follower is behind the newest acknowledged write:

```
sync : writes=45 ack ticks mean=5.8 max=8 | follower reads=100 stale=0 max lag=0 writes
async: writes=45 ack ticks mean=0.0 max=0 | follower reads=100 stale=69 max lag=2 writes
```

Sync paid about 6 ticks per write (mean 5.8, at most 8) and never returned a read older than an acknowledged write. Async acknowledged instantly, but 69 of 100 follower reads were behind the newest acknowledged write, by up to 2 writes. That is the "else" trade-off, present even when everything is healthy: latency or consistency.

According to my earlier post on replication, PostgreSQL streaming replication is asynchronous by default and can be made synchronous. JetStream replicated streams are quorum-based according to its docs; I describe that from the docs and did not run a cluster for this post.

## Mistakes to avoid with CAP

- Say "during a partition, C or A", never "CA". A system that is not partitioned has nothing to choose, and a system that can be partitioned has no third option.
- If you accept writes on both sides, decide the merge rule before launch. Deciding it after the first partition means deciding it with data already lost.
- LWW is a way to lose data quietly. It is fine for values where the newest really is the only one that matters, and wrong for a cart or a counter, as the demo shows.
- Do not read the simulation as measurements of real systems. The percentages here come from my own settings (partition length, write rate, delays), not from a real database.

## Exercise

Change `PartFrom`/`PartTo` and the replication delay. Which counts grow with the partition, which with the delay? Then add removal to the cart and see what a union does with it.

## What's next

Next, “Consistency models”: the space between linearizable and stale.
