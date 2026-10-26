+++
date = '2026-12-29T10:00:00+03:30'
draft = false
title = 'MVCC and VACUUM'
description = 'PostgreSQL MVCC and VACUUM with real runs: xmin, xmax and ctid, dead tuples, table bloat, VACUUM FULL, and a long transaction that blocks cleanup.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "mvcc", "vacuum", "bloat"]
cover = { image = "/images/covers/db-mvcc-vacuum.png", alt = "MVCC and VACUUM", hiddenInSingle = true }
+++

In the [previous post](/posts/db-isolation-levels-anomalies/) we saw what each isolation level promises. This post shows how PostgreSQL keeps that promise without making readers wait for writers: {{< term "mvcc" "MVCC" >}}, and the cost it leaves behind, which {{< term "vacuum" "VACUUM" >}} pays. It also explains why a table with 200k rows can occupy twice the disk it needs, a problem you may meet from the Go side ([transactions in Go](/posts/go-transactions-patterns/)) without knowing the cause.

> Everything ran on a real PostgreSQL 18.3 with the shared `shop` schema. Small demo tables had autovacuum switched off so nothing cleaned up behind my back. There are no timings. The two-session steps ran from one small Go program, so the order is fixed.

## An UPDATE writes a new row

Every row carries hidden columns: `xmin` (the {{< term "transaction" "transaction" >}} that created this version), `xmax` (the one that ended it, 0 if none) and `ctid` (its physical place: page, slot).

```text
SELECT ctid, xmin, xmax, * FROM acct ORDER BY id;     -- 3 rows inserted by tx 810
 (0,1) |  810 |    0 |  1 | ana |  100
 (0,2) |  810 |    0 |  2 | bob |  200
 (0,3) |  810 |    0 |  3 | cy  |  300

UPDATE acct SET balance = 150 WHERE id = 1;
 (0,4) |  811 |    0 |  1 | ana |  150      <- new ctid, new xmin
 (0,2) |  810 |    0 |  2 | bob |  200
 (0,3) |  810 |    0 |  3 | cy  |  300
```

The row moved from slot 1 to slot 4. The `pageinspect` extension shows what is really on the page:

```text
SELECT lp, t_xmin, t_xmax, t_ctid FROM heap_page_items(get_raw_page('acct',0));
 1 | 810 | 811 | (0,4)     <- old version: ended by 811, points to the new one
 2 | 810 |   0 | (0,2)
 3 | 810 |   0 | (0,3)
 4 | 811 |   0 | (0,4)     <- current version
```

The old version is still there. A query uses a snapshot and sees only versions created by transactions it can see and not ended by ones it can see. A reader that started before 811 committed still gets 100. That is how readers and writers avoid blocking each other.

A rolled-back update leaves garbage too: I updated `bob` to 999 and rolled back. Slot 5 holds the abandoned version, and the visible row is again `(0,2)` with `xmax = 812`, a transaction that never committed, so it is ignored.

## Dead tuples and VACUUM

A version nobody can see any more is a {{< term "dead-tuple" "dead tuple" >}}. After `pg_stat_force_next_flush()` (statistics reach the view with a short delay, so I forced a flush), `pg_stat_user_tables` said `n_dead_tup = 2`. Then `VACUUM acct`:

```text
 lp | lp_flags | t_xmin | t_xmax | t_ctid
  1 |        2 |        |        |            <- redirect to slot 4
  2 |        1 |    810 |    812 | (0,5)      <- live, stale xmax of the aborted tx
  3 |        1 |    810 |      0 | (0,3)
  4 |        1 |    811 |      0 | (0,4)
```

The dead data is gone, slot 5 was freed, and `n_dead_tup` is back to 0. Slot 1 became a redirect (`lp_flags = 2`, according to the pageinspect docs); this is a {{< term "hot-update" "HOT update" >}}: the new version stayed in the same page and no index entry was added, which works only when no indexed column changes and the page has room. Here `n_tup_hot_upd = 2` of `n_tup_upd = 2`.

## Bloat in numbers

I copied `orders` (200k rows, primary key) into `orders_copy` and updated every row:

```text
                         heap            pages   pkey
fresh                    13 MB            1677   4408 kB
after UPDATE (all rows)  26 MB            3353   8792 kB    n_dead_tup = 200000, n_tup_hot_upd = 0
after VACUUM             26 MB            3353   8792 kB    n_dead_tup = 0
after a 2nd UPDATE       26 MB            3353   8792 kB    (space reused)
after VACUUM FULL        13 MB            1677   4408 kB
```

The heap and the index doubled: this is {{< term "table-bloat" "table bloat" >}}. No HOT here, because the pages were full. Plain `VACUUM` did not shrink the file; it only marked space reusable, and the next full-table update stayed at 26 MB. `VACUUM FULL` rewrote the table into a new file and got back to 13 MB.

The price: according to the docs `VACUUM FULL` takes an `ACCESS EXCLUSIVE` lock. I checked the conflict with a reader holding an open transaction on a 10k-row table and `lock_timeout = 300ms`:

```text
VACUUM hold      -> ok
VACUUM FULL hold -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

So on a busy table, `VACUUM FULL` stops reads and writes while it runs. Plain `VACUUM` does not.

## A long transaction holds cleanup back

A `REPEATABLE READ` session took its snapshot (`sum = 631116377`). Another session updated all 10000 rows. `VACUUM (VERBOSE)` then reported:

```text
tuples: 0 removed, 20000 remain, 10000 are dead but not yet removable
removable cutoff: 826, which was 1 XIDs old when operation ended
```

The old versions are dead for everyone except that one snapshot, so nothing can be removed. The session still sees the old sum. After it committed:

```text
tuples: 10000 removed, 10000 remain, 0 are dead but not yet removable
```

A forgotten `idle in transaction` connection can therefore bloat tables all over the database.

## Autovacuum and the visibility map

You rarely run VACUUM by hand: {{< term "autovacuum" "autovacuum" >}} does it. According to the docs it vacuums a table when dead rows exceed `autovacuum_vacuum_threshold` plus `autovacuum_vacuum_scale_factor` times the row count; here `SHOW` returned 50 and 0.2. I did not tune it.

VACUUM also sets the {{< term "visibility-map" "visibility map" >}} (the second run above: "109 pages set all-visible"), which is what lets an {{< term "index-only-scan" "index-only scan" >}} skip the heap, as in [covering indexes](/posts/db-composite-partial-covering-indexes/).

## A few things to watch

- Every update leaves a version behind; a hot table needs VACUUM to keep up.
- Update only what changed; touching an indexed column rules out HOT.
- Alert on long transactions and `idle in transaction`.
- `VACUUM FULL` locks the table; I did not test the lighter alternatives.

## Exercise

Create a 100k-row table, update half of it, and watch `n_dead_tup`, `pg_relation_size`, `VACUUM` and `VACUUM FULL`. Then repeat with a `REPEATABLE READ` session open.

## What's next

Next in the series: Locks and deadlocks in the database.
