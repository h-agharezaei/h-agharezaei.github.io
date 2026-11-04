+++
date = '2026-11-23T10:00:00+03:30'
draft = false
title = 'Schema design and normalization'
description = 'Schema design and normalization in PostgreSQL: see update, insert and delete anomalies on a flat table, then fix them with keys, constraints and types.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "schema-design", "normalization"]
cover = { image = "/images/covers/db-schema-design-normalization.png", alt = "Schema design and normalization", hiddenInSingle = true }
+++

Sara changes her email address. The application updates it, but only one of her three order rows gets the new value. Now the database holds two different emails for the same person, and nothing inside it can say which one is true. This is not a query bug. The query did what it was told. The bug is in how the tables were designed, and a bad design keeps hurting for years, because every query, report and migration has to work around it.

After [The relational model and essential SQL](/posts/db-relational-sql-essentials/), where we learned to read and write data, this post is about how the tables themselves should look. I start from a bad design on purpose, break it in three different ways, and then fix it step by step.

> Everything below ran on a real PostgreSQL 18.3, using the shop schema of this series.

## A flat table and three ways it breaks

The tempting first design is one big table, like a spreadsheet: one row per order, with everything about the customer and the product written on that row. Here is `orders_flat`:

```sql
CREATE TABLE orders_flat (
    order_id       int,
    customer_name  text,
    customer_email text,
    country        text,
    product_name   text,
    category       text,
    price_cents    int
);
INSERT INTO orders_flat VALUES
 (1, 'Sara',  'sara@example.com',  'DE', 'Keyboard', 'hardware', 4500),
 (2, 'Sara',  'sara@example.com',  'DE', 'Mouse',    'hardware', 1900),
 (3, 'Sara',  'sara@example.com',  'DE', 'Keyboard', 'hardware', 4500),
 (4, 'Omid',  'omid@example.com',  'IR', 'Mouse',    'hardware', 1900);
```

Sara has orders 1 to 3 and Omid has order 4. It looks fine until you notice that Sara's name, email and country are written three times, and the Keyboard's price twice. Every repeated fact is a chance for the copies to disagree. Database people call the problems that follow **anomalies**, and there are three kinds.

**Update anomaly.** Sara changes her email, and the code updates only order 1:

```text
UPDATE orders_flat SET customer_email = 'sara@new.example' WHERE order_id = 1;

 order_id | customer_name |  customer_email  
----------+---------------+------------------
        1 | Sara          | sara@new.example
        2 | Sara          | sara@example.com
        3 | Sara          | sara@example.com

SELECT DISTINCT customer_email FROM orders_flat WHERE customer_name = 'Sara';
  customer_email  
------------------
 sara@example.com
 sara@new.example
```

The first result shows the three rows; the second shows two different emails for one customer. Which one is true? The database cannot tell.

**Insert anomaly.** Lena registers but has not ordered anything yet. Where do we store her? Every row in this table is an order, so the only way is a half-empty row:

```text
INSERT INTO orders_flat (customer_name, customer_email, country) VALUES ('Lena', 'lena@example.com', 'SE');
 order_id | customer_name |  customer_email  | country | product_name | category | price_cents 
----------+---------------+------------------+---------+--------------+----------+-------------
          | Lena          | lena@example.com | SE      |              |          |            
```

Every order and product column is NULL. That is a fake order that every report now has to remember to skip. (I deleted it again before the next step.)

**Delete anomaly.** Omid's only order is cancelled, so we delete it. Then we count his rows:

```text
DELETE FROM orders_flat WHERE order_id = 4;
SELECT count(*) AS omid_rows FROM orders_flat WHERE customer_name = 'Omid';
 omid_rows 
-----------
         0
```

Omid is gone entirely: his name, email and country disappeared together with his order.

All three have one cause: several different facts (about customers, about products, about orders) are stored in one table, so they live and die together.

## Normalization: every fact in one place

