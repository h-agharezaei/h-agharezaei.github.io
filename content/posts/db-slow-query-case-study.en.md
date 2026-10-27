+++
date = '2027-03-23T10:00:00+03:30'
draft = false
title = 'Case study: finding and fixing a slow query'
description = 'A slow query case study in PostgreSQL: stale statistics, a missing composite index, a function on a column and a correlated subquery, with buffer counts.'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "slow-query", "explain", "performance", "case-study"]
cover = { image = "/images/covers/db-slow-query-case-study.png", alt = "Case study: finding and fixing a slow query", hiddenInSingle = true }
+++

In the [previous post](/posts/db-connection-pooling/) we looked at how connections fail under load. Here is the last post of the series: a slow report, fixed one step at a time with what the earlier posts taught: [B-tree indexes and EXPLAIN](/posts/db-indexes-btree-explain/), [composite indexes](/posts/db-composite-partial-covering-indexes/) and [planner statistics](/posts/db-planner-statistics/).

> Real PostgreSQL 18.3 and the shop seed, plus a "nightly import" of 40k March 2026 orders (120k items) with autovacuum off, so it is never analyzed. The machine was busy, so I show buffers (8 KB pages), not milliseconds, from `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` with parallel workers off. `pg_stat_statements` fails here ("must be loaded via shared_preload_libraries", which I cannot set in this build), so I use `EXPLAIN` only.

## The report

Revenue per customer for paid orders in one month, top 10:

```sql
SELECT c.id, date_trunc('month', o.created_at) AS month, sum(oi.qty * oi.price_cents) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'paid' AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01'
GROUP BY c.id, month ORDER BY revenue DESC LIMIT 10;
```

Result of step 0: `Buffers: shared hit=67367`. The interesting lines:

```text
Seq Scan on orders o  (cost=0.00..6857.00 rows=1 ...) (actual rows=8000.00 loops=1)
Index Scan using order_items_pkey on order_items oi  (rows=3) (actual rows=3.00 loops=8000)
```

The planner expected 1 row and got 8000, so it ran 8000 index probes on each of two tables. A gap like this means bad statistics.

## Fix 1: ANALYZE

The import added March 2026 rows beyond the last value in the {{< term "planner-statistics" "statistics" >}}, so the planner assumed almost none. One command:

```sql
ANALYZE orders; ANALYZE order_items;
```

New plan: estimate 7684 vs actual 8000, hash joins, `Buffers: shared hit=8862`. From 67367 to 8862 pages with no schema change. (The estimated cost rose from 6877 to 23887: the first plan was cheap only on paper.) Still, `orders` is read completely: 3357 pages for 8000 rows.

## Fix 2: a composite index

The filter is an equality on `status` plus a range on `created_at`, which is what a {{< term "composite-index" "composite index" >}} is for:

```sql
CREATE INDEX orders_status_created_idx ON orders (status, created_at);
```

The `orders` node became a {{< term "bitmap-scan" "bitmap scan" >}} touching 371 pages instead of 3357, and the total fell to 5876. Note what did not change: `order_items` is still a `Seq Scan` (5295 pages). That is the right choice: the report needs 8000 orders, and 8000 probes cost far more than one sequential read. Not every `Seq Scan` is a bug.

## Fix 3: a function on the column

A colleague rewrites the month filter to be "readable":

```sql
WHERE status = 'paid' AND to_char(created_at, 'YYYY-MM') = '2026-03'
```

It is no longer {{< term "sargable" "sargable" >}}: 145 pages and an estimate of 238 rows (actual 8000), against 35 pages and 7628 for the range form. The index on `status` still helped, but dates were filtered after reading (`Rows Removed by Filter: 40000`). Keep the column bare.

## Fix 4: a correlated subquery

The second report counts March paid orders per customer in one country:

```sql
SELECT c.id, c.email,
  (SELECT count(*) FROM orders o WHERE o.customer_id = c.id AND o.status = 'paid'
     AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01')
FROM customers c WHERE c.country = 'IR';
```

A {{< term "correlated-subquery" "correlated subquery" >}} runs once per customer: `loops=1666`, and each loop read the month's 8000 rows and threw most away. Total: 618293 pages. Two steps, measured separately:

```text
 CREATE INDEX orders_customer_id_idx ON orders (customer_id)   -> 23493 pages
 rewrite as LEFT JOIN ... GROUP BY c.id                        ->   578 pages
```

The {{< term "foreign-key" "foreign key" >}} column had no index. It gave a 26x drop; the join another 40x. The same shape in application code is {{< term "n-plus-one" "N+1" >}}: no single slow plan, only many fast queries. That is where `pg_stat_statements` would help; I could not run it.

## Did the fixes hurt writes?

I made two copies of `orders` (240k rows): one with only the primary key, one with the two new indexes, then inserted the same 20k rows into each and compared the {{< term "wal" "WAL" >}}:

```text
 primary key only        3287672 bytes
 + two new indexes       8080232 bytes
```

About 2.5 times the WAL for the same rows, and the copy's indexes took 13 MB against 5288 kB. That is the price; on a write-heavy table I would check before paying it.

## A few things to watch

- Compare `rows` with `actual rows` first; it points to statistics.
- Change one thing at a time and record buffers after each.
- Look for `loops=` in the thousands: that is a per-row cost.
- Measure the write side before adding an index to a busy table.

## Checklist for the next slow query

1. Get the real query and run `EXPLAIN (ANALYZE, BUFFERS)` on realistic data.
2. Estimates far from actuals? `ANALYZE`, then extended statistics if needed.
3. Large scan for few rows? Check the index for the `WHERE` columns, in order.
4. A function or cast on a column? Rewrite it.
5. High `loops`? Replace the subquery or the N+1 with a join.
6. Re-measure, then check the write cost.

## Exercise

1. Load the seed, import the extra month without `ANALYZE`, and reproduce step 0.
2. Fix it in the order above and note the buffers after each.
3. Shrink the report to one week. Does the planner now probe `order_items` by index?

## What's next

This is the last post of the Databases series. The Distributed Systems series comes later in the roadmap.
