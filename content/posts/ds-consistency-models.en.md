+++
date = '2027-04-25T10:00:00+03:30'
draft = false
title = 'Consistency models'
description = 'Consistency models explained with a Go history checker: linearizable, sequential, read-your-writes and monotonic reads, tested on 1000 simulated histories.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consistency", "linearizability", "go", "replication"]
cover = { image = "/images/covers/ds-consistency-models.png", alt = "Consistency models", hiddenInSingle = true }
+++

You change your profile photo, the page says "saved", and you refresh. The old photo is still there. A minute later the new one appears. Was that a bug? It depends on what the system promised. If it promised "after a save you will see your own change", then yes. If it only promised "all copies will agree eventually", then no, it did exactly what it said.

"Consistent" is the word I have misused most in design reviews, because it names a whole ladder of different promises. The previous post, [CAP and PACELC, correctly](/posts/ds-cap-pacelc/), argued that the C in CAP means one specific thing, the strongest rung. This post covers the other rungs. The core idea is simple: **a consistency model is a statement about what a reader is allowed to observe.** The stronger the model, the fewer surprising things a reader can see, and the more the store pays for it in coordination.

The second goal is more practical: how to **check** a promise on recorded data instead of arguing about it in a meeting. For that we need a way to write down what happened, so we start there. Background: [why distributed systems are hard](/posts/ds-why-distributed-is-hard/) and [replication lag in Postgres](/posts/db-replication-streaming/).

> Honest labelling: everything here is Go code in one process, re-run with Go 1.27 (the original run used Go 1.26). The leader and followers are a **simulation** with seeded randomness and discrete ticks, not a network. Numbers are counts of histories, never timings. The checker itself is real and tested with `go test -race`.

## A history and a register

To talk about what readers observe, we record a **history**: the list of operations that clients performed on one **register** (one value that can be read and written, with initial value 0). For each operation we note the client, whether it was a read or a write, the value, and two times: when the call was **invoked** and when it **returned**.

Here is the smallest interesting history. Client 1 writes 1, and the write returns. After that, client 2 reads and gets 0. Everyone would call this a stale read, and the history is how we can say so precisely: the read started after the write had already finished, yet it did not see it.

One detail makes the checking easier: write values are unique and increase in the order the leader applied them. So a bigger value always means a newer version, and "this read is older than that one" is a simple comparison.

A checker takes a history and answers yes or no for one model. The demo has four checks:

- **{{< term "linearizability" "Linearizability" >}}** is the strongest: the whole history must look as if every operation took effect at a single instant somewhere between its invoke and return, on one copy of the data. The check is a brute-force search in the style of Wing and Gong. It repeatedly picks an operation that no remaining operation finished before it started, applies it to the register (a read must return the current value), and recurses. If it can order all operations this way, the history is linearizable. The search is exponential, so it only works for small histories, about ten operations here.
- **{{< term "sequential-consistency" "Sequential consistency" >}}** is weaker: some single order of all operations must exist that keeps each client's own order, but real time between different clients is ignored. The checker searches for any such order.
- **{{< term "read-your-writes" "Read-your-writes" >}}**: after a client wrote a value, its own later reads must return that value or a newer one.
- **{{< term "monotonic-reads" "Monotonic reads" >}}**: a client's reads never go back to an older value.

The last two are simple scans over each client's operations.

## Six named histories

I made six small histories by hand, to see where the checks agree and where they differ. Time flows to the right, and each four characters are one tick. `[` and `]` are invoke and return. `W1` means "wrote 1" and `R2` means "read and got 2". All six are drawn here from the demo's own data:

```
A  C1 [W1-------------]
   C2     [W2-------------]
   C3                         [R2-]
   C4                                 [R2-]

B  C1 [W1-------------]
   C2     [W2-------------]
   C3                         [R1-]
   C4                                 [R2-]

C  C1 [W1-----]
   C2             [R0-]

D  C1 [W1-----]   [R0-]

E  C1 [W1-]
   C2                 [R2-]   [R1-]
   C3         [W2-]

F  C1 [W1-----]
   C2             [R1-]
```

Here are the verdicts from my checker (the tests assert exactly this table):

```
history                                linearizable sequential   RYW   MR
A concurrent writes, reads agree       yes          yes          yes   yes
B concurrent writes, reads disagree    NO           yes          yes   yes
C stale read after write returned      NO           yes          yes   yes
D own write not visible                NO           NO           NO    yes
E value goes backwards                 NO           yes          yes   NO
F plain write then read                yes          yes          yes   yes
```

Reading the table one history at a time:

- **A.** The two writes overlap in time, so either may be first. Both readers see 2, which fits the order W1, W2. Nothing wrong.
- **B.** The same two writes, but now one reader sees 1 and a later one sees 2. Both writes had already returned before either read began, so after that moment the register holds one value and cannot change. Two readers cannot disagree about it, so this is not linearizable. But sequential consistency ignores real time: the order W1, R1, W2, R2 is a legal story, so it passes.
- **C.** The classic stale read: the write returned, then a read began and got the old value. Not linearizable. Sequentially it is fine: put the read before the write.
- **D.** Client 1 writes 1 and then reads 0 itself. Even ignoring real time, a client's own operations must stay in order, so no legal story exists. This one breaks everything except monotonic reads (which never saw an older value because it only read once).
- **E.** W1 finishes before W2 begins, so in real time the order is forced. Client 2 reads 2 and then 1: it went back in time. Not linearizable and it fails monotonic reads. Sequentially it passes: order W2, R2, W1, R1 is legal because the two writers are different clients.
- **F.** A write, then a read that sees it. Everything passes.

## The strength ladder

Putting the models in a row, from strongest to weakest:

| Model | One line |
|---|---|
| Linearizable | acts like one copy, respecting real time |
| Sequential | one global order, per-client order kept, real time ignored |
| {{< term "causal-consistency" "Causal" >}} | cause is seen before effect, unrelated writes may differ |
| {{< term "eventual-consistency" "Eventual" >}} | replicas converge if writes stop |

Read-your-writes and monotonic reads are session guarantees: they sit beside the ladder, because they are about one client's view, not about all clients. Causal consistency needs a way to say "this event could have influenced that one" ("happened before"), which is the subject of the next post. I did not implement a causal checker.

## A leader and a lagging follower

Now let me see where real violations come from. The simulation has one leader and two followers. A client request sent at tick `t` reaches its server at `t+1`, and the reply returns at `t+2`, so every operation occupies two ticks. A write goes to the leader, which gives it the next version number and ships it to each follower with a random lag of 1 to 5 ticks. Followers apply writes in order. A read goes to a random follower and returns the highest version that follower has applied so far.

Three clients do three operations each, about 40% of them writes. The same 1000 seeded workloads run in each of three modes, and every history is checked:

- **follower reads**: no protection, just read from a follower.
- **own-write token**: the client remembers the version of its last write. If the chosen follower has applied less than that, the read goes to the leader instead.
- **session token**: the same, but the token also rises to the highest version the client has seen in a read.

```
mode               not-linear      not-seq    RYW     MR   (violations out of 1000)
follower reads            388          148    221      3
own-write token           276            5      0      6
session token             271            0      0      0
```

Each number is how many of the 1000 histories violated that model. In the first row, plain follower reads break everything: 388 histories are not linearizable and 221 violate read-your-writes.

To see how one of those 221 happens, here is the first violating history (seed 2), drawn like the ones above. Client 2 writes (version 1) and then reads 0 from a follower that has not received it yet. The second drawing is the same workload with the session token, where that read goes to the leader and returns 2, the newest version:

```
follower reads (seed 2)
C0         [R0-----]           [W2-----]           [R2-----]
C1             [R0-----]           [W3-----]               [R3-----]
C2 [R0-----]       [W1-----]   [R0-----]

session token (same workload)
C0         [R0-----]           [W2-----]           [R2-----]
C1             [R0-----]           [W3-----]               [R3-----]
C2 [R0-----]       [W1-----]   [R2-----]
```

(I printed these two with a throwaway addition to the demo in a scratch copy. The demo's own output only shows the table.)

Back to the table. The first fix is the own-write token, and it works as designed: read-your-writes drops from 221 to 0, and sequential violations from 148 to 5. But two numbers do not drop to zero. Monotonic reads goes from 3 up to 6, and the reason is a nice detail. When a follower is behind the token, the read goes to the leader and sees the newest version. The client's next read may land on a follower that is past the token but still behind the leader, so it returns something older: the client has gone backwards. The token only remembers what the client **wrote**, not what it **read**. The session token fixes exactly that: it takes the highest version seen, read or written, and all three numbers go to 0.

But 271 histories are still not linearizable. Session guarantees say nothing about **other** clients' writes, and follower reads can be stale for them. I did not run a leader-only mode, but in this model it would fix that by construction, at the cost of putting all the read load on one node; a real leader can also be partitioned away, which is the CAP trade-off again.

## What real systems use

I did not run these, but real checkers exist: Jepsen with Knossos, and Porcupine in Go, which record histories of real databases under faults and check them. They solve the same problem as my toy, at a scale where brute force fails. In my experience the best habit is to ask of every read path which of these properties it promises and what happens when it hits a replica. JetStream's replicated streams are in [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/).

## Where consistency claims mislead

- "Eventually consistent" says nothing about how stale a read can be, or for how long. Measure the lag instead of trusting the word.
- A session token needs a fallback (here, the leader) for when no replica is fresh enough, and that fallback is a cost: it moves load to one node.
- A checker only proves something about the histories you recorded. A passing run is not a proof about all runs, and the simulation here has only nine operations per history.
- "Strongly consistent" in a database's docs may mean linearizable or something weaker. Ask which, and ask what happens during a partition.

## Exercise

Add a third property to the checker: "writes follow reads" (a write after a read is ordered after the version read). Then change the lag range in `makePlans` and see which counts move.

## What's next

Next, “Logical clocks: Lamport and vector clocks”: the "happened before" tracking that causal consistency needs.
