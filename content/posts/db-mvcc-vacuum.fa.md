+++
date = '2026-12-29T10:00:00+03:30'
draft = false
title = 'MVCC و VACUUM'
description = 'MVCC و VACUUM در PostgreSQL با اجرای واقعی: xmin، xmax و ctid، نسخه‌ی مرده، bloat، VACUUM FULL و تراکنش طولانی که پاک‌سازی را متوقف می‌کند.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "mvcc", "vacuum", "bloat"]
cover = { image = "/images/covers/db-mvcc-vacuum.fa.png", alt = "MVCC و VACUUM", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-isolation-levels-anomalies/) دیدیم هر سطح ایزولاسیون چه قولی می‌دهد. این پست نشان می‌دهد PostgreSQL چطور بدون اینکه خواننده‌ها منتظر نویسنده‌ها بمانند به آن قول عمل می‌کند: {{< term "mvcc" "MVCC" >}}، و هزینه‌ای که باقی می‌گذارد و {{< term "vacuum" "VACUUM" >}} آن را می‌پردازد. همچنین توضیح می‌دهد چرا جدولی با ۲۰۰ هزار ردیف می‌تواند دو برابر لازم دیسک بگیرد؛ مشکلی که از سمت Go ([تراکنش در Go](/fa/posts/go-transactions-patterns/)) ممکن است ببینید و علتش را ندانید.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی با schema مشترک `shop` اجرا شده. روی جدول‌های کوچک دمو autovacuum را خاموش کردم تا چیزی پشت سرم پاک نشود. زمان‌سنجی نیست. مرحله‌های دو session با یک برنامه‌ی کوچک Go اجرا شد، پس ترتیب ثابت است.

## UPDATE یک ردیف جدید می‌نویسد

هر ردیف چند ستون پنهان دارد: `xmin` ({{< term "transaction" "تراکنشی" >}} که این نسخه را ساخته)، `xmax` (تراکنشی که تمامش کرده؛ ۰ یعنی هنوز کسی تمامش نکرده) و `ctid` (جای فیزیکی: صفحه و slot).

```text
SELECT ctid, xmin, xmax, * FROM acct ORDER BY id;     -- 3 rows inserted by tx 810
 (0,1) |  810 |    0 |  1 | ana |  100
 (0,2) |  810 |    0 |  2 | bob |  200
 (0,3) |  810 |    0 |  3 | cy  |  300

UPDATE acct SET balance = 150 WHERE id = 1;
 (0,4) |  811 |    0 |  1 | ana |  150      <- new ctid, new xmin
 (0,2) |  810 |    0 |  2 | bob |  200
 (0,3) |  810 |    0 |  3 | cy  |  300
```

ردیف از slot ۱ به slot ۴ رفت. افزونه‌ی `pageinspect` نشان می‌دهد واقعاً روی صفحه چه هست:

```text
SELECT lp, t_xmin, t_xmax, t_ctid FROM heap_page_items(get_raw_page('acct',0));
 1 | 810 | 811 | (0,4)     <- old version: ended by 811, points to the new one
 2 | 810 |   0 | (0,2)
 3 | 810 |   0 | (0,3)
 4 | 811 |   0 | (0,4)     <- current version
```

نسخه‌ی قدیمی هنوز آنجاست. هر کوئری با یک snapshot کار می‌کند و فقط نسخه‌هایی را می‌بیند که تراکنشِ قابل‌دیدن ساخته و تراکنشِ قابل‌دیدن تمامشان نکرده است. خواننده‌ای که پیش از commit تراکنش ۸۱۱ شروع شده باشد هنوز ۱۰۰ می‌خواند. به همین ترتیب خواننده و نویسنده جلوی هم را نمی‌گیرند.

update که rollback شود هم آشغال باقی می‌گذارد: `bob` را به ۹۹۹ تغییر دادم و rollback کردم. slot ۵ نسخه‌ی رهاشده را نگه می‌دارد و ردیف قابل‌دیدن دوباره `(0,2)` است با `xmax = 812`، تراکنشی که هرگز commit نشد، پس نادیده گرفته می‌شود.

## نسخه‌ی مرده و VACUUM

نسخه‌ای که دیگر هیچ‌کس نمی‌بیند {{< term "dead-tuple" "نسخه‌ی مرده" >}} (dead tuple) است. بعد از `pg_stat_force_next_flush()` (آمار با کمی تأخیر به view می‌رسد، برای همین flush را اجباری کردم) `pg_stat_user_tables` نشان داد `n_dead_tup = 2`. بعد `VACUUM acct`:

```text
 lp | lp_flags | t_xmin | t_xmax | t_ctid
  1 |        2 |        |        |            <- redirect to slot 4
  2 |        1 |    810 |    812 | (0,5)      <- live, stale xmax of the aborted tx
  3 |        1 |    810 |      0 | (0,3)
  4 |        1 |    811 |      0 | (0,4)
```

