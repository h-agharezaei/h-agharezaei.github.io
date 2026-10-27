+++
date = '2027-01-30T10:00:00+03:30'
draft = false
title = 'Table partitioning'
description = 'PostgreSQL table partitioning with real runs: range partitions, pruning in EXPLAIN, primary key rules, DETACH and ATTACH, and when it does not help.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "partitioning", "performance"]
cover = { image = "/images/covers/db-partitioning.png", alt = "Table partitioning", hiddenInSingle = true }
+++

In the [previous post](/posts/db-zero-downtime-migrations/) we changed a live table without stopping it. This post is about a table that is simply too big to treat as one piece. {{< term "partitioning" "Partitioning" >}} splits one logical table into smaller physical ones. It helps in two situations: queries that touch one slice of the data, and removing old data cheaply. It does not make everything faster, and the evidence below shows where it costs you. It builds on [indexes and EXPLAIN](/posts/db-indexes-btree-explain/) and [the planner and statistics](/posts/db-planner-statistics/).

> Everything ran on a real PostgreSQL 18.3 with the shop `orders` table (200,000 rows, 2025-01-01 to 2026-02-05), copied into a partitioned table. Parallel scans were turned off to keep plans short, and there are no timings, only buffer counts. The session time zone was UTC.

## Range partitions by month

The parent table is declared with `PARTITION BY RANGE (created_at)`. First, the {{< term "primary-key" "primary key" >}} rule:

```text
ALTER TABLE orders_p ADD PRIMARY KEY (id);
ERROR:  unique constraint on partitioned table must include all partitioning columns
DETAIL:  PRIMARY KEY constraint on table "orders_p" lacks column "created_at" which is part of the partition key.
```

Each partition has its own index, so PostgreSQL can only guarantee uniqueness across partitions if the key is part of the constraint. `PRIMARY KEY (id, created_at)` worked. A loop then created 14 monthly partitions and `INSERT ... SELECT` loaded all 200,000 rows. Per-partition rows and sizes come from `pg_partition_tree` and `pg_relation_size`:

```text
    partition     | rows  |  size
 orders_p_2025_01 | 15500 | 1040 kB
 orders_p_2025_02 | 14000 | 936 kB
 ...
 orders_p_2026_01 | 15500 | 1048 kB
 orders_p_2026_02 |  2000 | 136 kB
```

## Partition pruning

A query on one month, then a query that filters on `status` only:

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

With the key, the {{< term "query-planner" "planner" >}} removed 13 partitions before running (this is {{< term "partition-pruning" "partition pruning" >}}): one scan, 126 buffers. Without the key, all 14 partitions were scanned: 1,679 buffers. Then I ran the first query again with `SET enable_partition_pruning = off`: it came back with the same 1,679 buffers and 14 scans, 13 of them returning 0 rows. Same answer, thirteen times the reading.

## Rows without a partition, and the default partition

```text
INSERT ... created_at = '2026-05-10'
ERROR:  no partition of relation "orders_p" found for row
DETAIL:  Partition key of the failing row contains (created_at) = (2026-05-10 00:00:00+00).
```

A {{< term "default-partition" "default partition" >}} catches such rows, and the same insert then worked. The trap: afterwards I tried to create the May partition.

```text
ERROR:  updated partition constraint for default partition "orders_p_default" would be violated by some row
```

The row for May was already in the default partition. The fix was in one transaction: detach the default, create May, insert the rows back from the default, truncate it, attach it again. Plan for new partitions before data arrives.

## Indexes

`CREATE INDEX orders_p_cust_idx ON orders_p (customer_id)` on the parent created a matching index on every partition (`orders_p_2025_01_customer_id_idx` and so on). New partitions get it automatically.

## DETACH and ATTACH

```text
count(*) orders_p: 200001   (the extra row is the May test row)
ALTER TABLE orders_p DETACH PARTITION orders_p_2025_01;
count(*) orders_p: 184501
count(*) orders_p_2025_01: 15500
```

The 15,500 rows left the parent at once and became an ordinary table to archive or `DROP`. I did the same with February and then `DROP TABLE`: removing a month is a catalog change, not a huge `DELETE` that leaves {{< term "vacuum" "dead rows" >}} behind. According to the docs, `DETACH PARTITION ... CONCURRENTLY` exists for less blocking; I did not run it.

Attaching is where validation matters. With `client_min_messages = debug1`:

```text
ATTACH ... (no CHECK constraint)
DEBUG:  verifying table "orders_p_2025_01"
DEBUG:  verifying table "orders_p_default"

after ADD CONSTRAINT jan_ck CHECK (created_at >= '2025-01-01' AND created_at < '2025-02-01')
DEBUG:  partition constraint for table "orders_p_2025_01" is implied by existing constraints
DEBUG:  verifying table "orders_p_default"
```

Without the `CHECK`, PostgreSQL verified (scanned) the table being attached; with it, the scan was skipped. It still scanned the default partition. A table with a row outside the range is refused: `ERROR: partition constraint of relation "bad" is violated by some row`.

## LIST and HASH

`PARTITION BY LIST (country)` with `FOR VALUES IN ('IR')` and `IN ('DE','FR','NL')` put 2 and 2 of my 4 test rows into the two partitions. `PARTITION BY HASH (id)` with `MODULUS 4` spread 1,000 rows as 259, 234, 276 and 231, and `WHERE id = 42` scanned only `ord_h_2`.

## When it does not help

Planning does more work as partitions multiply. I made two empty tables with 10 and 500 partitions (primary key `(id, t)`) and read `Planning: Buffers` (second run):

```text
                          10 partitions   500 partitions
filter on the key         198             1563
filter on id only         312             16989
```

Even a pruned query paid about eight times more planning buffers at 500 partitions, and a query without the key paid about fifty times more. These are counts on empty tables, not timings. My judgment: partition when you drop old data by date or most queries carry the key, keep the count in the tens, and do not partition a table just because it is big. An index often does more.

## A few things to watch

- The primary key and every unique index must include the partition key.
- Always have a plan (or a default partition) for rows outside every range.
- Add a matching `CHECK` before `ATTACH` to avoid a validation scan.
- A default partition makes adding partitions slower and can block it.
- Queries without the partition key read every partition.

## Exercise

Partition a copy of `order_items` or `orders` by `HASH (customer_id)`, then compare `EXPLAIN (ANALYZE, BUFFERS)` for a filter on `customer_id` and one on `status`. Then try attaching a table with one row outside the range.

## What's next

Next in the series: Replication with two real instances.
