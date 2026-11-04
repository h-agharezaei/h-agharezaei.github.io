+++
date = '2027-01-24T10:00:00+03:30'
draft = false
title = 'migration بدون downtime'
description = 'migration بدون downtime در PostgreSQL 18.3: کدام ALTER جدول را بازنویسی می‌کند، constraint با NOT VALID، CREATE INDEX CONCURRENTLY و expand/contract.'
contentType = 'engineering'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "migrations", "zero-downtime", "ddl"]
cover = { image = "/images/covers/db-zero-downtime-migrations.fa.png", alt = "migration بدون downtime", hiddenInSingle = true }
+++

یک deploy در روز شلوغ را تصور کنید. migration فقط یک خط است، `ALTER TABLE orders ADD COLUMN ...`، و روی لپ‌تاپ شما در چند میلی‌ثانیه رد شده. روی پروداکشن اجرا می‌شود و بعد کل سایت جواب نمی‌دهد. ایرادی در خود SQL نیست. آن دستور یک {{< term "lock" "قفل" >}} خیلی قوی روی جدول می‌خواست، تراکنش طولانیِ یک نفر دیگر از قبل قفل ضعیف‌تری را نگه داشته بود، و هر query که بعد از `ALTER` شما رسید پشت آن در صف ایستاد.

{{< term "migration" "migration" >}} یعنی تغییر در schema پایگاه داده (یک ستون جدید، یک ایندکس جدید، یک constraint جدید) که یک اسکریپت یا ابزار به ترتیب ثابت اجرایش می‌کند. روی جدول زنده خطر تقریباً هیچ‌وقت خود SQL نیست. دو چیز دیگر است: دستور کدام قفل را می‌گیرد و چه مدت نگهش می‌دارد. پس این پست تغییرهای رایج schema را یکی‌یکی و با خروجی واقعی دقیقاً از همین دو نظر بررسی می‌کند. پایه‌اش [قفل و deadlock](/fa/posts/db-locks-deadlocks/)، [MVCC](/fa/posts/db-mvcc-vacuum/)، [ایندکس](/fa/posts/db-indexes-btree-explain/) و [تراکنش](/fa/posts/db-transactions-acid/) است، و بعد از [JSONB و جست‌وجوی متنی](/fa/posts/db-jsonb-fulltext-search/) می‌آید که در آن ایندکس‌های نسبتاً بزرگ ساختیم بی‌آنکه به اثرشان روی sessionهای دیگر فکر کنیم.

> همه‌چیز روی PostgreSQL 18.3 واقعی اجرا شد (برای این نسخه‌ی پست دمو را دوباره اجرا کردم و خروجی زیر می‌خواند، جز یک عدد تصادفی که جایش را نشان می‌دهم). جدول یک کپی از جدول `orders` با ۲۰۰ هزار ردیف است به اسم `orders_m`. دو یا سه session را یک برنامه‌ی کوچک Go با ترتیب ثابت اجرا کرد، پس زمان‌بندی هر گام عمدی است. بعضی از این رفتارها به نسخه‌ی PostgreSQL بستگی دارند؛ من فقط 18.3 را اجرا کردم. زمان‌سنجی نشان نمی‌دهم چون به ماشین بستگی دارد. به‌جایش نشانه‌هایی را می‌خوانیم که عوض نمی‌شوند: جدول در کدام فایل است، کدام قفل گرفته شده، و آیا دستوری مسدود شد.

## سؤال اول: آیا دستور جدول را بازنویسی می‌کند؟

بعضی از دستورهای `ALTER TABLE` فقط توضیحِ جدول را در کاتالوگ سیستم عوض می‌کنند و این کار هر قدر هم جدول بزرگ باشد زمانی نمی‌برد. بعضی دیگر باید همه‌ی ردیف‌ها را بخوانند و دوباره در یک فایل جدید روی دیسک بنویسند. این نوع دوم {{< term "table-rewrite" "بازنویسی جدول" >}} است. در طول آن جدول قفل است، پس روی جدول بزرگ یعنی احتمالاً دقیقه‌ها downtime.

از کجا بفهمیم دستوری جدول را بازنویسی کرده؟ هر جدول در یک فایل زندگی می‌کند و `pg_relation_filenode()` شماره‌ی آن فایل را می‌دهد. اگر بعد از دستور شماره عوض شده باشد، جدول در فایل جدید کپی شده است. دمو هفت دستور را اجرا می‌کند و شماره را قبل و بعد از هرکدام مقایسه می‌کند:

