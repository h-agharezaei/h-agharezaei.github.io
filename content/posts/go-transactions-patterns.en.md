+++
date = '2027-01-19T10:00:00+03:30'
draft = false
title = 'Transactions and the repository pattern in Go'
description = 'Go pgx transactions: rollback, a WithTx helper, a unit of work over repositories, lost updates, SELECT FOR UPDATE, serializable retries and N+1 queries.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "transactions", "pgx", "repository"]
cover = { image = "/images/covers/go-transactions-patterns.png", alt = "Transactions and the repository pattern in Go", hiddenInSingle = true }
+++

Alice sends Carol 100. The code does two things: it takes 100 from Alice's balance, then adds 100 to Carol's. Now suppose Carol is already close to her account limit, so the second step fails. What happens to the first one? If nothing undoes it, Alice has lost 100, Carol has not received it, and the money is simply gone from the system.

This is the situation every service that writes to a database meets sooner or later: one business operation needs two or more writes, and either all of them must happen or none of them. The tool for this is the **{{< term "transaction" "transaction" >}}**. In the store from [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/) every call is its own little world, so there is nothing yet that ties two calls together. In this post we first reproduce the lost money, then fix it with a transaction, then look at how to keep transactions out of the business code, and finally at the problems a transaction does not solve by itself: two clients touching the same row at the same time.

> Everything was re-run with Go 1.27 on macOS (arm64), pgx v5.11.0 and a real PostgreSQL 18.3 started by the embedded-postgres module, as in the previous post. The demo is a local copy of the previous one, with a second migration that adds an `accounts` table and an `order_items` table. The `accounts` table has a `balance` column, and two named `CHECK` constraints keep it between 0 and 10000. The demo is a local example, not a published repo.

## The broken version: no transaction

The idea of a transaction is simple: a group of statements that the database treats as one unit. All of them take effect, or none of them do. To see why we need it, I first wrote the transfer without one. The repository has `Debit` and `Credit` methods, and each one runs a single `UPDATE`:

```go
func (r Repo) add(ctx context.Context, id string, delta int64) error {
	tag, err := r.db.Exec(ctx,
		`UPDATE accounts SET balance = balance + $2 WHERE id = $1`, id, delta)
	// ... maps the CHECK constraint names to ErrInsufficient / ErrLimit ...
}
```

The repository here is built on the connection pool directly, so the transfer is just two calls in a row:

```go
r := pgbank.NewRepo(pool)
err := r.Debit(ctx, "alice", 100)
if err == nil {
	err = r.Credit(ctx, "carol", 100)
}
```

Without a transaction, Postgres treats each statement as a transaction of its own and commits it as soon as it finishes. So the debit is permanent before the credit even starts. Alice has 1000, Carol has 9950, and the account limit is 10000, so the credit of 100 must fail. The output:

```
before: alice=1000 carol=9950 total=10950
transfer error: account limit exceeded
after : alice=900 carol=9950 total=10850
```

The last number in each line is the sum of both balances. It should never change in a transfer. It went from 10950 to 10850: the debit was committed, the credit was refused by the `CHECK` constraint, and 100 disappeared.

Now the same transfer inside a transaction:

```
transfer error: account limit exceeded | is ErrLimit: true
after : alice=1000 carol=9950 total=10950
```

The credit still fails with the same error, but this time the debit is undone as well, and the total is back to 10950. The property we just saw is called **atomicity**: all of it, or none of it. (It is the "A" in {{< term "acid" "ACID" >}}.)

## Begin, Commit, Rollback

A transaction has three moves. `Begin` opens it. Everything you run on it afterwards is held back from other clients. `Commit` makes all of it permanent at once. `Rollback` throws all of it away. In pgx it looks like this:

```go
tx, err := pool.Begin(ctx)
if err != nil {
	return err
}
defer tx.Rollback(ctx) // safe to leave in place
// ... tx.Exec, tx.Query ...
return tx.Commit(ctx)
```

The `defer` line is the important one. Whatever happens in the middle, an early `return` after an error or a panic, the transaction is rolled back and the connection goes back to the pool. After a successful `Commit` the deferred `Rollback` has nothing left to do. I called it explicitly once to see what it says:

```
commit: <nil>
rollback after commit: tx is closed | is ErrTxClosed: true
```

The commit worked (`<nil>` means no error), and the second call returned `pgx.ErrTxClosed`, which is harmless. This is why the `defer` can stay in place on the success path and you simply ignore its error.

One cost to keep in mind: a transaction holds on to one connection from the pool until it ends. So keep transactions short, and do not make HTTP calls or other slow work inside one.

