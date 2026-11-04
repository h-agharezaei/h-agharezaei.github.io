+++
date = '2027-01-04T10:00:00+03:30'
draft = false
title = 'Locks and deadlocks in the database'
description = 'PostgreSQL locks and deadlocks with real two-session runs: row locks, pg_locks, lock_timeout, a real deadlock and its fix, SKIP LOCKED queues, ALTER TABLE.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "locks", "deadlock", "concurrency"]
cover = { image = "/images/covers/db-locks-deadlocks.png", alt = "Locks and deadlocks in the database", hiddenInSingle = true }
+++

One open transaction that only read from a table, plus an `ALTER TABLE` waiting behind it, is enough to make even a plain, innocent `SELECT` fail. Most "the database is stuck" incidents have this shape: a {{< term "lock" "lock" >}} somebody did not release, and everyone else queued up behind it.

A lock means a session has to wait before touching data until another session that holds it is done. The simplest picture is a room with one key: until the person inside comes out, the next person stands at the door. In [MVCC and VACUUM](/posts/db-mvcc-vacuum/) we saw that {{< term "mvcc" "MVCC" >}} lets readers and writers pass each other, because each sees its own version. But two writers cannot work on the same row at the same time, and one has to wait. This post is about that waiting: what gets locked, which locks conflict, how to find out who is blocking whom, and two stories that almost every team lives through once: the deadlock and the queue behind an `ALTER TABLE`. The groundwork is [Transactions and ACID](/posts/db-transactions-acid/) and [Isolation levels and anomalies](/posts/db-isolation-levels-anomalies/).

> Everything below was re-run on a real PostgreSQL 18.3. Two or three sessions were driven by one small Go program in a fixed order, so the results are deterministic. Process and transaction numbers differ from run to run. The machine was busy, so there are no timings; it is all about how locks behave.

## Row locks

Let us start with the smallest lock: a row lock. Session A runs `SELECT ... WHERE id = 1 FOR UPDATE` on a small `acct` table and keeps the transaction open. `FOR UPDATE` means "lock this row for me, because I am going to change it". Now B tries three different things:

```text
B: UPDATE row 1       -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
B: FOR UPDATE NOWAIT  -> ERROR: could not obtain lock on row in relation "acct" (SQLSTATE 55P03)
B: SKIP LOCKED ids    -> [2 3]
```

- **`UPDATE` on the same row:** B waits. By default PostgreSQL has no time limit on this wait and waits forever; I set `lock_timeout = 300ms` so it gives up after 300 milliseconds. That is the error (`55P03`) you see.
- **`FOR UPDATE NOWAIT`:** does not wait at all. It fails immediately saying it could not get the row lock.
- **`FOR UPDATE SKIP LOCKED`:** skips the locked row and returns only rows nobody holds: `[2 3]`. We will use this for a job queue later.

Next question: not all row locks conflict with each other. PostgreSQL has four row-lock modes. I took each mode for A and tried B with all four (all with `NOWAIT` so it does not hang). "blocked" means B could not get the lock:

```text
A holds \ B asks    FOR KEY SHARE      FOR SHARE          FOR NO KEY UPDATE  FOR UPDATE
FOR KEY SHARE       ok                 ok                 ok                 blocked
FOR SHARE           ok                 ok                 blocked            blocked
FOR NO KEY UPDATE   ok                 blocked            blocked            blocked
FOR UPDATE          blocked            blocked            blocked            blocked
```

Each row is what A holds and each column is what B asks for. The weaker locks (top left) get along with each other, and the strongest, `FOR UPDATE`, conflicts with everything. What matters in practice: a plain `UPDATE` that does not change key columns takes `FOR NO KEY UPDATE`. That lock does not conflict with `FOR KEY SHARE`, and `FOR KEY SHARE` is the lock a {{< term "foreign-key" "foreign key" >}} check takes on the parent row. That is why, when A held a `NO KEY UPDATE` lock on row 1, `INSERT INTO note (acct_id) VALUES (1)` in B went through without trouble. But when A held `FOR UPDATE`, the same `INSERT` got stuck (and failed with `lock_timeout`).

