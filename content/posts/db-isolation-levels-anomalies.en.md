+++
date = '2026-12-21T10:00:00+03:30'
draft = false
title = 'Isolation levels and anomalies'
description = 'PostgreSQL isolation levels shown with two real concurrent sessions: non-repeatable reads, phantoms, lost updates, write skew and serialization failures.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "isolation", "transactions", "concurrency"]
cover = { image = "/images/covers/db-isolation-levels-anomalies.png", alt = "Isolation levels and anomalies", hiddenInSingle = true }
+++

In the [previous post](/posts/db-transactions-acid/) we met the "I" of {{< term "acid" "ACID" >}}, isolation, as a promise. This post checks the promise. Each {{< term "isolation-level" "isolation level" >}} allows some odd results and forbids others, and the only way I trust that is to watch two sessions interleave. If you write Go, [go-transactions-patterns](/posts/go-transactions-patterns/) used these levels from code; here we see why.

> Everything ran on a real PostgreSQL 18.3. A small Go program (a local example) opens two connections, **A** and **B**, and runs a fixed list of steps in order, so the output is deterministic. Tables: `accounts(id, balance)` with (1, 100) and (2, 50), `oncall(doctor, on_duty)`, plus the shared `shop` seed.

## READ COMMITTED: no dirty reads

This is PostgreSQL's default. Each statement sees data committed before that statement began. I even asked for `READ UNCOMMITTED`:

```text
A> BEGIN ISOLATION LEVEL READ UNCOMMITTED
A> SHOW transaction_isolation            -> read uncommitted
B> BEGIN
B> UPDATE accounts SET balance = 0 WHERE id = 1
A> SELECT balance FROM accounts WHERE id = 1   -> 100
B> ROLLBACK
```

A did not see B's uncommitted 0. According to the docs, PostgreSQL treats READ UNCOMMITTED as READ COMMITTED, and the run agrees.

## Non-repeatable reads and phantoms

At READ COMMITTED, A reads, B commits changes, A reads again:

```text
A> BEGIN
A> SELECT balance FROM accounts WHERE id = 1               -> 100
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 2
B> UPDATE accounts SET balance = 60 WHERE id = 1
B> INSERT INTO accounts VALUES (3, 70)
A> SELECT balance FROM accounts WHERE id = 1               -> 60
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 3
```

The balance changed under A: a {{< term "non-repeatable-read" "non-repeatable read" >}}. The count grew by a row that did not exist before: a {{< term "phantom-read" "phantom" >}}. Both are legal here.

## REPEATABLE READ: a snapshot

Same steps with `BEGIN ISOLATION LEVEL REPEATABLE READ`: A read 100 and 2 both times. After A committed, a fresh read gave 60. On the shop seed it is the same:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
B> INSERT INTO orders (customer_id, status, total_cents) VALUES (1, 'new', 999)
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
A> COMMIT, then the same query                          -> 11
```

A transaction reads one {{< term "snapshot-isolation" "snapshot" >}}. In PostgreSQL that also hides phantoms (the SQL standard would allow them at this level). The price is writes:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT balance FROM accounts WHERE id = 1               -> 100
B> UPDATE accounts SET balance = balance - 10 WHERE id = 1   (autocommit)
A> UPDATE accounts SET balance = balance - 10 WHERE id = 1
   ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
```

A would be updating a row that changed after its snapshot, so PostgreSQL aborts it.

## Lost update

At READ COMMITTED, with the arithmetic done in the application:

```text
A, B: BEGIN;  both SELECT balance -> 100
A> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
B> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
final balance -> 90
```

Two withdrawals of 10 from 100 should leave 80. The {{< term "lost-update" "lost update" >}} left 90. Two safe versions, both verified to end at 80:

- `UPDATE accounts SET balance = balance - 10`: B's UPDATE **waits** for A's lock, then re-reads the committed row and subtracts from 90.
- `SELECT balance ... FOR UPDATE`: B's SELECT blocked until A committed, then returned 90, and B wrote 80.

## Write skew

The rule: at least one doctor stays on duty. Both are on duty. Each session counts the doctors on duty (2), then sets a *different* row to false:

```text
A, B: BEGIN ISOLATION LEVEL REPEATABLE READ; both count -> 2
A> UPDATE oncall SET on_duty = false WHERE doctor = 'alice'
B> UPDATE oncall SET on_duty = false WHERE doctor = 'bob'
A> COMMIT      B> COMMIT      (both succeed)
SELECT * FROM oncall  -> alice, false | bob, false
```

Nobody is on duty. No row was updated twice, so there was no conflict to detect: this is {{< term "write-skew" "write skew" >}}. Rerun with `SERIALIZABLE`:

```text
A> COMMIT   -> COMMIT
B> COMMIT   -> ERROR: could not serialize access due to read/write dependencies among transactions (SQLSTATE 40001)
SELECT * FROM oncall  -> alice, false | bob, true
```

One transaction was aborted and the rule held. The aborted one did nothing wrong, so the application must **rerun the whole transaction**. That is the retry loop on {{< term "sqlstate" "SQLSTATE" >}} 40001 from [go-transactions-patterns](/posts/go-transactions-patterns/). I did not rerun it here.

## What I observed

| Anomaly | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
|---|---|---|---|
| Dirty read | not seen (also with READ UNCOMMITTED) | not possible (docs) | not possible (docs) |
| Non-repeatable read | seen | not seen | not possible (docs) |
| Phantom | seen | not seen | not possible (docs) |
| Lost update | seen | error 40001 | not possible (docs) |
| Write skew | not tested | seen | prevented (40001) |

## A few things to watch

- READ COMMITTED is the default, and every anomaly above except dirty reads is legal in it. Do not assume more.
- The lost update at REPEATABLE READ appeared as an error in my run; I only tried the relative `balance - 10` form.
- Prefer `SET x = x - n` or `FOR UPDATE` over read-modify-write in application code.
- Levels above READ COMMITTED can fail with 40001 at any statement or at COMMIT. Wrap the transaction in a retry, and keep side effects out of it.
- The test used row-level interleaving only; I did not test locks, deadlocks or other databases.

## Exercise

Reproduce the write skew yourself with two `psql` windows, then try to prevent it without SERIALIZABLE, for example by locking the rows you count with `FOR UPDATE`, and check whether it works. I did not run that variant.

## What's next

Next: MVCC and VACUUM, the machinery that makes these snapshots possible.
