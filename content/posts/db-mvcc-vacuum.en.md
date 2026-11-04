+++
date = '2026-12-29T10:00:00+03:30'
draft = false
title = 'MVCC and VACUUM'
description = 'PostgreSQL MVCC and VACUUM with real runs: xmin, xmax and ctid, dead tuples, table bloat, VACUUM FULL, and a long transaction that blocks cleanup.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "mvcc", "vacuum", "bloat"]
cover = { image = "/images/covers/db-mvcc-vacuum.png", alt = "MVCC and VACUUM", hiddenInSingle = true }
+++

I had a table with 200 thousand rows that took about 13 MB. I ran one `UPDATE` over all its rows, without adding a single row, and its size became 26 MB. Then I ran `VACUUM` and the size did not shrink. If you work with a database from application code ([Transactions and the Repository pattern in Go](/posts/go-transactions-patterns/)), sooner or later you meet something like this and wonder why the database needs twice the space just to "change a number".

The answer is {{< term "mvcc" "MVCC" >}}. In the [previous post](/posts/db-isolation-levels-anomalies/) we saw A read from an old snapshot at `REPEATABLE READ` while B changed the same row at the same time, with neither blocking the other. That is only possible if the database **keeps both values at the same time**. This is the idea of MVCC (multi-version concurrency control): the database does not change a row in place. It writes a new version and keeps the old one for as long as someone may still need it. Think of a ledger where, instead of erasing a number, you cross out the old one and write the new one on the next line; someone who was already reading the old line can finish reading it. The price is extra space, and someone eventually has to throw the crossed-out lines away. That someone is {{< term "vacuum" "VACUUM" >}}.

> Everything below was re-run on a real PostgreSQL 18.3 with the sample `shop` data. On the small tables in this post I turned autovacuum off so nobody cleans up behind me and we can see what happens. There is no timing, only counts and sizes. I ran the two-session steps with a small Go program, so the order is always the same. Transaction numbers (like 892 below) differ from run to run; what matters is how they relate to each other.

## UPDATE writes a new version

To see what a "version" is, we look at a few hidden columns that PostgreSQL adds to every row. They do not appear in `SELECT *`, but you can name them explicitly:

- `xmin`: the number of the {{< term "transaction" "transaction" >}} that created this version.
- `xmax`: the number of the transaction that ended this version (deleted or replaced it). 0 means nobody has ended it yet.
- `ctid`: the physical location of the version, as (page number, slot number inside the page).

I created a table with three rows and changed one of them:

```text
SELECT ctid, xmin, xmax, * FROM acct ORDER BY id;     -- 3 rows inserted by tx 892
 (0,1) |  892 |    0 |  1 | ana |  100
 (0,2) |  892 |    0 |  2 | bob |  200
 (0,3) |  892 |    0 |  3 | cy  |  300

UPDATE acct SET balance = 150 WHERE id = 1;
 (0,4) |  893 |    0 |  1 | ana |  150      <- new ctid, new xmin
 (0,2) |  892 |    0 |  2 | bob |  200
 (0,3) |  892 |    0 |  3 | cy  |  300
```

Transaction 892 created the three rows. After the `UPDATE`, ana's row, which used to be in slot 1, is now in slot 4 and its `xmin` is 893: the `UPDATE`'s transaction created it. But what happened to slot 1? The `pageinspect` extension lets us look at what is really on the page:

```text
SELECT lp, t_xmin, t_xmax, t_ctid FROM heap_page_items(get_raw_page('acct',0));
 1 | 892 | 893 |  (0,4)     <- old version: ended by 893, points to the new one
 2 | 892 |   0 |  (0,2)
 3 | 892 |   0 |  (0,3)
 4 | 893 |   0 |  (0,4)     <- current version
```

The old version is still there. Only its `xmax` is now 893, meaning "transaction 893 ended this version", and its `t_ctid` points to the new version. In this output `lp` is the slot number.

