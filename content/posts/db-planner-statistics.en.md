+++
date = '2026-12-09T10:00:00+03:30'
draft = false
title = 'The planner and statistics: why an index is not used'
description = 'PostgreSQL planner statistics explained with real EXPLAIN runs: why an index is skipped, stale ANALYZE, casts, functions, LIKE, OR and extended statistics.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "planner", "statistics", "explain"]
cover = { image = "/images/covers/db-planner-statistics.png", alt = "The planner and statistics: why an index is not used", hiddenInSingle = true }
+++

You created an index, ran the query, and `EXPLAIN` shows a `Seq Scan`. The index is right there, and PostgreSQL walks past it. Is that a bug? Most of the time it is not: the {{< term "query-planner" "query planner" >}}, the part of PostgreSQL that chooses how to run a query, is simply right, and the index would have been slower. Sometimes, though, the planner makes a bad choice because it works from wrong numbers. The skill is telling these two cases apart.

In the [previous post](/posts/db-composite-partial-covering-indexes/) we designed indexes. This post is about the other half: how the planner decides whether to use them, and what to check when it seems to decide badly.

> Everything below ran on a real PostgreSQL 18.3 with the shared `shop` schema (200k orders, 600k items). Plans are trimmed to the lines that matter and I show buffer counts, not milliseconds. The `rows=` estimates come from a random sample, so they can differ a little between runs (for the same query I saw 139567 in this run and 140407 in an earlier one).

## How the planner decides

The planner does not run your query to find out how long it will take. It estimates. For every possible plan it guesses how many rows each step will return, turns that into a **cost** with a simple formula, and picks the plan with the lowest cost. The numbers it works from are the table's {{< term "planner-statistics" "statistics" >}}: row counts, how many distinct values a column has, which values are most common. The command `ANALYZE` collects them into the `pg_stats` view.

You can even check the formula. For the plain sequential scan of `orders` the plan said `cost=0.00..5857.00`. The table has 3357 pages and 200,000 rows, and PostgreSQL's default costs are 1.0 per page read sequentially (`seq_page_cost`), 0.01 per row processed (`cpu_tuple_cost`) and 0.0025 per condition checked on a row (`cpu_operator_cost`):

```text
3357 pages x 1.0  +  200000 rows x 0.01  +  200000 rows x 0.0025  =  3357 + 2000 + 500  =  5857
```

That is exactly the number in the plan. (I did this arithmetic from the defaults, which I confirmed with `SHOW`, and the plan agrees.) The planner is not mysterious; it just adds up estimates. And that gives us the most useful habit of the post: **in every plan, compare the estimated `rows=` with the `actual rows=`.** If they are close, the planner understood your data, and its choice is probably sensible. If they are far apart, the plan is probably built on a wrong guess.

## Low selectivity: the Seq Scan is correct

I created three indexes on `orders` (`status`, `customer_id`, `created_at`) and ran `ANALYZE`. The `status` column has only four values, and one of them dominates:

```text
SELECT status, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC;
  status   | count  
-----------+--------
 shipped   | 140000
 paid      |  40000
 new       |  16000
 cancelled |   4000
```

Now two queries on that indexed column:

```text
SELECT * FROM orders WHERE status = 'shipped';
 Seq Scan on orders  (cost=0.00..5857.00 rows=139567 width=39) (actual rows=140000.00 loops=1)
   Filter: (status = 'shipped'::text)
   Rows Removed by Filter: 60000
   Buffers: shared hit=3357

SELECT * FROM orders WHERE status = 'cancelled';
 Bitmap Heap Scan on orders  (cost=46.57..3619.31 rows=3907 width=39) (actual rows=4000.00 loops=1)
   Recheck Cond: (status = 'cancelled'::text)
   Heap Blocks: exact=1529
   Buffers: shared hit=1534
   ->  Bitmap Index Scan on orders_status_idx  (cost=0.00..45.60 rows=3907 width=0) (actual rows=4000.00 loops=1)
         Index Cond: (status = 'cancelled'::text)
```

Look at the estimates: 139567 against 140000, and 3907 against 4000. The planner knew its data well. For `shipped` it chose a plain scan, because the query returns 70% of the table. A query that returns most rows has low {{< term "selectivity" "selectivity" >}}: the condition does not narrow anything down, so an index only adds work on top of a read that touches nearly every page anyway. For the rare value `cancelled` (2%) the index is used, and it does win, though less than you might expect: 1534 pages instead of 3357, because the cancelled orders are spread over almost half of the table's pages.

To see the alternative the planner rejected, I turned off sequential scans with `SET enable_seqscan = off`. This is a **diagnostic only**; it does not forbid the plan, it just makes it extremely expensive, so the planner shows you its second choice:

```text
 Bitmap Heap Scan on orders  (cost=1561.94..6663.53 rows=139567 ...) (actual rows=140000.00 ...)
   Heap Blocks: exact=1677
   Buffers: shared hit=1797
```

