+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = 'The relational model and essential SQL'
description = 'The relational model and essential SQL with real PostgreSQL 18 output: keys, joins, GROUP BY, NULL traps, CTEs and constraint errors with SQLSTATE codes.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "sql", "postgres", "relational", "beginner"]
cover = { image = "/images/covers/db-relational-sql-essentials.png", alt = "The relational model and essential SQL", hiddenInSingle = true }
+++

This post opens the Databases series. In the Go posts we already talked to Postgres from code, see [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/) and [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/). Here we step back and learn the database side properly, starting with SQL itself.

> Everything below ran on a real PostgreSQL 18.3 with `psql`, on a tiny hand-written dataset: 6 customers, 4 products, 5 orders. All the series posts share this "shop" schema.

## Tables, keys, DDL and DML

In the {{< term "relational-model" "relational model" >}} data lives in tables: rows are facts, columns are typed attributes. A {{< term "primary-key" "primary key" >}} identifies a row, and a {{< term "foreign-key" "foreign key" >}} says "this value must exist in that other table". Statements that define structure (`CREATE TABLE`) are DDL; statements that change rows (`INSERT`, `UPDATE`, `DELETE`) are DML. `psql` can show the structure:

```text
shop=> \dt
 public | customers   | table | app
 public | order_items | table | app
 public | orders      | table | app
 public | products    | table | app

shop=> \d orders
 id          | bigint      | not null | generated always as identity
 customer_id | bigint      | not null |
 status      | text        | not null |
 created_at  | timestamptz | not null | now()
 total_cents | bigint      | not null | 0
Indexes:
    "orders_pkey" PRIMARY KEY, btree (id)
Check constraints:
    "orders_status_check" CHECK (status = ANY (ARRAY['new', 'paid', 'shipped', 'cancelled']))
Foreign-key constraints:
    "orders_customer_id_fkey" FOREIGN KEY (customer_id) REFERENCES customers(id)
```

(I trimmed some columns and casts from the real output.) I also added a nullable `referred_by` column to `customers` for the NULL section.

## Reading and changing rows

```sql
SELECT name, country FROM customers WHERE country = 'US' ORDER BY name DESC;
-- Dana US, Ben US
SELECT id, name FROM customers ORDER BY id LIMIT 2 OFFSET 2;
-- 3 Cyrus, 4 Dana
UPDATE orders SET status = 'paid' WHERE id = 2 RETURNING id, status;
-- 2 | paid
DELETE FROM order_items WHERE order_id = 4 RETURNING *;
-- 4 | 2 | 1 | 1500
```

`RETURNING` gives back the rows that were changed, which saves a second query. Without `ORDER BY`, `LIMIT` and `OFFSET` pick rows in no promised order. Always sort first.

## Joins

An inner {{< term "sql-join" "JOIN" >}} keeps only matching rows. A `LEFT JOIN` keeps every customer, and "no match" shows up as empty (NULL) columns:

```text
SELECT c.name, o.id AS order_id FROM customers c LEFT JOIN orders o ON o.customer_id = c.id ORDER BY c.id, o.id;
 Ava   | 1
 Ava   | 2
 Ben   | 3
 Cyrus | 4
 Dana  | 5
 Eli   |
 Fay   |
```

Adding `WHERE o.id IS NULL` keeps only Eli and Fay: customers who never ordered.

## Grouping

```text
SELECT c.country, count(*) AS orders, sum(o.total_cents) AS cents
FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.country ORDER BY c.country;
 DE | 2 |  6900
 IR | 1 |  1500
 US | 2 | 22500
```

`WHERE` filters rows before grouping, `HAVING` filters groups after. `HAVING count(*) > 1` returned only Ava with 2 orders.

## NULL is not a value

{{< term "sql-null" "NULL" >}} means unknown, and I ran each of these:

```text
SELECT NULL = NULL AS eq, NULL IS NULL AS is_null;      -- eq: (empty)   is_null: t
SELECT count(*), count(referred_by) FROM customers;     -- 6 | 3
SELECT name FROM customers WHERE referred_by = NULL;    -- 0 rows
SELECT name FROM customers WHERE referred_by IS NULL;   -- Ava, Eli, Fay
```

`count(*)` counts rows, `count(col)` counts non-NULL values. The nastiest one: "who has referred nobody?"

```text
SELECT id, name FROM customers WHERE id NOT IN (SELECT referred_by FROM customers);
(0 rows)
SELECT id, name FROM customers c WHERE NOT EXISTS
  (SELECT 1 FROM customers r WHERE r.referred_by = c.id) ORDER BY id;
 3 Cyrus | 4 Dana | 5 Eli | 6 Fay
```

The subquery contains NULLs, so `id NOT IN (..., NULL)` is never true and you silently get nothing. Use `NOT EXISTS`.

## Subqueries and CTEs

A {{< term "cte" "CTE" >}} names a step so the query reads top to bottom:

```text
WITH spend AS (
  SELECT customer_id, sum(total_cents) AS cents
  FROM orders WHERE status <> 'cancelled' GROUP BY customer_id)
SELECT c.name, s.cents FROM spend s JOIN customers c ON c.id = s.customer_id
WHERE s.cents > 5000 ORDER BY s.cents DESC;
 Ben | 18000
 Ava |  6900
```

## Constraints say no

With `\set VERBOSITY verbose` psql prints the {{< term "sqlstate" "SQLSTATE" >}}:

```text
ERROR:  23505: duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(ava@example.com) already exists.
ERROR:  23503: insert or update on table "orders" violates foreign key constraint "orders_customer_id_fkey"
DETAIL:  Key (customer_id)=(999) is not present in table "customers".
ERROR:  23514: new row for relation "orders" violates check constraint "orders_status_check"
ERROR:  23503: update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

Your Go or Node code should branch on these codes, not on the message text.

## A few things to watch

- `= NULL` never matches; use `IS NULL`. Beware `NOT IN` with a subquery that can return NULL.
- `LIMIT`/`OFFSET` without `ORDER BY` is not stable.
- Every column in `SELECT` must be grouped or aggregated.
- `LEFT JOIN` plus a `WHERE` on the right table silently turns it into an inner join (unless you test `IS NULL`).
- Let constraints enforce rules; do not rely only on application checks.

## Exercise

On your own copy of the data: list products that were never ordered (use `LEFT JOIN` and, separately, `NOT EXISTS`), then the number of non-cancelled orders per country, only for countries with more than one.

## What's next

Next: Schema design and normalization.
