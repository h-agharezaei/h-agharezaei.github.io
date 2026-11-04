+++
date = '2027-05-18T10:00:00+03:30'
draft = false
title = 'Consensus and Raft'
description = 'Consensus and Raft explained with a seeded 5-node Go simulation: elections, partitions, log repair and a safety checker that catches a broken variant.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consensus", "raft", "go", "simulation"]
cover = { image = "/images/covers/ds-consensus-raft.png", alt = "Consensus and Raft", hiddenInSingle = true }
+++

Two machines both believe they are the leader. A client writes `balance=100` to one of them, another client writes `balance=50` to the other, and both writes are accepted. When the network heals there are two different histories, and nobody can say which one is true. This is {{< term "split-brain" "split-brain" >}}, and it is the failure that [replication and quorums](/posts/ds-replication-quorum/) left open: that post counted acknowledgements, but it never said who gets to be the leader, or how everyone agrees on the order of the writes.

Getting a group of machines to agree on one thing, even when some of them crash and messages get lost, is called {{< term "consensus" "consensus" >}}. "One thing" can be a single value ("who is the leader?") or an ordered list of commands ("the log of writes"). It is the basis of coordination services and replicated databases, and sharding ([the previous post](/posts/ds-sharding-consistent-hashing/)) does not make it go away: each shard still needs it. {{< term "raft" "Raft" >}} is a consensus algorithm designed to be understandable, from a paper by Ongaro and Ousterhout. I build a minimal version of it in Go and then try to break it.

This post is about the ideas first, with a small hand-drawn example, and then about a simulation that shows them working and shows what happens when a rule is removed. It leans on [consistency models](/posts/ds-consistency-models/), [CAP and PACELC](/posts/ds-cap-pacelc/) and [timeouts](/posts/ds-timeouts-retries-backoff/).

> This is a **simulation** in Go, re-run with Go 1.27 (the original run used Go 1.26; the output is the same). A single-threaded loop steps 5 nodes. The network (delay, loss, duplication, reordering, partitions) and the clock are simulated and seeded, so every run gives the same output. I show counts, not timings. Not implemented: membership changes, snapshots, real disks and read-index. I did not run a real Raft cluster.

## The idea in plain words

Raft rests on one rule: **nothing counts until a majority has it.** With 3 nodes a majority is 2, with 5 it is 3. Any two majorities share at least one node, which is the same overlap that made R + W > N work in the previous post. That shared node is how a new decision hears about an old one.

On top of that, Raft has three pieces:

1. **Election.** At any time the nodes agree on at most one leader per period of time. Time is cut into numbered periods called **terms**.
2. **Replication.** Only the leader accepts writes. It adds each one to its log and copies it to the followers.
3. **Commit.** A write counts as done, committed, when a majority of nodes have stored it.

Here is a hand-drawn trace with 3 nodes, S1, S2 and S3 (this is an illustration I made up, not demo output). Every node starts as a follower in term 0 with an empty log. The log notation is `term:command`.

```
S2's timer fires first.
  S2 becomes a candidate in term 1, votes for itself, asks S1 and S3 for a vote.
  S1 has not voted in term 1 yet -> votes yes. S2 now has 2 of 3 votes = majority.
  S2 is the leader of term 1.

A client sends x=1.
  S2 appends it:   S2 log [1:x=1]
  S2 sends AppendEntries(prevIndex=0, entries=[1:x=1]) to S1 and S3.
  S1 stores it:    S1 log [1:x=1]  -> replies OK.
  Now S2 and S1 hold it = 2 of 3 = majority  -> commit index = 1. S2 applies x=1.
  (S3 never got the message.)

S2 crashes.
  S1 and S3 stop hearing S2. S1's timer fires: S1 becomes a candidate in term 2.
  S3 votes for S1 (its log is empty, S1's is longer, so S1 is at least as up to date).
  S1 is the leader of term 2, and x=1 is still in its log.
```

Why can't the committed `x=1` be lost? Because it is on a majority, and a candidate needs the votes of a majority. Those two groups share a node. And a node votes only for a candidate whose log is at least as up to date as its own. So a candidate that is missing `x=1`, like S3, could never get the vote of S1. The new leader always has everything that was committed.

One more situation: a follower's log can have a tail that the leader does not agree with, for example left over from an old leader that crashed:

```
leader   [1:a 1:b 2:c]
follower [1:a 1:b 1:z]
```

