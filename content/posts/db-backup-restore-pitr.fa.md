+++
date = '2027-02-25T10:00:00+03:30'
draft = false
title = 'backup، restore و PITR'
description = 'backup و restore در PostgreSQL با دست: بک‌آپ منطقی، base backup سرد و آنلاین، WAL archiving و بازیابی به لحظه‌ی دلخواه تا یک restore point.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "backup", "pitr", "wal-archiving"]
cover = { image = "/images/covers/db-backup-restore-pitr.fa.png", alt = "backup، restore و PITR", hiddenInSingle = true }
+++

یک `DELETE FROM orders;` که `WHERE`اش فراموش شده، همه‌ی سفارش‌ها را یک‌جا پاک می‌کند. در [replication با دو instance واقعی](/fa/posts/db-replication-streaming/) دیدیم چنین `DELETE`ی کمی بعد روی replica هم ظاهر می‌شود: replica شما را از مردن سرور نجات می‌دهد، نه از یک دستور اشتباه. پس سؤال این پست این است: چطور به لحظه‌ی درست قبل از اشتباه برگردیم؟

جواب دو جزء دارد. اولی **base backup** است: یک کپی کامل از فایل‌های پایگاه داده در یک لحظه. دومی **آرشیو {{< term "wal" "WAL" >}}** است: جای امنی که هر تکه‌ی تمام‌شده‌ی write-ahead log در آن نگه داشته می‌شود. WAL را در [تراکنش و ACID](/fa/posts/db-transactions-acid/) دیدیم: رکورد ترتیبی هر تغییر، که پیش از رسیدن تغییر به فایل‌های داده نوشته می‌شود. کپی فایل‌های دیشب به‌علاوه‌ی همه‌ی لاگ از آن موقع، در اصل همه‌ی چیزی است که برای ساختن دوباره‌ی پایگاه داده در هر لحظه بعد از دیشب لازم است: از کپی شروع می‌کنید، لاگ را replay می‌کنید و هر جا خواستید می‌ایستید. این همان {{< term "pitr" "point-in-time recovery" >}} یا PITR است. بقیه‌ی پست آن را دستی می‌سازد و بعد به نقطه‌ای پیش از یک `DELETE` عمدی برمی‌گردد.

> همه‌چیز روی PostgreSQL 18.3 واقعی (باینری‌های embedded) و یک دیتابیس کوچک اجرا شد (دو جدول، ۱۰۰ customer، ۵۰۰ order؛ کل data directory در ابتدا ۴۷ مگابایت است). برای این نسخه‌ی پست دمو را دوباره اجرا کردم. زمان‌سنجی نیست. تنها `pg_dump` و `pg_basebackup` این ماشین نسخه‌ی 17.5 است و هر دو را روی سرور 18.3 امتحان کردم: هیچ‌کدام کار نمی‌کند، پس هیچ‌کدام را **با موفقیت اجرا نکردم**. هرجا معادل دستی گذاشتم گفته‌ام. زمان‌ها در لاگ‌ها UTC است و مسیرهای موقت در دستورها با `<archive>` عوض شده‌اند. همه‌چیز اینجا روی یک ماشین است؛ دایرکتوری آرشیو روی همان دیسک داده است، که سیستم واقعی نباید چنین کند.

## ۱. بک‌آپ منطقی، دستی

{{< term "logical-backup" "بک‌آپ منطقی" >}} کپی داده به‌شکل ردیف و SQL است، نه کپی فایل‌ها. `pg_dump` آن را می‌سازد، پس اول ببینیم امتحانش چه می‌دهد:

```text
$ pg_dump shop
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.3; pg_dump version: 17.5
$ pg_basebackup -D pbb
pg_basebackup: error: incompatible server version 18.3
```

(پیام اول از همین اجرا آمده؛ پیام `pg_basebackup` همان است که در پست replication نشان دادم.) پس بک‌آپ منطقی را با `\copy` ساختم که فقط یک اتصال معمولی می‌خواهد. تعریف جدول‌ها از فایل `schema.sql` است که خودم نوشتم. `pg_dump` واقعی آن را با constraintها، دسترسی‌ها و sequenceها می‌ساخت؛ مال من فقط همین دو جدول را دارد:

