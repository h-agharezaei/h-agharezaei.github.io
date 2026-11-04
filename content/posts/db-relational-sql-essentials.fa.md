+++
date = '2026-11-19T10:00:00+03:30'
draft = false
title = 'مدل رابطه‌ای و SQL ضروری'
description = 'مدل رابطه‌ای و SQL ضروری با خروجی واقعی PostgreSQL 18: کلیدها، join، GROUP BY، تله‌های NULL، CTE و خطاهای constraint با کدهای SQLSTATE.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "sql", "postgres", "relational", "beginner"]
cover = { image = "/images/covers/db-relational-sql-essentials.fa.png", alt = "مدل رابطه‌ای و SQL ضروری", hiddenInSingle = true }
+++

فرض کنید از دیتابیس می‌پرسید «کدام مشتری‌ها تا حالا کسی را معرفی نکرده‌اند؟» و سؤال را با `NOT IN` می‌نویسید. ممکن است جواب صفر ردیف باشد. نه خطایی، نه هشداری؛ فقط یک جواب خالی که کاملاً معقول به نظر می‌رسد. علتش یک مقدار خالی است که جایی در داده قایم شده. بدترین باگ‌های SQL همین شکلی‌اند: query اجرا می‌شود، چیزی برمی‌گرداند، و آن چیز غلط است.

این پست برای این است که SQL را آن‌قدر خوب یاد بگیریم که به این دام‌ها نیفتیم. در پست‌های Go از داخل کد با Postgres حرف زدیم، در [Postgres با pgx و sqlc در Go](/fa/posts/go-postgres-pgx-sqlc/) و [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/)، اما دیتابیس را جعبه‌ای در نظر گرفتیم که query می‌گیرد و جواب می‌دهد. این سری درِ آن جعبه را باز می‌کند. از طبقه‌ی اول شروع می‌کنیم: جدول چیست، جدول‌ها چطور به هم وصل می‌شوند، و چند قابلیت SQL که بیشتر کارهای روزمره را پوشش می‌دهند. آخر کار به معمای `NOT IN` برمی‌گردیم و می‌بینیم دقیقاً چرا خراب می‌شود.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی با `psql` و یک دیتاست کوچک دست‌نویس اجرا شده: ۶ مشتری، ۴ محصول، ۵ سفارش. همه‌ی پست‌های این سری از همین schema فروشگاهی («shop») استفاده می‌کنند (مشتری، محصول، سفارش و آیتم‌های سفارش)، پس ارزش دارد همین‌جا با آن آشنا شویم.

## جدول، فهرستی از واقعیت‌ها

یک صفحه‌گسترده (spreadsheet) را در نظر بگیرید که هر ردیفش یک واقعیت است و هر ستونش یک ویژگی از آن واقعیت. یک ردیف در `customers` می‌گوید «مشتری‌ای به اسم Ava هست، با این ایمیل، از آلمان». این است {{< term "relational-model" "مدل رابطه‌ای" >}}: داده در **جدول**ها زندگی می‌کند، هر جدول **ستون**هایی با نوع ثابت دارد (متن، عدد، زمان) و هر **ردیف** یک رکورد است.

دو نوع کلید جدول‌ها را به هم وصل می‌کنند:

- {{< term "primary-key" "کلید اصلی" >}} (**primary key**) ستون (یا ستون‌هایی) است که ردیف را مشخص می‌کند. دو ردیف نمی‌توانند مقدار یکسان داشته باشند و خالی هم نمی‌شود. در schema ما هر جدول یک `id` دارد که دیتابیس خودش شماره می‌زند.
- {{< term "foreign-key" "کلید خارجی" >}} (**foreign key**) ستونی است که کلید اصلی یک ردیف از جدول دیگر را نگه می‌دارد. `orders.customer_id` می‌گوید «این سفارش مال مشتری‌ای با این id است» و دیتابیس مقداری را که در `customers` نباشد نمی‌پذیرد.

اسم مشتری را در هر سفارش کپی نمی‌کنیم. سفارش فقط id مشتری را نگه می‌دارد و هر وقت اسم لازم شد، آن را پیدا می‌کنیم. «رابطه‌ای» یعنی همین: جدول‌ها با کلید به هم مربوط‌اند، نه با کپی.

