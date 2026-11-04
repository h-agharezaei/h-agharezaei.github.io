+++
date = '2027-02-13T10:00:00+03:30'
draft = false
title = 'replication با دو instance واقعی'
description = 'streaming replication در PostgreSQL با دو instance واقعی: راه‌اندازی، lag بر حسب بایت، توقف commit همگام، promote و اینکه replica بک‌آپ نیست.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "replication", "wal", "high-availability"]
cover = { image = "/images/covers/db-replication-streaming.fa.png", alt = "replication با دو instance واقعی", hiddenInSingle = true }
+++

سروری را تصور کنید که ساعت سه نیمه‌شب می‌میرد. همه‌چیز روی همان یک ماشین است، پس تا کسی آن را بازیابی نکند کل سرویس از کار افتاده. راه حل بدیهی این است که یک ماشین دوم با نسخه‌ی به‌روز داده آماده‌ی جایگزینی داشته باشید، و در این فاصله بگذارید به query‌های خواندن هم جواب بدهد. این همان {{< term "replication" "replication" >}} است.

ولی یک سوءتفاهم هست که به قیمت از دست رفتن داده تمام می‌شود و می‌خواهم زود نشانش بدهم: replica نسخه‌ی دوم کل سرور است که همیشه به‌روز نگه داشته می‌شود، و دقیقاً به همین دلیل بک‌آپ نیست. اگر روی primary ده ردیف را DELETE کنید، replica هم چند لحظه بعد آن‌ها را پاک می‌کند. این را در بخش آخر می‌بینیم.

[partitioning جدول‌ها](/fa/posts/db-partitioning/) یک جدول بزرگ را داخل یک سرور تکه‌تکه کرد؛ این پست جهت دیگر را می‌گیرد و از کل سرور نسخه می‌سازد. پایه‌اش همان {{< term "wal" "WAL" >}} است که در [تراکنش و ACID](/fa/posts/db-transactions-acid/) دیدیم، و ردیف‌های مرده‌ای که در [MVCC و VACUUM](/fa/posts/db-mvcc-vacuum/) بود.

## ایده: لاگ را بفرست

پیش از دمو یک ایده. وقتی PostgreSQL چیزی را تغییر می‌دهد (ردیفی اضافه می‌کند، عوض می‌کند، ایندکسی می‌سازد)، اول شرح کوتاهی از آن تغییر را به انتهای یک فایل ترتیبی به اسم write-ahead log یا همان WAL اضافه می‌کند و فقط بعداً تغییر را در فایل‌های جدول می‌نویسد. این لاگ برای این هست که بعد از crash سرور بتواند آن را از آخرین نقطه‌ی امن بخواند و تغییراتی را که نوشتنشان تمام نشده بود دوباره انجام دهد. یعنی لاگ یک دستور پخت است: اگر آن را روی یک نسخه از داده دوباره اجرا کنید، آن نسخه به حالتی می‌رسد که لاگ شرح می‌دهد.

streaming replication همین دستور پخت را بین ماشین‌ها به کار می‌برد. سرور اول، **primary**، نوشتن را قبول می‌کند. سرور دوم، **standby** (یا replica)، از یک نسخه‌ی داده‌ی primary شروع می‌کند، به آن وصل می‌شود و WAL را همین‌طور که primary تولید می‌کند دریافت می‌کند. هر رکورد را دوباره اجرا (replay) می‌کند، پس یک لحظه‌ی کوتاه عقب‌تر از primary حرکت می‌کند. یک موقعیت در این لاگ {{< term "lsn" "LSN" >}} نام دارد (log sequence number)؛ شکلش مثل `0/E40F7A0` است و همیشه بزرگ‌تر می‌شود. مقایسه‌ی LSNها راهی است که با آن می‌سنجیم standby چقدر عقب است.

