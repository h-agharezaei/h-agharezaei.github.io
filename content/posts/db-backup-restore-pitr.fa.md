+++
date = '2027-02-25T10:00:00+03:30'
draft = false
title = 'backup، restore و PITR'
description = 'backup و restore در PostgreSQL با دست: بک‌آپ منطقی، base backup سرد و آنلاین، WAL archiving و بازیابی به لحظه‌ی دلخواه تا یک restore point.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "backup", "pitr", "wal-archiving"]
cover = { image = "/images/covers/db-backup-restore-pitr.fa.png", alt = "backup، restore و PITR", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-replication-streaming/) یک `DELETE` روی primary کمی بعد روی replica هم دیده شد. replica شما را از مردن سرور نجات می‌دهد، نه از یک دستور اشتباه. این پست درباره‌ی چیزی است که نجات می‌دهد: یک base backup به‌علاوه‌ی آرشیوی از {{< term "wal" "WAL" >}} که در [تراکنش و ACID](/fa/posts/db-transactions-acid/) دیدیم، و با آن می‌توان تاریخچه را تا لحظه‌ای دلخواه replay کرد. این همان {{< term "pitr" "بازیابی به لحظه‌ی دلخواه" >}} یا PITR است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی (باینری‌های embedded) و یک دیتابیس کوچک اجرا شد (دو جدول، ۱۰۰ customer، ۵۰۰ order، حدود ۴۰ مگابایت). زمان‌سنجی نیست. تنها `pg_dump` و `pg_basebackup` این ماشین نسخه‌ی 17.5 است، پس هیچ‌کدام را **با موفقیت اجرا نکردم**. هرجا معادل دستی گذاشتم گفته‌ام. مسیرهای موقت پایین با `<archive>` جایگزین شده‌اند.

## ۱. بک‌آپ منطقی، دستی

```text
$ pg_dump shop
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.3; pg_dump version: 17.5
$ pg_basebackup -D pbb
pg_basebackup: error: incompatible server version 18.3
```

برای همین {{< term "logical-backup" "بک‌آپ منطقی" >}} را با `\copy` ساختم که فقط یک اتصال معمولی می‌خواهد. تعریف جدول‌ها را در فایل `schema.sql` گذاشتم که خودم نوشتم (`pg_dump` واقعی آن را همراه constraintها، grantها و sequenceها می‌سازد؛ فایل من فقط همین دو جدول را دارد):

```text
\copy customers TO customers.csv CSV     -- COPY 100
\copy orders TO orders.csv CSV           -- COPY 500
CREATE DATABASE shop_restored;
\i schema.sql ; \copy ... FROM ... CSV
shop|100|500|187875.00
shop_restored|100|500|187875.00
```

تعداد ردیف‌ها و `sum(total)` برابرند. بک‌آپ منطقی بین نسخه‌ها قابل حمل است، ولی عکسی از یک لحظه است و restore یعنی ساختن دوباره‌ی همه‌ی ایندکس‌ها.

## ۲. بک‌آپ فیزیکی سرد

سرور را خاموش کنید، data directory را کپی کنید، پورت را عوض کنید و کپی را بالا بیاورید:

```text
pg_ctl -D data stop ; cp -R data cold_copy ; pg_ctl -D cold_copy start
cold|100|500
```

لاگ کپی می‌گوید `database system was shut down at ...`، یعنی نیازی به recovery نبود. ساده و درست است، ولی downtime می‌خواهد.

## ۳. base backup آنلاین

کپی‌کردن data directory یک سرور روشن فقط وقتی معتبر است که سرور بداند. API سطح‌پایین همین کار را می‌کند و **session‌ای که `pg_backup_start` را صدا زده باید تا `pg_backup_stop` باز بماند**. من یک `psql` را با خواندن از یک FIFO زنده نگه داشتم و از شل به آن نوشتم:

```text
SELECT pg_backup_start('base1', true);    -- 0/3000028
-- در شل دیگر: cp -R data/. base/   (وسط کپی یک order اضافه کردم)
SELECT * FROM pg_backup_stop(true) \gset
\o base/backup_label
\qecho :labelfile
NOTICE:  all required WAL segments have been archived
stopped at 0/30034E0
```

فایل `backup_label` که `pg_backup_stop` برمی‌گرداند باید داخل کپی نوشته شود، نه داخل data directory زنده. شروعش این است:

