+++
date = '2026-12-05T10:00:00+03:30'
draft = false
title = 'Composite, partial and covering indexes'
description = 'Composite, partial and covering indexes in PostgreSQL 18: column order, INCLUDE and Index Only Scan, expression indexes, with real EXPLAIN plans.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "indexes", "explain", "performance"]
cover = { image = "/images/covers/db-composite-partial-covering-indexes.png", alt = "Composite, partial and covering indexes", hiddenInSingle = true }
+++

Here are two indexes on exactly the same two columns, only in a different order. For the same query, one reads 6 pages and the other reads 25. Neither one is "wrong": both are used, both return the right answer. But one is four times more work, and on a larger table the gap grows.

In [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/) we indexed one column. Real queries rarely look at only one: "this customer's orders in this week", "new orders from the last month", "the total of one customer's orders". This post covers the tools for those cases: a {{< term "composite-index" "composite index" >}} (one index over several columns), a {{< term "partial-index" "partial index" >}} (an index over only some rows), a {{< term "covering-index" "covering index" >}} (one that can answer a query without touching the table), and an {{< term "expression-index" "expression index" >}} (an index over a computed value).

> Everything below ran on a real PostgreSQL 18.3 with the shared shop schema (200k orders, 20k customers). Plans come from `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` and are trimmed to the lines that matter. As in the previous post I show buffer counts (8 KB pages touched), not milliseconds, because they do not depend on the machine. The split between `hit` and `read` depends on what happens to be cached, so look at the total.

## Column order matters

Think of a phone book sorted by last name, then by first name. Finding "Rezaei, Sara" is quick: jump to Rezaei, then to Sara. Finding everyone called Sara is hopeless, because the Saras are scattered across the whole book. A composite index is that phone book: it is sorted by the first column, and rows with the same first value are sorted by the second, and so on. The order of columns decides which questions it can answer quickly.

Our query: one customer's orders in one week. I built the same two columns in two orders and ran the same query with each (dropping the first index before building the second):

```sql
CREATE INDEX orders_cust_created ON orders (customer_id, created_at);   -- A
CREATE INDEX orders_created_cust ON orders (created_at, customer_id);   -- B
SELECT id, total_cents FROM orders
WHERE customer_id = 42 AND created_at >= '2025-02-01' AND created_at < '2025-02-08';
```

Customer 42 has 10 orders and none of them is in that week, so the query returns no rows. That is fine for our purpose: what matters is how much of the index each version had to read to find out.

```text
A: Index Scan using orders_cust_created on orders  (cost=0.42..8.44 rows=1 ...) (actual rows=0.00 loops=1)
     Index Searches: 1
     Buffers: shared hit=3 read=3

B: Index Scan using orders_created_cust on orders  (cost=0.42..105.61 rows=1 ...) (actual rows=0.00 loops=1)
     Index Searches: 1
     Buffers: shared hit=9 read=16
```

