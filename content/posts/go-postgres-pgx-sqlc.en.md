+++
date = '2027-01-09T10:00:00+03:30'
draft = false
title = 'Postgres with pgx and sqlc in Go'
description = 'Use PostgreSQL in Go with pgx and sqlc: migrations, a connection pool, query deadlines, SQL injection and the same service test, on the orders service.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "postgres", "pgx", "sqlc", "sql"]
cover = { image = "/images/covers/go-postgres-pgx-sqlc.png", alt = "Postgres with pgx and sqlc in Go", hiddenInSingle = true }
+++

So far the `orders` service keeps its data in a map. Restart the process and every order is gone. A real service needs a database, and for Go backends that very often means PostgreSQL. The question is what that costs the rest of the code. If the service logic has to change because the storage changed, something is wrong with the layout.

Here it does not change. One service test passes against the in-memory store, a store written with pgx, and a store generated with sqlc. That works because `Repository` is declared by the service ([project layout and clean architecture](/posts/go-project-layout-clean-architecture/)), so Postgres is just a second implementation of an interface that already exists. The service in this demo is the one from that post; the `net/http` handlers of [the previous post](/posts/go-http-api-stdlib/) sit on top of the same interface. I did not wire the Postgres store into that HTTP server in this demo; the checks run at the service level.

We use two tools. **pgx** is the Postgres driver and toolkit for Go: the library that opens connections, sends SQL and reads results. **sqlc** is a code generator: you write plain SQL, and it generates type-safe Go functions for it. We use pgx directly first, to see what is going on, then generate the same store with sqlc.

> Everything was re-run with Go 1.27 on macOS (arm64) against a real PostgreSQL 18.3. There is no Docker on this machine, so the demo starts real Postgres binaries with the `embedded-postgres` module (v1.34.0) on a random free port, with a temporary data directory that is deleted at the end. pgx is v5.11.0. IDs in the outputs are random, so they differ from run to run.

## Schema as plain SQL migrations

Before the code can store anything, the table must exist. A {{< term "migration" "migration" >}} is a numbered SQL file that moves the schema forward, and the set of migration files is the history of your schema. Here the migration file is the single source of truth:

```sql
CREATE TABLE orders (
    id         text        PRIMARY KEY,
    customer   text        NOT NULL,
    cents      bigint      NOT NULL CHECK (cents > 0),
    status     text        NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'paid')),
    created_at timestamptz NOT NULL DEFAULT now()
);
```

Notice the two `CHECK` clauses. They repeat rules the domain already enforces. This is deliberate: the database is the last line of defence, and we will see it fire later.

A tiny runner embeds the `*.sql` files in the binary, creates a `schema_migrations` table, and applies each file that is not yet recorded there, in order, inside a transaction. I ran it twice in a row and the second run did nothing, so the output shows the file applied once. Tools like goose or golang-migrate do this better (down migrations, locking between instances). I wrote the runner myself only to keep the demo self-contained.

## Why a pool, and how to configure it

A single `pgx.Conn` handles one query at a time. A server handles many requests at the same time, and opening a new connection for each request is slow and can exhaust Postgres, which has a limit on connections. A {{< term "connection-pool" "connection pool" >}} (`pgxpool`) keeps a bounded set of open connections and lends one out for each query:

```go
cfg, err := pgxpool.ParseConfig(url)
cfg.MaxConns = 10
cfg.MinConns = 2
cfg.MaxConnLifetime = 30 * time.Minute
cfg.MaxConnIdleTime = 5 * time.Minute
cfg.HealthCheckPeriod = time.Minute
cfg.ConnConfig.ConnectTimeout = 5 * time.Second
pool, err := pgxpool.NewWithConfig(ctx, cfg)
// then pool.Ping with a 3s timeout, so a bad URL fails at startup
```

