+++
date = '2027-03-09T10:00:00+03:30'
draft = false
title = 'connection pool و حالت‌های خرابی'
description = 'connection pool در PostgreSQL با محدودیت واقعی max_connections و دمو با pgxpool: صف انتظار، connection نشتی، idle in transaction و timeoutها.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "connection-pooling", "pgxpool", "timeouts"]
cover = { image = "/images/covers/db-connection-pooling.fa.png", alt = "connection pool و حالت‌های خرابی", hiddenInSingle = true }
+++

سرویس شما با سه instance خوب کار می‌کند. برای تحمل یک روز شلوغ آن را به سی تا می‌رسانید و ناگهان درخواست‌ها با `sorry, too many clients already` شکست می‌خورند. پایگاه داده کند نیست و CPU اش بیکار است. فقط حاضر نیست یک اتصال دیگر قبول کند. اتصال به پایگاه داده چیز ارزانی به نظر می‌رسد، یک خط به سرور، ولی اولین منبعی است که تمام می‌شود و ارزش کمی فکر کردن دارد.

[backup، restore و PITR](/fa/posts/db-backup-restore-pitr/) مطمئن شد داده برمی‌گردد؛ این پست درباره‌ی این است که اصلاً به داده برسیم. {{< term "connection-pool" "connection pool" >}} جواب استاندارد است: به‌جای باز کردن یک connection برای هر query، برنامه در شروع چند connection باز می‌کند، برای هر کار یکی را قرض می‌دهد و بعدش پس می‌گیرد. در [Postgres با pgx و sqlc](/fa/posts/go-postgres-pgx-sqlc/) از pool استفاده کردم؛ اینجا عمداً خرابش می‌کنم تا ببینم چطور از کار می‌افتد. به [تراکنش و ACID](/fa/posts/db-transactions-acid/) و [تراکنش در Go](/fa/posts/go-transactions-patterns/) هم گره می‌خورد.

> همه‌چیز روی PostgreSQL 18.3 واقعی روی loopback با `max_connections = 10` و یک برنامه‌ی Go با `pgxpool` (نسخه‌ی pgx 5.11.0) اجرا شد؛ این یک pool است که داخل خود process برنامه زندگی می‌کند. برای این نسخه‌ی پست دمو را دوباره اجرا کردم. ماشین شلوغ بود، پس زمان‌سنجی نیست؛ فقط تعداد و خطا. PgBouncer اینجا نصب نیست و اجرایش نکردم؛ بخش مربوط به آن از مستندات است.

## چرا connection گران است

PostgreSQL هر connection را با یک process جدا در سیستم‌عامل سرویس می‌دهد. سرور یک thread pool ندارد که کار را بین کلاینت‌ها پخش کند: وقتی کلاینتی وصل می‌شود، process اصلی (postmaster) یک process تازه فقط برای او شروع می‌کند و آن process تا وقتی connection هست زنده می‌ماند. نتیجه‌اش ساده است: connection بیشتر یعنی process بیشتر، هرکدام با حافظه‌ی خودش و سهم خودش از توجه scheduler، حتی وقتی همه بیکارند. برای همین سرور یک سقف سخت دارد، `max_connections`، و مقدار پیش‌فرضش بزرگ نیست.

ادعای «یک process برای هر connection» را روی سرور دمو وارسی کردم. با `ps` process هایی را شمردم که عنوانشان `postgres: app orders ...` است، یعنی همان طور که PostgreSQL process یک کلاینت را برچسب می‌زند. بعد سه connection دیگر باز کردم که هرکدام `select pg_sleep(8)` اجرا می‌کردند:

```text
client-backend processes before: 1
with 3 more connections: 4
after the sleeps ended: 1
```

هر connection جدید یک process اضافه کرد و وقتی بسته شدند process ها رفتند. (آن `1` یک connection است که launcher دمو باز نگه می‌دارد و در بخش بعد مهم می‌شود.) این همان هزینه‌ای است که pool از آن می‌گریزد: تعداد کم و ثابتی از این process ها را نگه می‌دارد و دوباره استفاده می‌کند.

## سقف سرور

برای دیدن سقف، آن‌قدر connection باز کردم که سرور رد کرد:

```text
connection 10 failed: ... FATAL: sorry, too many clients already (SQLSTATE 53300)
open connections: 9
max_connections: 10  client backends: 10
```

سقف ۱۰ است و تلاش دهم من شکست خورد. نُه تا مال من بود؛ جای دهم را connection بیکارِ خود launcher گرفته بود (`pg_stat_activity` یک session با `SELECT 1` نشان می‌دهد که مال من نیست). با یک role معمولی، برخلاف superuserای که بالا استفاده کردم، سقف زودتر می‌رسد، چون `superuser_reserved_connections` (به‌طور پیش‌فرض ۳) جاهایی نگه می‌دارد که فقط superuser می‌تواند استفاده کند. یک role بدون حق superuser ساختم و دوباره امتحان کردم:

```text
connection 7 failed: ... FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute (SQLSTATE 53300)
open connections: 6
```

