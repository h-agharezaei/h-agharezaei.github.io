+++
date = '2026-12-05T10:00:00+03:30'
draft = false
title = 'ایندکس ترکیبی، جزئی و پوششی'
description = 'ایندکس ترکیبی، جزئی و پوششی در PostgreSQL 18: ترتیب ستون‌ها، INCLUDE و Index Only Scan، ایندکس عبارتی، با planهای واقعی EXPLAIN.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "indexes", "explain", "performance"]
cover = { image = "/images/covers/db-composite-partial-covering-indexes.fa.png", alt = "ایندکس ترکیبی، جزئی و پوششی", hiddenInSingle = true }
+++

دو ایندکس روی دقیقاً همان دو ستون داریم، فقط با ترتیب متفاوت. برای یک query یکی ۶ page می‌خواند و دیگری ۲۵ page. هیچ‌کدام «غلط» نیست: هر دو استفاده می‌شوند و جواب درست می‌دهند. ولی یکی چهار برابر کار می‌کند، و روی جدول بزرگ‌تر این فاصله بیشتر می‌شود.

در [ایندکس B-tree و EXPLAIN ANALYZE](/fa/posts/db-indexes-btree-explain/) یک ستون را ایندکس کردیم. query‌های واقعی به‌ندرت فقط به یک ستون نگاه می‌کنند: «سفارش‌های این مشتری در این هفته»، «سفارش‌های جدید ماه گذشته»، «جمع سفارش‌های یک مشتری». این پست ابزارهای این موارد است: {{< term "composite-index" "ایندکس ترکیبی" >}} (یک ایندکس روی چند ستون)، {{< term "partial-index" "ایندکس جزئی" >}} (ایندکس فقط روی بعضی ردیف‌ها)، {{< term "covering-index" "ایندکس پوششی" >}} (ایندکسی که بدون دست زدن به جدول به query جواب می‌دهد) و {{< term "expression-index" "ایندکس عبارتی" >}} (ایندکس روی یک مقدار محاسبه‌شده).

> همه‌چیز روی PostgreSQL 18.3 واقعی و با schema فروشگاهی مشترک (۲۰۰ هزار سفارش، ۲۰ هزار مشتری) اجرا شد. پلن‌ها از `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` آمده و به خط‌های مهم کوتاه شده‌اند. مثل پست قبل تعداد bufferها (pageهای ۸ کیلوبایتی لمس‌شده) را نشان می‌دهم و نه میلی‌ثانیه، چون به ماشین بستگی ندارند. تقسیم بین `hit` و `read` به این بستگی دارد که چه چیزی اتفاقاً در cache بوده، پس به مجموع نگاه کنید.

## ترتیب ستون‌ها مهم است

یک دفترچه‌ی تلفن را در نظر بگیرید که اول بر اساس نام خانوادگی و بعد بر اساس نام کوچک مرتب شده. پیدا کردن «رضایی، سارا» سریع است: به رضایی بپر، بعد به سارا. پیدا کردن همه‌ی کسانی که اسمشان سارا است ناامیدکننده است، چون سارا‌ها در کل دفترچه پخش‌اند. ایندکس ترکیبی همین دفترچه است: بر اساس ستون اول مرتب است، ردیف‌هایی که ستون اولشان یکی است بر اساس ستون دوم مرتب‌اند، و همین‌طور ادامه. ترتیب ستون‌ها تعیین می‌کند به کدام سؤال‌ها سریع جواب می‌دهد.

query ما: سفارش‌های یک مشتری در یک هفته. همان دو ستون را با دو ترتیب ساختم و همان query را با هر کدام اجرا کردم (ایندکس اول را قبل از ساختن دومی حذف کردم):

```sql
CREATE INDEX orders_cust_created ON orders (customer_id, created_at);   -- A
CREATE INDEX orders_created_cust ON orders (created_at, customer_id);   -- B
SELECT id, total_cents FROM orders
WHERE customer_id = 42 AND created_at >= '2025-02-01' AND created_at < '2025-02-08';
```

