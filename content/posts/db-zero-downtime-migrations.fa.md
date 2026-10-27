+++
date = '2027-01-24T10:00:00+03:30'
draft = false
title = 'migration بدون downtime'
description = 'migration بدون downtime در PostgreSQL 18.3: کدام ALTER جدول را بازنویسی می‌کند، constraint با NOT VALID، CREATE INDEX CONCURRENTLY و expand/contract.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "migrations", "zero-downtime", "ddl"]
cover = { image = "/images/covers/db-zero-downtime-migrations.fa.png", alt = "migration بدون downtime", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-jsonb-fulltext-search/) روی یک جدول ایندکس JSONB و جست‌وجو ساختیم. روی لپ‌تاپ این کار مجانی است؛ اما روی جدولِ زنده‌ای که ترافیک دارد، همین {{< term "migration" "migration" >}} می‌تواند برنامه را بخواباند. هزینه معمولاً خود SQL نیست، [قفل](/fa/posts/db-locks-deadlocks/)هایی است که می‌گیرد و مدتی که نگه‌شان می‌دارد. این پست دستور به دستور بررسی می‌کند چه چیزی امن است. پایه‌اش [MVCC](/fa/posts/db-mvcc-vacuum/)، [ایندکس](/fa/posts/db-indexes-btree-explain/) و [تراکنش](/fa/posts/db-transactions-acid/) است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی و روی یک کپی از جدول `orders` با ۲۰۰ هزار ردیف (`orders_m`) اجرا شد. دو یا سه session را یک برنامه‌ی کوچک Go با ترتیب ثابت اجرا کرد. بعضی از این رفتارها به نسخه بستگی دارند؛ من فقط 18.3 را اجرا کردم. زمان‌سنجی نیست چون ماشین مشغول بود؛ به‌جایش نشانه‌های قطعی را می‌خوانیم.

## آیا جدول بازنویسی می‌شود؟

{{< term "table-rewrite" "بازنویسی جدول" >}} نوع خطرناک است. `pg_relation_filenode()` نشان می‌دهد: اگر عدد عوض شود، جدول در فایل جدید کپی شده است.

```text
ADD COLUMN note text DEFAULT 'none' (constant)       same file (no rewrite)
ADD COLUMN tag varchar(10)                           same file (no rewrite)
ALTER tag TYPE varchar(20) (widen)                   same file (no rewrite)
ALTER tag TYPE text                                  same file (no rewrite)
ADD COLUMN seen_at timestamptz DEFAULT clock_timestamp() NEW file (table rewritten)
ALTER total_cents TYPE numeric(14,2)                 NEW file (table rewritten)
ALTER total_cents TYPE bigint (back)                 NEW file (table rewritten)
```

default ثابت آنی است و بعدش هر ۲۰۰ هزار ردیف مقدار `none` را می‌دهند (۱ مقدار متمایز). default ناپایدار (volatile) باید برای هر ردیف حساب شود، پس جدول را بازنویسی می‌کند؛ بعدش ردیف‌ها ۶۵۲۰۰ مقدار متمایز `seen_at` داشتند (این عدد در هر اجرا فرق می‌کند). بزرگ‌تر کردن `varchar` یا تبدیلش به `text` اینجا بازنویسی نخواست، ولی `bigint` به `numeric` خواست. کوچک‌کردن `varchar` را امتحان نکردم.

## SET NOT NULL و CHECK ... NOT VALID

`SET NOT NULL` معمولاً کل جدول را زیر قفل سنگین اسکن می‌کند. با `client_min_messages = debug1` خود سرور می‌گوید چه کرد:

```text
plain SET NOT NULL:
    verifying table "orders_m"
SET NOT NULL after a validated CHECK:
    existing constraints on column "orders_m.ref2" are sufficient to prove that it does not contain nulls
```

پس ترفند این است: `CHECK (col IS NOT NULL) NOT VALID` را اضافه کن، `VALIDATE CONSTRAINT` بزن، بعد `SET NOT NULL` (اسکن را رد می‌کند) و در آخر check را حذف کن. دلیلش در قفل‌هاست. هر دستور را داخل تراکنش باز نگه داشتم و `pg_locks` را خواندم، در حالی که session B با `lock_timeout = 300ms` یک `INSERT` می‌زد:

```text
A plain ADD CONSTRAINT holds: orders_m:AccessExclusiveLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
A ... NOT VALID holds: orders_m:AccessExclusiveLock
INSERT total_cents=-1 while the constraint is NOT VALID: ERROR: new row for relation "orders_m" violates check constraint "t_pos" (SQLSTATE 23514)
A VALIDATE holds: orders_m:ShareUpdateExclusiveLock
B INSERT meanwhile: ok
```

`NOT VALID` قفل سنگین را فقط برای یک لحظه‌ی تغییر کاتالوگ می‌گیرد (اسکنی در کار نیست) و ردیف‌های جدید را از همان لحظه چک می‌کند. `VALIDATE` اسکن طولانی را زیر `ShareUpdateExclusiveLock` انجام می‌دهد که نوشتن را رد می‌کند.

## ایندکس

