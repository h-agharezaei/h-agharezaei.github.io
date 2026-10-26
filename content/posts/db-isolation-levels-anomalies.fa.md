+++
date = '2026-12-21T10:00:00+03:30'
draft = false
title = 'سطح‌های ایزولاسیون و ناهنجاری‌ها'
description = 'سطح‌های ایزولاسیون PostgreSQL با دو session هم‌زمان واقعی: non-repeatable read، phantom، lost update، write skew و خطای serialization.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "isolation", "transactions", "concurrency"]
cover = { image = "/images/covers/db-isolation-levels-anomalies.fa.png", alt = "سطح‌های ایزولاسیون و ناهنجاری‌ها", hiddenInSingle = true }
+++

در [پست قبلی](/fa/posts/db-transactions-acid/) با حرف «I» در {{< term "acid" "ACID" >}} یعنی ایزولاسیون، به‌عنوان یک وعده آشنا شدیم. این پست آن وعده را امتحان می‌کند. هر {{< term "isolation-level" "سطح ایزولاسیون" >}} بعضی نتیجه‌های عجیب را اجازه می‌دهد و بعضی را ممنوع می‌کند، و تنها راهی که به آن اعتماد دارم دیدنِ درهم‌رفتن دو session است. اگر Go می‌نویسید، [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/) این سطح‌ها را از کد به کار برده بود؛ اینجا می‌بینیم چرا.

> همه‌چیز روی یک PostgreSQL 18.3 واقعی اجرا شده. یک برنامه‌ی کوچک Go (مثال محلی) دو اتصال **A** و **B** باز می‌کند و فهرست ثابتی از گام‌ها را به ترتیب اجرا می‌کند، پس خروجی قطعی است. جدول‌ها: `accounts(id, balance)` با (1, 100) و (2, 50)، جدول `oncall(doctor, on_duty)` و seed مشترک `shop`.

## READ COMMITTED: بدون dirty read

این پیش‌فرض PostgreSQL است. هر statement داده‌ای را می‌بیند که پیش از شروع همان statement commit شده بود. حتی `READ UNCOMMITTED` خواستم:

```text
A> BEGIN ISOLATION LEVEL READ UNCOMMITTED
A> SHOW transaction_isolation            -> read uncommitted
B> BEGIN
B> UPDATE accounts SET balance = 0 WHERE id = 1
A> SELECT balance FROM accounts WHERE id = 1   -> 100
B> ROLLBACK
```

A مقدار commit‌نشده‌ی ۰ از B را ندید. طبق مستندات، PostgreSQL سطح READ UNCOMMITTED را مثل READ COMMITTED رفتار می‌کند و اجرا هم همین را نشان داد.

## Non-repeatable read و phantom

در READ COMMITTED، A می‌خواند، B تغییرها را commit می‌کند، A دوباره می‌خواند:

```text
A> BEGIN
A> SELECT balance FROM accounts WHERE id = 1               -> 100
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 2
B> UPDATE accounts SET balance = 60 WHERE id = 1
B> INSERT INTO accounts VALUES (3, 70)
A> SELECT balance FROM accounts WHERE id = 1               -> 60
A> SELECT count(*) FROM accounts WHERE balance >= 50       -> 3
```

موجودی زیر پای A عوض شد: {{< term "non-repeatable-read" "non-repeatable read" >}}. شمارش یک ردیف بیشتر شد که قبلاً وجود نداشت: {{< term "phantom-read" "phantom" >}}. هر دو در این سطح مجازند.

## REPEATABLE READ: یک snapshot

همان گام‌ها با `BEGIN ISOLATION LEVEL REPEATABLE READ`: A هر دو بار ۱۰۰ و ۲ را خواند. بعد از commit شدن A، خواندن تازه ۶۰ داد. روی seed فروشگاه هم همین است:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
B> INSERT INTO orders (customer_id, status, total_cents) VALUES (1, 'new', 999)
A> SELECT count(*) FROM orders WHERE customer_id = 1   -> 10
A> COMMIT, then the same query                          -> 11
```

تراکنش از یک {{< term "snapshot-isolation" "snapshot" >}} می‌خواند. در PostgreSQL این phantomها را هم پنهان می‌کند (استاندارد SQL در این سطح اجازه‌شان می‌دهد). هزینه‌اش در نوشتن است:

```text
A> BEGIN ISOLATION LEVEL REPEATABLE READ
A> SELECT balance FROM accounts WHERE id = 1               -> 100
B> UPDATE accounts SET balance = balance - 10 WHERE id = 1   (autocommit)
A> UPDATE accounts SET balance = balance - 10 WHERE id = 1
   ERROR: could not serialize access due to concurrent update (SQLSTATE 40001)
