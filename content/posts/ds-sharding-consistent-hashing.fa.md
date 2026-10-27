+++
date = '2027-05-15T10:00:00+03:30'
draft = false
title = 'sharding و consistent hashing'
description = 'sharding و consistent hashing: انحراف shard key، hot key، hash slot، شبیه‌سازی migration با crash و hash partition واقعی در Postgres.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "sharding", "consistent-hashing", "partitioning", "go", "postgres"]
cover = { image = "/images/covers/ds-sharding-consistent-hashing.fa.png", alt = "sharding و consistent hashing", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-replication-quorum/) همان داده را روی چند node کپی کرد. این به دسترس‌پذیری و خواندن کمک می‌کند، ولی هر node هنوز همه‌چیز را نگه می‌دارد و همه‌ی نوشتن‌ها را می‌گیرد. وقتی حجم داده یا نرخ نوشتن از یک ماشین بیشتر شود به {{< term "sharding" "sharding" >}} نیاز دارید: هر کلید روی یک shard زندگی می‌کند. مبانی ring را از [Bloom filter و consistent hashing](/fa/posts/algo-bloom-filter-consistent-hashing/) تکرار نمی‌کنم؛ کد ring آن را کپی کردم و رویش ساختم.

> صادقانه: بخش ۱ تا ۴ **شبیه‌سازی** با Go 1.26 روی یک ماشین است، با randomness ثابت (seed) و فقط شمارش، نه زمان. shardها map درون حافظه‌اند، نه شبکه. بخش ۵ یک Postgres 18.3 واقعی است، ولی روی یک node.

## ۱. shard key انحراف را تعیین می‌کند

۱۰٬۰۰۰ کاربر به ۵۰ tenant تعلق دارند و اندازه‌ی tenantها از یک قانون Zipf با seed ثابت می‌آید. بزرگ‌ترین tenant ‏۳٬۵۱۰ کاربر دارد (۳۵٫۱٪). تعداد ردیف در هر shard با ۴ shard:

```
  range by tenant id   rows per shard [8289 918 480 313] max=8289 max/mean=3.32
  hash by user id      rows per shard [2494 2502 2507 2497] max=2507 max/mean=1.00
  hash by tenant id    rows per shard [635 1463 1627 6275] max=6275 max/mean=2.51
```

range همسایه‌ها را کنار هم نگه می‌دارد (برای range scan خوب است) ولی انحراف را دنبال می‌کند. hash روی کاربر ردیف‌ها را یکنواخت پخش می‌کند، اما کاربران یک tenant همه‌جا پراکنده می‌شوند. hash روی tenant، tenant را روی یک shard نگه می‌دارد و باز هم غول را روی یک shard می‌گذارد. گزینه‌ی سوم directory است: جدول جستجویی که هر tenant را صریح جا می‌دهد. انعطاف‌پذیر است و یک جزء دیگر است که باید در دسترس بماند.

{{< term "hot-key" "hot key" >}} بدتر است: ۱۰۰٬۰۰۰ درخواست که ۲۰٪ آن‌ها به یک کلید مشهور می‌رسد.

```
  write load, salt=1: per shard [39826 20011 20271 19892] max/mean=1.59
  write load, salt=8: per shard [24774 29958 22821 22447] max/mean=1.20, a read of the celebrity touches 8 key(s)
```

هیچ تابع hashای کمک نمی‌کند، چون همان کلید همیشه به همان shard می‌رود. شکستن کلید با پسوند (`celebrity#0..7`) نوشتن را پخش می‌کند و هزینه‌اش شمرده شده: هر خواندن حالا ۸ کلید را می‌خواند.

## ۲. slot ثابت به‌جای جابه‌جایی کلید

افزودن node پنجم به ۱۰۰٬۰۰۰ کلید روی چهار node:

```
  mod N              moved  80097 keys (80.1%)
  ring, 100 vnodes   moved  18522 keys (18.5%)
  16384 slots        moved  19898 keys (19.9%) = 3276 whole slots of 16384
```