## Table-level locks

Besides rows, every statement also takes a lock on the table itself, which says what other statements it is compatible with. I read `pg_locks` for session A's backend:

```text
after SELECT:                       AccessShareLock
after UPDATE:                       RowExclusiveLock
after ALTER TABLE ... ADD COLUMN:   AccessExclusiveLock
```

`SELECT` takes only the mildest lock, `UPDATE` a bit stronger, and `ALTER TABLE` the strongest. According to the documentation, `AccessExclusiveLock` conflicts with every other mode, even the `AccessShareLock` of a `SELECT`. That is why `ALTER TABLE` and `VACUUM FULL` can stop a table. I saw it: A had an open transaction that had read `acct`, B ran `VACUUM FULL acct`, and `pg_locks` showed A holding an `AccessShareLock` while B's `AccessExclusiveLock` waited with `granted = false`:

```text
   false | AccessShareLock | true
   true | AccessExclusiveLock | false
```

The first column says whether the row belongs to B (`true` means B), the second is the lock type and the third is whether the lock was granted or is still waiting. When A committed, B's command finished. (A small side note: `VACUUM FULL` cannot run inside a transaction block; PostgreSQL gives the error `VACUUM cannot run inside a transaction block`, which is why I ran it from the other session.)

## Who is blocking whom?

When a system is stuck, this is the most important question. A updated row 2 and kept its transaction open. B updated the same row and waited. From a third session I asked:

```text
A is pid 56715, B is pid 56717
   56717 | Lock | transactionid | [56715] | UPDATE acct SET balance=balance+1 WHERE
   locks: transactionid | ShareLock | false
```

The columns of the first line are, in order, for B: `pid`, the wait type (`wait_event_type`), the wait name (`wait_event`), the list of processes blocking B (`pg_blocking_pids`), and the start of the query. `pg_blocking_pids` answers directly: process 56715, which is A. The second line shows that B is waiting for A's transaction number, not for the row itself. That is how row locks work in PostgreSQL: the writer of a row is identified by its transaction number, and the others wait on that number. So when you are stuck, look in `pg_stat_activity` for the blocker; it is often a connection in the `idle in transaction` state.

## Timeouts

Three settings keep a wait from being unlimited. We saw the first: `lock_timeout` produced the `55P03` error. The other two:

```text
statement_timeout 200ms, pg_sleep(2) -> ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
idle in transaction 900ms, next statement -> FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
```

`statement_timeout` limits the total time of one statement (our two-second statement was cancelled after 200 milliseconds). I set `idle_in_transaction_session_timeout` to 300 milliseconds; the session opened a transaction, did nothing for 900 milliseconds, and its next statement met a connection-termination error. This setting kills the connection so that a client that left and never came back does not hold its locks forever.

## A real {{< term "deadlock" "deadlock" >}}

Now the worst case. If two sessions each hold a lock that the other wants, neither can move. The order in this experiment:

```text
A: UPDATE row 1        (A holds row 1)
B: UPDATE row 2        (B holds row 2)
A: UPDATE row 2        (A waits for B)
B: UPDATE row 1        (B waits for A)   -> nobody can continue
```

PostgreSQL does not wait forever. After `deadlock_timeout` (on this instance `SHOW deadlock_timeout` said `1s`) it checks, and if it finds a cycle it cancels one of the sessions. This time B was the victim:

```text
B wants row 1 -> ERROR: deadlock detected (SQLSTATE 40P01)
      DETAIL: Process 56717 waits for ShareLock on transaction 962; blocked by process 56715.
      Process 56715 waits for ShareLock on transaction 963; blocked by process 56717.
      HINT: See server log for query details.
then A -> ok
```

