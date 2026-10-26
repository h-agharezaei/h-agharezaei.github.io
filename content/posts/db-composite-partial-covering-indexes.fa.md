+++
date = '2026-12-05T10:00:00+03:30'
draft = false
title = 'ایندکس ترکیبی، جزئی و پوششی'
description = 'ایندکس ترکیبی، جزئی و پوششی در PostgreSQL 18: ترتیب ستون‌ها، INCLUDE و Index Only Scan، ایندکس عبارتی، با planهای واقعی EXPLAIN.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "indexes", "explain", "performance"]
cover = { image = "/images/covers/db-composite-partial-covering-indexes.fa.png", alt = "ایندکس ترکیبی، جزئی و پوششی", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-indexes-btree-explain/) ایندکس‌های تک‌ستونی ساختیم و planشان را با `EXPLAIN ANALYZE` خواندیم. کوئری واقعی کم‌تر روی یک ستون فیلتر می‌کند. ابزارهای بعدی: {{< term "composite-index" "ایندکس ترکیبی" >}} (**composite index**)، {{< term "partial-index" "ایندکس جزئی" >}} (**partial index**)، {{< term "covering-index" "ایندکس پوششی" >}} (**covering index**) و {{< term "expression-index" "ایندکس عبارتی" >}} (**expression index**).

> همه‌چیز روی PostgreSQL 18.3 واقعی و با schema مشترک shop (۲۰۰ هزار سفارش، ۲۰ هزار مشتری) اجرا شده. planها از `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` آمده و فقط خطوط مهم را نگه داشته‌ام. به‌جای میلی‌ثانیه تعداد bufferها را می‌آورم، چون به ماشین بستگی ندارد.

## ترتیب ستون‌ها مهم است

کوئری: سفارش‌های یک مشتری در یک هفته. همان دو ستون، دو ترتیب:

```sql
CREATE INDEX orders_cust_created ON orders (customer_id, created_at);   -- A
CREATE INDEX orders_created_cust ON orders (created_at, customer_id);   -- B
SELECT id, total_cents FROM orders
WHERE customer_id = 42 AND created_at >= '2025-02-01' AND created_at < '2025-02-08';
```

```text
A: Index Scan using orders_cust_created   Buffers: shared hit=3 read=3     (6 pages)
B: Index Scan using orders_created_cust   Buffers: shared hit=9 read=16    (25 pages)
```

هر دو کار می‌کنند، اما B تمام ورودی‌های ایندکس آن هفته (حدود ۳۵۰۰ سفارش) را می‌گردد و `customer_id` را داخلشان چک می‌کند، در حالی که A مستقیم به مشتری ۴۲ می‌پرد. قاعده‌ی سرانگشتی: **ستون‌های مساوی (equality) اول، ستون بازه (range) آخر**. A همچنین `WHERE customer_id = 42 ORDER BY created_at DESC LIMIT 3` را بدون Sort جواب می‌دهد (`Index Scan Backward`، ۶ صفحه)، چون ورودی‌های هر مشتری از قبل بر اساس تاریخ مرتب‌اند.

## پیشوند چپ و یک سورپرایز در PostgreSQL 18

ایندکس `(a, b)` اول بر اساس `a` مرتب است، پس کوئری فقط روی `b` نمی‌تواند در آن جست‌وجو کند. روی `orders (customer_id, created_at)` فیلتر فقط روی یک روز، یک `Seq Scan` موازی روی ۳۳۵۷ صفحه داد.

اما روی `customers (country, created_at)` (۱۲ کشور) همین نوع کوئری از ایندکس استفاده کرد:

```text
Bitmap Index Scan on customers_country_created
  Index Cond: (created_at >= ... AND created_at < ...)
  Index Searches: 18
```

`Index Searches: 18` یعنی به‌جای یک بار، چندین بار در ایندکس جست‌وجو شد. تا جایی که می‌دانم این همان skip scan است که در PostgreSQL 18 آمده و فقط وقتی به کار می‌آید که ستون اول مقدارهای متمایز کمی داشته باشد. روی آن حساب نکنید: ستونی را که همیشه فیلتر می‌کنید اول بگذارید.

## ایندکس جزئی: فقط ردیف‌هایی که می‌پرسید

فقط ۸٪ سفارش‌ها `new` هستند و کوئری‌های مهم درباره‌ی همین‌ها می‌پرسند:

```sql
CREATE INDEX orders_status_created_full ON orders (status, created_at);
CREATE INDEX orders_created_new ON orders (created_at) WHERE status = 'new';
```

```text
orders_status_created_full   4448 kB
orders_created_new            312 kB
```

وقتی هر دو بودند، planner برای `status = 'new'` به‌همراه یک هفته `created_at` ایندکس جزئی را انتخاب کرد. محدودیت: برای `status = 'paid'` یا بدون شرط status قابل استفاده نیست و هر دو `Seq Scan` شدند (۳۳۵۷ صفحه). `WHERE` کوئری باید `WHERE` ایندکس را نتیجه بدهد.