```text
ADD COLUMN note text DEFAULT 'none' (constant)       same file (no rewrite)
ADD COLUMN tag varchar(10)                           same file (no rewrite)
ALTER tag TYPE varchar(20) (widen)                   same file (no rewrite)
ALTER tag TYPE text                                  same file (no rewrite)
ADD COLUMN seen_at timestamptz DEFAULT clock_timestamp() NEW file (table rewritten)
ALTER total_cents TYPE numeric(14,2)                 NEW file (table rewritten)
ALTER total_cents TYPE bigint (back)                 NEW file (table rewritten)
```

آن را در دو گروه بخوانید. در چهار خط اول فایل همان است. اضافه کردن ستون با default ثابت (`'none'`) آنی است: PostgreSQL مقدار default را یک بار در کاتالوگ نگه می‌دارد و به ۲۰۰ هزار ردیف دست نمی‌زند، با این حال همه‌ی ردیف‌ها بعدش `none` می‌خوانند (دمو ۱ مقدار متمایز شمرد). بزرگ‌تر کردن `varchar` یا تبدیلش به `text` هم اینجا بازنویسی نخواست.

سه خط آخر خطرناک‌اند. `clock_timestamp()` یک تابع *ناپایدار* (volatile) است: در هر بار صدا زدن مقدار دیگری برمی‌گرداند، پس PostgreSQL نمی‌تواند یک default ثابت نگه دارد و باید آن را برای هر ردیف حساب کند، یعنی همه‌ی ردیف‌ها را دوباره بنویسد. بعدش ردیف‌ها در این اجرا ۶۳٬۳۶۲ مقدار متمایز `seen_at` داشتند (در یک اجرای قبلی ۶۵٬۲۰۰ بود؛ به ساعت بستگی دارد و هر بار فرق می‌کند). تبدیل `bigint` به `numeric(14,2)` و برگشتش هم جدول را بازنویسی کرد، چون شکل ذخیره‌ی مقدارها عوض می‌شود. کوچک‌کردن `varchar` را امتحان نکردم، پس چیزی درباره‌اش نمی‌گویم.

یک واقعیت دیگر را هم در یک کپی موقت امتحان کردم: عوض کردن نام ستون و حذف ستون شماره‌ی فایل را تغییر ندادند، پس روی 18.3 هر دو فقط تغییر کاتالوگ‌اند. این جواب «آیا بازنویسی می‌کند؟» بود. سؤال بعدی درباره‌ی قفل است، و بیشتر دردسر واقعی همان‌جاست.

## اضافه کردن قاعده به جدول بزرگ: SET NOT NULL و CHECK ... NOT VALID

فرض کنید می‌خواهید روی ستونی از جدولی که از قبل داده دارد `NOT NULL` بگذارید. PostgreSQL باید ثابت کند هیچ ردیفی در آن ستون null ندارد، پس کل جدول را می‌خواند، و این کار را در حالی می‌کند که یک قفل قوی دارد. با `client_min_messages = debug1` خود سرور می‌گوید چه کرد. دمو `SET NOT NULL` را دو بار روی دو ستون مشابه اجرا می‌کند؛ بار دوم بعد از اینکه اول یک constraint از نوع `CHECK (col IS NOT NULL)` اضافه و validate شده:

```text
plain SET NOT NULL:
    verifying table "orders_m"
SET NOT NULL after a validated CHECK:
    existing constraints on column "orders_m.ref2" are sufficient to prove that it does not contain nulls
```

پیام اول می‌گوید سرور جدول را اسکن کرد («verifying table»). پیام دوم می‌گوید لازم نبود: یک `CHECK` که validate شده خودش ثابت می‌کند null وجود ندارد، پس اسکن را رد کرد. ترفند این است: `CHECK (col IS NOT NULL) NOT VALID` را اضافه کن، `VALIDATE CONSTRAINT` بزن، بعد `SET NOT NULL`، و آخر check را حذف کن.

