+++
date = '2027-05-11T10:00:00+03:30'
draft = false
title = 'Replication and quorums'
description = 'Replication and quorums in Go simulations: lost acknowledged writes, the R+W>N rule, read repair, Merkle trees, LWW losses and a non-linearizable read.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "replication", "quorum", "consistency", "go"]
cover = { image = "/images/covers/ds-replication-quorum.png", alt = "Replication and quorums", hiddenInSingle = true }
+++

A client saves an order. The database leader answers "OK", and a moment later the leader's machine dies. A follower is promoted to take over, and the order is not there. The client was told it was saved, and it was not.

Keeping several copies of the data, which is called {{< term "replication" "replication" >}}, is the usual defence against a dead machine. But the story above shows that copies alone are not enough. You also have to decide **when a write counts as done**: when the leader has it, when one copy has it, or when all of them have it. That choice decides which failures you survive and how much a write costs.

This post is about that choice, in two settings. First, a database with one leader and followers. Second, a "leaderless" design where any copy accepts writes and a read asks several copies. Along the way we will meet the rule that makes the second design work, R + W > N, and the repair tools that keep copies from drifting apart. [The previous post](/posts/ds-circuit-breaker-bulkhead/) was about protecting yourself from one sick dependency; here we keep several copies so that one sick machine is not the end. For the database side of the same topic, see [replication with two real instances](/posts/db-replication-streaming/).

> Everything here is a Go **simulation** on one machine, not a real cluster. Loss and delay are seeded random numbers, so every run gives the same output, and I show counts, not timings. I re-ran the demo with Go 1.27 (the original run used Go 1.26) and every number below is what it printed.

## One leader: when is a write "done"?

The setup is simple. One **leader** takes the writes and sends each one to two **followers**. If the leader dies, one of the followers is promoted to leader. The only question is when the leader says "OK" to the client. There are three common answers:

- **Asynchronous.** Reply at once, copy to the followers in the background. Fast, but the reply is a promise the followers have not yet helped to keep.
- **Semi-synchronous.** Reply when at least one follower has the write.
- **Synchronous.** Reply when both followers have the write.

Here is one write to make it concrete. The leader gets write number 7 at tick 14. The copy reaches follower 1 at tick 16 and follower 2 at tick 19. If the leader replies at tick 14, and crashes at tick 15, no follower will ever have write 7, yet the client was told "OK". If it replies at tick 16 (after follower 1 has it) and crashes at tick 17, write 7 survives, but only on follower 1. So even then it matters which follower is promoted.

The simulation does exactly this, many times. Each run has 20 writes, one every 2 ticks. Each follower receives each write after a random delay of 1 to 6 ticks, in order. The leader crashes at a random tick between 10 and 40. After the crash one follower is promoted, and I count the writes that were acknowledged to a client but are missing on the promoted follower. I ran 1000 seeded runs per policy:

```
  async                                            acked=13170 lost-acked=1505 runs-with-loss= 932  acked/20 with a follower down=20
  semi-sync (1 of 2), promote most advanced        acked=11665 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=20
  semi-sync (1 of 2), promote follower 0 blindly   acked=11665 lost-acked= 417 runs-with-loss= 323  acked/20 with a follower down=20
  sync (2 of 2)                                    acked=10840 lost-acked=   0 runs-with-loss=   0  acked/20 with a follower down=0
```

How to read a row: `acked` is how many writes were acknowledged before the crash, summed over the 1000 runs. `lost-acked` is how many of those acknowledged writes the promoted follower did not have. `runs-with-loss` is in how many of the 1000 runs at least one acknowledged write was lost.

- **Async** acknowledged the most writes (13170, because it never waits), and lost 1505 of them, in 932 of the 1000 runs. In this simulation, losing an acknowledged write when the leader dies is the normal outcome, not a rare one.
- **Sync** lost nothing, but it acknowledged fewer writes by the crash (10840), because each one had to wait for the slower follower.
- **Semi-sync** sits between them, and the result depends on one more decision. If we promote the follower with the longest log (the "most advanced"), nothing is lost: every acknowledged write is on at least one follower, and that follower is the one we pick. If we promote follower 0 without looking, 417 acknowledged writes are lost, because the write might have reached only follower 1.

