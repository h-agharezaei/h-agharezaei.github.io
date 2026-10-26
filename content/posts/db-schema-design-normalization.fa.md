+++
date = '2026-11-23T10:00:00+03:30'
draft = false
title = 'طراحی schema و نرمال‌سازی'
description = 'طراحی schema و نرمال‌سازی در PostgreSQL: anomalyهای update، insert و delete را روی یک جدول تخت ببینید و با کلید، قید و نوع داده درستشان کنید.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "schema-design", "normalization"]
cover = { image = "/images/covers/db-schema-design-normalization.fa.png", alt = "طراحی schema و نرمال‌سازی", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-relational-sql-essentials/) مدل رابطه‌ای و SQL لازم برای کوئری زدن را یاد گرفتیم. حالا سؤالی که پیش از هر کوئری می‌آید: جدول‌ها چه شکلی باشند؟ schema بد سال‌ها آزار می‌دهد. اینجا عمداً با یک جدول بد شروع می‌کنم، خراب شدنش را می‌بینیم و قدم‌به‌قدم درستش می‌کنیم.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی و با schema فروشگاهی همین سری اجرا شده است.

## یک جدول تخت و سه anomaly

جدول `orders_flat` به‌ازای هر سفارش یک ردیف دارد و مشخصات مشتری و محصول روی هر ردیف تکرار شده (۴ ردیف: سارا سفارش‌های ۱ تا ۳ و امید سفارش ۴ را دارد).

**Update anomaly.** سارا ایمیلش را عوض می‌کند. من فقط سفارش ۱ را آپدیت می‌کنم:

```text
 order_id | customer_name |  customer_email
----------+---------------+------------------
        1 | Sara          | sara@new.example
        2 | Sara          | sara@example.com
        3 | Sara          | sara@example.com
```

کدام درست است؟ دیتابیس نمی‌تواند بگوید.

**Insert anomaly.** لنا ثبت‌نام کرده ولی هنوز سفارشی نداده. تنها راه ذخیره‌اش یک ردیف نیمه‌خالی با NULL در همه‌ی ستون‌های سفارش و محصول است، یعنی یک سفارش جعلی.

**Delete anomaly.** تنها سفارش امید لغو شده و من حذفش می‌کنم. تعداد ردیف‌های او بعد از آن: `omid_rows = 0`. مشتری را هم از دست دادیم.

ریشه‌ی هر سه یکی است: چند واقعیت متفاوت (مشتری، محصول، سفارش) در یک جدول مخلوط شده‌اند.

## نرمال‌سازی به زبان ساده

{{< term "normalization" "نرمال‌سازی" >}} یعنی هر واقعیت فقط در یک جا باشد. سه مرحله، مطابق همین مثال:

- **1NF**: هر سلول یک مقدار دارد و ردیف‌ها قابل شناسایی‌اند. مثلاً «keyboard, mouse» در یک سلول نمی‌آید.
- **2NF**: هر ستون به کل کلید وابسته است. در یک خط سفارش با کلید (سفارش، محصول)، نام محصول فقط به محصول وابسته است و به `products` می‌رود.
- **3NF**: ستون‌ها به کلید وابسته‌اند، نه به ستون‌های دیگر. کشور مشتری به مشتری وابسته است نه به سفارش و به `customers` می‌رود.

نتیجه همان schema فروشگاه است: `customers`، `products`، `orders`، `order_items`. حالا ایمیل سارا یک ردیف است، لنا بدون سفارش وجود دارد (با `LEFT JOIN` بررسی کردم: امید ۰ سفارش دارد) و حذف سفارش هرگز مشتری را حذف نمی‌کند.

## کلیدها و foreign key

```sql
id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
```

این یک {{< term "surrogate-key" "surrogate key" >}} است: عددی بدون معنای کسب‌وکاری که هرگز تغییر نمی‌کند. ایمیل یک natural key است که ممکن است عوض شود، پس روی آن `UNIQUE` می‌گذاریم. `ALWAYS` باعث می‌شود PostgreSQL id دستی را رد کند:

```text
ERROR:  cannot insert a non-DEFAULT value into column "id"
DETAIL:  Column "id" is an identity column defined as GENERATED ALWAYS.
```

یک {{< term "foreign-key" "foreign key" >}} سفارش را به مشتری وصل می‌کند. با رفتار پیش‌فرض، حذف مشتری‌ای که هنوز سفارش دارد رد می‌شود:

```text
ERROR:  update or delete on table "customers" violates foreign key constraint "orders_customer_id_fkey" on table "orders"
DETAIL:  Key (id)=(1) is still referenced from table "orders".
```

با `ON DELETE CASCADE` (روی جدول موقت `orders_c` امتحان کردم) حذف مشتری ۲ بی‌صدا هر دو سفارشش را پاک کرد: `orders_c_left = 0`. نظر خودم: برای داده‌های مالی رفتار پیش‌فرض (رد کردن) و CASCADE فقط برای داده‌ی فرزندی که تنهایی معنا ندارد.

## قیدهایی که باگ را می‌گیرند

در اجرای من دیتابیس همه‌ی اینها را رد کرد: قیمت منفی (`CHECK`)، ایمیل تکراری (`UNIQUE`)، `customer_id = 999` (foreign key) و وضعیت `'lost'` (`CHECK`).

یک {{< term "partial-index" "partial unique index" >}} قاعده‌ی «هر مشتری یک سفارش باز» را بیان می‌کند:

```sql
CREATE UNIQUE INDEX one_open_order_per_customer
  ON orders (customer_id) WHERE status = 'new';
```

سفارش `'new'` دوم برای همان مشتری با خطای duplicate key رد شد، ولی سفارش `'cancelled'` بدون مشکل ثبت شد.

## نوع داده‌ها

پول `float` نیست:

```text
SELECT 0.1::float8 + 0.2::float8;        -> 0.30000000000000004   (equal to 0.3? f)
SELECT 0.1::numeric + 0.2::numeric;      -> 0.3                   (equal to 0.3? t)
sum of 0.1 a thousand times, float8      -> 99.9999999999986
sum of 0.1 a thousand times, numeric     -> 100.0
```

از `numeric` استفاده کنید یا مثل schema فروشگاه از سنت صحیح (`price_cents bigint`: جمع ۱۰ و ۲۰ دقیقاً ۳۰ است).

`timestamp` یک ساعت دیواری بدون منطقه‌ی زمانی ذخیره می‌کند و `timestamptz` یک لحظه را. همان مقدار را درج کردم و زیر دو time zone نشست خواندم:

```text
Asia/Tehran:       a = 2026-11-23 10:00:00   b = 2026-11-23 13:30:00+03:30
America/New_York:  a = 2026-11-23 10:00:00   b = 2026-11-23 05:00:00-05
```

مقدار `a` هرگز تغییر نکرد، پس معلوم نیست کدام لحظه است. پیش‌فرض را `timestamptz` بگذارید.

`text` یا `varchar(n)`؟ طبق مستندات PostgreSQL `varchar(n)` مزیت کارایی ندارد، پس `text` بگذارید و اگر قاعده‌ی واقعی دارید `CHECK` روی طول بزنید.

Enum یا lookup table؟ نوع enum فشرده است ولی تغییرش دردسر دارد. lookup table با foreign key راحت گسترش می‌یابد و می‌تواند ستون اضافه داشته باشد. فروشگاه ما از `CHECK (status IN (...))` استفاده می‌کند که ساده است ولی تغییرش migration می‌خواهد. وقتی مقادیر زیاد عوض می‌شوند من lookup table را انتخاب می‌کنم.

## چند نکته‌ی مهم

- فقط بعد از اندازه‌گیری denormalize کنید. موارد موجه به تجربه‌ی من: `total_cents` ذخیره‌شده روی `orders` که هماهنگش نگه می‌دارید، جدول‌های گزارش‌گیری و snapshot تاریخی مثل قیمت لحظه‌ی خرید (`order_items.price_cents`).
- foreign key خودش روی ستون ارجاع‌دهنده ایندکس نمی‌سازد؛ این موضوع پست بعدی است.
- `CASCADE` ممکن است خیلی بیشتر از انتظار شما حذف کند.

## تمرین

خودتان `orders_flat` را با ستون `shipping_address` بسازید. آن را به جدول `addresses` نرمال کنید و یک `CHECK` بنویسید که نام خالی را ممنوع کند. بعد سعی کنید آدرسی را که یک سفارش استفاده می‌کند حذف کنید.

## قدم بعدی

پست بعدی «ایندکس B-tree و EXPLAIN ANALYZE» است: اینکه PostgreSQL چطور ردیف‌ها را سریع پیدا می‌کند و چطور plan آن را بخوانیم.
