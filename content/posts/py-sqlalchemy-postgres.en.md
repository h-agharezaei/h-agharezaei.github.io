+++
date = '2027-05-01T10:00:00+03:30'
draft = false
title = 'SQLAlchemy and Postgres'
description = 'SQLAlchemy 2.1 with Postgres: Core text(), ORM Session, N+1 counted for real, pool limits, IntegrityError, isolation, Alembic and async, all run.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "sqlalchemy", "postgres", "alembic", "orm"]
cover = { image = "/images/covers/py-sqlalchemy-postgres.png", alt = "SQLAlchemy and Postgres", hiddenInSingle = true }
+++

In the [previous post](/posts/py-fastapi-pydantic/) the API had no database. Here we add one. SQLAlchemy has two layers: Core (SQL as Python, with bound parameters) and the {{< term "orm" "ORM" >}} on top. If you used `pg` from Node ([Postgres from Node.js](/posts/node-postgres-pg/)) or pgx in Go ([Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/)), think of Core as the driver and the ORM as an optional extra.

> Python 3.14.0, SQLAlchemy 2.1.6, psycopg 3.3.6 (`[binary]`, bundled libpq 18.0.6), Alembic 1.20.1, greenlet 3.5.6, real PostgreSQL 18.3 on `127.0.0.1`, throwaway venv. Ports replaced by `<port>`. I publish counts, not timings.

## Core: text() and bound parameters

```python
with engine.begin() as c:
    c.execute(text("INSERT INTO customers (email) VALUES (:e)"), [{"e": "a@example.com"}, ...])
    c.execute(text("SELECT count(*) FROM customers WHERE email = :e"), {"e": "x' OR '1'='1"}).scalar()
```

The second line printed `0`: the value travels as a parameter, so it is data, not SQL ({{< term "parameterized-query" "parameterized query" >}}). `engine.begin()` opens a {{< term "transaction" "transaction" >}} and commits on exit.

## The ORM: Session as a unit of work

```python
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
```

`Order` has a `ForeignKey("customers.id")` and the reverse `customer`. A `Session` is a {{< term "unit-of-work" "unit of work" >}}: it collects changes and flushes them together. I added a customer and counted rows:

```text
autoflush sees it: 4
after rollback: 3
after commit: 4
```

The query flushed the pending INSERT first (autoflush), so it saw 4. `rollback()` undid it; `commit()` made it permanent.

## A real IntegrityError

Adding a duplicate email and committing raised `IntegrityError`; the wrapped driver error is:

```text
UniqueViolation | duplicate key value violates unique constraint "customers_email_key"
```

Catch it, then call `rollback()`: the session cannot be used until you do.

## N+1, counted

I hooked `before_cursor_execute` to count statements, with 4 customers and 5 orders:

```text
lazy: 5 queries, result=5
selectinload: 2 queries, result=5
joinedload: 1 queries, result=5
```

Lazy loading is the default: one query for customers, then one per customer ({{< term "n-plus-one" "N+1" >}}). `selectinload` runs a second query with `IN (...)`; `joinedload` uses a JOIN (and needs `.unique()` on results). Which is better depends on shape; the point is to count. See the case in [finding a slow query](/posts/db-slow-query-case-study/).

## Seeing the SQL

`create_engine(url, echo=True)` logs everything. For one `select(Customer).where(Customer.id == 1)`:

```text
BEGIN (implicit)
SELECT customers.id, customers.email
FROM customers
WHERE customers.id = %(id_1)s::INTEGER
[generated ...] {'id_1': 1}
ROLLBACK
```

(Timestamps removed.) `str(query)` prints the SQL with placeholders; compiling with `literal_binds` lets you paste it into `EXPLAIN`. Here Postgres chose `Seq Scan on orders` with `Filter: (customer_id = 1)`: the table is tiny, and there is no index on `customer_id`, which Postgres does not create for a foreign key ([B-tree indexes](/posts/db-indexes-btree-explain/)).

## The pool

```python
create_engine(url, pool_size=2, max_overflow=1, pool_pre_ping=True, pool_timeout=1)
```

I checked out three connections and `engine.pool.status()` said `Pool size: 2  Connections in pool: 0 Current Overflow: 1 Current Checked out connections: 3`. A fourth failed after one second:

```text
TimeoutError | QueuePool limit of size 2 overflow 1 reached, connection timed out, timeout 1.00
```

After closing all, the status was `Connections in pool: 2 ... Checked out connections: 0`. `pool_pre_ping` tests a connection before use. Background: [connection pooling](/posts/db-connection-pooling/).

## Isolation levels

`create_engine(url, isolation_level="REPEATABLE READ")` made `SHOW transaction_isolation` return `repeatable read`; per connection, `execution_options(isolation_level="SERIALIZABLE")` returned `serializable`. What the levels mean is in [isolation levels](/posts/db-isolation-levels-anomalies/); I did not run concurrent sessions here.

## Alembic

With Alembic, `revision --autogenerate` compared my models with the empty database and wrote an `op.create_table` migration for both tables. `upgrade head --sql` printed the DDL:

```text
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, ...);
CREATE TABLE customers (id SERIAL NOT NULL, email VARCHAR(100) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE orders (id SERIAL NOT NULL, customer_id INTEGER NOT NULL, total INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(customer_id) REFERENCES customers (id));
INSERT INTO alembic_version (version_num) VALUES ('15ffbe55f27f') ...;
```

(Whitespace condensed.) Then `upgrade head` applied it, `current` showed `15ffbe55f27f (head)`, and `alembic check` said `No new upgrade operations detected`. Safe changes on live tables: [zero-downtime migrations](/posts/db-zero-downtime-migrations/). I did not run `downgrade`.

## Async

`create_async_engine` with the same psycopg URL ran three queries with `asyncio.gather` and returned `[5, 6, 7]` ([asyncio](/posts/py-asyncio/)). My first attempt failed with `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`; installing `greenlet` fixed it.

## Versus sqlc and pgx

With sqlc you write SQL and get generated, type-checked Go functions; the ORM does the reverse, generating SQL from objects. Either way a connection pool and parameter binding sit underneath.

## A few things to watch

- Count queries in tests; lazy loading hides N+1.
- Rollback after an error before reusing a session.
- Size `pool_size + max_overflow` against Postgres `max_connections`.
- Review autogenerated migrations; do not trust them blindly.

## Exercise

Add an `order_items` table and a migration. Load customers with their orders and items using nested `selectinload`, and assert the query count.

## What's next

The next post is "Packaging and publishing a Python project".