The leader sends `AppendEntries(prevIndex=2, prevTerm=1, [2:c])`: "after your entry 2, which has term 1, put `2:c`". The follower has a matching entry 2, so it accepts. Its entry 3 (`1:z`) conflicts, so it is dropped and replaced by `2:c`. If the follower had *not* had a matching entry 2, it would refuse, and the leader would step back one entry and try again until the logs match.

## The rules, a bit more precisely

**Election.** A follower that hears nothing from a leader for a random 12 to 23 ticks becomes a candidate, increments the term and asks for votes. The randomness makes it unlikely that two nodes time out together. A node votes once per term, and only for a candidate whose log is at least as up to date as its own. A majority wins ({{< term "leader-election" "leader election" >}}). A node's term, its vote and its log survive a crash; everything else (commit index, applied state) is lost and rebuilt.

**Replication.** Only the leader appends to the {{< term "replicated-log" "replicated log" >}}. It sends `AppendEntries(prevIndex, prevTerm, entries)`. A follower refuses unless it has the previous entry. The leader then steps back until the logs match, and overwrites any conflicting tail.

**Commit.** An entry is committed when a majority holds it, but there is a subtle catch: the leader counts replicas only for entries of **its own term**. Older entries become committed indirectly, when a newer entry on top of them does. That is why a new leader appends a no-op entry in its own term as soon as it wins. The check in the demo's code is this line, where `BugOldTerm` is a switch I use later to break it on purpose:

```go
if cnt >= c.maj() && (n.Log[N-1].Term == n.Term || c.cfg.BugOldTerm) { // commit N }
```

`cnt` is how many nodes hold entry `N`, `c.maj()` is the majority, and the second condition is the "own term" rule.

## Election, then a leader crash

The first demo (`go run . election`) starts 5 nodes with 2% message loss. It waits for a leader, sends three commands (`x=1`, `y=2`, `x=3`), crashes the leader, and waits for a new one. This is the real output:

```
== (a) first election, then (b) leader crash ==
t= 12  n2 election timeout -> candidate, term 1
t= 13  n0 votes for n2 in term 1
t= 13  n1 votes for n2 in term 1
t= 13  n3 votes for n2 in term 1
t= 15  n4 votes for n2 in term 1
t= 15  n2 wins term 1 with a majority -> LEADER
-- leader n2 log [1:noop 1:x=1 1:y=2 1:x=3] commit=4
t= 30  n2 CRASH (term 1, log 4, commit 4)
t= 47  n1 election timeout -> candidate, term 2
t= 49  n3 votes for n1 in term 2
t= 50  n0 votes for n1 in term 2
t= 52  n1 wins term 2 with a majority -> LEADER
t= 53  n4 election timeout -> candidate, term 2
-- new leader n1 term 2 log [1:noop 1:x=1 1:y=2 1:x=3 2:noop] commit=5 kv=map[x:3 y:2]
```

Reading it from the top:

- At `t=12` n2's random timer was the first to fire, so it became a candidate in term 1. The three votes at `t=13` are the other nodes granting it, and the "wins" line at `t=15` is when enough of the vote replies had arrived back at n2: its own vote plus two others is 3 of 5, a majority. The messages take one or more ticks, which is why the win comes after the votes.
- The first log line shows what the leader holds: the `noop` it appended when it won (index 1), then the three commands. `commit=4` means all four entries are committed.
- n2 crashes at `t=30`. The followers stop hearing heartbeats, and at `t=47` n1's timer fires first: a new election, term 2. Two nodes vote for it and it wins at `t=52`.
- The last line is the point. The new leader's log is the old log plus a new `2:noop`, so every committed entry survived. `kv=map[x:3 y:2]` is the state machine (a simple key-value map): `x` was overwritten by the later `x=3`.
- n4's timer fired at `t=53`, one tick after n1 had already won, so it started its own election for term 2. It cannot win: the others have already voted in term 2. When n1's next heartbeat arrives, n4 falls back to being a follower. The demo does not print that last step; it follows from the rules above.

## A partition

Now the case that causes split-brain. Five nodes, and the network is cut in two: the old leader n2 and n3 are on one side, and n0, n1 and n4 on the other. Clients keep sending writes to n2, the old leader, on the small side. The demo prints the state on both sides, and then heals the network (`go run . partition`):

