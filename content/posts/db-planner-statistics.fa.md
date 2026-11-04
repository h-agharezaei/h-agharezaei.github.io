+++
date = '2026-12-09T10:00:00+03:30'
draft = false
title = 'planner و آمار: چرا ایندکس استفاده نمی‌شود'
description = 'آمار planner در PostgreSQL با اجرای واقعی EXPLAIN: چرا ایندکس کنار گذاشته می‌شود؛ آمار کهنه، cast، تابع، LIKE، OR و آمار گسترده.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "planner", "statistics", "explain"]
cover = { image = "/images/covers/db-planner-statistics.fa.png", alt = "planner و آمار: چرا ایندکس استفاده نمی‌شود", hiddenInSingle = true }
+++

ایندکس ساختید، query را اجرا کردید و `EXPLAIN` یک `Seq Scan` نشان می‌دهد. ایندکس همان‌جاست و PostgreSQL از کنارش رد می‌شود. باگ است؟ بیشتر وقت‌ها نه: {{< term "query-planner" "planner" >}}، بخشی از PostgreSQL که انتخاب می‌کند query چطور اجرا شود، درست می‌گوید و ایندکس کندتر بود. اما گاهی planner انتخاب بدی می‌کند چون با عددهای غلط کار می‌کند. مهارت اصلی تشخیص این دو حالت از هم است.

در [پست قبل](/fa/posts/db-composite-partial-covering-indexes/) ایندکس طراحی کردیم. این پست نیمه‌ی دیگر ماجراست: planner چطور تصمیم می‌گیرد از آن‌ها استفاده کند یا نه، و وقتی بد تصمیم می‌گیرد چه چیزی را باید چک کرد.

> همه‌چیز روی PostgreSQL 18.3 واقعی و با schema فروشگاهی مشترک (۲۰۰ هزار سفارش، ۶۰۰ هزار آیتم) اجرا شد. پلن‌ها به خط‌های مهم کوتاه شده‌اند و به‌جای میلی‌ثانیه تعداد buffer را نشان می‌دهم. برآوردهای `rows=` از یک نمونه‌ی تصادفی می‌آیند، پس بین اجراها کمی فرق می‌کنند (برای همین query در این اجرا ۱۳۹۵۶۷ دیدم و در یک اجرای قبلی ۱۴۰۴۰۷).

## planner چطور تصمیم می‌گیرد

planner برای فهمیدن اینکه query چقدر طول می‌کشد آن را اجرا نمی‌کند. برآورد می‌کند. برای هر پلن ممکن حدس می‌زند هر گام چند ردیف برمی‌گرداند، آن را با یک فرمول ساده به **هزینه** (cost) تبدیل می‌کند و پلنی را که کمترین هزینه را دارد برمی‌گزیند. عددهایی که از آن‌ها کار می‌کند {{< term "planner-statistics" "آمار" >}} جدول است: تعداد ردیف‌ها، تعداد مقدارهای متمایز هر ستون، و اینکه کدام مقدارها رایج‌ترین‌اند. دستور `ANALYZE` آن‌ها را جمع می‌کند و در view به اسم `pg_stats` می‌گذارد.

فرمول را حتی می‌توانید وارسی کنید. برای اسکن ترتیبی ساده‌ی `orders` پلن `cost=0.00..5857.00` گفت. جدول ۳۳۵۷ page و ۲۰۰٬۰۰۰ ردیف دارد و هزینه‌های پیش‌فرض PostgreSQL این‌هاست: ۱٫۰ برای هر page که ترتیبی خوانده شود (`seq_page_cost`)، ۰٫۰۱ برای هر ردیفی که پردازش شود (`cpu_tuple_cost`) و ۰٫۰۰۲۵ برای هر شرطی که روی یک ردیف چک شود (`cpu_operator_cost`):