Its estimated cost, 6663.53, is higher than the Seq Scan's 5857.00, so the planner skipped it. Note that on this fully cached demo it touched fewer buffers (1797 against 3357), and I did not time either plan, so I cannot say it is slower here. The planner's model charges non-sequential page reads more than sequential ones (`random_page_cost` is 4 by default, `seq_page_cost` is 1), which is a reasonable assumption for a cold disk and may not match your hardware. Forcing a plain Index Scan, with bitmap scans off as well, gave an even higher estimated cost, 13181.88, with the same 1797 buffers. Never ship `enable_seqscan = off`; use it in a session to compare, then reset it.

## Tiny tables

The same logic explains this, which surprises people:

```text
SELECT * FROM tiny WHERE id = 7;     -- 50 rows, primary key exists
 Seq Scan on tiny  (cost=0.00..1.62 rows=1 width=7) (actual rows=1.00 loops=1)
   Filter: (id = 7)
   Rows Removed by Filter: 49
   Buffers: shared hit=1
```

The whole table fits in one page. Reading that one page is cheaper than walking an index to find the same page. The planner is right again.

## Missing or stale statistics

Now the case where the planner is wrong. I created a table `events` with 100,000 rows, 100 of them with `kind = 'rare'` and the rest `'common'`, an index on `kind`, and turned autovacuum off for the table (normally {{< term "autovacuum" "autovacuum" >}} runs `ANALYZE` in the background). Then I loaded the rows and did not run `ANALYZE`, as happens right after a big bulk load:

```text
SELECT relname, n_live_tup, last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE relname='events';
 relname | n_live_tup | last_analyze | last_autoanalyze 
---------+------------+--------------+------------------
 events  |          0 |              | 

SELECT reltuples, relpages FROM pg_class WHERE relname='events';
 reltuples | relpages 
-----------+----------
        -1 |        0
```

The planner knows nothing about this table (`reltuples = -1` means "never analyzed"). Look at what it did with two very different values:

```text
SELECT * FROM events WHERE kind = 'common';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258 ...) (actual rows=99900.00 ...)
   Buffers: shared hit=716

SELECT * FROM events WHERE kind = 'rare';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258 ...) (actual rows=100.00 ...)
   Buffers: shared hit=102
```

The estimate is 258 for both, whether the real answer is 99,900 or 100. That is a default guess, not knowledge. After `ANALYZE events`:

```text
SELECT * FROM events WHERE kind = 'common';
 Seq Scan on events  (cost=0.00..1887.00 rows=99923 ...) (actual rows=99900.00 ...)
   Buffers: shared hit=637

SELECT * FROM events WHERE kind = 'rare';
 Index Scan using events_kind_idx on events  (cost=0.29..10.52 rows=77 ...) (actual rows=100.00 ...)
   Buffers: shared hit=102
```

The estimates are now close (99,923 against 99,900, and 77 against 100), and each value gets the plan it deserves: a sequential scan for the 99.9% value (637 pages instead of 716) and an index scan for the rare one. Autovacuum normally analyzes for you, but after a large bulk load or a big data change, run `ANALYZE` yourself.

## Reading pg_stats

What does `ANALYZE` actually store? You can read it in `pg_stats`. For `orders` (psql in expanded mode):

```text
attname           | status
n_distinct        | 4
most_common_vals  | {shipped,paid,new,cancelled}
most_common_freqs | {0.69783336,0.2002,0.082433335,0.019533332}
correlation       | 0.5347375

attname           | customer_id
n_distinct        | -0.10015
most_common_vals  | {1003,1300,11968}
most_common_freqs | {0.00023333334,0.00023333334,0.00023333334}
correlation       | -0.004848448
```

How to read it:

- `n_distinct` is the number of different values. A positive number is a count (`status` has 4). A negative number means "this fraction of the table's rows": `-0.10015` means about 10% of 200,000 rows, roughly 20,000 customers (the real count is exactly 20,000; the stored value is an estimate from a sample).
- `most_common_vals` and `most_common_freqs` list the most frequent values and the fraction of rows each takes. For `status` this is exactly what we saw: `shipped` is about 70%. This list is what lets the planner estimate `status = 'shipped'` so well. For `customer_id` nothing stands out (each customer has about 10 orders), so the list is short and nearly meaningless.
- `histogram_bounds` (not shown in the box above) splits the other values into buckets with equal numbers of rows; it drives estimates for ranges such as `created_at >= ...`.
- `correlation` says how closely the physical order of rows in the table follows the order of the values, from -1 to 1. Near 1 means rows with similar values are stored together, which makes an index scan cheaper. Near 0, as for `customer_id`, means the matching rows are scattered.

How much detail does `ANALYZE` keep? That is set by `default_statistics_target`, 100 by default: it is the number of most-common-value entries and histogram buckets per column. According to the documentation, it also determines how many rows `ANALYZE` samples. The effect is visible with a table `hot` that I built: 300 values, each in exactly 200 rows, plus 40,000 unique noise values. The query asks for `v = 250`, whose real count is 200:

```text
STATISTICS 10:    Index Only Scan using hot_v_idx  (cost=0.29..65.27 rows=39 ...)
STATISTICS 100:   Index Only Scan using hot_v_idx  (cost=0.29..14.35 rows=5 ...)
STATISTICS 1000:  Index Only Scan using hot_v_idx  (cost=0.29..261.22 rows=200 ...)
```

With 100 slots there is no room for all 300 popular values, so 250 missed the most-common list and got an average guess for "values not on the list": 5 rows. With 1000 slots all 300 fit (I checked: the list had 300 entries) and the estimate is exact. With 10 slots the guess was 39. The plan type stayed the same here, but a wrong estimate in a bigger query, say a join, can change the join order or method. Raise the target for one column with `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS`, not globally: more detail makes `ANALYZE` and planning slower.

## Things that defeat an index

Sometimes the statistics are fine and the planner still cannot use the index, because of how the query is written. These are the ones I tested:

- **A type cast on the column.** `customer_id = 42` used the index (`Bitmap Heap Scan`, 15 pages). `customer_id = 42::numeric` gave a `Parallel Seq Scan` with `Filter: ((customer_id)::numeric = '42'::numeric)` and 3357 pages. The comparison forced PostgreSQL to cast the column, not the constant, so the index on the raw column could not be used. `customer_id::text = '42'` did the same. Also notice the estimate: `rows=1000` against 10 real rows. The planner cannot use its statistics once the column is wrapped.
- **A function on the column.** `lower(email) = '...'` was a Seq Scan (estimate 100, actual 1), and an index on `lower(email)` fixed it. A condition that an index can use is called {{< term "sargable" "sargable" >}}.
- **A leading wildcard.** With a `text_pattern_ops` index, `LIKE 'Customer 4242%'` used an Index Scan, because a prefix is a range in sorted order. `LIKE '%4242'` was a Seq Scan, since the match can start anywhere. (According to the PostgreSQL docs, in most non-C locales a prefix `LIKE` needs this special operator class to use a B-tree at all. I used it in the demo and did not test the plain index.)
- **`OR`.** `customer_id = 42 OR status = 'cancelled'` with both columns indexed used a `BitmapOr`: one bitmap from each index, merged. With `customer_id = 42 OR total_cents = 12345`, where `total_cents` has no index, it fell back to a Parallel Seq Scan. One unindexed branch of an `OR` is enough to force a full scan.

## Correlated columns: extended statistics

The planner has one more blind spot. It assumes columns are independent: when two conditions are combined, it multiplies their selectivities. That is wrong when one column determines the other. I made a table `customers_geo` with `country` and a derived `region` (every `DE` customer is in `EU`) and asked for `country = 'DE' AND region = 'EU'`, whose real count is 1666:

```text
before: Seq Scan on customers_geo  (cost=0.00..428.00 rows=694 ...) (actual rows=1666.00 ...)
CREATE STATISTICS geo_dep (dependencies) ON country, region FROM customers_geo;  ANALYZE customers_geo;
after:  Seq Scan on customers_geo  (cost=0.00..428.00 rows=1666 ...) (actual rows=1666.00 ...)
```

The 694 is the independence assumption at work: 1/12 of the customers are German, 5/12 are in `EU`, and 20,000 x 1/12 x 5/12 is about 694. But every German customer is in the EU, so the second condition removes nothing. After `CREATE STATISTICS ... (dependencies)` the planner knows that `country` determines `region` (the `pg_stats_ext` view shows `{"2 => 3": 1.000000}`, meaning column 2 determines column 3 with strength 1) and the estimate is exact. The plan did not change on a table this small. On a join, a 2.4x underestimate like this could lead to a worse plan.

## Troubleshooting checklist

1. Run `EXPLAIN (ANALYZE, BUFFERS)` and compare estimated and actual rows at each node.
2. If there is a big gap, `ANALYZE` the table, and check `last_analyze` in `pg_stat_user_tables`.
3. If it is still off, read `pg_stats`. Consider a higher per-column target, or `CREATE STATISTICS` for correlated columns.
4. If the estimates are fine and the index is still not used, check selectivity, casts, functions and wildcards.
5. Only then, try `enable_seqscan = off` in one session to see what the planner's second choice costs.

## Judging the planner

- A Seq Scan is not a bug. Judge by estimate against actual, not by the node name.
- Cast the parameter, never the column.
- `SET enable_*` is for diagnosis only.
- I did not test huge tables or `random_page_cost` tuning, so I cannot say much about them.

## Exercise

Load 200k rows where 99% of one indexed column is `'a'`, without `ANALYZE`. Compare the plans for `'a'` and for a rare value before and after `ANALYZE`.

## What's next

[Transactions and ACID](/posts/db-transactions-acid/). So far we only read; the next question is what happens when several statements must succeed or fail together.
