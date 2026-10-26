+++
date = '2026-12-09T10:00:00+03:30'
draft = false
title = 'planner و آمار: چرا ایندکس استفاده نمی‌شود'
description = 'آمار planner در PostgreSQL با اجرای واقعی EXPLAIN: چرا ایندکس کنار گذاشته می‌شود؛ آمار کهنه، cast، تابع، LIKE، OR و آمار گسترده.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "planner", "statistics", "explain"]
cover = { image = "/images/covers/db-planner-statistics.fa.png", alt = "planner و آمار: چرا ایندکس استفاده نمی‌شود", hiddenInSingle = true }
+++

ایندکس ساختید، کوئری را اجرا کردید و `EXPLAIN` یک `Seq Scan` نشان می‌دهد. معمولاً {{< term "query-planner" "planner" >}} درست می‌گوید؛ گاهی هم با عددهای غلط کار می‌کند. در [پست قبلی](/fa/posts/db-composite-partial-covering-indexes/) ایندکس طراحی کردیم؛ این پست نیمه‌ی دیگر ماجراست: planner چطور تصمیم می‌گیرد از آن‌ها استفاده کند.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی با schema مشترک `shop` (۲۰۰ هزار سفارش و ۶۰۰ هزار آیتم) اجرا شده. planها کوتاه شده‌اند، میلی‌ثانیه‌ای منتشر نشده و تخمین‌های نمونه‌گیری‌شده‌ی `rows=` ممکن است بین اجراها کمی فرق کنند.

## planner با عدد کار می‌کند

planner تخمین می‌زند هر مرحله چند ردیف برمی‌گرداند، هر plan را با یک مدل هزینه قیمت می‌زند و ارزان‌ترین را برمی‌دارد. ورودی‌اش {{< term "planner-statistics" "آمار" >}}ی است که `ANALYZE` در `pg_stats` جمع می‌کند. در هر plan تخمین `rows=` را با `actual rows=` مقایسه کنید: فاصله‌ی زیاد یعنی plan بد محتمل است.

## selectivity پایین: Seq Scan درست است

روی `orders (status)` ایندکس گذاشتم. ۷۰٪ ردیف‌ها `shipped` هستند:

```text
SELECT * FROM orders WHERE status = 'shipped';
 Seq Scan on orders  (cost=0.00..5857.00 rows=140407) (actual rows=140000.00)
   Buffers: shared hit=3357

SELECT * FROM orders WHERE status = 'cancelled';   -- 2% of rows
 Bitmap Heap Scan on orders  (cost=46.98..3623.15 rows=3960) (actual rows=4000.00)
   ->  Bitmap Index Scan on orders_status_idx
```

تخمین‌ها نزدیک‌اند. کوئری‌ای که ۷۰٪ جدول را برمی‌گرداند {{< term "selectivity" "selectivity" >}} پایین دارد: ایندکس به خواندنی که تقریباً همه‌ی صفحه‌ها را می‌خواند کار اضافه می‌دهد. برای مقدار کمیاب، ایندکس برنده است.

برای دیدن گزینه‌ی دیگر، `SET enable_seqscan = off` را **فقط برای تشخیص** بزنید:

```text
Bitmap Heap Scan ... (cost=1572.45..6684.54 rows=140407)   Buffers: shared hit=1797
```

هزینه‌ی تخمینی آن، ۶۶۸۴، از ۵۸۵۷ مربوط به Seq Scan بیشتر است و planner به همین دلیل آن را نیاورد. در این دموی کاملاً cache‌شده تعداد buffer کمتری خواند (۱۷۹۷ در برابر ۳۳۵۷) و هیچ‌کدام را زمان‌گیری نکردم، پس نمی‌توانم ادعا کنم اینجا کندتر است. مدل هزینه از `random_page_cost` هم استفاده می‌کند (پیش‌فرض ۴ در برابر ۱ برای خواندن ترتیبی). `enable_seqscan = off` را هرگز در محصول نگذارید.

## جدول‌های کوچک

```text
SELECT * FROM tiny WHERE id = 7;     -- 50 rows, primary key exists
 Seq Scan on tiny  (cost=0.00..1.62 rows=1)   Buffers: shared hit=1
```

یک صفحه: خواندنش از گشتن در ایندکس ارزان‌تر است.

## آمار نبودن یا کهنه بودن

جدول `events` را با ۱۰۰ هزار ردیف ساختم (۱۰۰ تای آن `rare`)، با ایندکس روی `kind`، autovacuum خاموش، و **بدون** `ANALYZE` پرش کردم:

```text
n_live_tup = 0, last_analyze = NULL, reltuples = -1

SELECT * FROM events WHERE kind = 'common';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258) (actual rows=99900.00)
```

تخمین ۲۵۸ و واقعیت ۹۹۹۰۰: planner چیزی نمی‌دانست و حدس زد. بعد از `ANALYZE events`:

```text
 Seq Scan on events  (cost=0.00..1887.00 rows=99927) (actual rows=99900.00)
 -- and for kind = 'rare':
 Index Scan using events_kind_idx  (cost=0.29..10.22 rows=73) (actual rows=100.00)
```

