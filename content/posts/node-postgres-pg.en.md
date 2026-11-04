+++
date = '2027-02-11T10:00:00+03:30'
draft = false
title = 'Postgres from Node.js with pg'
description = 'Postgres from Node.js with pg: Pool, parameters, type surprises, transactions, SQL injection, SQLSTATE errors, timeouts and shutdown, all run for real.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "postgres", "pg", "sql", "connection-pool"]
cover = { image = "/images/covers/node-postgres-pg.png", alt = "Postgres from Node.js with pg", hiddenInSingle = true }
+++

Here is a bug that is easy to miss. You run `SELECT count(*) AS n FROM orders`, then write `row.n + 1` to get "one more than the count". With 30 orders you expect 31. You get `301`. Nothing crashes and nothing warns you. The number is simply wrong.

The cause is that `pg`, the Postgres driver for Node.js, hands `count(*)` back as a string, so `+` glues the characters together instead of adding. That is only the first of several surprises waiting between a Node.js program and a database. The others are connections you must share carefully, transactions that must stay on one connection, and one very old mistake, building SQL out of user input.

In this post I connect `pg` (also called node-postgres) to a real PostgreSQL and go through those one at a time, each with a small script and its real output. The database address comes from an environment variable, `DATABASE_URL`, the kind of setting we learned to read and validate once in [Project structure and config in Node.js](/posts/node-project-structure-config/). For comparison, the same topics in Go are in [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/) and, for transactions, [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/).

