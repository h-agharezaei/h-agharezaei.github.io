+++
date = '2027-04-20T10:00:00+03:30'
draft = false
title = 'CAP and PACELC, correctly'
description = 'CAP and PACELC explained with seeded Go simulations: CP rejects, AP diverges and merges, and sync versus async replication trades latency for freshness.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cap-theorem", "pacelc", "consistency", "go"]
cover = { image = "/images/covers/ds-cap-pacelc.png", alt = "CAP and PACELC, correctly", hiddenInSingle = true }
+++

In [the previous post](/posts/ds-why-distributed-is-hard/) a timeout meant "unknown". CAP is what you get when that unknown lasts long enough that you must decide what to do about it. "Pick two of three" is the slogan everyone remembers, and in my opinion it misleads more than it teaches. State it properly first. Background: [replication](/posts/db-replication-streaming/) and [JetStream](/posts/nats-jetstream-production/).

> Honest labelling: everything below is a **simulation** in one Go 1.26 program (seeded, deterministic). Time is counted in fake "ticks", the "network" is a boolean and a delay. It is not a real network and I show no timings.

## The precise statement

The setup is two replicas, A and B, of one register. A {{< term "network-partition" "network partition" >}} cuts the link between them for ticks 30 to 69 out of 100. Clients write to A and read from B.

In the formal result (Gilbert and Lynch; I hedge on details) the letters mean:

- **C**: {{< term "linearizability" "linearizability" >}}, one up-to-date copy as seen by clients.
- **A**: every non-failing node answers every request.
- **P**: the system keeps working when the network drops messages between nodes.

A real network does partition, so P is not a choice. The honest statement is: **during a partition, you give up C or A** for the operations that cannot complete. The theorem is the {{< term "cap-theorem" "CAP theorem" >}}.

## 1. CP: refuse

Writes need both replicas ({{< term "quorum" "quorum" >}} of 2 out of 2; real systems use 3 so one can fail). Reads at B refuse when B cannot confirm it is current.

```
CP : writes=50 rejected=20 | reads=100 rejected=40 stale=0 | diverged=false final A=99 B=99
```

20 of 50 writes and 40 of 100 reads were rejected, yet nothing stale was ever returned and the replicas ended equal. Availability was the price.

## 2. AP: accept on both sides

Now both sides accept. A client also writes to B (4 extra writes during the partition). Outside the partition A replicates to B asynchronously with a 2-tick delay.

```
AP : writes accepted=49 (rejected=0, concurrent on B=4)
     stale reads at B: in partition 26/40, outside 0/60
     before heal: A=69 B=1065 | after heal with LWW: A=89 B=89
```

Nothing was rejected, but 26 of 40 reads at B were stale, and at heal the replicas disagreed (69 vs 1065). "Stale" means older than the newest acknowledged write, beyond the normal 2-tick lag. {{< term "last-write-wins" "Last write wins" >}} resolved it by stamp, silently dropping B's writes.

A shopping cart shows lost updates better. Both sides start with `tea`; A adds `book`, B adds `pen`:

```
cart LWW  : [pen tea] (book was added and acknowledged, now gone)
cart union: [book pen tea]
```

Set union is a tiny {{< term "crdt" "CRDT" >}}: merging in any order, any number of times, gives the same answer. For numbers, a G-counter keeps one slot per node, merges by per-slot maximum, and its value is the sum. Seed 42 gave +8 on A and +16 on B from 100:

```
counter: +8 on A, +16 on B, expected 124 | LWW register 116 (lost 8) | G-counter 124
```

The cost: a G-counter only counts up and a union set cannot remove; CRDTs buy convergence by restricting what you can say.

## What CAP does not say

| Common claim | What is true |
|---|---|
| "Pick any two" | P is forced; the choice is C or A, and only during a partition |
| "CA systems exist" | A single node is not distributed; a networked system cannot opt out of partitions |
| "AP means always inconsistent" | Without a partition an AP system can behave consistently |
| "CAP describes latency" | No; slow is not partitioned (see PACELC) |
| "A system is CP or AP, once" | It can differ per operation |

## PACELC: the other 99% of the time

Daniel Abadi's {{< term "pacelc" "PACELC" >}} adds the case without a partition: **if Partition, A or C; Else, Latency or Consistency.** Same two replicas, but a healthy link whose one-way delay is seeded between 2 and 4 ticks. Synchronous replication (as in {{< term "synchronous-commit" "synchronous commit" >}}) acks after the follower acks; asynchronous acks at once. 45 writes, 100 follower reads:

```
sync : writes=45 ack ticks mean=5.8 max=8 | follower reads=100 stale=0 max lag=0 writes
async: writes=45 ack ticks mean=0.0 max=0 | follower reads=100 stale=69 max lag=2 writes
```

Ticks are simulated. Sync paid about 6 ticks per write and never returned a read older than an acknowledged write. Async acked instantly, but 69 follower reads were behind the newest acknowledged write. That is the "else" tradeoff, present even when healthy.

According to my earlier post, PostgreSQL streaming replication is asynchronous by default and can be made synchronous. JetStream replicated streams are quorum-based according to its docs; I described that and did not run a cluster here.

## A few things to watch

- Say "during a partition, C or A", never "CA".
- If you accept both sides, decide the merge rule before launch.
- LWW is a way to lose data quietly.

## Exercise

Change `PartFrom`/`PartTo` and the replication delay. Which counts grow with the partition, which with delay? Then add removal to the cart and see what a union does with it.

## What's next

The next post is “Consistency models”.
