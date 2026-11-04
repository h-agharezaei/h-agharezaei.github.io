+++
date = '2026-11-23T10:00:00+03:30'
draft = false
title = 'طراحی schema و نرمال‌سازی'
description = 'طراحی schema و نرمال‌سازی در PostgreSQL: anomalyهای update، insert و delete را روی یک جدول تخت ببینید و با کلید، قید و نوع داده درستشان کنید.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "schema-design", "normalization"]
cover = { image = "/images/covers/db-schema-design-normalization.fa.png", alt = "طراحی schema و نرمال‌سازی", hiddenInSingle = true }
+++

سارا ایمیلش را عوض می‌کند. برنامه آن را آپدیت می‌کند، ولی فقط یکی از سه ردیف سفارش‌های او مقدار جدید را می‌گیرد. حالا دیتابیس برای یک نفر دو ایمیل متفاوت دارد و هیچ چیزی داخلش نمی‌تواند بگوید کدام درست است. این باگ query نیست؛ query همان کاری را کرد که از آن خواستیم. باگ در شکل جدول‌هاست، و طراحی بد سال‌ها آزار می‌دهد، چون هر query و هر گزارش و هر migration باید دور آن راه بروند.

بعد از [مدل رابطه‌ای و SQL ضروری](/fa/posts/db-relational-sql-essentials/) که در آن خواندن و نوشتن داده را یاد گرفتیم، این پست درباره‌ی خود شکل جدول‌هاست. عمداً از یک طراحی بد شروع می‌کنم، آن را به سه شکل می‌شکنم و بعد قدم‌به‌قدم درستش می‌کنم.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی و با schema فروشگاهی همین سری اجرا شده است.

## یک جدول تخت و سه شکل خراب‌شدنش

اولین طراحی وسوسه‌انگیز یک جدول بزرگ است، شبیه یک spreadsheet: به‌ازای هر سفارش یک ردیف، و همه‌چیز درباره‌ی مشتری و محصول روی همان ردیف. این هم `orders_flat`:

```sql
CREATE TABLE orders_flat (
    order_id       int,
    customer_name  text,
    customer_email text,
    country        text,
    product_name   text,
    category       text,
    price_cents    int
);
INSERT INTO orders_flat VALUES
 (1, 'Sara',  'sara@example.com',  'DE', 'Keyboard', 'hardware', 4500),
 (2, 'Sara',  'sara@example.com',  'DE', 'Mouse',    'hardware', 1900),
 (3, 'Sara',  'sara@example.com',  'DE', 'Keyboard', 'hardware', 4500),
 (4, 'Omid',  'omid@example.com',  'IR', 'Mouse',    'hardware', 1900);
```

سارا سفارش‌های ۱ تا ۳ و امید سفارش ۴ را دارد. همه‌چیز خوب به نظر می‌رسد تا وقتی که ببینید اسم و ایمیل و کشور سارا سه بار نوشته شده و قیمت Keyboard دو بار. هر واقعیتِ تکراری یک فرصت است برای اینکه نسخه‌ها با هم نخوانند. به مشکلاتی که از این می‌آید **anomaly** می‌گویند و سه نوع دارد.

**Update anomaly.** سارا ایمیلش را عوض می‌کند و کد فقط سفارش ۱ را آپدیت می‌کند:

```text
UPDATE orders_flat SET customer_email = 'sara@new.example' WHERE order_id = 1;

 order_id | customer_name |  customer_email  
----------+---------------+------------------
        1 | Sara          | sara@new.example
        2 | Sara          | sara@example.com
        3 | Sara          | sara@example.com

SELECT DISTINCT customer_email FROM orders_flat WHERE customer_name = 'Sara';
  customer_email  
------------------
 sara@example.com
 sara@new.example
```

نتیجه‌ی اول سه ردیف را نشان می‌دهد و دومی دو ایمیل متفاوت برای یک مشتری. کدام درست است؟ دیتابیس نمی‌تواند بگوید.

**Insert anomaly.** لنا ثبت‌نام کرده ولی هنوز سفارشی نداده. او را کجا ذخیره کنیم؟ هر ردیف این جدول یک سفارش است، پس تنها راه یک ردیف نیمه‌خالی است:

```text
INSERT INTO orders_flat (customer_name, customer_email, country) VALUES ('Lena', 'lena@example.com', 'SE');
 order_id | customer_name |  customer_email  | country | product_name | category | price_cents 
----------+---------------+------------------+---------+--------------+----------+-------------
          | Lena          | lena@example.com | SE      |              |          |            
```

