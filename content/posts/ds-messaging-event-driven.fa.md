+++
date = '2027-05-29T10:00:00+03:30'
draft = false
title = 'پیام‌رسانی و معماری رویدادمحور'
description = 'معماری رویدادمحور با Go و NATS: command و event، fan-out، envelope، consumer خودتوان، ترتیب، تغییر schema و محدودکردن حلقه‌ها.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "messaging", "event-driven", "nats", "go"]
cover = { image = "/images/covers/ds-messaging-event-driven.fa.png", alt = "پیام‌رسانی و معماری رویدادمحور", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/ds-cqrs-event-sourcing/) با event به عنوان راهی برای انتقال state تمام شد. این مقاله نگاه معماری به پیام‌رسانی است. طرز کار JetStream در [سری NATS](/fa/posts/nats-jetstream-retry-dlq/) آمده و اینجا تکرارش نمی‌کنم.

> برچسب صادقانه: همه‌چیز روی یک ماشین است، سرویس‌ها goroutine‌اند و «شبکه» loopback به یک nats-server توکار است. الگوها را نشان می‌دهد، نه شبکه‌ی واقعی را. فقط شمارش.

## command و event و query

| | Command | Event | Query |
|---|---|---|---|
| نام | امری: `PlaceOrder` | گذشته: `OrderPlaced` | `GetOrder` |
| معنا | لطفاً این را انجام بده | این اتفاق افتاد | بگو |
| گیرنده | یکی | صفر یا بیشتر | یکی |
| ردشدنی | بله | نه، یک واقعیت است | بی‌معنی |

## یک گیرنده یا چند گیرنده

۳۰ پیام را به سه subscriber با سه روش فرستادم.

```
core pub/sub, 3 subscribers      : 30 30 30
core queue group, 3 members      : 13 10 7
JetStream work queue, 3 workers  : 10 10 10
```

{{< term "fan-out" "fan-out" >}} روی subject به همه همه‌ی پیام‌ها را می‌دهد. {{< term "queue-group" "queue group" >}} هر پیام را به یک عضو می‌دهد، ولی تقسیم را سرور تعیین می‌کند (۱۳ و ۱۰ و ۷ در این اجرا). work-queue در JetStream با یک durable مشترک اینجا ۱۰ تا ۱۰ تا شد؛ قولش را نمی‌دهم، چون workerها هر وقت آزاد باشند pull می‌کنند ([scaling و lag](/fa/posts/nats-jetstream-scaling-lag/)).

## choreography یا orchestration

سه سرویس goroutine (orders و payments و shipping) با یک {{< term "event-envelope" "event envelope" >}} حرف می‌زنند: id و type و time و source و نسخه‌ی schema و correlation id و causation id و data. CloudEvents استاندارد چنین envelope ای است؛ مال من شبیه آن است، نه منطبق. در {{< term "choreography" "choreography" >}} هر سرویس به یک event واکنش نشان می‌دهد. ردیابی یک correlation id:

```
orders    publish OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  receive OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  publish PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  receive PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  publish ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
orders    receive ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
```

causation id زنجیره را بازسازی می‌کند و correlation id آن را در logها پیدا می‌کند. در {{< term "orchestration" "orchestration" >}} یک هماهنگ‌کننده `CapturePayment` را می‌فرستد، منتظر پاسخ می‌ماند، بعد `DispatchShipping` را: همان سه گام، ولی در یک تابع خوانا، و مسیر شکست (compensation) جای روشنی دارد. طبق تجربه‌ی من: orchestration برای جریان‌های پولی، choreography برای واکنش‌های مستقل مثل notification.

## at-least-once و consumer خودتوان

۵۰ event را به یک consumer در JetStream با ack wait برابر ۳۰۰ms فرستادم. handler در حدود ۲۰٪ تحویل‌های اول بعد از اثر جانبی و قبل از ack «crash» می‌کند (seed ثابت، تکرارپذیر).

```
events=50 deliveries=59 redelivered=9
side effects without dedupe=59, with dedupe table=50
```