```text
\copy customers TO customers.csv CSV     -- COPY 100
\copy orders TO orders.csv CSV           -- COPY 500
CREATE DATABASE shop_restored;
\i schema.sql ; \copy ... FROM ... CSV
shop|100|500|126425.95
shop_restored|100|500|126425.95
```

هر خط نام دیتابیس، تعداد customerها، تعداد orderها و مجموع `total` است. دیتابیس اصلی و بازیابی‌شده در هر سه عدد یکی هستند. (مجموع در هر اجرا فرق می‌کند چون مبلغ‌های دمو تصادفی‌اند.) بک‌آپ منطقی دو ویژگی دارد که باید یادتان بماند. بین نسخه‌ها قابل حمل است چون فقط داده است. ولی عکسی از یک لحظه است و بازیابی‌اش یعنی بار کردن همه‌ی ردیف‌ها و ساختن دوباره‌ی همه‌ی ایندکس‌ها.

## ۲. بک‌آپ فیزیکی سرد

بک‌آپ فیزیکی به‌جای داده، فایل‌های پایگاه داده را کپی می‌کند. ساده‌ترین راهش این است که سرور را خاموش کنید، data directory را کپی کنید و کپی را (اینجا روی پورت دیگری) روشن کنید:

```text
pg_ctl -D data stop ; cp -R data cold_copy ; pg_ctl -D cold_copy start
cold|100|500
```

لاگ کپی می‌گوید `database system was shut down at ...`، یعنی خاموشی تمیز بود و نیازی به recovery نبود. ساده و درست است و downtime می‌خواهد. برای همین گام بعدی مهم است.

## ۳. base backup آنلاین

چرا نمی‌شود فایل‌های سروری را که روشن است همین‌طور کپی کرد؟ چون فایل‌ها وسط کپی عوض می‌شوند. تا `cp` تمام شود، ابتدای کپی مال یک لحظه است و انتهایش مال لحظه‌ی دیگر، و pageهای داخلش در حالتی مخلوط‌اند. راه PostgreSQL این است که بگذارد کپی ناسازگار باشد و بعد با WAL درستش کند: سرور می‌نویسد لاگ در لحظه‌ی شروع کپی کجا بود، و replay کردن لاگ از آن نقطه هر page را به حالت سازگار می‌رساند. برای این باید بداند که شما دارید کپی می‌گیرید. API سطح پایین این کار را می‌کند و **sessionای که `pg_backup_start` را صدا می‌زند باید تا `pg_backup_stop` باز بماند**. من از یک اسکریپت `psql` استفاده کردم که کپی را با `\!` از داخل همان session اجرا می‌کرد و در همان حین از یک اتصال دیگر یک order اضافه کرد، تا نشان بدهد تغییری که وسط کپی رخ می‌دهد گم نمی‌شود:

```text
SELECT pg_backup_start('base1', true);    -- 0/4000028
\! cp -R data base                         -- (and, meanwhile, INSERT of order 501)
SELECT * FROM pg_backup_stop(true) \gset
\o base/backup_label
\qecho :labelfile
NOTICE:  all required WAL segments have been archived
```

`pg_backup_start` موقعیت WAL را که بک‌آپ از آنجا شروع می‌شود برگرداند، `0/4000028` (LSNها در هر اجرا فرق می‌کنند). `pg_backup_stop` متن یک فایل `backup_label` را برگرداند و `\qecho` آن را داخل کپی نوشت. این فایل باید در کپی باشد، نه در data directory ی زنده: هنگام راه‌اندازی به سرور بازیابی‌شده می‌گوید replay را از کجا شروع کند. اولین خط‌هایش در این اجرا:

```text
START WAL LOCATION: 0/4000028 (file 000000010000000000000004)
CHECKPOINT LOCATION: 0/4000080
BACKUP METHOD: streamed
BACKUP FROM: primary
START TIME: 2026-11-04 16:36:37 UTC
LABEL: base1
START TIMELINE: 1
```

