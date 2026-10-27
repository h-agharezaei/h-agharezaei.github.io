+++
date = '2027-01-24T10:00:00+03:30'
draft = false
title = 'Zero-downtime migrations'
description = 'Zero-downtime migrations on PostgreSQL 18.3: which ALTERs rewrite the table, NOT VALID constraints, CREATE INDEX CONCURRENTLY and expand/contract.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "migrations", "zero-downtime", "ddl"]
cover = { image = "/images/covers/db-zero-downtime-migrations.png", alt = "Zero-downtime migrations", hiddenInSingle = true }
+++

In the [previous post](/posts/db-jsonb-fulltext-search/) we added JSONB and search indexes to a table. On a laptop that is free; on a live table with traffic, the same {{< term "migration" "migration" >}} can freeze the application. The cost is rarely the SQL itself, it is the [locks](/posts/db-locks-deadlocks/) it takes and how long it holds them. This post checks, statement by statement, what is safe. It uses what we learned about [MVCC](/posts/db-mvcc-vacuum/), [indexes](/posts/db-indexes-btree-explain/) and [transactions](/posts/db-transactions-acid/).

> Everything ran on a real PostgreSQL 18.3, on a copy of the 200k-row `orders` table (`orders_m`). Two or three sessions were driven by one small Go program in a fixed order. Some of these behaviours depend on the version; I only ran 18.3. No timings: the machine was busy, so I use deterministic signals instead.

## Does it rewrite the table?

A {{< term "table-rewrite" "table rewrite" >}} is the dangerous kind. `pg_relation_filenode()` tells you: if the number changes, the table was copied into a new file.

```text
ADD COLUMN note text DEFAULT 'none' (constant)       same file (no rewrite)
ADD COLUMN tag varchar(10)                           same file (no rewrite)
ALTER tag TYPE varchar(20) (widen)                   same file (no rewrite)
ALTER tag TYPE text                                  same file (no rewrite)
ADD COLUMN seen_at timestamptz DEFAULT clock_timestamp() NEW file (table rewritten)
ALTER total_cents TYPE numeric(14,2)                 NEW file (table rewritten)
ALTER total_cents TYPE bigint (back)                 NEW file (table rewritten)
```

A constant default is instant, and all 200k rows read `none` afterwards (1 distinct value). A volatile default must be computed per row, so it rewrites; afterwards the rows had 65200 distinct `seen_at` values (this number differs per run). Widening a `varchar` or changing it to `text` needs no rewrite here, but changing `bigint` to `numeric` does. I did not test shrinking a `varchar`.

## SET NOT NULL and CHECK ... NOT VALID

`SET NOT NULL` normally scans the whole table under a strong lock. With `client_min_messages = debug1` the server tells us what it did:

```text
plain SET NOT NULL:
    verifying table "orders_m"
SET NOT NULL after a validated CHECK:
    existing constraints on column "orders_m.ref2" are sufficient to prove that it does not contain nulls
```

So the trick is: add `CHECK (col IS NOT NULL) NOT VALID`, run `VALIDATE CONSTRAINT`, then `SET NOT NULL` (it skips the scan), then drop the check. The reason this works is in the locks. I held each statement inside an open transaction and read `pg_locks`, while session B tried an `INSERT` with `lock_timeout = 300ms`:

```text
A plain ADD CONSTRAINT holds: orders_m:AccessExclusiveLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
A ... NOT VALID holds: orders_m:AccessExclusiveLock
INSERT total_cents=-1 while the constraint is NOT VALID: ERROR: new row for relation "orders_m" violates check constraint "t_pos" (SQLSTATE 23514)
A VALIDATE holds: orders_m:ShareUpdateExclusiveLock
B INSERT meanwhile: ok
```

`NOT VALID` takes the strong lock only for an instant (no scan) and already checks new rows. `VALIDATE` does the long scan under `ShareUpdateExclusiveLock`, which lets writes through.

## Indexes

`CREATE INDEX` blocks writes. {{< term "create-index-concurrently" "CREATE INDEX CONCURRENTLY" >}} does not, but it waits for older transactions, so I kept a writer open in session C and inserted from B while the build waited:

```text
A CREATE INDEX (open tx) holds: orders_m:ShareLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
CIC waiting; its table lock: ShareUpdateExclusiveLock
B INSERT meanwhile: ok
CIC result: ok
```

A concurrent build can fail halfway. I forced it with a unique index on a non-unique column:

```text
CREATE UNIQUE ... CONCURRENTLY: ERROR: could not create unique index "orders_m_cust_u" (SQLSTATE 23505)
   orders_m_cust      indisvalid=true indisready=true
   orders_m_cust_u    indisvalid=false indisready=false
DROP INDEX CONCURRENTLY orders_m_cust_u: ok
invalid indexes left: 0
```

The failed index stays, `indisvalid = false`, and costs write overhead for nothing. Drop it and retry.

## lock_timeout and retry

Even a quick `ALTER TABLE` needs `AccessExclusiveLock`, and it queues behind any long reader. Worse, everything behind it queues too. Set {{< term "lock-timeout" "lock_timeout" >}} on the DDL and retry. Session C held a read transaction open:

```text
attempt 1: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 2: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 3: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 4: ok
plain SELECT while ALTER waits in the queue: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

I released C before attempt 4. The last line, with no `lock_timeout` on the `ALTER`, shows the queue: a plain `SELECT` could not even start while the `ALTER` waited.

## Expand/contract

To rename `total_cents` to `amount_cents`, never use `RENAME` while old code runs. Use the {{< term "expand-contract" "expand/contract" >}} recipe; the locks are from `pg_locks`:

1. Add the nullable column (`AccessExclusiveLock`, but metadata only).
2. Add a {{< term "trigger" "trigger" >}} that copies the value on insert and update (`ShareRowExclusiveLock`). A new row with `total_cents = 777` got `amount_cents = 777`.
3. {{< term "backfill" "Backfill" >}} in batches (`RowExclusiveLock`, writes continue):

```text
   batch 1: ids (0, 50000] -> 50000 rows
   batch 2: ids (50000, 100000] -> 50000 rows
   batch 3: ids (100000, 150000] -> 50000 rows
   batch 4: ids (150000, 200000] -> 50000 rows
   tail (rows above the range): 2 rows
rows still NULL: 0  mismatches: 0
```

4. Enforce it: `CHECK ... NOT VALID`, `VALIDATE`, `SET NOT NULL` (no scan, as above).
5. Deploy the application to read and write `amount_cents`.
6. Contract: drop the trigger and `total_cents` (brief `AccessExclusiveLock`; according to the docs dropping a column does not rewrite the table, I did not check the file).

Between steps both old and new code work, which is the whole point.

## A few things to watch

- `RENAME COLUMN` is a metadata change (per the docs; I did not run it) but breaks running code; the recipe above is for compatibility, not speed.
- Every DDL in production gets `lock_timeout` and a retry loop.
- `CREATE INDEX CONCURRENTLY` cannot run in a transaction block; check for INVALID indexes afterwards.
- Behaviour such as which type changes skip a rewrite is version dependent: test on your version with `pg_relation_filenode()`.
- Migration tools (goose, Flyway and the like) only run files in order; they do not make a statement safe.

## Exercise

Copy a table, then plan "make `status` `NOT NULL` and add a foreign key" with no long blocking lock. For each statement predict the lock, then confirm it in `pg_locks`.

## What's next

The next post is "Table partitioning": splitting one huge table into parts the planner can skip.
