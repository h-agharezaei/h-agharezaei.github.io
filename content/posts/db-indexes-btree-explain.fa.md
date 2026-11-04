+++
date = '2026-11-29T10:00:00+03:30'
draft = false
title = 'ایندکس B-tree و EXPLAIN ANALYZE'
description = 'ایندکس B-tree در PostgreSQL با پلن‌های واقعی EXPLAIN ANALYZE: تفاوت sequential scan و ایندکس، ارتفاع درخت، index-only scan و هزینه ایندکس روی نوشتن.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "index", "btree", "explain", "performance"]
cover = { image = "/images/covers/db-indexes-btree-explain.fa.png", alt = "ایندکس B-tree و EXPLAIN ANALYZE", hiddenInSingle = true }
+++

صفحه‌ی «سفارش‌های من» را در نظر بگیرید. مشتری وارد می‌شود و صفحه باید ۱۰ سفارش او را از میان ۲۰۰ هزار سفارش بیاورد. query درست است، دقیقاً ۱۰ ردیف برمی‌گرداند، و PostgreSQL برای پیدا کردنشان کل جدول ۲۶ مگابایتی را می‌خواند. اشکالی در SQL نیست. دیتابیس فقط راه سریع‌تری برای پیدا کردن آن ردیف‌ها ندارد، پس همه را وارسی می‌کند.

راه حل معمول یک {{< term "database-index" "ایندکس" >}} است. بهترین تشبیه، فهرست آخر یک کتاب است. اگر همه‌ی صفحه‌هایی را می‌خواهید که از «تراکنش» حرف می‌زنند، کتاب را از صفحه‌ی اول نمی‌خوانید. فهرست را باز می‌کنید که الفبایی مرتب است، در چند ثانیه کلمه را پیدا می‌کنید و به صفحه‌هایی که نوشته می‌روید. ایندکس دیتابیس همین است: یک ساختار جدا و مرتب که مقدار یک ستون را به جایی که ردیف‌ها هستند وصل می‌کند، تا دیتابیس بقیه را رد کند. اینکه چه هزینه‌ای دارد و کجا کمک نمی‌کند نیمه‌ی دوم این پست است. و برای اینکه ببینیم یک ایندکس واقعاً کار می‌کند یا نه، باید یک {{< term "query-plan" "query plan" >}} (پلن اجرا) را بخوانیم، یعنی توصیف خود PostgreSQL از اینکه query را چطور اجرا می‌کند.

> همه‌چیز روی PostgreSQL 18.3 واقعی و با seed قطعی همین سری اجرا شد: ۲۰ هزار مشتری، ۱ هزار محصول، ۲۰۰ هزار سفارش و ۶۰۰ هزار آیتم سفارش در schema فروشگاهی [طراحی schema و نرمال‌سازی](/fa/posts/db-schema-design-normalization/). پیش از این پست فقط primary keyها و `customers.email` ایندکس داشتند. از `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` استفاده می‌کنم و به‌جای میلی‌ثانیه تعداد bufferها را نشان می‌دهم. PostgreSQL جدول و ایندکس را در pageهای ۸ کیلوبایتی نگه می‌دارد و هر «buffer» یک page است که query لمسش کرده. تعداد page روی هر ماشینی یکی است، برای همین آن را مقایسه می‌کنم و نه زمان را.

## خواندن یک پلن بدون ایندکس

`EXPLAIN` پلنی را که PostgreSQL انتخاب کرده نشان می‌دهد. `EXPLAIN ANALYZE` query را اجرا هم می‌کند و آنچه واقعاً اتفاق افتاد را اضافه می‌کند، و `BUFFERS` pageهای لمس‌شده را. (چون `ANALYZE` query را اجرا می‌کند، با دستورهایی که داده را عوض می‌کنند مراقب باشید.) اولین query: همه‌ی سفارش‌های مشتری ۱۲۳. `max_parallel_workers_per_gather = 0` گذاشتم تا پلن یک خط ساده بماند؛ با اسکن موازی روشن، PostgreSQL دو worker راه می‌اندازد که همان ۳۳۵۷ page را بین خودشان تقسیم می‌کنند.

