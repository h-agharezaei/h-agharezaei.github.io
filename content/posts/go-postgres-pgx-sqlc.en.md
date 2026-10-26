+++
date = '2027-01-09T10:00:00+03:30'
draft = false
title = 'Postgres with pgx and sqlc in Go'
description = 'Use PostgreSQL in Go with pgx and sqlc: migrations, a connection pool, query deadlines, SQL injection and the same service test, on the orders service.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "pgx", "sqlc", "sql"]
cover = { image = "/images/covers/go-postgres-pgx-sqlc.png", alt = "Postgres with pgx and sqlc in Go", hiddenInSingle = true }
+++

In the [previous post](/posts/go-http-api-stdlib/) the orders API stored everything in a map. Now we give it a real database. The `Repository` interface lives in the service, as we set up in [project layout and clean architecture](/posts/go-project-layout-clean-architecture/), so a Postgres store is just a second implementation of it. We use **pgx** (the Postgres driver and toolkit) directly first, then generate the same store with **sqlc**.

> Everything ran with Go 1.26 on macOS against a real PostgreSQL 18.3. There is no Docker here, so the demo starts real Postgres binaries with the `embedded-postgres` module (v1.34.0) on a free port. pgx is v5.11.0, sqlc is v1.31.1.

## Schema as plain SQL migrations

The migration file is the source of truth for the schema:

```sql
CREATE TABLE orders (
    id         text        PRIMARY KEY,
    customer   text        NOT NULL,
    cents      bigint      NOT NULL CHECK (cents > 0),
    status     text        NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'paid')),
    created_at timestamptz NOT NULL DEFAULT now()
);
```

A tiny runner embeds `*.sql`, creates a `schema_migrations` table, and applies each unseen file in order inside a transaction. Running it twice applied the file once. Tools like goose or golang-migrate do this better (down migrations, locking); I only wrote the runner to keep the demo self-contained.

## Why a pool, and how to configure it

A single `pgx.Conn` handles one query at a time. A server handles many requests at once, and opening a connection per request is slow and can exhaust Postgres. `pgxpool` keeps a bounded set of connections and lends them out:

```go
cfg, err := pgxpool.ParseConfig(url)
cfg.MaxConns = 10
cfg.MinConns = 2
cfg.MaxConnLifetime = 30 * time.Minute
cfg.MaxConnIdleTime = 5 * time.Minute
cfg.ConnConfig.ConnectTimeout = 5 * time.Second
pool, err := pgxpool.NewWithConfig(ctx, cfg)
// then pool.Ping with a 3s timeout, so a bad URL fails at startup
```

Pick `MaxConns` from what the database can serve across all your instances, not from your CPU count.

## Query, QueryRow, Exec and CollectRows

`Exec` is for statements without rows, `QueryRow` for one row, `Query` for many. `pgx.CollectRows` with `pgx.RowToStructByName` turns rows into structs by column name. The struct carries the `db` tags, so `domain.Order` stays free of SQL:

```go
type row struct {
	ID        string    `db:"id"`
	Customer  string    `db:"customer"`
	Cents     int64     `db:"cents"`
	Status    string    `db:"status"`
	CreatedAt time.Time `db:"created_at"`
}

func (s *Store) Get(ctx context.Context, id string) (domain.Order, error) {
	rows, err := s.pool.Query(ctx, `SELECT * FROM orders WHERE id = $1`, id)
	if err != nil {
		return domain.Order{}, err
	}
	r, err := pgx.CollectOneRow(rows, pgx.RowToStructByName[row])
	if errors.Is(err, pgx.ErrNoRows) {
		return domain.Order{}, domain.ErrNotFound
	}
	if err != nil {
		return domain.Order{}, err
	}
	return r.order(), nil
}
```

The store translates `pgx.ErrNoRows` into `domain.ErrNotFound`, so the service and the handler never learn which database is underneath (error mapping is covered in [config, logging and errors](/posts/go-config-logging-errors/)). `Save` is an `INSERT ... ON CONFLICT (id) DO UPDATE`, the same overwrite behaviour as the map. Run against the real server:

```
server_version: 18.3
applied 001_create_orders.sql
created {ID:4b3eb9b446634c1d Customer:ali Cents:1500 Status:new}
created {ID:67f26923bf79850f Customer:ali Cents:700 Status:new}
created {ID:21db0354404073a9 Customer:sara Cents:999 Status:new}
ali has 2 orders: [{ID:4b3eb9b446634c1d ...} {ID:67f26923bf79850f ...}]
get missing: order not found | is ErrNotFound: true
bad insert: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
```

The last line is the `CHECK` firing when I bypassed the domain rule: the database is the last line of defence.

## Deadlines on queries

Every pgx call takes a `context`. I ran `pg_sleep(5)` with a 300 ms deadline:

```go
qctx, cancel := context.WithTimeout(ctx, 300*time.Millisecond)
defer cancel()
_, err := pool.Exec(qctx, `SELECT pg_sleep(5)`)
```

```
pg_sleep(5) with 300ms deadline: timeout: context deadline exceeded (after ~300ms) | is DeadlineExceeded: true
next query: 1 <nil>
```

`errors.Is(err, context.DeadlineExceeded)` works, the call returned at the deadline instead of after five seconds, and the pool served the next query normally. Pass the request context down so a client that disconnects also cancels its query.

## SQL injection, for real

Two lookups on the same table, one concatenating the input and one using `$1`:

```go
q := "SELECT id FROM orders WHERE customer = '" + customer + "'" // do not do this
rows, err := pool.Query(ctx, `SELECT id FROM orders WHERE customer = $1`, customer)
```

```
input "sara"           concatenated: 1 rows <nil> | parameterized: 1 rows <nil>
input "x' OR '1'='1"   concatenated: 3 rows <nil> | parameterized: 0 rows <nil>
```

The hostile input made the concatenated query return all three orders; the parameterized one treated it as a customer name and found nothing. Parameters travel separately from the SQL text, so they can never change its structure. Only values can be parameters: table and column names cannot, so whitelist those.

## sqlc: generate the boring part

With sqlc you write SQL and get typed Go. The config reads the migrations folder as the schema:

```yaml
version: "2"
sql:
  - engine: "postgresql"
    schema: "migrations"
    queries: "query.sql"
    gen:
      go:
        package: "db"
        out: "internal/store/sqlcstore/db"
        sql_package: "pgx/v5"
```

`query.sql` has three annotated queries (`GetOrder :one`, `ListOrdersByCustomer :many`, `UpsertOrder :exec`). I ran `go run github.com/sqlc-dev/sqlc/cmd/sqlc@v1.31.1 generate` and got these signatures:

```go
func (q *Queries) GetOrder(ctx context.Context, id string) (Order, error)
func (q *Queries) ListOrdersByCustomer(ctx context.Context, customer string) ([]Order, error)
func (q *Queries) UpsertOrder(ctx context.Context, arg UpsertOrderParams) error
```

I added a query selecting a column `total` that is not in the schema, and `generate` failed with `query.sql:13:8: column "total" does not exist`, so mistakes surface before anything runs. The generated `Order` uses `pgtype.Timestamptz`, which is why my store maps it to `domain.Order` by hand.

## One test, three stores

The service-level checks live in a helper that takes any `service.Repository`: create then get, invalid order rejected, missing order is `ErrNotFound`. The memory store, the pgx store and the sqlc store all run it, and each has the guard `var _ service.Repository = (*Store)(nil)`:

```
$ go test -v ./internal/store/postgres
--- PASS: TestService (0.00s)
    --- PASS: TestService/create_then_get (0.00s)
    --- PASS: TestService/invalid_order_is_rejected (0.00s)
    --- PASS: TestService/missing_order_is_ErrNotFound (0.00s)
PASS
```

The sqlc package passed the same subtests. The service code did not change at all.

## A few things to watch

- `SELECT *` with `RowToStructByName` fails if the struct and columns differ, which is useful, but list columns explicitly in production queries.
- Always `defer cancel()` after `WithTimeout`, and set a deadline at the edge of every request.
- Keep the pool in `main` and close it on shutdown.
- sqlc output is code you commit; regenerate it in CI and fail on a diff.
- Embedded Postgres is convenient for tests but downloads binaries on first run; a CI service container is the other common option.

## What's next

Next: transactions and the repository pattern in Go, where several writes must succeed or fail together.