> I ran everything with Node v20.13.1, `pg` 8.23.1 and `pg-cursor` 2.22.1 (from the demo's lockfile) against PostgreSQL 18.3 on loopback. The database uses the shared "shop" schema of the Databases series (customers, products, orders, order items), with a few rows added by `setup.sql`: 6 customers, 2 products and 30 orders. There is no Docker on this machine, so Postgres ran from embedded binaries on a random free port. The scripts are local examples. I show no timings.

## A pool of connections, and a first query

To talk to Postgres you open a connection: a TCP connection to the server plus a login. That is slow compared with a typical query, and the server keeps resources for each connection. (According to the Postgres docs the default limit is 100 connections.) So a web service does not open a new connection per request. It keeps a few connections open and lends them out.

That is exactly what a {{< term "connection-pool" "connection pool" >}} is. `pool.query(...)` borrows an idle connection, runs the SQL on it and gives it back. If all connections are busy, the call waits for one.

The values of a query go in as *parameters*: `$1`, `$2` in the SQL text, and the actual values in an array next to it. Never paste them into the SQL string. We will see why in the injection section; for now just notice the shape:

```js
const pool = new Pool({ connectionString: process.env.DATABASE_URL, max: 4 });
const r = await pool.query('SELECT id, name FROM customers WHERE country = $1 ORDER BY id LIMIT $2', ['DE', 2]);
console.log(r.rows, r.rowCount, r.fields.map(f => f.name), r.command);
```

`max: 4` caps the pool at four connections. The result object has the rows, a row count, the column names and the kind of command. Here is what it printed:

```text
[ { id: '1', name: 'c1' }, { id: '2', name: 'c2' } ] 2 [ 'id', 'name' ] SELECT
```

The rows are plain objects, one per row. Look at `id`: it is the string `'1'`, not the number 1. That is the same surprise as `count(*)`, and it deserves its own section.

## Why numbers come back as strings

A Postgres `bigint` holds up to 64 bits. A JavaScript number is a double, which can represent integers exactly only up to 2^53. If `pg` converted every `bigint` to a number, large values would be silently damaged, so by default it returns a string. The same goes for `numeric` (exact decimals, which a double cannot hold exactly), and `count(*)` and `sum` produce `bigint` or `numeric`.

One script asks for several types in a single query and prints the JavaScript type of each column:

```text
n       string  30
s       string  46500
big     string  1
num     string  12.50
i       number  7
ts      object  Date  <the current time>
```

(The columns are `count(*)`, `sum(total_cents)`, `1::bigint`, `12.50::numeric`, `7::int` and `now()`. I replaced the real timestamp in the last line with a placeholder; it is the time of the run.) Only the plain `int` arrives as a number. `timestamptz` becomes a JavaScript `Date`.

How bad can the damage be? I asked for `9007199254740993::bigint`, one above 2^53. The string arrived intact, and converting it to a number lost the last digit:

```text
31 301
9007199254740993 9007199254740992
```

The first line is `Number(row.n) + 1` and `row.n + 1`: that is the 301 from the start. The second line is the big value as the string and after `Number()`.

So convert on purpose. Use `Number(row.n)` when you know the value is small, `BigInt` or the string itself when it may be large, or cast in SQL, for example `count(*)::int`. A {{< term "jsonb" "jsonb" >}} column, on the other hand, is parsed into a real object for you (`meta.tags` was `['a', 'b']`; see [JSONB and full-text search](/posts/db-jsonb-fulltext-search/)). In that same script a `numeric(10,2)` price came back as the string `'12.50'`, which keeps its decimals exactly. In Go, pgx scans a `bigint` straight into an `int64`; in Node the safe default is a string.

## What happens when the pool runs out

A pool has a limit, so a natural question is what happens when everyone is borrowing. In this script I set `max: 2` and `connectionTimeoutMillis: 300`, borrowed both connections with `pool.connect()` and never returned them, then ran a third query:

```text
total/idle/waiting 2 0 0
Error | timeout exceeded when trying to connect | undefined
after release 2 2
after idle timeout 0 0
```

Line by line: with two connections borrowed, the pool has 2 connections, 0 idle, 0 waiting (the third query has not started yet). The third query waits, and after 300 ms it throws "timeout exceeded when trying to connect" (the error has no `code`, hence `undefined`). After I released both, they were idle again (2 total, 2 idle). With `idleTimeoutMillis: 1000`, an idle connection is closed after a second, so the last line shows 0.

The important detail is that an exhausted pool does not fail at once. The query waits. By default, according to the pg docs, `connectionTimeoutMillis` is 0, which means wait forever. So a request would hang until someone returns a connection. A connection that is borrowed and never released, a leak, looks exactly like this. Set a timeout so you get an error instead of a hang.

## Transactions need one connection

Sometimes several statements must succeed or fail together, for example creating an order and its items. A {{< term "transaction" "transaction" >}} does that: you send `BEGIN`, run the statements, and then `COMMIT` to keep them all or `ROLLBACK` to undo them all.

A transaction lives on a single connection. If you ran `BEGIN` and `COMMIT` through `pool.query`, each call could use a different connection, and the transaction would be meaningless. So you take one connection out of the pool with `pool.connect()`, use it for everything, and return it in `finally`, whatever happens:

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

To try it, the script first commits two `paid` orders. Then it runs a transaction with a valid insert followed by an insert for a customer that does not exist, which must fail:

```text
paid before 0
after commit 2
inside tx sees 3
failed: 23503 orders_customer_id_fkey
after rollback 2 idle 1 total 1
```

Before anything there are no paid orders, and after the first transaction there are 2. In the failing transaction the connection sees its own uncommitted row (3). The second insert breaks the foreign key `orders_customer_id_fkey`, so the code rolls back and the count is back to 2. The last line shows the connection went back to the pool (1 idle of 1 total).

## SQL injection

Now the old mistake. Suppose you build the query by gluing the country into the text. The script runs the same lookup both ways. The "evil" input is `x' OR '1'='1`: it closes the string early and adds a condition that is always true.

```text
concat normal: 1 rows
concat evil  : 6 rows
param  evil  : 0 rows
notes before: notes
after param attack : notes
after concat attack: null
```

The normal input finds the one UK customer. With concatenation, the evil input returned all 6 customers. With `$1`, the same text is just a country name that does not exist, so zero rows. This is {{< term "sql-injection" "SQL injection" >}}: user input became part of the SQL itself.

It can be worse than leaking rows. The input `x'; DROP TABLE notes; --` ends the statement and starts another. After the parameterized call the table `notes` still existed. After the concatenated call it really was gone (`to_regclass` returned `null`, which means no such table). It was my own demo table, of course.

The reason parameters are safe is that they travel separately from the SQL text (this is a {{< term "parameterized-query" "parameterized query" >}}). The database parses the statement first and puts the values in afterwards, so a value can never change the structure of the query. One limit: table and column names cannot be parameters. If a name comes from the user, check it against a fixed allow-list.

## Reading errors by SQLSTATE

When a query fails, `pg` throws an error with a `code` property. That is the {{< term "sqlstate" "SQLSTATE" >}}, a five-character standard code, and `err.constraint` names the constraint that was violated. Branch on the code, not on the message text, because messages are meant for humans and can change. A single function can turn the codes you care about into your own domain errors, in the style of [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/):

```js
function mapPgError(err) {
  switch (err.code) {
    case '23505': return new DomainError('conflict', 'already exists');
    case '23503': return new DomainError('invalid', 'referenced row does not exist');
    case '23514': return new DomainError('invalid', 'value violates a rule');
    case '57014': return new DomainError('timeout', 'query took too long');
    default: return err;
  }
}
```

`23505` is a unique violation, `23503` a foreign key violation, `23514` a check violation and `57014` a cancelled statement. The script triggers four failures and maps each (the `->` lines show the HTTP-style status the demo chose):

```text
dup email | code 23505 | constraint customers_email_key | detail Key (email)=(ada@example.com) already exists.
   -> 409 conflict: already exists
bad fk   | code 23503 | constraint orders_customer_id_fkey | detail Key (customer_id)=(999999) is not present in table "customers".
   -> 422 invalid: referenced row does not exist
check    | code 23514 | constraint orders_status_check | detail Failing row contains (36, 1, weird, 2026-11-04 18:25:47.506092+03:30, 0).
   -> 422 invalid: value violates a rule
syntax   | code 42601 | constraint undefined | detail undefined
   -> unmapped, rethrow: syntax error at or near "SELEC"
```

The duplicate email, the missing customer and the bad status each map to a clear answer. The typo `SELEC` has code `42601` and no constraint, and nobody mapped it, so the code rethrows it: an unexpected error should stay an error. (The row id and timestamp in the `check` line change on every run.)

## Timeouts, and the error that crashes the process

A slow query needs a limit, and `pg` offers two that are not the same. With `statement_timeout: 200`, the *server* cancels any statement that runs longer than 200 ms, and the connection stays usable. With `query_timeout: 200`, the *client* gives up waiting and throws, but the server is not told:

```text
statement_timeout: 57014 canceling statement due to statement timeout
pool still works: 1
query_timeout: undefined Query read timeout
after: 1
```

The first case has a SQLSTATE (57014) and the pool works afterwards. The second has no code, only the message "Query read timeout". Is the server still working on it? I checked with a throwaway script: after the client gave up on `pg_sleep(2)`, a second connection looked at `pg_stat_activity` and still saw the statement as `active` with `wait_event` `PgSleep`; it was gone once the sleep had finished. So prefer `statement_timeout`, which really stops the work.

The second hazard is an idle connection dying while nobody is using it. I simulated that by killing the connection from another one with `pg_terminate_backend`. The pool re-emits the connection's `error` event, and in Node an `error` event with no listener throws. Without a handler, the process crashed:

```text
node:events:497
      throw er; // Unhandled 'error' event
      ^

error: terminating connection due to administrator command
...
  severity: 'FATAL',
  code: '57P01',
```

(I cut the stack trace; its paths are from my scratch directory.) With one line, `pool.on('error', (err, client) => ...)`, the process survived and the pool simply dropped the dead connection:

```text
pool error event: 57P01 terminating connection due to administrator command
survived; idle clients: 0
```

Every pool in a long-running service should have that handler.

## Big results, and shutting down cleanly

If a query returns a huge number of rows, loading them all into memory at once is a bad idea. The `pg-cursor` package reads them in batches. The script reads a 25-row series with batch size 10, and gets batches of 10, 10 and 5 (`total 25`). A cursor has to live on one dedicated connection (`pool.connect()`), not on `pool.query`.

For shutdown, `pool.end()` waits for borrowed connections to come back before closing. To see it, I started an HTTP server whose handler runs `pg_sleep(1)` and returns 42, sent one request, and then sent `SIGTERM` while the query was still running. The response `42` still arrived, and the log read `SIGTERM: closing server, then pool`, `pool ended, exiting`, with exit code 0. The order matters: stop accepting requests first, then end the pool. That is the same pattern as in [An HTTP server with node:http](/posts/node-http-server/).

## Where pg data goes wrong

- **Pasting values into SQL.** Always use parameters. A table or column name from the user needs an allow-list, since names cannot be parameters.
- **Trusting the type of a number.** `bigint`, `numeric`, `count(*)` and `sum` are strings. Convert on purpose, or cast in SQL, or `+` will concatenate.
- **Transactions through `pool.query`.** Use `pool.connect()`, and put `release()` in `finally`. A client that is never released slowly empties the pool.
- **No limits and no safety net.** Set `connectionTimeoutMillis` and `statement_timeout`, and add a `pool.on('error')` handler, or one dead idle connection can take the process down.
- **Reading the error message.** Branch on `err.code` (and `err.constraint`), not on the text.

## Exercise

Write `createOrder(customerId, productId, qty)` that inserts into `orders` and `order_items` inside `withTx`. Map `23503` to a 422 domain error, and write a test that proves a failed item insert leaves no row in `orders`.

## What's next

The next post is "NATS JetStream from Node.js". After the database comes the second pillar of a backend, messaging: how to send a message so it is not lost.