> همه‌چیز روی دو PostgreSQL 18.3 واقعی روی یک ماشین اجرا شد (پورت‌های تصادفی فقط روی loopback، بدون Docker). برای این نسخه‌ی پست کل دمو را دوباره اجرا کردم. زمان‌سنجی نیست، فقط بایت و وضعیت. باینری‌هایی که اینجا به کار می‌برم `pg_basebackup` ندارند و تنها نسخه‌ی موجود روی این ماشین 17.5 است که جواب می‌دهد `pg_basebackup: error: incompatible server version 18.3` (برای اطمینان اجرایش کردم). برای همین کپی را دستی ساختم: primary را خاموش کردم، data directory را کپی کردم و دو چیزی را که `pg_basebackup -R` می‌نویسد خودم نوشتم. روی سیستم زنده برای کپی گرفتن از primary در حال کار از `pg_basebackup -D replica -R -X stream` استفاده می‌کنید؛ من آن را اجرا نکردم. دو instance روی یک ماشین همچنین یعنی «ماشین replica» و «شبکه‌ی بینشان» واقعی نیستند: هرچه پایین می‌بینید سازوکار را نشان می‌دهد، نه رفتار دو دیتاسنتر را.

## تنظیم primary

قبل از دست‌زدن پیش‌فرض‌ها را دیدم: `wal_level` برابر `replica`، `max_wal_senders` (تعداد standbyهایی که می‌توانند وصل شوند) برابر ۱۰ و `hot_standby` (اینکه standby بتواند به queryهای خواندن جواب دهد) روشن است. تنها تنظیمی که عوض کردم `listen_addresses = '127.0.0.1'` بود. standby با یک role ویژه که صفت `REPLICATION` دارد وصل می‌شود و `pg_hba.conf` باید اجازه‌اش را بدهد. `initdb --auth-host=scram-sha-256` خط مربوط به اتصال‌های محلی را خودش ساخته بود:

```text
host    replication     all             127.0.0.1/32            scram-sha-256

CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '...';
```

## ساختن replica

standby سه چیز است: یک کپی از data directory ی primary، یک فایل خالی به اسم `standby.signal` (صرف وجودش به PostgreSQL می‌گوید «در حالت recovery بمان و replay را ادامه بده، primary نشو»)، و تنظیم `primary_conninfo` که می‌گوید primary کجاست. این همان چیزی است که `-R` در `postgresql.auto.conf` می‌نویسد و من دستی نوشتم (پورت در هر اجرا تصادفی است):

```text
primary_conninfo = 'host=127.0.0.1 port=52951 user=replicator password=... application_name=replica1'
```

بعد از روشن‌کردن هر دو، از primary پرسیدم چه کسی وصل است، و از replica پرسیدم خودش چیست. هر دو ستون LSN برابرند، یعنی هرچه primary فرستاده قبلاً replay شده:

```text
primary> SELECT application_name, state, sent_lsn, replay_lsn, sync_state FROM pg_stat_replication;
 replica1 | streaming | 0/E40F7A0 | 0/E40F7A0  | async

replica> SELECT pg_is_in_recovery();   -- t        (primary: f)
replica> SELECT status, sender_port FROM pg_stat_wal_receiver;
 streaming | 52951
```

`pg_stat_replication` نمای primary از standbyهایش است: `streaming` وضعیت دلخواه ماست، `sent_lsn` یعنی primary تا کجا فرستاده، `replay_lsn` یعنی standby تا کجا اجرا کرده، و `async` یعنی ناهمگام (پایین‌تر بیشتر). مقدارهای LSN در هر اجرا فرق می‌کنند ولی باید مثل اینجا برابر باشند. `pg_is_in_recovery()` روی standby برابر `t` است؛ و receiver روی standby تأیید می‌کند که از پورت primary در حال streaming است.

## نوشتن فقط یک‌طرفه است

روی primary یک customer اضافه کردم و replica را poll کردم تا ظاهر شد؛ اینجا همان poll اول بود. replica خودش نوشتن را قبول نمی‌کند:

```text
replica> INSERT INTO customers(name,email,country) VALUES ('x','x@example.com','NL');
ERROR:  cannot execute INSERT in a read-only transaction
```

## lag بر حسب بایت

replication به‌طور پیش‌فرض asynchronous است: primary commit می‌کند بی‌آنکه منتظر standby بماند، پس خواننده‌ی روی replica ممکن است داده‌ی قدیمی ببیند. ۶۰۰٬۰۰۰ ردیف در یک جدول تازه گذاشتم و بلافاصله بعد از insert از primary پرسیدم standby چقدر عقب است، بعد ردیف‌های replica را شمردم:

```text
SELECT pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes FROM pg_stat_replication;
 20803360
replica> SELECT count(*) FROM big;   -- 0   (ردیف‌ها هنوز replay نشده بودند)
```

`pg_wal_lsn_diff` دو LSN را از هم کم می‌کند و بایتِ WAL می‌دهد: حدود ۲۰ مگابایت هنوز منتظر replay بود، پس replica هنوز جدول را خالی می‌دید. یک poll بعد تعداد ۶۰۰٬۰۰۰ و lag صفر بود. عدد ۲۰ مگابایت مال همین اجراست و هر بار فرق می‌کند (اجراهای قبلی خودم از حدود ۶ تا ۲۱ مگابایت جواب دادند، و گاهی وقتی می‌شمردم replica از قبل رسیده بود). برای یک سرویس این یعنی باگ read-your-writes: اگر روی primary بنویسید و بلافاصله از replica بخوانید، ممکن است نوشته‌ی خودتان را نبینید.

## replication همگام (synchronous)

می‌توانیم primary را مجبور به صبر کنیم. با `synchronous_standby_names = 'replica1'` (فقط reload) مقدار `sync_state` شد `sync` و {{< term "synchronous-commit" "synchronous commit" >}} فقط وقتی برمی‌گردد که standby هم WAL را داشته باشد. این مشکل lag را برای داده‌ی commit شده برمی‌دارد و مشکل تازه‌ای می‌آورد. برای دیدنش replica را خاموش کردم و در یک session پس‌زمینه یک `INSERT` زدم. گیر کرد و `pg_stat_activity` دلیلش را نشان داد:

```text
IPC/SyncRep | active | insert into customers(name,email,country
```

رویداد انتظار `SyncRep` یعنی «منتظر standby همگام». query را با `pg_cancel_backend` لغو کردم:

```text
WARNING:  canceling wait for synchronous replication due to user request
DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.
```

هشدار را با دقت بخوانید: ردیف روی primary واقعاً commit شده بود (شمارش آنجا ۱ برگشت)؛ فقط انتظار لغو شد. این هزینه‌ی این تنظیم است. با یک standby همگام، مرگ standby همه‌ی نوشتن‌های primary را متوقف می‌کند. بعد از روشن‌کردن دوباره‌ی replica خودش عقب‌ماندگی را جبران کرد و ردیف را داشت.

## Promote و خطر دو primary

حالا خرابی برنامه‌ریزی‌شده. `pg_promote` یک standby را primary می‌کند: از حالت recovery بیرون می‌آید و نوشتن را قبول می‌کند.

```text
replica> SELECT pg_promote(wait => true);   -- t
replica> SELECT pg_is_in_recovery();        -- f
replica> INSERT INTO customers(...) VALUES ('on_new_primary', ...);   -- INSERT 0 1
```

(قبل از promote دوباره `synchronous_standby_names` را برداشتم تا primary قدیمی منتظر standbyای نماند که دیگر دنبالش نیست.) حالا بخش خطرناک. primary قدیمی را روشن گذاشته بودم و نوشتن خودش را بدون مشکل پذیرفت:

```text
old primary: 20003|on_old_primary
new primary: 20034|on_new_primary
```