```text
EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF) SELECT * FROM orders WHERE customer_id = 123;

 Seq Scan on orders  (cost=0.00..5857.00 rows=10 width=39) (actual rows=10.00 loops=1)
   Filter: (customer_id = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
 Planning:
   Buffers: shared hit=36
```

خط‌به‌خط:

- `Seq Scan on orders`: **node**، یعنی یک گام از پلن. اسکن ترتیبی جدول را از اولین page تا آخرین می‌خواند.
- `cost=0.00..5857.00`: برآورد planner با واحدی قراردادی، به‌شکل «هزینه‌ی تولید اولین ردیف .. هزینه‌ی تولید همه‌ی ردیف‌ها». این واحد به‌تنهایی معنایی ندارد؛ planner برای مقایسه‌ی پلن‌های جایگزین از آن استفاده می‌کند.
- `rows=10` برآورد تعداد ردیف‌های خروجی است و `width=39` میانگین اندازه‌ی ردیف به بایت.
- `actual rows=10.00 loops=1`: آنچه واقعاً شد. ۱۰ ردیف بیرون آمد و این node یک بار اجرا شد. وقتی برآورد و عدد واقعی نزدیک‌اند، planner داده را درست فهمیده.
- `Filter` و `Rows Removed by Filter: 199990`: همه‌ی ردیف‌ها خوانده و وارسی شدند و ۱۹۹٬۹۹۰ تا از ۲۰۰٬۰۰۰ تا دور ریخته شد. این اتلاف است.
- `Buffers: shared hit=3357`: ۳۳۵۷ page خوانده شد و همه در cache خود PostgreSQL بود (`hit`). جدول دقیقاً ۳۳۵۷ page دارد (۲۶ مگابایت، با `pg_relation_size` چک کردم)، پس برای برگرداندن ۱۰ ردیف کل جدول خوانده شد.
- `Planning: Buffers`: pageهایی که موقع برنامه‌ریزی لمس شد (بیشتر کاتالوگ‌های سیستم). فعلاً نادیده‌اش بگیرید.

## اضافه کردن ایندکس

```sql
CREATE INDEX orders_customer_id_idx ON orders (customer_id);
```

ایندکس جدید ۱۸۵۶ کیلوبایت است، یعنی ۲۳۲ page، در برابر ۳۳۵۷ page جدول. حالا همان query:

```text
 Bitmap Heap Scan on orders  (cost=4.37..42.86 rows=10 width=39) (actual rows=10.00 loops=1)
   Recheck Cond: (customer_id = 123)
   Heap Blocks: exact=10
   Buffers: shared hit=13 read=2
   ->  Bitmap Index Scan on orders_customer_id_idx  (cost=0.00..4.37 rows=10 width=0) (actual rows=10.00 loops=1)
         Index Cond: (customer_id = 123)
         Index Searches: 1
         Buffers: shared hit=3 read=2
 Planning:
   Buffers: shared hit=22
```

پلن یک درخت است و خط `->` تو‌رفته یک node فرزند است که به والدش می‌دهد. از داخل به بیرون بخوانیدش:

1. `Bitmap Index Scan` ایندکس را برای `customer_id = 123` جست‌وجو می‌کند (`Index Searches: 1`) و جای ۱۰ ردیف منطبق را در یک bitmap جمع می‌کند، یعنی فهرستی از «کدام pageهای جدول، کدام ردیف‌ها».
2. `Bitmap Heap Scan` آن فهرست را می‌گیرد و pageهای جدول را می‌بیند («heap» اسم PostgreSQL برای خود محل ذخیره‌ی جدول است). `Heap Blocks: exact=10` می‌گوید ۱۰ ردیف در ۱۰ page مختلف بودند، پس ۱۰ page خوانده شد، هر کدام یک بار و به ترتیب page. `Recheck Cond` فقط یعنی شرط روی ردیف‌های واکشی‌شده دوباره بررسی می‌شود.