What each setting means: `MaxConns` is the most connections the pool will open, and `MinConns` is how many it keeps ready. `MaxConnLifetime` and `MaxConnIdleTime` retire connections that are old or unused. `HealthCheckPeriod` is how often the pool checks its idle connections. `ConnectTimeout` limits how long opening one may take. The final `Ping` makes a wrong URL or a database that is down fail at startup instead of at the first request.

Pick `MaxConns` from what the database can serve across all your instances together, not from your CPU count: ten instances with `MaxConns = 10` can open a hundred connections.

## Query, QueryRow, Exec and CollectRows

In pgx, `Exec` is for statements that return no rows, `QueryRow` is for one row, and `Query` is for many. To turn rows into Go values, `pgx.CollectRows` and `pgx.RowToStructByName` map columns to struct fields by name. The struct carries the `db` tags, so `domain.Order` stays free of SQL:

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

`$1` is a placeholder for the first parameter; we meet it again in the injection section. The important line is the one that handles `pgx.ErrNoRows`: the store translates it into `domain.ErrNotFound`, so the service and the handler never learn which database is underneath (the mapping to HTTP codes is in [config, logging and errors](/posts/go-config-logging-errors/)). `Save` is an `INSERT ... ON CONFLICT (id) DO UPDATE`, which gives the same "overwrite" behaviour as assigning to a map key.

The demo program creates three orders through the service, lists one customer's orders, asks for a missing one, and finally inserts a bad row directly, bypassing the domain. It also prints a few lines about the server. This is the real output:

```
server_version: 18.3
applied 001_create_orders.sql
pool max conns: 10
created {ID:11e486ac452931b4 Customer:ali Cents:1500 Status:new}
created {ID:49b2cbb9c8bd1ea1 Customer:ali Cents:700 Status:new}
created {ID:6d623fe5f1ed1ada Customer:sara Cents:999 Status:new}
ali has 2 orders: [{ID:11e486ac452931b4 Customer:ali Cents:1500 Status:new} {ID:49b2cbb9c8bd1ea1 Customer:ali Cents:700 Status:new}]
get missing: order not found | is ErrNotFound: true
bad insert: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
```

Line by line: the first two lines say which Postgres version answered and that the migration ran. The pool reports its limit of 10. The three `created` lines are the orders, with random IDs made in Go. The next line lists only `ali`'s two orders. Then a missing ID returns `order not found`, and `errors.Is` confirms it is our `ErrNotFound`, not a pgx error. The last line is the {{< term "check-constraint" "CHECK constraint" >}} firing when I inserted `cents = -5` directly into the table: the database refused it and reported a {{< term "sqlstate" "SQLSTATE" >}} code, `23514`. The domain rule never ran for this insert, which is the point: even if some code path forgets the rule, the data stays valid.

## Deadlines on queries

A query can be slow: a lock, a missing index, an overloaded server. Every pgx call takes a {{< term "context" "context" >}}, so you can put a deadline on it. To see it work, I ran Postgres's `pg_sleep(5)`, a query that does nothing for five seconds, with a deadline of 300 ms:

```go
qctx, cancel := context.WithTimeout(ctx, 300*time.Millisecond)
defer cancel()
_, err := pool.Exec(qctx, `SELECT pg_sleep(5)`)
```

```
pg_sleep(5) with 300ms deadline: timeout: context deadline exceeded (after ~300ms) | is DeadlineExceeded: true
next query: 1 <nil>
```

The first line shows that the call returned after about 300 ms, not five seconds, and that `errors.Is(err, context.DeadlineExceeded)` works on the error. The second line shows that the pool is still healthy: the next query, `SELECT 1`, returned `1` with no error. In a server, pass the request's context down to these calls, so that a client who disconnects also cancels its query.

## SQL injection, for real

Why did the examples above use `$1` instead of building the string? Here are two lookups on the same table: one concatenates the input into the SQL text, and one uses a placeholder. The demo runs both with a normal name and with a hostile input:

