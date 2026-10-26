+++
date = '2026-12-13T10:00:00+03:30'
draft = false
title = 'تراکنش و ACID'
description = 'تراکنش و ACID در PostgreSQL با اجرای واقعی: BEGIN، ROLLBACK، savepoint، قیدها، DDL تراکنشی، WAL و synchronous_commit.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "transactions", "acid", "wal"]
cover = { image = "/images/covers/db-transactions-acid.fa.png", alt = "تراکنش و ACID", hiddenInSingle = true }
+++

انتقال پول دو update است: از اینجا کم کن، آنجا اضافه کن. اگر پردازه بین این دو بمیرد، پول گم می‌شود. {{< term "transaction" "تراکنش" >}} جواب دیتابیس است: گروهی از دستورها که یا همه اتفاق می‌افتند یا هیچ‌کدام. در [پست قبلی](/fa/posts/db-planner-statistics/) دیدیم planner چطور داده را می‌خواند؛ حالا می‌بینیم نوشتن چطور درست می‌ماند. سمت اپلیکیشن این ماجرا در [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/) آمده است.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی اجرا شده. یک جدول کوچک `accounts` داشتم (alice با ۱۰۰۰۰ سنت، bob با ۵۰۰۰) با `CHECK (balance_cents >= 0)` و جدول `transfers` با کلید خارجی. مجموع این تضمین‌ها {{< term "acid" "ACID" >}} نام دارد.

## autocommit در برابر BEGIN

بدون `BEGIN` هر دستور تراکنش خودش است و فوراً commit می‌شود (autocommit). `UPDATE accounts SET balance_cents = balance_cents - 3000 WHERE id = 1` همان لحظه alice را ۷۰۰۰ کرد، در حالی که bob هنوز چیزی نگرفته بود. انتقال دقیقاً باید از همین وضعیت دور بماند.

## Atomicity

انتقال را در تراکنش گذاشتم و دستور دوم را طوری نوشتم که شکست بخورد (bob به ‎-۴۰۰۰ می‌رسید):

```text
BEGIN;
UPDATE accounts SET balance_cents = balance_cents - 3000 WHERE id = 1;   -- UPDATE 1
UPDATE accounts SET balance_cents = balance_cents - 9000 WHERE id = 2;
ERROR:  new row for relation "accounts" violates check constraint "accounts_balance_cents_check"
DETAIL:  Failing row contains (2, bob, -4000).
SELECT 1;
ERROR:  current transaction is aborted, commands ignored until end of transaction block
COMMIT;
ROLLBACK
```

بعد از خطا تراکنش **aborted** است: تا پایان بلوک هر دستوری رد می‌شود. حتی `COMMIT` جواب `ROLLBACK` می‌دهد. موجودی‌ها بعد از آن alice ‏۱۰۰۰۰ و bob ‏۵۰۰۰ بود: update اول ناپدید شد. نسخه‌ی موفق (منهای ۳۰۰۰، به‌علاوه‌ی ۳۰۰۰ و `COMMIT`) ۷۰۰۰ و ۸۰۰۰ داد. `ROLLBACK` صریح هم همین‌طور است: داخل تراکنش alice را ۰ کردم و ۰ خواندم؛ بعد از `ROLLBACK` دوباره ۷۰۰۰ بود.

## Savepoint

{{< term "savepoint" "savepoint" >}} اجازه می‌دهد فقط بخشی را برگردانید:

```text
BEGIN;
UPDATE accounts SET balance_cents = balance_cents - 100 WHERE id = 1;
SAVEPOINT s1;
UPDATE accounts SET balance_cents = balance_cents - 99999 WHERE id = 1;   -- CHECK violation
ROLLBACK TO s1;                                                          -- transaction usable again
UPDATE accounts SET balance_cents = balance_cents - 200 WHERE id = 1;
COMMIT;
```

alice از ۷۰۰۰ به ۶۷۰۰ رسید: ‎-۱۰۰ و ‎-۲۰۰ ماندند و دستور شکست‌خورده نه. بدون savepoint آن خطا همه‌چیز را abort می‌کرد.

## Consistency

اینجا consistency یعنی قیدها. یک {{< term "check-constraint" "قید CHECK" >}} بالا شکست خورد؛ {{< term "foreign-key" "کلید خارجی" >}} هم همین کار را می‌کند. از alice ۵۰ کم کردم و انتقالی به حساب ۹۹ که وجود ندارد درج کردم:

```text
ERROR:  insert or update on table "transfers" violates foreign key constraint "transfers_to_id_fkey"
DETAIL:  Key (to_id)=(99) is not present in table "accounts".
```