پیام `NOTICE` می‌گوید چون آرشیو روشن است، `pg_backup_stop` صبر کرد تا همه‌ی WALی که این بک‌آپ لازم دارد با امنیت در آرشیو برسد. بعد در کپی `postmaster.pid` و محتوای `pg_wal` را پاک کردم، چون WAL را آرشیو می‌دهد (مستندات اجازه می‌دهند کنارشان بگذاریم). کپی از ۸۶ مگابایت به ۳۸ مگابایت رسید. حذف‌های دیگر را امتحان نکردم.

## ۴. آرشیو WAL

آرشیو فقط یک دایرکتوری است که هر segment تمام‌شده‌ی WAL در آن کپی می‌شود. WAL در فایل‌های ثابتی به اسم segment نوشته می‌شود، به‌طور پیش‌فرض هرکدام ۱۶ مگابایت. این تنظیم‌ها آرشیو را روشن می‌کنند (روی این ماشین در خط فرمان دادمشان):

```text
archive_mode = on
archive_command = 'test ! -f <archive>/%f && cp %p <archive>/%f'
SELECT pg_switch_wal();
```

و آرشیو در پایان دمو، بعد از نوشتن‌های بخش بعد، این‌طور بود (اندازه به بایت، بعد نام):

```text
16777216 000000010000000000000001
16777216 000000010000000000000002
16777216 000000010000000000000003
16777216 000000010000000000000004
     318 000000010000000000000004.00000028.backup
16777216 000000010000000000000005
```

`%p` مسیر segment و `%f` نام فایل آن است. بخش `test ! -f` از رونویسی فایلی که از قبل هست جلوگیری می‌کند، همان‌طور که مستندات توصیه می‌کنند. فایل کوچک `.backup` سرگذشت base backup ای است که گرفتیم. `pg_switch_wal()` segment فعلی را می‌بندد تا همین حالا آرشیو شود، نه وقتی پر شد؛ آن را بعد از آخرین نوشتن می‌زنم تا همان نوشتن هم در آرشیو باشد. طبق مستندات اگر `archive_command` شکست بخورد، PostgreSQL WAL آرشیو‌نشده را روی primary نگه می‌دارد که می‌تواند دیسک را پر کند، پس سیستم واقعی باید آن را مانیتور کند.

## ۵. Point-in-time recovery

بعد از base backup، روی primary ماجرا را بازی کردم، با یک اشتباه عمدی در انتها:

```text
INSERT ... 100 orders        -- 601 rows
SELECT clock_timestamp();    -- 2026-11-04 16:36:48.389665+00  (noted)
INSERT ... 50 orders         -- 651 rows
SELECT pg_create_restore_point('before_oops');
DELETE FROM orders;          -- DELETE 651  (forgot the WHERE)
SELECT pg_switch_wal();
```

`pg_create_restore_point` یک نشانه‌ی نام‌دار در WAL می‌نویسد. برچسبی است که بعداً می‌توانید بگویید «همین‌جا بایست» و تقریباً هزینه‌ای ندارد.

برای بازیابی، base backup را در یک دایرکتوری تازه کپی کردم و به تنظیماتش `restore_command` را اضافه کردم (چطور یک segment آرشیوشده را بیاورد: `cp <archive>/%f %p`)، یک هدف بازیابی، و `recovery_target_action = 'promote'` (وقتی به هدف رسید، یک سرور معمولی قابل نوشتن شو). بعد یک فایل خالی `recovery.signal` ساختم که وجودش به PostgreSQL می‌گوید در حالت recovery شروع کن، و سرور را روشن کردم. با `recovery_target_name = 'before_oops'` دیتابیس بازیابی‌شده ۶۵۱ order اش را برگرداند:

```text
restored by name|651|651
LOG:  starting backup recovery with redo LSN 0/4000028, checkpoint LSN 0/4000080, on timeline ID 1
LOG:  restored log file "000000010000000000000004" from archive
LOG:  starting point-in-time recovery to "before_oops"
LOG:  restored log file "000000010000000000000005" from archive
LOG:  consistent recovery state reached at 0/4003800
LOG:  recovery stopping at restore point "before_oops", time 2026-11-04 16:36:49.463056+00
LOG:  selected new timeline ID: 2
LOG:  archive recovery complete
```

