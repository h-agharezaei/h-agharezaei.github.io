+++
date = '2027-05-18T10:00:00+03:30'
draft = false
title = 'Consensus and Raft'
description = 'Consensus and Raft explained with a seeded 5-node Go simulation: elections, partitions, log repair and a safety checker that catches a broken variant.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "consensus", "raft", "go", "simulation"]
cover = { image = "/images/covers/ds-consensus-raft.png", alt = "Consensus and Raft", hiddenInSingle = true }
+++

[The previous post](/posts/ds-sharding-consistent-hashing/) split data across nodes. Copies raise a harder question: how do several nodes agree on one order of writes when some crash and the network lies? That is {{< term "consensus" "consensus" >}}. I build a minimal {{< term "raft" "Raft" >}} (paper by Ongaro and Ousterhout) and try to break it. See [replication and quorums](/posts/ds-replication-quorum/), [consistency models](/posts/ds-consistency-models/), [CAP](/posts/ds-cap-pacelc/) and [timeouts](/posts/ds-timeouts-retries-backoff/).

> Honest labelling: a **simulation** in Go 1.26 on one machine. A single-threaded loop steps 5 nodes; network (delay, loss, duplication, reordering, partitions) and clock are simulated and seeded, so outputs are reproducible. Counts only, no timings. Not implemented: membership changes, snapshots, real disks, read-index. No real Raft cluster was run.

## The three pieces

**Election.** Time is split into terms. A follower that hears nothing for a random 12 to 23 ticks becomes a candidate, increments the term and asks for votes. A node votes once per term, only for a candidate whose log is at least as up to date as its own. A majority wins ({{< term "leader-election" "leader election" >}}). Term and vote survive a crash; the rest is lost.

**Replication.** Only the leader appends to the {{< term "replicated-log" "replicated log" >}}. It sends `AppendEntries(prevIndex, prevTerm, entries)`. A follower refuses unless it has that previous entry; the leader steps back until the logs match, then overwrites any conflicting tail.

**Commit.** An entry is committed when a majority holds it, but the leader only counts replicas for entries of its own term. Older entries commit indirectly, so a new leader appends a no-op first.

```go
if cnt >= c.maj() && (n.Log[N-1].Term == n.Term || c.cfg.BugOldTerm) { // commit N }
```

## Election, then a leader crash

```
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

n2 timed out first and won. After it died, the committed entries survived on the new leader. n4 timed out late in term 2, lost, and followed n1.

## A partition

Old leader n2 and n3 are cut off from n0, n1, n4. Clients write to n2 on the small side:

```
t=108  n0 wins term 5 with a majority -> LEADER
  n2 term=1 role=leader log=7 commit=3
  n3 term=1 role=follower log=7 commit=3
  n0 term=5 role=leader log=6 commit=6
  n1 term=5 role=follower log=6 commit=6
  n4 term=5 role=follower log=6 commit=6
old leader n2 log during partition [1:noop 1:x=1 1:y=2 1:a=1 1:b=2 1:c=3 1:z=9]
t=148  HEAL
old leader n2 log after heal      [1:noop 1:x=1 1:y=2 5:noop 5:p=7 5:q=8] role=follower commit=6
```

The minority leader accepted four writes but its commit stayed at 3: two nodes are not a majority. The other side elected a leader and committed to 6. After healing, n2 saw term 5, stepped down, and its uncommitted entries vanished; nobody had been told they were committed. Any two {{< term "quorum" "quorum" >}}s share a node, so both sides of a {{< term "network-partition" "network partition" >}} can never commit; without that you get {{< term "split-brain" "split-brain" >}}.

## The safety checker

Every run is checked for four properties:

- **Election Safety:** at most one leader per term.
- **Log Matching:** if two logs agree on an entry's term at an index, they agree on everything before it.
- **Leader Completeness:** a new leader holds every committed entry.
- **State Machine Safety:** no two nodes apply different commands at one index.

Each run: 5 nodes, 1000 ticks, 10% loss, 5% duplication, delay 1 to 6, random crashes, restarts, partitions, and extra crashes of the leader. 3000 seeds, correct code:

```
correct Raft                       runs=3000 violations=0
  crashes=91790 partitions=21155 msgs sent=4263233 dropped=810305 duplicated=173709
  leaders elected=52685 entries committed=176166
  checks: election-safety=52685 leader-completeness=52685 log-matching=3030000 state-machine=1795219
```

Zero violations. A checker that never fires might be blind, so I break the code.

## Breaking it on purpose

Variant 1 is the Figure 8 bug from the paper: commit an old-term entry once a majority holds it. Variant 2 skips the up-to-date check when voting.

```
BROKEN: old-term entries by count  runs=3000 violations=2
  first failing seed 373: t=879: Leader Completeness: n0 became leader in term 45 without committed entry 36 ({25 noop})
    t=853  OLD-TERM: index 38 holds a term-25 entry, committed by counting replicas
    t=879  n0 wins term 45 with a majority -> LEADER
  same seed 373 with the correct code: violation=""
BROKEN: no up-to-date vote check   runs=3000 violations=2963
  first failing seed 1: t=389: Leader Completeness: n4 became leader in term 17 without committed entry 1 ({2 noop})
  same seed 1 with the correct code: violation=""
```

The first bug is rare (2 of 3000): it needs a leader to die at the wrong moment and a stale node to win. The second breaks almost every run. Both lose a committed entry; the same seeds pass with the real rules, and a test pins them.

## How many nodes

I crashed k of n nodes at the start (20 seeds each) and asked whether 5 commands commit:

```
3      2         yes yes no no  => tolerates 1 (formula (n-1)/2 = 1)
4      3         yes yes no no no  => tolerates 1 (formula (n-1)/2 = 1)
5      3         yes yes yes no no no  => tolerates 2 (formula (n-1)/2 = 2)
6      4         yes yes yes no no no no  => tolerates 2 (formula (n-1)/2 = 2)
```

f failures need 2f+1 nodes; a 4th node adds cost, not tolerance. The sweep for 1 to 7 is a test.

## A few things to watch

- Every write goes through the leader. A deposed leader may not know yet, so its reads can be stale; {{< term "linearizability" "linearizable" >}} reads need a read-index or a lease (named, not built).
- A rejoining node can bump terms and disturb a healthy leader; pre-vote addresses that (not built).
- Raft and Paxos solve the same problem. etcd and Consul use Raft. NATS documents JetStream replication as Raft-based; I did not re-read it for this post. See [JetStream in production](/posts/nats-jetstream-production/).
- In my experience, persistence is the bug magnet: not syncing the term or vote before replying breaks Election Safety. My simulation keeps them in memory, so it cannot show that.
- Finding nothing in 3000 runs is evidence, not a proof.

## Exercise

Remove the leader's no-op (keep the commit rule) and rerun 3000 seeds. Does safety fail? What gets slower, and why?

## What's next

"Sagas or two-phase commit?": consistency across several services without one shared log.
