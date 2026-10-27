+++
date = '2027-03-09T10:00:00+03:30'
draft = false
title = 'connection pool و حالت‌های خرابی'
description = 'connection pool در PostgreSQL با محدودیت واقعی max_connections و دمو با pgxpool: صف انتظار، connection نشتی، idle in transaction و timeoutها.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "connection-pooling", "pgxpool", "timeouts"]
cover = { image = "/images/covers/db-connection-pooling.fa.png", alt = "connection pool و حالت‌های خرابی", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-backup-restore-pitr/) مطمئن شدیم می‌توانیم داده را برگردانیم. این پست درباره‌ی رسیدن به خود داده است. هر query یک connection می‌خواهد و PostgreSQL برای هر کدام یک process جدا در سرور می‌سازد، پس تعدادشان محدود است. {{< term "connection-pool" "connection pool" >}} بین کد شما و این محدودیت می‌نشیند. در [Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/) از آن استفاده کردم؛ اینجا عمداً خرابش می‌کنم. به [تراکنش و ACID](/fa/posts/db-transactions-acid/) و [تراکنش در Go](/fa/posts/go-transactions-patterns/) هم وصل است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی روی loopback با `max_connections = 10` و یک برنامه‌ی Go با `pgxpool` (نسخه‌ی pgx 5.11.0) اجرا شد. ماشین شلوغ بود، پس زمان‌سنجی نیست؛ فقط تعداد و خطا.

## سقف سرور

آن‌قدر connection باز کردم که سرور رد کرد:

```text
connection 10 failed: ... FATAL: sorry, too many clients already (SQLSTATE 53300)
open connections: 9
max_connections: 10  client backends: 10
```

نُه تا مال من بود؛ جای دهم را connection بیکار خود launcher گرفته بود (در `pg_stat_activity` دیدمش). با یک role معمولی سقف زودتر می‌رسد، چون `superuser_reserved_connections` (پیش‌فرض ۳) چند جا را برای superuser نگه می‌دارد:

```text
connection 7 failed: ... FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute (SQLSTATE 53300)
open connections: 6
```

ده سرویس با pool بیست‌تایی همین حالا ۲۰۰ connection می‌خواهند. پس اندازه‌ی pool بودجه‌ای مشترک بین همه‌ی processهاست، نه سلیقه‌ی هر سرویس.

## pool با ۴ connection و ۲۰ goroutine

`MaxConns = 4` و ۲۰ goroutine که هر کدام `pool.Acquire` را صدا می‌زنند و connection را نگه می‌دارند تا یک gate باز کنم. `pool.Stat()` شمارنده‌ی «منتظر» ندارد، پس goroutineها را خودم شمردم:

```text
while holding: goroutines=20 got=4 waiting=16 acquired=4 idle=0 total=4 max=4
after: acquireCount=20 emptyAcquireCount=20 newConnsCount=4 acquired=0 idle=4 total=4
server-side client backends after 20 goroutines: 5
```

شانزده caller داخل `Acquire` منتظرند و سرور فقط ۴ connection از من دید (عدد ۵ شامل connection خود launcher است). `EmptyAcquireCount` تعداد acquireهایی است که pool را خالی دیدند و باید صبر می‌کردند؛ اینجا هر ۲۰ تا، چون همه‌ی goroutineها قبل از آزادشدن اولین connection درخواست دادند. بعد از release، ۴ connection برای استفاده‌ی دوباره بیکار می‌مانند.

## نشتی: فراموش‌کردن release

با `MaxConns = 1` یک connection گرفتم و هرگز `Release` نزدم. caller بعدی خطا نمی‌گیرد؛ منتظر می‌ماند تا context تمام شود:

```text
second Acquire: context deadline exceeded
pool.Exec: context deadline exceeded
acquired=1 idle=0 canceledAcquireCount=2
```

حتی `pool.Exec` هم گیر می‌کند، چون داخلش acquire می‌کند. اگر context {{< term "deadline" "deadline" >}} نداشت، تا ابد بلاک می‌شد. در اجرای اول، آخر برنامه هم `Release` را فراموش کرده بودم و `pool.Close()` آن‌قدر ماند که runtime گفت «all goroutines are asleep - deadlock!». بلافاصله بعد از هر `Acquire` موفق `defer c.Release()` بنویسید و همیشه context با timeout بدهید.

## Idle in transaction

یک connection را می‌شود گرفت و استفاده نکرد. یک transaction شروع کردم، `select 1` زدم و ایستادم. session دیگر این را دید:

```text
state="idle in transaction" last_query="select 1"
```

این connection از pool رفته است و طبق مستندات، transaction باز snapshot خودش را هم نگه می‌دارد که جلوی پاک‌شدن ردیف‌های مرده‌ی جدیدتر توسط [VACUUM](/fa/posts/db-mvcc-vacuum/) را می‌گیرد. علت رایج: صدا زدن یک HTTP API وسط transaction، یا `return`ی که `Rollback` را رد می‌کند.

## نگهبان‌ها

دو تنظیم این باگ‌ها را به خطا تبدیل می‌کنند. هر دو را برای session تنظیم کردم:

```text
SET idle_in_transaction_session_timeout = '1s'
after 1.5 s idle, next statement: FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)

SET statement_timeout = '200ms'; select pg_sleep(5)
slow statement: ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
same connection afterwards: <nil> 1
```

اولی connection را می‌کُشد، پس pool باید آن را دور بیندازد و تازه باز کند. دومی فقط statement را لغو می‌کند. انتظار برای قفل {{< term "lock-timeout" "lock_timeout" >}} جدا دارد. در production آن‌ها را روی role یا در connection string بگذارید، نه دستی.

## pool به سبک PgBouncer

{{< term "pgbouncer" "PgBouncer" >}} را اجرا نکردم (اینجا در دسترس نیست)، پس این بخش از مستندات آن است نه از اجرا. یک pooler بیرونی اجازه می‌دهد هزاران connection کلاینت چند connection سرور را share کنند. در حالت session هر کلاینت در کل جلسه یک connection سرور نگه می‌دارد. در حالت transaction فقط در طول transaction یکی می‌گیرد که connectionها را خیلی فشرده‌تر استفاده می‌کند، ولی نباید به وضعیت session (`SET`، قفل advisory در سطح session) بین transactionها تکیه کرد.

## چند نکته‌ی مهم

- مجموع اندازه‌ی poolهای همه‌ی سرویس‌ها باید زیر `max_connections` منهای جاهای رزرو بماند.
- برای `Acquire` و queryها همیشه context با deadline بدهید.
- بلافاصله بعد از acquire یا begin، `defer Release()` (یا `Rollback()`) بنویسید.
- `idle_in_transaction_session_timeout` و `statement_timeout` را پیش‌فرض بگذارید و وقتی فعال شدند log کنید.
- pool بزرگ‌تر یعنی دیتابیس سریع‌تر نیست؛ اگر ۴ connection آن را اشباع می‌کنند، ۴۰ تا فقط داخل سرور صف می‌شوند.

## تمرین

نشتی را با `MaxConns = 2` و ۵ goroutine بازسازی کنید که یکی `Release` را فراموش می‌کند. مقدار `acquired`، `idle` و `canceledAcquireCount` را پیش‌بینی کنید، بعد اجرا کنید و مقایسه کنید.

## قدم بعدی

پست بعد «case study: پیدا کردن و رفع یک query کند» است که `EXPLAIN` و ابزارهای این سری را روی یک مسئله به کار می‌بریم.
