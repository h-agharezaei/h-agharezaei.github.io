+++
date = '2026-12-05T10:00:00+03:30'
draft = false
title = 'Composite, partial and covering indexes'
description = 'Composite, partial and covering indexes in PostgreSQL 18: column order, INCLUDE and Index Only Scan, expression indexes, with real EXPLAIN plans.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "indexes", "explain", "performance"]
cover = { image = "/images/covers/db-composite-partial-covering-indexes.png", alt = "Composite, partial and covering indexes", hiddenInSingle = true }
+++

In the [previous post](/posts/db-indexes-btree-explain/) we added single-column indexes and read their plans with `EXPLAIN ANALYZE`. Real queries rarely filter on one column. Next tools: a {{< term "composite-index" "composite index" >}}, a {{< term "partial-index" "partial index" >}}, a {{< term "covering-index" "covering index" >}} and an {{< term "expression-index" "expression index" >}}.

> Everything ran on a real PostgreSQL 18.3 with the shared shop schema (200k orders, 20k customers). Plans come from `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)`, trimmed to the lines that matter. I show buffer counts, not milliseconds, because they do not depend on the machine.

## Column order matters

The query: one customer's orders in one week. Same two columns, two orders:

```sql
CREATE INDEX orders_cust_created ON orders (customer_id, created_at);   -- A
CREATE INDEX orders_created_cust ON orders (created_at, customer_id);   -- B
SELECT id, total_cents FROM orders
WHERE customer_id = 42 AND created_at >= '2025-02-01' AND created_at < '2025-02-08';
```

```text
A: Index Scan using orders_cust_created   Buffers: shared hit=3 read=3     (6 pages)
B: Index Scan using orders_created_cust   Buffers: shared hit=9 read=16    (25 pages)
```

Both work, but B walks every index entry of the week (about 3500 orders) and checks `customer_id` inside it, while A jumps straight to customer 42. Rule of thumb: **equality columns first, the range column last**. A also serves `WHERE customer_id = 42 ORDER BY created_at DESC LIMIT 3` with no Sort node (`Index Scan Backward`, 6 pages), because one customer's entries are already sorted by date.

## The leftmost prefix, and a PostgreSQL 18 surprise

An index on `(a, b)` is sorted by `a` first, so a query on `b` alone cannot search it. On `orders (customer_id, created_at)`, filtering on one day gave a parallel `Seq Scan` over 3357 pages.

But on `customers (country, created_at)` (12 countries) the same kind of query used the index:

```text
Bitmap Index Scan on customers_country_created
  Index Cond: (created_at >= ... AND created_at < ...)
  Index Searches: 18
```

`Index Searches: 18` means many probes instead of one. As far as I know this is the skip scan added in PostgreSQL 18; it helps only when the first column has few distinct values. Do not design around it: put the column you always filter on first.

## Partial index: index only the rows you ask about

Only 8% of orders are `new`, and the important queries ask about them:

```sql
CREATE INDEX orders_status_created_full ON orders (status, created_at);
CREATE INDEX orders_created_new ON orders (created_at) WHERE status = 'new';
```

```text
orders_status_created_full   4448 kB
orders_created_new            312 kB
```

With both present, the planner picked the partial one for `status = 'new'` plus a week of `created_at`. The limit: for `status = 'paid'`, or with no status condition, it cannot be used, and both ran as a `Seq Scan` (3357 pages). The query's `WHERE` must imply the index's `WHERE`.

## Covering index and the Index Only Scan surprise

An {{< term "index-only-scan" "Index Only Scan" >}} answers a query from the index alone. Add the extra column with `INCLUDE` (it is stored but not sorted):

```sql
CREATE INDEX orders_cust_created_inc ON orders (customer_id, created_at) INCLUDE (total_cents);
SELECT created_at, total_cents FROM orders WHERE customer_id BETWEEN 100 AND 199;
```

```text
without INCLUDE: Bitmap Heap Scan        Buffers: 763 pages
with INCLUDE:    Index Only Scan         Heap Fetches: 0     Buffers: 9 pages
```

Now the classic trap. I updated 20% of the orders and did not vacuum:

```text
Index Only Scan ...   Heap Fetches: 1200   Buffers: shared hit=1213
```

Same node, but 1213 pages. The index cannot tell whether a row is visible to us; the {{< term "visibility-map" "visibility map" >}} says which heap pages are all-visible, and the update cleared those bits. After `VACUUM orders` (see {{< term "vacuum" "VACUUM" >}}) it was `Heap Fetches: 0` and 14 pages. So an Index Only Scan on a frequently updated table depends on vacuum keeping up. Selecting `status`, which is not in the index, turned it back into a Bitmap Heap Scan.

## Expression index and non-sargable conditions

A condition is {{< term "sargable" "sargable" >}} when the planner can turn it into an index search. Wrapping the column in a function breaks that:

```text
WHERE email = 'user777@example.com'          -> Index Scan (unique index)
WHERE lower(email) = 'user777@example.com'   -> Seq Scan, Rows Removed by Filter: 19999, 207 pages
```

The fix is an expression index: `CREATE INDEX customers_email_lower ON customers (lower(email))`. The same query then used it (`Index Scan`, 3 pages). The query must use the exact same expression.

## Two single indexes or one composite?

With separate indexes on `status` and `customer_id`, PostgreSQL combines them with a {{< term "bitmap-scan" "BitmapAnd" >}}:

```text
BitmapAnd -> Bitmap Index Scan on orders_status_idx   (16000 rows)
          -> Bitmap Index Scan on orders_cust_idx     (15000 rows)
Result: 1200 rows, index buffers 37
```

One composite `(customer_id, status)` returned the same rows with 23 index buffers and the same 878 heap pages. A small gain here.

## Every index has a price

Sizes from `pg_stat_user_indexes` at the end: `orders_pkey` 8792 kB, `orders_cust_status` 2016 kB, `orders_cust_idx` 1856 kB, `orders_status_idx` 1368 kB. Each is written on every insert and update. `orders_cust_idx` is now redundant, since `(customer_id, status)` serves `customer_id` queries too.

## A few things to watch

- Equality columns first, range column last; put the `ORDER BY` column right after the equality ones.
- A partial index is tiny, but only queries whose `WHERE` implies its predicate can use it.
- `INCLUDE` columns are payload only; check `Heap Fetches` in `EXPLAIN` and keep vacuum healthy.
- Do not wrap indexed columns in functions; create an expression index or rewrite the condition.
- My own checklist: list the real queries, build a composite for the most frequent, consider partial for skewed columns, drop unused indexes.

## Exercise

Take your slowest query with two filters. Create both column orders, compare `Buffers`, drop the loser, then look for indexes with zero `idx_scan` in `pg_stat_user_indexes`.

## What's next

Sometimes the right index exists and PostgreSQL still ignores it. Next: "The planner and statistics: why an index is not used".
