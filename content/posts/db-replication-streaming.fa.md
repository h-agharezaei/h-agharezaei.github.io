+++
date = '2027-02-13T10:00:00+03:30'
draft = false
title = 'replication با دو instance واقعی'
description = 'streaming replication در PostgreSQL با دو instance واقعی: راه‌اندازی، lag بر حسب بایت، توقف commit همگام، promote و اینکه replica بک‌آپ نیست.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "replication", "wal", "high-availability"]
cover = { image = "/images/covers/db-replication-streaming.fa.png", alt = "replication با دو instance واقعی", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-partitioning/) یک جدول بزرگ را داخل یک سرور تکه‌تکه کردیم. این پست جهت دیگر را می‌گیرد: نگه‌داشتن یک نسخه‌ی دوم از کل سرور. {{< term "replication" "Replication" >}} ظرفیت خواندن می‌دهد و یک standby که وقتی primary بمیرد می‌توانید promote کنید. پایه‌اش همان {{< term "wal" "WAL" >}} است که در [تراکنش و ACID](/fa/posts/db-transactions-acid/) دیدیم، و ردیف‌های مرده‌ای که در [MVCC و VACUUM](/fa/posts/db-mvcc-vacuum/) بود.

> همه‌چیز روی دو PostgreSQL 18.3 واقعی روی یک ماشین اجرا شد (پورت‌های 55713 و 55714، فقط loopback، بدون Docker). زمان‌سنجی نیست، فقط بایت و وضعیت. باینری‌های embedded فایل `pg_basebackup` نداشتند و تنها نسخه‌ی موجود روی این ماشین 17.5 است که با سرور 18.3 کار نمی‌کند. برای همین کپی را دستی ساختم: primary را خاموش کردم، data directory را کپی کردم و دو چیزی را که `pg_basebackup -R` می‌نویسد خودم نوشتم. روی سیستم زنده از `pg_basebackup -D replica -R -X stream` استفاده کنید؛ من آن را اجرا نکردم.

## تنظیم primary

قبل از دست‌زدن پیش‌فرض‌ها را دیدم: `wal_level` برابر `replica`، `max_wal_senders` برابر ۱۰ و `hot_standby` روشن است. فقط `listen_addresses = '127.0.0.1'` را عوض کردم. یک role برای replication و یک خط `pg_hba.conf` لازم است؛ `initdb --auth-host=scram-sha-256` این خط را خودش ساخته بود:

```text
host    replication     all             127.0.0.1/32            scram-sha-256

CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '...';
```

## ساختن replica

standby یعنی کپی data directory به‌علاوه‌ی فایل `standby.signal` (وجودش یعنی «در حالت recovery بمان») و یک `primary_conninfo`. این همان چیزی است که `-R` در `postgresql.auto.conf` می‌نویسد:

```text
primary_conninfo = 'host=127.0.0.1 port=55713 user=replicator password=... application_name=replica1'
```

بعد از روشن‌کردن هر دو، primary replica را می‌بیند و موقعیت‌های {{< term "lsn" "LSN" >}} برابرند:

```text
primary> SELECT application_name, state, sent_lsn, replay_lsn, sync_state FROM pg_stat_replication;
 replica1 | streaming | 0/1830840 | 0/1830840 | async

replica> SELECT pg_is_in_recovery();   -- t        (primary: f)
replica> SELECT status, sender_port FROM pg_stat_wal_receiver;
 streaming | 55713
```

## نوشتن فقط یک‌طرفه است

روی primary یک customer اضافه کردم و replica را poll کردم تا ظاهر شد (اینجا با یک poll). replica نوشتن را رد می‌کند:

```text
replica> INSERT INTO customers(name,email,country) VALUES ('x','x@example.com','NL');
ERROR:  cannot execute INSERT in a read-only transaction
```

## lag بر حسب بایت

replication به‌طور پیش‌فرض asynchronous است، پس خواننده‌ی روی replica ممکن است داده‌ی قدیمی ببیند. ۳۰۰۰۰۰ ردیف در یک جدول گذاشتم و بلافاصله از primary پرسیدم:

```text
SELECT pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes FROM pg_stat_replication;
 6291496
replica> SELECT count(*) FROM big;   -- 0   (ردیف‌ها هنوز replay نشده بودند)
```