جمع: ۱۳ page از cache آمد و ۲ تا باید واکشی می‌شد (`read`: در cache خود PostgreSQL نبود، پس از سیستم‌عامل یا دیسک؛ ایندکس تازه ساخته شده بود). حدود ۱۵ page به‌جای ۳۳۵۷، و برآورد هزینه از ۵۸۵۷٫۰۰ به ۴۲٫۸۶ رسید.

planner node بیت‌مپ را انتخاب کرد چون آن را ارزان‌تر برآورد کرد. جایگزینش **Index Scan** ساده است که هر ردیف را همین‌که در ایندکس پیدا شد واکشی می‌کند. با `SET enable_bitmapscan = off` (کلیدی فقط برای آزمایش، نه برای production) مجبورش کردم. ۱۵ page لمس کرد و هزینه‌ی برآوردی‌اش ۴۴٫۴۷ بود، کمی بالاتر از ۴۲٫۸۶ پلن بیت‌مپ:

```text
 Index Scan using orders_customer_id_idx on orders  (cost=0.29..44.47 rows=10 width=39) (actual rows=10.00 loops=1)
   Index Cond: (customer_id = 123)
   Index Searches: 1
   Buffers: shared hit=15
```

## B-tree چیست

نوع پیش‌فرض ایندکس، و همان که الان ساختیم، {{< term "b-tree" "B-tree" >}} است. یک فهرست‌برگه‌ی کوچک کتاب‌خانه را تصور کنید: برگه‌ی بالا می‌گوید «A تا F در کشوی ۱، G تا M در کشوی ۲، ...»، هر کشو برگه‌هایی دارد که با اسم مرتب‌اند و هر برگه به یک قفسه اشاره می‌کند. B-tree همین ایده است که از pageهای ۸ کیلوبایتی ساخته شده: page **ریشه** (root) در بالا بازه‌ها را فهرست می‌کند و به pageهای زیرش اشاره می‌کند، و pageهای پایین، **برگ‌ها** (leaf)، کلیدهای مرتب را همراه اشاره‌گر به ردیف‌های جدول نگه می‌دارند. برای پیدا کردن یک کلید، ریشه را می‌خوانید، یک اشاره‌گر را دنبال می‌کنید و به یک برگ می‌رسید. این یک {{< term "binary-search" "جست‌وجوی دودویی" >}} است که در آن هر قدم نه نصف، بلکه تقریباً همه‌ی داده‌ی باقی‌مانده را کنار می‌گذارد، چون هر page صدها فرزند دارد.

عددهای واقعی را با افزونه‌ی `pageinspect` نشان می‌دهم. این query جزو فایل‌های دمو نیست؛ جدا روی همان داده اجرایش کردم:

```text
SELECT root, level FROM bt_metap('orders_customer_id_idx') \gset
SELECT :root AS root, :level AS level, type, live_items FROM bt_page_stats('orders_customer_id_idx', :root);
 root | level | type | live_items 
------+-------+------+------------
    3 |     1 | r    |        230
```

page ریشه (page شماره‌ی ۳) ۲۳۰ ورودی دارد، یکی برای هر page برگ: کل ایندکس ۲۳۲ page است، یعنی ۱ page فراداده، ۱ ریشه و ۲۳۰ برگ. (`level 1` یعنی یک سطح بالای برگ‌ها.) جست‌وجو ریشه را می‌خواند، یکی از ۲۳۰ فرزند را انتخاب می‌کند و فقط آن یک برگ را می‌خواند، و برگ ۱۰ ردیف منطبق را فهرست می‌کند. ایندکس primary key بزرگ‌تر است: ۱۰۹۹ page و `level 2`، یعنی ریشه، یک سطح میانی و برگ‌ها. برای همین `WHERE id = 123` فقط چند page خرج دارد:

```text
 Index Scan using orders_pkey on orders  (cost=0.42..8.44 rows=1 width=39) (actual rows=1.00 loops=1)
   Index Cond: (id = 123)
   Index Searches: 1
   Buffers: shared hit=7
```

هفت page لمس شد، در برابر ۳۳۵۷ برای اسکن ترتیبی. دقیقاً تفکیک نکرده‌ام که این هفت page کدام‌اند؛ مسیر از page ورودی ایندکس تا برگ را به‌علاوه‌ی page جدول که ردیف در آن است پوشش می‌دهند.

## بازه، ترتیب و index-only scan

چون کلیدهای B-tree مرتب نگه داشته می‌شوند، فقط جست‌وجوی برابری نیست که به دست می‌آید. بازه و ترتیب تقریباً مجانی‌اند. «۵ سفارش آخر بر اساس id» ایندکس primary key را از انتها به عقب می‌پیماید و بعد از ۵ ورودی می‌ایستد:

```text
SELECT * FROM orders ORDER BY id DESC LIMIT 5;
 Limit  (actual rows=5.00 loops=1)
   Buffers: shared hit=8
   ->  Index Scan Backward using orders_pkey on orders  (actual rows=5.00 loops=1)
```

(عددهای cost را حذف کرده‌ام.) این را با همان سؤال روی `created_at` مقایسه کنید که ایندکس ندارد. دیتابیس باید هر ۳۳۵۷ page را بخواند و ۲۰۰ هزار ردیف را مرتب کند تا پنج‌تای بالا را نگه دارد:

```text
 Limit  (cost=8678.93..8678.94 rows=5 width=39) (actual rows=5.00 loops=1)
   Buffers: shared hit=3357
   ->  Sort  (cost=8678.93..9178.93 rows=200000 width=39) (actual rows=5.00 loops=1)
         Sort Key: created_at DESC
         Sort Method: top-N heapsort  Memory: 25kB
         ->  Seq Scan on orders  (cost=0.00..5357.00 rows=200000 width=39) (actual rows=200000.00 loops=1)
```

یک ترفند دیگر هم هست. اگر query فقط ستون‌هایی بخواهد که در ایندکس‌اند، شاید دیتابیس اصلاً به جدول نیاز نداشته باشد:

```text
SELECT customer_id FROM orders WHERE customer_id BETWEEN 100 AND 110;
 Index Only Scan using orders_customer_id_idx on orders  (cost=0.29..6.46 rows=108 width=8) (actual rows=110.00 loops=1)
   Index Cond: ((customer_id >= 100) AND (customer_id <= 110))
   Heap Fetches: 0
   Buffers: shared hit=3
```

یک {{< term "index-only-scan" "Index Only Scan" >}} فقط از روی ایندکس جواب می‌دهد: ۱۱۰ ردیف از ۳ page. `Heap Fetches: 0` یعنی هیچ page جدولی دیده نشد. این فقط به این دلیل کار کرد که اول `VACUUM` اجرا کردم، که در {{< term "visibility-map" "visibility map" >}} ثبت می‌کند کدام pageهای جدول فقط ردیف‌هایی دارند که برای همه دیده می‌شوند. برای pageهایی که این‌طور علامت نخورده‌اند، دیتابیس برای اطمینان باید به جدول هم نگاه کند.

## وقتی ایندکس استفاده نمی‌شود

هر query نمی‌تواند از ایندکس استفاده کند. ستون را در یک عبارت بپیچید، و ایندکس روی خود ستون بی‌فایده می‌شود، چون ایندکس بر اساس `customer_id` مرتب است و نه بر اساس `customer_id + 0`:

```text
SELECT * FROM orders WHERE customer_id + 0 = 123;
 Seq Scan on orders  (cost=0.00..6357.00 rows=1000 width=39) (actual rows=10.00 loops=1)
   Filter: ((customer_id + 0) = 123)
   Rows Removed by Filter: 199990
   Buffers: shared hit=3357
```

