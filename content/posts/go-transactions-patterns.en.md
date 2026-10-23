+++
date = '2027-01-19T10:00:00+03:30'
draft = false
title = 'Transactions and the repository pattern in Go'
description = 'Go pgx transactions: rollback, a WithTx helper, a unit of work over repositories, lost updates, SELECT FOR UPDATE, serializable retries and N+1 queries.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "transactions", "pgx", "repository"]
cover = { image = "/images/covers/go-transactions-patterns.png", alt = "Transactions and the repository pattern in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-postgres-pgx-sqlc/) the orders service got a real Postgres store, but every call was its own little world. Real work often needs two writes that succeed or fail together. This post covers **transactions** in pgx, how to keep them out of the domain code, and the concurrency problems they do and do not solve.

> Go 1.26, pgx v5.11.0, a real PostgreSQL 18.3 started by the embedded-postgres module, as before. The demo is a local copy of the previous one, with a second migration adding an `accounts` table (balance must be between 0 and 10000, enforced by two named `CHECK` constraints) and an `order_items` table.

## Why a transaction

A transfer is two updates: debit alice, credit carol. Carol has 9950 and her limit is 10000, so crediting 100 must fail. Using the pool directly, each statement commits on its own:

```
before: alice=1000 carol=9950 total=10950
transfer error: account limit exceeded
after : alice=900 carol=9950 total=10850
```

The debit was committed, the credit failed, and 100 disappeared. Now the same transfer inside a transaction:

```
transfer error: account limit exceeded | is ErrLimit: true
after : alice=1000 carol=9950 total=10950
```

Nothing changed. That is atomicity: all of it, or none of it.

## Begin, Commit, Rollback

```go
tx, err := pool.Begin(ctx)
if err != nil {
	return err
}
defer tx.Rollback(ctx) // safe to leave in place
// ... tx.Exec, tx.Query ...
return tx.Commit(ctx)
```

The `defer` guarantees that every early `return` rolls back. After a successful commit the deferred call does nothing harmful; I called it explicitly to see:

```
commit: <nil>
rollback after commit: tx is closed | is ErrTxClosed: true
```

So you just ignore that error. The transaction holds one pooled connection until it ends, so keep it short and never do HTTP calls inside it.

## A WithTx helper

Repeating this block everywhere invites mistakes, so wrap it once:

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

Error means rollback, panic means rollback and re-panic, otherwise commit. I made `fn` update alice to 0 and then panic; after `recovered: boom` her balance was still 1000. pgx also ships `pgx.BeginFunc` with the same idea.

## One repository, pool or transaction

A repository should not care whether it runs inside a transaction. `*pgxpool.Pool` and `pgx.Tx` share these three methods, so the repository depends on a tiny interface, usually called **DBTX**:

```go
type DBTX interface {
	Exec(ctx context.Context, sql string, args ...any) (pgconn.CommandTag, error)
	Query(ctx context.Context, sql string, args ...any) (pgx.Rows, error)
	QueryRow(ctx context.Context, sql string, args ...any) pgx.Row
}

type Repo struct{ db DBTX }
func NewRepo(db DBTX) Repo { return Repo{db: db} }
```

The service must decide the transaction boundary without importing pgx. It owns a **unit of work** interface, and the Postgres package implements it:

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

The repository also maps constraint names to domain errors (`non_negative` becomes `ErrInsufficient`, `under_limit` becomes `ErrLimit`), as in [config, logging and errors](/posts/go-config-logging-errors/). Running the service:

```
transfer 100: <nil>
after : alice=900 carol=100 total=1000
transfer 5000: insufficient funds
after : alice=900 carol=100 total=1000
```

## Lost updates and FOR UPDATE

A transaction alone does not stop two of them from interfering. Two workers each read alice's balance (1000), wait 300 ms, and write `balance + 100`. At the default **READ COMMITTED** level:

```
plain read      : alice=1100 carol=0 total=1100
SELECT FOR UPDATE: alice=1200 carol=0 total=1200
```

Both read 1000, both wrote 1100: one update was lost. The second line is the same code with `SELECT balance ... FOR UPDATE`, which makes the second worker wait for the first to commit and then read the fresh value.

## Serializable and retries

The other approach is `pgx.TxOptions{IsoLevel: pgx.Serializable}`: no locks in your SQL, but Postgres aborts a transaction it cannot order safely:

```
worker 0: <nil>
worker 1: ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
```

This is normal, not a bug, and the answer is to rerun the whole transaction:

```go
func retry(fn func() error) error {
	for attempt := 1; ; attempt++ {
		err := fn()
		var pgErr *pgconn.PgError
		if err == nil || !errors.As(err, &pgErr) || pgErr.Code != "40001" || attempt == 5 {
			return err
		}
	}
}
```

With it, the final balance was 1200 and the two workers needed 3 attempts in total. The function you retry must be safe to run twice, so no emails inside it.

## Deadlocks, briefly

Two transactions that lock alice then carol, and carol then alice, wait for each other. Postgres detected it and killed one:

```
worker 0 (alice then carol): ERROR: deadlock detected (SQLSTATE 40P01)
worker 1 (carol then alice): <nil>
```

Always touch rows in a consistent order (for example sorted by id), and treat 40P01 like 40001: retry.

## N+1 queries

Not a transaction topic, but the same layer. I loaded 20 orders (60 items) and counted queries with a pgx tracer:

```
N+1          orders=20 items=60 queries=21
= ANY($1)    orders=20 items=60 queries=2
JOIN         orders=20 items=60 queries=1
```

One query for the orders plus one per order is the N+1 pattern. `WHERE order_id = ANY($1)` with a slice fetches all items at once; a `JOIN` does it in a single statement. Prefer one of these over a loop of queries.

## A few things to watch

- Keep transactions short; they pin a connection and hold locks.
- Pick one strategy per operation: row locks (`FOR UPDATE`) or serializable plus retry. Do not mix them casually.
- Check `RowsAffected()`: an `UPDATE` on a missing row is not an error.
- Anything that can run twice (a retry) must not have side effects outside the database.
- I counted queries with a tracer in the client; I did not try `pg_stat_statements` here.

## What's next

Next: concurrency patterns in Go, with a worker pool and errgroup.
