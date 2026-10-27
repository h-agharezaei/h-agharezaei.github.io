+++
date = '2027-05-19T10:00:00+03:30'
draft = false
title = 'پردازش داده‌ی کوچک با csv و sqlite3'
description = 'پردازش داده با csv و sqlite3 در Python: quoting، BOM، حافظه‌ی streaming، درج دسته‌ای، پارامتر، ایندکس، EXPLAIN و حالت WAL.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "csv", "sqlite", "sqlite3", "data"]
cover = { image = "/images/covers/py-data-csv-sqlite.fa.png", alt = "پردازش داده‌ی کوچک با csv و sqlite3", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-cli-scripts/) ابزار خط فرمان نوشتیم. خیلی از اسکریپت‌های واقعی بعدش یک کار دیگر هم می‌کنند: CSV‌ای را که کسی فرستاده می‌خوانند و به یک سؤال درباره‌اش جواب می‌دهند. کتابخانه‌ی استاندارد برای این کار کافی است. این مقاله `csv` و `sqlite3` را روی فایلی با ۲۰۰٬۰۰۰ ردیف به کار می‌برد و برای streaming از [generator](/fa/posts/py-functions-generators/) استفاده می‌کند. با [فایل و JSON در Go](/fa/posts/go-file-io-json/) مقایسه کنید.

> Python 3.14.0، SQLite 3.54.0 (از `sqlite3.sqlite_version`)، فقط کتابخانه‌ی استاندارد، در یک پوشه‌ی موقت. سفارش‌ها ساختگی‌اند (random با seed ثابت). ماشین مشغول بود (load حدود ۳)، پس **زمان‌بندی** منتشر نمی‌کنم، فقط تعداد و بایت. pandas اینجا نصب نیست و اجرایش نکردم. دمو یک نمونه‌ی محلی است.

## خواندن درست CSV

فایل `orders.csv` را با `csv.writer` ساختم: ستون‌های `id, customer, sku, qty, price, ts` و ۱۰٬۶۷۳٬۰۰۰ بایت. بعضی مشتری‌ها `Smith, John`، `Anne "Ace" Lee` و اسمی با خط جدید هستند. فایل ۲۲۵٬۰۰۶ خط فیزیکی دارد ولی ۲۰۰٬۰۰۰ ردیف. split ساده خراب می‌کند:

```text
split: 7 ['7', '"Smith', ' John"', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
csv:   ['7', 'Smith, John', 'SKU-001', '2', '19.99', '2027-01-01T10:00:00']
```

همیشه با `newline=""` و `encoding` صریح باز کنید. `csv.reader` لیست می‌دهد و `csv.DictReader` دیکشنری با کلیدهای هدر. همه‌ی مقدارها **رشته** هستند، پس `'3'` به `int()` نیاز دارد. `csv.DictWriter` فقط وقت لزوم quote می‌گذارد:

```text
'id,customer\r\n1,"Anne ""Ace"" Lee"\r\n2,"Line\nBreak"\r\n'
```

## encoding و BOM در Excel

متن فارسی با UTF-8 بدون مشکل رفت‌وبرگشت می‌کند. مشکل کلاسیک، فایل ذخیره‌شده با Excel است که با یک {{< term "byte-order-mark" "BOM" >}} شروع می‌شود. خواندنش با `utf-8` ساده نام ستون اول را آلوده می‌کند:

```text
raw bytes start: b'\xef\xbb\xbfid'
utf-8 read keys: ['﻿id', 'name']
utf-8-sig: {'id': '1', 'name': 'نیلوفر'}
```

با `utf-8-sig` بخوانید. برای فایلی که Excel درست نشان دهد، با `utf-8-sig` بنویسید.

## streaming با generator

حافظه با `tracemalloc` اندازه‌گیری شد (پیک، تا حد گرد کردن قابل تکرار):

```text
list rows 200000 peak MB 106
stream qty sum 599692 peak MB 0.19
```

`list(csv.DictReader(f))` همه چیز را نگه داشت: حدود ۱۰۶ مگابایت برای فایل ۱۰ مگابایتی، چون هر ردیف یک دیکشنری از رشته‌هاست. حلقه روی reader فقط ۰٫۱۹ مگابایت لازم داشت. reader را داخل یک {{< term "generator" "generator" >}} بگذارید و `itertools.islice(rows(), 3)` چند ردیف اول را بدون خواندن بقیه نشان می‌دهد. این همان ایده‌ی [استریم در Node.js](/fa/posts/node-streams-backpressure/) است.

## SQLite: همه را در یک تراکنش بارگذاری کنید

`sqlite3` سرور نمی‌خواهد. جدول ساختم و با `executemany` و یک generator، داخل یک {{< term "transaction" "تراکنش" >}} (`with db:`) بارگذاری کردم:

```python
with db:
    db.executemany("INSERT INTO orders VALUES (?,?,?,?,?,?)", gen())
```

یعنی ۲۰۰٬۰۰۰ ردیف و یک commit؛ `PRAGMA journal_mode` مقدار پیش‌فرض `delete` را نشان داد. روش کند، commit برای هر ردیف است: با ۲٬۰۰۰ ردیف می‌شود ۲٬۰۰۰ commit که هرکدام یک نوشتن پایدار روی دیسک را اجبار می‌کند. commitها را شمردم و به خاطر load زمان نگرفتم. هر commit یک sync دیسک است و فرق بزرگ است، ولی عددی نقل نمی‌کنم.

## bind کردن پارامتر

علامت‌های `?` همان {{< term "parameterized-query" "پارامتر bind شده" >}} هستند. یک دموی بی‌خطر روی جدول `users` با ورودی `x' OR '1'='1`:

```text
formatted: [('ali',), ('sara',)] bound: []
```

نسخه‌ی f-string همه‌ی کاربرها را برگرداند و نسخه‌ی bind شده هیچ‌کدام را. این همان {{< term "sql-injection" "SQL injection" >}} است؛ [تزریق و XSS](/fa/posts/sec-injection-xss/) را ببینید. هرگز SQL را با فرمت‌کردن رشته نسازید.

با `db.row_factory = sqlite3.Row` می‌توانید `row["sku"]` و `row.keys()` را به کار ببرید.

## ایندکس و EXPLAIN QUERY PLAN

برای `SELECT count(*), sum(qty*price) FROM orders WHERE sku = 'SKU-007'`:

```text
before: SCAN orders
after:  SEARCH orders USING INDEX idx_orders_sku (sku=?)
```

اولی کل جدول را می‌خواند؛ بعد از `CREATE INDEX` همان {{< term "query-plan" "plan" >}} از یک {{< term "database-index" "ایندکس" >}} استفاده می‌کند. ایده همان [ایندکس B-tree و EXPLAIN ANALYZE](/fa/posts/db-indexes-btree-explain/) است. گزارش، SQL ساده است:

```text
SELECT sku, count(*), round(sum(qty*price),2) ... GROUP BY sku ORDER BY revenue DESC LIMIT 3
('SKU-002', 4135, 636960.12)
('SKU-010', 4081, 630724.13)
('SKU-029', 4027, 628905.06)
```

## غافلگیری type affinity

جدول `a(n INTEGER)` ساختم و `'12'`، `'abc'`، `3.0` و `3.5` را درج کردم. `typeof(n)` این را داد:

```text
[(12, 'integer'), ('abc', 'text'), (3, 'integer'), (3.5, 'real')]
```

`'12'` تبدیل شد و `'abc'` پذیرفته شد. این {{< term "type-affinity" "type affinity" >}} است. جدول `STRICT` رد می‌کند: `IntegrityError cannot store TEXT value in INTEGER column s.n`.

## WAL، ATTACH و خروجی

بعد از `db.commit()`، دستور `PRAGMA journal_mode=WAL` مقدار `wal` را برگرداند و `ls` این را نشان داد:

```text
['shop.db', 'shop.db-shm', 'shop.db-wal']
```

WAL اجازه می‌دهد خواننده‌ها و یک نویسنده هم‌زمان کار کنند. در اجرای اول، تا وقتی تراکنشی باز بود این pragma اثری نداشت، پس اول commit کنید. `:memory:` دیتابیس موقت می‌دهد و `ATTACH` دیتابیس دوم را به همان اتصال اضافه می‌کند. یکی در حافظه attach کردم، جدول سه برتر را ساختم و با `csv.writer` به CSV برگرداندم:

```text
sku,q
SKU-002,12469
SKU-044,12308
SKU-018,12299
```

یک فایل SQLite به‌عنوان فرمت فایل اپلیکیشن هم رایج است. وقتی چند نویسنده، شبکه یا نقش‌ها لازم شد، به Postgres بروید ([SQLAlchemy و Postgres](/fa/posts/py-sqlalchemy-postgres/)).

## چند نکته‌ی مهم

- روی هر فایل CSV از `newline=""` و encoding صریح استفاده کنید.
- همه‌ی مقدارهای CSV رشته‌اند؛ تبدیلشان کنید.
- برای بارگذاری دسته‌ای یک تراکنش.
- پارامتر bind کنید و SQL را فرمت نکنید.
- قبل از عوض کردن journal mode، commit کنید.

## تمرین

گزینه‌ی `--stats` اضافه کنید که یک CSV را به یک SQLite در حافظه استریم کند و درآمد هر مشتری را چاپ کند. پیک حافظه را با `tracemalloc` بررسی کنید.

## قدم بعدی

مقاله‌ی بعدی «صدا زدن Rust از Python با ctypes و PyO3» است.
