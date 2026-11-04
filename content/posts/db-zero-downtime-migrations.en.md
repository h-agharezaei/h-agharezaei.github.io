+++
date = '2027-01-24T10:00:00+03:30'
draft = false
title = 'Zero-downtime migrations'
description = 'Zero-downtime migrations on PostgreSQL 18.3: which ALTERs rewrite the table, NOT VALID constraints, CREATE INDEX CONCURRENTLY and expand/contract.'
contentType = 'engineering'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "migrations", "zero-downtime", "ddl"]
cover = { image = "/images/covers/db-zero-downtime-migrations.png", alt = "Zero-downtime migrations", hiddenInSingle = true }
+++

Picture a deploy on a busy day. The migration is one line, `ALTER TABLE orders ADD COLUMN ...`, and it passed on your laptop in a few milliseconds. In production it starts, and then the whole site stops answering. Nothing is wrong with the SQL. The statement needed a very strong {{< term "lock" "lock" >}} on the table, someone's long transaction was already holding a weaker one, and every query that arrived after your `ALTER` stood in line behind it.

A {{< term "migration" "migration" >}} is a change to the database schema (a new column, a new index, a new constraint) applied in a fixed order by a script or a tool. On a live table the risk is almost never the SQL itself. It is two other things: which lock the statement takes, and how long it holds it. So this post takes the common schema changes one at a time and checks them, with real output, for exactly those two questions. It builds on [locks and deadlocks](/posts/db-locks-deadlocks/), on [MVCC](/posts/db-mvcc-vacuum/), [indexes](/posts/db-indexes-btree-explain/) and [transactions](/posts/db-transactions-acid/), and it follows [JSONB and full-text search](/posts/db-jsonb-fulltext-search/), where we built some fairly big indexes without caring what they did to other sessions.

> Everything ran on a real PostgreSQL 18.3 (I re-ran the demo for this version of the post and the output below matches, except for one number that is random and that I point out). The table is a copy of the 200,000-row `orders` table, called `orders_m`. Two or three sessions were driven by one small Go program in a fixed order, so the timing of each step is deliberate. Some of these behaviours depend on the PostgreSQL version; I only ran 18.3. I show no timings, because they depend on the machine. Instead I use signals that do not change: which file the table lives in, which lock is held, and whether a statement was blocked.

## First question: does the statement rewrite the table?

Some `ALTER TABLE` statements only change the table's description in the system catalog, which takes no time however big the table is. Others have to read every row and write all of them again into a new file on disk. That second kind is a {{< term "table-rewrite" "table rewrite" >}}. During it the table is locked, so on a big table it can mean minutes of downtime.

How do we know whether a statement rewrote the table? Every table lives in a file, and `pg_relation_filenode()` returns that file's number. If the number changes after the statement, the table was copied into a new file. The demo runs seven statements and compares the number before and after each:

```text
ADD COLUMN note text DEFAULT 'none' (constant)       same file (no rewrite)
ADD COLUMN tag varchar(10)                           same file (no rewrite)
ALTER tag TYPE varchar(20) (widen)                   same file (no rewrite)
ALTER tag TYPE text                                  same file (no rewrite)
ADD COLUMN seen_at timestamptz DEFAULT clock_timestamp() NEW file (table rewritten)
ALTER total_cents TYPE numeric(14,2)                 NEW file (table rewritten)
ALTER total_cents TYPE bigint (back)                 NEW file (table rewritten)
```

Read it as two groups. In the first four lines the file stays the same. Adding a column with a constant default (`'none'`) is instant: PostgreSQL stores the default once in the catalog and does not touch the 200,000 rows, yet every row reads `none` afterwards (the demo counted 1 distinct value). Widening a `varchar`, or changing it to `text`, also needed no rewrite here.

The last three lines are the dangerous ones. `clock_timestamp()` is a *volatile* function: it returns a different value on every call, so PostgreSQL cannot store one default, it must compute it for each row, and that means writing every row again. Afterwards the rows had 63,362 distinct `seen_at` values in this run (65,200 in an earlier run: it depends on the clock, so it differs every time). Changing `bigint` to `numeric(14,2)` and back also rewrote the table, because the stored form of the values changes. I did not test shrinking a `varchar`, so I make no claim about it.

One more fact I checked in a scratch copy: renaming a column and dropping a column left the file number unchanged, so on 18.3 both are catalog-only changes. That is the "does it rewrite?" answer. The next question is about the lock, and that question is where most of the real trouble lives.

## Adding a rule to a big table: SET NOT NULL and CHECK ... NOT VALID

