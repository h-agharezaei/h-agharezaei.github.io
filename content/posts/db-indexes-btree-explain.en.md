+++
date = '2026-11-29T10:00:00+03:30'
draft = false
title = 'B-tree indexes and EXPLAIN ANALYZE'
description = 'B-tree indexes in PostgreSQL with real EXPLAIN ANALYZE plans: sequential scan vs index, tree height, index-only scans and what indexes cost on writes.'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "index", "btree", "explain", "performance"]
cover = { image = "/images/covers/db-indexes-btree-explain.png", alt = "B-tree indexes and EXPLAIN ANALYZE", hiddenInSingle = true }
+++

In the [previous post](/posts/db-schema-design-normalization/) we designed the shop schema. Now the schema has 200k orders and the first slow query shows up: all orders of one customer. A {{< term "database-index" "database index" >}} is the usual answer, but let us check it with a {{< term "query-plan" "query plan" >}}.

> Everything ran on a real PostgreSQL 18.3 with the full seed (20k customers, 200k orders). Before this post the only indexes were the primary keys and `customers.email`. I use `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` and show buffer counts (8 KB pages touched), not milliseconds, because pages are the same on every machine.

## Reading a plan

```text
EXPLAIN (ANALYZE, BUFFERS, ...) SELECT * FROM orders WHERE customer_id = 123;

 Seq Scan on orders  (cost=0.00..5857.00 rows=10 width=39) (actual rows=10.00 loops=1)
   Filter: (customer_id = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
```

Each node has `cost` (the planner's estimate, in arbitrary units), `rows` (estimated) and `actual rows` (real). `Buffers: shared hit=3357` means 3357 pages came from cache; `read` would mean they came from disk. The table has exactly 3357 pages (26 MB), so the query read the whole table to return 10 rows. (I turned off parallel scans to keep the plan simple.)

## Adding the index

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

```text
 Bitmap Heap Scan on orders  (cost=4.37..42.86 rows=10 ...) (actual rows=10.00 loops=1)
   Recheck Cond: (customer_id = 123)
   Heap Blocks: exact=10
   Buffers: shared hit=13 read=2
   ->  Bitmap Index Scan on orders_customer_id_idx  (actual rows=10.00 loops=1)
         Buffers: shared hit=3 read=2
```

From 3357 pages to about 15, and the cost estimate dropped from 5857 to 42.9. The planner chose a **Bitmap Heap Scan**: it collects the matching row locations from the index, sorts them by page, then visits each table page once. The 10 rows live in 10 different pages.

## What a B-tree is

The default index type is a {{< term "b-tree" "B-tree" >}}: a balanced tree of 8 KB pages with keys kept sorted. A lookup reads the root, follows one pointer per level and lands in a leaf page that points to the table rows. It is a {{< term "binary-search" "binary search" >}} with a very wide fan-out. Real numbers, using the `pageinspect` extension:

```text
SELECT level FROM bt_metap('orders_customer_id_idx');   -- 1  (root + leaves)
SELECT level FROM bt_metap('orders_pkey');               -- 2  (root + 1 + leaves)
```

The index on `customer_id` has 232 pages (1856 KB) and two levels. The primary key index has three. That is why `WHERE id = 123` costs only `Buffers: shared hit=7`: a few index pages plus one table page.

## Ranges, ordering and index-only scans

Because keys are sorted, ranges and ordering come free:

```text
SELECT * FROM orders ORDER BY id DESC LIMIT 5;
 Limit -> Index Scan Backward using orders_pkey ... Buffers: shared hit=8
```

Eight pages for the last five orders. On the unindexed `created_at` the same query needs a `Sort` over a full `Seq Scan` (3357 pages). Ask for only indexed columns and the table can be skipped:

```text
SELECT customer_id FROM orders WHERE customer_id BETWEEN 100 AND 110;
 Index Only Scan using orders_customer_id_idx ... Heap Fetches: 0  Buffers: shared hit=3
```

`Heap Fetches: 0` means no table page was touched; this works because I ran `VACUUM` first, which marks pages as all-visible. Without that, it must check the table.

An index is not used when the column is wrapped in an expression: `WHERE customer_id + 0 = 123` went back to `Seq Scan` with 3357 pages. Likewise `status = 'paid'` matches about 20% of the table, and the planner chose a sequential scan.

## What an index costs

I made two copies of `orders` with 200k rows each, one with an extra index on `customer_id`, then inserted the same 20k rows into both and measured WAL:

```text
 without the index   3278888 bytes of WAL  (3202 kB)
 with the index      6356256 bytes of WAL  (6207 kB)
```

Almost double the {{< term "wal" "WAL" >}} for the same rows, because every insert also writes an index entry. I also compared index sizes: the primary key grew from 4408 to 4840 kB, but the `customer_id` index stayed at 1856 kB. I checked why afterwards: B-tree pages are built 90% full by default (`fillfactor`), and the same inserts grew an index built with `fillfactor = 100` from 3984 to 7936 kB, so the spare room absorbed them. The index is small because B-tree deduplication stores repeated keys once (4416 kB with it off).

## Unique indexes and unused indexes

A `UNIQUE` constraint is a B-tree that also rejects duplicates, so inserting an existing email fails:

```text
ERROR:  duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(user1@example.com) already exists.
```

To find indexes you pay for but never use, read `pg_stat_user_indexes`: `idx_scan` counts how often each was used. In my run `customers_email_key` had `idx_scan = 0` and 1376 kB of size. Check over a long period before dropping anything.

## A few things to watch

- Always run `EXPLAIN ANALYZE` on realistic data: on 1000 rows the planner prefers a `Seq Scan` and you learn nothing.
- `EXPLAIN ANALYZE` executes the query. Wrap `INSERT`, `UPDATE`, `DELETE` in a transaction you roll back.
- A big gap between `actual rows` and `rows` means stale statistics (`ANALYZE`).
- Every index adds write work and disk space. Index what you filter, join and sort on, not every column.
- Foreign keys do not create an index on the referencing column in PostgreSQL; `orders.customer_id` had none until I added it.

## Exercise

1. Load the shop seed and run `EXPLAIN (ANALYZE, BUFFERS)` for `WHERE customer_id = 123`.
2. Create the index and compare `Buffers`.
3. Find a query on `order_items` that scans the whole table, and fix it.
4. Repeat the WAL experiment with two indexes.

## What's next

Next post: Composite, partial and covering indexes.
