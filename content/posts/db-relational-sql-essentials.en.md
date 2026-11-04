+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = 'The relational model and essential SQL'
description = 'The relational model and essential SQL with real PostgreSQL 18 output: keys, joins, GROUP BY, NULL traps, CTEs and constraint errors with SQLSTATE codes.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "sql", "postgres", "relational", "beginner"]
cover = { image = "/images/covers/db-relational-sql-essentials.png", alt = "The relational model and essential SQL", hiddenInSingle = true }
+++

Ask a database "which customers have never referred anyone?" with `NOT IN`, and you can get zero rows. No error, no warning, just an empty answer that looks perfectly reasonable. The cause is a single missing value hiding in the data. The worst SQL bugs look like this: the query runs, returns something, and the something is wrong.

This post is about learning SQL well enough to avoid those. In the Go posts we already talked to Postgres from code, in [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/) and [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/), but we treated the database as a box that accepts queries. This series opens the box. We start with the ground floor: what a table is, how tables are connected, and the handful of SQL features that cover most of daily work. By the end we will come back to the `NOT IN` puzzle and see exactly why it fails.

> Everything below ran on a real PostgreSQL 18.3 with `psql`, on a tiny hand-written dataset: 6 customers, 4 products, 5 orders. Every post in this series uses the same "shop" schema (customers, products, orders and order items), so it is worth getting to know it here.

## A table is a list of facts

Think of a spreadsheet where every row is one fact and every column is one property of that fact. One row in `customers` says "there is a customer named Ava, with this email, from Germany". That is the {{< term "relational-model" "relational model" >}}: data lives in **tables**, each table has **columns** with a fixed type (text, number, timestamp), and each **row** is one record.

Two kinds of keys tie the tables together:

- A {{< term "primary-key" "primary key" >}} is the column (or columns) that identifies a row. No two rows can share it, and it cannot be empty. In our schema every table has an `id` that the database numbers for us.
- A {{< term "foreign-key" "foreign key" >}} is a column that holds the primary key of a row in another table. `orders.customer_id` says "this order belongs to the customer with this id", and the database refuses a value that does not exist in `customers`.

We do not copy the customer's name into every order. The order stores only the customer's id, and when we need the name we look it up. That is the whole idea of "relational": tables are related through keys, not through copies.

Statements that define structure, such as `CREATE TABLE`, are called **DDL** (data definition). Statements that change rows (`INSERT`, `UPDATE`, `DELETE`) are **DML** (data manipulation). `psql`, the command-line client, can show us the structure. First `\dt` lists the tables, then `\d orders` describes one of them:

```text
\dt
          List of relations
 Schema |    Name     | Type  | Owner 
--------+-------------+-------+-------
 public | customers   | table | app
 public | order_items | table | app
 public | orders      | table | app
 public | products    | table | app

\d orders
                                    Table "public.orders"
   Column    |           Type           | Collation | Nullable |           Default            
-------------+--------------------------+-----------+----------+------------------------------
 id          | bigint                   |           | not null | generated always as identity
 customer_id | bigint                   |           | not null | 
 status      | text                     |           | not null | 
 created_at  | timestamp with time zone |           | not null | now()
 total_cents | bigint                   |           | not null | 0
Indexes:
    "orders_pkey" PRIMARY KEY, btree (id)
Check constraints:
    "orders_status_check" CHECK (status = ANY (ARRAY['new'::text, 'paid'::text, 'shipped'::text, 'cancelled'::text]))
Foreign-key constraints:
    "orders_customer_id_fkey" FOREIGN KEY (customer_id) REFERENCES customers(id)
Referenced by:
    TABLE "order_items" CONSTRAINT "order_items_order_id_fkey" FOREIGN KEY (order_id) REFERENCES orders(id)
```

How to read it: each column line gives a name, a type, whether it may be empty (`not null` means it may not) and a default. `id` is filled in by the database (`generated always as identity`), and `created_at` defaults to the current time. Money is stored as an integer number of cents, which avoids fractional-number rounding. Below the columns come the rules the table enforces: the primary key (`orders_pkey`, which comes with an index, a topic for two posts from now), a {{< term "check-constraint" "check constraint" >}} that allows only four status values, and the foreign key to `customers`. The last block says that `order_items` points back at this table.

The customers table, with a `referred_by` column I added for the NULL section (it holds the id of the customer who recommended this one, and may be empty):

```text
SELECT * FROM customers ORDER BY id;
 id | name  |       email       | country |        created_at         | referred_by 
----+-------+-------------------+---------+---------------------------+-------------
  1 | Ava   | ava@example.com   | DE      | 2026-01-05 13:30:00+03:30 |            
  2 | Ben   | ben@example.com   | US      | 2026-01-06 13:30:00+03:30 |           1
  3 | Cyrus | cyrus@example.com | IR      | 2026-01-07 13:30:00+03:30 |           1
  4 | Dana  | dana@example.com  | US      | 2026-01-08 13:30:00+03:30 |           2
  5 | Eli   | eli@example.com   | DE      | 2026-01-09 13:30:00+03:30 |            
  6 | Fay   | fay@example.com   | IR      | 2026-01-10 13:30:00+03:30 |            
```