داده‌ی مرده رفت، slot ۵ آزاد شد و `n_dead_tup` به ۰ برگشت. slot ۱ به redirect تبدیل شد (`lp_flags = 2`، طبق مستندات pageinspect)؛ این یک {{< term "hot-update" "HOT update" >}} بود: نسخه‌ی جدید در همان صفحه ماند و ورودی جدیدی در ایندکس نیامد. این فقط وقتی ممکن است که ستون ایندکس‌شده تغییر نکند و در صفحه جا باشد. اینجا `n_tup_hot_upd = 2` از `n_tup_upd = 2` بود.

## bloat با عدد

`orders` (۲۰۰ هزار ردیف، با primary key) را در `orders_copy` کپی کردم و همه‌ی ردیف‌ها را update کردم:

```text
                         heap            pages   pkey
fresh                    13 MB            1677   4408 kB
after UPDATE (all rows)  26 MB            3353   8792 kB    n_dead_tup = 200000, n_tup_hot_upd = 0
after VACUUM             26 MB            3353   8792 kB    n_dead_tup = 0
after a 2nd UPDATE       26 MB            3353   8792 kB    (space reused)
after VACUUM FULL        13 MB            1677   4408 kB
```

heap و ایندکس دو برابر شدند: این همان {{< term "table-bloat" "bloat جدول" >}} است. HOT نداشتیم چون صفحه‌ها پر بودند. `VACUUM` ساده فایل را کوچک نکرد؛ فقط فضا را قابل استفاده‌ی دوباره کرد و update کامل بعدی هم روی ۲۶ مگابایت ماند. `VACUUM FULL` جدول را در فایل تازه بازنویسی کرد و به ۱۳ مگابایت رسید.

بهایش: طبق مستندات `VACUUM FULL` قفل `ACCESS EXCLUSIVE` می‌گیرد. تعارض را با خواننده‌ای که روی جدولی ۱۰ هزار ردیفی تراکنش باز دارد و `lock_timeout = 300ms` امتحان کردم:

```text
VACUUM hold      -> ok
VACUUM FULL hold -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
```

پس روی جدول پرترافیک، `VACUUM FULL` تا پایان کار جلوی خواندن و نوشتن را می‌گیرد. `VACUUM` ساده نمی‌گیرد.

## تراکنش طولانی پاک‌سازی را عقب می‌اندازد

یک session با `REPEATABLE READ` snapshot گرفت (`sum = 631116377`). session دیگر هر ۱۰۰۰۰ ردیف را update کرد. بعد `VACUUM (VERBOSE)` گفت:

```text
tuples: 0 removed, 20000 remain, 10000 are dead but not yet removable
removable cutoff: 826, which was 1 XIDs old when operation ended
```

نسخه‌های قدیمی برای همه مرده‌اند، جز برای همان یک snapshot، پس چیزی حذف نمی‌شود. آن session هنوز مجموع قدیمی را می‌بیند. بعد از commit آن:

```text
tuples: 10000 removed, 10000 remain, 0 are dead but not yet removable
```

یک اتصال فراموش‌شده در حالت `idle in transaction` می‌تواند جدول‌های کل دیتابیس را متورم کند.

## autovacuum و visibility map

VACUUM را کم‌تر دستی می‌زنید: {{< term "autovacuum" "autovacuum" >}} این کار را می‌کند. طبق مستندات وقتی ردیف‌های مرده از `autovacuum_vacuum_threshold` به‌علاوه‌ی `autovacuum_vacuum_scale_factor` ضربدر تعداد ردیف‌ها بیشتر شود جدول را vacuum می‌کند؛ اینجا `SHOW` مقدارهای ۵۰ و ۰.۲ را داد. تنظیمش نکردم.

VACUUM همچنین {{< term "visibility-map" "visibility map" >}} را پر می‌کند (اجرای دوم بالا: «109 pages set all-visible»)، و همین باعث می‌شود {{< term "index-only-scan" "index-only scan" >}} بتواند از heap رد شود، مثل [ایندکس پوششی](/fa/posts/db-composite-partial-covering-indexes/).

## چند نکته‌ی مهم

- هر update یک نسخه باقی می‌گذارد؛ جدول پر‌update به VACUUM نیاز دارد تا عقب نماند.
- فقط چیزی را update کنید که تغییر کرده؛ دست زدن به ستون ایندکس‌شده HOT را ممکن نمی‌کند.
- برای تراکنش‌های طولانی و `idle in transaction` هشدار بگذارید.
- `VACUUM FULL` جدول را قفل می‌کند؛ گزینه‌های سبک‌تر را امتحان نکردم.

## تمرین

جدولی با ۱۰۰ هزار ردیف بسازید، نیمی از آن را update کنید و `n_dead_tup`، `pg_relation_size`، `VACUUM` و `VACUUM FULL` را ببینید. بعد همین را با یک session باز `REPEATABLE READ` تکرار کنید.

## قدم بعدی

پست بعدی این سری: قفل و deadlock در دیتابیس.
