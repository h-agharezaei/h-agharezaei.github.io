+++
date = '2027-03-23T10:00:00+03:30'
draft = false
title = 'Case study: finding and fixing a slow query'
description = 'A slow query case study in PostgreSQL: stale statistics, a missing composite index, a function on a column and a correlated subquery, with buffer counts.'
contentType = 'engineering'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "slow-query", "explain", "performance", "case-study"]
cover = { image = "/images/covers/db-slow-query-case-study.png", alt = "Case study: finding and fixing a slow query", hiddenInSingle = true }
+++

Somebody tells you: "the monthly revenue report has become very slow." That is all you get. No plan, no culprit, no hint about which part is slow. This post is that situation, told as an investigation: one report query, four fixes, and for each fix what I looked at, what it told me and what changed. Nothing here is new theory; it is the earlier posts of this series put to work on one problem: [B-tree indexes and EXPLAIN](/posts/db-indexes-btree-explain/), [composite indexes](/posts/db-composite-partial-covering-indexes/) and [planner statistics](/posts/db-planner-statistics/). It comes after [Connection pooling and its failure modes](/posts/db-connection-pooling/) and it is the last post of the series.

> Everything ran on a real PostgreSQL 18.3 (I re-ran the whole case study for this version of the post) with the shop seed (200,000 orders, 600,000 order items), plus a "nightly import" of 40,000 March 2026 orders and 120,000 items. For the import I switched autovacuum off on those two tables, so nothing analyzes the new rows until I do it myself. A real system has this window too: between a big import and the next automatic analyze. The machine was busy, so I show buffers (one buffer is one 8 kB page that the query touched), not milliseconds, from `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` with parallel workers off. Buffer counts are exact and repeat from run to run; row estimates come from a random sample, so they can differ slightly between runs, and I point out where they did.

## The report

The report is the revenue per customer for paid orders in one month, top 10:

```sql
SELECT c.id, date_trunc('month', o.created_at) AS month, sum(oi.qty * oi.price_cents) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'paid' AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01'
GROUP BY c.id, month ORDER BY revenue DESC LIMIT 10;
```

The first move is always the same: run it under `EXPLAIN (ANALYZE, BUFFERS)` and read the plan before touching anything. The top line says `Buffers: shared hit=67367`: this one query touched 67,367 pages (some of them the same page many times over; at 8 kB each that is about 526 MB of page accesses) to return ten rows. The lines that matter:

```text
Seq Scan on orders o  (cost=0.00..6857.00 rows=1 ...) (actual rows=8000.00 loops=1)
Index Scan using order_items_pkey on order_items oi  (rows=3) (actual rows=3.00 loops=8000)
```

Two things to read here. First, `rows=1` against `actual rows=8000`: the planner expected one March order and found 8,000. Second, `loops=8000`: the planner thought one order meant a cheap nested loop, so for each of those 8,000 orders it went and probed `order_items` through its primary key, and (not shown above) `customers` through its primary key, 8,000 times each. The buffers add up: 3,357 for the scan of `orders`, 16,001 for the 8,000 `customers` probes and 48,000 for the 8,000 `order_items` probes make 67,358 of the 67,367. A gap between estimate and actual of this size is a sign of bad statistics, before anything else.

## Fix 1: ANALYZE

Why would the planner expect one row? It does not look at the table to plan; it uses {{< term "planner-statistics" "statistics" >}}, a summary of the column values collected earlier by `ANALYZE`. Those statistics were collected before the import, so the most recent `created_at` they know is early February 2026. The query asks for March, beyond everything the planner has ever seen, so it assumed almost no rows match. The fix is one command:

```sql
ANALYZE orders; ANALYZE order_items;
```

The new plan estimates about 7,500 rows against 8,000 actual (7,549 in this run; the sample makes it a little different each time), switches to hash joins and reads `Buffers: shared hit=8862`. From 67,367 pages to 8,862, with no change to the schema or to the query. The estimated cost went from 6,877 to about 23,900: the first plan only looked cheap on paper, because it was built on a wrong row count. Look at what the 8,862 are made of: 5,295 for `order_items`, 3,357 for `orders` and 207 for `customers`. The report still reads all of `orders` for 8,000 rows.

## Fix 2: a composite index

That last observation points to the next step. The filter has an equality on `status` and a range on `created_at`, and that is exactly the shape of a {{< term "composite-index" "composite index" >}}: equality column first, range column second.

```sql
CREATE INDEX orders_status_created_idx ON orders (status, created_at);
```

Now the planner reads `orders` with a {{< term "bitmap-scan" "bitmap scan" >}}: it first collects, from the index, which table pages hold matching rows, then visits just those pages. That touches 371 pages (337 hits and 34 reads) instead of 3,357, and the total fell to 5,876. Note what did not change: `order_items` is still read with a `Seq Scan` (5,295 pages). This is the right choice and not a leftover problem: the report needs 8,000 orders and about 24,000 of their items, and 8,000 index probes cost far more than reading the table once from start to end. Not every `Seq Scan` is a bug.

## Fix 3: a function on the column

Here is a mistake that is easy to make while "improving" a query. A colleague rewrites the month filter to be more readable:

```sql
WHERE status = 'paid' AND to_char(created_at, 'YYYY-MM') = '2026-03'
```

