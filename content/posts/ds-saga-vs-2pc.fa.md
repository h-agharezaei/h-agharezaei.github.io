+++
date = '2027-05-23T10:00:00+03:30'
draft = false
title = 'saga یا 2PC؟'
description = 'saga یا commit دو فازی: شبیه‌سازی 2PC که block می‌شود، PREPARE TRANSACTION واقعی در Postgres و sagaهای سفارش با جبران که کامل بررسی شده‌اند.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "saga", "two-phase-commit", "transactions", "go", "postgres"]
cover = { image = "/images/covers/ds-saga-vs-2pc.fa.png", alt = "saga یا 2PC؟", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-consensus-raft/) روی یک log توافق کرد. سفارش به چند سرویس می‌رسد (موجودی، پرداخت، ارسال) و هیچ log واحدی همه را پوشش نمی‌دهد. دو جواب هست: {{< term "two-phase-commit" "commit دو فازی" >}} (2PC) که atomicity را نگه می‌دارد، و {{< term "saga" "saga" >}} که ایزولاسیون را کنار می‌گذارد. ببینید [ACID](/fa/posts/db-transactions-acid/)، [outbox](/fa/posts/go-outbox-pattern-nats/)، [idempotency](/fa/posts/nats-jetstream-idempotency/) و [retry](/fa/posts/ds-timeouts-retries-backoff/).

> صادقانه: بخش‌های 2PC و saga **شبیه‌سازی** در Go 1.26 روی یک ماشین‌اند: ساعت و شبکه شبیه‌سازی‌شده (تأخیر ۱ تا ۳ tick با seed ثابت) و سرویس‌ها داخل یک process. بدون زمان‌سنجی. بخش ۲ یک PostgreSQL 18.3 واقعی روی loopback است با `psql`.

## 2PC در شبیه‌سازی

یک coordinator و سه participant که هرکدام یک row را lock می‌کنند. فاز ۱: `PREPARE`؛ هر participant کارش را durable می‌کند، lock را نگه می‌دارد و رأی می‌دهد. فاز ۲: coordinator تصمیم را در log می‌نویسد و `COMMIT` یا `ABORT` می‌فرستد. اجرای خلاصه‌شده وقتی shipping رأی no می‌دهد:

```
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping votes NO (rolls back, no lock kept)
t=  4  coord <- shipping NO
t=  4  coord LOG "ABORT"
t=  6  inventory ABORT, lock released after 3 ticks
t=  6  payment ABORT, lock released after 5 ticks
```

در مسیر عادی lockها ۵ تا ۷ tick می‌مانند. عیب معروف: coordinator بعد از رأی yes هر سه، پیش از نوشتن تصمیم crash می‌کند.

```
t=  6  coord CRASH: all voted yes, no decision written yet
t= 60  coord RESTART, reads its log [BEGIN]
t= 60  coord found BEGIN without a decision -> presumed ABORT
t= 61  inventory ABORT, lock released after 58 ticks
decision: ABORT lock ticks: map[inventory:58 payment:60 shipping:62] competing writes refused: 12 of 13
```

participantی که yes داده نمی‌تواند تنها تصمیم بگیرد: شاید جواب commit باشد. فقط می‌تواند بپرسد (هر ۱۰ tick؛ تا وقتی coordinator پایین است سؤال‌ها گم می‌شوند) و صبر کند. این **blocking** است. اگر `COMMIT` در log بود، دوباره فرستاده می‌شود. زمان lock با طول خرابی بالا می‌رود:

```
recover at t=10    lock ticks inventory=9    payment=11   shipping=11   refused=2/4
recover at t=200   lock ticks inventory=198  payment=202  shipping=202  refused=40/42
recover at t=1000  lock ticks inventory=1000 payment=1000 shipping=1000 refused=200/202
```

refused: نویسنده‌ی رقیبی که هر ۵ tick row موجودی را می‌خواهد.

## ابزار واقعی در Postgres

Postgres سمت participant را به شکل {{< term "prepared-transaction" "prepared transaction" >}} می‌دهد. `max_prepared_transactions` باید بیشتر از ۰ باشد (instance خودم را با ۵ بالا آوردم). یک database جای دو resource manager است.

```
begin; update account set balance = balance - 30 where id = 1;
       update stock set qty = qty - 1 where sku = 'A';
prepare transaction 'order-42';
```

session تمام می‌شود؛ داده هنوز مقدار قدیمی است (balance 100، qty 5)، اما:

```
   gid    | owner | database 
 order-42 | app   | orders
 locktype |   rel   |       mode       | granted | no_session 
 relation | account | RowExclusiveLock | t       | t
```

session دیگری با `lock_timeout = '500ms'` همان row را update کرد:

```
ERROR:  canceling statement due to lock timeout
CONTEXT:  while updating tuple (0,1) in relation "account"
```

بعد از restart روی همان data directory، `order-42` هنوز در فهرست بود. یک session تازه `COMMIT PREPARED 'order-42'` زد و مقدارها ۷۰ و ۴ شدند. مستندات می‌گوید برای «استفاده در برنامه‌ها» نیست و فقط برای transaction manager بیرونی است؛ هشدار می‌دهد prepared فراموش‌شده lockها را نگه می‌دارد و جلوی VACUUM را می‌گیرد. XA رابط استاندارد این managerهاست؛ من یکی را اجرا نکردم.

## saga: orchestration و choreography

saga سفارش را به قدم‌های محلی با {{< term "compensating-transaction" "جبران" >}} می‌شکند: رزرو موجودی (جبران: آزادسازی)، پرداخت (جبران: refund)، ارسال (قدم آخر). هر دو سبک را نوشتم؛ orchestration: یک state machine که log ذخیره‌شده‌اش `begin`، `done`، `failed` و `comp` را ثبت می‌کند. choreography: سرویس‌ها به eventها روی یک صف durable با at-least-once واکنش نشان می‌دهند (`ShippingFailed` باعث refund و `PaymentRefunded` باعث آزادسازی موجودی می‌شود).

checker می‌گوید: charged اگر و فقط اگر shipped، و موجودی رزرو شده اگر و فقط اگر shipped. حالت‌ها: شکست هر قدم (یا هیچ‌کدام)، تحویل دوباره‌ی هر call یا نه، شکست اولین جبران یا نه، crash پیش از هر نوشتن log و هر call، و crash دوم هنگام recovery.

```
orchestration (persisted log) cases=3468 violations=0
choreography (events)     cases=2508 violations=0
```

تستی با refundی که کاری نمی‌کند گرفته می‌شود، پس checker می‌تواند هشدار بدهد. دلیل: callها idempotent‌اند (نتیجه به‌ازای هر saga id ذخیره می‌شود)، جبران tombstone می‌گذارد که call دیرهنگام را رد کند، و تا موفقیت تکرار می‌شود.

## saga چه چیزی را دیدنی می‌کند

ایزولاسیون نیست. وقتی ارسال شکست می‌خورد، خواننده‌ای که در هر قدم می‌خواند این را می‌بیند:

```
reads=20  naive view saw 'charged'=7, final charged=false
PENDING view (status exposed only when the saga ends): reads that showed 'charged'=0
```

هفت خواندن پولی را دیدند که بعداً برگشت. راه‌حل‌ها: وضعیت `PENDING` قابل‌دیدن، **semantic lock** (پرچمی که عملیات دیگر روی سفارش را منتظر یا ناموفق می‌کند) و updateهای جابه‌جاپذیر. فقط pending view را ساختم.

## مقایسه

| | 2PC | Saga |
|---|---|---|
| Atomicity | همه یا هیچ | در نهایت، با جبران |
| Isolation | lock در زمان prepare | ندارد، حالت میانی دیده می‌شود |
| Availability | روی coordinator block می‌شود | ادامه می‌دهد، بعداً ترمیم می‌کند |
| Latency | دو رفت‌وبرگشت با lock | بدون lock بین سرویس‌ها |
| Complexity | در پروتکل | در جبران‌های شما |
| Coupling | منابع سازگار با 2PC | هر سرویس با API |

به تجربه‌ی من saga به سرویس‌های جدا می‌خورد و 2PC به چند database که خودتان کنترل می‌کنید. Percolator و Spanner برای نداشتن coordinator تکی، 2PC را روی گروه‌های consensus اجرا می‌کنند؛ فقط نامشان را می‌آورم. TCC (try-confirm-cancel) یک saga است که «try»اش رزرو است.

## چند نکته‌ی مهم

- نیت را پیش از call و نتیجه را بعد از آن در log بنویسید؛ crash در فاصله‌ی این دو است.
- جبران rollback نیست: refund یک واقعیت تازه است؛ ایمیل برگشت‌پذیر نیست.
- قدمی را که نمی‌شود برگرداند یا شکست نمی‌خورد آخر بگذارید.
- eventهای saga را با outbox منتشر کنید، وگرنه گم می‌شوند.
- شبیه‌سازی partition ندارد.

## تمرین

ارسال را اول بگذارید. کدام جبران‌ها گران می‌شوند، و checker هنوز صفر violation نشان می‌دهد؟

## قدم بعدی

«CQRS و event sourcing»: نگه داشتن log رویدادها به‌عنوان منبع حقیقت و خواندن از viewهای جدا.
