+++
date = '2026-11-29T10:00:00+03:30'
draft = false
title = 'ایندکس B-tree و EXPLAIN ANALYZE'
description = 'ایندکس B-tree در PostgreSQL با پلن‌های واقعی EXPLAIN ANALYZE: تفاوت sequential scan و ایندکس، ارتفاع درخت، index-only scan و هزینه ایندکس روی نوشتن.'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "index", "btree", "explain", "performance"]
cover = { image = "/images/covers/db-indexes-btree-explain.fa.png", alt = "ایندکس B-tree و EXPLAIN ANALYZE", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/db-schema-design-normalization/) schema فروشگاه را طراحی کردیم. حالا ۲۰۰ هزار سفارش داریم و اولین query کند پیدا شده: همه‌ی سفارش‌های یک مشتری. جواب معمول یک {{< term "database-index" "ایندکس" >}} است، ولی بیایید با یک {{< term "query-plan" "query plan" >}} امتحانش کنیم.

> همه‌چیز روی PostgreSQL 18.3 واقعی و با seed کامل (۲۰ هزار مشتری، ۲۰۰ هزار سفارش) اجرا شد. پیش از این پست فقط primary keyها و `customers.email` ایندکس داشتند. از `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` استفاده می‌کنم و به‌جای میلی‌ثانیه، تعداد bufferها (pageهای ۸ کیلوبایتی لمس‌شده) را نشان می‌دهم، چون روی هر ماشینی یکی است.

## خواندن یک پلن

```text
EXPLAIN (ANALYZE, BUFFERS, ...) SELECT * FROM orders WHERE customer_id = 123;

 Seq Scan on orders  (cost=0.00..5857.00 rows=10 width=39) (actual rows=10.00 loops=1)
   Filter: (customer_id = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
```

هر node یک `cost` دارد (تخمین planner با واحد قراردادی)، یک `rows` (تخمینی) و یک `actual rows` (واقعی). `Buffers: shared hit=3357` یعنی ۳۳۵۷ page از cache آمده؛ `read` یعنی از دیسک. جدول دقیقاً ۳۳۵۷ page (حدود ۲۶ مگابایت) است، پس برای برگرداندن ۱۰ ردیف کل جدول خوانده شد. (برای ساده ماندن پلن، اسکن موازی را خاموش کردم.)

## اضافه کردن ایندکس

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

```text
 Bitmap Heap Scan on orders  (cost=4.37..42.86 rows=10 ...) (actual rows=10.00 loops=1)
   Recheck Cond: (customer_id = 123)
   Heap Blocks: exact=10
   Buffers: shared hit=13 read=2
   ->  Bitmap Index Scan on orders_customer_id_idx  (actual rows=10.00 loops=1)
         Buffers: shared hit=3 read=2
```

از ۳۳۵۷ page به حدود ۱۵ رسیدیم و هزینه‌ی تخمینی از ۵۸۵۷ به ۴۲٫۹ افتاد. planner یک **Bitmap Heap Scan** انتخاب کرد: جای ردیف‌های مطابق را از ایندکس جمع می‌کند، بر اساس page مرتب می‌کند و هر page جدول را فقط یک بار می‌خواند. این ۱۰ ردیف در ۱۰ page مختلف بودند.

## B-tree چیست

نوع پیش‌فرض ایندکس یک {{< term "b-tree" "B-tree" >}} است: درخت متوازنی از pageهای ۸ کیلوبایتی با کلیدهای مرتب. جست‌وجو ریشه را می‌خواند، در هر سطح یک اشاره‌گر را دنبال می‌کند و به page برگی می‌رسد که به ردیف‌های جدول اشاره دارد. یک {{< term "binary-search" "جست‌وجوی دودویی" >}} با شاخه‌های بسیار زیاد است. اعداد واقعی با extension به نام `pageinspect`:

```text
SELECT level FROM bt_metap('orders_customer_id_idx');   -- 1  (ریشه + برگ‌ها)
SELECT level FROM bt_metap('orders_pkey');               -- 2  (ریشه + ۱ سطح + برگ‌ها)
```

ایندکس `customer_id` ‏۲۳۲ page (حدود ۱۸۵۶ کیلوبایت) و دو سطح دارد؛ ایندکس primary key سه سطح. برای همین `WHERE id = 123` فقط `Buffers: shared hit=7` خرج دارد: چند page ایندکس و یک page جدول.

## بازه، ترتیب و index-only scan

چون کلیدها مرتب‌اند، بازه و ترتیب رایگان می‌آیند:

```text
SELECT * FROM orders ORDER BY id DESC LIMIT 5;
 Limit -> Index Scan Backward using orders_pkey ... Buffers: shared hit=8
```