`COMMIT` آخر در عمل rollback شد و alice همان ۶۷۰۰ ماند. قیدها حتی با باگ در کد اپلیکیشن از داده محافظت می‌کنند. دیتابیس فقط قاعده‌هایی را اجرا می‌کند که اعلام کرده‌اید؛ قواعد کسب‌وکاری که قید نیستند با خودتان است.

## DDL تراکنشی است (PostgreSQL)

`BEGIN; CREATE TABLE temp_demo ...; INSERT ...; SELECT count(*)` (جواب ۱) و بعد `ROLLBACK` زدم. بعد از آن `to_regclass('temp_demo')` خالی بود: جدول هرگز وجود نداشت. این ویژگی PostgreSQL است؛ دیتابیس‌های دیگر را امتحان نکرده‌ام و بعضی‌شان با DDL به‌طور ضمنی commit می‌کنند، پس جای دیگر فرضش نکنید. مایگریشن را امن‌تر می‌کند.

## Isolation: یک نمونه‌ی کوتاه

یک برنامه‌ی کوچک Go دو اتصال باز کرد. نشست A تراکنش را شروع کرد، ۵۰۰ از alice کم کرد و یک انتقال درج کرد:

```text
A: BEGIN; update alice -500; insert a transfer row
  A sees: alice=6200, transfers=1
  B sees: alice=6700, transfers=0
A: COMMIT
  B sees: alice=6200, transfers=1
```

B کار commit نشده را نمی‌بیند. اینکه در حالت‌های پیچیده‌تر B دقیقاً چه چیزی ببیند به سطح isolation بستگی دارد که موضوع پست بعدی است.

## Durability، ‏WAL و synchronous_commit

تغییرِ commit شده باید از crash جان سالم به در ببرد. PostgreSQL هر تغییر را اول در {{< term "wal" "WAL" >}} می‌نویسد و موقع commit آن را flush می‌کند. تنظیم‌های واقعی اینجا:

```text
synchronous_commit = on     fsync = on     wal_level = replica     full_page_writes = on
```

با {{< term "synchronous-commit" "synchronous_commit" >}} برابر `on`، دستور `COMMIT` بعد از flush شدن WAL برمی‌گردد. WAL را با `pg_current_wal_insert_lsn()` قبل و بعد اندازه گرفتم (بایت، قطعی):

```text
UPDATE of one row (autocommit):      112 bytes
BEGIN; UPDATE; COMMIT:               112 bytes
BEGIN; COMMIT (empty):                 0 bytes
BEGIN; UPDATE; ROLLBACK:             112 bytes
```

دو درس: تراکنش خالی هزینه‌ای ندارد و تراکنش rollback‌شده هم WAL نوشته است. (تلاش اول من با `pg_current_wal_lsn()` برای rollback عدد ۰ نشان داد چون آن داده هنوز نوشته نشده بود؛ موقعیت insert معیار درست است.) اولین update بعد از راه‌اندازی ۴۵۶۸ بایت نوشت. دلیلش را بعداً با `pg_walinspect` سنجیدم: update درست بعد از `CHECKPOINT` یک full-page image ثبت می‌کند (رکورد `FPI_FOR_HINT` با برچسب `FPW`) و update بعدی روی همان page فقط ۱۱۲ بایت نوشت. اندازه‌ی آن image به پر بودن page بستگی دارد. **durability را crash-test نکردم**، مثلاً با `kill -9`؛ پس این بخش به تنظیم‌ها و مستندات تکیه دارد.

## چند نکته‌ی مهم

- تراکنش را کوتاه نگه دارید. تراکنش طولانی lock و نسخه‌های قدیمی ردیف را نگه می‌دارد و جلوی پاکسازی را می‌گیرد؛ پست MVCC و VACUUM توضیحش می‌دهد.
- داخل تراکنش منتظر کاربر یا یک فراخوانی HTTP نمانید.
- بعد از خطا، تراکنش تا `ROLLBACK` یا `ROLLBACK TO` یک savepoint مرده است.
- `synchronous_commit = off` سریع‌تر است ولی در crash ممکن است commitهای آخر را از دست بدهد؛ آن را تست نکردم.
- در کد اپلیکیشن یک helper مثل `WithTx` بنویسید و `BEGIN` دستی پخش نکنید.

## تمرین

درج در `transfers` را به انتقال اضافه کنید تا فقط وقتی هر دو موجودی عوض شدند ردیف ثبت شود. update دوم را با نقض CHECK شکست بدهید و با `SELECT` ببینید نه موجودی‌ها و نه `transfers` تغییر نکرده‌اند. بعد همین را با یک `SAVEPOINT` دور درج تکرار کنید.

## قدم بعدی

در پست بعدی این سری: سطح‌های ایزولاسیون و ناهنجاری‌ها.
