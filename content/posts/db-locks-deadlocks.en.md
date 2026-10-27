+++
date = '2027-01-04T10:00:00+03:30'
draft = false
title = 'Locks and deadlocks in the database'
description = 'PostgreSQL locks and deadlocks with real two-session runs: row locks, pg_locks, lock_timeout, a real deadlock and its fix, SKIP LOCKED queues, ALTER TABLE.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "locks", "deadlock", "concurrency"]
cover = { image = "/images/covers/db-locks-deadlocks.png", alt = "Locks and deadlocks in the database", hiddenInSingle = true }
+++

In the [previous post](/posts/db-mvcc-vacuum/) {{< term "mvcc" "MVCC" >}} let readers and writers pass each other. Two writers on the same row cannot: the second one has to wait. That wait is a {{< term "lock" "lock" >}}, and most "the database is stuck" incidents are a lock somebody forgot to release. This post makes sessions block each other on purpose, shows how to see who blocks whom, and ends with the classic traps. It builds on [transactions and ACID](/posts/db-transactions-acid/) and [isolation levels](/posts/db-isolation-levels-anomalies/).

> Everything ran on a real PostgreSQL 18.3. Two or three sessions were driven by one small Go program in a fixed order, so each result is deterministic. Process ids differ per run. The machine was busy, so there are no timings.

## Row locks

Session A runs `SELECT ... WHERE id = 1 FOR UPDATE` on a small `acct` table and keeps the transaction open. Session B then tries:

```text
B: UPDATE row 1       -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
B: FOR UPDATE NOWAIT  -> ERROR: could not obtain lock on row in relation "acct" (SQLSTATE 55P03)
B: SKIP LOCKED ids    -> [2 3]
```

By default B would wait forever; I set `lock_timeout = 300ms` so it gave up. `NOWAIT` fails at once, and `SKIP LOCKED` returns only the rows nobody holds. Which lock modes conflict? A holds a mode, B asks with `NOWAIT`:

```text
A holds \ B asks    FOR KEY SHARE      FOR SHARE          FOR NO KEY UPDATE  FOR UPDATE
FOR KEY SHARE       ok                 ok                 ok                 blocked
FOR SHARE           ok                 ok                 blocked            blocked
FOR NO KEY UPDATE   ok                 blocked            blocked            blocked
FOR UPDATE          blocked            blocked            blocked            blocked
```

`FOR NO KEY UPDATE` is what a plain `UPDATE` that does not touch key columns takes. It still lets foreign-key checks through: with it held, `INSERT INTO note (acct_id) VALUES (1)` worked; with `FOR UPDATE` held, it blocked.

## Table-level locks

Every statement also takes a table lock. I read it from `pg_locks` for session A's backend:

```text
after SELECT:                       AccessShareLock
after UPDATE:                       RowExclusiveLock
after ALTER TABLE ... ADD COLUMN:   AccessExclusiveLock
```

According to the docs `AccessExclusiveLock` conflicts with every other mode, which is why `ALTER TABLE` and `VACUUM FULL` can stop a table. I saw it: A held an open transaction that had read `acct`, B ran `VACUUM FULL acct`, and `pg_locks` showed A's `AccessShareLock` granted and B's `AccessExclusiveLock` with `granted = false`. When A committed, B finished.

## Who blocks whom

A updated row 2 and kept the transaction open; B updated the same row and waited:

```text
A is pid 8550, B is pid 8552
   8552 | Lock | transactionid | [8550] | UPDATE acct SET balance=balance+1 WHERE
   locks: transactionid | ShareLock | false
```

The columns are `pid`, `wait_event_type`, `wait_event`, `pg_blocking_pids(pid)` and the query, all for B. `pg_blocking_pids` gives the answer directly: process 8550. B waits for A's transaction id, not for a row, which is how row locks work here. Find the blocker in `pg_stat_activity` and look at its `state` and `xact_start`: it is usually idle in transaction.

## Timeouts

Three settings keep waiting bounded. `lock_timeout` gave the 55P03 error above. The other two:

```text
statement_timeout 200ms, pg_sleep(2) -> ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
idle in transaction 900ms, next statement -> FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
```

I used `idle_in_transaction_session_timeout = 300ms`. It kills the connection, which is the point: a client that began a transaction and went away stops holding locks.

## A real deadlock

`SHOW deadlock_timeout` gave `1s` (I did not time it). A updated row 1, B updated row 2, A asked for row 2 and waited, then B asked for row 1:

```text
A -> ERROR: deadlock detected (SQLSTATE 40P01)
      DETAIL: Process 8550 waits for ShareLock on transaction 792; blocked by process 8552.
      Process 8552 waits for ShareLock on transaction 791; blocked by process 8550.
      HINT: See server log for query details.
```

PostgreSQL cancelled A, and B's update then went through. Which session is chosen is not something to rely on. The fix is one ordering rule: always lock rows in the same order (by id). With both sessions starting at row 1, B just waited for A to commit and both finished without error. Your code should still retry on 40P01.

## A job queue with SKIP LOCKED

Six rows in `jobs`. Each worker runs:

```sql
SELECT id FROM jobs WHERE state='new' ORDER BY id LIMIT 2 FOR UPDATE SKIP LOCKED
```

Worker 1 claimed `[1 2]` with its transaction open; worker 2, at the same moment, claimed `[3 4]`. Worker 1 marked its jobs done and committed; worker 2 rolled back, simulating a crash, so jobs 3 and 4 went back to `new`. This is the {{< term "skip-locked" "SKIP LOCKED" >}} pattern; compare it with the table-based approach in [the outbox pattern](/posts/go-outbox-pattern-nats/).

## The ALTER TABLE queue

S1 opened a transaction and only read `acct`. S2 ran `ALTER TABLE acct ADD COLUMN` and waited for S1. Then S3 ran a plain `SELECT`:

```text
S3: plain SELECT with lock_timeout 300ms -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
   8550 | AccessShareLock | true | []
   8552 | AccessExclusiveLock | false | [8550]
```

A harmless read was refused, because it queued behind the waiting `ALTER`. On a busy table one forgotten open transaction plus one migration stops everything. Run migrations with a short `lock_timeout` and retry.

## Advisory locks

An {{< term "advisory-lock" "advisory lock" >}} locks a number you pick. A took key 42; B's `pg_try_advisory_lock(42)` returned `false`. After A unlocked, it returned `true`.

## A few things to watch

- Keep transactions short; locks last until commit or rollback.
- Set `lock_timeout` for migrations and `idle_in_transaction_session_timeout` for apps.
- Lock in a fixed order and retry on 40P01.
- Look at `pg_blocking_pids()` before killing anything.

## Exercise

Reproduce the deadlock in two `psql` windows, then fix it with ordering. Then open a transaction, run `ALTER TABLE` from another window and watch `pg_locks`.

## What's next

Next in the series: JSONB and full-text search.
