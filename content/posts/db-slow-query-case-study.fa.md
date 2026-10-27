+++
date = '2027-03-23T10:00:00+03:30'
draft = false
title = 'case study: پیدا کردن و رفع یک query کند'
description = 'case study یک query کند در PostgreSQL: آمار قدیمی، ایندکس ترکیبی گم‌شده، تابع روی ستون و زیرپرس‌وجوی وابسته، با شمارش واقعی bufferها.'
categories = ["Databases"]
series = ["Databases"]
tags = ["postgresql", "databases", "slow-query", "explain", "performance", "case-study"]
cover = { image = "/images/covers/db-slow-query-case-study.fa.png", alt = "case study: پیدا کردن و رفع یک query کند", hiddenInSingle = true }
+++

در [پست قبل](/fa/posts/db-connection-pooling/) دیدیم connectionها زیر بار چطور خراب می‌شوند. این آخرین پست مجموعه است: یک گزارش کند که قدم‌به‌قدم و با چیزهایی که پست‌های قبل یاد دادند درست می‌شود: [ایندکس B-tree و EXPLAIN](/fa/posts/db-indexes-btree-explain/)، [ایندکس ترکیبی](/fa/posts/db-composite-partial-covering-indexes/) و [آمار planner](/fa/posts/db-planner-statistics/).

> PostgreSQL 18.3 واقعی و seed فروشگاه، به‌علاوه‌ی یک «import شبانه» از ۴۰ هزار سفارش مارس ۲۰۲۶ با ۱۲۰ هزار آیتم، با autovacuum خاموش تا هیچ‌وقت analyze نشود. ماشین شلوغ بود، پس به‌جای میلی‌ثانیه، bufferها (pageهای ۸ کیلوبایتی) را از `EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, SUMMARY OFF)` با اجرای موازی خاموش نشان می‌دهم. `pg_stat_statements` اینجا کار نمی‌کند (خطای «must be loaded via shared_preload_libraries» که در این build نمی‌توانم تنظیمش کنم)، پس فقط از `EXPLAIN` استفاده می‌کنم.

## گزارش

درآمد هر مشتری از سفارش‌های `paid` در یک ماه، ۱۰ تای اول:

```sql
SELECT c.id, date_trunc('month', o.created_at) AS month, sum(oi.qty * oi.price_cents) AS revenue
FROM orders o
JOIN order_items oi ON oi.order_id = o.id
JOIN customers c ON c.id = o.customer_id
WHERE o.status = 'paid' AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01'
GROUP BY c.id, month ORDER BY revenue DESC LIMIT 10;
```

نتیجه‌ی قدم صفر: `Buffers: shared hit=67367`. خط‌های جالب:

```text
Seq Scan on orders o  (cost=0.00..6857.00 rows=1 ...) (actual rows=8000.00 loops=1)
Index Scan using order_items_pkey on order_items oi  (rows=3) (actual rows=3.00 loops=8000)
```

planner یک ردیف انتظار داشت و ۸۰۰۰ ردیف آمد، برای همین روی هر دو جدول ۸۰۰۰ بار با ایندکس جست‌وجو کرد. چنین فاصله‌ای یعنی آمار بد.

## رفع ۱: ANALYZE

import ردیف‌های مارس ۲۰۲۶ را بعد از آخرین مقدار {{< term "planner-statistics" "آمار" >}} اضافه کرد و planner فرض کرد تقریباً هیچ ردیفی نیست. یک دستور:

```sql
ANALYZE orders; ANALYZE order_items;
```

پلن جدید: تخمین ۷۶۸۴ در برابر واقعی ۸۰۰۰، hash join و `Buffers: shared hit=8862`. از ۶۷۳۶۷ به ۸۸۶۲ page، بدون تغییر schema. (هزینه‌ی تخمینی از ۶۸۷۷ به ۲۳۸۸۷ رفت: پلن اول فقط روی کاغذ ارزان بود.) با این حال `orders` کامل خوانده می‌شود: ۳۳۵۷ page برای ۸۰۰۰ ردیف.

## رفع ۲: ایندکس ترکیبی

فیلتر، تساوی روی `status` و بازه روی `created_at` است، دقیقاً کار یک {{< term "composite-index" "ایندکس ترکیبی" >}}:

```sql
CREATE INDEX orders_status_created_idx ON orders (status, created_at);
```

node مربوط به `orders` شد یک {{< term "bitmap-scan" "bitmap scan" >}} با ۳۷۱ page به‌جای ۳۳۵۷ و مجموع به ۵۸۷۶ رسید. چیزی که عوض نشد: `order_items` هنوز `Seq Scan` است (۵۲۹۵ page). و درست هم هست: گزارش ۸۰۰۰ سفارش می‌خواهد و ۸۰۰۰ جست‌وجو خیلی گران‌تر از یک خواندن ترتیبی است. هر `Seq Scan` باگ نیست.