دستورهایی که ساختار را تعریف می‌کنند، مثل `CREATE TABLE`، **DDL** (تعریف داده) نام دارند. دستورهایی که ردیف‌ها را عوض می‌کنند (`INSERT`، `UPDATE`، `DELETE`) **DML** (دست‌کاری داده) هستند. `psql`، کلاینت خط فرمان، ساختار را نشانمان می‌دهد. اول `\dt` جدول‌ها را فهرست می‌کند و بعد `\d orders` یکی از آن‌ها را توصیف می‌کند:

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

خواندنش این‌طور است: هر خط ستون یک اسم دارد، یک نوع، اینکه می‌تواند خالی باشد یا نه (`not null` یعنی نمی‌تواند) و یک مقدار پیش‌فرض. `id` را خود دیتابیس پر می‌کند (`generated always as identity`) و `created_at` به‌طور پیش‌فرض زمان حال است. پول را به‌صورت عدد صحیحِ «سنت» نگه می‌داریم تا با گرد شدن اعداد اعشاری درگیر نشویم. زیر ستون‌ها قاعده‌هایی می‌آید که جدول اجرا می‌کند: کلید اصلی (`orders_pkey`، که یک ایندکس هم همراهش ساخته می‌شود و موضوع دو پست بعد است)، یک {{< term "check-constraint" "check constraint" >}} که فقط چهار مقدار برای status اجازه می‌دهد، و کلید خارجی به `customers`. بلوک آخر می‌گوید `order_items` به این جدول اشاره می‌کند.

جدول مشتری‌ها، با ستون `referred_by` که برای بخش NULL اضافه کرده‌ام (id مشتری‌ای را نگه می‌دارد که این یکی را معرفی کرده و می‌تواند خالی باشد):

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

(`created_at` با منطقه‌ی زمانی نشست من، +03:30، نمایش داده شده.) Ava دو نفر را معرفی کرده، Ben و Cyrus، و Ben یک نفر را، Dana. سه نفر دیگر `referred_by` خالی دارند. این جدول را یادتان بماند؛ بعداً لازمش داریم.

## خواندن و تغییر ردیف‌ها

`SELECT` می‌خواند. می‌گویید کدام ستون‌ها، از کدام جدول، کدام ردیف‌ها (`WHERE`) و با چه ترتیبی (`ORDER BY`). `LIMIT` و `OFFSET` یک برش می‌گیرند: `OFFSET 2` دو ردیف را رد می‌کند و `LIMIT 2` دو ردیف بعدی را برمی‌گرداند. بعد `UPDATE` و `DELETE` داده را عوض می‌کنند، و اگر `RETURNING` اضافه کنید ردیف‌هایی را که دست زده‌اند پس می‌دهند، پس برای دیدن نتیجه به query دوم نیازی نیست:

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

query اول دو مشتری آمریکایی را برمی‌گرداند، مرتب‌شده از Z به A. دومی Ava و Ben را رد می‌کند و Cyrus و Dana را می‌دهد. `UPDATE` سفارش ۲ را «پرداخت‌شده» می‌کند و وضعیت جدید را نشان می‌دهد. `DELETE` یک آیتم از سفارش ۴ را پاک می‌کند و همان را نشان می‌دهد.

یک هشدار درباره‌ی query دوم: بدون `ORDER BY` دیتابیس هیچ ترتیبی را تضمین نمی‌کند، پس `LIMIT` و `OFFSET` ممکن است هر بار ردیف‌های دیگری بردارند. همیشه اول مرتب کنید.

## Join: کنار هم گذاشتن تکه‌ها

سفارش فقط `customer_id` را نگه می‌دارد، پس برای چاپ اسم مشتری کنار سفارش باید دو جدول را وصل کنیم. کار {{< term "sql-join" "JOIN" >}} همین است: هر ردیف یک جدول را با ردیف‌های منطبق جدول دیگر جفت می‌کند، با شرطی که بعد از `ON` می‌دهید.

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

(`c` و `o` نام‌های کوتاه برای جدول‌ها هستند.) این join داخلی است: فقط جفت‌های منطبق را نگه می‌دارد. Eli و Fay سفارشی ندارند، پس اصلاً در نتیجه نیستند. گاهی همین چیزی است که می‌خواهید و گاهی دقیقاً همان مشکل. وقتی همه‌ی مشتری‌ها را می‌خواهید، چه سفارش داشته باشند چه نه، `LEFT JOIN` می‌خواهید: همه‌ی ردیف‌های جدول چپ را نگه می‌دارد و اگر چیزی منطبق نشد سمت راست را با مقدار خالی ({{< term "sql-null" "NULL" >}}) پر می‌کند.

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