```text
3357 pages x 1.0  +  200000 rows x 0.01  +  200000 rows x 0.0025  =  3357 + 2000 + 500  =  5857
```

دقیقاً همان عددی است که در پلن آمده. (این محاسبه را از مقدارهای پیش‌فرض انجام دادم که با `SHOW` تأییدشان کردم، و پلن با آن می‌خواند.) planner رازآلود نیست؛ فقط برآوردها را جمع می‌زند. و این ما را به مفیدترین عادت این پست می‌رساند: **در هر پلن، `rows=` برآوردی را با `actual rows=` مقایسه کنید.** اگر نزدیک بودند، planner داده‌ی شما را فهمیده و انتخابش احتمالاً منطقی است. اگر از هم دور بودند، پلن احتمالاً روی یک حدس غلط ساخته شده.

## selectivity پایین: Seq Scan درست است

سه ایندکس روی `orders` ساختم (`status`، `customer_id`، `created_at`) و `ANALYZE` زدم. ستون `status` فقط چهار مقدار دارد و یکی‌شان غالب است:

```text
SELECT status, count(*) FROM orders GROUP BY 1 ORDER BY 2 DESC;
  status   | count  
-----------+--------
 shipped   | 140000
 paid      |  40000
 new       |  16000
 cancelled |   4000
```

حالا دو query روی همین ستون ایندکس‌شده:

```text
SELECT * FROM orders WHERE status = 'shipped';
 Seq Scan on orders  (cost=0.00..5857.00 rows=139567 width=39) (actual rows=140000.00 loops=1)
   Filter: (status = 'shipped'::text)
   Rows Removed by Filter: 60000
   Buffers: shared hit=3357

SELECT * FROM orders WHERE status = 'cancelled';
 Bitmap Heap Scan on orders  (cost=46.57..3619.31 rows=3907 width=39) (actual rows=4000.00 loops=1)
   Recheck Cond: (status = 'cancelled'::text)
   Heap Blocks: exact=1529
   Buffers: shared hit=1534
   ->  Bitmap Index Scan on orders_status_idx  (cost=0.00..45.60 rows=3907 width=0) (actual rows=4000.00 loops=1)
         Index Cond: (status = 'cancelled'::text)
```

برآوردها را ببینید: ۱۳۹۵۶۷ در برابر ۱۴۰۰۰۰ و ۳۹۰۷ در برابر ۴۰۰۰. planner داده‌اش را خوب می‌شناخت. برای `shipped` اسکن ساده را انتخاب کرد، چون query ۷۰٪ جدول را برمی‌گرداند. queryای که بیشتر ردیف‌ها را برمی‌گرداند {{< term "selectivity" "selectivity" >}} پایین دارد: شرط چیزی را محدود نمی‌کند، پس ایندکس فقط روی خواندنی که به‌هرحال تقریباً هر page را لمس می‌کند کار اضافه می‌گذارد. برای مقدار کمیاب `cancelled` (۲٪) از ایندکس استفاده می‌شود و می‌برد هم، ولی کمتر از آنچه فکر می‌کنید: ۱۵۳۴ page به‌جای ۳۳۵۷، چون سفارش‌های لغوشده تقریباً در نصف pageهای جدول پخش‌اند.

برای دیدن جایگزینی که planner رد کرد، اسکن ترتیبی را با `SET enable_seqscan = off` خاموش کردم. این **فقط ابزار تشخیص** است؛ آن پلن را ممنوع نمی‌کند، فقط فوق‌العاده گرانش می‌کند تا planner انتخاب دومش را نشانتان بدهد:

```text
 Bitmap Heap Scan on orders  (cost=1561.94..6663.53 rows=139567 ...) (actual rows=140000.00 ...)
   Heap Blocks: exact=1677
   Buffers: shared hit=1797
```