```

A می‌خواست ردیفی را عوض کند که بعد از snapshot او تغییر کرده، پس PostgreSQL آن را abort کرد.

## Lost update

در READ COMMITTED و وقتی حساب‌وکتاب در اپلیکیشن انجام می‌شود:

```text
A, B: BEGIN;  both SELECT balance -> 100
A> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
B> UPDATE accounts SET balance = 90 WHERE id = 1; COMMIT
final balance -> 90
```

دو برداشت ۱۰تایی از ۱۰۰ باید ۸۰ بگذارد. {{< term "lost-update" "lost update" >}} عدد ۹۰ را گذاشت. دو روش امن، که هر دو را اجرا کردم و به ۸۰ رسیدند:

- `UPDATE accounts SET balance = balance - 10`: UPDATE در B روی قفل A **منتظر می‌ماند**، بعد ردیف commit‌شده را دوباره می‌خواند و از ۹۰ کم می‌کند.
- `SELECT balance ... FOR UPDATE`: SELECT در B تا commit شدن A بلاک ماند، بعد ۹۰ برگرداند و B عدد ۸۰ را نوشت.

## Write skew

قاعده: دست‌کم یک پزشک سر کار بماند. هر دو سر کارند. هر session تعداد پزشکان سر کار را می‌شمارد (۲)، بعد ردیفِ *متفاوتی* را false می‌کند:

```text
A, B: BEGIN ISOLATION LEVEL REPEATABLE READ; both count -> 2
A> UPDATE oncall SET on_duty = false WHERE doctor = 'alice'
B> UPDATE oncall SET on_duty = false WHERE doctor = 'bob'
A> COMMIT      B> COMMIT      (both succeed)
SELECT * FROM oncall  -> alice, false | bob, false
```

هیچ‌کس سر کار نیست. هیچ ردیفی دوبار به‌روز نشد، پس تداخلی برای تشخیص نبود: این {{< term "write-skew" "write skew" >}} است. همین را با `SERIALIZABLE` دوباره اجرا کنید:

```text
A> COMMIT   -> COMMIT
B> COMMIT   -> ERROR: could not serialize access due to read/write dependencies among transactions (SQLSTATE 40001)
SELECT * FROM oncall  -> alice, false | bob, true
```

یکی abort شد و قاعده حفظ شد. تراکنش abort‌شده کار اشتباهی نکرده بود، پس اپلیکیشن باید **کل تراکنش را دوباره اجرا کند**. همان حلقه‌ی retry روی کد {{< term "sqlstate" "SQLSTATE" >}} برابر 40001 در [تراکنش و الگوی Repository در Go](/fa/posts/go-transactions-patterns/). اینجا دوباره اجرایش نکردم.

## آنچه دیدم

| ناهنجاری | READ COMMITTED | REPEATABLE READ | SERIALIZABLE |
|---|---|---|---|
| Dirty read | دیده نشد (با READ UNCOMMITTED هم) | ممکن نیست (مستندات) | ممکن نیست (مستندات) |
| Non-repeatable read | دیده شد | دیده نشد | ممکن نیست (مستندات) |
| Phantom | دیده شد | دیده نشد | ممکن نیست (مستندات) |
| Lost update | دیده شد | خطای 40001 | ممکن نیست (مستندات) |
| Write skew | تست نشد | دیده شد | جلوگیری شد (40001) |

## چند نکته‌ی مهم

- READ COMMITTED پیش‌فرض است و همه‌ی ناهنجاری‌های بالا به‌جز dirty read در آن مجازند. بیشتر از این فرض نکنید.
- lost update در REPEATABLE READ در اجرای من به شکل خطا ظاهر شد؛ فقط شکل نسبی `balance - 10` را امتحان کردم.
- به‌جای read-modify-write در کد اپلیکیشن، `SET x = x - n` یا `FOR UPDATE` را ترجیح دهید.
- سطح‌های بالاتر از READ COMMITTED می‌توانند در هر statement یا در COMMIT با 40001 شکست بخورند. تراکنش را در retry بپیچید و اثر جانبی داخلش نگذارید.
- آزمایش فقط درهم‌رفتن در سطح ردیف بود؛ قفل‌های دیگر، deadlock و دیتابیس‌های دیگر را امتحان نکردم.

## تمرین

write skew را خودتان با دو پنجره‌ی `psql` بازسازی کنید، بعد سعی کنید بدون SERIALIZABLE جلویش را بگیرید، مثلاً با قفل کردن ردیف‌هایی که می‌شمارید با `FOR UPDATE`، و ببینید جواب می‌دهد یا نه. من این حالت را اجرا نکردم.

## قدم بعدی

بعدی: MVCC و VACUUM، سازوکاری که این snapshotها را ممکن می‌کند.