دوباره ۳۳۵۷ page، با اینکه ایندکس وجود دارد. شرطی که طوری نوشته شود که ایندکس بتواند به آن جواب دهد {{< term "sargable" "sargable" >}} نام دارد؛ راه حل نوشتن `customer_id = 123` است. (به `rows=1000` در برابر `actual rows=10` هم دقت کنید: planner برای یک عبارت نمی‌توانست برآورد کند و حدس زد. به برآوردها در یک پست بعدی برمی‌گردیم.)

مورد دوم ستونی است که با سهم بزرگی از جدول منطبق می‌شود. در این دمو روی `status` ایندکسی نیست، پس `WHERE status = 'paid'` به هر حال `Seq Scan` است و برای برگرداندن ۴۰٬۰۰۰ ردیف (۲۰٪ جدول) ۱۶۰٬۰۰۰ ردیف را دور ریخت. برای دیدن اینکه چه چیزی عوض می‌شود، روی یک نسخه‌ی scratch از جدول یک ایندکس روی `status` اضافه کردم. planner آن‌وقت از اسکن بیت‌مپ استفاده کرد ولی باز هم ۱۷۱۲ buffer خواند، یعنی حدود نصف جدول، چون ۴۰٬۰۰۰ ردیف منطبق در ۱۶۷۷ page از ۳۳۵۷ page جدول پخش شده‌اند. ایندکس وقتی می‌ارزد که بتواند بیشتر جدول را رد کند، و برای ستونی با فقط چهار مقدار اغلب نمی‌تواند.

## ایندکس چه هزینه‌ای دارد

خواندن سریع‌تر می‌شود، ولی حالا هر insert کار بیشتری دارد، چون هر ایندکس هم باید به‌روز شود. برای اندازه‌گیری دو نسخه از `orders` ساختم، هر کدام با ۲۰۰ هزار ردیف، یکی با یک ایندکس اضافه روی `customer_id`، بعد همان ۲۰ هزار ردیف جدید را در هر دو درج کردم و اندازه گرفتم هر درج چند بایت {{< term "wal" "WAL" >}} (لاگ write-ahead که PostgreSQL برای هر تغییر می‌نویسد) تولید کرد:

```text
 wal_without_index | wal_with_index | bytes_a | bytes_b 
-------------------+----------------+---------+---------
 3217 kB           | 6207 kB        | 3294328 | 6356256
```

تقریباً دو برابر WAL برای همان ردیف‌ها، چون هر insert یک ورودی ایندکس هم می‌نویسد. (در اجرای اولیه جدول بدون ایندکس اضافه ۳۲۷۸۸۸۸ بایت نوشت و جدول با ایندکس همان ۶۳۵۶۲۵۶؛ عدد اول از اجرایی به اجرای دیگر کمی جابه‌جا می‌شود.)

اندازه‌ی ایندکس‌ها را هم قبل و بعد از آن ۲۰ هزار درج مقایسه کردم. ایندکس primary key از ۴۴۰۸ به ۴۸۴۰ کیلوبایت رسید، ولی ایندکس `customer_id` روی ۱۸۵۶ کیلوبایت ماند. چرا رشد نکرد؟ دو دلیل دارد و هر دو را روی یک نسخه‌ی scratch چک کردم:

- pageهای B-tree به‌طور پیش‌فرض فقط ۹۰٪ پر ساخته می‌شوند (`fillfactor = 90`) و برای ورودی‌های جدید جا می‌گذارند. ایندکسی که با `fillfactor = 100` ساخته شد، در همان آزمایش دو برابر شد، از ۱۷۰۴ به ۳۴۰۰ کیلوبایت.
- ایندکس از ابتدا کوچک است به‌خاطر **deduplication**: وقتی ردیف‌های زیادی کلید یکسان دارند (اینجا هر مشتری حدود ۱۰ سفارش دارد)، PostgreSQL کلید را یک بار همراه فهرستی از جای ردیف‌ها ذخیره می‌کند. با `deduplicate_items = off` همان ایندکس ۴۴۱۶ کیلوبایت بود، نه ۱۸۵۶.

