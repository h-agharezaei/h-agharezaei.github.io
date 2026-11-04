+++
date = '2027-04-29T10:00:00+03:30'
draft = false
title = 'Logical clocks: Lamport and vector clocks'
description = 'Logical clocks in Go: Lamport and vector clocks checked against a true happens-before order on 5000 simulated runs, plus conflict detection.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "logical-clocks", "lamport", "vector-clock", "go"]
cover = { image = "/images/covers/ds-logical-clocks.png", alt = "Logical clocks: Lamport and vector clocks", hiddenInSingle = true }
+++

Two servers log what they did, and you merge the logs by timestamp to understand an incident. In the merged log, a server receives a message at 10:00:03 that was sent at 10:00:05. The effect appears before its cause. Nothing is broken except the clocks, and the log is now telling a story that cannot be true.

This is the problem of this post: how can a system say "this happened before that" without trusting any clock? [Consistency models](/posts/ds-consistency-models/) left a question open: causal consistency promises that a cause is seen before its effect, so something must be able to detect causes. Here I build that tool, in two versions of increasing precision, and check them against the real answer on thousands of simulated runs. It leans on [why distributed systems are hard](/posts/ds-why-distributed-is-hard/) (clock skew) and [CAP and PACELC, correctly](/posts/ds-cap-pacelc/) (last write wins).

> Honest labelling: everything is Go code in one process, re-run with Go 1.27 (the original run used Go 1.26). The "processes" and the message delays are a **simulation** with seeded randomness (messages are picked at random from those in flight, so they arrive in a different order than they were sent). It is not a network. Numbers are counts, never timings. Tests run with `go test -race`.

## Why wall clocks fail

I give each of three simulated processes a wall clock with a fixed offset: 0, -4 and +3 ticks. These offsets are my own invention to model {{< term "clock-skew" "clock skew" >}}. Every event is stamped with its process's wall clock. A concrete case: process P2 (clock +3) sends a message at tick 10 and stamps it 13. P1 (clock -4) receives it at tick 12 and stamps it 8. The receive is stamped five ticks before the send.

How common is this? In 5000 runs of 24 events each, **3537** runs contained at least one message received with a wall timestamp no later than its own send (5738 such receives in total). The order of timestamps is not the order of causes.

## Happens-before, precisely

To fix this we first need a precise definition of "this could have influenced that". {{< term "happens-before" "Happens-before" >}}, written a → b, has three rules:

1. Events on one process are ordered by the order they ran (program order).
2. A send happens before its matching receive.
3. The relation is transitive: if a → b and b → c, then a → c.

If neither a → b nor b → a, the events are **concurrent**: no chain of messages connects them, so neither could have influenced the other. Concurrent does not mean "at the same time"; it means "unrelated by cause".

In the simulation I compute this ground truth from the recorded log alone, by following those three rules and closing the relation. It never looks at a clock. Whatever a logical clock claims, we can compare it with this answer.

## Lamport clocks

The first idea is a counter that follows causality instead of time. A {{< term "lamport-clock" "Lamport clock" >}} is one integer per process. The rules:

- On every local event or send, increment your counter.
- A message carries the sender's counter. On receive, set your counter to the larger of your own and the message's, plus one.

In the simulator it is two lines:

```go
lam[p]++                              // local or send
lam[p] = max(lam[p], m.lam) + 1       // receive
```

Here is a real trace, printed by the demo: seed 2, three processes P0 to P2, 10 events. Kind `L` is a local event, `S` a send and `R` a receive; `from` is the id of the send that an `R` received. The `vector` column belongs to the next section, ignore it for now:

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

Let me trace two events by hand. Event 5: P2 has done nothing yet (counter 0) and receives the message sent by event 4, which carries 4. So its counter becomes max(0, 4) + 1 = 5. Event 7: P0's counter is 2 (after events 0 and 6). It receives the message sent by event 1, which carries 1, so the counter becomes max(2, 1) + 1 = 3. Every row follows from the rules in the same way.

Now the question is how good this is. Over the same 5000 random runs (2,760,000 ordered pairs of events: 5000 runs × 24 × 23):

```
happens-before pairs: 685631, concurrent pairs: 1388738
lamport: a->b but L(a)>=L(b): 0
lamport: concurrent but L(a)<L(b): 608758, L equal: 171222
```

(The first line counts ordered pairs: 685,631 pairs where a → b, the same number again where b → a, and 1,388,738 concurrent ordered pairs, which adds up to 2,760,000.)

The second line is the good news. Whenever a → b, the Lamport timestamps satisfy L(a) < L(b): zero violations. So if L(a) is not smaller than L(b), a cannot have caused b.

