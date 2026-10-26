+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = 'مدل رابطه‌ای و SQL ضروری'
description = 'مدل رابطه‌ای و SQL ضروری با خروجی واقعی PostgreSQL 18: کلیدها، join، GROUP BY، تله‌های NULL، CTE و خطاهای constraint با کدهای SQLSTATE.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "sql", "postgres", "relational", "beginner"]
cover = { image = "/images/covers/db-relational-sql-essentials.fa.png", alt = "مدل رابطه‌ای و SQL ضروری", hiddenInSingle = true }
+++

این پست شروع سری Databases است. در پست‌های Go قبلاً از داخل کد با Postgres حرف زدیم، یعنی [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/) و [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/). حالا یک قدم عقب می‌رویم و سمت دیتابیس را درست یاد می‌گیریم، با خود SQL شروع می‌کنیم.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی با `psql` و یک دیتاست کوچک دست‌نویس اجرا شده: ۶ مشتری، ۴ محصول، ۵ سفارش. همه‌ی پست‌های این سری از همین schema فروشگاهی («shop») استفاده می‌کنند.

## جدول، کلید، DDL و DML

در {{< term "relational-model" "مدل رابطه‌ای" >}} داده در جدول‌ها زندگی می‌کند: سطرها واقعیت‌اند و ستون‌ها ویژگی‌های نوع‌دار. {{< term "primary-key" "کلید اصلی" >}} (**primary key**) سطر را مشخص می‌کند و {{< term "foreign-key" "کلید خارجی" >}} (**foreign key**) می‌گوید «این مقدار باید در آن جدول دیگر وجود داشته باشد». دستورهایی که ساختار را تعریف می‌کنند (`CREATE TABLE`) **DDL** هستند و دستورهایی که سطرها را عوض می‌کنند (`INSERT`، `UPDATE`، `DELETE`) **DML**. `psql` ساختار را نشان می‌دهد:

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

(بعضی ستون‌ها و castها را از خروجی واقعی کوتاه کرده‌ام.) برای بخش NULL یک ستون nullable به اسم `referred_by` هم به `customers` اضافه کردم.

## خواندن و تغییر سطرها

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

`RETURNING` سطرهای تغییرکرده را برمی‌گرداند و یک query اضافه را حذف می‌کند. بدون `ORDER BY`، `LIMIT` و `OFFSET` سطرها را با ترتیب تضمین‌نشده برمی‌دارند. همیشه اول مرتب کنید.

## Join

یک {{< term "sql-join" "JOIN" >}} داخلی فقط سطرهای منطبق را نگه می‌دارد. `LEFT JOIN` همه‌ی مشتری‌ها را نگه می‌دارد و «بدون تطابق» به شکل ستون‌های خالی (NULL) دیده می‌شود:

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

با اضافه کردن `WHERE o.id IS NULL` فقط Eli و Fay می‌مانند: مشتری‌هایی که هیچ‌وقت سفارش نداده‌اند.

## گروه‌بندی

```text
SELECT c.country, count(*) AS orders, sum(o.total_cents) AS cents
FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY c.country ORDER BY c.country;
 DE | 2 |  6900
 IR | 1 |  1500
 US | 2 | 22500
```

`WHERE` سطرها را قبل از گروه‌بندی فیلتر می‌کند و `HAVING` گروه‌ها را بعد از آن. `HAVING count(*) > 1` فقط Ava را با ۲ سفارش برگرداند.

## NULL یک مقدار نیست

{{< term "sql-null" "NULL" >}} یعنی نامعلوم، و همه‌ی این‌ها را اجرا کردم:

```text
SELECT NULL = NULL AS eq, NULL IS NULL AS is_null;      -- eq: (empty)   is_null: t
SELECT count(*), count(referred_by) FROM customers;     -- 6 | 3
SELECT name FROM customers WHERE referred_by = NULL;    -- 0 rows
SELECT name FROM customers WHERE referred_by IS NULL;   -- Ava, Eli, Fay
```

`count(*)` سطرها را می‌شمارد و `count(col)` مقدارهای غیر NULL را. بدترینش این است: «چه کسی هیچ‌کس را معرفی نکرده؟»

```text
SELECT id, name FROM customers WHERE id NOT IN (SELECT referred_by FROM customers);
(0 rows)
SELECT id, name FROM customers c WHERE NOT EXISTS
  (SELECT 1 FROM customers r WHERE r.referred_by = c.id) ORDER BY id;
 3 Cyrus | 4 Dana | 5 Eli | 6 Fay
```

subquery شامل NULL است، پس `id NOT IN (..., NULL)` هرگز درست نمی‌شود و بی‌صدا هیچ نتیجه‌ای نمی‌گیرید. از `NOT EXISTS` استفاده کنید.

## Subquery و CTE

یک {{< term "cte" "CTE" >}} به یک گام نام می‌دهد تا query از بالا به پایین خوانده شود:

```text
WITH spend AS (
  SELECT customer_id, sum(total_cents) AS cents
  FROM orders WHERE status <> 'cancelled' GROUP BY customer_id)
SELECT c.name, s.cents FROM spend s JOIN customers c ON c.id = s.customer_id
WHERE s.cents > 5000 ORDER BY s.cents DESC;
 Ben | 18000
 Ava |  6900
```

## constraintها «نه» می‌گویند

با `\set VERBOSITY verbose` ‏psql کد {{< term "sqlstate" "SQLSTATE" >}} را هم چاپ می‌کند:

```text
ERROR:  23505: duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(ava@example.com) already exists.
ERROR:  23503: insert or update on table "orders" violates foreign key constraint "orders_customer_id_fkey"
DETAIL:  Key (customer_id)=(999) is not present in table "customers".
ERROR:  23514: new row for relation "orders" violates check constraint "orders_status_check"
ERROR:  23503: update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

کد Go یا Node شما باید روی همین کدها تصمیم بگیرد، نه روی متن پیام.

## چند نکته‌ی مهم

- `= NULL` هیچ‌وقت match نمی‌شود؛ از `IS NULL` استفاده کنید. مراقب `NOT IN` با subqueryای که می‌تواند NULL برگرداند باشید.
- `LIMIT`/`OFFSET` بدون `ORDER BY` پایدار نیست.
- هر ستون در `SELECT` باید یا گروه‌بندی شده باشد یا aggregate.
- `LEFT JOIN` به‌علاوه‌ی `WHERE` روی جدول سمت راست بی‌صدا آن را به join داخلی تبدیل می‌کند (مگر `IS NULL` را بررسی کنید).
- قواعد را به constraint بسپارید؛ فقط به چک‌های برنامه تکیه نکنید.

## تمرین

روی نسخه‌ی خودتان از داده: محصولاتی را که هیچ‌وقت سفارش داده نشده‌اند فهرست کنید (یک بار با `LEFT JOIN` و یک بار با `NOT EXISTS`)، سپس تعداد سفارش‌های غیرلغوشده را به تفکیک کشور بشمارید، فقط برای کشورهایی که بیش از یک سفارش دارند.

## قدم بعدی

بعدی: «طراحی schema و نرمال‌سازی».