It looks nicer, and it is no longer {{< term "sargable" "sargable" >}}: the index cannot be used for a condition on `to_char(created_at, ...)`, because the index stores `created_at`, not its text form. I compared it with the range form on the count of March paid orders. I ran `VACUUM` on `orders` first, so that PostgreSQL can answer from the index alone (an index-only scan; without it each of the 8,000 matches must also be checked in the table, and both queries read about 7,000 pages here, which hid the difference):

```text
to_char(...) form:  Buffers: shared hit=145   estimate 241 rows   Rows Removed by Filter: 40000
range form:         Buffers: shared hit=35    estimate 7709 rows
```

The estimate with the function is 241 rows against an actual 8,000, and the planner has no statistics for the expression, so it guesses. The `status` part of the index was still used, but the dates were filtered after reading the index entries: 40,000 rows removed by the filter, and 145 pages instead of 35. The lesson: keep the column bare, and put the computation on the constant side.

## Fix 4: a correlated subquery

The second report, for another team, counts March paid orders for each customer in one country:

```sql
SELECT c.id, c.email,
  (SELECT count(*) FROM orders o WHERE o.customer_id = c.id AND o.status = 'paid'
     AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01')
FROM customers c WHERE c.country = 'IR';
```

A {{< term "correlated-subquery" "correlated subquery" >}} is a subquery that refers to the outer row (`c.id` here), so it has to run once per outer row. The plan shows `loops=1666`: one subquery run per customer in that country. Each run read the month's 8,000 rows through the composite index and threw nearly all of them away (`Rows Removed by Filter: 8000`), so the total came to 618,293 pages. Two steps, measured separately:

```text
 CREATE INDEX orders_customer_id_idx ON orders (customer_id)   -> 23493 pages
 rewrite as LEFT JOIN ... GROUP BY c.id                        ->   578 pages
```

The first step is an index on the {{< term "foreign-key" "foreign key" >}} column `customer_id`, which had none. Now each subquery run finds that customer's rows (about 12) directly: a 26 times drop. The second step rewrites the query as a `LEFT JOIN` with `GROUP BY`, which lets the planner read the month's orders once and join them with the customers in one pass: another 40 times. Notice that the final plan does not even use the new `customer_id` index; it uses the composite index from fix 2. The index mattered for the intermediate form, and the rewrite did the rest.

## Finding the query in the first place

In this story somebody handed me the slow query. In real life nobody does, and the extension `pg_stat_statements` is what finds it: it records, for each distinct query, how often it ran and how many buffers it touched in total. It needs `shared_preload_libraries = 'pg_stat_statements'` and a server restart, which I could set on my own instance. To see how it describes the shapes in this post, I ran, in the final state of the case study, the report once and the per-customer count as a loop of 1,666 separate prepared statements (what application code does when it queries inside a loop):

```text
                           query                            | calls | rows | total_blocks | blocks_per_call
 PREPARE paid_count(int) AS SELECT count(*) FROM orders o W |  1666 | 1666 |        23289 |              14
 SELECT c.id, date_trunc($1, o.created_at) AS month, sum(oi |     1 |   10 |         5876 |            5876
```

The loop looks harmless per call: 14 blocks each, nothing a slow-query log would ever flag. Yet in total it touched four times the buffers of the report that had worried everybody. This is the {{< term "n-plus-one" "N+1" >}} pattern: no single slow plan, only many fast queries. A log of slow queries by duration is unlikely to flag it; sorting by total work shows it at once. The numbers `total_blocks` and `calls` are exact; the split between hits and reads depends on what was cached. (An earlier version of this post said `pg_stat_statements` could not be used here. It can, if you start your own instance with the library preloaded.)

## Did the fixes hurt writes?

Every index must be updated on every insert. So before declaring victory I measured the write side. I made two copies of `orders` (240,000 rows): one with only a primary key, one with the primary key plus the two new indexes. Then I inserted the same 20,000 rows into each and compared how much {{< term "wal" "WAL" >}} (the write-ahead log) each insert produced:

```text
 primary key only        3287696 bytes
 + two new indexes       8080248 bytes
```

About 2.5 times the WAL for the same rows, and the indexes of the copy took 13 MB against 5,288 kB. That is the price of the fixes. The WAL byte counts repeat almost exactly, not to the last digit (they differ by a few dozen bytes from an earlier run of mine). On a write-heavy table I would measure this before paying it; on this table, a monthly report that went from 67,367 pages to 5,876 is a good trade.

## Lessons from this case

- **Compare `rows` with `actual rows` first.** A big gap points at statistics, and `ANALYZE` is the cheapest fix there is.
- **Change one thing at a time and record the buffers after each.** That is how you know which step did the work, and the table above is only possible because each fix was measured alone.
- **Look for `loops=` in the thousands.** That is a cost paid per row.
- **Do not treat every `Seq Scan` as a bug.** If the query needs a large part of the table, reading it once is the cheapest plan.
- **Measure the write side before adding an index to a busy table.**

## Checklist for the next slow query

1. Get the real query (from `pg_stat_statements` or the logs) and run `EXPLAIN (ANALYZE, BUFFERS)` on realistic data.
2. Estimates far from actuals? `ANALYZE`, then extended statistics if needed.
3. Large scan for few rows? Check the index for the `WHERE` columns, in order.
4. A function or cast on a column? Rewrite it.
5. High `loops`? Replace the subquery or the N+1 with a join.
6. Re-measure, then check the write cost.

## What's next

This is the last post of the Databases series. The Distributed Systems series comes later in the roadmap.