plan برای هر مقدار درست شد. معمولاً autovacuum خودش analyze می‌کند؛ بعد از بارگذاری حجیم، `ANALYZE` را خودتان بزنید.

## خواندن pg_stats

```text
status:  n_distinct = 4, most_common_vals = {shipped,paid,new,cancelled},
         most_common_freqs = {0.702,0.199,0.079,0.0198}
customer_id: n_distinct = 19893, correlation = 0.0006
```

`n_distinct` و فهرست مقدارهای پرتکرار تخمین برابری را می‌سازند، `histogram_bounds` بازه‌ها را، و `correlation` (تطابق ترتیب فیزیکی با ترتیب مقدارها) روی ارزان دیده شدن index scan اثر دارد.

`default_statistics_target` (۱۰۰) تعداد مقدارهای پرتکرار و باکت‌های histogram را تعیین می‌کند. جدول `hot` را ساختم با ۳۰۰ مقدار که هرکدام ۲۰۰ ردیف دارند، به‌علاوه‌ی مقدارهای یکتا، و `v = 250` را پرسیدم (واقعی: ۲۰۰ ردیف):

```text
STATISTICS 100:   Index Only Scan using hot_v_idx  rows=5
STATISTICS 1000:  Index Only Scan using hot_v_idx  rows=200
```

با ۱۰۰ جا، مقدار ۲۵۰ از فهرست پرتکرارها بیرون ماند و حدس میانگین گرفت. با ۱۰۰۰ تخمین دقیق است. آن را برای هر ستون بالا ببرید (`ALTER TABLE ... SET STATISTICS`) نه سراسری.

## چیزهایی که ایندکس را بی‌اثر می‌کنند

- **cast روی ستون.** `customer_id = 42` از ایندکس استفاده کرد. `customer_id = 42::numeric` یک `Parallel Seq Scan` با `Filter: ((customer_id)::numeric = '42'::numeric)` داد، چون ستون cast شد نه مقدار ثابت. `customer_id::text = '42'` هم همین‌طور.
- **تابع روی ستون.** `lower(email) = '...'` یک Seq Scan بود (تخمین ۱۰۰، واقعی ۱). ایندکس روی `lower(email)` درستش کرد. شرطی که ایندکس بتواند استفاده کند {{< term "sargable" "sargable" >}} نام دارد.
- **wildcard ابتدایی.** با ایندکس `text_pattern_ops`، `LIKE 'Customer 4242%'` از Index Scan استفاده کرد؛ `LIKE '%4242'` Seq Scan بود.
- **OR.** `customer_id = 42 OR status = 'cancelled'` با دو ایندکس از `BitmapOr` استفاده کرد. با `total_cents` که ایندکس ندارد به Parallel Seq Scan برگشت: یک شاخه‌ی بدون ایندکس کافی است.

## ستون‌های وابسته: آمار گسترده

planner فرض می‌کند ستون‌ها مستقل‌اند. جدول `customers_geo` را با `country` و ستون مشتق `region` ساختم (`DE` همیشه `EU` است). برای `country = 'DE' AND region = 'EU'` (واقعی: ۱۶۶۶):

```text
before: rows=694
CREATE STATISTICS geo_dep (dependencies) ON country, region FROM customers_geo;  ANALYZE ...
after:  rows=1666
```

عدد ۶۹۴ همان یک‌دوازدهم ضرب در پنج‌دوازدهم از ۲۰ هزار است. در جدولی به این کوچکی plan عوض نشد؛ در join تخمین بهتر می‌تواند عوضش کند.

## چک‌لیست عیب‌یابی

1. `EXPLAIN (ANALYZE, BUFFERS)`: تخمین و واقعی را در هر node مقایسه کنید.
2. فاصله‌ی زیاد: جدول را `ANALYZE` کنید؛ `last_analyze` را در `pg_stat_user_tables` ببینید.
3. هنوز غلط است: `pg_stats` را بخوانید؛ target بالاتر برای ستون یا `CREATE STATISTICS` را در نظر بگیرید.
4. تخمین خوب است ولی ایندکس نیست: selectivity، cast، تابع و wildcard را بررسی کنید.
5. فقط بعد از این، `enable_seqscan = off` را در یک session برای مقایسه بزنید.

## چند نکته‌ی مهم

- Seq Scan باگ نیست؛ با مقایسه‌ی تخمین و واقعی قضاوت کنید.
- parameter را cast کنید، نه ستون را.
- `SET enable_*` فقط برای تشخیص است.
- جدول‌های خیلی بزرگ و تنظیم `random_page_cost` را آزمایش نکرده‌ام.

## تمرین

۲۰۰ هزار ردیف بسازید که ۹۹٪ یک ستون ایندکس‌دار برابر `'a'` است، بدون `ANALYZE`. plan را برای `'a'` و یک مقدار کمیاب قبل و بعد از `ANALYZE` مقایسه کنید.

## قدم بعدی

پست بعدی سری: تراکنش و ACID.
