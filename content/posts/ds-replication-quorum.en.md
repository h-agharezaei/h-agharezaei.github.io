+++
date = '2027-05-11T10:00:00+03:30'
draft = false
title = 'Replication and quorums'
description = 'Replication and quorums in Go simulations: lost acknowledged writes, the R+W>N rule, read repair, Merkle trees, LWW losses and a non-linearizable read.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "replication", "quorum", "consistency", "go"]
cover = { image = "/images/covers/ds-replication-quorum.png", alt = "Replication and quorums", hiddenInSingle = true }
+++

[The previous post](/posts/ds-circuit-breaker-bulkhead/) was about surviving a sick dependency. The other way to survive a dead machine is to keep several copies of the data, which is {{< term "replication" "replication" >}}. For the database view see [replication with two real instances](/posts/db-replication-streaming/).

> Honest labelling: everything here is a Go 1.26 simulation on one machine. Loss and delays are seeded random numbers and I show counts, not timings.

## Leader-based: when is a write acknowledged?

One leader, two followers, 20 writes, and the leader crashes at a random tick. I ran 1000 seeded runs per mode and counted writes that were acknowledged to the client but missing on the follower that took over.

```
  async                                            acked=13170 lost-acked=1505 runs-with-loss= 932  acked/20 with a follower down=20
  semi-sync (1 of 2), promote most advanced        acked=11665 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=20
  semi-sync (1 of 2), promote follower 0 blindly   acked=11665 lost-acked= 417 runs-with-loss= 323  acked/20 with a follower down=20
  sync (2 of 2)                                    acked=10840 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=0
```

Async acknowledges at once and loses acknowledged writes in 932 of 1000 runs. Waiting for both followers loses none, but with one follower down it acknowledges nothing, the same outage as one synchronous standby in the Postgres post. Semi-sync, waiting for any one follower, is the middle: no loss, but only if you promote the follower that has the most log. Promoting blindly lost 417 writes. According to the Postgres docs, `synchronous_standby_names = 'ANY 1 (a, b)'` expresses this; I did not run it here.

## Leaderless quorums: R + W > N

In a Dynamo-style design any replica takes a write. N=3. A write goes to all three and succeeds if W acknowledge; a read asks all three and uses the newest of R answers. A {{< term "quorum" "quorum" >}} of reads and writes overlaps when R+W>N. Each of 20000 rounds writes a new version of one of 8 keys, then reads it; every message leg is lost with 20% probability.

```
  R=1 W=1 R+W>N=false failed-writes=  941 failed-reads=  946 stale= 3368 read-uncommitted=  404
  R=1 W=3 R+W>N=true  failed-writes=14733 failed-reads=  946 stale=    0 read-uncommitted=12822
  R=3 W=1 R+W>N=true  failed-writes=  955 failed-reads=14685 stale=    0 read-uncommitted=  212
  R=2 W=2 R+W>N=true  failed-writes= 5897 failed-reads= 5884 stale=    0 read-uncommitted= 3763
```

Stale means older than the newest acknowledged write. It is zero whenever R+W>N, and 3368 for R=1, W=1. But look at `read-uncommitted`: a write that reached fewer than W replicas is reported as failed, yet its value stays on those replicas, and later reads return it. The client was told "failed" and the value is visible anyway.

## Repair: read repair, anti-entropy, hinted handoff

{{< term "read-repair" "Read repair" >}} writes the newest version back to responders that were behind. After 3000 operations on 256 keys, replica-key pairs behind the newest version: 146 without repair, 111 with it. It only helps keys that are read. {{< term "anti-entropy" "Anti-entropy" >}} compares replicas in the background with a {{< term "merkle-tree" "Merkle tree" >}}: equal roots mean equal data, and you descend only into subtrees that differ.

```
  differing keys=0  found=[]  hash comparisons=1 (full scan: 1024)
  differing keys=1  found=[17]  hash comparisons=21 (full scan: 1024)
  differing keys=3  found=[17 18 900]  hash comparisons=41 (full scan: 1024)
```

{{< term "hinted-handoff" "Hinted handoff" >}} I only describe, I did not implement it: while a replica is down, another node keeps its writes and delivers them later. That is a sloppy quorum, so the overlap above no longer holds.

## Conflicts: LWW versus version vectors

Two writers update the same key through different replicas, 2000 trials, half truly concurrent, half where the second writer had read the first. Clocks are skewed by up to 5 ticks.

```
  concurrent trials=1000: LWW silently lost a write in 1000; version vectors flagged 1000 as concurrent
  causal trials=1000: LWW lost the NEWER write (clock skew) in 355; version vectors false conflicts=0
```

{{< term "last-write-wins" "Last-write-wins" >}} keeps one of two concurrent writes, so losing one is by construction. Worse, with skewed clocks it dropped the newer write in 355 causal cases. A {{< term "version-vector" "version vector" >}} (see [logical clocks](/posts/ds-logical-clocks/)) flagged every concurrent pair and no ordered one, but the application must then merge the siblings.

## Availability

With p=0.99 per replica, a quorum of W needs at least W replicas up. Exactly, W=2 gives 0.999702 (unavailable 0.000298) and W=3 gives 0.970299 (0.029701), computed with the binomial formula and checked against the closed form in a test. A seeded Monte Carlo of 10^6 trials gave 320 and 29537 failures against 298 and 29701 expected. Requiring all replicas makes unavailability about 100 times larger. This assumes independent failures, which in my experience is the optimistic part.

## Quorums are not linearizable

Scripted interleaving, N=3, R=2, W=2: write 1 has reached only replica A and has not returned. Reader 1 asks A and B and gets 1. Reader 2 starts after that and asks B and C, getting 0. With the checker idea from the [consistency models](/posts/ds-consistency-models/) post:

```
  writeBack=false reader1 saw 1, reader2 (started later) saw 0, linearizable=false
  writeBack=true  reader1 saw 1, reader2 (started later) saw 1, linearizable=true
```

If readers write back what they saw before returning, the history passes, though that is one scripted case. {{< term "linearizability" "Linearizability" >}} in general needs consensus; Raft and Paxos get their own posts later in the series. Real systems use it: see replicas `R3` in [JetStream in production](/posts/nats-jetstream-production/).

## A few things to watch

- A "failed" quorum write may still be visible.
- LWW is acceptable only when losing a write is acceptable.
- Failover must pick the most advanced follower.

## Exercise

Add a fourth replica with N=4, W=3, R=2 and rerun the table. Does anything change under loss?

## What's next

The next post is “Sharding and consistent hashing”.