The last column is not a measurement. It comes from the definition of each policy: if one follower is down, sync can never get two acknowledgements, so it acknowledges nothing, while async and semi-sync carry on. This is the same effect I saw with a real Postgres in the replication post, where a dead synchronous standby stopped all writes.

So the lesson is two things, not one. Wait for at least one follower before you say "OK", **and** on failover choose the follower that has the most log. According to the Postgres docs, `synchronous_standby_names = 'ANY 1 (a, b)'` expresses "wait for any one of these"; I did not run that setting here.

## Without a leader: R + W > N

Now take away the leader. In a Dynamo-style design any copy can accept a write, and a client sends it to all of them. A client can then read from several copies and keep the newest version it sees. Three numbers describe the setup:

- **N**: how many copies of each key exist.
- **W**: how many copies must acknowledge a write before it counts as successful.
- **R**: how many copies must answer a read before it returns.

Let me show why the numbers matter with N = 3, with copies A, B and C, before giving the rule. All three hold version 1 of a key. A client writes version 2 with W = 2. The write reaches A and B, and both acknowledge. C is unreachable at that moment and still has version 1. The write counts as successful.

Now a reader asks two copies (R = 2). There are only three pairs it can get:

```
ask A and B:  versions 2 and 2  ->  newest is 2
ask A and C:  versions 2 and 1  ->  newest is 2
ask B and C:  versions 2 and 1  ->  newest is 2
```

Every pair of two copies contains A or B, so the reader always sees version 2. Now try R = 1. If the reader asks only C, it gets version 1: a stale read of a write that had succeeded.

The reason is counting. The set of copies that took the write has 2 members, the set the reader asks has 2 members, and there are only 3 copies, so the two sets cannot avoid sharing at least one. In general, if **R + W > N**, any set of R copies and any set of W copies share at least one copy, and that copy has the newest acknowledged version. A group of replicas whose overlap guarantees this is called a {{< term "quorum" "quorum" >}}. With N = 3, W = 2 and R = 2 gives 4 > 3. W = 1 and R = 1 gives 2, which is not more than 3, so stale reads are possible.

The simulation runs 20000 rounds per setting with N = 3. Each round writes a new version of one of 8 keys and then reads it. Every message can be lost with probability 20%, in each direction (so a request/reply pair succeeds only 64% of the time). Here are the four settings:

```
  R=1 W=1 R+W>N=false failed-writes=  941 failed-reads=  946 stale= 3368 read-uncommitted=  404
  R=1 W=3 R+W>N=true  failed-writes=14733 failed-reads=  946 stale=    0 read-uncommitted=12822
  R=3 W=1 R+W>N=true  failed-writes=  955 failed-reads=14685 stale=    0 read-uncommitted=  212
  R=2 W=2 R+W>N=true  failed-writes= 5897 failed-reads= 5884 stale=    0 read-uncommitted= 3763
```

The columns, per 20000 rounds:

- `failed-writes` and `failed-reads` count operations that could not collect enough answers (fewer than W acknowledgements, or fewer than R replies).
- `stale` counts reads that returned something older than the newest acknowledged write.
- `read-uncommitted` counts reads that returned a value from a write the client had been told failed. I will explain this one below.

What the rows show:

- **R=1, W=1** is fast and rarely fails (about 5% of operations), but it returned a stale value 3368 times, about one read in six. Here R + W is not greater than N.
- **Every row with R + W > N has `stale=0`.** That is the rule working.
- The three rows differ in where they put the cost. **W=3** needs all three copies to acknowledge, so most writes fail (14733 of 20000). **R=3** is the mirror image: most reads fail (14685). **R=2, W=2** splits the pain, with roughly 29% failures on each side.