مشتری ۴۲ ده سفارش دارد و هیچ‌کدام در آن هفته نیست، پس query هیچ ردیفی برنمی‌گرداند. برای هدف ما اشکالی ندارد: مهم این است که هر نسخه برای فهمیدن این موضوع چقدر از ایندکس را خواند.

```text
A: Index Scan using orders_cust_created on orders  (cost=0.42..8.44 rows=1 ...) (actual rows=0.00 loops=1)
     Index Searches: 1
     Buffers: shared hit=3 read=3

B: Index Scan using orders_created_cust on orders  (cost=0.42..105.61 rows=1 ...) (actual rows=0.00 loops=1)
     Index Searches: 1
     Buffers: shared hit=9 read=16
```

A شش page می‌خواند و B بیست‌وپنج page (و برآورد هزینه‌ی planner، ۸٫۴۴ در برابر ۱۰۵٫۶۱، هم درباره‌ی بدتر بودن B موافق است). دلیلش در نحوه‌ی مرتب بودن هر ایندکس است. در A همه‌ی ورودی‌های مشتری ۴۲ کنار هم و به ترتیب تاریخ‌اند، پس دیتابیس مستقیم سراغ مشتری ۴۲ می‌رود و هفته را داخل همان گروه کوچک نگاه می‌کند. در B ورودی‌ها اول بر اساس تاریخ مرتب‌اند، پس همه‌ی سفارش‌های آن هفته (حدود ۳۵۰۰ تا) کنار هم‌اند و دیتابیس باید همه را مرور کند و روی هر کدام `customer_id` را چک کند.

قاعده‌ی سرانگشتی که از این درمی‌آید: **ستون‌هایی را که با برابری مقایسه می‌کنید اول بگذارید و ستونی را که با بازه (`>=`، `<`، `BETWEEN`) مقایسه می‌کنید آخر.** اگر query `ORDER BY` هم دارد، ستون مرتب‌سازی باید درست بعد از ستون‌های برابری بیاید. برای نمونه A به «۳ سفارش آخر مشتری ۴۲» هم بدون هیچ مرحله‌ی مرتب‌سازی جواب می‌دهد، چون ورودی‌های یک مشتری از قبل به ترتیب تاریخ‌اند:

```text
SELECT id, created_at FROM orders WHERE customer_id = 42 ORDER BY created_at DESC LIMIT 3;
 Limit  (cost=0.42..13.67 rows=3 ...) (actual rows=3.00 loops=1)
   Buffers: shared hit=3 read=3
   ->  Index Scan Backward using orders_cust_created on orders  (cost=0.42..44.59 rows=10 ...) (actual rows=3.00 loops=1)
         Index Cond: (customer_id = 42)
```

`Index Scan Backward` ورودی‌ها را از انتها می‌خواند تا تازه‌ترین‌ها اول بیایند و `Limit` بعد از سه‌تا می‌ایستد. باز هم ۶ page.

## پیشوند چپ، و یک غافلگیری در PostgreSQL 18

دفترچه‌ی تلفن حد را هم نشان می‌دهد. ایندکس روی `(a, b)` اول بر اساس `a` مرتب است، پس queryای که فقط روی `b` فیلتر می‌کند نمی‌تواند از این ترتیب برای جست‌وجو استفاده کند. این قاعده‌ی **پیشوند چپ** (leftmost prefix) است: ایندکس به queryهایی کمک می‌کند که ستون اولش، یا دو ستون اولش و همین‌طور ادامه را به کار ببرند، نه ستون‌های بعدی را به‌تنهایی. روی `orders (customer_id, created_at)`، queryای برای سفارش‌های یک روز بدون شرط مشتری، یک `Seq Scan` موازی روی هر ۳۳۵۷ page انجام داد:

```text
SELECT id FROM orders WHERE created_at >= '2025-02-01' AND created_at < '2025-02-02';
 Gather  ...  (actual rows=502.00 loops=1)
   ->  Parallel Seq Scan on orders  ...
         Filter: ((created_at >= ...) AND (created_at < ...))
         Rows Removed by Filter: 66499
         Buffers: shared hit=3357
```