{{< term "consistent-hashing" "Consistent hashing" >}} حدود یک‌پنجم را جابه‌جا می‌کند. طراحی با {{< term "hash-slot" "hash slot" >}} تقریباً همین‌قدر جابه‌جا می‌کند، اما به شکل دیگر: کلید همیشه به `hash(key) mod 16384` می‌رسد و یک جدول slotها را به node‌ها می‌دهد. افزودن node کل slotها را دوباره تخصیص می‌دهد، پس می‌شود آن‌ها را یکی‌یکی جابه‌جا، ردیابی و تکرار کرد. تا آنجا که از مستندات می‌دانم Redis Cluster از ۱۶۳۸۴ slot استفاده می‌کند و Kafka کل partitionها را به brokerها می‌دهد؛ هیچ‌کدام را اینجا بررسی نکردم. طبق تجربه‌ی من، جدول slot از ring راحت‌تر اداره می‌شود، چون پاسخ «چه چیزی جابه‌جا می‌شود» صریح است.

## ۳. جابه‌جایی shard بدون گم‌شدن کلید

routing یا کتابخانه‌ی سمت client است که یک shard map نسخه‌دار را می‌خواند، یا proxy که این کار را برایتان می‌کند. در هر دو حالت تغییر map به migration مرحله‌ای نیاز دارد: copy، dual write، verify، cutover، cleanup. پیشرفت (فاز و cursor کپی) پایدار ذخیره می‌شود تا بعد از restart ادامه دهد. در شبیه‌سازی نوشتن زنده ادامه دارد و هر مرحله idempotent است. checker می‌خواهد هر کلید دقیقاً روی یک shard و با آخرین مقدار تأییدشده باشد.

migrator را قبل از تک‌تک عملیاتش crash دادم، restart کردم و چک کردم:

```
  ops in a clean run: 604 (copy=201 dual-write=1 verify=201 cutover=1 cleanup=200 )
  crash before each of the 604+1 points, restart, check: runs=605 violations=0
  negative control (dual write and verify repair removed): runs=605 violations=605
```

negative control مهم است: نشان می‌دهد checker می‌تواند fail کند. شبیه‌سازی delete، خطای شبکه و چند migrator ندارد، پس کمتر از آنچه به نظر می‌رسد ثابت می‌کند. با `go test -race` پاس می‌شود.

## ۴. کار بین shardها

کوئری بدون shard key باید از همه‌ی shardها بپرسد: {{< term "scatter-gather" "scatter-gather" >}}. این حساب سرانگشتی است، نه اندازه‌گیری: ۱٬۰۰۰ کوئری با shard key می‌شود ۱٬۰۰۰ درخواست به shard؛ ۱٬۰۰۰ کوئری با ستون دیگر می‌شود ۴٬۰۰۰ با ۴ shard، ۱۶٬۰۰۰ با ۱۶ و ۶۴٬۰۰۰ با ۶۴. تراکنش بین shardها saga یا two-phase commit می‌خواهد که موضوع یک مقاله‌ی بعدی است.

## ۵. Postgres واقعی: partition یعنی shard نیست

```sql
CREATE TABLE events (... user_id int NOT NULL, created_at timestamptz NOT NULL, ...)
  PARTITION BY HASH (user_id);   -- 4 partitions: MODULUS 4, REMAINDER 0..3
```

۲۰٬۰۰۰ ردیف درج کردم (user id تصادفی و بدون seed، پس اعداد شما فرق می‌کند):

```
 events_p0 |  5087
 events_p1 |  4941
 events_p2 |  5281
 events_p3 |  4691
```

```
 Seq Scan on events_p2 events
   Filter: (user_id = 42)
```

با `created_at > ...` پلن یک `Append` روی هر چهار partition است. یعنی {{< term "partition-pruning" "partition pruning" >}} فقط روی `user_id`؛ خواندن پلن را در [ایندکس B-tree و EXPLAIN ANALYZE](/fa/posts/db-indexes-btree-explain/) ببینید. این {{< term "partitioning" "partitioning" >}} روی یک node است: همان دیسک، همان CPU، همان نقطه‌ی خرابی. پخش partitionها بین nodeها کار `postgres_fdw` یا Citus است؛ فقط اسم می‌برم و اجرایشان نکردم.

## چند نکته‌ی مهم

- shard key را از روی کوئری‌هایتان انتخاب کنید؛ عوض کردنش یعنی جابه‌جایی همه‌چیز.
- بزرگ‌ترین کلید را بسنجید نه میانگین را: max/mean عدد مهم است.
- salt کردن hot key یک خواندن را به چند خواندن تبدیل می‌کند.
- resharding را قبل از اجرای زنده با crash تمرین کنید.

## تمرین

cutover را جلوتر از verify ببرید تا شبیه‌سازی عمداً یک کلید گم کند و ببینید checker کدام نقطه‌های crash را علامت می‌زند.

## قدم بعدی

مقاله‌ی بعد «consensus و Raft» است.