## ایندکس پوششی و سورپرایز Index Only Scan

{{< term "index-only-scan" "Index Only Scan" >}} کوئری را فقط از ایندکس جواب می‌دهد. ستون اضافه را با `INCLUDE` می‌آوریم (ذخیره می‌شود ولی مرتب نیست):

```sql
CREATE INDEX orders_cust_created_inc ON orders (customer_id, created_at) INCLUDE (total_cents);
SELECT created_at, total_cents FROM orders WHERE customer_id BETWEEN 100 AND 199;
```

```text
without INCLUDE: Bitmap Heap Scan        Buffers: 763 pages
with INCLUDE:    Index Only Scan         Heap Fetches: 0     Buffers: 9 pages
```

حالا تله‌ی کلاسیک. ۲۰٪ سفارش‌ها را update کردم و vacuum نزدم:

```text
Index Only Scan ...   Heap Fetches: 1200   Buffers: shared hit=1213
```

همان node، ولی ۱۲۱۳ صفحه. ایندکس نمی‌داند ردیف برای ما قابل‌دیدن است یا نه؛ {{< term "visibility-map" "visibility map" >}} صفحه‌های کاملاً قابل‌دیدن heap را علامت می‌زند و update این بیت‌ها را پاک کرد. بعد از `VACUUM orders` (درباره‌ی {{< term "vacuum" "VACUUM" >}}) شد `Heap Fetches: 0` و ۱۴ صفحه. پس Index Only Scan روی جدول پر‌update به عقب‌نماندن vacuum وابسته است. انتخاب `status` هم که در ایندکس نیست، دوباره Bitmap Heap Scan شد.

## ایندکس عبارتی و شرط‌های non-sargable

شرطی {{< term "sargable" "sargable" >}} است که planner بتواند آن را به جست‌وجوی ایندکس تبدیل کند. پیچیدن ستون در تابع این را می‌شکند:

```text
WHERE email = 'user777@example.com'          -> Index Scan (unique index)
WHERE lower(email) = 'user777@example.com'   -> Seq Scan, Rows Removed by Filter: 19999, 207 pages
```

راه‌حل ایندکس عبارتی است: `CREATE INDEX customers_email_lower ON customers (lower(email))`. بعدش همان کوئری از آن استفاده کرد (`Index Scan`، ۳ صفحه). کوئری باید دقیقاً همان عبارت را بنویسد.

## دو ایندکس تکی یا یک ترکیبی؟

با ایندکس‌های جدا روی `status` و `customer_id`، PostgreSQL آن‌ها را با {{< term "bitmap-scan" "BitmapAnd" >}} ترکیب می‌کند:

```text
BitmapAnd -> Bitmap Index Scan on orders_status_idx   (16000 rows)
          -> Bitmap Index Scan on orders_cust_idx     (15000 rows)
Result: 1200 rows, index buffers 37
```

یک ایندکس ترکیبی `(customer_id, status)` همان ردیف‌ها را با ۲۳ buffer ایندکس و همان ۸۷۸ صفحه‌ی heap برگرداند. سود اینجا کوچک است.

## هر ایندکس هزینه دارد

اندازه‌ها از `pg_stat_user_indexes` در پایان: `orders_pkey` ‏8792 kB، `orders_cust_status` ‏2016 kB، `orders_cust_idx` ‏1856 kB، `orders_status_idx` ‏1368 kB. هرکدام با هر insert و update نوشته می‌شود. حالا `orders_cust_idx` اضافه است چون `(customer_id, status)` کوئری‌های `customer_id` را هم جواب می‌دهد.

## چند نکته‌ی مهم

- ستون‌های equality اول، ستون range آخر؛ ستون `ORDER BY` را درست بعد از equalityها بگذارید.
- ایندکس جزئی کوچک است، ولی فقط کوئری‌ای از آن استفاده می‌کند که `WHERE`اش شرط ایندکس را نتیجه بدهد.
- ستون‌های `INCLUDE` فقط بار اضافه‌اند؛ `Heap Fetches` را در `EXPLAIN` ببینید و vacuum را سالم نگه دارید.
- ستون ایندکس‌شده را در تابع نپیچید؛ ایندکس عبارتی بسازید یا شرط را بازنویسی کنید.
- چک‌لیست خودم: کوئری‌های واقعی را فهرست کنید، برای پرتکرارترین یک ترکیبی بسازید، برای ستون‌های نامتوازن جزئی را بسنجید، بلااستفاده‌ها را حذف کنید.

## تمرین

کندترین کوئری دو‌شرطی‌تان را بردارید. هر دو ترتیب ستون را بسازید، `Buffers` را مقایسه کنید، بازنده را حذف کنید، و بعد در `pg_stat_user_indexes` دنبال ایندکس‌هایی با `idx_scan` صفر بگردید.

## قدم بعدی

گاهی ایندکس درست وجود دارد و PostgreSQL باز هم نادیده‌اش می‌گیرد. پست بعدی: «planner و آمار: چرا ایندکس استفاده نمی‌شود».
