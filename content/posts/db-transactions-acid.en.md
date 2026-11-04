+++
date = '2026-12-13T10:00:00+03:30'
draft = false
title = 'Transactions and ACID'
description = 'PostgreSQL transactions and ACID with real runs: BEGIN, ROLLBACK, savepoints, constraints, transactional DDL, WAL and synchronous_commit.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "transactions", "acid", "wal"]
cover = { image = "/images/covers/db-transactions-acid.png", alt = "Transactions and ACID", hiddenInSingle = true }
+++

Say alice wants to send bob $30. Your code does two things: it takes 30 dollars out of alice's account, then adds 30 dollars to bob's. Now imagine the process dies right between the two statements, or the second one fails with an error. alice has lost $30, bob has not received it, and the money has vanished from the system.

The database's answer to this problem is the **{{< term "transaction" "transaction" >}}**: a group of statements that the database treats as one unit of work. Either all of them take effect or none of them do. The [previous post](/posts/db-planner-statistics/) was about reading, and how the database decides how to find data. This one is about writing, and how data stays correct after it is written. The application side, how to open a transaction from Go, is in [Transactions and the Repository pattern in Go](/posts/go-transactions-patterns/); here we look at the database itself.

> Every example below was re-run on a real PostgreSQL 18.3, and the outputs are what I saw. I have two small tables. `accounts` holds two rows, alice with 10000 cents and bob with 5000 cents, plus a constraint that a balance can never go negative (`CHECK (balance_cents >= 0)`). `transfers` records transfers and has foreign keys to the accounts. I store money in cents so I do not have to deal with floating-point numbers.

## What does ACID mean?

The guarantees a transaction gives are summarized by four letters, **{{< term "acid" "ACID" >}}**. Here is a quick look at all four before we test them one by one:

- **Atomicity (all or nothing):** a transaction either runs completely or counts as never having run. There is no half-done state.
- **Consistency:** a transaction moves the data from one valid state to another valid state. "Valid" means every constraint you defined still holds.
- **Isolation:** transactions running at the same time do not see each other's unfinished work, up to a point. How far that goes is decided by the isolation level, and the next post is entirely about it.
- **Durability:** once the database has said `COMMIT` succeeded, the change survives even if the power goes out a moment later.

## Autocommit versus BEGIN

If you do not write `BEGIN`, PostgreSQL treats every statement as its own transaction and commits it immediately. This is called autocommit. When I ran `UPDATE accounts SET balance_cents = balance_cents - 3000 WHERE id = 1` that way, alice was at 7000 right away and nobody could take it back, while bob had received nothing yet. A money transfer must stay away from exactly this state. The fix is to put both statements between `BEGIN` and `COMMIT` so they become one unit.

## Atomicity: when an error comes in the middle

Let us see what "all or nothing" means in practice. I put the transfer inside a transaction, but wrote the second statement so that it fails on purpose: instead of 3000 cents it takes 9000 cents from bob, which would leave him negative. The `CHECK` constraint does not allow that. The `psql` output was:

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

Line by line:

- The first statement succeeded (`UPDATE 1`): inside the transaction, alice is now at 7000.
- The second statement failed. `DETAIL` says the row that was about to be written (`bob` with `-4000`) violates the constraint.
- After the error the transaction is in the **aborted** state. From this point to the end of the block PostgreSQL rejects every statement. Even a plain `SELECT 1` fails.
- The last line is the interesting one. We typed `COMMIT`, but the answer was `ROLLBACK`. The database does not let you commit a broken transaction.

Afterwards I read the balances: alice was back at 10000 and bob at 5000. The first statement, which was perfectly fine by itself, had disappeared too. That is atomicity. When I wrote the same transfer correctly (take 3000 from alice, add 3000 to bob, `COMMIT`), the result was 7000 and 8000.

You can also write `ROLLBACK` yourself. Inside a transaction I set alice to 0 and a `SELECT` showed 0; after `ROLLBACK` she was back at 7000. So until `COMMIT`, changes exist only for the transaction itself, and you can throw them away whenever you like.

## Savepoints: undoing only part of the work

Sometimes you do not want one error to throw away the whole transaction. A {{< term "savepoint" "savepoint" >}} is a point you can return to inside a transaction: you roll back only as far as that point, and the transaction stays usable afterwards.

```text
BEGIN;
UPDATE accounts SET balance_cents = balance_cents - 100 WHERE id = 1;
SAVEPOINT s1;
UPDATE accounts SET balance_cents = balance_cents - 99999 WHERE id = 1;   -- CHECK violation
ROLLBACK TO s1;                                                          -- transaction usable again
UPDATE accounts SET balance_cents = balance_cents - 200 WHERE id = 1;
COMMIT;
```

First we subtract 100 cents and set `s1`. Then an impossible subtraction (99999 cents) hits the constraint and fails. Instead of giving up on the transaction, we run `ROLLBACK TO s1`. That undoes only the failed statement, and the transaction can be used again. Then we subtract another 200 cents and `COMMIT`.

alice went from 7000 to 6700: the 100 and the 200 stayed, and the failed statement did not. Without the savepoint, that error would have aborted the entire transaction.

## Consistency: constraints

In ACID, consistency means in practice the constraints you defined yourself: a {{< term "check-constraint" "CHECK constraint" >}}, uniqueness, a {{< term "foreign-key" "foreign key" >}} and so on. We already saw a `CHECK` stop a negative balance. A foreign key does the same for the relationship between tables. This time I took 50 cents from alice and then recorded a transfer to an account with id 99, which does not exist:

```text
ERROR:  insert or update on table "transfers" violates foreign key constraint "transfers_to_id_fkey"
DETAIL:  Key (to_id)=(99) is not present in table "accounts".
```