```
== (c) partition: minority cannot commit ==
before: old leader n2 term 1 commit=3 log [1:noop 1:x=1 1:y=2]
t=108  n0 wins term 5 with a majority -> LEADER
  n2 term=1 role=leader log=7 commit=3
  n3 term=1 role=follower log=7 commit=3
  --
  n0 term=5 role=leader log=6 commit=6
  n1 term=5 role=follower log=6 commit=6
  n4 term=5 role=follower log=6 commit=6
  --
old leader n2 log during partition [1:noop 1:x=1 1:y=2 1:a=1 1:b=2 1:c=3 1:z=9]
t=148  HEAL
old leader n2 log after heal      [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8] role=follower commit=6
new leader n0 log                 [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8]
safety violation: ""
```

- **The minority side** (first block). n2 still believes it is the leader of term 1 and has accepted four new writes (`a=1`, `b=2`, `c=3`, `z=9`), so its log has 7 entries, and n3 has copied them. But **`commit=3` has not moved**: two nodes out of five are not a majority, so none of the four writes can commit.
- **The majority side** (second block). The three nodes elected n0 at `t=108`. The term is 5, so terms 2, 3 and 4 passed without a leader; the demo prints only LEADER lines here, so I cannot tell you why (lost messages or competing candidates are the usual reasons). The new leader committed `p=7` and `q=8`, and its `commit=6`.
- **After the heal** (`t=148`). n2 receives a message with term 5, sees that its own term 1 is old, and steps down to follower. Its four uncommitted entries are overwritten by the leader's log. Nobody was ever told those four writes were committed, so nothing a client was promised is lost.
- The final line, `safety violation: ""`, is the checker saying no property was broken.

The reason the two sides could not both commit is the arithmetic from the start: any two majorities share a node, so two sides of a {{< term "network-partition" "network partition" >}} can never both hold one. Without that rule you get the split-brain from the start of this post.

## The safety checker

One demo and two outputs prove little; the cleaner way to build trust is to let a checker watch thousands of random runs. Every run checks four properties from the Raft paper:

- **Election Safety:** at most one leader per term. (An old leader from an earlier term may still exist for a while, as in the partition above, but two leaders can never share a term.)
- **Log Matching:** if two logs hold an entry with the same index and the same term, then the logs are identical up to that index.
- **Leader Completeness:** a new leader's log contains every entry committed before it. (The property from the hand-drawn trace.)
- **State Machine Safety:** no two nodes ever apply different commands at the same log index.

Each run has 5 nodes and 1000 ticks, with 10% message loss, 5% duplication, delays from 1 to 6 ticks (so messages can arrive out of order), random crashes, restarts, partitions, and extra crashes aimed at the current leader. Clients write to whoever is leader. I ran 3000 seeds against the correct code (`go run . safety`):

```
correct Raft                       runs=3000 violations=0
  crashes=91790 partitions=21155 msgs sent=4263233 dropped=810305 duplicated=173709
  leaders elected=52685 entries committed=176166
  checks: election-safety=52685 leader-completeness=52685 log-matching=3030000 state-machine=1795219
```

The first line is the answer: **zero violations in 3000 runs**. The next lines show the checker actually had things to look at: over 91 thousand crashes and 21 thousand partitions, and 52,685 elections. The `checks` line counts how many times each property was tested: election-safety and leader-completeness once per elected leader, log-matching for each pair of nodes every 10 ticks, and state-machine for each entry that a node applied.

A checker that never fires might simply be blind. So the next step is to make the code wrong on purpose and see whether the checker notices.

## Breaking it on purpose

I made two bugs, each behind a switch (`go run . broken`). **Variant 1** is the situation Figure 8 of the Raft paper warns about: the leader commits an entry from an *older* term as soon as a majority holds it, instead of waiting for an entry of its own term. **Variant 2** skips the "log at least as up to date" check when voting. Both are small, tempting-looking changes. The real output:

```
BROKEN: old-term entries by count  runs=3000 violations=2
  crashes=91781 partitions=21155 msgs sent=4263085 dropped=810292 duplicated=173702
  leaders elected=52682 entries committed=177618
  checks: election-safety=52682 leader-completeness=52682 log-matching=3029850 state-machine=1815410
  first failing seed 373: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
  replay seed 373, last events before the violation:
    t=845  OLD-TERM: index 30 holds a term-9 entry, committed by counting replicas
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    ...
    t=853  n2 (leader, term 38) commits up to index 38
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    t=861  PARTITION groups=[1 1 1 1 1]
    t=876  n4 restart: term 38, voted 2, log 70 kept; commit/applied/kv lost
    t=879  n0 wins term 45 with a majority -> LEADER
  replay: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
  same seed 373 with the correct code: violation=""
BROKEN: no up-to-date vote check   runs=3000 violations=2963
  crashes=30043 partitions=6986 msgs sent=1312485 dropped=252070 duplicated=52991
  leaders elected=18840 entries committed=81165
  checks: election-safety=18840 leader-completeness=18840 log-matching=981960 state-machine=654398
  first failing seed 1: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  replay seed 1, last events before the violation:
    ...
    t=338  n1 CRASH (term 14, log 36, commit 36)
    t=340  n3 CRASH (term 14, log 36, commit 34)
    t=370  n1 restart: term 14, voted 1, log 36 kept; commit/applied/kv lost
    t=381  n3 restart: term 14, voted 1, log 36 kept; commit/applied/kv lost
    t=389  n4 wins term 17 with a majority -> LEADER
  replay: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  same seed 1 with the correct code: violation=""
```