این همان {{< term "at-least-once-delivery" "تحویل at-least-once" >}} است: ۹ اثر جانبی تکراری بدون محافظت، و صفر با جدولی که کلیدش id رویداد است. در سرویس واقعی این جدول در همان transaction اثر نوشته می‌شود؛ ببینید [idempotency](/fa/posts/nats-jetstream-idempotency/) و [outbox](/fa/posts/go-outbox-pattern-nats/).

## ترتیب

JetStream ترتیب را فقط داخل یک stream نگه می‌دارد. وقتی یک ack گم شود، redelivery آن را می‌شکند. سه event با نسخه‌های v1 created و v2 paid و v3 shipped برای یک سفارش، و v2 بار اول ack نشده:

```
arrived v1 created  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#1 applied-by-version-check=true
arrived v3 shipped  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#2 applied-by-version-check=false
last-arrival-wins state="paid", version-checked state="shipped" (v3)
```

اعمال به ترتیب رسیدن به state غلط می‌رسد؛ نادیده‌گرفتن نسخه‌هایی که جدیدتر نیستند درست تمام می‌شود. با چند worker، eventهای یک aggregate را روی یک subject نگه دارید؛ اجرا نکردم.

## تغییر schema

event نسخه‌ی ۲ دو فیلد `currency` و `coupon` اضافه می‌کند. consumer نسخه‌ی ۱ که {{< term "tolerant-reader" "tolerant reader" >}} است کار می‌کند؛ نسخه‌ی سخت‌گیر می‌شکند:

```
tolerant v1 reader on v2 event: {OrderID:o-9 Amount:120} err=<nil>
strict v1 reader on v2 event:   err=json: unknown field "currency"
```

فقط فیلد اضافه کنید، هرگز تغییر نام یا معنا؛ قواعدش همان [نسخه‌بندی API](/fa/posts/eng-api-design-versioning-pagination/) است.

## event چاق، event لاغر، request/reply

همان سفارش به صورت event-carried state transfer برابر ۶۲۴ بایت است؛ به صورت اعلان لاغر فقط با id برابر ۱۷۵ بایت، ولی آن‌وقت هر consumer باید با یک request برگردد و آن فراخوانی timeout می‌خواهد ([timeout و retry](/fa/posts/ds-timeouts-retries-backoff/)):

```
callback, responder gone: err=nats: no responders available for request
callback, slow responder: err=nats: timeout
```

چاق: داده کپی می‌شود؛ لاغر: coupling در زمان اجرا.

## خطرها

{{< term "eventual-consistency" "Eventual consistency" >}} در کاربری دیده می‌شود که پرداخت کرده و هنوز «pending» می‌بیند: صادقانه «در حال پردازش» نشان دهید. بدتر از همه حلقه است: دو سرویس که به هم جواب می‌دهند. بدون محدودیت، مال من تا kill switch در ۲۰۰ پیام ادامه داد؛ با فیلد `hops` در envelope متوقف شد.

```
no hop limit  handled=200 dropped-by-hop-limit=0 killed-by-switch=true
max hops=5    handled=5 dropped-by-hop-limit=1 killed-by-switch=false
```

{{< term "poison-message" "poison message" >}} مشکل خواهر آن است: تعداد تحویل را محدود کنید و به یک {{< term "dlq" "dead-letter queue" >}} بفرستید ([retry و DLQ](/fa/posts/nats-jetstream-retry-dlq/)).

## چند نکته‌ی مهم

- فرض کنید تکرار و بههم‌ریختگی ترتیب هست؛ با id تکراری‌زدایی و نسخه‌ها را مقایسه کنید.
- correlation id و causation id را از روز اول در هر envelope بگذارید.
- حلقه‌ها و retryها را با hops یا TTL محدود کنید.
- طبق تجربه‌ی من، اگر یک تیم هر دو طرف را دارد و یک فراخوانی ساده کافی است، سراغ event-driven نروید؛ جداسازی می‌خرید که شاید لازم نباشد.

تست‌ها: unit test برای dedupe و نسخه‌ها و یک تست با سرور توکار برای محدودیت hop، با `go test -race` ([تست JetStream](/fa/posts/nats-jetstream-testing/)).

## تمرین

event ای به نام `PaymentFailed` به choreography اضافه کنید تا orders سفارش را لغو کند.

## قدم بعدی

مقاله‌ی بعدی «service discovery و load balancing» است.
