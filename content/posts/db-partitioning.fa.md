+++
date = '2027-01-30T10:00:00+03:30'
draft = false
title = 'partitioning جدول‌ها'
description = 'partitioning جدول در PostgreSQL با اجرای واقعی: range partition، partition pruning در EXPLAIN، قانون primary key، DETACH و ATTACH و جایی که کمکی نمی‌کند.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "partitioning", "performance"]
cover = { image = "/images/covers/db-partitioning.fa.png", alt = "partitioning جدول‌ها", hiddenInSingle = true }
+++

جدول `orders` را تصور کنید که سال‌هاست بزرگ می‌شود. هر query روی آن نسبت به پارسال کمی کندتر است و `VACUUM` هر بار بیشتر طول می‌کشد. ماهی یک بار باید کسی سفارش‌های قدیمی‌تر از دو سال را پاک کند. این یک `DELETE` غول‌آسا روی میلیون‌ها ردیف است که طول می‌کشد و تعداد زیادی ردیف مرده برای `VACUUM` باقی می‌گذارد. و بیشتر وقت‌ها برنامه فقط به چند هفته‌ی آخر کار دارد. چرا پایگاه داده باید با کل جدول مثل یک توده‌ی بزرگ رفتار کند؟

{{< term "partitioning" "Partitioning" >}} جواب PostgreSQL است: یک جدول منطقی تعریف می‌کنید، ولی در عمل در چند جدول فیزیکی کوچک‌تر به اسم پارتیشن ذخیره می‌شود، که هرکدام یک تکه از داده را نگه می‌دارد (مثلاً یک ماه). برنامه همچنان از همان یک جدول منطقی query می‌گیرد. دو چیز بهتر می‌شود. queryای که فقط یک تکه را لازم دارد می‌تواند از بقیه‌ی تکه‌ها رد شود. و پاک کردن داده‌ی قدیمی به‌جای حذف ردیف‌به‌ردیف، کنار گذاشتن یک پارتیشن کامل می‌شود. بقیه‌ی چیزها سریع‌تر نمی‌شوند و بعضی کندتر هم می‌شوند، که بخش‌های آخر نشانش می‌دهند.

این پست بعد از [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/) می‌آید و به [ایندکس و EXPLAIN](/fa/posts/db-indexes-btree-explain/) و [planner و آمار](/fa/posts/db-planner-statistics/) تکیه دارد، چون فایده‌اش در planها دیده می‌شود.

> همه‌چیز روی PostgreSQL 18.3 واقعی اجرا شد (برای این نسخه‌ی پست دمو را دوباره اجرا کردم). داده، جدول `orders` فروشگاه است (۲۰۰٬۰۰۰ ردیف، از 2025-01-01 تا 2026-02-05) که در یک جدول partitioned کپی شد. اسکن موازی را خاموش کردم تا planها کوتاه بمانند، و زمان‌سنجی نشان نمی‌دهم، فقط تعداد buffer. یک buffer اینجا یک page هشت کیلوبایتی از جدول است که از حافظه یا دیسک خوانده شده، پس عدد کمتر یعنی داده‌ی کمتری خوانده شده. time zone نشست برابر UTC بود.

## range partition ماهانه

جدول والد با `PARTITION BY RANGE (created_at)` تعریف می‌شود. یعنی هر ردیف بسته به اینکه `created_at`اش در کدام بازه بیفتد به یک پارتیشن می‌رود. ستونی که بر اساسش تقسیم می‌کنید **کلید پارتیشن** نام دارد. اولین کاری که امتحان کردم اضافه کردن {{< term "primary-key" "primary key" >}} روی `id` تنها بود:

```text
ALTER TABLE orders_p ADD PRIMARY KEY (id);
ERROR:  unique constraint on partitioned table must include all partitioning columns
DETAIL:  PRIMARY KEY constraint on table "orders_p" lacks column "created_at" which is part of the partition key.
```