## A WithTx helper

Writing this block in every function invites mistakes: forgetting the rollback on one branch, or forgetting to handle a panic. So I wrap it once:

```go
func WithTx(ctx context.Context, pool *pgxpool.Pool, opts pgx.TxOptions, fn func(pgx.Tx) error) error {
	tx, err := pool.BeginTx(ctx, opts)
	if err != nil {
		return err
	}
	defer func() {
		if p := recover(); p != nil {
			_ = tx.Rollback(ctx)
			panic(p)
		}
	}()
	if err := fn(tx); err != nil {
		_ = tx.Rollback(ctx)
		return err
	}
	return tx.Commit(ctx)
}
```

The rule has three lines. If `fn` returns an error, roll back and return it. If `fn` panics, roll back and let the panic continue. Otherwise commit. To test the panic case, the demo makes `fn` set Alice's balance to 0 and then panic with `"boom"`:

```
recovered: boom
after : alice=1000 carol=0 total=1000
```

The `recovered: boom` line comes from a `recover` in the demo, outside `WithTx`. Alice's balance is still 1000, so the half-finished `UPDATE` was rolled back. As far as I know from the pgx docs, pgx also ships a similar helper, `pgx.BeginFunc`; I wrote my own here so that the panic handling is visible.

## Keeping the transaction out of the domain code

We now have a transaction, but there is a design question. The service decides what belongs together (debit and credit in one transfer). The repository knows SQL. How can the service say "do these together" without importing pgx and without knowing about `tx`?

First, the repository should not care whether it runs inside a transaction or not. `*pgxpool.Pool` and `pgx.Tx` both have the same three methods, so the repository depends on a tiny interface. People often call it **DBTX**:

```go
type DBTX interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type Repo struct{ db DBTX }
func NewRepo(db DBTX) Repo { return Repo{db: db} }
```

You can hand `NewRepo` the pool (every call commits alone, as in the broken version) or a `tx` (every call joins the transaction). The same repository code works in both cases.

Second, the service owns the decision about the boundary through an interface called a {{< term "unit-of-work" "unit of work" >}}: "run this function so that everything inside it commits or rolls back together". The service package declares it and does not import pgx. The Postgres package implements it:

```go
// package bank (no pgx import)
type UnitOfWork interface {
	Do(ctx context.Context, fn func(Accounts) error) error
}

func (s *Service) Transfer(ctx context.Context, from, to string, cents int64) error {
	return s.uow.Do(ctx, func(a Accounts) error {
		if err := a.Debit(ctx, from, cents); err != nil {
			return err
		}
		return a.Credit(ctx, to, cents)
	})
}

// package pgbank
func (u UoW) Do(ctx context.Context, fn func(bank.Accounts) error) error {
	return WithTx(ctx, u.Pool, pgx.TxOptions{}, func(tx pgx.Tx) error {
		return fn(NewRepo(tx))
	})
}
```

Read `Transfer` as a plain sentence: "in one unit of work, debit and then credit". The service has no idea that a transaction exists. `Do` opens it, gives `fn` a repository bound to it, and commits or rolls back depending on what `fn` returns. This has the same shape as the repository interface in the earlier posts: the service declares what it needs, and the database package satisfies it ([project layout and clean architecture](/posts/go-project-layout-clean-architecture/)).

One more detail: the repository translates the constraint names to domain errors (`non_negative` becomes `ErrInsufficient`, `under_limit` becomes `ErrLimit`), in the same way as in [config, logging and errors](/posts/go-config-logging-errors/). Running the service twice, once with a valid amount and once with an amount larger than the balance:

```
transfer 100: <nil>
after : alice=900 carol=100 total=1000
transfer 5000: insufficient funds
after : alice=900 carol=100 total=1000
```

The first transfer moved 100 and the total stayed 1000. The second tried to move 5000 from a balance of 900, the `non_negative` constraint refused it, and nothing changed.

## Two transactions at once: the lost update

So far there was one transaction at a time. A real server runs many at once, and a transaction alone does not stop two of them from stepping on each other. Here is the classic example. Two workers each want to add 100 to Alice's balance. Each one does three things: read the balance, think for a moment (the demo sleeps 300 ms so the two workers overlap), and write `balance + 100`. If they run one after the other, Alice ends with 1200. But watch what happens when they overlap:

```
plain read      : alice=1100 carol=0 total=1100
SELECT FOR UPDATE: alice=1200 carol=0 total=1200
```

