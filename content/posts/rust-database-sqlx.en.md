+++
date = '2027-01-23T10:00:00+03:30'
draft = false
title = 'Databases with SQLx in Rust'
description = 'Postgres in Rust with SQLx: PgPool, query_as and FromRow, bind parameters, transactions with automatic rollback, migrations and checked queries.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "sqlx", "postgres", "database", "backend"]
cover = { image = "/images/covers/rust-database-sqlx.png", alt = "Databases with SQLx in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-http-axum-api/) we built an orders API with Axum that kept everything in memory. This post swaps that for Postgres. I wrote a small `OrderStore` for this demo: a struct holding a connection pool, with `create`, `get`, `find`, `list` and a transactional method. It stands alone; plug it into Axum as shared state the same way. I use **SQLx**, an async SQL toolkit that is not an ORM: you write SQL, it handles pooling, parameters and row mapping. The Go counterpart is [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/).

> Rust 1.90, `sqlx` 0.8.6 (features `runtime-tokio`, `postgres`, `migrate`, `macros`), `tokio` 1.54.1, against a real PostgreSQL 18.3 started by a tiny Go launcher with `embedded-postgres` (no Docker), stopped afterwards. The newest sqlx on crates.io, 0.9.0, declares rustc 1.94 as its minimum, so Cargo refused it on my 1.90 and I pinned 0.8.

## Pool, rows and parameters

`PgPoolOptions` configures the **connection pool**; `PgPool` is a cheap, cloneable handle, so the store can be `#[derive(Clone)]`.

```rust
let pool = PgPoolOptions::new()
    .max_connections(5)
    .acquire_timeout(Duration::from_secs(3))
    .connect(url)
    .await?;
```

`query_as` maps rows into a struct that derives `FromRow` (columns matched by name). Values go in with `.bind()` against `$1`, `$2`, never into the SQL string:

```rust
#[derive(Debug, sqlx::FromRow)]
pub struct Order { pub id: i64, pub customer: String, pub cents: i64, pub status: String }

sqlx::query_as::<_, Order>("INSERT INTO orders (customer, cents) VALUES ($1, $2)
                            RETURNING id, customer, cents, status")
    .bind(customer).bind(cents)
    .fetch_one(&self.pool).await
```

The fetch method states how many rows you expect: `fetch_one` (exactly one, otherwise `Err`), `fetch_optional` (`Option`), `fetch_all` (`Vec`). When `fetch_one` finds nothing it returns `sqlx::Error::RowNotFound`; I map it to a domain error so callers never see SQLx types for a normal "missing" case:

```rust
.fetch_one(&self.pool).await.map_err(|e| match e {
    sqlx::Error::RowNotFound => StoreError::NotFound(id),
    other => StoreError::Db(other),
})
```

`StoreError` is a hand-written enum with `Display`, `Error` and `From<sqlx::Error>`; the next post replaces that boilerplate.

## Transactions and rollback on drop

`pool.begin()` returns a `Transaction`. Pass `&mut *tx` as the executor, then call `commit()`. If the transaction is dropped without `commit`, SQLx rolls it back, so an early `?` return is safe:

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

## Embedded migrations

Put numbered `.sql` files in `migrations/` and `sqlx::migrate!("./migrations").run(&pool).await?` embeds them in the binary and applies the pending ones. SQLx records each in a `_sqlx_migrations` table. Running the whole demo once:

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

The count stays 3 after the failing transaction: the dropped insert was rolled back. The committed id is 4, not 3: the rejected `bob` insert consumed an identity value.

## Compile-time checked queries

The `query!` and `query_as!` macros connect to the database **while compiling** and check the SQL against the real schema. A misspelled column:

```text
error: error returned from database: column "custmer" does not exist
  --> src/bin/bad_column.rs:13:18
   |
13 |     let orders = sqlx::query_as!(Order, "SELECT id, custmer, cents FROM orders")
```

A struct field `cents: i32` for a `bigint` column fails in the type checker (`the trait bound i32: From<i64> is not satisfied`), and binding a `&str` to `WHERE id = $1` gives `expected i64, found &str`. The macros need `DATABASE_URL` at build time. Without it:

```text
error: set `DATABASE_URL` to use query macros online, or run `cargo sqlx prepare` to update the query cache
```

For CI and Docker builds without a database, `cargo sqlx prepare` runs the checks once and writes a `.sqlx/` directory of JSON files (query text, column types, nullability) that you commit. I installed `sqlx-cli` 0.8.6 into a private directory (it took a few minutes to build), ran `cargo sqlx prepare`, then built with `DATABASE_URL` unset: it compiled. Changing the query text without re-preparing brought back the error above.

## Compared with Go's pgx and sqlc

Both ecosystems keep SQL as SQL. Go's usual path is sqlc: it reads your schema and queries and generates Go code ahead of time, so the compiler checks calls to that code and no database is needed at build time. SQLx's macros check at compile time too, but against a live database, or the committed `.sqlx` cache. Plain `sqlx::query_as` and pgx's `Query` are both unchecked: a typo fails when the query runs.

## A few things to watch

- Prefer explicit column lists over `SELECT *`; `FromRow` matches names, so extra or renamed columns surface as runtime errors.
- Commit `.sqlx/` and run `cargo sqlx prepare --check` in CI so the cache cannot go stale.
- Do not hold a `Transaction` across slow non-database work; it pins a pool connection.
- A rolled-back insert still burns identity values; do not expect gap-free ids.

## Exercise

1. Add a `mark_paid(id)` method that uses `UPDATE ... WHERE id = $1 AND status = 'new'` and returns `NotFound` when no row changes (hint: `execute` returns a result with `rows_affected()`).
2. Add a third migration that adds a `created_at timestamptz NOT NULL DEFAULT now()` column and check `_sqlx_migrations`.

## What's next

Our `StoreError` is ugly boilerplate. Next: errors in real apps with thiserror and anyhow.