The insert failed, so the final `COMMIT` became a `ROLLBACK` as well, and alice stayed at 6700: the 50 cents she had lost came back. So even if the application code has a bug, the database refuses to store invalid data. One important point: the database enforces only the rules you declared as constraints. A business rule that is not a constraint, such as "each user may make at most ten transfers a day", is still your job.

## DDL is transactional too (in PostgreSQL)

Transactions are not only for `INSERT` and `UPDATE`. In PostgreSQL, the statements that create and change tables (DDL) live inside transactions too. I opened a transaction, created the table `temp_demo`, inserted a row, and `SELECT count(*)` returned 1. Then I ran `ROLLBACK`. After that `to_regclass('temp_demo')` returned empty (`NULL`): the table had never existed.

This is a PostgreSQL feature. I have not tried other databases, and I know that some of them commit implicitly when you run DDL, so do not assume this behavior elsewhere. In PostgreSQL it makes migrations safer: if a multi-step migration fails halfway, everything goes back to how it was.

## Isolation: a short example

So far there was only one session. But a database serves many connections at once. A small Go program opened two connections, A and B. A started a transaction, took 500 cents from alice and inserted a transfer row. Before the `COMMIT`, both connections read the balance:

```text
A: BEGIN; update alice -500; insert a transfer row
  A sees: alice=6200, transfers=1
  B sees: alice=6700, transfers=0
A: COMMIT
  B sees: alice=6200, transfers=1
```

A sees its own work: 6200 and one transfer. B still sees 6700 and zero transfers, because A has not committed yet. After the `COMMIT`, B sees the change too. (The 6700 comes from continuing the same session of experiments: alice had reached 6700 in the sections above.) So the result of unfinished work is invisible from outside. But this is only the simplest case. What B sees in trickier situations, for example when A commits in the middle of B's own transaction, depends on the isolation level, and that is the subject of the next post.

## Durability: WAL and synchronous_commit

Now the last letter: durability. When `COMMIT` succeeds, the change has to survive a crash. PostgreSQL guarantees this with a simple trick: before it writes a change to the main table files, it writes the change to a sequential log called the {{< term "wal" "WAL" >}} (write-ahead log). At `COMMIT` it flushes that log to disk. If the program or the server dies, then after the database starts again it replays the committed changes from the log. The actual settings of this instance:

```text
synchronous_commit = on     fsync = on     wal_level = replica     full_page_writes = on
```

The most important one is {{< term "synchronous-commit" "synchronous_commit" >}}. When it is `on`, `COMMIT` answers the application only after the WAL has been written to disk.

To see how much WAL each kind of work writes, I read the WAL position with `pg_current_wal_insert_lsn()` before and after each piece of work and computed the difference in bytes. This number is deterministic and does not depend on how fast the machine is:

```text
UPDATE of one row (autocommit):      112 bytes
BEGIN; UPDATE; COMMIT:               112 bytes
BEGIN; COMMIT (empty):                 0 bytes
BEGIN; UPDATE; ROLLBACK:             112 bytes
```

I re-ran these four lines and got exactly these numbers. Two things follow. First, an empty transaction costs nothing (0 bytes). Second, a transaction that was rolled back also wrote WAL, because PostgreSQL writes the change first and only later settles its fate. The cancelled row versions are ignored afterwards, but they were written. (A note on the method: `pg_current_wal_lsn()` is not the right position for this measurement. On my first attempt it showed 0 for the rollback case, because that transaction's data had not been written yet; the insert position, `pg_current_wal_insert_lsn()`, is the right one.)

You might think every `UPDATE` always costs 112 bytes. It does not. In my first run, the first update after startup wrote 4568 bytes. I checked why with `pg_walinspect`: right after a `CHECKPOINT`, the first change to any page puts the whole page (a full-page image) into the WAL, and the next update on the same page writes only 112 bytes. I tried this again this time: after a `CHECKPOINT` the first update wrote 952 bytes and the second wrote 112. The first number depends on how full the page is (our table has only two rows), so it is not the same everywhere; and 112 is the cost of this simple update on this table, not a general rule.

An honest warning: **I did not crash-test durability**, for example by killing the database with `kill -9` in the middle of a commit. So this part rests on the settings above and on the PostgreSQL documentation, not on an experiment.

## Transaction pitfalls

- **Keep transactions short.** A long transaction holds locks and prevents old row versions from being cleaned up. Why that is, I explain in [MVCC and VACUUM](/posts/db-mvcc-vacuum/).
- **Do not wait for a human or the network inside a transaction.** If you wait for a user's answer or an HTTP call between `BEGIN` and `COMMIT`, the transaction and everything it holds stay open for a long time.
- **After an error, the transaction is dead.** As we saw, nothing is accepted until `ROLLBACK` or `ROLLBACK TO` a savepoint. If you use a library that hides this state, be careful.
- **`synchronous_commit = off` is faster, but gives up some durability.** According to the PostgreSQL documentation, with it a crash can lose the last few commits. I did not test that.
- **Do not scatter manual `BEGIN`s through your code.** Write one helper such as `WithTx` that handles the start, `COMMIT` and `ROLLBACK` in one place, so nobody forgets one.

## Exercise

Add the insert into `transfers` to the transfer, so that the transfer row is recorded only when both balances have changed. Make the second update fail by violating the `CHECK`, and use `SELECT` to see that neither the balances nor `transfers` changed. Then repeat it with a `SAVEPOINT` around the insert and see what difference it makes.

## What's next

[Isolation levels and anomalies](/posts/db-isolation-levels-anomalies/): we saw that B does not see A's uncommitted work, but we do not yet know what happens when A commits in the middle of B's transaction. The answer depends on the isolation level.
