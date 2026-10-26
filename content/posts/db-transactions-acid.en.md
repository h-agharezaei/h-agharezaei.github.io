+++
date = '2026-12-13T10:00:00+03:30'
draft = false
title = 'Transactions and ACID'
description = 'PostgreSQL transactions and ACID with real runs: BEGIN, ROLLBACK, savepoints, constraints, transactional DDL, WAL and synchronous_commit.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "transactions", "acid", "wal"]
cover = { image = "/images/covers/db-transactions-acid.png", alt = "Transactions and ACID", hiddenInSingle = true }
+++

A money transfer is two updates: subtract here, add there. If the process dies between them, money disappears. A {{< term "transaction" "transaction" >}} is the database's answer: a group of statements that either all happen or none do. In the [previous post](/posts/db-planner-statistics/) we looked at how the planner reads data; now we look at how writes stay correct. The application side of this is in [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/).

> Everything ran on a real PostgreSQL 18.3. I used a small `accounts` table (alice 10000 cents, bob 5000) with `CHECK (balance_cents >= 0)` and a `transfers` table with foreign keys. The pieces together are called {{< term "acid" "ACID" >}}.

## Autocommit versus BEGIN

Without `BEGIN`, every statement is its own transaction and commits immediately (autocommit). `UPDATE accounts SET balance_cents = balance_cents - 3000 WHERE id = 1` made alice 7000 at once, even though bob had not received anything yet. That is the problem a transfer must avoid.

## Atomicity

I wrapped the transfer in a transaction, with a second statement that fails (bob would go to -4000):

```text
BEGIN;
UPDATE accounts SET balance_cents = balance_cents - 3000 WHERE id = 1;   -- UPDATE 1
UPDATE accounts SET balance_cents = balance_cents - 9000 WHERE id = 2;
ERROR:  new row for relation "accounts" violates check constraint "accounts_balance_cents_check"
DETAIL:  Failing row contains (2, bob, -4000).
SELECT 1;
ERROR:  current transaction is aborted, commands ignored until end of transaction block
COMMIT;
ROLLBACK
```

After an error the transaction is **aborted**: every further command is refused until the block ends. Even `COMMIT` answers `ROLLBACK`. The balances afterwards were alice 10000, bob 5000: the first update vanished. The successful version (minus 3000, plus 3000, `COMMIT`) gave 7000 and 8000. An explicit `ROLLBACK` works the same: inside the transaction I set alice to 0 and read 0; after `ROLLBACK` she was 7000 again.

## Savepoints

A {{< term "savepoint" "savepoint" >}} lets you undo a part:

```text
BEGIN;
UPDATE accounts SET balance_cents = balance_cents - 100 WHERE id = 1;
SAVEPOINT s1;
UPDATE accounts SET balance_cents = balance_cents - 99999 WHERE id = 1;   -- CHECK violation
ROLLBACK TO s1;                                                          -- transaction usable again
UPDATE accounts SET balance_cents = balance_cents - 200 WHERE id = 1;
COMMIT;
```

Alice went from 7000 to 6700: the -100 and -200 survived, the failed one did not. Without the savepoint the error would have aborted everything.

## Consistency

Consistency here means constraints. A {{< term "check-constraint" "CHECK" >}} failed above; a {{< term "foreign-key" "foreign key" >}} does the same. I subtracted 50 from alice and inserted a transfer to account 99, which does not exist:

```text
ERROR:  insert or update on table "transfers" violates foreign key constraint "transfers_to_id_fkey"
DETAIL:  Key (to_id)=(99) is not present in table "accounts".
```

The final `COMMIT` rolled back and alice stayed 6700. Constraints guard the data even if the application code has a bug. The database only enforces rules you declared; business rules that are not constraints are your job.

## DDL is transactional (PostgreSQL)

I did `BEGIN; CREATE TABLE temp_demo ...; INSERT ...; SELECT count(*)` (returned 1) and then `ROLLBACK`. Afterwards `to_regclass('temp_demo')` was empty: the table never existed. This is a PostgreSQL feature; I did not test other databases, and some of them commit implicitly on DDL, so do not assume it elsewhere. It makes migrations safer.

## Isolation: a teaser

A small Go program opened two connections. Session A began a transaction, subtracted 500 from alice and inserted a transfer:

```text
A: BEGIN; update alice -500; insert a transfer row
  A sees: alice=6200, transfers=1
  B sees: alice=6700, transfers=0
A: COMMIT
  B sees: alice=6200, transfers=1
```

B does not see uncommitted work. What exactly B may see in more complex cases depends on the isolation level, which is the next post.

## Durability, WAL and synchronous_commit

A committed change must survive a crash. PostgreSQL writes each change to the {{< term "wal" "WAL" >}} first and flushes it on commit. Real settings here:

```text
synchronous_commit = on     fsync = on     wal_level = replica     full_page_writes = on
```

With {{< term "synchronous-commit" "synchronous_commit" >}} `on`, `COMMIT` returns after the WAL is flushed. I measured WAL with `pg_current_wal_insert_lsn()` before and after (bytes, deterministic):

```text
UPDATE of one row (autocommit):      112 bytes
BEGIN; UPDATE; COMMIT:               112 bytes
BEGIN; COMMIT (empty):                 0 bytes
BEGIN; UPDATE; ROLLBACK:             112 bytes
```

Two lessons: an empty transaction costs nothing, and a rolled-back transaction still wrote WAL. (My first try used `pg_current_wal_lsn()`, which showed 0 for the rollback because that data was not yet written out; the insert position is the right one.) The very first update after startup wrote 4568 bytes. I checked the cause afterwards with `pg_walinspect`: an update right after a `CHECKPOINT` logs a full-page image (record `FPI_FOR_HINT`, flagged `FPW`), and the next update on the same page wrote only 112 bytes. The size of that image depends on how full the page is. **I did not crash-test durability**, for example with `kill -9`, so this section rests on the settings and the documentation.

## A few things to watch

- Keep transactions short. A long one holds locks and old row versions, which blocks cleanup; the post on MVCC and VACUUM explains it.
- Never wait for a user or an HTTP call inside a transaction.
- After an error the transaction is dead until `ROLLBACK` or `ROLLBACK TO` a savepoint.
- `synchronous_commit = off` is faster but can lose the last commits in a crash; I did not test it.
- In application code use one `WithTx` helper rather than hand-written `BEGIN` calls.

## Exercise

Add a `transfers` insert to the transfer, so a row is recorded only when both balances change. Make the second update fail with a CHECK violation and verify with `SELECT` that neither balance nor `transfers` changed. Then repeat it with a `SAVEPOINT` around the insert.

## What's next

Next in the series: Isolation levels and anomalies.