Say you want `NOT NULL` on a column of a table that already holds data. PostgreSQL must prove that no row has a null there, so it reads the whole table, and it does that while holding a strong lock. With `client_min_messages = debug1` the server tells us what it did. The demo runs `SET NOT NULL` twice, on two similar columns, the second after adding and validating a `CHECK (col IS NOT NULL)` constraint first:

```text
plain SET NOT NULL:
    verifying table "orders_m"
SET NOT NULL after a validated CHECK:
    existing constraints on column "orders_m.ref2" are sufficient to prove that it does not contain nulls
```

The first message says the server scanned the table ("verifying table"). The second says it did not need to: a validated `CHECK` already proves there are no nulls, so it skipped the scan. The trick is therefore to add `CHECK (col IS NOT NULL) NOT VALID`, run `VALIDATE CONSTRAINT`, then `SET NOT NULL`, and finally drop the check.

Why is that better, if it is the same amount of checking in the end? The answer is in the locks. A constraint added with `NOT VALID` means "enforce it for new and changed rows from now on, and do not look at the old rows yet". `VALIDATE CONSTRAINT` is the separate step that scans the old rows. To see the locks, the demo holds each statement open inside a transaction and reads `pg_locks`, while a second session B tries an `INSERT` with `lock_timeout = 300ms` (it gives up with an error if it has to wait more than 300 ms):

```text
A plain ADD CONSTRAINT holds: orders_m:AccessExclusiveLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
A ... NOT VALID holds: orders_m:AccessExclusiveLock
INSERT total_cents=-1 while the constraint is NOT VALID: ERROR: new row for relation "orders_m" violates check constraint "t_pos" (SQLSTATE 23514)
A VALIDATE holds: orders_m:ShareUpdateExclusiveLock
B INSERT meanwhile: ok
```

Line by line:

1. A plain `ADD CONSTRAINT ... CHECK` holds `AccessExclusiveLock`, the strongest table lock. B's insert could not get in and timed out. On a real table this is the time while the whole table is scanned.
2. `NOT VALID` also takes `AccessExclusiveLock`, but there is nothing to scan, so it is held only for the instant of the catalog change. (The demo shows the lock, not its duration.)
3. Even though the old rows were not checked, the constraint already works: inserting a row with `total_cents = -1` was rejected with a check violation (SQLSTATE 23514).
4. `VALIDATE` does the long scan, but under `ShareUpdateExclusiveLock`, a much weaker lock, and B's insert went through (`ok`). Writes continue while the old rows are being checked.

That is the whole idea of the section: split one long, blocking step into one instant blocking step and one long step that does not block writers.

## Indexes: CREATE INDEX versus CONCURRENTLY

A plain `CREATE INDEX` blocks writes to the table while it builds. {{< term "create-index-concurrently" "CREATE INDEX CONCURRENTLY" >}} was made so that it does not, but it has a cost: it takes more passes over the table and it has to wait for older transactions to finish. To see both, I opened a transaction in A with a plain `CREATE INDEX` and tried an insert from B. Then I ran the concurrent build while session C kept an old writing transaction open, and inserted from B again while the build was waiting for C:

```text
A CREATE INDEX (open tx) holds: orders_m:ShareLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
CIC waiting; its table lock: ShareUpdateExclusiveLock
B INSERT meanwhile: ok
CIC result: ok
```

The plain build holds `ShareLock`, which conflicts with writes, so B's insert timed out. The concurrent build, even while it was waiting for C, held only `ShareUpdateExclusiveLock`, B's insert worked, and when C committed the build finished (`CIC result: ok`). The price of the concurrent version is that it waits for every transaction that was already open, so a forgotten open transaction makes it wait a long time.

The other price is that a concurrent build can fail halfway. To force this, I tried to create a unique index on `customer_id`, which is not unique:

```text
CREATE UNIQUE ... CONCURRENTLY: ERROR: could not create unique index "orders_m_cust_u" (SQLSTATE 23505)
   orders_m_cust      indisvalid=true indisready=true
   orders_m_cust_u    indisvalid=false indisready=false
DROP INDEX CONCURRENTLY orders_m_cust_u: ok
invalid indexes left: 0
```

The build failed with a duplicate-key error, but it did not clean up after itself. The half-built index `orders_m_cust_u` is still in the catalog with `indisvalid = false` and `indisready = false`: the planner never uses it, and it is only clutter that confuses the next person who reads the schema. (The other index, `orders_m_cust`, is the healthy one from the previous step.) The fix is to drop it, with `DROP INDEX CONCURRENTLY` so that the drop does not block either, and then try again. The last line confirms nothing invalid was left.

## Protect everybody else: lock_timeout and retry