حالا Eli و Fay هم هستند، با خانه‌ی خالی. این یک ترفند به ما می‌دهد. اگر `WHERE o.id IS NULL` اضافه کنید فقط ردیف‌هایی می‌مانند که چیزی به آن‌ها نخورده، یعنی دقیقاً Eli و Fay: مشتری‌هایی که هیچ‌وقت سفارش نداده‌اند.

## گروه‌بندی: یک ردیف برای هر گروه

گاهی خلاصه می‌خواهید، نه فهرست: در هر کشور چند سفارش و چقدر پول. `GROUP BY` ردیف‌های هم‌مقدار را در یک گروه می‌گذارد و **تابع‌های تجمیعی** (aggregate) مثل `count` و `sum` برای هر گروه یک عدد حساب می‌کنند:

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

آلمان دو سفارش دارد (هر دو مال Ava: ۶۰۰۰ + ۹۰۰ سنت)، ایران یکی و آمریکا دو تا. برای فیلتر دو ابزار دارید و فرقشان در زمان کارشان است. `WHERE` ردیف‌ها را قبل از گروه‌بندی فیلتر می‌کند و `HAVING` گروه‌ها را بعد از محاسبه‌ی تجمیع‌ها. مثلاً `GROUP BY c.name HAVING count(*) > 1` فقط Ava را برمی‌گرداند، تنها مشتری‌ای که بیشتر از یک سفارش دارد.

## NULL یک مقدار نیست

حالا معمای اول پست. **NULL** یعنی «نامعلوم» یا «غایب» و مثل هیچ مقدار عادی‌ای رفتار نمی‌کند. آیا یک نامعلوم با نامعلوم دیگر برابر است؟ نمی‌شود گفت، پس SQL دوباره NULL جواب می‌دهد و `WHERE` آن را «درست نیست» حساب می‌کند. همه‌ی این‌ها را اجرا کردم:

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

`NULL = NULL` درست نیست، خودش NULL است (خانه‌ی خالی زیر `eq`). فقط `IS NULL` می‌تواند آن را تست کند. برای همین `= NULL` هیچ‌چیز پیدا نمی‌کند و `IS NULL` سه مشتریِ بدون معرف را پیدا می‌کند. خط `count` یک نتیجه‌ی دیگر را نشان می‌دهد: `count(*)` ردیف‌ها را می‌شمارد (۶) ولی `count(referred_by)` فقط مقدارهای غیر NULL را (۳).

حالا سؤال «چه کسی هیچ‌کس را معرفی نکرده؟» را به دو شکل می‌نویسیم:

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

query اول طبیعی خوانده می‌شود، «idهایی که در فهرست معرف‌ها نیستند»، و هیچ‌چیز برنمی‌گرداند. دلیل: فهرست معرف‌ها NULL دارد (Ava و Eli و Fay معرف ندارند)، پس فهرست `(1, 1, 2, NULL, NULL, NULL)` است. برای Cyrus، `3 NOT IN (1, 1, 2, NULL, ...)` یعنی «۳ با ۱ فرق دارد، و با ۲، و با NULL». بخش آخر نامعلوم است، پس کل شرط نامعلوم می‌شود و `WHERE` ردیف را کنار می‌گذارد. هیچ idای نمی‌تواند رد شود و نتیجه خالی است.

query دوم سؤال دیگری می‌پرسد: «آیا مشتری‌ای هست که `referred_by`اش برابر id من باشد؟» برای هر مشتری دنبال چنین ردیفی می‌گردد و ردیف‌های NULL هیچ‌وقت منطبق نمی‌شوند. چهار اسم درست را برمی‌گرداند. پس قاعده این است: وقتی subquery می‌تواند NULL برگرداند، به‌جای `NOT IN` از `NOT EXISTS` استفاده کنید.

## CTE: نام دادن به یک گام

