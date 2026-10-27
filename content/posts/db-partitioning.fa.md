+++
date = '2027-01-30T10:00:00+03:30'
draft = false
title = 'partitioning جدول‌ها'
description = 'partitioning جدول در PostgreSQL با اجرای واقعی: range partition، partition pruning در EXPLAIN، قانون primary key، DETACH و ATTACH و جایی که کمکی نمی‌کند.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "partitioning", "performance"]
cover = { image = "/images/covers/db-partitioning.fa.png", alt = "partitioning جدول‌ها", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-zero-downtime-migrations/) یک جدول زنده را بدون توقف تغییر دادیم. این پست درباره‌ی جدولی است که آن‌قدر بزرگ شده که نمی‌شود با آن مثل یک تکه رفتار کرد. {{< term "partitioning" "Partitioning" >}} یک جدول منطقی را به چند جدول فیزیکی کوچک‌تر تقسیم می‌کند. در دو وضعیت کمک می‌کند: کوئری‌هایی که فقط به یک تکه از داده دست می‌زنند و حذف ارزان داده‌ی قدیمی. همه‌چیز را سریع‌تر نمی‌کند و شواهد زیر نشان می‌دهد هزینه‌اش کجاست. پایه‌اش [ایندکس و EXPLAIN](/fa/posts/db-indexes-btree-explain/) و [planner و آمار](/fa/posts/db-planner-statistics/) است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی اجرا شد. جدول `orders` فروشگاه (۲۰۰٬۰۰۰ ردیف، از 2025-01-01 تا 2026-02-05) در یک جدول partitioned کپی شد. اسکن موازی را خاموش کردم تا planها کوتاه بمانند و زمان‌سنجی نیست، فقط تعداد buffer. time zone برابر UTC بود.

## range partition ماهانه

جدول والد با `PARTITION BY RANGE (created_at)` تعریف می‌شود. اول قانون {{< term "primary-key" "primary key" >}}:

```text
ALTER TABLE orders_p ADD PRIMARY KEY (id);
ERROR:  unique constraint on partitioned table must include all partitioning columns
DETAIL:  PRIMARY KEY constraint on table "orders_p" lacks column "created_at" which is part of the partition key.
```

هر پارتیشن ایندکس خودش را دارد، پس PostgreSQL فقط وقتی می‌تواند یکتایی را بین پارتیشن‌ها تضمین کند که کلید پارتیشن جزو constraint باشد. `PRIMARY KEY (id, created_at)` کار کرد. یک حلقه ۱۴ پارتیشن ماهانه ساخت و `INSERT ... SELECT` هر ۲۰۰٬۰۰۰ ردیف را بار کرد. تعداد ردیف و اندازه‌ی هر پارتیشن از `pg_partition_tree` و `pg_relation_size` آمد:

```text
    partition     | rows  |  size
 orders_p_2025_01 | 15500 | 1040 kB
 orders_p_2025_02 | 14000 | 936 kB
 ...
 orders_p_2026_01 | 15500 | 1048 kB
 orders_p_2026_02 |  2000 | 136 kB
```

## partition pruning

یک کوئری روی یک ماه، و یک کوئری که فقط روی `status` فیلتر می‌کند:

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

با وجود کلید، {{< term "query-planner" "planner" >}} پیش از اجرا ۱۳ پارتیشن را حذف کرد ({{< term "partition-pruning" "partition pruning" >}}): یک اسکن و ۱۲۶ buffer. بدون کلید هر ۱۴ پارتیشن اسکن شد: ۱٬۶۷۹ buffer. بعد همان کوئری اول را با `SET enable_partition_pruning = off` اجرا کردم: همان ۱٬۶۷۹ buffer و ۱۴ اسکن آمد که ۱۳ تایش صفر ردیف برمی‌گرداند. جواب یکی، خواندن سیزده برابر.

## ردیف بی‌پارتیشن و default partition

```text
INSERT ... created_at = '2026-05-10'
ERROR:  no partition of relation "orders_p" found for row
DETAIL:  Partition key of the failing row contains (created_at) = (2026-05-10 00:00:00+00).
```

یک {{< term "default-partition" "default partition" >}} این ردیف‌ها را می‌گیرد و همان insert بعد از ساختنش کار کرد. تله این بود که بعدش خواستم پارتیشن ماه مه را بسازم:

```text
ERROR:  updated partition constraint for default partition "orders_p_default" would be violated by some row
```

ردیف ماه مه از قبل در default بود. راه‌حل در یک تراکنش: default را detach کردم، ماه مه را ساختم، ردیف‌ها را از default برگرداندم، آن را truncate و دوباره attach کردم. پارتیشن‌های جدید را پیش از رسیدن داده بسازید.

