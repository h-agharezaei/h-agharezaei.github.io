+++
date = '2027-05-15T10:00:00+03:30'
draft = false
title = 'Sharding and consistent hashing'
description = 'Sharding and consistent hashing: shard-key skew, a hot key, hash slots, a crash-tested migration simulation and real Postgres hash partitions.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "sharding", "consistent-hashing", "partitioning", "go", "postgres"]
cover = { image = "/images/covers/ds-sharding-consistent-hashing.png", alt = "Sharding and consistent hashing", hiddenInSingle = true }
+++

Imagine an application that serves many companies, and you split its users across four databases, one slice of companies per database. Now suppose one company turns out to be a third of all your users. Three of the four databases are quiet, and the fourth takes every request of that company. You have four machines, and the system is only as fast as one of them.

This is the problem of {{< term "sharding" "sharding" >}}: splitting one dataset across several machines (called **shards**) so that each key lives on exactly one of them. [Replication](/posts/ds-replication-quorum/), the previous post, puts the *same* data on several machines. That helps when a machine dies and when many clients read, but every machine still holds everything and takes every write. When the data or the write rate outgrows one machine, you have to divide it.

Sharding raises three questions, and this post goes through them in order:

1. **Which shard does a key go to?** The choice of the *shard key* decides whether the load is even.
2. **What happens when you add a machine?** A careless rule moves almost every key; a good one moves only a few.
3. **How do you move data without losing it, and what do you give up?** Queries and transactions that touch several shards get harder.

I will not repeat the ring basics from [Bloom filters and consistent hashing](/posts/algo-bloom-filter-consistent-hashing/); the ring here is a simplified version of its ring, with a different hash finalizer, so the exact counts differ from that post.

> Sections 1 to 4 are a Go **simulation** on one machine. The randomness is seeded and I show counts only, no timings. The shards are in-memory maps, not a network. The numbers are the same as in my original run with Go 1.26; I re-ran the demo with Go 1.27, including `go test -race`. Section 5 is plain arithmetic. Section 6 is a real PostgreSQL 18.3, but on a single node. The SQL for it was not saved in the demo directory, so I wrote it again as a scratch script and ran that with Go-embedded Postgres 18.3; the SQL shown is that script.

## 1. The shard key decides the skew

The **shard key** is the field whose value decides the shard. Everything about balance follows from that choice. To make it concrete, the simulation has 10,000 users who belong to 50 tenants (companies). Tenant sizes follow a seeded Zipf law, which means a few tenants are huge and many are tiny, a common shape for real data. The biggest tenant has 3,510 users, which is 35.1% of everyone.

I put these users on 4 shards in three ways and counted the rows on each shard. `max/mean` is the busiest shard divided by the average; 1.00 would be perfect:

```
  range by tenant id   rows per shard [8289 918 480 313] max=8289 max/mean=3.32
  hash by user id      rows per shard [2494 2502 2507 2497] max=2507 max/mean=1.00
  hash by tenant id    rows per shard [635 1463 1627 6275] max=6275 max/mean=2.51
```

- **Range by tenant id** gives tenants 1 to 13 to shard 0, and so on. Neighbouring keys stay together, which is good for range scans, but it follows the skew: in this data the biggest tenants have the lowest ids, so shard 0 holds 8,289 rows, 3.32 times the average.
- **Hash by user id** spreads the rows almost perfectly (max/mean 1.00). The price is that one tenant's users are now on all four shards.
- **Hash by tenant id** keeps each tenant on one shard, which is convenient, but the giant tenant still lands on a single shard: 6,275 rows, 2.51 times the average.

A fourth option is a **directory**: a lookup table that says which shard each tenant lives on. You can put the giant tenant alone on a shard. It is flexible, and it is one more thing that must be fast and always available.

There is no best choice here. It depends on what your queries ask for. The point is that you should look at the size of your biggest key, not only at the average.

## 2. A hot key: when hashing cannot help

A {{< term "hot-key" "hot key" >}} is a different problem. Here one single key gets a huge share of the traffic. In the simulation, 100,000 write requests arrive and 20% of them go to one "celebrity" key; the rest are spread over ordinary user keys:

```
  write load, salt=1: per shard [39826 20011 20271 19892] max/mean=1.59
  write load, salt=8: per shard [24774 29958 22821 22447] max/mean=1.20, a read of the celebrity touches 8 key(s)
```