PostgreSQL قبول نکرد. دلیل این است که هر پارتیشن ایندکس خودش را دارد و یک ایندکس فقط پارتیشن خودش را می‌بیند. پس PostgreSQL فقط وقتی می‌تواند یکتایی را بین همه‌ی پارتیشن‌ها تضمین کند که کلید پارتیشن جزو constraint باشد: آن‌وقت دو کلید برابر ناچار در یک پارتیشن می‌افتند و یک ایندکس می‌تواند آن‌ها را بگیرد. `PRIMARY KEY (id, created_at)` کار کرد. نتیجه‌ی عملی این است که `id` تنها دیگر از نظر پایگاه داده یکتا نیست.

بعد یک حلقه ۱۴ پارتیشن ماهانه ساخت، از ژانویه‌ی 2025 تا فوریه‌ی 2026، و `INSERT ... SELECT` هر ۲۰۰٬۰۰۰ ردیف را بار کرد. تعداد ردیف و اندازه‌ی هر پارتیشن از `pg_partition_tree` و `pg_relation_size` آمد:

```text
    partition     | rows  |  size
 orders_p_2025_01 | 15500 | 1040 kB
 orders_p_2025_02 | 14000 | 936 kB
 ...
 orders_p_2026_01 | 15500 | 1048 kB
 orders_p_2026_02 |  2000 | 136 kB
```

(ردیف‌های وسط را حذف کرده‌ام؛ هرکدام حدود ۱۵ هزار ردیف و نزدیک یک مگابایت است.) پارتیشن آخر کوچک است چون داده در پنجم فوریه تمام می‌شود.

## partition pruning: کل ماجرا همین است

حالا دو query. اولی روی یک ماه از `created_at`، یعنی کلید پارتیشن، فیلتر می‌کند. دومی روی `status` که جزو کلید نیست. هر دو به خط‌های مهم کوتاه شده‌اند:

```text
WHERE created_at >= '2025-06-01' AND created_at < '2025-07-01'
 Aggregate
   Buffers: shared hit=126
   ->  Seq Scan on orders_p_2025_06 orders_p
 Planning:
   Buffers: shared hit=26

WHERE status = 'paid'
 Aggregate
   Buffers: shared hit=1679
   ->  Append
         ->  Seq Scan on orders_p_2025_01 ... (14 scans in total)
 Planning:
   Buffers: shared hit=56
```

در query اول {{< term "query-planner" "planner" >}} از روی بازه‌ها می‌دانست ردیف‌های ژوئن فقط در کدام پارتیشن می‌توانند باشند و ۱۳ پارتیشن دیگر را پیش از اجرای هر چیزی کنار گذاشت. این همان {{< term "partition-pruning" "partition pruning" >}} است. پلن فقط یک اسکن دارد، روی `orders_p_2025_06`، و ۱۲۶ buffer خواند (اندازه‌ی آن پارتیشن ۱٬۰۰۸ کیلوبایت است، یعنی ۱۲۶ page هشت کیلوبایتی، پس دقیقاً یک بار خواندن کامل آن). در query دوم `status` چیزی درباره‌ی ماه ردیف نمی‌گوید، پس planner نمی‌تواند هیچ پارتیشنی را رد کند. گره‌ی `Append` هر ۱۴ پارتیشن را اسکن می‌کند و ۱٬۶۷۹ buffer می‌خواند.

برای اثبات اینکه صرفه‌جویی از pruning است، query اول را دوباره با `SET enable_partition_pruning = off` اجرا کردم. همان جواب برگشت، ولی با ۱٬۶۷۹ buffer و ۱۴ اسکن که ۱۳ تایش صفر ردیف برمی‌گرداند. نتیجه‌ی یکسان، سیزده برابر خواندن. خط‌های `Planning` هزینه‌ی ساختن پلن را نشان می‌دهند که در آخر مهم می‌شود.

## ردیفی که در هیچ پارتیشنی جا نمی‌شود

```text
INSERT ... created_at = '2026-05-10'
ERROR:  no partition of relation "orders_p" found for row
DETAIL:  Partition key of the failing row contains (created_at) = (2026-05-10 00:00:00+00).
```

من پارتیشن‌ها را فقط تا فوریه‌ی 2026 ساخته بودم، پس این insert شکست خورد. در یک سیستم واقعی همین می‌تواند نیمه‌شب اول یک ماه رخ دهد، اگر کسی به‌موقع پارتیشن ماه جدید را نساخته باشد. {{< term "default-partition" "default partition" >}} تور ایمنی است: هر ردیفی را که جای دیگری جا نمی‌شود قبول می‌کند. بعد از ساختنش همان insert کار کرد. ولی یک تله هست. وقتی بعدش خواستم پارتیشن درست ماه مه را بسازم:

```text
ERROR:  updated partition constraint for default partition "orders_p_default" would be violated by some row
```

ردیف ماه مه از قبل در default بود و PostgreSQL تا وقتی default ردیف‌های ماه مه را دارد پارتیشن ماه مه نمی‌سازد، چون آن ردیف آن‌وقت به دو جا تعلق می‌گیرد. راه خروج، در یک تراکنش: default را detach کن، پارتیشن ماه مه را بساز، ردیف‌ها را از جدول default دوباره insert کن (حالا به ماه مه می‌روند)، default را truncate کن و دوباره attach کن. درس این است که پارتیشن‌ها را قبل از رسیدن داده‌ی آن‌ها بسازید و ردیف در default partition را یک هشدار حساب کنید.

## ایندکس‌ها

`CREATE INDEX orders_p_cust_idx ON orders_p (customer_id)` روی والد، روی هر پارتیشن یک ایندکس هم‌نام ساخت (مثل `orders_p_2025_01_customer_id_idx`) و پارتیشن‌های جدید خودکار آن را می‌گیرند. پس ایندکس روی جدول partitioned در واقع چند ایندکس کوچک است، یکی برای هر پارتیشن.

## DETACH و ATTACH: راه ارزان حذف داده‌ی قدیمی

```text
count(*) orders_p: 200001   (the extra row is the May test row)
ALTER TABLE orders_p DETACH PARTITION orders_p_2025_01;
count(*) orders_p: 184501
count(*) orders_p_2025_01: 15500
```

۱۵٬۵۰۰ ردیف ژانویه در یک گام از والد بیرون رفت و به یک جدول معمولی تبدیل شد که می‌شود بایگانی کرد یا `DROP` زد. با فوریه هم همین را کردم و بعد `DROP TABLE` زدم. حذف یک ماه تغییر در کاتالوگ است، نه یک `DELETE` بزرگ که برای `VACUUM` {{< term "vacuum" "ردیف مرده" >}} باقی می‌گذارد. این همان فایده‌ی دومی است که اول پست گفتم و برای خیلی از تیم‌ها فایده‌ی اصلی است.

طبق مستندات `DETACH PARTITION ... CONCURRENTLY` برای این هست که detach کمتر مسدود کند. در یک اجرای موقت روی 18.3 آن را روی همین جدول، که هنوز default partition داشت، امتحان کردم و رد شد: `ERROR: cannot detach partitions concurrently when a default partition exists`. پس default partition هزینه‌ی دومی هم دارد. مسیر موفق را امتحان نکردم.

جایی که اعتبارسنجی مهم می‌شود attach کردن است (چه جدولی که برش می‌گردانید، چه جدول تازه‌ای که جدا بار کرده‌اید). PostgreSQL باید مطمئن شود هر ردیف پارتیشن جدید واقعاً به بازه‌اش تعلق دارد. با `client_min_messages = debug1` خود سرور می‌گوید چه کرد:

```text
ATTACH ... (no CHECK constraint)
DEBUG:  verifying table "orders_p_2025_01"
DEBUG:  verifying table "orders_p_default"

after ADD CONSTRAINT jan_ck CHECK (created_at >= '2025-01-01' AND created_at < '2025-02-01')
DEBUG:  verifying table "orders_p_2025_01"        (printed by ADD CONSTRAINT itself)
DEBUG:  partition constraint for table "orders_p_2025_01" is implied by existing constraints
DEBUG:  verifying table "orders_p_default"
```

بدون `CHECK`، PostgreSQL جدولِ در حال attach را verify، یعنی اسکن، کرد، آن هم به‌عنوان بخشی از خود attach. با یک `CHECK` که همین حرف را از قبل می‌زند، اسکن حذف شد («implied by existing constraints»). اسکن پارتیشن default باز هم انجام شد. (آن یک خط `verifying` اضافه از `ADD CONSTRAINT` است که جدول مستقل را اسکن می‌کند تا ردیف‌های خودش را بسنجد. نکته همین است: هزینه‌ی این اسکن را پیش از attach و روی جدولی می‌دهید که کسی از آن query نمی‌گیرد، نه در حین attach.) جدولی که ردیفی خارج از بازه دارد رد می‌شود: `ERROR: partition constraint of relation "bad" is violated by some row`.