## ایندکس‌ها

`CREATE INDEX orders_p_cust_idx ON orders_p (customer_id)` روی والد، روی هر پارتیشن یک ایندکس هم‌نام ساخت (مثل `orders_p_2025_01_customer_id_idx`). پارتیشن‌های جدید خودکار آن را می‌گیرند.

## DETACH و ATTACH

```text
count(*) orders_p: 200001   (the extra row is the May test row)
ALTER TABLE orders_p DETACH PARTITION orders_p_2025_01;
count(*) orders_p: 184501
count(*) orders_p_2025_01: 15500
```

۱۵٬۵۰۰ ردیف یک‌باره از والد بیرون رفت و به یک جدول معمولی تبدیل شد که می‌شود بایگانی یا `DROP` کرد. با فوریه هم همین را کردم و `DROP TABLE` زدم: حذف یک ماه تغییر در catalog است، نه یک `DELETE` بزرگ که {{< term "vacuum" "ردیف مرده" >}} باقی می‌گذارد. طبق مستندات `DETACH PARTITION ... CONCURRENTLY` برای قفل کمتر هست؛ آن را اجرا نکردم.

در attach، اعتبارسنجی مهم است. با `client_min_messages = debug1`:

```text
ATTACH ... (no CHECK constraint)
DEBUG:  verifying table "orders_p_2025_01"
DEBUG:  verifying table "orders_p_default"

after ADD CONSTRAINT jan_ck CHECK (created_at >= '2025-01-01' AND created_at < '2025-02-01')
DEBUG:  partition constraint for table "orders_p_2025_01" is implied by existing constraints
DEBUG:  verifying table "orders_p_default"
```

بدون `CHECK`، PostgreSQL جدولِ در حال attach را verify (اسکن) کرد و با آن اسکن حذف شد. پارتیشن default را باز هم اسکن کرد. جدولی که ردیفی خارج از بازه دارد رد می‌شود: `ERROR: partition constraint of relation "bad" is violated by some row`.

## LIST و HASH

`PARTITION BY LIST (country)` با `FOR VALUES IN ('IR')` و `IN ('DE','FR','NL')` از ۴ ردیف آزمایشی من ۲ و ۲ را در دو پارتیشن گذاشت. `PARTITION BY HASH (id)` با `MODULUS 4` هزار ردیف را به‌صورت ۲۵۹، ۲۳۴، ۲۷۶ و ۲۳۱ پخش کرد و `WHERE id = 42` فقط `ord_h_2` را اسکن کرد.

## کجا کمک نمی‌کند

با زیاد شدن پارتیشن‌ها، planning کار بیشتری می‌کند. دو جدول خالی با ۱۰ و ۵۰۰ پارتیشن ساختم (primary key برابر `(id, t)`) و `Planning: Buffers` را خواندم (اجرای دوم):

```text
                          10 partitions   500 partitions
filter on the key         198             1563
filter on id only         312             16989
```

حتی کوئری با pruning در ۵۰۰ پارتیشن حدود هشت برابر buffer planning گرفت و کوئری بدون کلید حدود پنجاه برابر. اینها شمارش روی جدول خالی است، نه زمان. نظر خودم: وقتی partition کنید که داده‌ی قدیمی را بر اساس تاریخ حذف می‌کنید یا بیشتر کوئری‌ها کلید را دارند، تعداد را در حد دهها نگه دارید و فقط چون جدول بزرگ است partition نکنید. یک ایندکس اغلب بیشتر کمک می‌کند.

## چند نکته‌ی مهم

- primary key و هر ایندکس یکتا باید کلید پارتیشن را داشته باشد.
- برای ردیف‌های خارج از همه‌ی بازه‌ها برنامه (یا default partition) داشته باشید.
- پیش از `ATTACH` یک `CHECK` هم‌خوان اضافه کنید تا اسکن اعتبارسنجی نشود.
- default partition ساخت پارتیشن جدید را کندتر می‌کند و می‌تواند مسدودش کند.
- کوئری بدون کلید پارتیشن همه‌ی پارتیشن‌ها را می‌خواند.

## تمرین

یک کپی از `orders` یا `order_items` را با `HASH (customer_id)` پارتیشن کنید و `EXPLAIN (ANALYZE, BUFFERS)` را برای فیلتر روی `customer_id` و فیلتر روی `status` مقایسه کنید. بعد سعی کنید جدولی با یک ردیف خارج از بازه attach کنید.

## قدم بعدی

پست بعدی این سری: replication با دو instance واقعی.