The third line is the catch. The converse is false: in 608,758 concurrent ordered pairs, L(a) is still smaller than L(b), and in 171,222 they are equal. In the trace, events 0 and 2 are concurrent (no message connects P0's first event to P1's second), yet their timestamps are 1 and 2, which looks like "0 before 2". A Lamport timestamp cannot tell "before" from "concurrent". It is consistent with causality, not equal to it.

One more use. If you break ties by process id, comparing the pair `(L, pid)`, you get a **total** order that is consistent with causality. That is useful for things like a distributed lock queue, where everyone must agree on one order. But remember it invents an order between concurrent events.

## Vector clocks

To detect concurrency we need more than one number. A {{< term "vector-clock" "vector clock" >}} keeps one counter per process, so with three processes each event carries three numbers. The rules:

- On every local event or send, increment your own slot.
- A message carries the sender's whole vector. On receive, take the element-wise maximum of your vector and the message's, then increment your own slot.

Look at event 7 in the trace again. P0 had `[2 0 0]` and receives a message carrying `[0 1 0]`. The element-wise maximum is `[2 1 0]`; incrementing P0's own slot (the first one) gives `[3 1 0]`, exactly the row shown above.

To compare two vectors, look at every slot. If one vector is smaller or equal in every slot, its event happened before. If each one is bigger in some slot, they are concurrent:

```go
case less && greater: return Concurrent
case less:            return Before
case greater:         return After
```

(`less` means some slot of `a` is smaller than `b`'s, `greater` that some slot is larger.) In the trace, event 0 is `[1 0 0]` and event 2 is `[0 2 0]`: the first is bigger in slot 0, the second in slot 1, so they are concurrent, exactly right. The demo prints this: "Lamport orders them, vectors say concurrent".

How well does it work? For all 2,760,000 pairs I asserted that `Compare` gives exactly the ground-truth answer (before, after or concurrent):

```
vector clock vs ground truth, mismatches: 0
```

Zero mismatches. A vector clock gives exact causality information. The cost is that each message carries a vector of N counters, one per process. Designs such as dotted version vectors and interval tree clocks address this cost in different ways; I only name them and did not implement them.

## Detecting conflicting writes

A practical use is replicated storage. Two replicas hold one key. The simulation does 10 random steps: either one replica receives a put, or one replica pulls the other's data. The same 1000 seeded workloads run with two strategies (998 of them contained at least one write):

- **Version vectors.** Each put carries a vector, and the client first reads every value the replica currently has and writes one merged value. When a replica pulls from the other, it drops only the versions that are dominated by another (the vector is smaller). A vector clock attached to a stored value like this is a {{< term "version-vector" "version vector" >}}. Versions that are concurrent are both kept; they are called siblings.
- **{{< term "last-write-wins" "Last write wins" >}}.** Keep the value with the biggest wall timestamp. Replica 1's clock is 5 ticks behind, again my invention.

One run (seed 13), showing the four writes, then what each strategy keeps:

```
write a v=[1 0] wall=4
write b v=[2 0] wall=5
write c v=[2 1] wall=2
write d v=[3 0] wall=8
version vectors keep: d[3 0] c[2 1]
last-write-wins keeps: d
```

Read the vectors: `b` `[2 0]` is after `a` `[1 0]`. Then `c` `[2 1]` was written on the other replica after it saw `b`, and `d` `[3 0]` was written on the first replica without having seen `c`. So `c` and `d` are concurrent. Version vectors keep both. LWW keeps only `d`, so `c` is gone, and nobody was told.

Over all workloads:

```
998 seeded workloads: with a conflict 499, writes LWW dropped silently 499, LWW winner was not a latest write 92, version vectors lost 0
```

In 499 of 998 workloads there was a real conflict (two concurrent latest writes). In each of them LWW silently dropped one, 499 writes in total. In 92 workloads the LWW winner was not even a latest write: a later write had already superseded it, so LWW picked the wrong one because of a skewed clock. Version vectors lost nothing, and a test asserts it. The price is that they hand the application both siblings to merge.

## Hybrid logical clocks

Real databases sometimes want timestamps that are close to real time (so humans can read them) and still respect causality. {{< term "hybrid-logical-clock" "Hybrid logical clocks" >}} combine a physical time with a logical counter for this. I did not run one; from what I know of the published design, that is the compromise some databases use.

## Where logical clocks stop helping

- Lamport order is consistent with causality, not equal to it. Do not read "L(a) < L(b)" as "a caused b".
- A vector's size grows with the number of participants. In a store with many clients, tracking per replica instead of per client is usual.
- Detecting a conflict does not resolve it. Someone, the application or a CRDT, has to merge the siblings.
- In my experience, wall-clock LWW is fine for caches and wrong for anything you cannot lose.

## Exercise

Add a fourth process and check that the zero-mismatch result still holds. Then make `Put` stop merging siblings and see how many siblings pile up.

## What's next

Next, “Timeouts, retries and backoff with jitter”: what to do when a call simply does not answer.