## رفع ۳: تابع روی ستون

یک همکار فیلتر ماه را «خواناتر» می‌نویسد:

```sql
WHERE status = 'paid' AND to_char(created_at, 'YYYY-MM') = '2026-03'
```

دیگر {{< term "sargable" "sargable" >}} نیست: ۱۴۵ page و تخمین ۲۳۸ ردیف (واقعی ۸۰۰۰)، در برابر ۳۵ page و تخمین ۷۶۲۸ برای شکل بازه‌ای. ایندکس `status` باز هم کمک کرد، ولی تاریخ‌ها بعد از خواندن فیلتر شدند (`Rows Removed by Filter: 40000`). ستون را دست‌نخورده نگه دارید.

## رفع ۴: زیرپرس‌وجوی وابسته

گزارش دوم تعداد سفارش‌های `paid` مارس را برای مشتری‌های یک کشور می‌شمارد:

```sql
SELECT c.id, c.email,
  (SELECT count(*) FROM orders o WHERE o.customer_id = c.id AND o.status = 'paid'
     AND o.created_at >= '2026-03-01' AND o.created_at < '2026-04-01')
FROM customers c WHERE c.country = 'IR';
```

یک {{< term "correlated-subquery" "correlated subquery" >}} برای هر مشتری یک بار اجرا می‌شود: `loops=1666` و هر دور ۸۰۰۰ ردیف ماه را خواند و بیشترش را دور ریخت. مجموع: ۶۱۸۲۹۳ page. دو قدم، جدا اندازه‌گیری‌شده:

```text
 CREATE INDEX orders_customer_id_idx ON orders (customer_id)   -> 23493 page
 بازنویسی با LEFT JOIN ... GROUP BY c.id                       ->   578 page
```

ستون {{< term "foreign-key" "foreign key" >}} ایندکس نداشت. ایندکس ۲۶ برابر کم کرد و join ۴۰ برابر دیگر. همین شکل در کد برنامه {{< term "n-plus-one" "N+1" >}} است: یک پلن کند نمی‌بینید، فقط query‌های سریع زیاد. اینجا `pg_stat_statements` به کار می‌آمد که نتوانستم اجرایش کنم.

## آیا رفع‌ها نوشتن را بدتر کردند؟

دو کپی از `orders` (۲۴۰ هزار ردیف) ساختم: یکی فقط با primary key و یکی با دو ایندکس جدید، همان ۲۰ هزار ردیف را در هر دو insert کردم و {{< term "wal" "WAL" >}} را مقایسه کردم:

```text
 فقط primary key         3287672 بایت
 + دو ایندکس جدید        8080232 بایت
```

حدود ۲٫۵ برابر WAL برای همان ردیف‌ها، و ایندکس‌های کپی ۱۳ مگابایت شدند در برابر ۵۲۸۸ کیلوبایت. این بهاست؛ روی جدول پرنوشتن، پیش از پرداختش اندازه می‌گیرم.

## چند نکته‌ی مهم

- اول `rows` را با `actual rows` مقایسه کنید؛ به آمار اشاره می‌کند.
- هر بار یک چیز را عوض کنید و بعدش buffer را ثبت کنید.
- دنبال `loops=` در حد هزاران بگردید: هزینه‌ی هر ردیف است.
- پیش از اضافه کردن ایندکس به جدول شلوغ، هزینه‌ی نوشتن را اندازه بگیرید.

## چک‌لیست برای query کند بعدی

1. query واقعی را بگیرید و `EXPLAIN (ANALYZE, BUFFERS)` را روی داده‌ی واقع‌گرایانه بزنید.
2. تخمین‌ها دور از واقعی‌اند؟ `ANALYZE`، و در صورت نیاز آمار گسترده.
3. اسکن بزرگ برای ردیف کم؟ ایندکس ستون‌های `WHERE` را به ترتیب بررسی کنید.
4. تابع یا cast روی ستون؟ بازنویسی کنید.
5. `loops` بالا؟ زیرپرس‌وجو یا N+1 را با join عوض کنید.
6. دوباره اندازه بگیرید، بعد هزینه‌ی نوشتن را ببینید.

## تمرین

1. seed را بارگذاری کنید، ماه اضافه را بدون `ANALYZE` import کنید و قدم صفر را بازتولید کنید.
2. به ترتیب بالا درستش کنید و بعد از هر قدم buffer را یادداشت کنید.
3. گزارش را به یک هفته کوچک کنید. آیا planner حالا `order_items` را با ایندکس جست‌وجو می‌کند؟

## قدم بعدی

این آخرین پست مجموعه‌ی Databases است. مجموعه‌ی Distributed Systems بعداً در برنامه می‌آید.
