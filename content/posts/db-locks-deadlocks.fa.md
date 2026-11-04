+++
date = '2027-01-04T10:00:00+03:30'
draft = false
title = 'قفل و deadlock در دیتابیس'
description = 'قفل و deadlock در PostgreSQL با اجرای واقعی دو session: قفل ردیف، pg_locks، lock_timeout، یک deadlock واقعی و راه‌حلش، صف SKIP LOCKED و ALTER TABLE.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "locks", "deadlock", "concurrency"]
cover = { image = "/images/covers/db-locks-deadlocks.fa.png", alt = "قفل و deadlock در دیتابیس", hiddenInSingle = true }
+++

یک تراکنش باز که فقط از یک جدول خوانده، به‌علاوه‌ی یک `ALTER TABLE` که پشتش منتظر مانده، کافی است تا حتی یک `SELECT` ساده‌ی بی‌گناه هم شکست بخورد. بیشتر ماجراهای «دیتابیس گیر کرده» همین شکل را دارند: {{< term "lock" "قفلی" >}} که کسی آزادش نکرده و بقیه پشتش صف بسته‌اند.

قفل یعنی یک session قبل از دست زدن به داده صبر کند تا session دیگری که آن را در دست دارد کارش را تمام کند. ساده‌ترین تصویرش اتاقی با یک کلید است: تا کسی که داخل است بیرون نیاید، نفر بعدی پشت در می‌ایستد. در [MVCC و VACUUM](/fa/posts/db-mvcc-vacuum/) دیدیم که {{< term "mvcc" "MVCC" >}} خواننده‌ها و نویسنده‌ها را از کنار هم رد می‌کند، چون هر کدام نسخه‌ی خودش را می‌بیند. ولی دو نویسنده روی یک ردیف نمی‌توانند هم‌زمان کار کنند و یکی باید صبر کند. این نوشته درباره‌ی همین صبر کردن است: چه چیزهایی قفل می‌شوند، کدام قفل‌ها با هم تداخل دارند، چطور بفهمیم چه کسی جلوی چه کسی را گرفته، و دو ماجرایی که تقریباً هر تیمی یک بار تجربه می‌کند: deadlock و صف پشت `ALTER TABLE`. پایه‌ی کار [تراکنش و ACID](/fa/posts/db-transactions-acid/) و [سطح‌های ایزولاسیون و ناهنجاری‌ها](/fa/posts/db-isolation-levels-anomalies/) است.

> همه‌چیز را روی یک PostgreSQL 18.3 واقعی دوباره اجرا کرده‌ام. دو یا سه session را یک برنامه‌ی کوچک Go با ترتیب ثابت اجرا می‌کند، پس نتیجه‌ها قطعی‌اند. شماره‌ی process‌ها و تراکنش‌ها در هر اجرا فرق می‌کند. چون ماشین مشغول بود، زمان‌سنجی در کار نیست؛ همه‌چیز فقط درباره‌ی رفتار قفل‌هاست.

## قفل ردیف

شروع از کوچک‌ترین قفل: قفل یک ردیف. session A روی جدول کوچک `acct` دستور `SELECT ... WHERE id = 1 FOR UPDATE` را می‌زند و تراکنش را باز نگه می‌دارد. `FOR UPDATE` یعنی «این ردیف را برای من قفل کن، چون قصد دارم عوضش کنم». حالا B سه کار مختلف می‌کند:

```text
B: UPDATE row 1       -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
B: FOR UPDATE NOWAIT  -> ERROR: could not obtain lock on row in relation "acct" (SQLSTATE 55P03)
B: SKIP LOCKED ids    -> [2 3]
```

- **`UPDATE` روی همان ردیف:** B منتظر می‌ماند. به‌طور پیش‌فرض PostgreSQL مهلتی برای این انتظار ندارد و تا ابد صبر می‌کند؛ من `lock_timeout = 300ms` گذاشتم تا بعد از ۳۰۰ میلی‌ثانیه منصرف شود. همین خطا (`55P03`) را می‌بینید.
- **`FOR UPDATE NOWAIT`:** اصلاً صبر نمی‌کند و فوراً خطا می‌دهد که قفل ردیف را نتوانستم بگیرم.
- **`FOR UPDATE SKIP LOCKED`:** ردیف قفل‌شده را رد می‌کند و فقط ردیف‌هایی را برمی‌گرداند که کسی نگرفته: `[2 3]`. بعداً از این برای صف کار استفاده می‌کنیم.

