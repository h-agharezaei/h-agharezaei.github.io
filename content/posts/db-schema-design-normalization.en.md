+++
date = '2026-11-23T10:00:00+03:30'
draft = false
title = 'Schema design and normalization'
description = 'Schema design and normalization in PostgreSQL: see update, insert and delete anomalies on a flat table, then fix them with keys, constraints and types.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "schema-design", "normalization"]
cover = { image = "/images/covers/db-schema-design-normalization.png", alt = "Schema design and normalization", hiddenInSingle = true }
+++

In the [previous post](/posts/db-relational-sql-essentials/) we learned the relational model and the SQL to query it. Now the question that comes before every query: how should the tables look? A bad schema hurts for years. Here I start from a bad table on purpose, watch it break, and fix it step by step.

> Everything ran on a real PostgreSQL 18.3, using the shop schema of this series.

## A flat table and three anomalies

`orders_flat` has one row per order, with the customer and product details repeated on each row (4 rows: Sara has orders 1-3, Omid has order 4).

**Update anomaly.** Sara changes her email. I update only order 1:

```text
 order_id | customer_name |  customer_email
----------+---------------+------------------
        1 | Sara          | sara@new.example
        2 | Sara          | sara@example.com
        3 | Sara          | sara@example.com
```

Which one is true? The database cannot tell.

**Insert anomaly.** Lena registers but has not ordered yet. The only way to store her is a half-empty row with NULL in every order and product column. That is a fake order.

**Delete anomaly.** Omid's only order is cancelled, so I delete it. His row count afterwards: `omid_rows = 0`. We lost the customer too.

All three have one cause: several different facts (customer, product, order) share one table.

## Normalization, in plain words

{{< term "normalization" "Normalization" >}} means each fact lives in one place. Three steps, tied to this example:

- **1NF**: every cell holds one value and rows are identifiable. No "keyboard, mouse" in one cell.
- **2NF**: every column depends on the whole key. In an order line keyed by (order, product), the product's name depends only on the product, so it moves to `products`.
- **3NF**: columns depend on the key, not on other columns. The customer's country depends on the customer, not on the order, so it moves to `customers`.

The result is the shop schema: `customers`, `products`, `orders`, `order_items`. Now Sara's email is one row, Lena exists without orders (I checked with a `LEFT JOIN`: Omid shows 0 orders), and deleting an order never deletes a customer.

## Keys and foreign keys

```sql
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

This is a {{< term "surrogate-key" "surrogate key" >}}: a number with no business meaning that never changes. The email is a natural key that can change, so it is `UNIQUE` instead. `ALWAYS` makes PostgreSQL refuse a manual id:

```text
ERROR:  cannot insert a non-DEFAULT value into column "id"
DETAIL:  Column "id" is an identity column defined as GENERATED ALWAYS.
```

A {{< term "foreign-key" "foreign key" >}} links orders to customers. With the default behaviour, deleting a customer who still has orders is rejected:

```text
ERROR:  update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

With `ON DELETE CASCADE` (I tried it on a throwaway `orders_c` table) deleting customer 2 removed their 2 orders silently: `orders_c_left = 0`. My judgment: use the default (reject) for money-related data and CASCADE only for true child data that has no meaning alone.

## Constraints that catch bugs

Each of these was rejected by the database in my run: a negative price (`CHECK`), a duplicate email (`UNIQUE`), `customer_id = 999` (foreign key), and status `'lost'` (`CHECK`).

A {{< term "partial-index" "partial unique index" >}} expresses "one open order per customer":

```sql
CREATE UNIQUE INDEX one_open_order_per_customer
  ON orders (customer_id) WHERE status = 'new';
```

A second `'new'` order for the same customer failed with a duplicate key error, while a `'cancelled'` one went in fine.

## Data types

Money is not `float`:

```text
SELECT 0.1::float8 + 0.2::float8;        -> 0.30000000000000004   (equal to 0.3? f)
SELECT 0.1::numeric + 0.2::numeric;      -> 0.3                   (equal to 0.3? t)
sum of 0.1 a thousand times, float8      -> 99.9999999999986
sum of 0.1 a thousand times, numeric     -> 100.0
```

Use `numeric` or, like the shop schema, integer cents (`price_cents bigint`: 10 + 20 is exactly 30).

`timestamp` stores a wall-clock reading with no zone; `timestamptz` stores an instant. I inserted the same value and read it back under two session time zones:

```text
Asia/Tehran:       a = 2026-11-23 10:00:00   b = 2026-11-23 13:30:00+03:30
America/New_York:  a = 2026-11-23 10:00:00   b = 2026-11-23 05:00:00-05
```

`a` never changed, so you cannot tell what moment it means. Default to `timestamptz`.

`text` or `varchar(n)`? According to the PostgreSQL docs there is no performance advantage for `varchar(n)`, so use `text` and add a `CHECK` on length when a real rule exists.

Enum or lookup table? An enum type is compact but changing it is awkward. A lookup table plus a foreign key is easy to extend and can carry extra columns. The shop uses `CHECK (status IN (...))`, which is simple but needs a migration to change. I pick a lookup table once values change often.

## A few things to watch

- Denormalize only after measuring. Justified cases in my experience: a stored `total_cents` on `orders` that you keep in sync, reporting tables, and history snapshots such as the price at purchase time (`order_items.price_cents`).
- Foreign keys do not create an index on the referencing column; that is a topic for the next post.
- `CASCADE` can delete far more than you expect.

## Exercise

Create `orders_flat` yourself with a `shipping_address` column. Normalize it into an `addresses` table, and write a `CHECK` that forbids empty names. Then try to delete an address that an order uses.

## What's next

The next post is "B-tree indexes and EXPLAIN ANALYZE": how PostgreSQL finds rows fast, and how to read its plans.
