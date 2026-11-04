+++
date = '2027-05-01T10:00:00+03:30'
draft = false
title = 'SQLAlchemy and Postgres'
description = 'SQLAlchemy 2.1 with Postgres: Core text(), ORM Session, N+1 counted for real, pool limits, IntegrityError, isolation, Alembic and async, all run.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "sqlalchemy", "postgres", "alembic", "orm"]
cover = { image = "/images/covers/py-sqlalchemy-postgres.png", alt = "SQLAlchemy and Postgres", hiddenInSingle = true }
+++

Here is a loop that looks completely innocent:

```python
for customer in session.scalars(select(Customer)):
    print(len(customer.orders))
```

With 4 customers in the database it sends 5 queries to Postgres: one to load the customers, and then one more for each customer, to load their orders. Nothing in the Python code says so. `customer.orders` looks like a plain list attribute, but touching it quietly goes to the database. With 4 customers that is harmless. With 10,000 it is a bad afternoon.

This is the main reason to understand SQLAlchemy before using it. The API from [the previous post](/posts/py-fastapi-pydantic/) has no database yet, and before adding one I want to see what the library does underneath. SQLAlchemy has two layers. **Core** lets you write SQL as Python and sends it with bound parameters. The **ORM** (object-relational mapper, {{< term "orm" "ORM" >}}) sits on top of Core and maps tables to Python classes, so rows become objects. If you used `pg` from Node ([Postgres from Node.js](/posts/node-postgres-pg/)) or pgx in Go ([Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/)), think of Core as the driver and the ORM as an optional extra on top.

> I re-ran the demo with Python 3.14.0, SQLAlchemy 2.1.6, psycopg 3.3.6 (the `[binary]` install, with bundled libpq 18.0.6), Alembic 1.20.1 and greenlet 3.5.6, against a real PostgreSQL 18.3 on `127.0.0.1`, in a throwaway virtual environment. I replace the port with `<port>` where it would appear. I show counts, not timings. The Alembic revision id and the SQLAlchemy `generated in ...s` time change on every run.

## Core: text() and bound parameters

The simplest way to use SQLAlchemy is to write SQL yourself and let it deal with the connection:

```python
with engine.begin() as c:
    c.execute(text("INSERT INTO customers (email) VALUES (:e)"), [{"e": "a@example.com"}, ...])
    c.execute(text("SELECT count(*) FROM customers WHERE email = :e"), {"e": "x' OR '1'='1"}).scalar()
```

`:e` is a named placeholder. The value is never pasted into the SQL string. It travels to Postgres separately, as a parameter ({{< term "parameterized-query" "parameterized query" >}}). To check that, the second statement looks up an email that is a classic injection string. It printed `0`: Postgres looked for a customer whose email is literally that odd text, found none, and the quote did not change the meaning of the query. That is the defence against {{< term "sql-injection" "SQL injection" >}}. `engine.begin()` opens a {{< term "transaction" "transaction" >}} and commits when the `with` block ends (or rolls back if it raises).

## The ORM: a Session as a unit of work

The ORM lets you describe tables as classes:

```python
class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True)
    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
```

`Order` is the other side: it has a `ForeignKey("customers.id")` and a `customer` attribute pointing back. `relationship` is what makes `customer.orders` work, and, as we will see, it is also what hides the extra queries.

You talk to the database through a `Session`. The best way to think about it is as a shopping basket, formally a {{< term "unit-of-work" "unit of work" >}}. You add objects and change them; the session remembers all of it and sends the changes together when it flushes. To see how this behaves I added a customer and counted the rows at three moments. There were 3 customers before:

```text
autoflush sees it: 4
after rollback: 3
after commit: 4
```

After `s.add(...)` I ran a count query and got 4, even though I had not committed. The reason is **autoflush**: before running a query, the session first sends its pending changes to the database (inside the open transaction), so the query sees them. Then `rollback()` undid the insert and the count went back to 3. After adding again and calling `commit()`, the row was permanent: 4.