A reads 6 pages and B reads 25 (and the planner's cost estimates, 8.44 against 105.61, agree about which is worse). The reason is in how each index is sorted. In A, all entries of customer 42 sit together, sorted by date, so the database goes straight to customer 42 and looks at the week inside that tiny group. In B, the entries are sorted by date first, so all the orders of that week (about 3500 of them) sit together, and the database must walk through all of them and check `customer_id` on each one.

The rule of thumb that follows: **put the columns you compare with equality first, and the column you compare with a range (`>=`, `<`, `BETWEEN`) last.** If the query also has an `ORDER BY`, the sorted column should come right after the equality columns. For example A also serves "the latest 3 orders of customer 42" with no sorting step at all, because one customer's entries are already in date order:

```text
SELECT id, created_at FROM orders WHERE customer_id = 42 ORDER BY created_at DESC LIMIT 3;
 Limit  (cost=0.42..13.67 rows=3 ...) (actual rows=3.00 loops=1)
   Buffers: shared hit=3 read=3
   ->  Index Scan Backward using orders_cust_created on orders  (cost=0.42..44.59 rows=10 ...) (actual rows=3.00 loops=1)
         Index Cond: (customer_id = 42)
```

`Index Scan Backward` reads the entries from the end, so the newest come first, and `Limit` stops after three. Again 6 pages.

## The leftmost prefix, and a PostgreSQL 18 surprise

The phone book also shows the limit. An index on `(a, b)` is sorted by `a` first, so a query that filters only on `b` cannot use that order to search. This is called the **leftmost prefix** rule: the index helps queries that use its first column, or its first two, and so on, but not the later columns alone. On `orders (customer_id, created_at)`, a query for one day of orders with no customer condition did a parallel `Seq Scan` over all 3357 pages:

```text
SELECT id FROM orders WHERE created_at >= '2025-02-01' AND created_at < '2025-02-02';
 Gather  ...  (actual rows=502.00 loops=1)
   ->  Parallel Seq Scan on orders  ...
         Filter: ((created_at >= ...) AND (created_at < ...))
         Rows Removed by Filter: 66499
         Buffers: shared hit=3357
```

But on `customers (country, created_at)` the same kind of query, with only a date condition, did use the index. There are only 12 countries in the data:

```text
Bitmap Heap Scan on customers  ... (actual rows=109.00 loops=1)
   ->  Bitmap Index Scan on customers_country_created  ... (actual rows=109.00 loops=1)
         Index Cond: (created_at >= ... AND created_at < ...)
         Index Searches: 18
         Buffers: shared hit=19 read=19
```

`Index Searches: 18` means the index was probed many times, not once. As far as I know this is the **skip scan** that PostgreSQL 18 added: when the first column has few distinct values, the database can hop from one value of `country` to the next and search the date range inside each. It helps only in this situation, and it is still many searches instead of one. Do not design around it: put the column you always filter on first.

## Partial index: index only the rows you ask about

Only 8% of orders are `new` (16,000 of 200,000), and a typical operational query asks about exactly those. Why index the other 92%? A partial index adds a `WHERE` to `CREATE INDEX`, and only the rows that match are stored. I built a normal and a partial index for the same purpose and compared them:

```sql
CREATE INDEX orders_status_created_full ON orders (status, created_at);
CREATE INDEX orders_created_new ON orders (created_at) WHERE status = 'new';
```

```text
orders_status_created_full   4448 kB
orders_created_new            312 kB
```

The partial index is 14 times smaller. With both present, the planner picked the partial one for `status = 'new'` plus a week of `created_at`, and the query returned 500 rows. After I dropped the full one, the plan was the same, with 436 buffers in total, of which only 3 were index pages and 433 were table pages. So the partial index did not make this query faster than the full one. What it gives is a much smaller index, which means less disk, less cache and less work on every write to the table.

The limit is that the partial index applies only when the query's `WHERE` implies the index's `WHERE`. For `status = 'paid'`, or with no status condition at all, it cannot be used, and both queries ran as a `Seq Scan` over 3357 pages.

## Covering index and the Index Only Scan surprise

Last time we saw that an {{< term "index-only-scan" "Index Only Scan" >}} answers a query from the index alone, when the query asks only for indexed columns. A **covering index** is an index designed for that. Suppose the query also needs `total_cents`. You could add it as a third key column, but then the index is sorted by it too, which you do not need. `INCLUDE` adds the column as plain payload: stored in the leaf pages, not sorted. First I ran the query with the plain two-column index, then with `INCLUDE`:

```sql
CREATE INDEX orders_cust_created_inc ON orders (customer_id, created_at) INCLUDE (total_cents);
SELECT created_at, total_cents FROM orders WHERE customer_id BETWEEN 100 AND 199;
```

```text
without INCLUDE: Bitmap Heap Scan   Heap Blocks: exact=753   Buffers: shared hit=758 read=5   (763 pages)
with INCLUDE:    Index Only Scan    Heap Fetches: 0           Buffers: shared hit=3 read=6     (9 pages)
```

Both return the 1000 rows of 100 customers. Without `INCLUDE` the database had to visit 753 table pages for the `total_cents` values; with it, 9 index pages were enough. The cost is index size: the covering index is 7944 kB.

Now the classic trap. An Index Only Scan can only skip the table for pages that the {{< term "visibility-map" "visibility map" >}} marks as all-visible. Every row in PostgreSQL carries visibility information that lives in the table, not in the index, so for pages that are not marked, the database must still go to the table to check. I updated 20% of the orders (40,000 rows) and did not vacuum:

```text
Index Only Scan using orders_cust_created_inc ...   Heap Fetches: 1200   Buffers: shared hit=1213
```

The updates cleared the all-visible bits, so the same plan now made 1200 trips to the table and touched 1213 pages instead of 9. After `VACUUM orders` (see {{< term "vacuum" "VACUUM" >}}) it was back to `Heap Fetches: 0` and 14 pages (not exactly 9 again, because the update changed both the table and the index). So an Index Only Scan on a frequently updated table depends on vacuum keeping up. And if the query asks for a column that is not in the index, such as `status`, the plan turns back into a Bitmap Heap Scan (801 buffers in my run).

## Expression index and non-sargable conditions

Remember {{< term "sargable" "sargable" >}} conditions from the last post: a condition the planner can turn into an index search. Wrapping the column in a function breaks that. The email column has a unique index, but compare:

```text
WHERE email = 'user777@example.com'          -> Index Scan (unique index), 3 pages
WHERE lower(email) = 'user777@example.com'   -> Seq Scan, Rows Removed by Filter: 19999, 207 pages
```

The index is sorted by `email`, not by `lower(email)`, so it cannot help. If you really need case-insensitive lookups, give the database an index of the expression itself:

```sql
CREATE INDEX customers_email_lower ON customers (lower(email));
```

The same query then used it (`Index Scan using customers_email_lower`, 3 pages). The query must use exactly the same expression as the index; `lower(email)` matches, `upper(email)` does not.

## Two single-column indexes or one composite?

If you have separate indexes on `status` and `customer_id`, PostgreSQL can still combine them. It builds a bitmap from each index and keeps the rows that are in both, a {{< term "bitmap-scan" "BitmapAnd" >}}:

```text
SELECT id FROM orders WHERE customer_id BETWEEN 1 AND 1500 AND status = 'new';

Bitmap Heap Scan on orders  (actual rows=1200.00 loops=1)   Heap Blocks: exact=878
  ->  BitmapAnd
        ->  Bitmap Index Scan on orders_status_idx   (actual rows=16000.00 loops=1)
        ->  Bitmap Index Scan on orders_cust_idx     (actual rows=15000.00 loops=1)
```

Each index returns thousands of rows (16,000 and 15,000), but only 1200 are in both. The two index scans touched 37 index pages in total. A single composite `(customer_id, status)` returned the same 1200 rows with 23 index pages and the same 878 table pages, a small gain.

But this query has an equality on `status` and a range on `customer_id`, so by our rule the order should be `(status, customer_id)`. I tried that in a scratch copy of the demo (this variant is not in the demo files): same rows, same 878 table pages, and only 7 index pages (3 hit and 4 read), against 23. The rule worked.

## Every index has a price

Final sizes from `pg_stat_user_indexes` at the end of the demo: `orders_pkey` 8792 kB, `orders_cust_status` 2016 kB, `orders_cust_idx` 1856 kB and `orders_status_idx` 1368 kB, next to a 26 MB table. Each of these is written to on every insert and update. And one of them is now redundant: `orders_cust_idx` is covered by `(customer_id, status)`, which serves `customer_id` queries too, so you could drop it.

## Rules and traps for multi-column indexes

- Equality columns first, range column last. Put the `ORDER BY` column right after the equality ones.
- A partial index is tiny, but only queries whose `WHERE` implies its predicate can use it.
- `INCLUDE` columns are payload only. After heavy updates, check `Heap Fetches` in `EXPLAIN` and make sure vacuum keeps up.
- Do not wrap indexed columns in functions. Create an expression index, or rewrite the condition.
- My own checklist: list the real queries, build a composite for the most frequent, consider a partial index for skewed columns, and drop indexes nobody uses.

## Exercise

Take your slowest query with two filters. Create both column orders, compare `Buffers`, drop the loser, then look for indexes with zero `idx_scan` in `pg_stat_user_indexes`.

## What's next

[The planner and statistics: why an index is not used](/posts/db-planner-statistics/). Sometimes the right index exists and PostgreSQL ignores it anyway, so the next post looks at how the planner decides.
