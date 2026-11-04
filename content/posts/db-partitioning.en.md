+++
date = '2027-01-30T10:00:00+03:30'
draft = false
title = 'Table partitioning'
description = 'PostgreSQL table partitioning with real runs: range partitions, pruning in EXPLAIN, primary key rules, DETACH and ATTACH, and when it does not help.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "partitioning", "performance"]
cover = { image = "/images/covers/db-partitioning.png", alt = "Table partitioning", hiddenInSingle = true }
+++

Imagine an `orders` table that has been growing for years. Every query on it is a little slower than last year, and `VACUUM` takes longer each time it runs. Once a month somebody has to delete orders older than two years. That is a huge `DELETE` that touches millions of rows, takes a long time, and leaves a pile of dead rows behind for `VACUUM` to clean up later. And most of the time the application only cares about the last few weeks. Why should the database keep treating the whole table as one big heap?

{{< term "partitioning" "Partitioning" >}} is PostgreSQL's answer: you declare one logical table, but it is stored as several smaller physical tables, called partitions, each holding one slice of the data (for example one month). The application still queries the single logical table. Two things get better. A query that only needs one slice can skip all the other slices. And removing old data becomes dropping a whole partition instead of deleting row by row. Everything else does not get faster, and some things get slower, which is what the last sections show.

This comes after [Zero-downtime migrations](/posts/db-zero-downtime-migrations/), and it leans on [indexes and EXPLAIN](/posts/db-indexes-btree-explain/) and on [the planner and statistics](/posts/db-planner-statistics/), because the benefit shows up in the plans.

> Everything ran on a real PostgreSQL 18.3 (I re-ran the demo for this version of the post). The data is the shop `orders` table (200,000 rows, from 2025-01-01 to 2026-02-05), copied into a partitioned table. I turned parallel scans off so the plans stay short, and I show no timings, only buffer counts. A buffer here is one 8 kB page of the table read from memory or disk, so a lower count means less data was read. The session time zone was UTC.

## Range partitions by month

The parent table is declared with `PARTITION BY RANGE (created_at)`. This means: every row goes to a partition according to which range its `created_at` falls in. The column you partition on is called the **partition key**. The first thing I tried was adding a {{< term "primary-key" "primary key" >}} on `id` alone:

```text
ALTER TABLE orders_p ADD PRIMARY KEY (id);
ERROR:  unique constraint on partitioned table must include all partitioning columns
DETAIL:  PRIMARY KEY constraint on table "orders_p" lacks column "created_at" which is part of the partition key.
```

PostgreSQL refused. The reason is that each partition has its own index, and an index only sees its own partition. So PostgreSQL can guarantee uniqueness across all partitions only if the partition key is part of the constraint: then two equal keys must land in the same partition, where one index can catch them. `PRIMARY KEY (id, created_at)` worked. The practical consequence is that `id` alone is no longer unique as far as the database is concerned.

A loop then created 14 monthly partitions, January 2025 to February 2026, and `INSERT ... SELECT` loaded all 200,000 rows. The rows and size of each partition come from `pg_partition_tree` and `pg_relation_size`:

```text
    partition     | rows  |  size
 orders_p_2025_01 | 15500 | 1040 kB
 orders_p_2025_02 | 14000 | 936 kB
 ...
 orders_p_2026_01 | 15500 | 1048 kB
 orders_p_2026_02 |  2000 | 136 kB
```

(I cut the middle rows; each is about 15,000 rows and a bit under or over 1 MB.) The last partition is small because the data ends on 5 February.

## Partition pruning: the point of it all

Now two queries. The first filters on one month of `created_at`, the partition key. The second filters on `status`, which is not part of the key. Both are shortened to the lines that matter:

```text
WHERE created_at >= '2025-06-01' AND created_at < '2025-07-01'
 Aggregate
   Buffers: shared hit=126
   ->  Seq Scan on orders_p_2025_06 orders_p
 Planning:
   Buffers: shared hit=26

WHERE status = 'paid'
 Aggregate
   Buffers: shared hit=1679
   ->  Append
         ->  Seq Scan on orders_p_2025_01 ... (14 scans in total)
 Planning:
   Buffers: shared hit=56
```

In the first query the {{< term "query-planner" "planner" >}} knew from the ranges which partition can contain June rows, and removed the other 13 before running anything. This is {{< term "partition-pruning" "partition pruning" >}}. The plan has one scan, on `orders_p_2025_06` only, and read 126 buffers (the partition is 1,008 kB, which is 126 pages of 8 kB, so that is exactly one pass over it). In the second query `status` says nothing about which month a row is in, so the planner cannot skip anything. The `Append` node scans all 14 partitions and reads 1,679 buffers.

To prove that the saving comes from pruning, I ran the first query again with `SET enable_partition_pruning = off`. It returned the same answer but with 1,679 buffers and 14 scans, 13 of which returned 0 rows. Same result, thirteen times the reading. The `Planning` lines show the cost of building the plan, which will matter at the end.

## What happens to a row that fits no partition

```text
INSERT ... created_at = '2026-05-10'
ERROR:  no partition of relation "orders_p" found for row
DETAIL:  Partition key of the failing row contains (created_at) = (2026-05-10 00:00:00+00).
```

