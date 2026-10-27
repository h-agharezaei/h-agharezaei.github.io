+++
date = '2027-02-11T10:00:00+03:30'
draft = false
title = 'Postgres from Node.js with pg'
description = 'Postgres from Node.js with pg: Pool, parameters, type surprises, transactions, SQL injection, SQLSTATE errors, timeouts and shutdown, all run for real.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "postgres", "pg", "sql", "connection-pool"]
cover = { image = "/images/covers/node-postgres-pg.png", alt = "Postgres from Node.js with pg", hiddenInSingle = true }
+++

In the previous post, [Project structure and config in Node.js](/posts/node-project-structure-config/), the database URL came from config. Now we use it. I connect to a real PostgreSQL with `pg` (node-postgres), and compare with [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/). The transaction helper mirrors [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/).

> Node v20.13.1, `pg` 8.23.1, `pg-cursor` 2.22.1, PostgreSQL 18.3 on loopback, the shared "shop" schema (customers, orders...) with a few rows. Local example scripts; outputs are real. No timings.

## Pool and query

A {{< term "connection-pool" "connection pool" >}} keeps a few open connections and lends them out. `pool.query` borrows one, runs the SQL, and returns it. Values go in as parameters (`$1`), never inside the SQL string:

```js
const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 4 });
const r = await pool.query('SELECT id, name FROM customers WHERE country = $1 ORDER BY id LIMIT $2', ['DE', 2]);
console.log(r.rows, r.rowCount, r.fields.map(f => f.name), r.command);
```

```text
[ { id: '1', name: 'c1' }, { id: '2', name: 'c2' } ] 2 [ 'id', 'name' ] SELECT
```

The result has `rows`, `rowCount`, `fields` and `command`. Note `id` is the string `'1'`.

## Type surprises

I selected several types in one query:

```text
count   string  30
sum     string  46500
bigint  string  1
numeric string  12.50
int     number  7
now()   Date
```

`bigint`, `numeric`, `count(*)` and `sum` come back as **strings**. JavaScript numbers are doubles, so a bigger-than-2^53 value would be damaged: `9007199254740993::bigint` arrived as `'9007199254740993'`, and `Number()` of it gave `9007199254740992`. The trap is `row.n + 1`: it gave `301`, not `31`. Convert deliberately (`Number(row.n)` when you know it is small, `BigInt` or a string otherwise, or cast in SQL with `count(*)::int`). `timestamptz` becomes a `Date`, and a {{< term "jsonb" "jsonb" >}} column is parsed into a real object (`meta.tags` was `['a', 'b']`, see [JSONB and full-text search](/posts/db-jsonb-fulltext-search/)). pgx in Go scans `bigint` into `int64` directly; here the safe default is a string.

## Pool limits

I set `max: 2` and `connectionTimeoutMillis: 300`, borrowed both connections with `pool.connect()` and then ran a third query:

```text
total/idle/waiting 2 0 0
Error | timeout exceeded when trying to connect
after release 2 2
after idle timeout 0 0
```

An exhausted pool does not fail at once: the query waits, and after the timeout it throws that error. Without `connectionTimeoutMillis` (default: wait forever) it hangs. A leaked client (no `release()`) looks the same. After release both clients were idle, and with `idleTimeoutMillis: 1000` they were closed.

## Transactions with a dedicated client

A transaction must run on ONE connection, so `BEGIN`/`COMMIT` through `pool.query` is wrong: each call may use a different connection. Take a client and always release it in `finally`:

```js
async function withTx(fn) {
  const client = await pool.connect();
  try {
    await client.query('BEGIN');
    const result = await fn(client);
    await client.query('COMMIT');
    return result;
  } catch (err) {
    await client.query('ROLLBACK');
    throw err;
  } finally {
    client.release();
  }
}
```

I committed two `paid` orders, then ran a transaction with one valid insert and one with a customer that does not exist:

```text
paid before 0
after commit 2
inside tx sees 3
failed: 23503 orders_customer_id_fkey
after rollback 2 idle 1 total 1
```

The failed {{< term "transaction" "transaction" >}} saw its own row (3), then rolled it back (2). The client went back to the pool.

## SQL injection

I built the same query two ways. The attacker input is `x' OR '1'='1`:

```text
concat normal: 1 rows
concat evil  : 6 rows
param  evil  : 0 rows
notes before: notes
after param attack : notes
after concat attack: null
```

With string concatenation the evil input returned all 6 customers, and the input `x'; DROP TABLE notes; --` really dropped my own demo table (`null` means it no longer exists). With `$1` the same text is just a country that does not exist. This is {{< term "sql-injection" "SQL injection" >}}. Parameters travel separately from the SQL text, so you cannot escape them. Table and column names cannot be parameters; use an allow-list.

## Errors and SQLSTATE

`err.code` is the {{< term "sqlstate" "SQLSTATE" >}}, `err.constraint` the constraint name. One function maps them to domain errors, as in [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/):

```js
function mapPgError(err) {
  switch (err.code) {
    case '23505': return new DomainError('conflict', 'already exists');
    case '23503': return new DomainError('invalid', 'referenced row does not exist');
    case '23514': return new DomainError('invalid', 'value violates a rule');
    default: return err;
  }
}
```

```text
dup email | code 23505 | constraint customers_email_key  -> 409 conflict
bad fk    | code 23503 | constraint orders_customer_id_fkey -> 422 invalid
check     | code 23514 | constraint orders_status_check  -> 422 invalid
syntax    | code 42601 -> unmapped, rethrow
```

Unknown codes are rethrown as bugs.

## Timeouts and the pool error event

With `statement_timeout: 200` the server cancels a slow query, and the connection stays usable:

```text
statement_timeout: 57014 canceling statement due to statement timeout
pool still works: 1
query_timeout: undefined Query read timeout
```

`query_timeout` is different: the client gives up (no SQLSTATE) and the server is not told. I checked: a second connection still saw `select pg_sleep(4)` as `active` with `wait_event = PgSleep` after the client had timed out. Prefer `statement_timeout`.

An idle client can die (I killed it with `pg_terminate_backend`). Without a handler, the pool re-emits its error, and Node crashes with `Unhandled 'error' event` (code 57P01). With `pool.on('error', ...)` the process survived and the pool dropped the dead client:

```text
pool error event: 57P01 terminating connection due to administrator command
survived; idle clients: 0
```

## Cursor and shutdown

For a big result, `pg-cursor` reads in batches instead of loading every row (a 25-row series with batch size 10: `10, 10, 5`). Use it on a dedicated client.

For shutdown, `pool.end()` waits for borrowed clients. I started an HTTP server whose handler ran `pg_sleep(1)`, sent a request and then `SIGTERM`. The response `42` still arrived, and the log read `closing server, then pool`, `pool ended, exiting`, exit code 0. This is the pattern from [An HTTP server with node:http](/posts/node-http-server/).

## A few things to watch

- Always parameters; never concatenate values into SQL.
- `bigint`, `numeric` and `count(*)` are strings: convert on purpose.
- Use `pool.connect()` for transactions, `release()` in `finally`.
- Set `connectionTimeoutMillis`, `statement_timeout` and a `pool.on('error')` handler.
- Branch on `err.code`, not on the message.

## Exercise

Write `createOrder(customerId, productId, qty)` that inserts into `orders` and `order_items` inside `withTx`, maps `23503` to a 422 domain error, and prove with a test that a failed item insert leaves no order row.

## What's next

The next post is "NATS JetStream from Node.js".
