+++
date = '2027-01-04T10:00:00+03:30'
draft = false
title = 'قفل و deadlock در دیتابیس'
description = 'قفل و deadlock در PostgreSQL با اجرای واقعی دو session: قفل ردیف، pg_locks، lock_timeout، یک deadlock واقعی و راه‌حلش، صف SKIP LOCKED و ALTER TABLE.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "locks", "deadlock", "concurrency"]
cover = { image = "/images/covers/db-locks-deadlocks.fa.png", alt = "قفل و deadlock در دیتابیس", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-mvcc-vacuum/) {{< term "mvcc" "MVCC" >}} اجازه داد خواننده‌ها و نویسنده‌ها از کنار هم رد شوند. دو نویسنده روی یک ردیف نمی‌توانند: دومی باید صبر کند. این انتظار یک {{< term "lock" "قفل" >}} است و بیشتر ماجراهای «دیتابیس گیر کرده» قفلی است که کسی آزادش نکرده. این پست عمداً session‌ها را گیر می‌اندازد، نشان می‌دهد چه کسی جلوی چه کسی را گرفته و با تله‌های کلاسیک تمام می‌شود. پایه‌اش [تراکنش و ACID](/fa/posts/db-transactions-acid/) و [سطح‌های ایزولاسیون](/fa/posts/db-isolation-levels-anomalies/) است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی اجرا شد. دو یا سه session را یک برنامه‌ی کوچک Go با ترتیب ثابت اجرا کرد، پس هر نتیجه قطعی است. ماشین مشغول بود، پس زمان‌سنجی نیست.

## قفل ردیف

session A روی جدول کوچک `acct` دستور `SELECT ... WHERE id = 1 FOR UPDATE` را می‌زند و تراکنش را باز نگه می‌دارد. بعد B تلاش می‌کند:

```text
B: UPDATE row 1       -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
B: FOR UPDATE NOWAIT  -> ERROR: could not obtain lock on row in relation "acct" (SQLSTATE 55P03)
B: SKIP LOCKED ids    -> [2 3]
```

به‌طور پیش‌فرض B تا ابد صبر می‌کرد؛ من `lock_timeout = 300ms` گذاشتم تا منصرف شود. `NOWAIT` فوری خطا می‌دهد و `SKIP LOCKED` فقط ردیف‌هایی را برمی‌گرداند که کسی نگرفته. کدام حالت‌های قفل با هم تداخل دارند؟ A یک حالت را نگه می‌دارد و B با `NOWAIT` می‌خواهد:

```text
A holds \ B asks    FOR KEY SHARE      FOR SHARE          FOR NO KEY UPDATE  FOR UPDATE
FOR KEY SHARE       ok                 ok                 ok                 blocked
FOR SHARE           ok                 ok                 blocked            blocked
FOR NO KEY UPDATE   ok                 blocked            blocked            blocked
FOR UPDATE          blocked            blocked            blocked            blocked
```

`FOR NO KEY UPDATE` همان چیزی است که یک `UPDATE` ساده‌ی بدون دست زدن به ستون‌های کلید می‌گیرد. بررسی foreign key را هنوز رد می‌کند: وقتی آن را نگه داشتم `INSERT INTO note (acct_id) VALUES (1)` اجرا شد؛ با `FOR UPDATE` گیر کرد.

## قفل سطح جدول

هر دستور یک قفل روی جدول هم می‌گیرد. از `pg_locks` برای backend مربوط به session A خواندم:

```text
after SELECT:                       AccessShareLock
after UPDATE:                       RowExclusiveLock
after ALTER TABLE ... ADD COLUMN:   AccessExclusiveLock
```

طبق مستندات `AccessExclusiveLock` با همه‌ی حالت‌های دیگر تداخل دارد؛ برای همین `ALTER TABLE` و `VACUUM FULL` می‌توانند جدول را متوقف کنند. دیدمش: A تراکنشی باز داشت که `acct` را خوانده بود، B دستور `VACUUM FULL acct` را زد و `pg_locks` برای B قفل `AccessExclusiveLock` را با `granted = false` نشان داد. با commit شدن A، کار B تمام شد.

## چه کسی جلوی چه کسی را گرفته

A ردیف ۲ را update کرد و تراکنش را باز نگه داشت؛ B همان ردیف را update کرد و منتظر ماند:

```text
A is pid 8550, B is pid 8552
   8552 | Lock | transactionid | [8550] | UPDATE acct SET balance=balance+1 WHERE
   locks: transactionid | ShareLock | false
```