```go
q := "SELECT id FROM orders WHERE customer = '" + customer + "'" // do not do this
rows, err := pool.Query(ctx, `SELECT id FROM orders WHERE customer = $1`, customer)
```

```
input "sara"           concatenated: 1 rows <nil> | parameterized: 1 rows <nil>
input "x' OR '1'='1"   concatenated: 3 rows <nil> | parameterized: 0 rows <nil>
```

For `sara`, both find one order. For the hostile input, the concatenated query became `... WHERE customer = 'x' OR '1'='1'`, a condition that is always true, so it returned all three orders in the table. That is {{< term "sql-injection" "SQL injection" >}}. The {{< term "parameterized-query" "parameterized" >}} query treated the same text as a customer name, found nobody with that name, and returned zero rows. Parameters travel separately from the SQL text, so they can never change its structure. One limit: only values can be parameters. Table and column names cannot, so if you ever need a dynamic one, check it against a fixed list.

## sqlc: generate the boring part

Writing `row` structs and scanning code by hand is repetitive. With sqlc you write the SQL and get typed Go. Its config reads the migrations folder as the schema, so there is only one definition of the table:

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

`query.sql` has three queries, each with a name and a kind in a comment: `GetOrder :one`, `ListOrdersByCustomer :many` and `UpsertOrder :exec`. Running `sqlc generate` produced these signatures:

```go
func (q *Queries) GetOrder(ctx context.Context, id string) (Order, error)
func (q *Queries) ListOrdersByCustomer(ctx context.Context, customer string) ([]Order, error)
func (q *Queries) UpsertOrder(ctx context.Context, arg UpsertOrderParams) error
```

Those signatures are copied from the generated file in the demo (its header says it was made by sqlc v1.31.1). This time I could not download sqlc again, because the module mirror timed out, so I did not re-run `generate`. What I checked is that the committed generated code matches these signatures and that the whole sqlc store passes the tests below. The `generate` run itself, and the experiment in the next paragraph, are from my original run.

A useful property: sqlc checks your SQL against the schema when it generates. In the original run I added a query selecting a column `total` that is not in the table, and `generate` failed with `query.sql:13:8: column "total" does not exist`. So a typo in a query is caught before anything runs, not in production. The generated `Order` type uses `pgtype.Timestamptz` for `created_at`, which is why my store maps it to `domain.Order` by hand, in a few lines.

## One test, three stores

How do we know the three stores behave the same? The service-level checks live in a helper that takes any `service.Repository`: create then get, invalid order rejected, missing order is `ErrNotFound`. The memory store, the pgx store and the sqlc store all run it, and each has the compile-time guard `var _ service.Repository = (*Store)(nil)` from the layout post:

```
$ go test -v ./internal/store/postgres
--- PASS: TestService (0.00s)
    --- PASS: TestService/create_then_get (0.00s)
    --- PASS: TestService/invalid_order_is_rejected (0.00s)
    --- PASS: TestService/missing_order_is_ErrNotFound (0.00s)
PASS
```

(I removed the `=== RUN` lines.) The Postgres test starts a real server in `TestMain`, applies the migration, runs the three subtests and stops the server. The memory and sqlc packages passed the same three subtests. The service code did not change at all. This is a small version of what the layering was for.

## pgx and sqlc traps

- `SELECT *` with `RowToStructByName` fails if the struct and the columns differ. That is useful as an alarm, but in production queries list the columns explicitly, so adding a column later does not break the code.
- Always `defer cancel()` after `WithTimeout`, and set a deadline at the edge of every request.
- Keep the pool in `main`, create it once, and close it on shutdown.
- sqlc output is code you commit. Regenerate it in CI and fail the build on a diff, so the generated code never drifts from the SQL.
- Embedded Postgres is convenient for tests, but according to its documentation it downloads the Postgres binaries on first use. A Postgres service container in CI is the other common option.

## What's next

Next is "Transactions and the repository pattern in Go". Here each write commits on its own, while real work often needs several writes to succeed or fail together.