هزینه‌ی برآوردی‌اش، ۶۶۶۳٫۵۳، از هزینه‌ی Seq Scan یعنی ۵۸۵۷٫۰۰ بالاتر است، پس planner ردش کرد. توجه کنید که روی این دموی کاملاً cache‌شده buffer کمتری لمس کرد (۱۷۹۷ در برابر ۳۳۵۷) و من هیچ‌کدام از دو پلن را زمان‌گیری نکردم، پس نمی‌توانم بگویم اینجا کندتر است. مدل planner خواندن غیرترتیبی page را گران‌تر از ترتیبی حساب می‌کند (`random_page_cost` به‌طور پیش‌فرض ۴ است و `seq_page_cost` برابر ۱)، که برای دیسک سرد فرض معقولی است و ممکن است با سخت‌افزار شما نخواند. وقتی اسکن بیت‌مپ را هم خاموش کردم و یک Index Scan ساده را مجبور کردم، هزینه‌ی برآوردی باز هم بالاتر شد، ۱۳۱۸۱٫۸۸، با همان ۱۷۹۷ buffer. هرگز `enable_seqscan = off` را به production نبرید؛ در یک نشست برای مقایسه استفاده‌اش کنید و بعد reset کنید.

## جدول‌های کوچک

همین منطق این را هم توضیح می‌دهد که آدم‌ها را غافلگیر می‌کند:

```text
SELECT * FROM tiny WHERE id = 7;     -- 50 rows, primary key exists
 Seq Scan on tiny  (cost=0.00..1.62 rows=1 width=7) (actual rows=1.00 loops=1)
   Filter: (id = 7)
   Rows Removed by Filter: 49
   Buffers: shared hit=1
```

کل جدول در یک page جا می‌شود. خواندن آن یک page ارزان‌تر از گشتن در ایندکس برای پیدا کردن همان page است. باز هم planner درست می‌گوید.

## آمار گم‌شده یا کهنه

حالا حالتی که planner اشتباه می‌کند. جدولی به اسم `events` ساختم با ۱۰۰٬۰۰۰ ردیف که ۱۰۰ تای آن‌ها `kind = 'rare'` و بقیه `'common'` بودند، یک ایندکس روی `kind`، و autovacuum را برای جدول خاموش کردم (معمولاً {{< term "autovacuum" "autovacuum" >}} در پس‌زمینه `ANALYZE` را اجرا می‌کند). بعد ردیف‌ها را بارگذاری کردم و `ANALYZE` نزدم، همان‌طور که بعد از یک بارگذاری حجیم پیش می‌آید:

```text
SELECT relname, n_live_tup, last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE relname='events';
 relname | n_live_tup | last_analyze | last_autoanalyze 
---------+------------+--------------+------------------
 events  |          0 |              | 

SELECT reltuples, relpages FROM pg_class WHERE relname='events';
 reltuples | relpages 
-----------+----------
        -1 |        0
```

planner درباره‌ی این جدول هیچ نمی‌داند (`reltuples = -1` یعنی «هیچ‌وقت analyze نشده»). ببینید با دو مقدار کاملاً متفاوت چه کرد:

```text
SELECT * FROM events WHERE kind = 'common';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258 ...) (actual rows=99900.00 ...)
   Buffers: shared hit=716

SELECT * FROM events WHERE kind = 'rare';
 Bitmap Heap Scan on events  (cost=6.29..494.79 rows=258 ...) (actual rows=100.00 ...)
   Buffers: shared hit=102
```

برآورد برای هر دو ۲۵۸ است، چه جواب واقعی ۹۹٬۹۰۰ باشد چه ۱۰۰. این یک حدس پیش‌فرض است، نه دانش. بعد از `ANALYZE events`:

```text
SELECT * FROM events WHERE kind = 'common';
 Seq Scan on events  (cost=0.00..1887.00 rows=99923 ...) (actual rows=99900.00 ...)
   Buffers: shared hit=637

SELECT * FROM events WHERE kind = 'rare';
 Index Scan using events_kind_idx on events  (cost=0.29..10.52 rows=77 ...) (actual rows=100.00 ...)
   Buffers: shared hit=102
```