## ایندکس یکتا و ایندکس بی‌استفاده

قید `UNIQUE` یک B-tree است که تکراری را هم رد می‌کند. ایمیل در `customers` یکی دارد و برای همین درج ایمیل موجود شکست می‌خورد:

```text
ERROR:  duplicate key value violates unique constraint "customers_email_key"
DETAIL:  Key (email)=(user1@example.com) already exists.
```

ایندکسی که هزینه‌اش را می‌دهید ولی هیچ‌وقت استفاده نمی‌شود هزینه‌ی محض است. PostgreSQL در `pg_stat_user_indexes` شمارنده نگه می‌دارد و `idx_scan` می‌گوید هر ایندکس چند بار استفاده شده:

```text
  relname  |      indexrelname      | idx_scan |  size   
-----------+------------------------+----------+---------
 customers | customers_email_key    |        0 | 1376 kB
 customers | customers_pkey         |   200000 | 456 kB
 orders    | orders_customer_id_idx |        5 | 1856 kB
 orders    | orders_pkey            |   800002 | 8792 kB
 orders_b  | orders_b_customer_idx  |        0 | 1856 kB
```

(یک ردیف را حذف کرده‌ام. عددها مال همین یک نشست دمو هستند.) `customers_email_key` `idx_scan = 0` دارد و ۱۳۷۶ کیلوبایت جا گرفته، ولی ایندکس یکتا کاری هم می‌کند که اسکن نیست: تکراری را رد می‌کند. پس ایندکسِ بدون اسکن باید بررسی شود، نه اینکه خودکار حذف شود. پیش از حذف هر چیزی، آن را در یک بازه‌ی طولانی روی سیستم واقعی بررسی کنید.

## اشتباه‌های رایج با EXPLAIN و ایندکس

- `EXPLAIN ANALYZE` را روی داده‌ی واقع‌گرایانه اجرا کنید. روی ۱۰۰۰ ردیف planner به‌درستی `Seq Scan` را ترجیح می‌دهد و چیزی یاد نمی‌گیرید.
- `EXPLAIN ANALYZE` خود query را اجرا می‌کند. برای `INSERT`، `UPDATE` و `DELETE` آن را در تراکنشی بپیچید که rollback می‌کنید.
- فاصله‌ی زیاد بین `rows` (برآورد) و `actual rows` معمولاً یعنی آمار کهنه یا خیلی درشت است؛ اجرای `ANALYZE` اولین کاری است که باید امتحان کرد.
- هر ایندکس کار نوشتن و فضای دیسک اضافه می‌کند. روی چیزی ایندکس بگذارید که فیلتر، join و مرتب می‌کنید، نه روی هر ستون.
- foreign key در PostgreSQL روی ستون ارجاع‌دهنده ایندکس نمی‌سازد. `orders.customer_id` تا وقتی در ابتدای این پست اضافه‌اش نکردم ایندکس نداشت، و دقیقاً برای همین اولین query همه‌چیز را اسکن کرد.

## تمرین

1. seed فروشگاه را بارگذاری کنید و `EXPLAIN (ANALYZE, BUFFERS)` را برای `WHERE customer_id = 123` اجرا کنید.
2. ایندکس را بسازید و `Buffers` را مقایسه کنید.
3. روی `order_items` queryای پیدا کنید که کل جدول را اسکن می‌کند و درستش کنید.
4. آزمایش WAL را با دو ایندکس تکرار کنید.

## قدم بعدی

[ایندکس ترکیبی، جزئی و پوششی](/fa/posts/db-composite-partial-covering-indexes/). query‌های واقعی به‌ندرت روی یک ستون فیلتر می‌کنند، پس سؤال بعدی این است که برای چند ستون چطور ایندکس طراحی کنیم.