شش connection من به‌علاوه‌ی یکی launcher، هفت جایی را پر می‌کنند که role معمولی می‌تواند استفاده کند (۱۰ منهای ۳ رزرو). حالا یک استقرار واقعی را در نظر بگیرید: ده سرویس با pool ی ۲۰ تایی از همین حالا ۲۰۰ connection می‌خواهند. پس اندازه‌ی pool یک بودجه است که همه‌ی process هایی که به این پایگاه داده وصل می‌شوند با هم خرج می‌کنند، نه هوس هر process. سی instance با pool ی ۱۰ تایی ۳۰۰ connection می‌شود.

## pool با ۴ connection و ۲۰ goroutine

وقتی تعداد درخواست‌کننده‌ها از connectionها بیشتر است، pool چه می‌کند؟ در دمو `MaxConns = 4` است و ۲۰ goroutine هرکدام `pool.Acquire` را صدا می‌زنند و connection را نگه می‌دارند تا من دروازه‌ای را باز کنم. `pool.Stat()` شمارنده‌ی «منتظر» ندارد، پس goroutineها را خودم شمردم:

```text
while holding: goroutines=20 got=4 waiting=16 acquired=4 idle=0 total=4 max=4
after: acquireCount=20 emptyAcquireCount=20 newConnsCount=4 acquired=0 idle=4 total=4
server-side client backends after 20 goroutines: 5
```

در خط اول فقط ۴ goroutine connection گرفتند (`got=4`) و ۱۶ تای دیگر داخل `Acquire` منتظرند. چیزی شکست نمی‌خورد؛ درخواست‌کننده‌ها فقط در صف می‌ایستند. هر ۴ connection قرض داده شده (`acquired=4`) و هیچ‌کدام بیکار نیست. در خط دوم، بعد از باز شدن دروازه، هر ۲۰ acquire تمام شد (`acquireCount=20`)، ولی فقط ۴ connection ساخته شد (`newConnsCount=4`). `emptyAcquireCount` تعداد acquireهایی است که pool را خالی دیدند و مجبور به انتظار شدند؛ اینجا هر ۲۰ تاست، چون همه‌ی goroutineها پیش از آزاد شدن هر connection درخواست کردند. حالا ۴ connection بیکار و آماده‌ی استفاده‌ی دوباره‌اند. خط آخر سمت سرور است: فقط ۴ connection از من دید (۵ تا backend یعنی با connection launcher)، نه ۲۰.

pool بیست درخواست‌کننده را به ۴ process در سرور تبدیل کرد. برای وارسی این با کارهای کوتاه، که به سرویس واقعی نزدیک‌تر است، یک نسخه‌ی موقت اجرا کردم (آن را در یک کپی دورریختنی از دمو اضافه کردم؛ در دایرکتوری دمو نیست): ۲۰۰ goroutine که هرکدام یک `select pg_sleep(0.02)` را از یک pool ی ۴ تایی اجرا می‌کنند، در حالی که یک connection جدا هر چند میلی‌ثانیه تعداد client backendها را نمونه می‌گرفت:

```text
200 goroutines, pool of 4: completed=200 newConnsCount=4 maxClientBackendsSeen=6
```

هر ۲۰۰ تا تمام شدند و در کل ۴ connection ساخته شد. بیشترین تعداد client backend که نمونه‌گیر دید ۶ بود: ۴ تای من، یکی launcher و connection خود نمونه‌گیر. (دو بار اجرایش کردم و همین آمد.) سرور هرگز بیشتر از آن ۴ تا برای ۲۰۰ درخواست‌کننده‌ی من کار نداشت.

## نشت: فراموش کردن Release

خطر قرض دادن این است که کسی پس نیاورد. با `MaxConns = 1` یک connection گرفتم و هرگز `Release` را صدا نزدم. درخواست‌کننده‌ی بعدی شکست نمی‌خورد، منتظر می‌ماند تا context اش تمام شود:

```text
second Acquire: context deadline exceeded
pool.Exec: context deadline exceeded
acquired=1 idle=0 canceledAcquireCount=2
```

هر دو انتظار (`Acquire` و `pool.Exec` که داخلش acquire می‌کند) بعد از ۵۰۰ میلی‌ثانیه با `context deadline exceeded` تمام شدند، چون به آن‌ها context با timeout دادم. `canceledAcquireCount=2` همین دو انتظار لغوشده را می‌شمارد. بدون {{< term "deadline" "deadline" >}} روی context تا ابد بلاک می‌شدند و نشتی در یک مسیر درخواست آهسته آهسته سرویس را منجمد می‌کند. در اجرای اولم آخر برنامه هم `Release` را فراموش کردم و `pool.Close()` معلق ماند تا runtime ی Go پیام «all goroutines are asleep - deadlock!» را داد. همیشه بلافاصله بعد از `Acquire` موفق `defer c.Release()` بنویسید، و همیشه context با timeout بدهید.

## Idle in transaction

