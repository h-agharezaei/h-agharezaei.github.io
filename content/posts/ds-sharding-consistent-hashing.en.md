+++
date = '2027-05-15T10:00:00+03:30'
draft = false
title = 'Sharding and consistent hashing'
description = 'Sharding and consistent hashing: shard-key skew, a hot key, hash slots, a crash-tested migration simulation and real Postgres hash partitions.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "sharding", "consistent-hashing", "partitioning", "go", "postgres"]
cover = { image = "/images/covers/ds-sharding-consistent-hashing.png", alt = "Sharding and consistent hashing", hiddenInSingle = true }
+++

[The previous post](/posts/ds-replication-quorum/) copied the same data to several nodes. That helps availability and reads, but every node still holds everything and takes every write. When the data or the write rate outgrows one machine you need {{< term "sharding" "sharding" >}}: each key lives on one shard. I will not repeat the ring basics from [Bloom filters and consistent hashing](/posts/algo-bloom-filter-consistent-hashing/); I copied its ring code and build on it.

> Honest labelling: sections 1 to 4 are a Go 1.26 simulation on one machine, with seeded randomness and counts only, no timings. The shards are in-memory maps, not a network. Section 5 is a real Postgres 18.3, but on one node.

## 1. The shard key decides the skew

10,000 users belong to 50 tenants, with tenant sizes drawn from a seeded Zipf law. The biggest tenant has 3,510 users (35.1%). Rows per shard with 4 shards:

```
  range by tenant id   rows per shard [8289 918 480 313] max=8289 max/mean=3.32
  hash by user id      rows per shard [2494 2502 2507 2497] max=2507 max/mean=1.00
  hash by tenant id    rows per shard [635 1463 1627 6275] max=6275 max/mean=2.51
```

Range keeps neighbours together (good for range scans) but follows the skew. Hashing the user spreads rows evenly, but a tenant's users are now everywhere. Hashing the tenant keeps a tenant on one shard and still lands the giant one on a single shard. A third option is a directory: a lookup table that places each tenant explicitly. It is flexible and it is one more thing to keep available.

A {{< term "hot-key" "hot key" >}} is worse: 100,000 requests, 20% to one celebrity key.

```
  write load, salt=1: per shard [39826 20011 20271 19892] max/mean=1.59
  write load, salt=8: per shard [24774 29958 22821 22447] max/mean=1.20, a read of the celebrity touches 8 key(s)
```

No hash function helps, the same key hashes to the same shard. Splitting the key with a suffix (`celebrity#0..7`) spreads the writes, and the price is counted: every read now touches 8 keys.

## 2. Fixed slots instead of key moves

Adding a fifth node to 100,000 keys on four:

```
  mod N              moved  80097 keys (80.1%)
  ring, 100 vnodes   moved  18522 keys (18.5%)
  16384 slots        moved  19898 keys (19.9%) = 3276 whole slots of 16384
```

{{< term "consistent-hashing" "Consistent hashing" >}} moves about 1/5. A {{< term "hash-slot" "hash slot" >}} design moves about the same, but in a different way: a key always maps to `hash(key) mod 16384`, and a table maps slots to nodes. Adding a node reassigns whole slots, so you can move, track and retry them one by one. As far as I know from its docs, Redis Cluster uses 16384 slots and Kafka assigns whole partitions to brokers; I did not verify either here. In my experience a slot table is easier to operate than a ring, because the "what moves" question has an explicit answer.

## 3. Moving a shard without losing keys

Routing is either a client-side library that reads a versioned shard map, or a proxy that does it for you. Either way, changing the map needs a staged migration: copy, dual write, verify, cutover, cleanup. The progress (phase and copy cursor) is stored durably, so a restart resumes. In the simulation live writes keep arriving, and each step is idempotent. The checker demands that every key is on exactly one shard with its last acknowledged value.

I crashed the migrator before every one of its operations, restarted it, and checked:

```
  ops in a clean run: 604 (copy=201 dual-write=1 verify=201 cutover=1 cleanup=200 )
  crash before each of the 604+1 points, restart, check: runs=605 violations=0
  negative control (dual write and verify repair removed): runs=605 violations=605
```

The negative control matters: it shows the checker can fail. The simulation has no deletes, no failed network calls and a single migrator, so it proves less than it looks like. It passes `go test -race`.

## 4. Cross-shard work

A query without the shard key must ask every shard, a {{< term "scatter-gather" "scatter-gather" >}}. This is arithmetic, not a measurement: 1,000 queries by shard key make 1,000 shard requests; 1,000 queries by another column make 4,000 with 4 shards, 16,000 with 16 and 64,000 with 64. A transaction across shards needs a saga or two-phase commit, which is a later post.

## 5. Real Postgres: partitions are not shards

```sql
CREATE TABLE events (... user_id int NOT NULL, created_at timestamptz NOT NULL, ...)
  PARTITION BY HASH (user_id);   -- 4 partitions: MODULUS 4, REMAINDER 0..3
```

I inserted 20,000 rows (random user ids, not seeded, so your counts differ):

```
 events_p0 |  5087
 events_p1 |  4941
 events_p2 |  5281
 events_p3 |  4691
```

```
 Seq Scan on events_p2 events
   Filter: (user_id = 42)
```

With `created_at > ...` the plan is an `Append` over all four partitions. That is {{< term "partition-pruning" "partition pruning" >}} on `user_id` only; see [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/) for reading plans. This is {{< term "partitioning" "partitioning" >}} on one node: same disk, same CPU, same failure. Spreading partitions across nodes is what `postgres_fdw` or Citus are for; I only name them, I did not run them.

## A few things to watch

- Choose the shard key from your queries; changing it later means moving everything.
- Check the biggest key, not the average: max/mean is the number to watch.
- Salting a hot key turns one read into several.
- Rehearse resharding with crashes before doing it live.

## Exercise

Make the simulation lose a key on purpose by moving cutover before verify, and see which crash points the checker flags.

## What's next

The next post is “Consensus and Raft”.