With `salt=1` the celebrity key lives on one shard. That shard gets its fair 20,000 requests plus the celebrity's 20,000, about 40,000. No hash function can fix this, because the same key always hashes to the same shard.

The fix is to **salt** the key: split `celebrity` into 8 keys, `celebrity#0` to `celebrity#7`, and let each write pick one at random. They hash to different shards, so with `salt=8` the busiest shard drops to max/mean 1.20. The price is on the read side: to read the celebrity's value you must now read all 8 keys and combine them. That is the trade, counted in the last column: one read now touches 8 keys.

## 3. When you add a machine: `% N` against a ring

Say you have 4 nodes and a key goes to `hash(key) % 4`. You add a fifth, and the rule becomes `hash(key) % 5`. A small example shows what that does. Pretend the hash of a key is the key itself, and watch the keys 0 to 11 when the number of nodes goes from 3 to 4:

```
key:        0 1 2 3 4 5 6 7 8 9 10 11
% 3 node:   0 1 2 0 1 2 0 1 2 0  1  2
% 4 node:   0 1 2 3 0 1 2 3 0 1  2  3
stays?      y y y n n n n n n n  n  n
```

Only keys 0, 1 and 2 stay; 9 of the 12 keys move. On a cache that means almost everything is suddenly in the wrong place, and on a database it means copying most of the data.

**Consistent hashing** changes the question. Imagine a ring of positions, here 0 to 99 (in code they are 64-bit hash values). Each node is placed on the ring at a point given by hashing its name, and a key is hashed to a point too. A key belongs to the first node you meet going clockwise from its point:

```
position:   0 ....... 10 ........ 40 ........ 70 ........ 99
                      [A]         [B]         [C]

key 25 -> walk right, first node is B (40)
key 55 -> walk right, first node is C (70)
key 85 -> walk right, pass 99, wrap around to 0, first node is A (10)
```

Now add node D at position 60. Which keys change owner? Only the keys between 40 and 60: they used to belong to C (their next point was 70) and now belong to D. Every other key still finds the same node first. Keys move only *onto* the new node, never between the old ones.

With one point per node the arcs between points are uneven, so some nodes would own much more than others. The fix is to give each node many points on the ring, called **virtual nodes** (here 100 per node), so that the many small arcs average out.

The simulation adds a fifth node to 4 nodes with 100,000 keys and counts the keys whose owner changes:

```
  mod N              moved  80097 keys (80.1%)
  ring, 100 vnodes   moved  18522 keys (18.5%)
  16384 slots        moved  19898 keys (19.9%) = 3276 whole slots of 16384
```