یک connection بدون نشت هم می‌تواند از دست برود. sessionای که تراکنش را شروع کرده و دیگر دستوری نمی‌فرستد {{< term "idle-in-transaction" "idle in transaction" >}} است: pool فکر می‌کند مشغول است، پس هیچ‌کس دیگر نمی‌تواند از آن استفاده کند. من تراکنشی شروع کردم، `select 1` را اجرا کردم و ایستادم. session دیگری دید:

```text
seen from another session: state="idle in transaction" last_query="select 1"
```

آن connection برای pool از دست رفته. طبق مستندات، یک تراکنش باز snapshot خودش را هم نگه می‌دارد، که [VACUUM](/fa/posts/db-mvcc-vacuum/) را از پاک کردن ردیف‌های مرده‌ی جدیدتر از آن بازمی‌دارد. دلیل رایجش یک فراخوانی HTTP وسط تراکنش است، یا یک `return` زودهنگام که `Rollback` را رد می‌کند.

## حفاظ‌ها

دو تنظیم این باگ‌ها را به‌جای توقف بی‌صدا به خطا تبدیل می‌کنند. هر دو را برای یک session گذاشتم:

```text
SET idle_in_transaction_session_timeout = '1s'
after 1.5 s idle, next statement: FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
idle-in-transaction sessions now: 0

SET statement_timeout = '200ms'; select pg_sleep(5)
slow statement: ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
same connection afterwards: <nil> 1
```

اولی session فراموش‌شده را می‌کشد: بعد از ۱٫۵ ثانیه سرور آن را بسته بود (تعداد sessionهای idle-in-transaction به ۰ رسید) و دستور بعدی روی آن با `FATAL` شکست خورد. pool باید آن connection را دور بیندازد و یکی تازه باز کند. دومی فقط دستور را لغو می‌کند و connection قابل استفاده می‌ماند (`<nil> 1` یعنی `select 1` بعدی کار کرد و ۱ برگرداند). انتظار برای قفل‌ها هم {{< term "lock-timeout" "lock_timeout" >}} خودش را دارد. در پروداکشن این‌ها را برای هر role یا در connection string بگذارید، نه دستی در هر session.

## pooler بیرونی چه چیزی را عوض می‌کند

{{< term "pgbouncer" "PgBouncer" >}} را اجرا نکردم (اینجا در دسترس نیست)، پس این بخش از مستندات آن است، نه از یک اجرا. poolهای بالا داخل هر process برنامه زندگی می‌کنند: سی instance با ۱۰ connection هرکدام باز هم ۳۰۰ connection سروری می‌شود. pooler بیرونی برنامه‌ی جدایی است که بین همه‌ی برنامه‌ها و PostgreSQL قرار می‌گیرد، تا هزاران connection کلاینتی چند connection سروری را با هم تقسیم کنند. در حالت session، کلاینت یک connection سروری را در کل session اش نگه می‌دارد. در حالت transaction فقط به اندازه‌ی طول یک تراکنش آن را می‌گیرد و بعد پس می‌دهد، که connectionها را خیلی فشرده‌تر جا می‌دهد. اجرای ۲۰۰ goroutine بالا همین ایده در مقیاس کوچک است: درخواست‌کننده‌های زیاد، که هرکدام فقط تا وقتی کار می‌کنند connection را نگه می‌دارند، روی چند connection واقعی. هزینه‌ی حالت transaction این است که نباید بین تراکنش‌ها به state ی session (مثل `SET` و قفل‌های advisory سطح session) تکیه کرد، چون تراکنش بعدی ممکن است روی connection سروری دیگری اجرا شود.

## بودجه‌ی connection و تله‌هایش

- **مجموع اندازه‌ی poolها در همه‌ی سرویس‌ها باید زیر `max_connections` منهای جاهای رزرو بماند.** همه‌ی instance های همه‌ی سرویس‌ها را بشمارید، و migrationها و ابزارهای مدیریتی که وصل می‌شوند را هم.
- **برای `Acquire` و queryها همیشه context با deadline بدهید،** تا نشتی به خطا تبدیل شود نه به قفل شدن.
- **بلافاصله بعد از acquire یا begin، `defer Release()` (یا `Rollback()`) بنویسید.**
- **`idle_in_transaction_session_timeout` و `statement_timeout` را پیش‌فرض بگذارید و وقتی فعال می‌شوند لاگ کنید.**
- **pool بزرگ‌تر پایگاه داده‌ی سریع‌تر نیست.** اگر ۴ connection آن را اشباع کرده‌اند، ۴۰ تا فقط داخل سرور صف می‌بندند و process های بیشتری خرج می‌کنند.

## تمرین

نشتی را با `MaxConns = 2` و ۵ goroutine بازتولید کنید که یکی‌شان `Release` را فراموش می‌کند. `acquired`، `idle` و `canceledAcquireCount` را پیش‌بینی کنید، بعد اجرا کنید و مقایسه کنید.

## قدم بعدی

قدم بعدی [case study: پیدا کردن و رفع یک query کند](/fa/posts/db-slow-query-case-study/) است، که در آن `EXPLAIN` و ابزارهای این سری را روی یک مسئله به کار می‌بریم، از اولین شکایت تا رفع.