خط اول تعداد order و بزرگ‌ترین id است (۶۵۱ و ۶۵۱؛ کلمه‌ی قبل از آن‌ها برچسبی است که query چاپ می‌کند). order شماره‌ی ۵۰۱ که وسط کپی اضافه شد هم بینشان است. لاگ مثل یک داستان خوانده می‌شود. از موقعیت `backup_label` شروع کرد، segment ۴ و بعد ۵ را از آرشیو آورد، به حالت سازگار رسید، تا نقطه‌ی بازیابی replay کرد و همان‌جا ایستاد، پیش از `DELETE`. بعد **timeline 2** را انتخاب کرد: timeline یک شاخه‌ی شماره‌دار از تاریخچه است. بعد از recoveryای که در گذشته می‌ایستد، سرور شاخه‌ی تازه‌ای باز می‌کند تا نوشتن‌های جدیدش با تاریخچه‌ی قدیمی که به `DELETE` رسید قاطی نشود. (در لاگ خط‌هایی مثل `cp: ...00000002.history: No such file` هم هست. عادی‌اند: PostgreSQL دنبال فایل تاریخچه‌ی timeline جدیدتر می‌گردد و آرشیو چنین فایلی ندارد.)

نقطه‌ی بازیابی یک نام است. می‌شود در یک زمان هم ایستاد. با `recovery_target_time` روی همان `2026-11-04 16:36:48.389665+00` یادداشت‌شده، در یک کپی تازه از همان base backup:

```text
restored by time|601|601
LOG:  starting point-in-time recovery to 2026-11-04 16:36:48.389665+00
LOG:  recovery stopping before commit of transaction 765, time 2026-11-04 16:36:49.460867+00
```

۶۰۱ order: دقیقاً حالت قبل از insert پنجاه‌تایی. سرور تا اولین commit بعد از زمان هدف replay کرد و پیش از آن ایستاد. هدف زمانی از هدف نام‌دار کم‌دقت‌تر است: باید لحظه‌ی درست را، در time zone درست، بدانید و ساعت سرور باید قابل اعتماد باشد. یک restore point فقط یک صدا زدن تابع هزینه دارد، پس پیش از هر کار پرخطر، مثل migrationهای [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/)، یکی بسازید. و بالاخره هدفی که هرگز رخ نمی‌دهد خطاست، نه بازیابی ناقص بی‌صدا. نقطه‌ای به اسم `no_such_point` خواستم و سرور بالا نیامد:

```text
FATAL:  recovery ended before configured recovery target was reached
```

## بک‌آپ واقعی چه می‌خواهد

- **replica بک‌آپ نیست.** `DELETE` اشتباه replicate می‌شود، همان‌طور که دیدیم. هر دو را داشته باشید.
- **بک‌آپی که هرگز بازیابی نکرده‌اید یک امید است.** کل این پست روی بازیابی ساخته شد، چون تنها راه دانستن اینکه کار می‌کند همین است. طبق برنامه در یک instance موقت بازیابی کنید و یک query واقعی بزنید.
- **آرشیو را بیرون از دیسک primary نگه دارید** و مراقب شکست `archive_command` باشید.
- **برای سیستم واقعی از `pg_basebackup` یا ابزارهایی مثل pgBackRest و Barman استفاده کنید.** فقط اسمشان را می‌برم؛ هیچ‌کدام را اجرا نکردم، و base backup دستی من راهی برای دیدن کاری است که آن‌ها می‌کنند، نه چیزی که باید اجرا کنید.
- **اینجا امتحان نشد:** بک‌آپ از سیستم شلوغ، رمزگذاری بک‌آپ، tablespace و بازیابی در timelineهای بعد از اولی.

## تمرین

از یک دیتابیس که می‌توانید خرابش کنید base backup بگیرید. دو restore point دور یک `DROP TABLE` بگذارید، به هرکدام بازیابی کنید و مقایسه کنید. اگر یک هدف زمانی هم بگذارید که قبل از شروع base backup باشد چه می‌شود؟

## قدم بعدی

قدم بعدی [connection pool و حالت‌های خرابی](/fa/posts/db-connection-pooling/) است. وقتی بدانیم داده برمی‌گردد، سؤال بعدی این است که اصلاً به آن برسیم: هر query یک connection می‌خواهد و connectionها محدودند.