## LIST و HASH

range تنها راه تقسیم نیست. `PARTITION BY LIST (country)` با `FOR VALUES IN ('IR')` و `IN ('DE','FR','NL')` از ۴ ردیف آزمایشی من ۲ و ۲ را در دو پارتیشن گذاشت. `PARTITION BY HASH (id)` با `MODULUS 4` بازه‌ی طبیعی ندارد؛ ردیف‌ها را با hash کلید یکنواخت پخش می‌کند. هزار ردیف را به‌صورت ۲۵۹، ۲۳۴، ۲۷۶ و ۲۳۱ پخش کرد و `WHERE id = 42` فقط روی یک پارتیشن، `ord_h_2`، index scan زد.

## کجا کمک نمی‌کند

pruning رایگان نیست: با زیاد شدن پارتیشن‌ها planner چیزهای بیشتری برای نگاه کردن دارد. برای اندازه‌گیری، دو جدول خالی با ۱۰ و ۵۰۰ پارتیشن ساختم (primary key برابر `(id, t)`) و خط `Planning: Buffers` را خواندم (اجرای دوم؛ در تکرار هم همین عددها آمد):

```text
                          10 partitions   500 partitions
filter on the key         198             1563
filter on id only         312             16989
```

حتی queryای که تا یک پارتیشن pruning می‌شود با ۵۰۰ پارتیشن حدود هشت برابر buffer planning گرفت (۱٬۵۶۳ در برابر ۱۹۸) و queryای که کلید را ندارد حدود پنجاه‌وپنج برابر (۱۶٬۹۸۹ در برابر ۳۱۲). اینها شمارش روی جدول خالی است، نه زمان، پس چیزی نمی‌گویند که چند میلی‌ثانیه از دست می‌دهید. نظر خودم: وقتی partition کنید که داده‌ی قدیمی را بر اساس تاریخ حذف می‌کنید یا بیشتر queryها کلید پارتیشن را دارند. تعداد پارتیشن‌ها را در حد دهها نگه دارید. و فقط چون جدول بزرگ است partition نکنید: یک ایندکس معمولی اغلب با دردسر خیلی کمتر بیشتر کمک می‌کند.

## پیش از partition کردن

- **primary key و هر ایندکس یکتا باید کلید پارتیشن را داشته باشد.** کلیدهایتان را بر اساس آن طراحی کنید.
- **برای ردیف‌هایی که در هیچ بازه‌ای نمی‌افتند برنامه داشته باشید**: کاری که پارتیشن‌ها را از پیش می‌سازد، یا یک default partition که رویش نظارت دارید.
- **پیش از `ATTACH` یک `CHECK` هم‌خوان اضافه کنید** تا attach به اسکن اعتبارسنجی زیر قفل نیاز نداشته باشد.
- **default partition ساخت پارتیشن جدید را کندتر می‌کند و می‌تواند مسدودش کند،** و (همان‌طور که دیدم) `DETACH ... CONCURRENTLY` را هم مسدود کرد.
- **queryهای بدون کلید پارتیشن همه‌ی پارتیشن‌ها را می‌خوانند،** پس پیش از انتخاب کلید، planهای queryهای واقعی‌تان را بررسی کنید.

## تمرین

یک کپی از `orders` یا `order_items` را با `HASH (customer_id)` پارتیشن کنید و `EXPLAIN (ANALYZE, BUFFERS)` را برای فیلتر روی `customer_id` و فیلتر روی `status` مقایسه کنید. بعد سعی کنید جدولی با یک ردیف خارج از بازه attach کنید و ببینید خطا چه می‌گوید.

## قدم بعدی

قدم بعدی [replication با دو instance واقعی](/fa/posts/db-replication-streaming/) است. partitioning یک جدول را داخل یک سرور به تکه‌ها تقسیم کرد؛ replication جهت دیگر است: نسخه‌ی دومِ کل سرور که دنبال اولی می‌رود.