Now the visibility rule becomes simple. Each query works with a snapshot, and it sees a version only if the transaction that created it (`xmin`) is committed for this snapshot and the transaction that ended it (`xmax`) is not. A reader that started before transaction 893 committed still reads 100, because for it 893 has not committed and the version in slot 1 is alive. The next reader sees the version in slot 4. That is why readers and writers do not block each other.

An `UPDATE` that is rolled back leaves garbage too. I changed `bob` to 999 and then rolled back. The new 999 version stayed in slot 5, and the visible row is `(0,2)` again, but with `xmax = 894`. 894 is a transaction that never committed, so that `xmax` is ignored and the version with 200 is still alive. Slot 5 is no longer visible to anyone. In other words, a rollback does not erase anything; it only creates a version that is never seen.

## Dead versions and VACUUM

A version that no transaction, present or future, can see any more is called a {{< term "dead-tuple" "dead tuple" >}}. Our table now has two: ana's old version and bob's abandoned one. PostgreSQL delivers statistics to the stats views with a small delay, so before reading `pg_stat_user_tables` I called `pg_stat_force_next_flush()` to see the numbers of this very moment. The result was `n_dead_tup = 2`. Then I ran `VACUUM acct` and looked at the page again:

```text
 lp | lp_flags | t_xmin | t_xmax | t_ctid
  1 |        2 |        |        |            <- redirect to slot 4
  2 |        1 |    892 |    894 | (0,5)      <- live, stale xmax of the aborted tx
  3 |        1 |    892 |      0 | (0,3)
  4 |        1 |    893 |      0 | (0,4)
```

The dead data is gone. Slot 5 was freed completely, and `n_dead_tup` went back to 0. Slot 1 became a redirect (`lp_flags = 2`; according to the pageinspect documentation that means the entry points to another row and holds no data itself). This was a {{< term "hot-update" "HOT update" >}}: the new version stayed inside the same page, so no new entry had to be added to the indexes. The index still points to slot 1, and slot 1 sends you on to slot 4. HOT is only possible when no indexed column changed and there is room in the page. Here `n_tup_hot_upd = 2` out of `n_tup_upd = 2`, so both updates were HOT.

An important point: VACUUM gives the freed space back to the database to be reused for later rows. It does not necessarily make the file smaller. We see this with numbers in the next section.

## Bloat in numbers

Now the question we started with. I copied the `orders` table (200 thousand rows, with a primary key) into a table called `orders_copy`, turned autovacuum off for it and ran `VACUUM ANALYZE` so the starting point is clean. Then I updated all the rows and measured the size after each step:

```text
                         heap            pages   pkey
fresh                    13 MB            1677   4408 kB
after UPDATE (all rows)  26 MB            3353   8792 kB    n_dead_tup = 200000, n_tup_hot_upd = 0
after VACUUM             26 MB            3353   8792 kB    n_dead_tup = 0
after a 2nd UPDATE       26 MB            3353   8792 kB    (space reused)
after VACUUM FULL        13 MB            1677   4408 kB
```

Line by line:

- **fresh:** 13 MB, 1677 pages of 8 KB. The primary key index is 4408 kB.
- **after UPDATE of all rows:** 200 thousand new versions were written and 200 thousand old ones stayed. The heap and the index both doubled. This is {{< term "table-bloat" "table bloat" >}}: space occupied by dead versions. `n_tup_hot_upd = 0` means none of them was HOT, because the pages were full and had no room for the new versions; so the index got a new entry for every version, which is why the index doubled too.
- **after VACUUM:** `n_dead_tup` is zero but the size stays at 26 MB. A plain `VACUUM` frees space for reuse, not for returning to the operating system.
- **after a second full update:** still 26 MB. The new versions were written into the freed spots and the file did not grow. This matters in practice: if a table that is updated all the time is vacuumed regularly, it settles near a roughly constant size instead of growing forever (as long as nothing such as a long transaction blocks the cleanup, which we see later).
- **after VACUUM FULL:** 13 MB. `VACUUM FULL` rewrites the table into a new file and carries over only the live rows.

