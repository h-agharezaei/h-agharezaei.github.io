+++
date = '2027-05-26T10:00:00+03:30'
draft = false
title = 'CQRS و event sourcing'
description = 'CQRS و event sourcing با Go روی Postgres واقعی: optimistic concurrency، snapshot، upcasting، projection عقب‌مانده، replay و زمان‌هایی که نباید استفاده کرد.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cqrs", "event-sourcing", "postgres", "go"]
cover = { image = "/images/covers/ds-cqrs-event-sourcing.fa.png", alt = "CQRS و event sourcing", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-saga-vs-2pc/) چند سرویس را با saga هماهنگ کرد. این مقاله چیزی را عوض می‌کند که یک سرویس ذخیره می‌کند: نه وضعیت فعلی، بلکه واقعیت‌هایی که به آن رسیدند. این همان {{< term "event-sourcing" "event sourcing" >}} است و {{< term "cqrs" "CQRS" >}} همراه همیشگی آن. همچنین ببینید [تراکنش و ACID](/fa/posts/db-transactions-acid/)، [مدل‌های consistency](/fa/posts/ds-consistency-models/)، [الگوی outbox](/fa/posts/go-outbox-pattern-nats/) و [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/).

> صادقانه: یک برنامه‌ی Go 1.26 روی یک ماشین با PostgreSQL 18.3 واقعی روی loopback. تصادف seed ثابت دارد، شمارش نشان می‌دهم نه زمان؛ `go test -race` سبز است. «زمان‌بندی poller» و «crash» در بخش آخر **شبیه‌سازی** است.

## وضعیت به‌صورت fold رویدادها

`Account` هرگز ذخیره نمی‌شود. وضعیتش fold روی `Opened` و `Deposited` و `Withdrawn` و `Closed` است. command قواعد را روی وضعیت فعلی بررسی و رویداد برمی‌گرداند؛ چیزی را mutate نمی‌کند. جدول `PRIMARY KEY (stream_id, version)` دارد و یک ستون `bigserial` برای ترتیب بین stream‌ها.

دو session یک stream را در version 2 (موجودی ۱۰۰۰۰ سنت) می‌خوانند و هر دو ۷۰۰۰ برداشت می‌کنند، به ترتیب ثابت:

```
A append: <nil>
B append: version conflict: ERROR: duplicate key value violates unique constraint "events_pkey" (SQLSTATE 23505)
B reloads and decides again: retries=0 err=insufficient funds
```

این {{< term "optimistic-concurrency" "optimistic concurrency" >}} است: بدون قفل، کلید اصلی version 3 دوم را رد می‌کند، B دوباره می‌خواند و حالا قاعده آن را رد می‌کند. `UPDATE` روی رویداد در SQL شدنی است (`UPDATE 1`، rollback کردم)؛ برنامه فقط هرگز آن را نمی‌زند. جلوگیری با trigger یا گرفتن دسترسی را امتحان نکردم.

## replay، snapshot، upcasting، سفر در زمان

یک stream با ۱۰٬۱۲۳ رویداد که هر ۵۰۰ رویداد یک {{< term "event-snapshot" "snapshot" >}} دارد:

```
no snapshot : version=10123 balance=989607 replayed=10123 events
snapshot/500: version=10123 balance=989607 replayed=123 events
state at 2027-03-01: version=1416 balance=138314 (replayed 1416 events)
```

وضعیت یکسان، ۱۲۳ رویداد به‌جای ۱۰٬۱۲۳. snapshot کش است نه حقیقت. خط آخر query زمانی است: تا یک version replay کنید (که از `created_at` پیدا شد؛ در این demo هر version یک ساعت است) و گذشته را دارید، بدون جدول audit. رویدادها audit trail را هم رایگان می‌دهند.

شکل رویدادها عوض می‌شود. نسخه‌ی ۱ مقدار `{"amount": 5}` (دلار) ذخیره می‌کرد؛ نسخه‌ی ۲ `amount_cents` و `currency`. رویداد قدیمی را هرگز ویرایش نکنید: هنگام خواندن {{< term "upcasting" "upcast" >}} کنید. سطرهای قدیمی که با SQL خام گذاشتم:

```
stored Deposited {"amount": 5}  -> upcast {"amount_cents":500,"currency":"USD"}
stored Deposited {"currency": "USD", "amount_cents": 250} -> unchanged
stored Withdrawn {"amount": 2}  -> upcast {"amount_cents":200,"currency":"USD"}
legacy balance=550 cents
```