هشت page برای پنج سفارش آخر. همین query روی `created_at` که ایندکس ندارد، یک `Sort` روی `Seq Scan` کامل (۳۳۵۷ page) می‌خواهد. اگر فقط ستون‌های ایندکس‌شده را بخواهید، به جدول هم نیازی نیست:

```text
SELECT customer_id FROM orders WHERE customer_id BETWEEN 100 AND 110;
 Index Only Scan using orders_customer_id_idx ... Heap Fetches: 0  Buffers: shared hit=3
```

`Heap Fetches: 0` یعنی به هیچ page جدولی دست نزد؛ این به خاطر `VACUUM` قبلی است که pageها را all-visible علامت می‌زند. بدون آن باید جدول را هم چک کند.

اگر ستون داخل یک عبارت باشد ایندکس استفاده نمی‌شود: `WHERE customer_id + 0 = 123` دوباره `Seq Scan` با ۳۳۵۷ page شد. همچنین `status = 'paid'` حدود ۲۰٪ جدول را برمی‌گرداند و planner اسکن ترتیبی انتخاب کرد.

## ایندکس چه هزینه‌ای دارد

دو کپی از `orders` با ۲۰۰ هزار ردیف ساختم، یکی با ایندکس اضافه روی `customer_id`، و همان ۲۰ هزار ردیف را در هر دو insert کردم و WAL را اندازه گرفتم:

```text
 بدون ایندکس   3278888 بایت WAL  (3202 kB)
 با ایندکس     6356256 بایت WAL  (6207 kB)
```

تقریباً دو برابر {{< term "wal" "WAL" >}} برای همان ردیف‌ها، چون هر insert یک ورودی ایندکس هم می‌نویسد. اندازه‌ی ایندکس‌ها را هم مقایسه کردم: primary key از ۴۴۰۸ به ۴۸۴۰ کیلوبایت رسید، ولی ایندکس `customer_id` روی ۱۸۵۶ کیلوبایت ماند. بعداً دلیلش را آزمودم: pageهای B-tree به‌طور پیش‌فرض ۹۰٪ پر ساخته می‌شوند (`fillfactor`) و همین insertها ایندکسی با `fillfactor = 100` را از ۳۹۸۴ به ۷۹۳۶ کیلوبایت رساندند؛ پس جای خالی آن‌ها را جذب کرد. ایندکس کوچک است چون deduplication در B-tree کلید تکراری را یک بار نگه می‌دارد (بدون آن ۴۴۱۶ کیلوبایت).

## ایندکس unique و ایندکس بی‌استفاده

یک constraint از نوع `UNIQUE` یک B-tree است که تکراری را هم رد می‌کند:

```text
ERROR:  duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(user1@example.com) already exists.
```

برای پیدا کردن ایندکس‌هایی که هزینه‌شان را می‌دهید ولی استفاده نمی‌شوند، `pg_stat_user_indexes` را ببینید: `idx_scan` تعداد استفاده را می‌شمارد. در اجرای من `customers_email_key` مقدار `idx_scan = 0` و ۱۳۷۶ کیلوبایت حجم داشت. قبل از حذف، مدت طولانی مشاهده کنید.

## چند نکته‌ی مهم

- `EXPLAIN ANALYZE` را روی داده‌ی واقع‌گرایانه بزنید: روی ۱۰۰۰ ردیف planner همیشه `Seq Scan` می‌خواهد و چیزی یاد نمی‌گیرید.
- `EXPLAIN ANALYZE` خود query را اجرا می‌کند. `INSERT`، `UPDATE` و `DELETE` را داخل تراکنشی بزنید که rollback می‌شود.
- فاصله‌ی زیاد `actual rows` و `rows` یعنی آمار قدیمی است (`ANALYZE`).
- هر ایندکس کار نوشتن و فضای دیسک اضافه می‌کند. چیزی را ایندکس کنید که روی آن filter، join و sort می‌کنید، نه همه‌ی ستون‌ها.
- در PostgreSQL، foreign key روی ستون ارجاع‌دهنده ایندکس نمی‌سازد؛ `orders.customer_id` تا وقتی اضافه‌اش نکردم ایندکس نداشت.

## تمرین

1. seed فروشگاه را بارگذاری کنید و `EXPLAIN (ANALYZE, BUFFERS)` را برای `WHERE customer_id = 123` بزنید.
2. ایندکس را بسازید و `Buffers` را مقایسه کنید.
3. روی `order_items` یک query پیدا کنید که کل جدول را اسکن می‌کند و درستش کنید.
4. آزمایش WAL را با دو ایندکس تکرار کنید.

## قدم بعدی

پست بعدی: «ایندکس ترکیبی، جزئی و پوششی».