What the numbers say:

- The checker **does** fire. Variant 1 broke 2 of 3000 runs. It is rare because it needs a leader to commit an old entry and then die at the wrong moment, and then a node without that entry has to win. In seed 373 the leader n2 committed index 38, which held a term-25 entry, only by counting copies (`t=853`). After a partition and a restart, n0 won term 45 without that entry in its log, and the checker reported Leader Completeness: a committed entry was missing from a new leader.
- Variant 2 broke 2963 of 3000 runs, nearly all of them. Without the vote check a node with a stale log can win an election. In seed 1, n4 became leader in term 17 without committed entry 1.
- Both lines end with the control: **the same seed with the correct code gives no violation.** The simulation is deterministic, so the same seed makes the same crashes and partitions; only the rule differs. A test (`TestBrokenVariantsAreCaught`) pins exactly these two seeds.

## How many nodes do you need?

If a majority is needed for everything, how many nodes can you lose? The last demo (`go run . sweep`) starts a cluster of n nodes, crashes k of them at the very start, and asks whether 5 commands still get committed within 400 ticks, for every one of 20 seeds. Each row is one cluster size, and the `yes`/`no` values are for k = 0, 1, 2, and so on:

```
nodes  majority  crashed-from-start -> committed 5 commands in 400 ticks?
1      1         yes no  => tolerates 0 (formula (n-1)/2 = 0)
2      2         yes no no  => tolerates 0 (formula (n-1)/2 = 0)
3      2         yes yes no no  => tolerates 1 (formula (n-1)/2 = 1)
4      3         yes yes no no no  => tolerates 1 (formula (n-1)/2 = 1)
5      3         yes yes yes no no no  => tolerates 2 (formula (n-1)/2 = 2)
6      4         yes yes yes no no no no  => tolerates 2 (formula (n-1)/2 = 2)
7      4         yes yes yes yes no no no no  => tolerates 3 (formula (n-1)/2 = 3)
```

Take the row for 5 nodes: it commits with 0, 1 or 2 nodes crashed, and fails with 3 or more, because 2 survivors are not a majority of 5. To tolerate f failures you need 2f + 1 nodes. The rows for 4 and 6 are the interesting ones: a 4th node tolerates no more failures than 3 nodes (still only 1), and a 6th no more than 5. An even number of nodes adds cost without adding tolerance. A test runs this sweep for every size from 1 to 7.

## Raft traps

- **Every write goes through the leader, and a leader can be out of date.** A deposed leader may not know yet that it was deposed, so a read from it can be stale. Linearizable reads need a read-index or a lease (I name these, I did not build them).
- **A node that rejoins can disturb a healthy leader.** A node that was cut off keeps timing out and raising its term; when it returns, its high term forces the leader to step down. Pre-vote is the usual fix (also not built).
- **Raft and Paxos solve the same problem.** etcd and Consul use Raft. NATS documents JetStream replication as Raft-based, which I did not re-read for this post; see [JetStream in production](/posts/nats-jetstream-production/).
- **Persistence is where bugs hide.** In my experience this is the bug magnet: if a node replies to a vote request before it has saved its term and vote to disk, a crash can make it vote twice in one term, which breaks Election Safety. My in-memory simulation cannot show that.
- **Finding nothing in 3000 runs is evidence, not a proof.** The two broken variants show the checker can find bugs; a bug that needs a more unusual sequence may still hide.

## Exercise

Remove the leader's no-op, but keep the commit rule, and rerun the 3000 seeds. Does safety fail? What gets slower, and why? (Hint: think about what an old-term entry needs before it can commit.)

## What's next

The next post is "Sagas or two-phase commit?". Raft gives you one agreed log for one group of nodes. What about a business operation that spans several separate services, each with its own database, with no shared log between them?