In the first line both workers read 1000, both computed 1100, and both wrote 1100. One of the two additions vanished. This is called a {{< term "lost-update" "lost update" >}}. It happens at Postgres's default {{< term "isolation-level" "isolation level" >}}, **READ COMMITTED**, where each statement sees whatever was committed before it started. Both reads happened before either write, so both saw 1000.

The second line is the same code, but the read is `SELECT balance ... FOR UPDATE`. That asks Postgres to take a lock on the row (a {{< term "lock" "row lock" >}}) while reading it. The second worker's `SELECT` now has to wait until the first transaction commits, and then it reads the fresh value of 1100. The result is the expected 1200.

## The other way: serializable and retries

Locking is one way to be safe. The other is to ask Postgres for the strictest isolation level, **SERIALIZABLE**: you write ordinary SQL with no `FOR UPDATE`, and Postgres makes sure the result is the same as if the transactions had run one at a time. When it cannot guarantee that, it aborts one of them:

```go
pgx.TxOptions{IsoLevel: pgx.Serializable}
```

```
worker 1: <nil>
worker 0: ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
no retry: alice=1100 carol=0 total=1100
```

One worker succeeded and the other got an error with the {{< term "sqlstate" "SQLSTATE" >}} code `40001`. The balance is 1100, so only one addition was applied. Which worker is the one that fails changes from run to run, because it depends on timing. This failure is not a bug in your code. It is how serializable mode works, and the answer is to run the whole transaction again:

```go
func retry(fn func() error) error {
	for attempt := 1; ; attempt++ {
		err := fn()
		if err == nil || !isCode(err, "40001") || attempt == 5 {
			return err
		}
		fmt.Printf("  attempt %d failed with 40001, retrying\n", attempt)
	}
}
```

(`isCode` is a small helper in the demo that uses `errors.As` to find the `*pgconn.PgError` and compare its `Code`.) With the retry wrapped around the same two workers:

```
  attempt 1 failed with 40001, retrying
with retry: alice=1200 carol=0 total=1200
total attempts: 3
```

The final balance is the expected 1200. One worker needed two attempts and the other one, so three attempts in total. Two rules come with this. The function you retry must be safe to run twice, so do not send an email inside it. And retry the whole transaction, not just the last statement, because the earlier reads may be stale now.

## Deadlocks

Locks bring one more problem. Suppose transaction A locks Alice and then wants Carol, while transaction B locked Carol first and now wants Alice. Each waits for the other forever. This is a {{< term "deadlock" "deadlock" >}}. Postgres notices it (by default after waiting about a second, according to its docs) and kills one of the two:

```
  worker 1 (carol then alice): ERROR: deadlock detected (SQLSTATE 40P01)
  worker 0 (alice then carol): <nil>
```

Again, which worker is the victim varies. The best defence is to always touch rows in the same order, for example sorted by id, so that the circular wait can never form. And because `40P01` also means "run it again", treat it like `40001` in your retry helper.

## N+1 queries

This one is not about transactions, but it lives in the same repository layer and costs a lot, so I include it. Say you load 20 orders, and each order has items. The tempting code loads the orders with one query and then loops over them, running one more query per order. That is 1 + 20 queries: the {{< term "n-plus-one" "N+1" >}} pattern. I counted queries with a pgx tracer (a hook that pgx calls on every query) for three versions of the same loading code, with 20 orders and 60 items:

```
N+1          orders=20 items=60 queries=21
= ANY($1)    orders=20 items=60 queries=2
JOIN         orders=20 items=60 queries=1
```

The loop sends 21 queries. `WHERE order_id = ANY($1)` takes the whole slice of ids as one parameter and fetches all items in a second query, so 2 in total. A `JOIN` gets orders and items in a single statement. The data is the same; only the number of round trips to the database changes. I counted queries in the client with the tracer; I did not look at `pg_stat_statements` here.

## Where transactions bite

- **Long transactions hurt.** A transaction pins a pooled connection and holds its locks until it ends. Keep it short and do not call other services from inside it.
- **Choose one strategy per operation.** Either take row locks with `FOR UPDATE`, or use SERIALIZABLE and retry. Mixing them casually makes it hard to say what is guaranteed.
- **Check `RowsAffected()`.** An `UPDATE` on a row that does not exist is not an error, it just changes zero rows. That is why `add` returns `ErrNotFound` when the count is zero.
- **Code that can run twice must not have side effects outside the database.** A retry may run your function again, and an email or a payment call inside it would then happen twice.

## What's next

So far the concurrency in this post happened between database clients. The next post, "Concurrency patterns: worker pool and errgroup", moves to concurrency inside the Go process itself: many goroutines, and how to keep them under control.
