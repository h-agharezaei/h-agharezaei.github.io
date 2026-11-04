+++
date = '2026-11-29T10:00:00+03:30'
draft = false
title = 'B-tree indexes and EXPLAIN ANALYZE'
description = 'B-tree indexes in PostgreSQL with real EXPLAIN ANALYZE plans: sequential scan vs index, tree height, index-only scans and what indexes cost on writes.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "index", "btree", "explain", "performance"]
cover = { image = "/images/covers/db-indexes-btree-explain.png", alt = "B-tree indexes and EXPLAIN ANALYZE", hiddenInSingle = true }
+++

Picture a "my orders" page. A customer logs in, and the page needs their 10 orders out of 200,000. The query is correct, it returns exactly 10 rows, and PostgreSQL reads the entire 26 MB table to find them. Nothing is wrong with the SQL. The database simply has no faster way to find those rows, so it checks all of them.

The usual fix is a {{< term "database-index" "database index" >}}. The best comparison is the index at the back of a book. If you want every page that mentions "transactions", you do not read the book from page one. You open the index, which is sorted alphabetically, find the word in a few seconds, and jump to the listed pages. A database index is the same thing: a separate, sorted structure that maps a column's values to the places where the rows live, so the database can skip everything else. What it costs, and when it does not help, is the second half of this post. And to see whether an index is actually working, we need to read a {{< term "query-plan" "query plan" >}}, which is PostgreSQL's own description of how it will run a query.

> Everything below ran on a real PostgreSQL 18.3 with the series' deterministic seed: 20k customers, 1k products, 200k orders and 600k order items in the shop schema from [Schema design and normalization](/posts/db-schema-design-normalization/). Before this post the only indexes were the primary keys and `customers.email`. I use `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` and show buffer counts, not milliseconds. PostgreSQL stores tables and indexes in 8 KB pages, and a "buffer" is one such page touched by the query. Page counts are the same on every machine, which is why I compare them instead of times.

## Reading a plan without an index

`EXPLAIN` shows the plan PostgreSQL chose. `EXPLAIN ANALYZE` also runs the query and adds what really happened, and `BUFFERS` adds the pages touched. (Because `ANALYZE` runs the query, be careful with statements that change data.) Here is the first query: all orders of customer 123. I set `max_parallel_workers_per_gather = 0` so the plan stays a single simple line; with parallel scans on, PostgreSQL launches two workers that split the same 3357 pages between them.

```text
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF) SELECT * FROM orders WHERE customer_id = 123;

 Seq Scan on orders  (cost=0.00..5857.00 rows=10 width=39) (actual rows=10.00 loops=1)
   Filter: (customer_id = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
 Planning:
   Buffers: shared hit=36
```

Line by line:

- `Seq Scan on orders`: the **node**, one step of the plan. A sequential scan reads the table from the first page to the last.
- `cost=0.00..5857.00`: the planner's estimate, in arbitrary units, as "cost to produce the first row .. cost to produce all rows". The units mean nothing by themselves; the planner uses them to compare alternative plans.
- `rows=10` is the estimate of how many rows come out, and `width=39` the average row size in bytes.
- `actual rows=10.00 loops=1`: what really happened. 10 rows came out, and this node ran once. When the estimate and the actual number are close, the planner understood the data.
- `Filter` and `Rows Removed by Filter: 199990`: every row was read and checked, and 199,990 of the 200,000 were thrown away. This is the waste.
- `Buffers: shared hit=3357`: 3357 pages were read, all found in PostgreSQL's cache (`hit`). The table has exactly 3357 pages (26 MB, I checked with `pg_relation_size`), so the whole table was read to return 10 rows.
- `Planning: Buffers`: pages touched while planning (mostly the system catalogs). Ignore it for now.

## Adding the index

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

The new index is 1856 kB, which is 232 pages, compared with 3357 for the table. Now the same query:

```text
 Bitmap Heap Scan on orders  (cost=4.37..42.86 rows=10 width=39) (actual rows=10.00 loops=1)
   Recheck Cond: (customer_id = 123)
   Heap Blocks: exact=10
   Buffers: shared hit=13 read=2
   ->  Bitmap Index Scan on orders_customer_id_idx  (cost=0.00..4.37 rows=10 width=0) (actual rows=10.00 loops=1)
         Index Cond: (customer_id = 123)
         Index Searches: 1
         Buffers: shared hit=3 read=2
 Planning:
   Buffers: shared hit=22
```

A plan is a tree, and the indented `->` line is a child node that feeds its parent. Read it from the inside out:

1. `Bitmap Index Scan` searches the index for `customer_id = 123` (`Index Searches: 1`) and collects the locations of the 10 matching rows into a bitmap, a list of "which table pages, which rows".
2. `Bitmap Heap Scan` takes that list and visits the table pages (the "heap" is PostgreSQL's name for the table's own storage). `Heap Blocks: exact=10` says the 10 rows were in 10 different pages, so 10 pages were read, each once, in page order. `Recheck Cond` just means the condition is checked again on the rows it fetched.

