+++
date = '2027-01-23T10:00:00+03:30'
draft = false
title = 'Databases with SQLx in Rust'
description = 'Postgres in Rust with SQLx: PgPool, query_as and FromRow, bind parameters, transactions with automatic rollback, migrations and checked queries.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "sqlx", "postgres", "database", "backend"]
cover = { image = "/images/covers/rust-database-sqlx.png", alt = "Databases with SQLx in Rust", hiddenInSingle = true }
+++

Your `orders` table has a column `cents bigint`. In your Rust struct you write `cents: i32`. Or you misspell a column in a query, `custmer` instead of `customer`. When do you find out? With most database libraries the answer is "when that line of code runs", which might be in production, on a rarely used path. SQLx gives you a choice: plain queries are checked when they run, and the `query!` macros check them *while the program is compiled*.

This post replaces the in-memory store of the [orders API with Axum](/posts/rust-http-axum-api/) with Postgres. I wrote a small `OrderStore` for the demo: a struct holding a connection pool, with `create`, `get`, `find`, `list` and one method that uses a transaction. It stands alone here; you would plug it into Axum as shared state in the same way as before. The library is **SQLx**, an async SQL toolkit. It is not an ORM (a library that hides SQL behind objects): you write the SQL yourself, and SQLx handles the pool of connections, the parameters and the mapping of rows into Rust values. The Go counterpart is [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/).

> I used Rust 1.90, `sqlx` 0.8.6 (features `runtime-tokio`, `postgres`, `migrate` and `macros`) and `tokio` 1.54.1, against a real PostgreSQL 18.3 started by a tiny Go launcher with `embedded-postgres` (no Docker) on a random local port and stopped afterwards. I re-ran every demo for this version of the post and the outputs match. In my original run the newest sqlx on crates.io, 0.9.0, declared rustc 1.94 as its minimum, so Cargo refused it on my 1.90 and I pinned 0.8.

## The tables

The demo has two tables, created by two numbered migration files (more on migrations below):

```sql
CREATE TABLE orders (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer text   NOT NULL,
    cents    bigint NOT NULL CHECK (cents > 0),
    status   text   NOT NULL DEFAULT 'new'
);
CREATE TABLE order_events (
    id       bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    order_id bigint NOT NULL REFERENCES orders (id),
    kind     text   NOT NULL
);
```

The database numbers the rows itself (`GENERATED ALWAYS AS IDENTITY`), refuses an order with `cents <= 0` (the `CHECK`), and every event must point to an existing order (`REFERENCES`). Keep these rules in mind; the demo will run into some of them on purpose.

## A pool, a query and a row type

Opening a database connection is slow, so a service keeps a few open and lends them to requests. That set of connections is a {{< term "connection-pool" "connection pool" >}}. `PgPoolOptions` configures it, and the `PgPool` you get back is a cheap, cloneable handle to the shared pool. That is why `OrderStore` can simply be `#[derive(Clone)]`:

```rust
let pool = PgPoolOptions::new()
    .max_connections(5)
    .acquire_timeout(Duration::from_secs(3))
    .connect(url)
    .await?;
```

At most five connections are open, and a request that has to wait more than three seconds for one gets an error instead of waiting forever.

Now a query. `query_as` runs SQL and maps each row into a struct that derives `FromRow`; columns are matched to fields *by name*. The values go in with `.bind()`, against the placeholders `$1` and `$2`, and never into the SQL text itself. That is a {{< term "parameterized-query" "parameterized query" >}}: the database receives the SQL and the values separately, so a value can never be mistaken for SQL.

```rust
#[derive(Debug, sqlx::FromRow)]
pub struct Order { pub id: i64, pub customer: String, pub cents: i64, pub status: String }

sqlx::query_as::<_, Order>("INSERT INTO orders (customer, cents) VALUES ($1, $2)
                            RETURNING id, customer, cents, status")
    .bind(customer).bind(cents)
    .fetch_one(&self.pool).await
```

`RETURNING` makes Postgres send back the inserted row, with the `id` and the default `status` it generated, so one round trip creates and reads. The last call says how many rows you expect:

- `fetch_one`: exactly one row, otherwise an error.
- `fetch_optional`: zero or one row, as an `Option`.
- `fetch_all`: any number of rows, as a `Vec`.

When `fetch_one` finds nothing, it returns `sqlx::Error::RowNotFound`. A missing order is a normal situation, not a database failure, so I translate it into my own error and callers never need to know about SQLx types:

```rust
.fetch_one(&self.pool).await.map_err(|e| match e {
    sqlx::Error::RowNotFound => StoreError::NotFound(id),
    other => StoreError::Db(other),
})
```

`StoreError` is an enum I wrote by hand, together with its `Display`, `Error` and `From<sqlx::Error>` implementations. It is a lot of boilerplate for two variants; the next post replaces it.

## Transactions and rollback on drop

Sometimes two statements must succeed or fail together: here, inserting an order and writing an audit event about it. A {{< term "transaction" "transaction" >}} makes that promise. `pool.begin()` starts one and returns a `Transaction`. You run your queries against `&mut *tx` instead of the pool, and finish with `commit()`. If the transaction is dropped without a commit, SQLx rolls it back. That means an early `return` or a `?` in the middle is safe:

```rust
let mut tx = self.pool.begin().await?;
let (id,): (i64,) = sqlx::query_as("INSERT INTO orders (customer, cents) VALUES ($1, $2) RETURNING id")
    .bind(customer).bind(cents).fetch_one(&mut *tx).await?;
if fail_after_insert {
    return Err(StoreError::NotFound(-1)); // tx dropped here, never committed
}
sqlx::query("INSERT INTO order_events (order_id, kind) VALUES ($1, 'created')")
    .bind(id).execute(&mut *tx).await?;
tx.commit().await?;
```