The fix has a simple core idea. {{< term "normalization" "Normalization" >}} means splitting a table until each fact is stored in exactly one place. Sara's email is one fact, so it should be one cell in one row. Everything else refers to Sara by her id.

People describe the steps as "normal forms". The textbook definitions are more formal; here is the practical reading, tied to our example:

- **First normal form (1NF):** every cell holds one value, and every row can be identified. No "Keyboard, Mouse" in a single cell, because you could not search, count or constrain it properly.
- **Second normal form (2NF):** when a row is identified by several columns together, every other column must depend on all of them. An order line is identified by (order, product). The product's name depends only on the product, not on the order, so it moves to its own `products` table.
- **Third normal form (3NF):** columns should describe the row's key, not another column. The customer's country describes the customer, not the order, so it moves to `customers`.

Applied to `orders_flat`, the result is the shop schema we already know. Each arrow means "refers to by id":

```text
customers   (id, name, email, country, created_at)
products    (id, name, category, price_cents)
orders      (id, customer_id -> customers, status, created_at, total_cents)
order_items (order_id -> orders, product_id -> products, qty, price_cents)
```

Now let's retell the same stories on these tables. I created the schema, added Sara and Omid, a keyboard, and two orders for Sara, then changed her email once:

```text
UPDATE customers SET email='sara@new.example' WHERE id=1;
 id |      email       
----+------------------
  1 | sara@new.example

SELECT c.name, count(o.id) AS orders FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.name ORDER BY c.name;
 name | orders 
------+--------
 Omid |      0
 Sara |      2
```

Sara's email exists in exactly one place, so there is nothing to disagree with. Omid exists as a customer with 0 orders (the `LEFT JOIN` from the previous post keeps him), which solves the insert anomaly. And deleting an order can no longer delete a customer, since they are different rows in different tables.

## Keys and foreign keys

Splitting only works if the pieces are tied back together reliably, and that is the job of keys. Every table gets this line:

```sql
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

This is a {{< term "surrogate-key" "surrogate key" >}}: a number the database generates, with no business meaning, that never needs to change. The email looks like a natural identifier, but people change emails, and an identifier that changes would have to be updated in every table that refers to it. So the email gets a `UNIQUE` constraint instead, and the `id` is what other tables point at. `ALWAYS` makes PostgreSQL refuse a hand-written id. I tried one, and the error (with `\set VERBOSITY verbose`, which also prints the {{< term "sqlstate" "SQLSTATE" >}} code) is:

```text
ERROR:  428C9: cannot insert a non-DEFAULT value into column "id"
DETAIL:  Column "id" is an identity column defined as GENERATED ALWAYS.
HINT:  Use OVERRIDING SYSTEM VALUE to override.
```

A {{< term "foreign-key" "foreign key" >}} ties an order to its customer. What should happen when you delete a customer who still has orders? The default is to refuse:

```text
ERROR:  23503: update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

The alternative is `ON DELETE CASCADE`: delete the customer and the database deletes the orders too. I tried it on a throwaway table, `orders_c`, with two orders for customer 2. After deleting customer 2 there were none left, and nothing warned me:

```text
SELECT count(*) AS orders_c_left FROM orders_c;
 orders_c_left 
---------------
             0
```

My judgment: keep the default (refuse) for anything related to money, where a silent delete is a disaster, and use `CASCADE` only for child data that has no meaning on its own.

## Constraints that catch bugs

With the tables split, rules can live in the schema, where no code path can skip them. In my run the database rejected each of these:

- a negative price (`CHECK (price_cents >= 0)`): `23514`, "Failing row contains (2, Bad, x, -5)";
- a duplicate email (`UNIQUE`): `23505`;
- an order with `customer_id = 999` (foreign key): `23503`;
- an order with status `'lost'` (`CHECK`): `23514`.