هر دو ردیف تقریباً هم‌زمان در `customers` روی دو سرور درج شدند و هر سرور فقط ردیف خودش را دارد. (idها هم فرق دارند: هر سرور حالا خودش idها را می‌دهد.) این {{< term "split-brain" "split-brain" >}} است: دو سرور که هر دو قابل نوشتن‌اند و تاریخچه‌هایشان فرق دارد. هیچ‌کدام از دیگری خبر ندارد و یکی‌کردن دو تاریخچه بعداً دستی است و اغلب داده از دست می‌رود. خود PostgreSQL هسته {{< term "failover" "failover" >}} خودکار ندارد؛ فقط دستور `pg_promote` را می‌دهد. ابزارهایی مثل Patroni یا repmgr برای بقیه‌اش هستند (من اجرایشان نکردم). هر چه استفاده کنید باید مطمئن شود primary قدیمی fence شده، یعنی نمی‌تواند بنویسد، پیش از آنکه برگردد.

## replica بک‌آپ نیست

برگردیم به سوءتفاهم اول. یک جفت primary و replica را دوباره ساختم، جدولی به اسم `keep_me` با ۱۰ ردیف ساختم (replica هم آن‌ها را داشت) و بعد روی primary پاکشان کردم:

```text
before: primary 10 replica 10
DELETE 10
replica poll 1: 0
replica poll 2: 0
replica poll 3: 0
```

replica در همان poll اول ۰ ردیف نشان داد. `DELETE` فقط یک رکورد دیگر در WAL است و replica هر چه لاگ بگوید وفادارانه اجرا می‌کند. یک `UPDATE` اشتباه هم همین‌طور است، و `DROP TABLE` هم: حذف جدول روی primary باعث شد `select * from keep_me` روی replica با `relation "keep_me" does not exist` شکست بخورد. نسخه‌های قدیمی ردیف که [VACUUM](/fa/posts/db-mvcc-vacuum/) هنوز پاکشان نکرده undo log نیستند که برای بازیابی به کار بیاید. اگر می‌خواهید به لحظه‌ی قبل از اشتباه برگردید، بک‌آپ واقعی لازم است، که موضوع پست بعدی است.

(نسخه‌ی قبلی این پست می‌گفت ۱۰ ردیف از `products` را پاک کردم. در schema فروشگاه این کار شکست می‌خورد چون `order_items` به آن‌ها ارجاع دارد، پس به‌جایش از این جدول موقت استفاده کردم.)

## replication چه چیزی را حل نمی‌کند

- **replicaهای async عقب می‌مانند.** نوشته‌ی خودتان را بدون چک‌کردن LSN از replica نخوانید، یا این خواندن‌ها را به primary بفرستید.
- **یک standby همگام، خرابی‌اش را به توقف نوشتن تبدیل می‌کند.** چند کاندیدا بگذارید، یا replication ناهمگام و پنجره‌ی کوچک احتمال از دست رفتن داده‌اش را بپذیرید.
- **promote یک دستور است؛ سخت، تصمیم‌گرفتن درباره‌ی primary و خاموش‌کردن قدیمی است.**
- **replica همان داده‌ی خراب primary را دارد.** جواب «سرور مرد» است، نه «کسی DELETE زد».
- **logical replication** (publication و subscription، در سطح جدول) ابزار دیگری است. فقط نامش را می‌برم؛ اجرایش نکردم.

## تمرین

دو instance بالا بیاورید، replica را بسازید، سپس برای یک session مقدار `synchronous_commit = remote_apply` بگذارید و آنچه خواندن روی replica بلافاصله بعد از commit می‌بیند را با حالت پیش‌فرض `on` مقایسه کنید. تفاوت را با ستون‌های LSN توضیح دهید.

## قدم بعدی

پست بعدی [backup، restore و PITR](/fa/posts/db-backup-restore-pitr/) است: چطور به لحظه‌ی قبل از آن `DELETE` اشتباه برگردیم.