The `fail_after_insert` flag exists only for the demo: it returns an error right after the first insert, standing in for any failure, so we can watch the rollback.

## Migrations, and one full run

A **migration** is a numbered `.sql` file that changes the schema; the files are applied in order, and each one only once. Put them in a `migrations/` directory, and `sqlx::migrate!("./migrations").run(&pool).await?` embeds the files in the binary and applies the pending ones. SQLx remembers what it applied in a table called `_sqlx_migrations`.

The demo's `main` creates an order for `alice`, lists her orders, looks up an id that does not exist, tries an order with negative cents, runs one successful transaction and one that is dropped, and finally prints the migration table. This is its output:

```text
created: Order { id: 1, customer: "alice", cents: 1500, status: "new" }
alice has 2 orders
get(999)  -> order 999 not found
find(999) -> None
bad cents -> database error: error returned from database: new row for relation "orders" violates check constraint "orders_cents_check"
count before tx tests: 2
committed tx, new id 4, count: 3
failing tx -> order -1 not found
count after dropped tx: 3
migration 1 create orders success=true
migration 2 create order events success=true
```

Line by line:

- The first two lines are the insert with `RETURNING` and a second order for alice, so `list` finds two.
- `get(999)` uses `fetch_one`, so the missing row becomes our `NotFound` error. `find(999)` uses `fetch_optional` for the same id and gets `None`. Same query, two ways to ask.
- `bad cents` is the `CHECK (cents > 0)` rule in action. The database refused the row, and the error we see is the database's message wrapped in our `Db` variant. It is the database, not our Rust code, that enforces the rule.
- Then the transactions. The committed one inserted an order and its event, and the count went from 2 to 3. The failing one inserted a row and then returned early; afterwards the count is still 3, so the dropped insert was rolled back.
- The committed order has id 4, not 3. The rejected `bob` insert never became a row, but it still used up an identity number. Do not expect ids without gaps.
- The last two lines come straight from `_sqlx_migrations`: both migrations were applied successfully.

## Compile-time checked queries

Everything above checks the SQL when it *runs*: a typo in a column name would fail at that moment. The macros `query!` and `query_as!` do something unusual. When you compile, they connect to the database (the address comes from the `DATABASE_URL` environment variable), ask it to analyse the query, and check your SQL and your Rust types against the real schema. The demo directory `checked` has one such query, `SELECT id, customer, cents FROM orders WHERE cents >= $1`, and runs it:

```text
Order { id: 1, customer: "alice", cents: 1500 }
Order { id: 2, customer: "alice", cents: 700 }
```

Three programs that are meant to fail show what you gain. First, a misspelled column:

```text
error: error returned from database: column "custmer" does not exist
  --> src/bin/bad_column.rs:13:18
   |
13 |     let orders = sqlx::query_as!(Order, "SELECT id, custmer, cents FROM orders")
```

The mistake is a compile error, reported with the database's own message and the exact line. Second, a struct with `cents: i32` for a `bigint` column fails in the type checker with `the trait bound i32: From<i64> is not satisfied`. Third, binding a `&str` to `WHERE id = $1`, where `id` is a `bigint`, gives `expected i64, found &str`. (The compiler output also lists other types that implement `From`; I left that out.)

The price is that the macros need the database at build time. Without `DATABASE_URL`, you get:

```text
error: set `DATABASE_URL` to use query macros online, or run `cargo sqlx prepare` to update the query cache
```

The message also names the way out. For CI and Docker builds that have no database, `cargo sqlx prepare` (from the tool `sqlx-cli`) runs the checks once and writes a `.sqlx/` directory of small JSON files with each query's text, column types and nullability; you commit it. The demo's `.sqlx/` has one file for our one query. I built `checked` again with `DATABASE_URL` unset and with that directory present, and it compiled; with the directory moved away, it gave the error above. In my original run I also installed `sqlx-cli` 0.8.6 into a private directory (it took a few minutes to build) and ran `cargo sqlx prepare` myself; there I saw that changing the query text without re-preparing brought the error back. For this re-run I did not repeat the `prepare` step; I used the committed cache.

## Compared with Go's pgx and sqlc

Both ecosystems keep SQL as SQL. The usual Go route is sqlc: it reads your schema and queries and *generates* Go code ahead of time, so the Go compiler checks every call to that generated code, and no database is needed at build time. SQLx's macros also check at compile time, but against a live database or the committed `.sqlx` cache. Plain `sqlx::query_as` and pgx's `Query` are both unchecked: a typo fails when the query runs.

## Database traps

- **Prefer explicit column lists over `SELECT *`.** `FromRow` matches by name, so extra or renamed columns turn into runtime errors, and `SELECT *` makes them more likely.
- **Commit `.sqlx/` and run `cargo sqlx prepare --check` in CI.** Otherwise the cache can go stale and the build will pass or fail depending on whether a database is around.
- **Do not hold a `Transaction` across slow work that is not database work.** It keeps one connection from the pool for the whole time.
- **A rolled-back insert still uses up identity numbers.** Do not expect gap-free ids, and never use them to count rows.

## Exercise

1. Add a `mark_paid(id)` method that uses `UPDATE ... WHERE id = $1 AND status = 'new'` and returns `NotFound` when no row changes (hint: `execute` returns a result with `rows_affected()`).
2. Add a third migration that adds a `created_at timestamptz NOT NULL DEFAULT now()` column and look at the `_sqlx_migrations` table afterwards.

## What's next

Our `StoreError` is a lot of hand-written boilerplate for two variants. The next post, *Errors in real apps: thiserror and anyhow*, removes it.