حالا سؤال بعدی: همه‌ی قفل‌های ردیف با هم تداخل ندارند. PostgreSQL چهار حالت قفل ردیف دارد. من هر حالت را برای A گرفتم و B را با هر چهار حالت (همه با `NOWAIT` تا معطل نشود) امتحان کردم. «blocked» یعنی B نتوانست قفل را بگیرد:

```text
A holds \ B asks    FOR KEY SHARE      FOR SHARE          FOR NO KEY UPDATE  FOR UPDATE
FOR KEY SHARE       ok                 ok                 ok                 blocked
FOR SHARE           ok                 ok                 blocked            blocked
FOR NO KEY UPDATE   ok                 blocked            blocked            blocked
FOR UPDATE          blocked            blocked            blocked            blocked
```

هر سطر چیزی است که A نگه داشته و هر ستون چیزی که B می‌خواهد. قفل‌های ضعیف‌تر (بالا و چپ) با هم کنار می‌آیند و قوی‌ترین، `FOR UPDATE`، با همه تداخل دارد. چیزی که در عمل مهم است: یک `UPDATE` ساده که ستون‌های کلید را عوض نمی‌کند `FOR NO KEY UPDATE` می‌گیرد. این قفل با `FOR KEY SHARE` تداخل ندارد، و `FOR KEY SHARE` همان قفلی است که بررسی {{< term "foreign-key" "کلید خارجی" >}} روی ردیف والد می‌گیرد. برای همین، وقتی A روی ردیف ۱ قفل `NO KEY UPDATE` را نگه داشته بود، `INSERT INTO note (acct_id) VALUES (1)` در B بی‌مشکل اجرا شد. ولی وقتی A قفل `FOR UPDATE` گرفته بود، همان `INSERT` گیر کرد (و با `lock_timeout` خطا داد).

## قفل سطح جدول

هر دستور علاوه بر ردیف‌ها یک قفل روی خود جدول هم می‌گیرد، که نشان می‌دهد این دستور با چه دستورهای دیگری سازگار است. از `pg_locks` برای backend مربوط به session A خواندم:

```text
after SELECT:                       AccessShareLock
after UPDATE:                       RowExclusiveLock
after ALTER TABLE ... ADD COLUMN:   AccessExclusiveLock
```

`SELECT` فقط ملایم‌ترین قفل را می‌گیرد، `UPDATE` کمی قوی‌تر، و `ALTER TABLE` قوی‌ترین. طبق مستندات، `AccessExclusiveLock` با همه‌ی حالت‌های دیگر تداخل دارد، حتی با `AccessShareLock` یک `SELECT`. برای همین `ALTER TABLE` و `VACUUM FULL` می‌توانند جدول را متوقف کنند. من این را دیدم: A تراکنشی باز داشت که `acct` را خوانده بود، B دستور `VACUUM FULL acct` را زد، و `pg_locks` نشان داد A قفل `AccessShareLock` را نگه داشته و قفل `AccessExclusiveLock` مربوط به B با `granted = false` منتظر مانده است:

```text
   false | AccessShareLock | true
   true | AccessExclusiveLock | false
```

ستون اول می‌گوید این ردیف مال B است یا نه (`true` یعنی B)، ستون دوم نوع قفل و ستون سوم اینکه قفل گرفته شده یا هنوز منتظر است. با commit شدن A، کار B تمام شد. (یک نکته‌ی کوچک: `VACUUM FULL` را نمی‌شود داخل بلوک تراکنش اجرا کرد؛ PostgreSQL خطای `VACUUM cannot run inside a transaction block` می‌دهد، برای همین آن را از session دیگر زدم.)

## چه کسی جلوی چه کسی را گرفته؟

وقتی سیستم گیر کرده، مهم‌ترین سؤال همین است. A ردیف ۲ را update کرد و تراکنش را باز نگه داشت. B همان ردیف را update کرد و منتظر ماند. از session سوم این را پرسیدم:

```text
A is pid 56715, B is pid 56717
   56717 | Lock | transactionid | [56715] | UPDATE acct SET balance=balance+1 WHERE
   locks: transactionid | ShareLock | false
```