یک poll بعد تعداد ۳۰۰۰۰۰ و lag صفر بود. عدد ۶ مگابایت چیزی است که در همین اجرا دیدم؛ از اجرایی به اجرای دیگر فرق می‌کند. برای یک سرویس یعنی اگر بلافاصله بعد از نوشتن، خواندن را به replica بفرستید به باگ read-your-writes می‌خورید.

## Synchronous commit

با `synchronous_standby_names = 'replica1'` (فقط reload) مقدار `sync_state` شد `sync` و {{< term "synchronous-commit" "synchronous commit" >}} صبر می‌کند تا standby هم WAL را داشته باشد. replica را خاموش کردم و یک INSERT را در session پس‌زمینه زدم. گیر کرد و `pg_stat_activity` دلیلش را نشان داد:

```text
IPC/SyncRep | active | insert into customers(name,email,country
```

با `pg_cancel_backend` لغوش کردم:

```text
WARNING:  canceling wait for synchronous replication due to user request
DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.
```

ردیف روی primary واقعاً commit شده بود. این هزینه‌ی این تنظیم است: با یک standby همگام، مرگ standby همه‌ی نوشتن‌ها را متوقف می‌کند. بعد از روشن‌کردن دوباره‌ی replica خودش عقب‌ماندگی را جبران کرد.

## Promote

```text
replica> SELECT pg_promote(wait => true);   -- t
replica> SELECT pg_is_in_recovery();        -- f
replica> INSERT INTO customers(...) VALUES ('on_new_primary', ...);   -- INSERT 0 1
```

حالا بخش خطرناک. primary قدیمی را روشن گذاشته بودم و نوشتن خودش را بدون مشکل پذیرفت:

```text
old primary: 8|on_old_primary  7|sync
new primary: 39|on_new_primary  7|sync
```

این {{< term "split-brain" "split-brain" >}} است: دو سرور که هر دو قابل نوشتن‌اند و تاریخچه‌هایشان فرق دارد. خود PostgreSQL هسته {{< term "failover" "failover" >}} خودکار ندارد؛ ابزارهایی مثل Patroni یا repmgr برای این کار هستند (من اجرایشان نکردم). هر چه استفاده کنید باید مطمئن شود primary قدیمی قبل از برگشتن از مدار خارج شده است.

## replica بک‌آپ نیست

روی primary ۱۰ ردیف از `products` را DELETE کردم. replica در همان poll اول ۰ ردیف نشان داد. DELETE فقط یک رکورد WAL دیگر است، پس `UPDATE`، `DELETE` یا `DROP TABLE` اشتباه هم وفادارانه replicate می‌شود. نسخه‌های مرده‌ای که [VACUUM](/fa/posts/db-mvcc-vacuum/) هنوز نیاز دارد هم undo log قابل استفاده نیستند. برای بازیابی بک‌آپ واقعی لازم است.

## چند نکته‌ی مهم

- replicaهای async عقب می‌مانند. نوشته‌ی خودتان را بدون چک‌کردن LSN یا استفاده از primary از آن‌ها نخوانید.
- یک standby همگام، خرابی‌اش را به توقف نوشتن تبدیل می‌کند؛ چند کاندیدا بگذارید یا async را بپذیرید.
- promote یک دستور است؛ سخت، تصمیم‌گرفتن درباره‌ی primary و خاموش‌کردن قدیمی است.
- replica همان داده‌ی خراب primary را دارد. جواب «سرور مرد» است، نه «کسی DELETE زد».
- logical replication (publication و subscription، در سطح جدول) را فقط نام می‌برم؛ اجرایش نکردم.

## تمرین

دو instance بالا بیاورید، replica را بسازید، سپس برای یک session مقدار `synchronous_commit = remote_apply` بگذارید و آنچه خواندن روی replica بلافاصله بعد از commit می‌بیند را با حالت پیش‌فرض `on` مقایسه کنید. تفاوت را با ستون‌های LSN توضیح دهید.

## قدم بعدی

پست بعدی «backup، restore و PITR» است: چطور به لحظه‌ی قبل از آن DELETE اشتباه برگردیم.