اگر در نهایت همان مقدار بررسی انجام می‌شود، چرا بهتر است؟ جواب در قفل‌هاست. constraintی که با `NOT VALID` اضافه شود یعنی «از حالا برای ردیف‌های جدید و تغییرکرده اجرایش کن و ردیف‌های قدیمی را فعلاً نگاه نکن». `VALIDATE CONSTRAINT` گام جداگانه‌ای است که ردیف‌های قدیمی را اسکن می‌کند. برای دیدن قفل‌ها، دمو هر دستور را داخل یک تراکنش باز نگه می‌دارد و `pg_locks` را می‌خواند، در حالی که session دوم (B) با `lock_timeout = 300ms` یک `INSERT` می‌زند (یعنی اگر مجبور شود بیشتر از ۳۰۰ میلی‌ثانیه صبر کند، با خطا کنار می‌کشد):

```text
A plain ADD CONSTRAINT holds: orders_m:AccessExclusiveLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
A ... NOT VALID holds: orders_m:AccessExclusiveLock
INSERT total_cents=-1 while the constraint is NOT VALID: ERROR: new row for relation "orders_m" violates check constraint "t_pos" (SQLSTATE 23514)
A VALIDATE holds: orders_m:ShareUpdateExclusiveLock
B INSERT meanwhile: ok
```

خط به خط:

1. `ADD CONSTRAINT ... CHECK` معمولی `AccessExclusiveLock` می‌گیرد، قوی‌ترین قفل جدول. insert جلسه‌ی B راه پیدا نکرد و timeout شد. روی جدول واقعی این همان مدتی است که کل جدول اسکن می‌شود.
2. `NOT VALID` هم `AccessExclusiveLock` می‌گیرد، ولی چیزی برای اسکن نیست، پس فقط برای یک لحظه‌ی تغییر کاتالوگ نگهش می‌دارد. (دمو خودِ قفل را نشان می‌دهد، نه مدتش را.)
3. با اینکه ردیف‌های قدیمی چک نشده‌اند، constraint همین حالا کار می‌کند: insert ردیفی با `total_cents = -1` با خطای نقض check (کد ۲۳۵۱۴) رد شد.
4. `VALIDATE` اسکن طولانی را انجام می‌دهد ولی زیر `ShareUpdateExclusiveLock`، قفلی خیلی ضعیف‌تر، و insert جلسه‌ی B انجام شد (`ok`). تا وقتی ردیف‌های قدیمی چک می‌شوند، نوشتن ادامه دارد.

کل ایده‌ی این بخش همین است: یک گام طولانیِ مسدودکننده را به یک گام مسدودکننده‌ی آنی و یک گام طولانی که جلوی نویسنده‌ها را نمی‌گیرد تقسیم کن.

## ایندکس: CREATE INDEX در برابر CONCURRENTLY

`CREATE INDEX` معمولی تا وقتی ایندکس ساخته می‌شود جلوی نوشتن در جدول را می‌گیرد. {{< term "create-index-concurrently" "CREATE INDEX CONCURRENTLY" >}} برای این ساخته شده که نگیرد، ولی هزینه دارد: چند بار روی جدول می‌گذرد و باید منتظر تمام شدن تراکنش‌های قدیمی‌تر بماند. برای دیدن هر دو، در A تراکنشی با `CREATE INDEX` معمولی باز کردم و از B درج کردم. بعد ساخت concurrent را اجرا کردم، در حالی که session C یک تراکنش نویسنده‌ی قدیمی را باز نگه داشته بود، و دوباره از B درج کردم وقتی ساخت منتظر C بود:

```text
A CREATE INDEX (open tx) holds: orders_m:ShareLock
B INSERT meanwhile: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
CIC waiting; its table lock: ShareUpdateExclusiveLock
B INSERT meanwhile: ok
CIC result: ok
```

ساخت معمولی `ShareLock` نگه می‌دارد که با نوشتن تداخل دارد، پس insert جلسه‌ی B timeout شد. ساخت concurrent حتی وقتی منتظر C بود فقط `ShareUpdateExclusiveLock` داشت، insert جلسه‌ی B کار کرد، و وقتی C commit کرد ساخت تمام شد (`CIC result: ok`). بهای نسخه‌ی concurrent این است که منتظر همه‌ی تراکنش‌هایی می‌ماند که از قبل باز بوده‌اند، پس یک تراکنش فراموش‌شده آن را مدت زیادی منتظر نگه می‌دارد.

بهای دیگرش این است که ساخت concurrent می‌تواند وسط کار شکست بخورد. برای اجبار این اتفاق، خواستم روی `customer_id`، که یکتا نیست، یک ایندکس unique بسازم:

```text
CREATE UNIQUE ... CONCURRENTLY: ERROR: could not create unique index "orders_m_cust_u" (SQLSTATE 23505)
   orders_m_cust      indisvalid=true indisready=true
   orders_m_cust_u    indisvalid=false indisready=false
DROP INDEX CONCURRENTLY orders_m_cust_u: ok
invalid indexes left: 0
```

ساخت با خطای کلید تکراری شکست خورد، ولی بعد از خودش تمیز نکرد. ایندکس نیمه‌ساخته‌ی `orders_m_cust_u` هنوز در کاتالوگ است، با `indisvalid = false` و `indisready = false`: planner هرگز از آن استفاده نمی‌کند و فقط شلوغی‌ای است که نفر بعدی را که schema را می‌خواند گیج می‌کند. (ایندکس دیگر، `orders_m_cust`، همان ایندکس سالم گام قبل است.) راه‌حل این است که حذفش کنی، با `DROP INDEX CONCURRENTLY` تا حذف هم جلوی کسی را نگیرد، و دوباره بسازی. خط آخر تأیید می‌کند هیچ ایندکس نامعتبری نمانده.

## از بقیه محافظت کن: lock_timeout و تلاش دوباره

حالا به ماجرای اول پست برگردیم. حتی یک `ALTER TABLE` خیلی سریع هم `AccessExclusiveLock` می‌خواهد. اگر تراکنشی به جدول دست زده و تمام نشده باشد، `ALTER` منتظرش می‌ماند. و تا وقتی منتظر است، هر query جدید روی آن جدول پشت `ALTER` در صف می‌ایستد، چون PostgreSQL اجازه نمی‌دهد تازه‌رسیده‌ها از جلوی یک قفل قویِ منتظر رد شوند. این‌طور است که یک تراکنش فراموش‌شده به‌علاوه‌ی یک migration یک سایت را می‌خواباند.

محافظت {{< term "lock-timeout" "lock_timeout" >}} است: آن را روی session مربوط به DDL بگذار، و اگر قفل به‌موقع گرفته نشد دستور کنار می‌کشد و صفِ پشتش دوباره راه می‌افتد. بعد فقط در یک حلقه دوباره تلاش می‌کنی. در دمو session C یک تراکنش باز کرد و جدول را خواند، و A (با `lock_timeout = 200ms`) چهار بار سعی کرد ستون اضافه کند. قبل از تلاش چهارم C را commit کردم:

```text
attempt 1: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 2: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 3: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
attempt 4: ok
```

هر تلاش ناموفق فقط ۲۰۰ میلی‌ثانیه انتظار خرج داشت و بیشتر نه، پس کسی مدت زیادی گیر نیفتاد، و وقتی C رفت migration در تلاش بعدی رد شد.

برای دیدن خود صف، همین را بدون `lock_timeout` روی `ALTER` (که هر قدر لازم باشد منتظر می‌ماند) تکرار کردم و از B با timeout ۳۰۰ میلی‌ثانیه‌ی خودش یک `SELECT` ساده زدم:

```text
plain SELECT while ALTER waits in the queue: ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

یک خواندن ساده حتی شروع نشد. `SELECT` با C تداخلی ندارد، ولی با `ALTER`ای که جلویش منتظر است تداخل دارد. (بعد از commit جلسه‌ی C، `ALTER` تمام شد: دمو `ALTER finished: ok` چاپ کرد.)

## عوض کردن امن نام ستون: expand/contract

حالت سخت‌تر: می‌خواهید `total_cents` را به `amount_cents` تغییر نام دهید. خودِ `RENAME` فقط تغییر کاتالوگ است (بالا چک کردم)، ولی همان لحظه هر نسخه‌ی در حال اجرای برنامه که هنوز اسم قدیمی را به کار می‌برد شروع به خطا دادن می‌کند. تنها راه این است که هیچ‌وقت کد در حال اجرا را نشکنی. روش {{< term "expand-contract" "expand/contract" >}} این را با سازگار نگه داشتن هر گام هم با کد قدیمی و هم با کد جدید انجام می‌دهد. قفل‌های زیر همان‌هایی‌اند که در هر گام از `pg_locks` خواندم:

1. **Expand: ستون جدید را اضافه کن**، nullable. `AccessExclusiveLock` می‌گیرد، ولی فقط تغییر کاتالوگ است و کوتاه می‌ماند.
2. **با یک {{< term "trigger" "trigger" >}} همگامش نگه دار**: تابعی که PostgreSQL خودکار در هر insert و update اجرا می‌کند و اینجا `total_cents` را در `amount_cents` کپی می‌کند (برای ساختنش `ShareRowExclusiveLock`). چک کردم: ردیف جدیدی که با `total_cents = 777` درج شد با `amount_cents = 777` درآمد.
3. **ردیف‌های قدیمی را دسته‌دسته {{< term "backfill" "backfill" >}} کن.** یک `UPDATE` روی کل جدول یک تراکنش غول‌آسا می‌شود که همه‌ی قفل‌های ردیفش را تا آخر نگه می‌دارد، پس آن را با بازه‌های id انجام دادم (`RowExclusiveLock`؛ نوشتن عادی ادامه دارد):

```text
   batch 1: ids (0, 50000] -> 50000 rows
   batch 2: ids (50000, 100000] -> 50000 rows
   batch 3: ids (100000, 150000] -> 50000 rows
   batch 4: ids (150000, 200000] -> 50000 rows
   tail (rows above the range): 2 rows