برآوردها حالا نزدیک‌اند (۹۹٬۹۲۳ در برابر ۹۹٬۹۰۰ و ۷۷ در برابر ۱۰۰) و هر مقدار پلنی را می‌گیرد که سزاوارش است: اسکن ترتیبی برای مقدار ۹۹٫۹٪ (۶۳۷ page به‌جای ۷۱۶) و اسکن ایندکس برای مقدار کمیاب. autovacuum معمولاً خودش analyze می‌کند، ولی بعد از بارگذاری بزرگ یا تغییر بزرگ داده، `ANALYZE` را خودتان بزنید.

## خواندن pg_stats

`ANALYZE` دقیقاً چه چیزی ذخیره می‌کند؟ در `pg_stats` می‌توانید بخوانید. برای `orders` (psql در حالت expanded):

```text
attname           | status
n_distinct        | 4
most_common_vals  | {shipped,paid,new,cancelled}
most_common_freqs | {0.69783336,0.2002,0.082433335,0.019533332}
correlation       | 0.5347375

attname           | customer_id
n_distinct        | -0.10015
most_common_vals  | {1003,1300,11968}
most_common_freqs | {0.00023333334,0.00023333334,0.00023333334}
correlation       | -0.004848448
```

خواندنش:

- `n_distinct` تعداد مقدارهای متفاوت است. عدد مثبت یک تعداد است (`status` ۴ تا دارد). عدد منفی یعنی «این کسر از ردیف‌های جدول»: `-0.10015` یعنی حدود ۱۰٪ از ۲۰۰٬۰۰۰ ردیف، تقریباً ۲۰٬۰۰۰ مشتری (تعداد واقعی دقیقاً ۲۰٬۰۰۰ است؛ مقدار ذخیره‌شده برآوردی از یک نمونه است).
- `most_common_vals` و `most_common_freqs` پرتکرارترین مقدارها و کسری از ردیف‌ها را که هر کدام دارد فهرست می‌کنند. برای `status` دقیقاً همان است که دیدیم: `shipped` حدود ۷۰٪ است. همین فهرست باعث می‌شود planner بتواند `status = 'shipped'` را این‌قدر خوب برآورد کند. برای `customer_id` چیزی برجسته نیست (هر مشتری حدود ۱۰ سفارش دارد)، پس فهرست کوتاه و تقریباً بی‌معناست.
- `histogram_bounds` (در کادر بالا نیامده) بقیه‌ی مقدارها را به سطل‌هایی با تعداد ردیف برابر تقسیم می‌کند؛ برآورد بازه‌هایی مثل `created_at >= ...` را همین می‌چرخاند.
- `correlation` می‌گوید ترتیب فیزیکی ردیف‌ها در جدول چقدر از ترتیب مقدارها پیروی می‌کند، از ۱- تا ۱. نزدیک ۱ یعنی ردیف‌های با مقدار نزدیک کنار هم ذخیره شده‌اند و اسکن ایندکس ارزان‌تر می‌شود. نزدیک ۰، مثل `customer_id`، یعنی ردیف‌های منطبق پراکنده‌اند.

`ANALYZE` چقدر جزئیات نگه می‌دارد؟ این را `default_statistics_target` تعیین می‌کند، که پیش‌فرضش ۱۰۰ است: تعداد ورودی‌های فهرست مقدارهای رایج و سطل‌های histogram به‌ازای هر ستون. طبق مستندات، تعداد ردیف‌هایی را که `ANALYZE` نمونه می‌گیرد هم همین تعیین می‌کند. اثرش را با جدولی به اسم `hot` می‌شود دید که ساختم: ۳۰۰ مقدار که هر کدام دقیقاً در ۲۰۰ ردیف هستند، به‌علاوه‌ی ۴۰٬۰۰۰ مقدار یکتای نویز. query مقدار `v = 250` را می‌خواهد که تعداد واقعی‌اش ۲۰۰ است:

```text
STATISTICS 10:    Index Only Scan using hot_v_idx  (cost=0.29..65.27 rows=39 ...)
STATISTICS 100:   Index Only Scan using hot_v_idx  (cost=0.29..14.35 rows=5 ...)
STATISTICS 1000:  Index Only Scan using hot_v_idx  (cost=0.29..261.22 rows=200 ...)
```

با ۱۰۰ جا برای همه‌ی ۳۰۰ مقدار رایج جایی نیست، پس ۲۵۰ از فهرست رایج‌ها بیرون ماند و برآورد میانگین «مقدارهای خارج از فهرست» را گرفت: ۵ ردیف. با ۱۰۰۰ جا هر ۳۰۰ مقدار جا شدند (چک کردم: فهرست ۳۰۰ ورودی داشت) و برآورد دقیق است. با ۱۰ جا حدس ۳۹ بود. نوع پلن اینجا همان ماند، ولی برآورد غلط در یک query بزرگ‌تر، مثلاً یک join، می‌تواند ترتیب یا روش join را عوض کند. target را برای یک ستون با `ALTER TABLE ... ALTER COLUMN ... SET STATISTICS` بالا ببرید، نه سراسری: جزئیات بیشتر `ANALYZE` و برنامه‌ریزی را کندتر می‌کند.

## چیزهایی که ایندکس را بی‌اثر می‌کنند

گاهی آمار درست است و planner باز هم نمی‌تواند از ایندکس استفاده کند، به‌خاطر شکل نوشتن query. این‌ها مواردی‌اند که امتحان کردم:

- **cast روی ستون.** `customer_id = 42` از ایندکس استفاده کرد (`Bitmap Heap Scan`، ۱۵ page). `customer_id = 42::numeric` یک `Parallel Seq Scan` داد با `Filter: ((customer_id)::numeric = '42'::numeric)` و ۳۳۵۷ page. مقایسه PostgreSQL را مجبور کرد ستون را cast کند، نه ثابت را، پس ایندکس روی ستون خام قابل استفاده نبود. `customer_id::text = '42'` هم همین بود. به برآورد هم دقت کنید: `rows=1000` در برابر ۱۰ ردیف واقعی. وقتی ستون پیچیده می‌شود planner نمی‌تواند از آمارش استفاده کند.
- **تابع روی ستون.** `lower(email) = '...'` یک Seq Scan بود (برآورد ۱۰۰، واقعی ۱) و ایندکس روی `lower(email)` درستش کرد. شرطی که ایندکس بتواند به آن جواب دهد {{< term "sargable" "sargable" >}} نام دارد.
- **wildcard ابتدایی.** با یک ایندکس `text_pattern_ops`، `LIKE 'Customer 4242%'` از Index Scan استفاده کرد، چون پیشوند در ترتیب مرتب یک بازه است. `LIKE '%4242'` یک Seq Scan بود، چون تطابق می‌تواند از هر جا شروع شود. (طبق مستندات PostgreSQL، در بیشتر localeهای غیر C، `LIKE` پیشوندی برای استفاده از B-tree اصلاً به این operator class ویژه نیاز دارد. در دمو از آن استفاده کردم و ایندکس ساده را امتحان نکردم.)
- **`OR`.** `customer_id = 42 OR status = 'cancelled'` با ایندکس روی هر دو ستون از `BitmapOr` استفاده کرد: یک bitmap از هر ایندکس، ادغام‌شده. با `customer_id = 42 OR total_cents = 12345` که `total_cents` ایندکس ندارد، به Parallel Seq Scan برگشت. یک شاخه‌ی بدون ایندکس در `OR` برای مجبور کردن به اسکن کامل کافی است.