Now the odd column. A write that reached fewer than W copies is reported to the client as failed. But its value was already stored on the copies it did reach, and nothing removes it. A later read can return it. So "failed" does not mean "did not happen". It means "unknown". That is why `read-uncommitted` is not zero even when the quorum rule holds. If you build on quorum writes, a failed write may still show up later, so retries need {{< term "idempotency" "idempotent" >}} writes.

## Keeping copies in sync: repair

Quorums are not enough to keep copies equal. A copy that missed a write stays behind until something fixes it. Real stores use a few repair mechanisms; the demo implements the first two.

**{{< term "read-repair" "Read repair" >}}.** When a read finds that one of the copies it asked is behind, it writes the newest version back to it. The idea: the reader already knows the answer, so it might as well fix it. In the demo, I counted (copy, key) pairs behind the newest version after 3000 operations on 256 keys: 146 without read repair and 111 with it. It helps, but only for keys somebody reads. A key nobody reads stays wrong.

**{{< term "anti-entropy" "Anti-entropy" >}}.** A background process compares copies and fixes differences whether or not anybody reads the data. Comparing every key one by one is expensive, so a {{< term "merkle-tree" "Merkle tree" >}} is used. Here is the idea with four keys, k0 to k3, where `h()` is a hash:

```
              root = h(left, right)
             /                      \
     left = h(k0, k1)        right = h(k2, k3)
```

Two copies compare their roots. If the roots are equal, all the data is equal, and we are done after one comparison. If they differ, compare the two children, and go down only into the side that differs. At the bottom we find exactly the keys that differ. The demo does this for 1024 keys:

```
  differing keys=0  found=[]  hash comparisons=1 (full scan: 1024)
  differing keys=1  found=[17]  hash comparisons=21 (full scan: 1024)
  differing keys=3  found=[17 18 900]  hash comparisons=41 (full scan: 1024)
```

With no difference, one comparison is enough. With one differing key, 21 comparisons find it: the root, then two children on each of the 10 levels below it (1 + 2 × 10), instead of looking at 1024 keys. With three, 41. What this counts is the comparisons between the two trees. Building each tree still has to hash all the data once; the demo builds both from scratch each time, and I did not measure the cost of keeping trees up to date.

**{{< term "hinted-handoff" "Hinted handoff" >}}.** I only describe this one, I did not implement it. When a copy is down, another node accepts its writes and keeps them with a "hint" saying whom they belong to, and hands them over when the copy returns. It improves availability, but those writes did not go to the copies the quorum rule counts on, so the overlap guarantee above no longer holds. This is called a sloppy quorum.

## Conflicts: last-write-wins and version vectors

Leaderless writes bring a new problem: two clients can update the same key at the same time through different copies. When the copies compare notes, they have two different values. Which one is right?

The simplest rule is {{< term "last-write-wins" "last-write-wins" >}} (LWW): every write carries a timestamp, and the higher one wins. A concrete failure: writer 1 saves "blue" at its clock time 100. Writer 2 saves "green" really two ticks later, but its clock runs 3 ticks behind and stamps it 99. LWW keeps "blue" and silently drops the write that came later. This is what happens with [clock skew](/posts/ds-why-distributed-is-hard/), and LWW trusts the clocks completely.

The alternative is a {{< term "version-vector" "version vector" >}}, built on the ideas from [logical clocks](/posts/ds-logical-clocks/). Each value carries a small table of "how many writes from each copy it has seen". For example `{A:1}` is a value written on A, and `{A:1, B:1}` is a value written on B after it saw A's write. The second contains the first, so the second is clearly newer. But `{A:1}` and `{B:1}` each contain something the other does not: neither is newer, they are concurrent, and the store knows it has a real conflict to hand back.

The demo runs 2000 trials, half with two truly concurrent writes and half where the second writer had read the first one. Clocks are skewed by up to 5 ticks in either direction, and the second writer really is 1 to 3 ticks later:

```
  concurrent trials=1000: LWW silently lost a write in 1000; version vectors flagged 1000 as concurrent
  causal trials=1000: LWW lost the NEWER write (clock skew) in 355; version vectors false conflicts=0
```