همه‌ی ستون‌های سفارش و محصول NULL است. این یک سفارش جعلی است که حالا هر گزارشی باید یادش بماند ردش کند. (قبل از قدم بعد دوباره حذفش کردم.)

**Delete anomaly.** تنها سفارش امید لغو شده و حذفش می‌کنیم. بعد ردیف‌هایش را می‌شماریم:

```text
DELETE FROM orders_flat WHERE order_id = 4;
SELECT count(*) AS omid_rows FROM orders_flat WHERE customer_name = 'Omid';
 omid_rows 
-----------
         0
```

امید کاملاً از بین رفته: اسم و ایمیل و کشورش همراه سفارشش ناپدید شده‌اند.

ریشه‌ی هر سه یکی است: چند واقعیت متفاوت (درباره‌ی مشتری، محصول و سفارش) در یک جدول ذخیره شده‌اند و با هم زنده می‌مانند و با هم می‌میرند.

## نرمال‌سازی: هر واقعیت فقط یک جا

راه حل یک ایده‌ی ساده دارد. {{< term "normalization" "نرمال‌سازی" >}} یعنی جدول را آن‌قدر بشکنیم که هر واقعیت دقیقاً یک جا ذخیره شود. ایمیل سارا یک واقعیت است، پس باید یک سلول در یک ردیف باشد. بقیه با id به سارا اشاره می‌کنند.

این مرحله‌ها را «فرم‌های نرمال» می‌نامند. تعریف کتاب‌های درسی رسمی‌تر است؛ این هم خوانش عملی‌اش، با همین مثال:

- **فرم نرمال اول (1NF):** هر سلول یک مقدار دارد و هر ردیف قابل شناسایی است. «Keyboard, Mouse» در یک سلول نمی‌آید، چون نمی‌شود درست رویش جست‌وجو کرد، شمرد یا قید گذاشت.
- **فرم نرمال دوم (2NF):** وقتی ردیف با چند ستون با هم شناسایی می‌شود، هر ستون دیگر باید به همه‌ی آن‌ها وابسته باشد. یک خط سفارش با (سفارش، محصول) شناسایی می‌شود. نام محصول فقط به محصول وابسته است، نه به سفارش، پس به جدول `products` خودش می‌رود.
- **فرم نرمال سوم (3NF):** ستون‌ها باید درباره‌ی کلید ردیف باشند، نه درباره‌ی ستون دیگر. کشور مشتری درباره‌ی مشتری است، نه سفارش، پس به `customers` می‌رود.

نتیجه‌ی اعمال این‌ها روی `orders_flat` همان schema فروشگاهی است که می‌شناسیم. هر فلش یعنی «با id به آن اشاره می‌کند»:

```text
customers   (id, name, email, country, created_at)
products    (id, name, category, price_cents)
orders      (id, customer_id -> customers, status, created_at, total_cents)
order_items (order_id -> orders, product_id -> products, qty, price_cents)
```

حالا همان داستان‌ها را روی این جدول‌ها دوباره تعریف می‌کنیم. schema را ساختم، سارا و امید، یک کیبورد و دو سفارش برای سارا اضافه کردم و ایمیل او را یک بار عوض کردم:

```text
UPDATE customers SET email='sara@new.example' WHERE id=1;
 id |      email       
----+------------------
  1 | sara@new.example

SELECT c.name, count(o.id) AS orders FROM customers c LEFT JOIN orders o ON o.customer_id=c.id GROUP BY c.name ORDER BY c.name;
 name | orders 
------+--------
 Omid |      0
 Sara |      2
```

ایمیل سارا دقیقاً یک جا هست، پس چیزی نیست که با آن نخواند. امید به‌عنوان مشتری با ۰ سفارش وجود دارد (`LEFT JOIN` پست قبل او را نگه می‌دارد) و این insert anomaly را حل می‌کند. و حذف سفارش دیگر نمی‌تواند مشتری را حذف کند، چون ردیف‌های جدا در جدول‌های جدا هستند.

## کلیدها و foreign key

شکستن جدول وقتی کار می‌کند که تکه‌ها قابل‌اعتماد به هم وصل شوند، و این کار کلیدهاست. هر جدول این خط را دارد:

```sql
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

این یک {{< term "surrogate-key" "surrogate key" >}} (کلید جایگزین) است: عددی که دیتابیس می‌سازد، بدون معنای کسب‌وکاری، و هیچ‌وقت لازم نیست تغییر کند. ایمیل شبیه یک شناسه‌ی طبیعی است، ولی آدم‌ها ایمیلشان را عوض می‌کنند و شناسه‌ای که عوض شود باید در همه‌ی جدول‌هایی که به آن اشاره می‌کنند آپدیت شود. پس روی ایمیل `UNIQUE` می‌گذاریم و `id` چیزی است که جدول‌های دیگر به آن اشاره می‌کنند. `ALWAYS` باعث می‌شود PostgreSQL id دست‌نویس را رد کند. یکی را امتحان کردم و خطا این است (با `\set VERBOSITY verbose` که کد {{< term "sqlstate" "SQLSTATE" >}} را هم چاپ می‌کند):

```text
ERROR:  428C9: cannot insert a non-DEFAULT value into column "id"
DETAIL:  Column "id" is an identity column defined as GENERATED ALWAYS.
HINT:  Use OVERRIDING SYSTEM VALUE to override.
```

یک {{< term "foreign-key" "foreign key" >}} سفارش را به مشتری‌اش می‌بندد. وقتی مشتری‌ای را که هنوز سفارش دارد حذف کنید چه باید بشود؟ پیش‌فرض این است که رد شود:

```text
ERROR:  23503: update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

جایگزین `ON DELETE CASCADE` است: مشتری را حذف کنید و دیتابیس سفارش‌ها را هم حذف می‌کند. روی یک جدول موقت به اسم `orders_c` با دو سفارش برای مشتری ۲ امتحانش کردم. بعد از حذف مشتری ۲ هیچ سفارشی نماند و هیچ‌چیز هشدار نداد:

```text
SELECT count(*) AS orders_c_left FROM orders_c;
 orders_c_left 
---------------
             0
```

نظر خودم: برای هر چیزی که به پول مربوط است رفتار پیش‌فرض (رد کردن) را نگه دارید، چون حذف بی‌صدا فاجعه است، و `CASCADE` را فقط برای داده‌ی فرزندی بگذارید که تنهایی معنا ندارد.

## قیدهایی که باگ را می‌گیرند

وقتی جدول‌ها شکسته شدند، قاعده‌ها می‌توانند در خود schema زندگی کنند، جایی که هیچ مسیر کدی نمی‌تواند دورشان بزند. در اجرای من دیتابیس هر کدام از این‌ها را رد کرد:

- قیمت منفی (`CHECK (price_cents >= 0)`): کد `23514` و «Failing row contains (2, Bad, x, -5)»؛
- ایمیل تکراری (`UNIQUE`): کد `23505`؛
- سفارشی با `customer_id = 999` (foreign key): کد `23503`؛
- سفارشی با وضعیت `'lost'` (`CHECK`): کد `23514`.

یک {{< term "partial-index" "partial unique index" >}} (ایندکس یکتای جزئی) قاعده‌ای را بیان می‌کند که یک قید ساده نمی‌تواند: «هر مشتری حداکثر یک سفارش باز دارد». ایندکس یکتا معمولاً کل جدول را می‌پوشاند؛ با اضافه کردن `WHERE` فقط ردیف‌های منطبق را می‌پوشاند، پس فقط آن‌ها باید یکتا باشند:

```sql
CREATE UNIQUE INDEX one_open_order_per_customer
  ON orders (customer_id) WHERE status = 'new';
```

در دموی من مشتری ۱ از قبل یک سفارش `'new'` داشت (سفارش ۱)، پس هر دو سفارش `'new'` که سعی کردم درج کنم با خطای duplicate key رد شدند، و یک سفارش `'cancelled'` بدون مشکل درج شد:

```text
ERROR:  23505: duplicate key value violates unique constraint "one_open_order_per_customer"
DETAIL:  Key (customer_id)=(1) already exists.
```

(این خطا دو بار آمد، یک بار برای هر تلاش. درج `'cancelled'` خروجی `INSERT 0 1` داد.) `\d orders` بعد از آن ایندکس جدید را با شرطش نشان می‌دهد: `UNIQUE, btree (customer_id) WHERE status = 'new'::text`.

## نوع داده‌ها

schema فقط جدول و ستون نیست، مجموعه‌ای از انتخاب نوع هم هست، و چند تا از آن‌ها باگ واقعی می‌سازند.

**پول `float` نیست.** عددهای اعشاری شناور (floating-point) تقریب دودویی ذخیره می‌کنند و کسرهای ده‌دهی مثل ۰٫۱ را نمی‌شود دقیق ذخیره کرد:

```text
SELECT 0.1::float8 + 0.2::float8;        -> 0.30000000000000004   (equal to 0.3? f)
SELECT 0.1::numeric + 0.2::numeric;      -> 0.3                   (equal to 0.3? t)
sum of 0.1 a thousand times, float8      -> 99.9999999999986
sum of 0.1 a thousand times, numeric     -> 100.0
```

(این خلاصه‌ی فشرده‌ی نتیجه‌ی query‌های دمو است، یک خط برای هر query.) از `numeric` استفاده کنید، یا کاری را بکنید که schema فروشگاه می‌کند و سنت صحیح نگه دارید (`price_cents bigint`: جمع ۱۰ و ۲۰ دقیقاً ۳۰ است).

**`timestamp` یا `timestamptz`؟** `timestamp` یک عدد ساعت دیواری را بدون منطقه‌ی زمانی ذخیره می‌کند، مثل «ساعت ۱۰ روی دیوار». `timestamptz` یک لحظه‌ی دقیق را ذخیره می‌کند. همان مقدار را در هر دو ستون درج کردم و زیر دو منطقه‌ی زمانی نشست خواندم:

```text
Asia/Tehran:       a = 2026-11-23 10:00:00   b = 2026-11-23 13:30:00+03:30
America/New_York:  a = 2026-11-23 10:00:00   b = 2026-11-23 05:00:00-05
```

`a` (از نوع `timestamp`) در هر دو منطقه یکسان چاپ شد، پس معلوم نیست کدام لحظه را می‌گوید. `b` (از نوع `timestamptz`) به ساعت محلی هر منطقه تبدیل شد؛ همان یک لحظه است که دو جور نشان داده می‌شود. پیش‌فرض را `timestamptz` بگذارید.

**`text` یا `varchar(n)`؟** طبق مستندات PostgreSQL، `varchar(n)` مزیت کارایی ندارد (تنها فرق یک بررسی کوچک طول است). پس `text` بگذارید و اگر قاعده‌ی واقعی دارید، `CHECK` روی طول بزنید.

**Enum یا lookup table؟** نوع enum فشرده است، ولی وقتی مقدارها در داده استفاده شدند تغییرش دردسر دارد. lookup table، یعنی یک جدول کوچک از مقدارهای مجاز به‌علاوه‌ی یک foreign key، راحت گسترش می‌یابد و می‌تواند ستون اضافه مثل نام نمایشی داشته باشد. فروشگاه ما از `CHECK (status IN (...))` استفاده می‌کند که ساده‌ترین گزینه است ولی تغییرش migration می‌خواهد. وقتی مقدارها شروع به تغییر زیاد کنند من lookup table را انتخاب می‌کنم.

## کی denormalize کنیم و دام‌های دیگر

{{< term "denormalization" "Denormalization" >}} حرکت مقابل است: عمداً یک واقعیت را در چند جا ذخیره کردن. یک مبادله است، نه گناه، ولی با اندازه‌گیری انجامش بدهید، نه از سر عادت.

- فقط بعد از اندازه‌گیری denormalize کنید. موارد موجه به تجربه‌ی من: `total_cents` ذخیره‌شده روی `orders` که هماهنگش نگه می‌دارید، جدول‌های گزارش‌گیری و snapshot تاریخی مثل قیمت لحظه‌ی خرید (`order_items.price_cents`). مورد آخر اصلاً تکرار نیست: قیمت امروز محصول و قیمتی که مشتری پرداخته دو واقعیت متفاوت‌اند.
- foreign key خودش روی ستون ارجاع‌دهنده (`orders.customer_id`) ایندکس نمی‌سازد. بدون آن، join و حذف روی جدول والد می‌تواند کند شود؛ پست بعدی به آن می‌پردازد.
- `CASCADE` ممکن است خیلی بیشتر از انتظار شما حذف کند، چون زنجیره‌ی foreign keyها را دنبال می‌کند.
- نرمال‌سازی یعنی جدول و join بیشتر. این طبیعی است و بهای یک منبع حقیقت است.

## تمرین

خودتان `orders_flat` را با ستون `shipping_address` بسازید. آن را به جدول `addresses` نرمال کنید و یک `CHECK` بنویسید که نام خالی را ممنوع کند. بعد سعی کنید آدرسی را که یک سفارش استفاده می‌کند حذف کنید.

## قدم بعدی

[ایندکس B-tree و EXPLAIN ANALYZE](/fa/posts/db-indexes-btree-explain/). حالا داده شکل درستی دارد. وقتی حجمش زیاد شد، سؤال بعدی این است که PostgreSQL ردیف‌های لازم را چطور سریع پیدا می‌کند.