ستون‌های خط اول به ترتیب برای B است: `pid`، نوع انتظار (`wait_event_type`)، نام انتظار (`wait_event`)، فهرست process‌هایی که جلوی B را گرفته‌اند (`pg_blocking_pids`) و ابتدای کوئری. `pg_blocking_pids` مستقیم جواب می‌دهد: process شماره‌ی ۵۶۷۱۵، یعنی A. خط دوم نشان می‌دهد B منتظر شماره‌ی تراکنش A است، نه خود ردیف. قفل ردیف در PostgreSQL این‌طور کار می‌کند: نویسنده‌ی ردیف را شماره‌ی تراکنشش مشخص می‌کند و بقیه روی آن شماره صبر می‌کنند. پس وقتی گیر کردید، در `pg_stat_activity` دنبال مسدودکننده بگردید؛ معمولاً یک اتصال با حالت `idle in transaction` است.

## timeoutها

سه تنظیم می‌گذارند انتظار نامحدود نباشد. اولی را دیدیم: `lock_timeout` همان خطای `55P03` را داد. دو تای دیگر:

```text
statement_timeout 200ms, pg_sleep(2) -> ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
idle in transaction 900ms, next statement -> FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
```

`statement_timeout` کل زمان یک دستور را محدود می‌کند (دستور دو‌ثانیه‌ای ما بعد از ۲۰۰ میلی‌ثانیه لغو شد). مقدار `idle_in_transaction_session_timeout` را ۳۰۰ میلی‌ثانیه گذاشتم؛ session تراکنش را باز کرد، ۹۰۰ میلی‌ثانیه هیچ نکرد و دستور بعدی‌اش با خطای قطع اتصال روبه‌رو شد. این تنظیم اتصال را می‌کُشد تا کلاینتی که رفته و برنگشته، قفل‌هایش را برای همیشه نگه ندارد.

## یک {{< term "deadlock" "deadlock" >}} واقعی

حالا بدترین حالت. اگر دو session هرکدام قفلی را نگه دارند که دیگری می‌خواهد، هیچ‌کدام جلو نمی‌رود. ترتیب در این آزمایش:

```text
A: UPDATE row 1        (A holds row 1)
B: UPDATE row 2        (B holds row 2)
A: UPDATE row 2        (A waits for B)
B: UPDATE row 1        (B waits for A)   -> nobody can continue
```

PostgreSQL منتظر نمی‌ماند تا ابد. بعد از `deadlock_timeout` (در این نمونه `SHOW deadlock_timeout` مقدار `1s` داد) وارسی می‌کند و اگر دور بسته پیدا کند یکی را لغو می‌کند. این بار B قربانی شد:

```text
B wants row 1 -> ERROR: deadlock detected (SQLSTATE 40P01)
      DETAIL: Process 56717 waits for ShareLock on transaction 962; blocked by process 56715.
      Process 56715 waits for ShareLock on transaction 963; blocked by process 56717.
      HINT: See server log for query details.
then A -> ok
```

`DETAIL` همان دور بسته را می‌گوید: process B منتظر تراکنش A است و process A منتظر تراکنش B. با لغو شدن B، قفل‌هایش آزاد شد و دستور A بدون خطا تمام شد. نکته‌ی مهم این است که انتخاب قربانی قابل پیش‌بینی نیست: در اجرای قبلی همین آزمایش A قربانی شده بود و B موفق شد. اگر کدتان به یکی از این دو حالت تکیه کند، خراب می‌شود.

راه حل یک قاعده‌ی ساده است: **همیشه ردیف‌ها را با یک ترتیب ثابت قفل کنید**، مثلاً به ترتیب `id`. وقتی هر دو session از ردیف ۱ شروع کردند، B فقط تا commit شدن A صبر کرد و هر دو بدون خطا تمام شدند:

```text
-- fix: both sessions lock rows in id order
B wants row 1 first and waits for A
A commits; B: ok
B second update: ok
```

حتی با این قاعده، کد شما باید روی `40P01` دوباره تلاش کند، چون همیشه نمی‌شود ترتیب را تضمین کرد (مثلاً وقتی ردیف‌ها را کاربران مختلف از مسیرهای مختلف می‌گیرند).

## صف کار با SKIP LOCKED

قفل فقط مزاحم نیست؛ می‌شود ازش استفاده کرد. فرض کنید جدولی از کارها دارید و چند worker هم‌زمان می‌خواهند کار بردارند. شش ردیف در `jobs` گذاشتم و هر worker این کوئری را اجرا می‌کند:

```sql
SELECT id FROM jobs WHERE state='new' ORDER BY id LIMIT 2 FOR UPDATE SKIP LOCKED
```