The first line is not a surprise: with two concurrent writes LWW has to keep one of them, so one is lost every time. The demo counts it by definition. What matters is that the version vectors noticed all 1000 conflicts, so the application had a chance to merge. The second line is the more interesting one. When the second write really came after the first, so there was nothing to argue about, LWW still kept the older one in 355 of 1000 trials, because the clock error was larger than the real gap. The version vectors reported no false conflict. The price of a version vector is that the application must decide what to do with the "siblings" it gets back.

## Availability: what a quorum costs

Waiting for more copies makes a write safer, but also makes it more likely to fail. Suppose each of the 3 copies is up 99% of the time, independently. A write with W = 2 needs at least 2 copies up. The probability is "all three up" plus "exactly one of the three down":

```
0.99³  +  3 × 0.99² × 0.01  =  0.970299 + 0.029403  =  0.999702
```

So W = 2 is unavailable 0.000298 of the time. W = 3 needs all three up: 0.99³ = 0.970299, so it is unavailable 0.029701 of the time. That is about 100 times worse (0.029701 / 0.000298 ≈ 100). The demo checks this formula in a test, and a seeded Monte Carlo of 10^6 trials gave 320 failures for W = 2 (expected 298) and 29537 for W = 3 (expected 29701). For W = 1 the formula gives 0.000001, and the Monte Carlo got 0 failures out of 10^6 against an expected 1.

All of this assumes the copies fail independently. In my experience that is the optimistic part: machines in the same rack or the same deployment tend to fail together.

## A quorum is not linearizable

One more trap. With R + W > N, a read after a **completed** write always sees it. But what about a write that is still in progress? Take N = 3, R = 2, W = 2 and a write of version 1 that has so far reached only copy A and has not returned to its client:

1. Reader 1 asks A and B. A has version 1, so it returns 1.
2. Reader 2 starts after reader 1 has returned. It asks B and C. Neither has version 1, so it returns 0.

The value went from 1 back to 0 while nobody wrote anything. That is not allowed by {{< term "linearizability" "linearizability" >}} (the "one copy" illusion from [consistency models](/posts/ds-consistency-models/)), and the checker from that post agrees:

```
  writeBack=false reader1 saw 1, reader2 (started later) saw 0, linearizable=false
  writeBack=true  reader1 saw 1, reader2 (started later) saw 1, linearizable=true
```

The second line shows a fix: if reader 1 first writes what it saw back to the copies it asked (A and B), then reader 2 asking B and C will find version 1 on B. In this one scripted case the history becomes linearizable. It is one hand-made interleaving, not a proof. I believe this write-back idea is the heart of the classic ABD algorithm for a replicated register (Attiya, Bar-Noy and Dolev), but I did not test it here. What I am sure of is that operations beyond single reads and writes, such as compare-and-set or choosing a leader, need a full {{< term "consensus" "consensus" >}} protocol. A real example is a JetStream stream with `Replicas: 3`, which is a small Raft group ([JetStream in production](/posts/nats-jetstream-production/)). Raft gets its own post later in this series.

## Where quorums surprise you

- **A "failed" quorum write may still become visible.** It stayed on the copies it reached. Treat failure as "unknown", and make writes safe to retry.
- **LWW is only fine when losing a write is fine.** A page-view counter or a "last seen" time can tolerate it; a bank balance cannot. And clock skew can make it drop the newer write.
- **Failover must choose the most advanced follower.** In the table, promoting follower 0 blindly lost 417 acknowledged writes under semi-sync, while promoting the longest log lost none.
- **R + W > N is not a guarantee against everything.** It gives you "see the newest acknowledged write", not linearizability, and sloppy quorums break even that.

## Exercise

Change the demo to N = 4 and run W = 3, R = 2. Check by hand first whether R + W > N, then rerun the table. Does anything change under message loss? (The cluster size is fixed at 3 in the code, so you will have to make it a parameter.)

## What's next

Next is "Sharding and consistent hashing". Replication puts the same data on several machines. When the data no longer fits on one machine, you have to split it, and that is a different problem.