(`created_at` is shown in my session's time zone, +03:30.) Ava referred Ben and Cyrus, and Ben referred Dana. The other three have an empty `referred_by`. Remember this table; we need it later.

## Reading and changing rows

`SELECT` reads. You say which columns, from which table, which rows (`WHERE`) and in which order (`ORDER BY`). `LIMIT` and `OFFSET` take a slice: `OFFSET 2` skips two rows and `LIMIT 2` returns the next two. Then `UPDATE` and `DELETE` change data, and adding `RETURNING` makes them hand back the rows they touched, so you do not need a second query to see what happened:

```text
SELECT name, country FROM customers WHERE country = 'US' ORDER BY name DESC;
 name | country 
------+---------
 Dana | US
 Ben  | US

SELECT id, name FROM customers ORDER BY id LIMIT 2 OFFSET 2;
 id | name  
----+-------
  3 | Cyrus
  4 | Dana

UPDATE orders SET status = 'paid' WHERE id = 2 RETURNING id, status;
 id | status 
----+--------
  2 | paid

DELETE FROM order_items WHERE order_id = 4 RETURNING *;
 order_id | product_id | qty | price_cents 
----------+------------+-----+-------------
        4 |          2 |   1 |        1500
```

The first query returns the two US customers, sorted by name from Z to A. The second skips Ava and Ben and returns Cyrus and Dana. The `UPDATE` marks order 2 as paid and shows the new state. The `DELETE` removes one line item from order 4 and shows what was removed.

One warning about the second query: without `ORDER BY`, the database promises no particular order, so `LIMIT` and `OFFSET` could pick different rows at different times. Always sort first.

## Joins: putting the pieces back together

An order stores only `customer_id`, so to print the customer's name next to the order we need to connect the two tables. That is what a {{< term "sql-join" "JOIN" >}} does: it pairs each row of one table with the matching rows of another, using a condition you give after `ON`.

```text
SELECT c.name, o.id AS order_id, o.status
FROM customers c JOIN orders o ON o.customer_id = c.id ORDER BY o.id;
 name  | order_id |  status   
-------+----------+-----------
 Ava   |        1 | paid
 Ava   |        2 | paid
 Ben   |        3 | shipped
 Cyrus |        4 | cancelled
 Dana  |        5 | paid
```

(`c` and `o` are short aliases for the table names.) This is an inner join: it keeps only the pairs that match. Eli and Fay have no orders, so they are not in the result at all. Often that is what you want, and sometimes it is exactly the problem. When you want every customer, with or without orders, use `LEFT JOIN`: it keeps every row from the left table and fills the right side with empty values ({{< term "sql-null" "NULL" >}}) when nothing matches.

```text
SELECT c.name, o.id AS order_id
FROM customers c LEFT JOIN orders o ON o.customer_id = c.id ORDER BY c.id, o.id;
 name  | order_id 
-------+----------
 Ava   |        1
 Ava   |        2
 Ben   |        3
 Cyrus |        4
 Dana  |        5
 Eli   |         
 Fay   |         
```

Now Eli and Fay appear, with nothing next to them. That gives us a useful trick. Adding `WHERE o.id IS NULL` keeps only the rows where nothing matched, so the query returns exactly Eli and Fay: the customers who never ordered.

## Grouping: one row per group

Sometimes you want a summary instead of a list: how many orders per country, and how much money. `GROUP BY` puts rows with the same value into one group, and **aggregate functions** such as `count` and `sum` compute one number per group:

```text
SELECT c.country, count(*) AS orders, sum(o.total_cents) AS cents
FROM customers c JOIN orders o ON o.customer_id = c.id
GROUP BY c.country ORDER BY c.country;
 country | orders | cents 
---------+--------+-------
 DE      |      2 |  6900
 IR      |      1 |  1500
 US      |      2 | 22500
```

Germany has two orders (both Ava's: 6000 + 900 cents), Iran one, the US two. To filter you have two tools, and the difference is when they act. `WHERE` filters rows before they are grouped. `HAVING` filters the groups after the aggregates are computed. For example, `GROUP BY c.name HAVING count(*) > 1` returns only Ava, the one customer with more than one order.

## NULL is not a value

Now the puzzle from the beginning. **NULL** means "unknown" or "missing", and it behaves unlike any normal value. Is an unknown equal to another unknown? We cannot say, so SQL answers with NULL again, which `WHERE` treats as "not true". I ran each of these:

```text
SELECT NULL = NULL AS eq, NULL IS NULL AS is_null;
 eq | is_null 
----+---------
    | t

SELECT count(*) AS all_rows, count(referred_by) AS with_referrer FROM customers;
 all_rows | with_referrer 
----------+---------------
        6 |             3

SELECT name FROM customers WHERE referred_by = NULL;       -- (0 rows)
SELECT name FROM customers WHERE referred_by IS NULL ORDER BY id;   -- Ava, Eli, Fay
```

`NULL = NULL` is not true, it is NULL (the empty cell under `eq`). Only `IS NULL` can test for it. That is why `= NULL` finds nothing while `IS NULL` finds the three customers without a referrer. The `count` line shows another consequence: `count(*)` counts rows (6), but `count(referred_by)` counts only non-NULL values (3).

Now the question "who has referred nobody?" Two ways to write it:

```text
SELECT id, name FROM customers WHERE id NOT IN (SELECT referred_by FROM customers);
 id | name 
----+------
(0 rows)

SELECT id, name FROM customers c
WHERE NOT EXISTS (SELECT 1 FROM customers r WHERE r.referred_by = c.id) ORDER BY id;
 id | name  
----+-------
  3 | Cyrus
  4 | Dana
  5 | Eli
  6 | Fay
```

The first query reads naturally, "ids that are not in the list of referrers", and returns nothing. The reason: the list of referrers contains NULL (Ava, Eli and Fay have none), so the list is `(1, 1, 2, NULL, NULL, NULL)`. For Cyrus, `3 NOT IN (1, 1, 2, NULL, ...)` means "3 is different from 1, and from 2, and from NULL". The last part is unknown, so the whole condition is unknown, and `WHERE` drops the row. Not one id can ever pass, so the result is empty.

The second query asks a different question: "is there any customer whose `referred_by` equals my id?" For each customer it looks for such a row, and NULL rows simply never match. It returns the four correct names. So the rule is: when a subquery can return NULL, use `NOT EXISTS` instead of `NOT IN`.

## CTEs: naming a step

As queries grow, nested subqueries get hard to read. A {{< term "cte" "CTE" >}} (common table expression) gives a step a name with `WITH`, so the query reads top to bottom. Here, "customers who spent more than 5000 cents, ignoring cancelled orders" is first computed per customer, then joined with the names:

```text
WITH spend AS (
  SELECT customer_id, sum(total_cents) AS cents
  FROM orders WHERE status <> 'cancelled' GROUP BY customer_id)
SELECT c.name, s.cents FROM spend s JOIN customers c ON c.id = s.customer_id
WHERE s.cents > 5000 ORDER BY s.cents DESC;
 name | cents 
------+-------
 Ben  | 18000
 Ava  |  6900
```

Ava's 6900 is 6000 plus 900. Dana's single order of 4500 is below the threshold, and Cyrus's order is cancelled, so neither appears.

## Constraints say no

A good schema does not rely on every piece of application code behaving. The rules we saw in `\d orders` are enforced by the database itself. Let's break each one on purpose. With `\set VERBOSITY verbose`, psql also prints the {{< term "sqlstate" "SQLSTATE" >}}: a five-character error code that is the same across messages and languages. The four attempts are: a duplicate email, an order for customer 999, an order with status `'lost'`, and deleting a customer who still has orders.

```text
ERROR:  23505: duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(ava@example.com) already exists.
ERROR:  23503: insert or update on table "orders" violates foreign key constraint "orders_customer_id_fkey"
DETAIL:  Key (customer_id)=(999) is not present in table "customers".
ERROR:  23514: new row for relation "orders" violates check constraint "orders_status_check"
DETAIL:  Failing row contains (7, 1, lost, <timestamp>, 0).
ERROR:  23503: update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

(psql also prints some `SCHEMA NAME`, `TABLE NAME`, `CONSTRAINT NAME` and `LOCATION` lines, which I left out; `<timestamp>` replaces the current time, and the `7` is an identity number that varies.) Each code names the kind of problem: `23505` is a unique violation, `23503` a foreign-key violation (note it covers both inserting a bad reference and deleting a referenced row), and `23514` a check violation. Your Go or Node code should branch on these codes, not on the message text, which can change between versions and languages.

## Common SQL traps

- `= NULL` never matches anything; use `IS NULL`. Be especially careful with `NOT IN` when the subquery can return NULL: it silently returns nothing. Use `NOT EXISTS`.
- `LIMIT` and `OFFSET` without `ORDER BY` pick rows in no promised order, so pages can overlap or skip rows.
- Every column in `SELECT` must either be in `GROUP BY` or be inside an aggregate. A column that is neither has no single value for the group, and Postgres rejects it (the one exception is a column that follows from a grouped primary key).
- A `LEFT JOIN` followed by a `WHERE` condition on the right table (for example `o.status = 'paid'`) throws away the rows with NULL on the right, which turns it back into an inner join. Put such a condition in the `ON` clause, unless you are deliberately testing for `IS NULL`.
- Let constraints enforce rules. An application check can be skipped by another service, a script or a bug; a constraint cannot.

## Exercise

On your own copy of the data: list the products that were never ordered, once with `LEFT JOIN` and once with `NOT EXISTS`. Then count the non-cancelled orders per country, only for countries with more than one.

## What's next

[Schema design and normalization](/posts/db-schema-design-normalization/). A correct query cannot rescue a bad design, so the next question is what the tables themselves should look like.