Totals: 13 pages came from cache and 2 had to be fetched (`read`: not in PostgreSQL's cache, so from the operating system or the disk; the index had just been built). About 15 pages instead of 3357, and the cost estimate dropped from 5857.00 to 42.86.

The planner chose the bitmap node because it estimated it as the cheaper one. A plain **Index Scan**, which fetches each row as soon as it finds it in the index, is the alternative. I forced it by running `SET enable_bitmapscan = off` (a switch for experiments only, not for production). It touched 15 pages and its estimated cost was 44.47, slightly above the bitmap plan's 42.86:

```text
 Index Scan using orders_customer_id_idx on orders  (cost=0.29..44.47 rows=10 width=39) (actual rows=10.00 loops=1)
   Index Cond: (customer_id = 123)
   Index Searches: 1
   Buffers: shared hit=15
```

## What a B-tree is

The default index type, and the one we just built, is a {{< term "b-tree" "B-tree" >}}. Imagine a tiny library catalogue: a top card says "A-F in drawer 1, G-M in drawer 2, ...", each drawer holds cards sorted by name, and each card points to a shelf. A B-tree is that idea made of 8 KB pages: a **root** page at the top lists ranges and points to the pages below, and the bottom pages, the **leaves**, hold the sorted keys together with pointers to the table rows. To find a key you read the root, follow one pointer, and arrive at a leaf. It is a {{< term "binary-search" "binary search" >}} where every step discards not half but nearly all of the remaining data, because each page has hundreds of children.

I can show the real numbers with the `pageinspect` extension. This query is not part of the demo files; I ran it separately on the same data:

```text
SELECT root, level FROM bt_metap('orders_customer_id_idx') \gset
SELECT :root AS root, :level AS level, type, live_items FROM bt_page_stats('orders_customer_id_idx', :root);
 root | level | type | live_items 
------+-------+------+------------
    3 |     1 | r    |        230
```

The root page (page 3) has 230 entries, one per leaf page: the whole index is 232 pages, which is 1 metadata page, 1 root and 230 leaves. (`level 1` means one level above the leaves.) A lookup reads the root, picks one of 230 children and reads that one leaf, and the leaf lists the 10 matching rows. The primary key index is bigger: 1099 pages and `level 2`, that is root, one middle level and leaves. That is why `WHERE id = 123` costs only a handful of pages:

```text
 Index Scan using orders_pkey on orders  (cost=0.42..8.44 rows=1 width=39) (actual rows=1.00 loops=1)
   Index Cond: (id = 123)
   Index Searches: 1
   Buffers: shared hit=7
```

Seven pages touched, against 3357 for the sequential scan. I did not break down exactly which seven pages they are; they cover the path from the index's entry page down to the leaf plus the table page that holds the row.

## Ranges, ordering and index-only scans

Because the keys in a B-tree are kept sorted, you get more than equality lookups. Ranges and ordering come almost free. "The 5 newest orders by id" walks the primary key index backwards from the end, and stops after 5 entries:

```text
SELECT * FROM orders ORDER BY id DESC LIMIT 5;
 Limit  (actual rows=5.00 loops=1)
   Buffers: shared hit=8
   ->  Index Scan Backward using orders_pkey on orders  (actual rows=5.00 loops=1)
```

(I trimmed the cost figures.) Compare that with the same question on `created_at`, which has no index. The database must read all 3357 pages and sort 200,000 rows to keep the top five:

```text
 Limit  (cost=8678.93..8678.94 rows=5 width=39) (actual rows=5.00 loops=1)
   Buffers: shared hit=3357
   ->  Sort  (cost=8678.93..9178.93 rows=200000 width=39) (actual rows=5.00 loops=1)
         Sort Key: created_at DESC
         Sort Method: top-N heapsort  Memory: 25kB
         ->  Seq Scan on orders  (cost=0.00..5357.00 rows=200000 width=39) (actual rows=200000.00 loops=1)
```

There is one more trick. If the query asks only for columns that are in the index, the database may not need the table at all:

```text
SELECT customer_id FROM orders WHERE customer_id BETWEEN 100 AND 110;
 Index Only Scan using orders_customer_id_idx on orders  (cost=0.29..6.46 rows=108 width=8) (actual rows=110.00 loops=1)
   Index Cond: ((customer_id >= 100) AND (customer_id <= 110))
   Heap Fetches: 0
   Buffers: shared hit=3
```

An {{< term "index-only-scan" "Index Only Scan" >}} answers from the index alone: 110 rows from 3 pages. `Heap Fetches: 0` says no table page was visited. That works only because I ran `VACUUM` first, which records in the {{< term "visibility-map" "visibility map" >}} which table pages are known to hold only rows visible to everyone. For pages not marked that way, the database must still look at the table to be sure.

## When the index is not used

Not every query can use an index. Wrap the column in an expression, and the index on the plain column becomes useless, because the index is sorted by `customer_id` and not by `customer_id + 0`:

```text
SELECT * FROM orders WHERE customer_id + 0 = 123;
 Seq Scan on orders  (cost=0.00..6357.00 rows=1000 width=39) (actual rows=10.00 loops=1)
   Filter: ((customer_id + 0) = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
```

Back to 3357 pages, even though the index exists. A condition written so that an index can serve it is called {{< term "sargable" "sargable" >}}; the fix is to write `customer_id = 123`. (Note also `rows=1000` against `actual rows=10`: the planner could not estimate an expression, so it guessed. We return to estimates in a later post.)

A second case is a column that matches a large share of the table. There is no index on `status` in this demo, so `WHERE status = 'paid'` is a `Seq Scan` regardless, and it removed 160,000 rows to return 40,000 (20% of the table). In a scratch copy of the table I added an index on `status` to see what would change. The planner then used a bitmap scan but still read 1712 buffers, about half the table, because the 40,000 matching rows are spread over 1677 of the table's 3357 pages. An index pays off when it lets you skip most of the table, and for a column with only four values it often cannot.

## What an index costs

Reads are faster, but every insert now has more work, because each index must also be updated. To measure it I made two copies of `orders` with 200k rows each, one with an extra index on `customer_id`, then inserted the same 20k new rows into both and measured how many bytes of {{< term "wal" "WAL" >}} (the write-ahead log PostgreSQL writes for every change) each insert produced:

```text
 wal_without_index | wal_with_index | bytes_a | bytes_b 
-------------------+----------------+---------+---------
 3217 kB           | 6207 kB        | 3294328 | 6356256
```

Almost double the WAL for the same rows, because each insert also writes an index entry. (In the original run the table without the extra index wrote 3278888 bytes and the one with it wrote the same 6356256; the first number moves a little from run to run.)

I also compared index sizes before and after those 20k inserts. The primary key index grew from 4408 to 4840 kB, but the `customer_id` index stayed at 1856 kB. Why did it not grow? There are two reasons, and I checked both in a scratch copy:

- B-tree pages are built only 90% full by default (`fillfactor = 90`), leaving room for new entries. An index built with `fillfactor = 100` instead doubled in the same test, from 1704 kB to 3400 kB.
- The index is small to begin with because of **deduplication**: when many rows have the same key (here each customer has about 10 orders), PostgreSQL stores the key once with a list of row locations. With `deduplicate_items = off` the same index was 4416 kB instead of 1856 kB.

## Unique indexes and unused indexes

A `UNIQUE` constraint is a B-tree that also rejects duplicates. The email on `customers` has one, which is why inserting an existing email fails:

```text
ERROR:  duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(user1@example.com) already exists.
```

Indexes you pay for but never use are pure cost. PostgreSQL keeps counters in `pg_stat_user_indexes`, and `idx_scan` says how often each index was used:

```text
  relname  |      indexrelname      | idx_scan |  size   
-----------+------------------------+----------+---------
 customers | customers_email_key    |        0 | 1376 kB
 customers | customers_pkey         |   200000 | 456 kB
 orders    | orders_customer_id_idx |        5 | 1856 kB
 orders    | orders_pkey            |   800002 | 8792 kB
 orders_b  | orders_b_customer_idx  |        0 | 1856 kB
```

(I trimmed a row. The counts are from this one demo session.) `customers_email_key` shows `idx_scan = 0` and occupies 1376 kB, but a unique index is also doing a job that is not a scan: it rejects duplicates. So an index with zero scans is a candidate for review, not an automatic drop. Check over a long period on the real system before removing anything.

## Common mistakes with EXPLAIN and indexes

- Run `EXPLAIN ANALYZE` on realistic data. On 1000 rows the planner rightly prefers a `Seq Scan`, and you learn nothing.
- `EXPLAIN ANALYZE` executes the query. For `INSERT`, `UPDATE` and `DELETE`, wrap it in a transaction that you roll back.
- A big gap between `rows` (estimate) and `actual rows` usually means stale or too-coarse statistics; running `ANALYZE` is the first thing to try.
- Every index adds write work and disk space. Index what you filter, join and sort on, not every column.
- A foreign key does not create an index on the referencing column in PostgreSQL. `orders.customer_id` had no index until I added one at the start of this post, which is exactly why the first query scanned everything.

## Exercise

1. Load the shop seed and run `EXPLAIN (ANALYZE, BUFFERS)` for `WHERE customer_id = 123`.
2. Create the index and compare `Buffers`.
3. Find a query on `order_items` that scans the whole table, and fix it.
4. Repeat the WAL experiment with two indexes.

## What's next

[Composite, partial and covering indexes](/posts/db-composite-partial-covering-indexes/). Real queries rarely filter on one column, so the next question is how to design an index for several.