وقتی query بزرگ می‌شود، subqueryهای تودرتو سخت خوانده می‌شوند. یک {{< term "cte" "CTE" >}} (common table expression) با `WITH` به یک گام نام می‌دهد تا query از بالا به پایین خوانده شود. اینجا «مشتری‌هایی که بیش از ۵۰۰۰ سنت خرج کرده‌اند، بدون سفارش‌های لغوشده» اول برای هر مشتری حساب می‌شود و بعد با اسم‌ها join می‌شود:

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

۶۹۰۰ برای Ava همان ۶۰۰۰ به‌علاوه‌ی ۹۰۰ است. سفارش تکی Dana، ۴۵۰۰، زیر آستانه است و سفارش Cyrus لغو شده، پس هیچ‌کدام در نتیجه نیستند.

## constraintها «نه» می‌گویند

schema خوب به این تکیه نمی‌کند که همه‌ی کدهای برنامه درست رفتار کنند. قاعده‌هایی که در `\d orders` دیدیم را خود دیتابیس اجرا می‌کند. بیایید عمداً هر کدام را بشکنیم. با `\set VERBOSITY verbose` ‏psql کد {{< term "sqlstate" "SQLSTATE" >}} را هم چاپ می‌کند: یک کد پنج‌نویسه که در همه‌ی نسخه‌ها و زبان‌ها یکی است. چهار تلاش این‌هاست: ایمیل تکراری، سفارش برای مشتری ۹۹۹، سفارشی با status برابر `'lost'`، و پاک کردن مشتری‌ای که هنوز سفارش دارد.

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

(psql چند خط `SCHEMA NAME`، `TABLE NAME`، `CONSTRAINT NAME` و `LOCATION` هم چاپ می‌کند که حذفشان کرده‌ام؛ `<timestamp>` جای زمان حال نشسته و عدد `7` شماره‌ی identity است و تغییر می‌کند.) هر کد نوع مشکل را می‌گوید: `23505` نقض یکتایی است، `23503` نقض کلید خارجی (هم برای درج مرجع بد و هم برای پاک کردن ردیفی که به آن ارجاع داده شده) و `23514` نقض check. کد Go یا Node شما باید روی همین کدها تصمیم بگیرد، نه روی متن پیام که بین نسخه‌ها و زبان‌ها عوض می‌شود.

## تله‌های رایج SQL

- `= NULL` هیچ‌وقت چیزی را پیدا نمی‌کند؛ از `IS NULL` استفاده کنید. مراقب `NOT IN` باشید وقتی subquery می‌تواند NULL برگرداند: بی‌صدا هیچ‌چیز برنمی‌گرداند. از `NOT EXISTS` استفاده کنید.
- `LIMIT` و `OFFSET` بدون `ORDER BY` ردیف‌ها را با ترتیب تضمین‌نشده برمی‌دارند، پس صفحه‌ها ممکن است هم‌پوشانی داشته باشند یا ردیفی جا بماند.
- هر ستون در `SELECT` باید یا در `GROUP BY` باشد یا داخل یک تابع تجمیعی. ستونی که هیچ‌کدام نیست برای گروه یک مقدار واحد ندارد و Postgres آن را رد می‌کند (تنها استثنا ستونی است که از یک کلید اصلیِ گروه‌بندی‌شده نتیجه می‌شود).
- `LEFT JOIN` و بعد یک شرط `WHERE` روی جدول سمت راست (مثلاً `o.status = 'paid'`) ردیف‌های NULLِ سمت راست را دور می‌ریزد و آن را دوباره به join داخلی تبدیل می‌کند. چنین شرطی را در `ON` بگذارید، مگر عمداً `IS NULL` را تست می‌کنید.
- قاعده‌ها را به constraint بسپارید. چک برنامه را ممکن است سرویس دیگر، یک اسکریپت یا یک باگ دور بزند؛ constraint را نه.

## تمرین

روی نسخه‌ی خودتان از داده: محصولاتی را که هیچ‌وقت سفارش داده نشده‌اند فهرست کنید، یک بار با `LEFT JOIN` و یک بار با `NOT EXISTS`. بعد تعداد سفارش‌های غیرلغوشده را به تفکیک کشور بشمارید، فقط برای کشورهایی که بیش از یک سفارش دارند.

## قدم بعدی

[طراحی schema و نرمال‌سازی](/fa/posts/db-schema-design-normalization/). query درست نمی‌تواند طراحی بد را نجات دهد، پس سؤال بعدی این است که خود جدول‌ها چه شکلی باشند.