## A real IntegrityError

What happens when the database refuses a change? I added a customer whose email already exists and committed. SQLAlchemy raised `IntegrityError`, and the original driver error inside it says:

```text
UniqueViolation | duplicate key value violates unique constraint "customers_email_key"
```

The `unique=True` from the model became a real constraint in Postgres, so the database enforced it, not Python. Catch the error, and then call `rollback()`. The session is left in a failed state after an error and cannot be used for anything until you roll back.

## N+1, counted

Now the loop from the beginning. To count queries instead of guessing, I attached a listener to the `before_cursor_execute` event, which SQLAlchemy fires before every statement it sends, and incremented a counter in it. Then I ran the same job three ways. Each one loads all customers and sums the lengths of their `orders` lists. The database had 4 customers and 5 orders:

```python
def lazy():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer)))
def selectin():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer).options(selectinload(Customer.orders))))
def joined():
    with Session(engine) as s:
        return sum(len(c.orders) for c in s.scalars(select(Customer).options(joinedload(Customer.orders))).unique())
```

```text
lazy: 5 queries, result=5
selectinload: 2 queries, result=5
joinedload: 1 queries, result=5
```

All three return the same answer, 5 orders. What differs is the number of round trips to the database:

- **Lazy loading** is the default. One query loads the customers; then each customer's first access to `.orders` runs one more. That is 1 + 4 = 5, the {{< term "n-plus-one" "N+1" >}} pattern: one query plus N more.
- **`selectinload`** loads the customers, then runs one more query for all their orders at once, with `WHERE customer_id IN (...)`. Two queries, however many customers.
- **`joinedload`** uses a single JOIN, so one query. Because a customer with three orders appears as three rows, you need `.unique()` on the result to get each customer once.

Which one is better depends on the shape of the data, and a JOIN is not always cheaper. The thing to take away is to count. For a real case of tracking down a slow query, see [Finding a slow query](/posts/db-slow-query-case-study/).

## Seeing the SQL

If you want to see what the ORM sends, `create_engine(url, echo=True)` logs every statement. For one `select(Customer).where(Customer.id == 1)` the log was:

```text
BEGIN (implicit)
SELECT customers.id, customers.email
FROM customers
WHERE customers.id = %(id_1)s::INTEGER
[generated ...] {'id_1': 1}
ROLLBACK
```

I removed the timestamps, and the three setup queries SQLAlchemy runs when it first connects (version, current schema, string settings). Read it top to bottom: the session started a transaction, sent a `SELECT` with a placeholder, and sent the value `1` separately. The `ROLLBACK` at the end is just the session closing without any changes.

You can also print a query without running it: `str(query)` gives the SQL with placeholders. Compiling it with `literal_binds` puts the values inline, so you can paste it after `EXPLAIN`. For `select(Order).where(Order.customer_id == 1)`, Postgres answered with `Seq Scan on orders` and `Filter: (customer_id = 1)`: it read the whole table. The table is tiny, so that is fine here, but note that there is no index on `customer_id`. Postgres does not create an index for a foreign key by itself. On a large table you would add one ([B-tree indexes](/posts/db-indexes-btree-explain/)).

## The connection pool

Opening a database connection is slow, so SQLAlchemy keeps a pool of them ({{< term "connection-pool" "connection pool" >}}) and lends them out. The pool has limits, and what happens at the limit is worth seeing once:

```python
create_engine(url, pool_size=2, max_overflow=1, pool_pre_ping=True, pool_timeout=1)
```

This pool keeps 2 connections and may open 1 extra under pressure, so 3 at most. I checked out three connections and printed `engine.pool.status()`:

```text
Pool size: 2  Connections in pool: 0 Current Overflow: 1 Current Checked out connections: 3
```

Nothing is left in the pool and one overflow connection is in use. A fourth request had to wait, and after `pool_timeout=1` second it failed:

```text
TimeoutError | QueuePool limit of size 2 overflow 1 reached, connection timed out, timeout 1.00
```

After I closed all three, the status was `Connections in pool: 2 ... Checked out connections: 0`: the connections went back to the pool for reuse, and the overflow one was closed. `pool_pre_ping=True` makes the pool test a connection with a tiny query before handing it out, so a connection that died while idle is replaced instead of failing your request. More on why pools exist is in [Connection pooling](/posts/db-connection-pooling/).

## Isolation levels

Transactions that run at the same time can see each other's changes in different ways, depending on the isolation level. SQLAlchemy lets you set it for the whole engine or for one connection. `create_engine(url, isolation_level="REPEATABLE READ")` made `SHOW transaction_isolation` return `repeatable read`, and `execution_options(isolation_level="SERIALIZABLE")` on one connection returned `serializable`. What the levels actually mean is in [Isolation levels](/posts/db-isolation-levels-anomalies/). I did not run concurrent sessions here, only checked that the setting reaches Postgres.

## Alembic: schema changes as code

Until now the demo created its tables with `create_all`, which is fine for a demo but cannot change an existing table. **Alembic** keeps the schema's history as numbered migration files. The command `alembic revision --autogenerate` compares your models with the real database and writes a migration for the difference. Against an empty database it wrote an `op.create_table` migration for both tables. Then `alembic upgrade head --sql` printed the SQL it would run, without running it:

```text
CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL, ...);
CREATE TABLE customers (id SERIAL NOT NULL, email VARCHAR(100) NOT NULL, PRIMARY KEY (id), UNIQUE (email));
CREATE TABLE orders (id SERIAL NOT NULL, customer_id INTEGER NOT NULL, total INTEGER NOT NULL, PRIMARY KEY (id), FOREIGN KEY(customer_id) REFERENCES customers (id));
INSERT INTO alembic_version (version_num) VALUES ('15ffbe55f27f') ...;
```

(Whitespace condensed; the revision id `15ffbe55f27f` is from the original run, a new run generates a different one.) The first table, `alembic_version`, is Alembic's own bookkeeping: it stores which revision the database is at, and the last line records it. Then `upgrade head` applied the migration, `alembic current` showed the revision with `(head)`, and `alembic check` answered `No new upgrade operations detected`, meaning the models and the database agree. I did not run `downgrade`. How to change a live table without downtime is in [Zero-downtime migrations](/posts/db-zero-downtime-migrations/).

## Async

SQLAlchemy also works with asyncio. `create_async_engine` with the same psycopg URL ran three queries concurrently with `asyncio.gather` and returned `[5, 6, 7]` (each query computes `i + count(*)` over the 5 orders, for `i` = 0, 1, 2; see [asyncio in Python](/posts/py-asyncio/)). My first run failed with `ImportError: The SQLAlchemy asyncio module requires that the Python 'greenlet' library is installed`; installing `greenlet` fixed it.

## Compared with sqlc and pgx

With sqlc you write the SQL and get generated, type-checked Go functions; the ORM works the other way round and generates SQL from your objects. Either way, a connection pool and parameter binding sit underneath, and in both cases you should still look at the SQL that actually runs.

## What to count and review

- Count queries in tests. Lazy loading hides N+1, and the code looks perfectly fine.
- After an error, roll back before reusing a session; otherwise the next call fails with a confusing message.
- Size `pool_size + max_overflow` against Postgres `max_connections`, and remember that every app process has its own pool.
- Read autogenerated migrations before applying them; do not trust them blindly. According to the Alembic docs, autogenerate cannot detect everything, a renamed column for example looks like a drop plus an add.

## Exercise

Add an `order_items` table and a migration for it. Load customers with their orders and items using nested `selectinload`, and write a test that asserts the query count.

## What's next

Next is "Packaging and publishing a Python project", because code becomes useful to other people only once they can install it.