So why not always run `VACUUM FULL`? According to the documentation, `VACUUM FULL` takes an `ACCESS EXCLUSIVE` lock, which means nobody can read from or write to the table until it finishes. To see it, I put a reader with an open transaction on a 10-thousand-row table, and in another session set `lock_timeout = 300ms` so the wait does not go on forever:

```text
VACUUM hold      -> ok
VACUUM FULL hold -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

A plain `VACUUM` has no problem with a reader that has an open transaction. `VACUUM FULL` got stuck behind that same reader and gave up after 300 milliseconds. So on a busy table, `VACUUM FULL` blocks reads and writes for as long as it runs.

## A long transaction holds back cleanup

Now a question: when is VACUUM sure it can throw away an old version? When no old snapshot exists that could still see it. So one long open transaction can stop the whole cleanup. I tried it: one session took a snapshot at `REPEATABLE READ` and read the sum of the `total_cents` column (`sum = 631116377`). Another session updated all 10000 rows of the table. Then `VACUUM (VERBOSE)` said:

```text
tuples: 0 removed, 20000 remain, 10000 are dead but not yet removable
removable cutoff: 918, which was 1 XIDs old when operation ended
```

The 10000 old versions are dead for everyone except that one snapshot, so nothing was removed (`0 removed`), and the phrase "dead but not yet removable" says exactly that. It is easy to confirm: that same session still saw the old sum. After that session committed, `VACUUM (VERBOSE)` again:

```text
tuples: 10000 removed, 10000 remain, 0 are dead but not yet removable
```

Now the 10000 old versions were removed. The only difference was one open transaction. In practice, a forgotten connection in the {{< term "idle-in-transaction" "idle in transaction" >}} state (an open transaction that is doing nothing) can block the cleanup of dead versions for the tables of the whole database and make them swell. (The `removable cutoff` number differs from run to run; what matters is what gets removed, not the number itself.)

## autovacuum and the visibility map

You do not need to run VACUUM by hand every time. {{< term "autovacuum" "Autovacuum" >}} does it in the background. According to the documentation, it vacuums a table when the number of dead rows exceeds `autovacuum_vacuum_threshold` plus `autovacuum_vacuum_scale_factor` times the number of rows. On this instance `SHOW` gave the defaults, 50 and 0.2. I did not tune anything.

VACUUM does something else too: it fills the {{< term "visibility-map" "visibility map" >}}, which marks which pages have only rows visible to everyone. In the second VACUUM above, the report said "109 pages set all-visible". This is what lets an {{< term "index-only-scan" "index-only scan" >}} answer from the index alone instead of going to the heap, as in [Composite, partial and covering indexes](/posts/db-composite-partial-covering-indexes/). So VACUUM is not only a cleaner; it also makes reads faster.

## Hidden costs of MVCC

- **Every update creates a new version.** A table that is updated a lot needs regular VACUUM so it does not fall behind.
- **Update only the column that actually changed.** Touching an indexed column rules out HOT, and every version then grows the indexes too.
- **Set up alerts for long transactions and `idle in transaction`.** As we saw, one idle transaction can stop cleanup of every table.
- **`VACUUM FULL` locks the table.** It is not a routine job for a busy table; I did not try the lighter alternatives.

## Exercise

Create a table with 100 thousand rows, update half of it and look at `n_dead_tup`, `pg_relation_size`, `VACUUM` and `VACUUM FULL`. Then repeat it with an open `REPEATABLE READ` session and see what `VACUUM` cannot remove.

## What's next

[Locks and deadlocks in the database](/posts/db-locks-deadlocks/): MVCC helps readers, but two writers on the same row still have to wait for each other. There we see when and how.