```text
START WAL LOCATION: 0/3000028 (file 000000010000000000000003)
CHECKPOINT LOCATION: 0/3000080
BACKUP METHOD: streamed
LABEL: base1
```

داخل کپی `postmaster.pid` و فایل‌های `pg_wal` را پاک کردم، چون WAL را آرشیو می‌دهد (طبق مستندات می‌شود از کپی حذفشان کرد). حجم کپی از ۷۰ به ۳۸ مگابایت رسید. حذف‌های دیگر را آزمایش نکردم.

## ۴. WAL archiving

آرشیو فقط یک پوشه است که هر segment تمام‌شده‌ی WAL در آن کپی می‌شود:

```text
archive_mode = on
archive_command = 'test ! -f <archive>/%f && cp %p <archive>/%f'
SELECT pg_switch_wal();
16777216 000000010000000000000002
16777216 000000010000000000000003
     322 000000010000000000000003.00000028.backup
16777216 000000010000000000000004
```

بخش `test ! -f` طبق مستندات جلوی بازنویسی فایل موجود را می‌گیرد. `pg_switch_wal()` segment ۱۶ مگابایتی جاری را می‌بندد تا همین حالا آرشیو شود، نه وقتی پر شد. اگر `archive_command` خطا بدهد WAL روی primary می‌ماند تا دیسک پر شود، پس مانیتورش کنید.

## ۵. بازیابی به لحظه‌ی دلخواه

بعد از base backup، روی primary:

```text
INSERT ... 100 orders        -- 601 ردیف
SELECT clock_timestamp();    -- 09:27:07.594437 (یادداشت شد)
INSERT ... 50 orders         -- 651 ردیف
SELECT pg_create_restore_point('before_oops');
DELETE FROM orders;          -- DELETE 651  (WHERE را فراموش کردم)
SELECT pg_switch_wal();
```

برای restore، base backup را کپی کنید، `restore_command = 'cp <archive>/%f %p'` و یک target و `recovery_target_action = 'promote'` اضافه کنید، فایل خالی `recovery.signal` را بسازید و بالا بیاورید. در کپی `archive_mode = off` هم گذاشتم تا داخل آرشیو ننویسد. با `recovery_target_name = 'before_oops'`:

```text
restored by name|651
LOG:  starting point-in-time recovery to "before_oops"
LOG:  restored log file "000000010000000000000004" from archive
LOG:  recovery stopping at restore point "before_oops"
LOG:  selected new timeline ID: 2
LOG:  archive recovery complete
```

۶۵۱ order برگشت. خطوط `cp: ...00000002.history: No such file` در لاگ عادی‌اند: PostgreSQL دنبال timeline جدیدتر می‌گردد. با `recovery_target_time = '2026-10-27 09:27:07.594437+03:30'` (از کپی تازه‌ی همان base):

```text
restored by time|601|1000
LOG:  recovery stopping before commit of transaction 764, time 2026-10-27 09:27:08.632306+03:30
```

target زمانی از نام دقیق‌تر نیست: ساعت و time zone درست لازم است. یک restore point فقط یک فراخوانی تابع است، پس پیش از هر migration پرخطر یکی بسازید (ببینید [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/)). targetی که هرگز رخ ندهد خطاست، نه restore ناقص بی‌صدا:

```text
FATAL:  recovery ended before configured recovery target was reached
```

## چند نکته‌ی مهم

- replica بک‌آپ نیست: `DELETE` اشتباه هم replicate می‌شود. هر دو را داشته باشید.
- بک‌آپی که هرگز restore نکرده‌اید فقط امید است. به‌صورت زمان‌بندی‌شده در یک instance آزمایشی restore کنید و یک query واقعی بزنید.
- آرشیو را خارج از دیسک primary نگه دارید و `archive_command` خراب را زیر نظر بگیرید.
- در سیستم واقعی از `pg_basebackup` یا ابزارهایی مثل pgBackRest و Barman استفاده کنید. فقط نامشان را می‌برم؛ اجرایشان نکردم.
- اینجا آزمایش نشد: بک‌آپ سیستم شلوغ، رمزنگاری بک‌آپ، tablespace و restore در timelineهای بعد از اولی.

## تمرین

از دیتابیسی که می‌توانید خرابش کنید base backup بگیرید. دو restore point دور یک `DROP TABLE` بسازید، به هرکدام recover کنید و مقایسه کنید. اگر target زمانی قبل از شروع base backup بگذارید چه می‌شود؟

## قدم بعدی

پست بعدی «connection pool و حالت‌های خرابی» است.
