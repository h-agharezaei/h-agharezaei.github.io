+++
date = '2026-12-21T10:00:00+03:30'
draft = false
title = 'Isolation levels and anomalies'
description = 'PostgreSQL isolation levels shown with two real concurrent sessions: non-repeatable reads, phantoms, lost updates, write skew and serialization failures.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "isolation", "transactions", "concurrency"]
cover = { image = "/images/covers/db-isolation-levels-anomalies.png", alt = "Isolation levels and anomalies", hiddenInSingle = true }
+++

An account holds 100 and two people withdraw 10 at the same time. We expect 80 to be left. Sometimes 90 is left, with no error and no warning: one of the two withdrawals has silently vanished. This is called a {{< term "lost-update" "lost update" >}}, and PostgreSQL's default level allows it.

In [Transactions and ACID](/posts/db-transactions-acid/) we saw that a transaction guarantees "all or nothing", and a short example showed that one transaction's unfinished work is invisible from outside. That invisibility is the letter I in {{< term "acid" "ACID" >}}, isolation. But that example was the simplest case. When two transactions really get tangled up, harder questions appear: if the other one commits in the middle of my work, what should I see? Each {{< term "isolation-level" "isolation level" >}} answers that differently, and each one allows some strange results and forbids others. The only way I trust to understand them is to deliberately tangle two sessions and watch what happens. The Go side of this is in [Transactions and the Repository pattern in Go](/posts/go-transactions-patterns/); here I want to see why.

> Everything below was re-run on a real PostgreSQL 18.3. A small Go program (a local example) opens two connections to the database and calls them **A** and **B**. Each connection is a session: a separate conversation with the database that has its own transaction. The program runs a fixed list of steps in a fixed order, so the interleaving is always the same and the output is deterministic. The tables: `accounts(id, balance)` with two rows (1, 100) and (2, 50), a table `oncall(doctor, on_duty)` for the doctors example, and the sample `shop` data we use throughout this series. In all outputs, `A>` is a statement session A ran and `->` is its result.

## Four levels, several anomalies

The SQL standard defines four isolation levels: `READ UNCOMMITTED`, `READ COMMITTED`, `REPEATABLE READ` and `SERIALIZABLE`. The further down the list, the more the transactions are kept apart and the fewer anomalies can happen. An "anomaly" is any strange result that could never happen if the transactions ran one after the other. These are the anomalies we will meet:

- **Dirty read:** reading something that has not been committed yet.
- **Non-repeatable read:** I read one row twice and see two different values.
- **Phantom:** I run a query twice and the second time it returns more rows.
- **Lost update:** two people read the same value and each writes a result computed from it; one overwrites the other.
- **Write skew:** two people change different rows and together break a rule that neither would have broken alone.

Let us see which happens at which level, one by one. First the default.

## READ COMMITTED: no dirty reads

`READ COMMITTED` is PostgreSQL's default. Its rule is: **each statement** sees what was committed before that statement began. So something uncommitted is never seen. To be sure, I even asked for `READ UNCOMMITTED`, which according to the standard should allow dirty reads:

```text
A> BEGIN ISOLATION LEVEL READ UNCOMMITTED
A> SHOW transaction_isolation            -> read uncommitted
B> BEGIN
B> UPDATE accounts SET balance = 0 WHERE id = 1
A> SELECT balance FROM accounts WHERE id = 1   -> 100
B> ROLLBACK
```

B set the balance to 0 inside its own transaction but did not commit. A, which asked for `READ UNCOMMITTED`, still saw 100 and never saw the 0. The second line shows that PostgreSQL accepts the requested level and reports it back; but it behaves differently. According to the documentation, PostgreSQL runs `READ UNCOMMITTED` as `READ COMMITTED`, and our run showed exactly that.

## Non-repeatable reads and phantoms

But "each statement sees its own data" has a side effect. If someone else commits in the middle of A's transaction, two statements of A get two different answers. A reads two things, B changes data and commits (B has no `BEGIN`, so each of its statements is its own committed transaction), and A reads the same things again:

```text
A> BEGIN
A> SELECT balance FROM accounts WHERE id = 1               -> 100
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 2
B> UPDATE accounts SET balance = 60 WHERE id = 1
B> INSERT INTO accounts VALUES (3, 70)
A> SELECT balance FROM accounts WHERE id = 1               -> 60
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 3
```

A read the balance of account 1 twice and saw 100 once and 60 the other time: the row changed under A's feet. This is a {{< term "non-repeatable-read" "non-repeatable read" >}}. A also counted the accounts with a balance of at least 50 twice, and got 2 the first time and 3 the second. The reason is a row that did not exist before and appeared (account 3 with 70). A new row showing up like this is called a {{< term "phantom-read" "phantom" >}}. Both are allowed at `READ COMMITTED`. For many applications this is fine, but if A wants to build a report whose figures all come from one moment, it is a problem.

## REPEATABLE READ: one snapshot

The next level fixes this. I ran the same steps with `BEGIN ISOLATION LEVEL REPEATABLE READ`. This time A read 100 and 2 both times, even after B had committed its changes. After A ended its own transaction with `COMMIT`, a fresh read gave 60. The idea is that at this level the transaction takes a **{{< term "snapshot-isolation" "snapshot" >}}** of the committed state of the database the first time it reads something, and from then on reads only from that snapshot. I saw the same on the sample shop data:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
B> INSERT INTO orders (customer_id, status, total_cents) VALUES (1, 'new', 999)
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
A> COMMIT, then the same query                          -> 11
```

Customer 1 has ten orders. B records a new order for them. While A is inside its transaction it still sees 10, and after the transaction ends it sees 11. Note that this differs from what the SQL standard says: the standard allows phantoms at `REPEATABLE READ`, but PostgreSQL hides those too, because of the snapshot.

But it is not free. The cost of the snapshot is paid when writing. If A tries to change a row that someone else changed after A's snapshot was taken, A can no longer trust its old snapshot:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT balance FROM accounts WHERE id = 1               -> 100
B> UPDATE accounts SET balance = balance - 10 WHERE id = 1   (autocommit)
A> UPDATE accounts SET balance = balance - 10 WHERE id = 1
   ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
```

A saw a balance of 100. After that B withdrew 10 and committed. Now A wants to subtract 10 too, but the row A wants to change is no longer the row that was in A's snapshot. PostgreSQL rejects A's transaction with error code `40001`, which means: "I cannot run this consistently with your snapshot; try again."

## Lost update: the 100 and the 90

Now back to the first problem. If the application reads the balance, subtracts 10 in memory and writes the result, this is what happens at `READ COMMITTED`:

```text
A, B: BEGIN;  both SELECT balance -> 100
A> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
B> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
final balance -> 90
```

Both sessions read 100, both worked out in the application that 100 minus 10 is 90, and both wrote 90. Two withdrawals of 10 from 100 should leave 80; here 90 remained and one withdrawal was lost. There was no error either, because from the database's point of view B just wrote the value 90 into the row, and there is nothing to object to.

There are two safe ways, and I ran both and both ended at 80:

- **Let the database do the arithmetic:** `UPDATE accounts SET balance = balance - 10`. While A holds the row lock, B's `UPDATE` **waits**. After A commits, it re-reads the new committed row, subtracts from 90, and gets 80.
- **Lock the row before reading it:** `SELECT balance ... FOR UPDATE`. In our run B's `SELECT` blocked until A committed, then returned 90 (the new value), and B wrote 80.

At `REPEATABLE READ` and `SERIALIZABLE` the same broken code (the one that computes 90 itself) no longer fails silently; it raises an error instead. I ran the same scenario at both levels: B's `UPDATE` failed with `40001`, and the final balance stayed 90 (only A's withdrawal). So instead of silently losing one, the database forces you to redo B's transaction from the start with the fresh balance.

## Write skew: different rows, one rule