The ideal is 20%, since the new node should take only its fair fifth. `% N` moves 80.1%, four times more than needed. The ring moves 18.5%, close to the ideal, which is {{< term "consistent-hashing" "consistent hashing" >}} doing its job. (The ring's share can land a little above or below 20% depending on where the points fall; in the Bloom filter post, with a different hash, it was 22.6%.)

The third row is a different design, the {{< term "hash-slot" "hash slot" >}} approach. A key *always* maps to a slot, `hash(key) mod 16384`, and that never changes. A separate table says which node owns each slot. Adding a node means reassigning whole slots to it: here 3,276 of the 16,384, which carry 19,898 keys. Because the unit of movement is a whole slot, you can move, track and retry them one at a time, and the answer to "what is moving?" is an explicit list. As far as I know from its docs, Redis Cluster uses 16,384 slots and Kafka assigns whole partitions to brokers; I did not verify either here. In my experience a slot table is easier to operate than a ring for that reason.

## 4. Moving data without losing it

Knowing *which* keys move is the easy part. Moving them while clients keep writing is the hard part. A router, either a client library or a proxy, reads a versioned shard map and sends each request to the right shard. Changing that map requires a staged migration:

1. **Copy** all keys from the source shard A to the new shard B, while live writes keep going to A.
2. **Dual write**: from now on every write goes to both A and B.
3. **Verify**: compare A and B and repair any difference (while dual write is still on).
4. **Cutover**: reads and writes now go to B only.
5. **Cleanup**: delete the keys from A.

The migration's progress, the phase and the copy cursor, is stored durably, so if the migrator crashes it resumes where it stopped. Every step is safe to repeat. In the simulation, live writes keep arriving during every phase, and a checker asserts the invariant: every key is on exactly one shard and holds its last acknowledged value.

To test it, I crashed the migrator before every single one of its operations, restarted it, and ran the checker:

```
  ops in a clean run: 604 (copy=201 dual-write=1 verify=201 cutover=1 cleanup=200 )
  crash before each of the 604+1 points, restart, check: runs=605 violations=0
  negative control (dual write and verify repair removed): runs=605 violations=605
```

The first line says a clean run has 604 operations, split by phase. The second line says I made 605 runs: a crash before each of the 604 operations, plus one run with no crash, and none of them broke the invariant. The third line is a **negative control**: the same test with dual write and the verify repair removed. It fails in all 605 runs, including the one without a crash, because without dual write the writes that arrive during the copy are lost whatever the crash point. That is its job: it shows that the checker can fail, so "0 violations" means something.

This proves less than it looks like. The simulation has no deletes, no failed network calls and a single migrator, and its shards are maps in one process. It passes `go test -race`, but a real migration has many more ways to go wrong.

## 5. What you give up: queries and transactions across shards

If a query contains the shard key, the router sends it to one shard. If it does not, for example you look up users by email but the data is sharded by tenant, it has to ask every shard and merge the answers. This is called {{< term "scatter-gather" "scatter-gather" >}}. The cost is plain arithmetic, not a measurement: 1,000 queries by the shard key make 1,000 shard requests, while 1,000 queries by another column make 4,000 with 4 shards, 16,000 with 16 and 64,000 with 64. The more shards you have, the worse it gets.

A transaction that changes data on two shards is harder still. There is no single database to make it atomic. That needs a saga or two-phase commit, the topic of [Sagas or two-phase commit?](/posts/ds-saga-vs-2pc/) later in this series.

## 6. Real Postgres: partitions are not shards

Postgres can split one table into pieces by a hash of a column. Here is a table with 4 hash partitions (I ran this from a scratch script, not from the demo directory):

```sql
CREATE TABLE events (
  id bigint GENERATED ALWAYS AS IDENTITY,
  user_id int NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  payload text
) PARTITION BY HASH (user_id);
CREATE TABLE events_p0 PARTITION OF events FOR VALUES WITH (MODULUS 4, REMAINDER 0);
-- ... the same for events_p1, p2, p3 (REMAINDER 1, 2, 3)
```

I inserted 20,000 rows with random user ids (unseeded, so your counts will differ) and counted the rows per partition:

```
 events_p0 |  4903
 events_p1 |  5044
 events_p2 |  5131
 events_p3 |  4922
```

Hashing spreads the rows evenly, as in section 1. Then I asked for one user. The plan below shows that Postgres looked at only one partition, because the query filters on the partition key:

```
 Seq Scan on events_p2 events
   Filter: (user_id = 42)
```

A query on a different column cannot do this. With `created_at > now() - interval '1 hour'` the plan is an `Append` over `Seq Scan`s of all four partitions: like scatter-gather, it touches everything. Skipping partitions that cannot hold the answer is called {{< term "partition-pruning" "partition pruning" >}}, and here it works only for `user_id`. To read plans like these, see [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/).

The point of this section is a limit. This is {{< term "partitioning" "partitioning" >}} on **one node**: the same disk, the same CPU and the same failure. It makes tables easier to manage and queries easier to prune, but it does not spread the load across machines. Spreading partitions over several nodes is what `postgres_fdw` or Citus are for; I only name them, I did not run them.

## Where sharding hurts

- **The shard key is hard to change.** Choose it from your queries, because changing it later means moving every row.
- **Look at the biggest key, not the average.** `max/mean` is the number to watch, as the 3.32 and 2.51 above show.
- **Salting a hot key turns one read into several.** It cures the hot shard by making reads more expensive.
- **Rehearse resharding with crashes before doing it live.** The negative control above is the reason: without the dual write the migration looks fine until it loses data.

## Exercise

Make the simulation lose a key on purpose: move the cutover step before verify, then see which crash points the checker flags.

## What's next

The next post is "Consensus and Raft". Both replication and sharding quietly assumed that someone decides the leader, or the shard map, and that everybody agrees. The next post is about how several nodes agree on one value even when some of them fail.
