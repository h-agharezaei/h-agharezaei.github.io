+++
date = '2026-12-09T10:00:00+03:30'
draft = false
title = 'The planner and statistics: why an index is not used'
description = 'PostgreSQL planner statistics explained with real EXPLAIN runs: why an index is skipped, stale ANALYZE, casts, functions, LIKE, OR and extended statistics.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "planner", "statistics", "explain"]
cover = { image = "/images/covers/db-planner-statistics.png", alt = "The planner and statistics: why an index is not used", hiddenInSingle = true }
+++

You created an index, ran the query, and `EXPLAIN` shows a `Seq Scan`. Usually the {{< term "query-planner" "planner" >}} is right; sometimes it works from bad numbers. In the [previous post](/posts/db-composite-partial-covering-indexes/) we designed indexes; this one is about the other half: how the planner decides to use them.

> Everything ran on a real PostgreSQL 18.3 with the shared `shop` schema (200k orders, 600k items). Plans are trimmed, there are no milliseconds, and sampled `rows=` estimates can differ a little between runs.

## The planner works from numbers

The planner estimates how many rows each step returns, prices every plan with a cost model, and picks the cheapest. The inputs are {{< term "planner-statistics" "statistics" >}} that `ANALYZE` gathers into `pg_stats`. In any plan, compare estimated `rows=` with `actual rows=`: a big gap means a bad plan is likely.

## Low selectivity: the Seq Scan is correct

I indexed `orders (status)`. 70% of the rows are `shipped`:

```text
SELECT * FROM orders WHERE status = 'shipped';
 Seq Scan on orders  (cost=0.00..5857.00 rows=140407) (actual rows=140000.00)
   Buffers: shared hit=3357

SELECT * FROM orders WHERE status = 'cancelled';   -- 2% of rows
 Bitmap Heap Scan on orders  (cost=46.98..3623.15 rows=3960) (actual rows=4000.00)
   ->  Bitmap Index Scan on orders_status_idx
```

The estimates are close. A query returning 70% of the table has low {{< term "selectivity" "selectivity" >}}: the index adds work to a read that touches almost every page anyway. For the rare value the index wins.

To see the alternative, use `SET enable_seqscan = off` **only as a diagnostic**:

```text
Bitmap Heap Scan ... (cost=1572.45..6684.54 rows=140407)   Buffers: shared hit=1797
```

Its estimated cost, 6684, is higher than the Seq Scan's 5857, so the planner skipped it. Honestly, on this fully cached demo it touched fewer buffers (1797 vs 3357) and I did not time either, so I cannot claim it is slower here. The cost model also uses `random_page_cost` (4 by default, 1 for sequential pages); I do not tune it. Never ship `enable_seqscan = off`.

## Tiny tables

```text
SELECT * FROM tiny WHERE id = 7;     -- 50 rows, primary key exists
 Seq Scan on tiny  (cost=0.00..1.62 rows=1)   Buffers: shared hit=1
```

One page: cheaper to read than to walk an index.

## Missing or stale statistics

I created `events` with 100k rows (100 of them `rare`), an index on `kind`, autovacuum off, and loaded it **without** `ANALYZE`:

```text
n_live_tup = 0, last_analyze = NULL, reltuples = -1

SELECT * FROM events WHERE kind = 'common';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258) (actual rows=99900.00)
```

Estimate 258, actual 99900: the planner knew nothing and guessed. After `ANALYZE events`:

```text
 Seq Scan on events  (cost=0.00..1887.00 rows=99927) (actual rows=99900.00)
 -- and for kind = 'rare':
 Index Scan using events_kind_idx  (cost=0.29..10.22 rows=73) (actual rows=100.00)
```

The plan flipped to the right one for each value. Autovacuum normally analyzes for you; after a big bulk load, run `ANALYZE` yourself.

## Reading pg_stats

```text
status:  n_distinct = 4, most_common_vals = {shipped,paid,new,cancelled},
         most_common_freqs = {0.702,0.199,0.079,0.0198}
customer_id: n_distinct = 19893, correlation = 0.0006
```

`n_distinct` and the most-common-values list drive equality estimates, `histogram_bounds` drives ranges, and `correlation` (how well physical order matches value order) affects how cheap an index scan looks.

`default_statistics_target` (100) sets how many MCV entries and histogram buckets are kept. I made a table `hot` with 300 values of 200 rows each, plus unique noise, and asked for `v = 250` (real: 200 rows):

```text
STATISTICS 100:   Index Only Scan using hot_v_idx  rows=5
STATISTICS 1000:  Index Only Scan using hot_v_idx  rows=200
```

With 100 slots, 250 missed the MCV list and got an average guess. With 1000 the estimate is exact. Raise it per column with `ALTER TABLE ... SET STATISTICS`, not globally.

## Things that defeat an index

- **Type cast on the column.** `customer_id = 42` used the index. `customer_id = 42::numeric` gave a `Parallel Seq Scan` with `Filter: ((customer_id)::numeric = '42'::numeric)`, because the column, not the constant, was cast. `customer_id::text = '42'` did the same.
- **Function on the column.** `lower(email) = '...'` was a Seq Scan (estimate 100, actual 1). An index on `lower(email)` fixed it. A condition the index can use is called {{< term "sargable" "sargable" >}}.
- **Leading wildcard.** With a `text_pattern_ops` index, `LIKE 'Customer 4242%'` used an Index Scan; `LIKE '%4242'` was a Seq Scan.
- **OR.** `customer_id = 42 OR status = 'cancelled'` with both indexed used a `BitmapOr`. With `total_cents`, which has no index, it fell back to a Parallel Seq Scan: one unindexed branch is enough.

## Correlated columns: extended statistics

The planner assumes columns are independent. I made `customers_geo` with `country` and a derived `region` (`DE` is always `EU`). For `country = 'DE' AND region = 'EU'` (real: 1666):

```text
before: rows=694
CREATE STATISTICS geo_dep (dependencies) ON country, region FROM customers_geo;  ANALYZE ...
after:  rows=1666
```

694 is 1/12 times 5/12 of 20000. The plan did not change on a table this small; on a join the better estimate could.

## Troubleshooting checklist

1. `EXPLAIN (ANALYZE, BUFFERS)`: compare estimated and actual rows at each node.
2. Big gap: `ANALYZE` the table; check `last_analyze` in `pg_stat_user_tables`.
3. Still off: read `pg_stats`; consider a higher per-column target or `CREATE STATISTICS`.
4. Estimates fine but no index: check selectivity, casts, functions, wildcards.
5. Only then, `enable_seqscan = off` in a session to compare.

## A few things to watch

- A Seq Scan is not a bug; judge by estimate versus actual.
- Cast the parameter, never the column.
- `SET enable_*` is for diagnosis only.
- I did not test huge tables or `random_page_cost` tuning.

## Exercise

Load 200k rows where 99% of one indexed column is `'a'`, without `ANALYZE`. Compare plans for `'a'` and a rare value before and after `ANALYZE`.

## What's next

Next in the series: Transactions and ACID.