ستون‌ها: `pid`، `wait_event_type`، `wait_event`، `pg_blocking_pids` و کوئری، همه برای B. `pg_blocking_pids` مستقیم جواب می‌دهد: process شماره‌ی 8550. B منتظر transaction id مربوط به A است، نه خود ردیف؛ قفل ردیف اینجا این‌طور کار می‌کند. مسدودکننده را در `pg_stat_activity` پیدا کنید؛ معمولاً idle in transaction است.

## timeout‌ها

سه تنظیم انتظار را محدود می‌کنند. `lock_timeout` همان خطای 55P03 بالا را داد. دو تای دیگر:

```text
statement_timeout 200ms, pg_sleep(2) -> ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
idle in transaction 900ms, next statement -> FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
```

مقدار `idle_in_transaction_session_timeout = 300ms` بود. اتصال را می‌کشد تا کلاینتِ رفته قفل نگه ندارد.

## یک {{< term "deadlock" "deadlock" >}} واقعی

`SHOW deadlock_timeout` مقدار `1s` را داد. A ردیف ۱ را update کرد، B ردیف ۲ را، A ردیف ۲ را خواست و منتظر ماند، بعد B ردیف ۱ را خواست:

```text
A -> ERROR: deadlock detected (SQLSTATE 40P01)
      DETAIL: Process 8550 waits for ShareLock on transaction 792; blocked by process 8552.
      Process 8552 waits for ShareLock on transaction 791; blocked by process 8550.
      HINT: See server log for query details.
```

PostgreSQL A را لغو کرد و update مربوط به B رد شد. انتخاب قربانی را نمی‌شود پیش‌بینی کرد. راه‌حل یک قاعده‌ی ترتیب است: همیشه ردیف‌ها را با یک ترتیب ثابت (مثلاً id) قفل کنید. وقتی هر دو session از ردیف ۱ شروع کردند، B فقط تا commit شدن A صبر کرد و هر دو بی‌خطا تمام شدند. کد شما باز هم باید روی 40P01 retry کند.

## صف کار با SKIP LOCKED

شش ردیف در `jobs`. هر worker این را اجرا می‌کند:

```sql
SELECT id FROM jobs WHERE state='new' ORDER BY id LIMIT 2 FOR UPDATE SKIP LOCKED
```

worker 1 با تراکنش باز `[1 2]` را برداشت؛ worker 2 همان لحظه `[3 4]` را. worker 1 کارهایش را done کرد و commit زد؛ worker 2 برای شبیه‌سازی crash rollback کرد و کارهای ۳ و ۴ به `new` برگشتند. این الگوی {{< term "skip-locked" "SKIP LOCKED" >}} است؛ با رویکرد مبتنی بر جدول در [Outbox Pattern](/fa/posts/go-outbox-pattern-nats/) مقایسه کنید.

## صف پشت ALTER TABLE

S1 تراکنشی باز کرد و فقط `acct` را خواند. S2 دستور `ALTER TABLE acct ADD COLUMN` را زد و منتظر S1 ماند. بعد S3 یک `SELECT` ساده زد:

```text
S3: plain SELECT with lock_timeout 300ms -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
   8550 | AccessShareLock | true | []
   8552 | AccessExclusiveLock | false | [8550]
```

یک خواندن بی‌ضرر رد شد، چون پشت `ALTER` منتظر صف ایستاد. روی جدول پرترافیک یک تراکنش فراموش‌شده به‌علاوه‌ی یک migration همه‌چیز را متوقف می‌کند. migration را با `lock_timeout` کوتاه اجرا کنید و دوباره تلاش کنید.

## قفل‌های advisory

یک {{< term "advisory-lock" "advisory lock" >}} عددی را که خودتان انتخاب می‌کنید قفل می‌کند. A کلید 42 را گرفت؛ `pg_try_advisory_lock(42)` در B مقدار `false` داد. بعد از آزاد شدن توسط A مقدار `true` شد.

## چند نکته‌ی مهم

- تراکنش را کوتاه نگه دارید؛ قفل‌ها تا commit یا rollback می‌مانند.
- برای migration `lock_timeout` و برای اپلیکیشن `idle_in_transaction_session_timeout` بگذارید.
- با ترتیب ثابت قفل کنید و روی 40P01 retry کنید.
- پیش از kill، `pg_blocking_pids()` را ببینید.

## تمرین

deadlock را در دو پنجره‌ی `psql` بازتولید کنید و با ترتیب ثابت درستش کنید. بعد تراکنشی باز کنید، از پنجره‌ی دیگر `ALTER TABLE` بزنید و `pg_locks` را ببینید.

## قدم بعدی

پست بعدی این سری: JSONB و جست‌وجوی متنی.