worker 1 با تراکنش باز `[1 2]` را برداشت. worker 2 همان لحظه `[3 4]` را برداشت: ردیف‌هایی را که worker 1 قفل کرده بود رد کرد و منتظر نماند. بعد worker 1 کارهایش را `done` کرد و commit زد. worker 2 برای شبیه‌سازی crash، rollback کرد. نتیجه:

```text
   1 | done
   2 | done
   3 | new
   4 | new
   5 | new
   6 | new
```

کارهای ۱ و ۲ انجام شده‌اند و کارهای ۳ و ۴، که worker 2 قبل از «مرگ» برداشته بود، دوباره `new` شدند و کس دیگری می‌تواند بردارد. هیچ کاری هم دوبار برداشته نشد. این الگوی {{< term "skip-locked" "SKIP LOCKED" >}} است؛ با رویکرد مبتنی بر جدول در [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/) مقایسه کنید.

## صف پشت ALTER TABLE

حالا برگردیم به حادثه‌ی اول. S1 تراکنشی باز کرد و فقط از `acct` خواند؛ هنوز commit نکرده است. S2 دستور `ALTER TABLE acct ADD COLUMN` را زد و چون `AccessExclusiveLock` با قفل خواندن S1 تداخل دارد، منتظر ماند. بعد S3 یک `SELECT` ساده زد:

```text
S3: plain SELECT with lock_timeout 300ms -> ERROR: canceling statement due to lock timeout (SQLSTATE 55P03)
   56715 | AccessShareLock | true | []
   56717 | AccessExclusiveLock | false | [56715]
```

یک خواندن کاملاً بی‌ضرر رد شد. چرا؟ چون S3 با S1 مشکلی ندارد، ولی `AccessExclusiveLock` در انتظار S2 جلوی همه‌ی قفل‌های جدیدی که با آن تداخل دارند صف بسته است، و `SELECT` S3 پشت S2 ایستاد. دو خط پایین همین را نشان می‌دهند: S1 قفل را دارد (`true`)، و S2 منتظر است (`false`) و `[56715]` می‌گوید منتظر S1 است. روی جدول پرترافیک، یک تراکنش فراموش‌شده به‌علاوه‌ی یک migration همه‌چیز را متوقف می‌کند. راهش این است که migration را با `lock_timeout` کوتاه اجرا کنید و اگر نشد بعداً دوباره تلاش کنید، به‌جای اینکه همه را پشت خودش صف ببندد. وقتی S1 commit کرد، `ALTER` تمام شد و `SELECT` S3 دوباره جواب داد.

## قفل‌های advisory

گاهی می‌خواهید چیزی را قفل کنید که ردیف یا جدول نیست، مثلاً «فقط یک نمونه از این job هم‌زمان اجرا شود». یک {{< term "advisory-lock" "advisory lock" >}} قفلی روی عددی است که خودتان انتخاب می‌کنید؛ دیتابیس قفل را اجرا می‌کند ولی هیچ معنایی به آن عدد نمی‌دهد. A کلید ۴۲ را گرفت و `pg_try_advisory_lock(42)` در B مقدار `false` داد. بعد از اینکه A آزادش کرد، همان فراخوانی `true` شد.

## چطور گیر نیفتیم

- **تراکنش را کوتاه نگه دارید.** قفل‌ها تا commit یا rollback می‌مانند.
- **تایم‌اوت بگذارید.** برای migration یک `lock_timeout` کوتاه و برای اپلیکیشن `idle_in_transaction_session_timeout`، تا تراکنش فراموش‌شده همه را معطل نکند.
- **ردیف‌ها را با ترتیب ثابت قفل کنید** و روی `40P01` دوباره تلاش کنید.
- **پیش از کشتن یک اتصال، `pg_blocking_pids()` را ببینید.** مسدودکننده‌ی واقعی را پیدا کنید، نه فقط قربانی را.

## تمرین

deadlock را در دو پنجره‌ی `psql` بازتولید کنید و با ترتیب ثابت درستش کنید. بعد تراکنشی باز کنید و فقط از جدول بخوانید، از پنجره‌ی دیگر `ALTER TABLE` بزنید و از پنجره‌ی سوم یک `SELECT`. `pg_locks` را ببینید و بفهمید صف چطور شکل گرفته.

## قدم بعدی

[JSONB و جست‌وجوی متنی](/fa/posts/db-jsonb-fulltext-search/): تا اینجا درباره‌ی هم‌زمانی حرف زدیم. حالا نوبت شکل داده است: چطور داخل JSON و متن جست‌وجو کنیم.