یک unit test همین را و دست‌نخورده‌ماندن ورودی را بررسی می‌کند.

## سمت query سرانجام consistent است

نوشتن در `events` است. خواندن از `account_balances` و `daily_totals` است که یک {{< term "projection" "projection" >}} می‌سازد: poller رویدادهای بعد از checkpoint را می‌خواند و read model را در همان تراکنشِ checkpoint به‌روز می‌کند. ۳۰۰ واریز روی ۵ حساب، هر کدام با یک خواندن فوری از read model؛ poller با پرتاب سکه‌ی seed‌دار و حداکثر ۵ رویداد در هر اجرا کار می‌کند:

```
300 writes ... 222 stale reads, max lag 10 events
after the projector catches up, read model == truth: true
```

این همان {{< term "eventual-consistency" "eventual consistency" >}} است که آگاهانه انتخاب کردید: ۲۲۲ از ۳۰۰ خواندن، نوشته‌ی خودش را ندید. به تجربه‌ی من باید UI را برای آن طراحی کرد.

projection را می‌شود دوباره ساخت. checkpoint را ریست و هر ۱۰٬۴۳۵ رویداد را دوباره replay کردم:

```
balances unchanged=true; daily_totals deposited 2048518 -> 4097036 (naive counter doubled)
rebuild from scratch: 10435 events replayed -> 8 balance rows, 422 daily rows, deposited 2048518 (== first run: true)
```

handler موجودی {{< term "idempotency" "idempotent" >}} است: `ON CONFLICT ... DO UPDATE ... WHERE last_version < EXCLUDED.last_version` نسخه‌های اعمال‌شده را رد می‌کند. شمارنده‌ی روزانه نیست و دو برابر شد؛ راه‌حل truncate و replay است که مقدار اجرای اول را برگرداند. چند projection از یک log همین حلقه با handlerهای دیگر است.

## log به‌عنوان outbox

جدول events می‌تواند {{< term "outbox-pattern" "outbox" >}} هم باشد: publisher فقط یک خواننده‌ی دیگر با checkpoint خودش است. اگر بین publish و ذخیره‌ی checkpoint بمیرد، batch تکرار می‌شود؛ یعنی {{< term "at-least-once-delivery" "at-least-once delivery" >}}. ۶۹ crash را با عقب‌بردن checkpoint شبیه‌سازی کردم:

```
events=10435 deliveries=13885 distinct=10435 simulated-crashes=69
```

۳٬۴۵۰ تکراری؛ مصرف‌کننده‌ای که با `(stream_id, version)` dedupe کند دقیقاً ۱۰٬۴۳۵ اثر می‌گیرد.

## چه وقت استفاده نکنیم

به نظر من بیشتر برنامه‌های CRUD نباید: هزینه‌اش پیچیدگی، eventual consistency و upcasterهای همیشگی است. یک جدول معمولی به‌علاوه‌ی جدول audit تاریخچه را با ابزار بسیار کمتر می‌دهد؛ رویداد وقتی می‌ارزد که تاریخچه خودِ دامنه باشد (دفتر حساب، سفارش با چرخه‌ی پیچیده). log تغییرناپذیر با درخواست حذف داده هم تعارض دارد. یک پاسخ شناخته‌شده {{< term "crypto-shredding" "crypto-shredding" >}} است: فیلدهای شخصی را برای هر فرد رمز کنید و کلید را نابود کنید. پیاده‌اش نکردم. همچنین position از نوع `bigserial` ممکن است در تراکنش‌های همزمان بی‌ترتیب دیده شود و poller رویدادی را رد کند؛ بازتولیدش نکردم.

## چند نکته‌ی مهم

- command روی وضعیت اعتبارسنجی و رویداد صادر می‌کند؛ handler نباید مستقیم state بنویسد.
- snapshot و projection دورریختنی‌اند؛ حقیقت رویدادهاست.
- رویداد ذخیره‌شده را ویرایش نکنید؛ هنگام خواندن upcast کنید.
- هر مصرف‌کننده را idempotent کنید؛ تحویل at-least-once است.

## تمرین

جدول `daily_seen` با کلید `(stream_id, version)` اضافه کنید و `daily_totals` را idempotent کنید. replay دوباره را اجرا کنید: باید روی ۲۰۴۸۵۱۸ بماند؟

## قدم بعدی

مقاله‌ی بعد «پیام‌رسانی و معماری رویدادمحور» است.