A {{< term "partial-index" "partial unique index" >}} can express a rule that a plain constraint cannot: "a customer may have at most one open order". A unique index normally covers the whole table; adding `WHERE` makes it cover only the rows that match, so only those must be unique:

```sql
CREATE UNIQUE INDEX one_open_order_per_customer
  ON orders (customer_id) WHERE status = 'new';
```

In my demo customer 1 already had one `'new'` order (order 1), so both new `'new'` orders I tried to insert failed with a duplicate key error, while a `'cancelled'` one went in without a problem:

```text
ERROR:  23505: duplicate key value violates unique constraint "one_open_order_per_customer"
DETAIL:  Key (customer_id)=(1) already exists.
```

(That error appeared twice, once per attempt. The `'cancelled'` insert printed `INSERT 0 1`.) `\d orders` afterwards lists the new index with its condition: `UNIQUE, btree (customer_id) WHERE status = 'new'::text`.

## Data types

A schema is also a set of type choices, and a few of them cause real bugs.

**Money is not `float`.** Floating-point numbers store binary approximations, and decimal fractions like 0.1 cannot be stored exactly:

```text
SELECT 0.1::float8 + 0.2::float8;        -> 0.30000000000000004   (equal to 0.3? f)
SELECT 0.1::numeric + 0.2::numeric;      -> 0.3                   (equal to 0.3? t)
sum of 0.1 a thousand times, float8      -> 99.9999999999986
sum of 0.1 a thousand times, numeric     -> 100.0
```

(This is a compact summary of the results of the demo queries, one line per query.) Use `numeric`, or do what the shop schema does and keep integer cents (`price_cents bigint`: 10 + 20 is exactly 30).

**`timestamp` or `timestamptz`?** `timestamp` stores a wall-clock reading with no time zone, like "10:00 on the wall". `timestamptz` stores an exact instant. I inserted the same value into both columns and read it back under two session time zones:

```text
Asia/Tehran:       a = 2026-11-23 10:00:00   b = 2026-11-23 13:30:00+03:30
America/New_York:  a = 2026-11-23 10:00:00   b = 2026-11-23 05:00:00-05
```

`a` (the `timestamp`) printed the same in both zones, so you cannot tell what moment it means. `b` (the `timestamptz`) was converted to each zone's local time; it is the same instant shown two ways. Default to `timestamptz`.

**`text` or `varchar(n)`?** According to the PostgreSQL docs, there is no performance advantage to `varchar(n)` (the only difference is a small check of the length). So use `text`, and add a `CHECK` on the length when you have a real rule.

**Enum or lookup table?** An enum type is compact, but once values are in use it is awkward to change. A lookup table, a small table of allowed values plus a foreign key, is easy to extend and can carry extra columns, such as a display name. The shop uses `CHECK (status IN (...))`, which is the simplest option but needs a migration to change. I pick a lookup table once the values start changing often.

## When to denormalize, and other traps

{{< term "denormalization" "Denormalization" >}} is the opposite move: deliberately storing a fact in more than one place. It is a trade, not a sin, but make it with measurements, not by habit.

- Denormalize only after measuring. Justified cases in my experience: a stored `total_cents` on `orders` that you keep in sync, reporting tables, and history snapshots such as the price at purchase time (`order_items.price_cents`). The last one is not even duplication: the product's price today and the price the customer paid are two different facts.
- A foreign key does not create an index on the referencing column (`orders.customer_id`). Joins and deletes on the parent table can become slow without one; the next post covers it.
- `CASCADE` can delete far more than you expect, because it follows chains of foreign keys.
- Normalizing means more tables and more joins. That is normal, and it is the cost of one source of truth.

## Exercise

Create `orders_flat` yourself with a `shipping_address` column. Normalize it into an `addresses` table, and write a `CHECK` that forbids empty names. Then try to delete an address that an order uses.

## What's next

[B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/). The data is shaped correctly now. Once there is a lot of it, the next question is how PostgreSQL finds the rows it needs quickly.