Now to the story from the beginning. Even a very quick `ALTER TABLE` needs `AccessExclusiveLock`. If any transaction has touched the table and not finished, the `ALTER` waits for it. And while it waits, every new query on that table queues behind the `ALTER`, because PostgreSQL does not let newcomers jump ahead of a waiting strong lock. That is how one forgotten transaction plus one migration stops a site.

The protection is {{< term "lock-timeout" "lock_timeout" >}}: put it on the DDL session, and if the lock is not obtained in time, the statement gives up and the queue behind it moves again. Then you simply try again, in a loop. In the demo session C opened a transaction and read the table, and A (with `lock_timeout = 200ms`) tried to add a column four times. Before the fourth attempt I committed C:

```text
attempt 1: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 2: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 3: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 4: ok
```

Each failed attempt cost 200 ms of waiting and no more, so nobody was stuck for long, and once C was gone the migration went through on the next try.

To see the queue itself, I repeated this with no `lock_timeout` on the `ALTER` (so it waits as long as it must) and tried a plain `SELECT` from B, with its own 300 ms timeout:

```text
plain SELECT while ALTER waits in the queue: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

A plain read could not even start. The `SELECT` has no conflict with C, but it conflicts with the `ALTER` that is waiting in front of it. (After C committed, the `ALTER` finished: the demo printed `ALTER finished: ok`.)

## Renaming a column the safe way: expand/contract

A harder case: you want to rename `total_cents` to `amount_cents`. The `RENAME` itself is a catalog-only change (I checked this above), but the instant it runs, every running copy of the application that still uses the old name starts failing. The only way out is to never break the running code. The {{< term "expand-contract" "expand/contract" >}} recipe does that by making every step compatible with both the old and the new code. The locks below are what I read from `pg_locks` in each step:

1. **Expand: add the new column**, nullable. `AccessExclusiveLock`, but only a catalog change, so it is brief.
2. **Keep it in sync with a {{< term "trigger" "trigger" >}}**: a function PostgreSQL runs automatically on every insert and update, here copying `total_cents` into `amount_cents` (`ShareRowExclusiveLock` to create it). I checked: a new row inserted with `total_cents = 777` came out with `amount_cents = 777`.
3. **{{< term "backfill" "Backfill" >}} the old rows in batches.** One `UPDATE` over the whole table would be one huge transaction that holds all its row locks until the end, so I did it in id ranges (`RowExclusiveLock`, normal writes continue):

```text
   batch 1: ids (0, 50000] -> 50000 rows
   batch 2: ids (50000, 100000] -> 50000 rows
   batch 3: ids (100000, 150000] -> 50000 rows
   batch 4: ids (150000, 200000] -> 50000 rows
   tail (rows above the range): 2 rows
rows still NULL: 0  mismatches: 0
```

   Four batches of 50,000 rows cover the original 200,000. The "tail" is the 2 rows that session B inserted earlier in the demo (ids 900002 and 900005, before the trigger existed), so they sit above the id ranges and still had no `amount_cents`. At the end no row has `amount_cents` null and none differs from `total_cents`.
4. **Enforce it** with the trick from earlier: `CHECK ... NOT VALID`, `VALIDATE`, `SET NOT NULL` (no scan this time), drop the check.
5. **Deploy the application** so that it reads and writes `amount_cents` (the demo does not do this, it is only a step in the order).
6. **Contract: drop the trigger and the old column.** A brief `AccessExclusiveLock`; the earlier scratch check showed that dropping a column does not rewrite the table.

At every point between the steps both the old code and the new code work. That is the entire point of the recipe, and the price is that one rename becomes six steps and usually at least two deploys.

## Rules I would apply to DDL in production

- **Put `lock_timeout` and a retry loop on every DDL.** A migration that waits silently is a migration that blocks everyone else.
- **Ask two questions about every statement:** does it rewrite the table, and which lock does it take for how long. `pg_relation_filenode()` answers the first, `pg_locks` the second.
- **`CREATE INDEX CONCURRENTLY` cannot run inside a transaction block.** Many migration tools run each file in a transaction by default, so check that yours has a way to turn that off for such a file. And afterwards look for `INVALID` indexes.
- **Which type changes skip a rewrite depends on the version.** Test on your own version with `pg_relation_filenode()` before trusting a list from the internet, including this one.
- **A migration tool does not make a statement safe.** Tools such as goose or Flyway only run the files in order; the safety is in what you write in them.

## What's next

[Table partitioning](/posts/db-partitioning/) is the next step: when a table grows so big that it is hard to treat as one piece, you split it into parts, so that the planner can skip the parts a query does not need.