I had partitions only up to February 2026, so this insert failed. In a real system the same thing can happen at midnight on the first day of a month, if nobody created the new partition in time. A {{< term "default-partition" "default partition" >}} is the safety net: it accepts every row that fits nowhere else. After creating one, the same insert worked. But there is a trap. When I afterwards tried to create the proper May partition:

```text
ERROR:  updated partition constraint for default partition "orders_p_default" would be violated by some row
```

The May row was already sitting in the default partition, and PostgreSQL will not create a May partition while the default holds May rows, because the row would then belong to two places. The way out, in one transaction: detach the default partition, create the May partition, insert the rows back from the default table (they now go to May), truncate the default, and attach it again. The lesson is to create partitions before data for them arrives, and to treat rows in the default partition as an alarm.

## Indexes

`CREATE INDEX orders_p_cust_idx ON orders_p (customer_id)` on the parent created a matching index on every partition (for example `orders_p_2025_01_customer_id_idx`), and new partitions get one automatically. So an index on a partitioned table is really many small indexes, one per partition.

## Detach and attach: the cheap way to remove old data

```text
count(*) orders_p: 200001   (the extra row is the May test row)
ALTER TABLE orders_p DETACH PARTITION orders_p_2025_01;
count(*) orders_p: 184501
count(*) orders_p_2025_01: 15500
```

The 15,500 rows of January left the parent in one step and became an ordinary table, which you can archive or `DROP`. I did the same with February and then ran `DROP TABLE` on it. Removing a month is a catalog change, not a huge `DELETE` that leaves {{< term "vacuum" "dead rows" >}} behind for `VACUUM`. This is the second benefit I mentioned at the start, and for many teams it is the main one.

According to the docs, `DETACH PARTITION ... CONCURRENTLY` exists so that detaching blocks less. In a scratch run on 18.3 I tried it on this table, which still had its default partition, and it was refused with `ERROR: cannot detach partitions concurrently when a default partition exists`. So the default partition has a second cost. I did not test the successful path.

Attaching a table back (or attaching a new table you loaded separately) is where validation matters. PostgreSQL must be sure every row in the new partition really belongs to its range. With `client_min_messages = debug1` the server tells us what it did:

```text
ATTACH ... (no CHECK constraint)
DEBUG:  verifying table "orders_p_2025_01"
DEBUG:  verifying table "orders_p_default"

after ADD CONSTRAINT jan_ck CHECK (created_at >= '2025-01-01' AND created_at < '2025-02-01')
DEBUG:  verifying table "orders_p_2025_01"        (printed by ADD CONSTRAINT itself)
DEBUG:  partition constraint for table "orders_p_2025_01" is implied by existing constraints
DEBUG:  verifying table "orders_p_default"
```

Without a `CHECK`, PostgreSQL verified, that is scanned, the table being attached, as part of the attach itself. With a `CHECK` that already says the same thing, the scan was skipped ("implied by existing constraints"). The scan of the default partition still happened. (The one extra `verifying` line is the `ADD CONSTRAINT` scanning the standalone table to check its own rows. That is the point: you pay for this scan before the attach, on a table nobody is querying, not during it.) A table with a row outside the range is refused: `ERROR: partition constraint of relation "bad" is violated by some row`.

## LIST and HASH

Range is not the only way to split. `PARTITION BY LIST (country)` with `FOR VALUES IN ('IR')` and `IN ('DE','FR','NL')` put 2 and 2 of my 4 test rows into the two partitions. `PARTITION BY HASH (id)` with `MODULUS 4` has no natural ranges; it spreads rows evenly by a hash of the key. It spread 1,000 rows as 259, 234, 276 and 231, and `WHERE id = 42` used an index scan on only one partition, `ord_h_2`.

## When it does not help

Pruning is not free: with more partitions the planner has more to look at. To measure this I made two empty tables with 10 and 500 partitions (primary key `(id, t)`) and read the `Planning: Buffers` line (second run; the numbers were the same on a repeat):

```text
                          10 partitions   500 partitions
filter on the key         198             1563
filter on id only         312             16989
```

Even a query that is pruned down to one partition paid about eight times more planning buffers with 500 partitions (1,563 against 198), and a query without the key paid about fifty-five times more (16,989 against 312). These are counts on empty tables, not timings, so they say nothing about how many milliseconds you would lose. My judgment: partition when you remove old data by date, or when most queries carry the partition key. Keep the number of partitions in the tens. And do not partition a table only because it is big: an ordinary index often does more for much less trouble.

## Before you partition

- **The primary key and every unique index must include the partition key.** Plan your keys around it.
- **Always have a plan for rows outside every range**: a job that creates partitions ahead of time, or a default partition you watch.
- **Add a matching `CHECK` before `ATTACH`**, so the attach does not need a validation scan under lock.
- **A default partition makes adding partitions slower and can block it,** and (as I saw) it blocked `DETACH ... CONCURRENTLY` as well.
- **Queries without the partition key read every partition,** so check the plans of your real queries before you commit to a key.

## Exercise

Partition a copy of `order_items` or `orders` by `HASH (customer_id)`, then compare `EXPLAIN (ANALYZE, BUFFERS)` for a filter on `customer_id` and one on `status`. Then try attaching a table that has one row outside the range, and see what the error says.

## What's next

The next post is [Replication with two real instances](/posts/db-replication-streaming/). Partitioning split one table into parts inside one server; replication goes the other way: a second copy of the whole server that follows the first.