`CREATE INDEX` جلوی نوشتن را می‌گیرد. {{< term "create-index-concurrently" "CREATE INDEX CONCURRENTLY" >}} نمی‌گیرد، ولی منتظر تراکنش‌های قدیمی‌تر می‌ماند؛ پس در session C یک نویسنده را باز نگه داشتم و در حالی که ساخت منتظر بود از B درج کردم:

```text
A CREATE INDEX (open tx) holds: orders_m:ShareLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
CIC waiting; its table lock: ShareUpdateExclusiveLock
B INSERT meanwhile: ok
CIC result: ok
```

ساخت concurrent می‌تواند وسط کار شکست بخورد. با یک ایندکس unique روی ستون غیریکتا شکست را اجبار کردم:

```text
CREATE UNIQUE ... CONCURRENTLY: ERROR: could not create unique index "orders_m_cust_u" (SQLSTATE 23505)
   orders_m_cust      indisvalid=true indisready=true
   orders_m_cust_u    indisvalid=false indisready=false
DROP INDEX CONCURRENTLY orders_m_cust_u: ok
invalid indexes left: 0
```

ایندکس شکست‌خورده با `indisvalid = false` می‌ماند. حذفش کن و دوباره بساز.

## lock_timeout و تلاش دوباره

حتی یک `ALTER TABLE` سریع هم `AccessExclusiveLock` می‌خواهد و پشت هر خواننده‌ی طولانی در صف می‌ایستد. بدتر اینکه همه‌ی دستورهای بعدی هم پشتش صف می‌بندند. روی DDL مقدار {{< term "lock-timeout" "lock_timeout" >}} بگذار و دوباره تلاش کن. session C یک تراکنش خواندن را باز نگه داشته بود:

```text
attempt 1: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 2: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 3: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 4: ok
plain SELECT while ALTER waits in the queue: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

قبل از تلاش چهارم C را آزاد کردم. خط آخر، وقتی `ALTER` بدون `lock_timeout` بود، صف را نشان می‌دهد: تا وقتی `ALTER` منتظر بود، یک `SELECT` ساده هم نتوانست شروع شود.

## Expand/contract

برای تغییر نام `total_cents` به `amount_cents` تا وقتی کد قدیمی اجراست هرگز `RENAME` نزن. از روش {{< term "expand-contract" "expand/contract" >}} استفاده کن؛ قفل‌ها از `pg_locks` آمده‌اند:

1. ستون جدید nullable را اضافه کن (`AccessExclusiveLock`، ولی فقط metadata).
2. یک {{< term "trigger" "trigger" >}} بگذار که مقدار را در insert و update کپی کند (`ShareRowExclusiveLock`). ردیف جدیدی با `total_cents = 777` مقدار `amount_cents = 777` گرفت.
3. {{< term "backfill" "backfill" >}} را دسته‌دسته انجام بده (`RowExclusiveLock`، نوشتن ادامه دارد):

```text
   batch 1: ids (0, 50000] -> 50000 rows
   batch 2: ids (50000, 100000] -> 50000 rows
   batch 3: ids (100000, 150000] -> 50000 rows
   batch 4: ids (150000, 200000] -> 50000 rows
   tail (rows above the range): 2 rows
rows still NULL: 0  mismatches: 0
```

4. اجبارش کن: `CHECK ... NOT VALID`، `VALIDATE` و `SET NOT NULL` (بدون اسکن، مثل بالا).
5. برنامه را طوری deploy کن که `amount_cents` را بخواند و بنویسد.
6. Contract: trigger و `total_cents` را حذف کن (`AccessExclusiveLock` کوتاه؛ طبق مستندات حذف ستون جدول را بازنویسی نمی‌کند، ولی فایل را بررسی نکردم).

بین گام‌ها هم کد قدیمی کار می‌کند هم جدید.

## چند نکته‌ی مهم

- `RENAME COLUMN` تغییر metadata است (طبق مستندات؛ اجرایش نکردم) ولی کد در حال اجرا را می‌شکند؛ روش بالا برای سازگاری است، نه سرعت.
- روی هر DDL در پروداکشن `lock_timeout` و حلقه‌ی تلاش دوباره بگذار.
- `CREATE INDEX CONCURRENTLY` داخل بلوک تراکنش اجرا نمی‌شود؛ بعدش ایندکس‌های INVALID را بررسی کن.
- اینکه کدام تغییر نوع بازنویسی نمی‌خواهد به نسخه بستگی دارد: روی نسخه‌ی خودت با `pg_relation_filenode()` امتحان کن.
- ابزارهای migration (مثل goose و Flyway) فقط فایل‌ها را به ترتیب اجرا می‌کنند؛ دستوری را امن نمی‌کنند.

## تمرین

یک جدول را کپی کن و برنامه‌ی «`status` را `NOT NULL` کن و یک foreign key اضافه کن» را بدون قفل سنگین طولانی بچین. برای هر دستور قفل را پیش‌بینی کن و با `pg_locks` تأیید کن.

## قدم بعدی

پست بعدی «partitioning جدول‌ها» است: تقسیم یک جدول عظیم به تکه‌هایی که planner می‌تواند از بعضی‌شان رد شود.