`DETAIL` describes the cycle: process B waits for A's transaction and process A waits for B's. Once B was cancelled, its locks were released and A's statement finished without an error. An important point: the choice of victim is not predictable. In an earlier run of the same experiment A was the victim and B succeeded. If your code depends on one of the two outcomes, it will break.

The fix is a simple rule: **always lock rows in a fixed order**, for example by `id`. When both sessions started from row 1, B only waited until A committed and both finished without errors:

```text
-- fix: both sessions lock rows in id order
B wants row 1 first and waits for A
A commits; B: ok
B second update: ok
```

Even with this rule, your code should retry on `40P01`, because you cannot always guarantee the order (for example when different users reach the rows by different paths).

## A job queue with SKIP LOCKED

Locks are not only a nuisance; you can use them. Imagine a table of jobs and several workers that want to pick up jobs at the same time. I put six rows in `jobs`, and each worker runs this query:

```sql
SELECT id FROM jobs WHERE state='new' ORDER BY id LIMIT 2 FOR UPDATE SKIP LOCKED
```

Worker 1 took `[1 2]` and kept its transaction open. Worker 2, at the same moment, took `[3 4]`: it skipped the rows worker 1 had locked and did not wait. Then worker 1 marked its jobs `done` and committed. Worker 2 rolled back, to simulate a crash. The result:

```text
   1 | done
   2 | done
   3 | new
   4 | new
   5 | new
   6 | new
```

Jobs 1 and 2 are done, and jobs 3 and 4, which worker 2 had taken before it "died", are `new` again so someone else can pick them up. No job was taken twice. This is the {{< term "skip-locked" "SKIP LOCKED" >}} pattern; compare it with the table-based approach in [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/).

## The queue behind ALTER TABLE

Now back to the opening incident. S1 opened a transaction and only read from `acct`; it has not committed. S2 ran `ALTER TABLE acct ADD COLUMN` and, since `AccessExclusiveLock` conflicts with S1's read lock, waited. Then S3 ran a plain `SELECT`:

```text
S3: plain SELECT with lock_timeout 300ms -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
   56715 | AccessShareLock | true | []
   56717 | AccessExclusiveLock | false | [56715]
```

A perfectly harmless read was rejected. Why? S3 has no problem with S1, but the `AccessExclusiveLock` waiting for S1 blocks every new lock that would conflict with it, so S3's `SELECT` stood in line behind S2. The two lines at the bottom show this: S1 holds its lock (`true`), and S2 waits (`false`), with `[56715]` saying it is waiting for S1. On a busy table, one forgotten transaction plus one migration stops everything. The remedy is to run the migration with a short `lock_timeout` and try again later if it fails, instead of making everyone queue behind it. When S1 committed, the `ALTER` finished and S3's `SELECT` worked again.

## Advisory locks

Sometimes you want to lock something that is not a row or a table, for example "only one instance of this job may run at a time". An {{< term "advisory-lock" "advisory lock" >}} is a lock on a number you choose; the database enforces the lock but attaches no meaning to the number. A took key 42 and `pg_try_advisory_lock(42)` in B returned `false`. After A released it, the same call returned `true`.

## How not to get stuck

- **Keep transactions short.** Locks stay until commit or rollback.
- **Set timeouts.** A short `lock_timeout` for migrations and `idle_in_transaction_session_timeout` for the application, so a forgotten transaction does not hold everyone up.
- **Lock rows in a fixed order** and retry on `40P01`.
- **Look at `pg_blocking_pids()` before killing a connection.** Find the real blocker, not just the victim.

## Exercise

Reproduce the deadlock in two `psql` windows and fix it with a fixed order. Then open a transaction that only reads from a table, run `ALTER TABLE` from another window and a `SELECT` from a third. Look at `pg_locks` and work out how the queue formed.

## What's next

[JSONB and full-text search](/posts/db-jsonb-fulltext-search/): so far we talked about concurrency. Now it is the shape of the data: how to search inside JSON and text.