A lost update happens when two people change the same row. There is a subtler anomaly where the rows are different. A hospital has a rule: **at least one doctor must stay on duty.** Right now alice and bob are both on duty. Each session first counts the doctors on duty (2, so it is fine), and then takes one doctor off duty, but each a *different* row:

```text
A, B: BEGIN ISOLATION LEVEL REPEATABLE READ; both count -> 2
A> UPDATE oncall SET on_duty = false WHERE doctor = 'alice'
B> UPDATE oncall SET on_duty = false WHERE doctor = 'bob'
A> COMMIT      B> COMMIT      (both succeed)
SELECT * FROM oncall  -> alice, false | bob, false
```

Both commits succeeded and now nobody is on duty. No row was changed twice, so the database saw no conflict; each transaction reasoned correctly from its own snapshot. This is {{< term "write-skew" "write skew" >}}, and `REPEATABLE READ` does not prevent it. At `READ COMMITTED` the same thing happened (I ran the same scenario there too).

The real fix is the `SERIALIZABLE` level. Run the same steps with it:

```text
A> COMMIT   -> COMMIT
B> COMMIT   -> ERROR: could not serialize access due to read/write dependencies among transactions (SQLSTATE 40001)
SELECT * FROM oncall  -> alice, false | bob, true
```

This time B was rejected at `COMMIT`: the database noticed that the result of these two transactions cannot be explained by any one-after-the-other order. alice left, bob stayed, and the rule held. The important point is that the rejected transaction did nothing wrong. So the application must **rerun the whole transaction from the start**; this is the retry loop on {{< term "sqlstate" "SQLSTATE" >}} `40001` written in [Transactions and the Repository pattern in Go](/posts/go-transactions-patterns/). I did not rerun it here.

A lighter way is to lock the rows you count. I ran the same scenario at `READ COMMITTED` with `SELECT doctor FROM oncall WHERE on_duty FOR UPDATE` instead of `count(*)`. B's `SELECT` blocked until A committed and then returned only `bob`, because alice was no longer on duty. So B could see that only one person was left and refuse to leave. The final result was `alice, false | bob, true`. This only works when the rule is about rows that exist; `FOR UPDATE` cannot lock a row that does not exist yet.

## Summary of what I saw

| Anomaly | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
|---|---|---|---|
| Dirty read | not seen (even with READ UNCOMMITTED) | not possible (docs) | not possible (docs) |
| Non-repeatable read | seen | not seen | not possible (docs) |
| Phantom | seen | not seen | not possible (docs) |
| Lost update | seen | error 40001 | error 40001 |
| Write skew | seen | seen | prevented (40001) |

## Concurrency traps

- **`READ COMMITTED` is the default, and every anomaly above except dirty reads is allowed in it.** If your code relies on data staying the same between two reads, by default you have no guarantee.
- **Do the arithmetic in the `UPDATE`, not in the application.** Instead of read, compute and write in application code, prefer `SET x = x - n` or `SELECT ... FOR UPDATE`.
- **Levels above `READ COMMITTED` can fail with `40001`**, both in a statement and at `COMMIT`. Wrap the transaction in a retry loop and put no side effects such as sending an email or an HTTP call inside it, because they would run again on every retry.
- **Our experiments only covered interleaving at the row level.** We did not look at other kinds of locks or at deadlocks (the post [Locks and deadlocks in the database](/posts/db-locks-deadlocks/) covers them), and I did not try other databases.

## Exercise

Rebuild the doctors' write skew yourself with two `psql` windows. First see the rule break at `READ COMMITTED`. Then stop it with `SELECT ... FOR UPDATE` on the rows you count, and then with `SERIALIZABLE`. In each case watch what the second session sees and where it waits or fails.

## What's next

[MVCC and VACUUM](/posts/db-mvcc-vacuum/): we saw A read from an old snapshot at `REPEATABLE READ` while B changed the same row at the same time, with neither blocking the other. Where do the two versions of that row live side by side? The answer is MVCC.