## ستون‌های وابسته: آمار گسترش‌یافته

planner یک نقطه‌ی کور دیگر هم دارد. فرض می‌کند ستون‌ها مستقل‌اند: وقتی دو شرط ترکیب می‌شوند، selectivityشان را در هم ضرب می‌کند. این وقتی غلط است که یک ستون ستون دیگر را تعیین کند. جدولی به اسم `customers_geo` ساختم با `country` و یک `region` مشتق‌شده (هر مشتری `DE` در `EU` است) و `country = 'DE' AND region = 'EU'` را خواستم، که تعداد واقعی‌اش ۱۶۶۶ است:

```text
before: Seq Scan on customers_geo  (cost=0.00..428.00 rows=694 ...) (actual rows=1666.00 ...)
CREATE STATISTICS geo_dep (dependencies) ON country, region FROM customers_geo;  ANALYZE customers_geo;
after:  Seq Scan on customers_geo  (cost=0.00..428.00 rows=1666 ...) (actual rows=1666.00 ...)
```

عدد ۶۹۴ همان فرض استقلال است: ۱/۱۲ مشتری‌ها آلمانی‌اند، ۵/۱۲ در `EU` هستند و ۲۰٬۰۰۰ × ۱/۱۲ × ۵/۱۲ حدود ۶۹۴ می‌شود. ولی هر مشتری آلمانی در اروپاست، پس شرط دوم چیزی را حذف نمی‌کند. بعد از `CREATE STATISTICS ... (dependencies)` planner می‌داند `country` ستون `region` را تعیین می‌کند (view به اسم `pg_stats_ext` مقدار `{"2 => 3": 1.000000}` را نشان می‌دهد، یعنی ستون ۲ ستون ۳ را با قدرت ۱ تعیین می‌کند) و برآورد دقیق می‌شود. پلن روی جدولی به این کوچکی عوض نشد. روی یک join، کم‌برآوردی ۲٫۴ برابری مثل این می‌تواند به پلن بدتر منجر شود.

## چک‌لیست عیب‌یابی

1. `EXPLAIN (ANALYZE, BUFFERS)` را اجرا کنید و در هر node برآورد و واقعی را مقایسه کنید.
2. اگر فاصله‌ی زیاد است، جدول را `ANALYZE` کنید و `last_analyze` را در `pg_stat_user_tables` ببینید.
3. اگر هنوز بد است، `pg_stats` را بخوانید. target بالاتر برای ستون یا `CREATE STATISTICS` برای ستون‌های وابسته را در نظر بگیرید.
4. اگر برآوردها خوب‌اند و ایندکس باز هم استفاده نمی‌شود، selectivity، cast، تابع و wildcard را چک کنید.
5. فقط بعد از آن، `enable_seqscan = off` را در یک نشست امتحان کنید تا ببینید انتخاب دوم planner چقدر هزینه دارد.

## قضاوت درباره‌ی planner

- Seq Scan باگ نیست. با مقایسه‌ی برآورد و واقعی قضاوت کنید، نه با اسم node.
- پارامتر را cast کنید، هرگز ستون را.
- `SET enable_*` فقط برای تشخیص است.
- جدول‌های خیلی بزرگ و تنظیم `random_page_cost` را امتحان نکردم، پس چیز زیادی درباره‌شان نمی‌توانم بگویم.

## تمرین

۲۰۰ هزار ردیف بارگذاری کنید که ۹۹٪ یک ستون ایندکس‌شده در آن `'a'` است، بدون `ANALYZE`. پلن‌های `'a'` و یک مقدار کمیاب را قبل و بعد از `ANALYZE` مقایسه کنید.

## قدم بعدی

[تراکنش و ACID](/fa/posts/db-transactions-acid/). تا اینجا فقط خواندیم؛ سؤال بعدی این است که وقتی چند دستور باید با هم موفق یا شکست بخورند چه اتفاقی می‌افتد.