rows still NULL: 0  mismatches: 0
```

   چهار دسته‌ی ۵۰ هزارتایی همان ۲۰۰ هزار ردیف اصلی را پوشش می‌دهند. «tail» همان ۲ ردیفی است که session B زودتر در دمو درج کرده بود (idهای ۹۰۰۰۰۲ و ۹۰۰۰۰۵، پیش از ساخته شدن trigger)، پس بالاتر از بازه‌های id بودند و هنوز `amount_cents` نداشتند. در پایان هیچ ردیفی `amount_cents` تهی ندارد و هیچ‌کدام با `total_cents` فرق ندارد.
4. **اجبارش کن** با ترفند بالا: `CHECK ... NOT VALID`، `VALIDATE`، `SET NOT NULL` (این بار بدون اسکن)، و حذف check.
5. **برنامه را deploy کن** تا `amount_cents` را بخواند و بنویسد (دمو این را انجام نمی‌دهد؛ فقط گامی در ترتیب کار است).
6. **Contract: trigger و ستون قدیمی را حذف کن.** `AccessExclusiveLock` کوتاه؛ همان چک موقت قبلی نشان داد حذف ستون جدول را بازنویسی نمی‌کند.

در هر لحظه‌ی بین گام‌ها هم کد قدیمی کار می‌کند هم کد جدید. کل هدف این روش همین است، و بهایش این است که یک تغییر نام می‌شود شش گام و معمولاً دست‌کم دو deploy.

## قاعده‌هایی که برای DDL در پروداکشن به کار می‌برم

- **روی هر DDL `lock_timeout` و حلقه‌ی تلاش دوباره بگذار.** migrationی که بی‌صدا منتظر می‌ماند migrationی است که جلوی بقیه را می‌گیرد.
- **درباره‌ی هر دستور دو سؤال بپرس:** آیا جدول را بازنویسی می‌کند، و کدام قفل را برای چه مدت می‌گیرد. `pg_relation_filenode()` جواب اولی را می‌دهد و `pg_locks` دومی را.
- **`CREATE INDEX CONCURRENTLY` داخل بلوک تراکنش اجرا نمی‌شود.** خیلی از ابزارهای migration به‌طور پیش‌فرض هر فایل را در یک تراکنش اجرا می‌کنند، پس ببین ابزارت راهی برای خاموش کردنش برای چنین فایلی دارد. و بعدش دنبال ایندکس‌های `INVALID` بگرد.
- **اینکه کدام تغییر نوع بازنویسی نمی‌خواهد به نسخه بستگی دارد.** قبل از اعتماد به فهرستی از اینترنت، از جمله همین فهرست، روی نسخه‌ی خودت با `pg_relation_filenode()` امتحان کن.
- **ابزار migration دستوری را امن نمی‌کند.** ابزارهایی مثل goose و Flyway فقط فایل‌ها را به ترتیب اجرا می‌کنند؛ امنیت در چیزی است که داخل فایل‌ها می‌نویسی.

## قدم بعدی

قدم بعدی [partitioning جدول‌ها](/fa/posts/db-partitioning/) است: وقتی جدول آن‌قدر بزرگ می‌شود که یک تکه دیدنش سخت است، آن را به چند بخش تقسیم می‌کنی تا planner بتواند بخش‌هایی را که query لازم ندارد رد کند.