ولی روی `customers (country, created_at)` همین نوع query، با فقط شرط تاریخ، از ایندکس استفاده کرد. در داده فقط ۱۲ کشور هست:

```text
Bitmap Heap Scan on customers  ... (actual rows=109.00 loops=1)
   ->  Bitmap Index Scan on customers_country_created  ... (actual rows=109.00 loops=1)
         Index Cond: (created_at >= ... AND created_at < ...)
         Index Searches: 18
         Buffers: shared hit=19 read=19
```

`Index Searches: 18` یعنی ایندکس چندین بار کاوش شد، نه یک بار. تا جایی که می‌دانم این همان **skip scan** است که PostgreSQL 18 اضافه کرد: وقتی ستون اول مقدارهای متمایز کمی دارد، دیتابیس می‌تواند از یک مقدار `country` به مقدار بعدی بپرد و بازه‌ی تاریخ را داخل هر کدام جست‌وجو کند. فقط در همین وضعیت کمک می‌کند و باز هم چندین جست‌وجو است نه یکی. اطراف آن طراحی نکنید: ستونی را که همیشه فیلتر می‌کنید اول بگذارید.

## ایندکس جزئی: فقط ردیف‌هایی را ایندکس کن که می‌پرسی

فقط ۸٪ سفارش‌ها `new` هستند (۱۶٬۰۰۰ از ۲۰۰٬۰۰۰) و queryهای عملیاتی معمول دقیقاً درباره‌ی همین‌ها می‌پرسند. چرا ۹۲٪ دیگر را ایندکس کنیم؟ ایندکس جزئی به `CREATE INDEX` یک `WHERE` اضافه می‌کند و فقط ردیف‌های منطبق ذخیره می‌شوند. برای یک هدف، یک ایندکس عادی و یک جزئی ساختم و مقایسه کردم:

```sql
CREATE INDEX orders_status_created_full ON orders (status, created_at);
CREATE INDEX orders_created_new ON orders (created_at) WHERE status = 'new';
```

```text
orders_status_created_full   4448 kB
orders_created_new            312 kB
```

ایندکس جزئی ۱۴ برابر کوچک‌تر است. وقتی هر دو بودند، planner برای `status = 'new'` به‌علاوه‌ی یک هفته `created_at` ایندکس جزئی را انتخاب کرد و query ۵۰۰ ردیف برگرداند. بعد از حذف ایندکس کامل پلن همان بود، با ۴۳۶ buffer در مجموع که فقط ۳ تا page ایندکس و ۴۳۳ تا page جدول بودند. پس ایندکس جزئی این query را سریع‌تر از ایندکس کامل نکرد. آنچه می‌دهد ایندکس خیلی کوچک‌تر است، یعنی دیسک کمتر، cache کمتر و کار کمتر در هر نوشتن روی جدول.

حد آن این است که ایندکس جزئی فقط وقتی به کار می‌آید که `WHERE` در query شرط `WHERE` ایندکس را نتیجه بدهد. برای `status = 'paid'`، یا وقتی اصلاً شرط status نیست، نمی‌شود از آن استفاده کرد و هر دو query به‌شکل `Seq Scan` روی ۳۳۵۷ page اجرا شدند.

## ایندکس پوششی و غافلگیری Index Only Scan

دفعه‌ی قبل دیدیم که {{< term "index-only-scan" "Index Only Scan" >}} وقتی query فقط ستون‌های ایندکس‌شده را بخواهد، فقط از روی ایندکس جواب می‌دهد. **ایندکس پوششی** ایندکسی است که برای همین طراحی شده. فرض کنید query به `total_cents` هم نیاز دارد. می‌توانید آن را به‌عنوان ستون کلید سوم اضافه کنید، ولی آن‌وقت ایندکس بر اساس آن هم مرتب می‌شود که لازم ندارید. `INCLUDE` ستون را فقط به‌عنوان بار اضافه می‌کند: در page‌های برگ ذخیره می‌شود و مرتب نیست. اول query را با ایندکس دوستونه‌ی ساده اجرا کردم و بعد با `INCLUDE`:

```sql
CREATE INDEX orders_cust_created_inc ON orders (customer_id, created_at) INCLUDE (total_cents);
SELECT created_at, total_cents FROM orders WHERE customer_id BETWEEN 100 AND 199;
```

```text
without INCLUDE: Bitmap Heap Scan   Heap Blocks: exact=753   Buffers: shared hit=758 read=5   (763 pages)
with INCLUDE:    Index Only Scan    Heap Fetches: 0           Buffers: shared hit=3 read=6     (9 pages)
```

هر دو ۱۰۰۰ ردیف ۱۰۰ مشتری را برمی‌گردانند. بدون `INCLUDE` دیتابیس برای مقدارهای `total_cents` باید ۷۵۳ page جدول را می‌دید؛ با آن، ۹ page ایندکس کافی بود. هزینه‌اش اندازه‌ی ایندکس است: ایندکس پوششی ۷۹۴۴ کیلوبایت است.

حالا تله‌ی کلاسیک. Index Only Scan فقط برای pageهایی می‌تواند جدول را رد کند که {{< term "visibility-map" "visibility map" >}} آن‌ها را all-visible علامت زده باشد. هر ردیف در PostgreSQL اطلاعات visibility دارد که در جدول است نه در ایندکس، پس برای pageهایی که علامت نخورده‌اند دیتابیس برای اطمینان باید به جدول برود. ۲۰٪ سفارش‌ها (۴۰٬۰۰۰ ردیف) را آپدیت کردم و vacuum نزدم:

```text
Index Only Scan using orders_cust_created_inc ...   Heap Fetches: 1200   Buffers: shared hit=1213
```

آپدیت‌ها بیت‌های all-visible را پاک کردند، پس همان پلن حالا ۱۲۰۰ بار به جدول سر زد و به‌جای ۹ page، ۱۲۱۳ page لمس کرد. بعد از `VACUUM orders` (به {{< term "vacuum" "VACUUM" >}} نگاه کنید) دوباره `Heap Fetches: 0` و ۱۴ page شد (دقیقاً ۹ نشد، چون آپدیت هم جدول را عوض کرد و هم ایندکس را). پس Index Only Scan روی جدولی که زیاد آپدیت می‌شود به این وابسته است که vacuum عقب نماند. و اگر query ستونی را بخواهد که در ایندکس نیست، مثل `status`، پلن دوباره به Bitmap Heap Scan برمی‌گردد (در اجرای من ۸۰۱ buffer).

## ایندکس عبارتی و شرط‌های non-sargable

شرط‌های {{< term "sargable" "sargable" >}} پست قبل یادتان هست: شرطی که planner می‌تواند آن را به جست‌وجوی ایندکس تبدیل کند. پیچیدن ستون در یک تابع این را خراب می‌کند. ستون ایمیل ایندکس یکتا دارد، ولی مقایسه کنید:

```text
WHERE email = 'user777@example.com'          -> Index Scan (unique index), 3 pages
WHERE lower(email) = 'user777@example.com'   -> Seq Scan, Rows Removed by Filter: 19999, 207 pages
```

ایندکس بر اساس `email` مرتب است، نه `lower(email)`، پس نمی‌تواند کمک کند. اگر واقعاً جست‌وجوی بی‌توجه به حروف بزرگ و کوچک لازم دارید، ایندکسی روی خود عبارت به دیتابیس بدهید:

```sql
CREATE INDEX customers_email_lower ON customers (lower(email));
```

همان query بعد از آن از آن استفاده کرد (`Index Scan using customers_email_lower`، ۳ page). query باید دقیقاً همان عبارت ایندکس را به کار ببرد؛ `lower(email)` منطبق می‌شود و `upper(email)` نه.

## دو ایندکس تک‌ستونه یا یک ترکیبی؟

اگر ایندکس‌های جدا روی `status` و `customer_id` داشته باشید، PostgreSQL باز هم می‌تواند آن‌ها را ترکیب کند. از هر ایندکس یک bitmap می‌سازد و ردیف‌هایی را نگه می‌دارد که در هر دو هستند، یک {{< term "bitmap-scan" "BitmapAnd" >}}:

```text
SELECT id FROM orders WHERE customer_id BETWEEN 1 AND 1500 AND status = 'new';

Bitmap Heap Scan on orders  (actual rows=1200.00 loops=1)   Heap Blocks: exact=878
  ->  BitmapAnd
        ->  Bitmap Index Scan on orders_status_idx   (actual rows=16000.00 loops=1)
        ->  Bitmap Index Scan on orders_cust_idx     (actual rows=15000.00 loops=1)
```

هر ایندکس هزاران ردیف برمی‌گرداند (۱۶٬۰۰۰ و ۱۵٬۰۰۰) ولی فقط ۱۲۰۰ تا در هر دو هستند. دو اسکن ایندکس در مجموع ۳۷ page ایندکس لمس کردند. یک ایندکس ترکیبی `(customer_id, status)` همان ۱۲۰۰ ردیف را با ۲۳ page ایندکس و همان ۸۷۸ page جدول برگرداند، یک بهبود کوچک.

ولی این query برای `status` برابری و برای `customer_id` بازه دارد، پس طبق قاعده‌ی خودمان ترتیب باید `(status, customer_id)` باشد. آن را روی یک نسخه‌ی scratch از دمو امتحان کردم (این نوع در فایل‌های دمو نیست): همان ردیف‌ها، همان ۸۷۸ page جدول، و فقط ۷ page ایندکس (۳ hit و ۴ read)، در برابر ۲۳. قاعده کار کرد.

## هر ایندکس بهایی دارد

اندازه‌های پایانی از `pg_stat_user_indexes` در پایان دمو: `orders_pkey` ‏۸۷۹۲ کیلوبایت، `orders_cust_status` ‏۲۰۱۶، `orders_cust_idx` ‏۱۸۵۶ و `orders_status_idx` ‏۱۳۶۸ کیلوبایت، کنار جدولی ۲۶ مگابایتی. روی هر کدام با هر insert و update نوشته می‌شود. و یکی از آن‌ها حالا زائد است: `orders_cust_idx` را `(customer_id, status)` پوشش می‌دهد که به queryهای `customer_id` هم جواب می‌دهد، پس می‌توانید حذفش کنید.

## قاعده‌ها و دام‌های ایندکس چندستونه

- ستون‌های برابری اول، ستون بازه آخر. ستون `ORDER BY` را درست بعد از ستون‌های برابری بگذارید.
- ایندکس جزئی خیلی کوچک است، ولی فقط queryهایی می‌توانند از آن استفاده کنند که `WHERE`شان شرط آن را نتیجه بدهد.
- ستون‌های `INCLUDE` فقط بارند. بعد از آپدیت‌های سنگین `Heap Fetches` را در `EXPLAIN` چک کنید و مطمئن شوید vacuum عقب نمانده.
- ستون ایندکس‌شده را در تابع نپیچید. ایندکس عبارتی بسازید یا شرط را بازنویسی کنید.
- چک‌لیست خودم: queryهای واقعی را فهرست کن، برای پرتکرارترین یک ایندکس ترکیبی بساز، برای ستون‌های نامتوازن ایندکس جزئی را در نظر بگیر و ایندکس‌هایی را که کسی استفاده نمی‌کند حذف کن.

## تمرین

کندترین query‌تان را که دو فیلتر دارد بردارید. هر دو ترتیب ستون را بسازید، `Buffers` را مقایسه کنید، بازنده را حذف کنید، و بعد در `pg_stat_user_indexes` دنبال ایندکس‌هایی با `idx_scan` صفر بگردید.

## قدم بعدی

[planner و آمار: چرا ایندکس استفاده نمی‌شود](/fa/posts/db-planner-statistics/). گاهی ایندکس درست وجود دارد و PostgreSQL باز هم نادیده‌اش می‌گیرد، پس پست بعدی می‌بیند planner چطور تصمیم می‌گیرد.
