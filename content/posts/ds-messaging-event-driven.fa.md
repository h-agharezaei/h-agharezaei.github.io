+++
date = '2027-05-29T10:00:00+03:30'
draft = false
title = 'پیام‌رسانی و معماری رویدادمحور'
description = 'معماری رویدادمحور با Go و NATS: command و event، fan-out، envelope، consumer خودتوان، ترتیب، تغییر schema و محدودکردن حلقه‌ها.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "messaging", "event-driven", "nats", "go"]
cover = { image = "/images/covers/ds-messaging-event-driven.fa.png", alt = "پیام‌رسانی و معماری رویدادمحور", hiddenInSingle = true }
+++
مشتری یک سفارش ثبت می‌کند. سرویس سفارش، سرویس پرداخت را صدا می‌زند و آن هم سرویس ارسال را. اگر در همان لحظه سرویس ارسال از دسترس خارج باشد، کل زنجیره شکست می‌خورد، با اینکه پرداخت مشتری انجام شده است. هر سرویس باید سرویس بعدی را بشناسد و هم‌زمان با بقیه بالا باشد.

همین جریان را می‌شود طور دیگری سیم‌کشی کرد. سرویس سفارش هیچ‌کس را صدا نمی‌زند. فقط یک واقعیت را اعلام می‌کند: «سفارش o-1 ثبت شد». هر که به آن اهمیت می‌دهد، پرداخت، ارسال یا سرویس ایمیل، اعلام را می‌شنود و هر وقت آماده بود سهم خودش را انجام می‌دهد. اعلام از طریق یک **message broker** می‌رسد، سروری که کارش گرفتن پیام‌ها و رساندنشان به سرویس‌هایی است که آن‌ها را خواسته‌اند. در این مقاله broker همان NATS است. این سبک را معماری رویدادمحور می‌گویند و موضوع این مقاله است.

وابستگی واقعی را برمی‌دارد، ولی مجانی نیست. همین جریان حالا تکرار، به‌هم‌ریختگی ترتیب، تغییر schema و حلقه دارد. در اجرای من ۵۰ event به ۵۹ اثر جانبی رسید. پس این مقاله این مشکل‌ها را یکی‌یکی می‌گذراند، هرکدام با یک آزمایش کوچک. [مقاله‌ی قبل](/fa/posts/ds-cqrs-event-sourcing/) با event برای انتقال state از یک مدل به مدل دیگر تمام شد؛ JetStream، بخش ماندگار NATS، در [سری NATS](/fa/posts/nats-jetstream-retry-dlq/) آمده است.

> برچسب صادقانه: همه‌چیز روی یک ماشین است. سرویس‌ها goroutine‌اند و «شبکه» loopback به یک nats-server توکار است (نسخه‌ی v2.15.1 با nats.go نسخه‌ی v1.54.0) که روی یک پورت تصادفی بالا می‌آید. الگوها را نشان می‌دهد، نه شبکه‌ی واقعی را. دمو را با Go 1.27 دوباره اجرا کردم و `go test -race` می‌گذرد. شمارش نشان می‌دهم و زمان نه.

## command و event و query

قبل از هر کد، سه نوع پیام هست و قاطی کردنشان بیشتر سردرگمی‌ها را می‌سازد:

| | Command | Event | Query |
|---|---|---|---|
| نام | امری: `PlaceOrder` | گذشته: `OrderPlaced` | `GetOrder` |
| معنا | لطفاً این را انجام بده | این اتفاق افتاد | بگو |
| گیرنده | یکی | صفر یا بیشتر | یکی |
| ردشدنی | بله | نه، یک واقعیت است | بی‌معنی |

command از یک سرویس مشخص می‌خواهد کاری بکند و آن سرویس می‌تواند نه بگوید. event چیزی را گزارش می‌کند که قبلاً اتفاق افتاده، پس کسی نمی‌تواند ردش کند و ناشر حتی نمی‌داند چند سرویس گوش می‌دهند: می‌تواند صفر باشد یا ده. query اطلاعات می‌خواهد و منتظر جواب است. بقیه‌ی مقاله بیشتر درباره‌ی event است، ولی هر سه را می‌بینیم.

## یک گیرنده یا چند گیرنده

اولین سؤال برای یک broker این است که چه کسی پیام را می‌گیرد. ۳۰ پیام را به سه گیرنده با سه روش فرستادم و شمردم هرکدام چندتا گرفت:

```
core pub/sub, 3 subscribers      : 30 30 30
core queue group, 3 members      : 13 10 7
JetStream work queue, 3 workers  : 10 10 10
```

- **pub/sub معمولی.** در {{< term "publish-subscribe" "publish-subscribe" >}} ناشرها به یک *subject* (نامی نقطه‌دار مثل `events.order.placed`) می‌فرستند و هر مشترکِ آن subject همه‌ی پیام‌ها را می‌گیرد. برای همین هر مشترک ۳۰ تا دارد. event به همین شکل هم‌زمان به پرداخت و ارسال و ایمیل می‌رسد.
- **queue group.** مشترک‌هایی که نام گروه مشترک دارند یک {{< term "queue-group" "queue group" >}} می‌سازند و هر پیام فقط به یک عضو می‌رسد. با این روش کار را بین چند نسخه از یک سرویس تقسیم می‌کنید. تقسیم را سرور تعیین می‌کند و مساوی نیست: ۱۳ و ۱۰ و ۷ در اجرای اصلی. از اجرایی به اجرای دیگر هم عوض می‌شود؛ اجرای دوباره‌ام با Go 1.27 ۱۲ و ۷ و ۱۱ و بار دیگر ۱۳ و ۸ و ۹ داد.
- **work queue در JetStream.** یک stream ذخیره‌شده است که هر پیام بعد از ack یک worker از آن برداشته می‌شود. سه worker یک consumer نام‌دار مشترک دارند و هر وقت آزادند پیام می‌کشند (pull). اینجا هرکدام ۱۰ تا گرفت (در اجراهای دوباره‌ام هم)، ولی قولش را نمی‌دهم: workerی که آزاد است پیام بعدی را می‌کشد، پس تقسیم به سرعت هرکدام بستگی دارد ([scaling و lag](/fa/posts/nats-jetstream-scaling-lag/)).

## choreography یا orchestration

حالا یک جریان واقعی. سه سرویس، orders و payments و shipping، باید برای یک سفارش همکاری کنند. دو راه برای سازمان‌دهی هست.

در {{< term "choreography" "choreography" >}} هیچ‌کس مسئول نیست. هر سرویس به event‌ای که به آن مربوط است واکنش نشان می‌دهد و event خودش را منتشر می‌کند. رقصنده‌هایی را تصور کنید که هرکدام نقش خودشان را بلدند. در {{< term "orchestration" "orchestration" >}} یک هماهنگ‌کننده مسئول است: به payments یک command می‌فرستد، منتظر پاسخ می‌ماند و بعد به shipping command می‌فرستد.

برای choreography سرویس‌ها با یک {{< term "event-envelope" "event envelope" >}} حرف می‌زنند، یعنی یک قالب ثابت دور هر event با فیلدهای metadata یکسان: یک `id`، یک `type`، زمان، سرویس مبدأ (`source`)، نسخه‌ی schema، یک **correlation id** که در کل جریان کسب‌وکار ثابت می‌ماند و یک **causation id** که نام eventی را دارد که مستقیماً باعث این event شده. بعد `data` می‌آید. CloudEvents مشخصات شناخته‌شده‌ای برای چنین envelope‌هایی است؛ مال من شبیه آن است، نه منطبق (نام فیلدها از خودم است).

این خروجی واقعی با یک correlation id (`corr-42`) است. از بالا به پایین بخوانید:

```
orders    publish OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  receive OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  publish PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  receive PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  publish ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
orders    receive ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
```

orders رویداد `OrderPlaced` را منتشر می‌کند و علتی ندارد (`-`). payments واکنش نشان می‌دهد و eventِ `PaymentCaptured`ش `cause=evt-1` دارد، پس می‌بینید کدام event آن را ساخته. shipping به آن واکنش نشان می‌دهد و در پایان orders می‌شنود که ارسال انجام شده. هیچ سرویسی سرویس دیگر را صدا نزد. causation id زنجیره‌ی «چه کسی به چه واکنش نشان داد» را بازسازی می‌کند و correlation id تمام خط‌های log این سفارش را در همه‌ی سرویس‌ها پیدا می‌کند.

orchestration همین سه گام را طور دیگری انجام می‌دهد. هماهنگ‌کننده `CapturePayment` را می‌فرستد و منتظر پاسخ می‌ماند، بعد `DispatchShipping` را. این خروجی واقعی همان اجراست که از request و reply در NATS استفاده می‌کند:

```
orchestrator send CapturePayment  id=evt-4
payments     command CapturePayment  id=evt-4
orchestrator got  PaymentCaptured id=evt-5
orchestrator send DispatchShipping id=evt-6
shipping     command DispatchShipping id=evt-6
orchestrator got  ShippingDispatched id=evt-7
```

جریان در یک جا، یک تابع، خوانا است و مسیر شکست جای روشنی دارد: اگر گامی شکست بخورد، هماهنگ‌کننده جایی است که compensation (خنثی کردن گام‌های قبلی، مثل [مقاله‌ی saga](/fa/posts/ds-saga-vs-2pc/)) از آن شروع می‌شود. طبق تجربه‌ی من: orchestration برای جریان‌های پولی مناسب است و choreography برای واکنش‌های مستقل مثل ارسال notification.

## تضمین‌های تحویل: چرا تکرار پیش می‌آید

برگردیم به عدد ابتدای مقاله. broker درباره‌ی تحویل می‌تواند یکی از سه قول را بدهد و یک مثال کوچک فرقشان را نشان می‌دهد. فرض کنید پیام می‌گوید «مبلغ ۱۰ را از مشتری بگیر» و consumer شارژ را انجام می‌دهد و بعد «انجام شد» را برمی‌گرداند ({{< term "acknowledgement" "تأیید" >}}، یا ack).

- **At-most-once (حداکثر یک بار).** broker پیام را یک بار می‌فرستد و دیگر هرگز. اگر consumer پیش از شارژ crash کند، پیام گم می‌شود و از کسی پول گرفته نمی‌شود. هیچ‌چیز دوبار انجام نمی‌شود، ولی ممکن است کاری صفر بار انجام شود.
- **At-least-once (دست‌کم یک بار).** broker پیام را نگه می‌دارد تا ack برسد و اگر ack در مهلت نرسد دوباره می‌فرستد (JetStream این مهلت را {{< term "ack-wait" "ack wait" >}} می‌نامد). حالا فرض کنید consumer شارژ می‌کند و پیش از فرستادن ack crash می‌کند. broker ack نمی‌بیند و دوباره تحویل می‌دهد و مشتری دوبار شارژ می‌شود. چیزی گم نمی‌شود، ولی ممکن است کاری دوبار انجام شود. این همان {{< term "at-least-once-delivery" "تحویل at-least-once" >}} است و انتخاب معمول است، چون گم شدن پیام معمولاً بدتر است.
- **اثر exactly-once.** چیزی که مردم واقعاً می‌خواهند. تا جایی که می‌دانم، شبکه نمی‌تواند تحویل «دقیقاً یک بار» را قابل‌اعتماد بدهد، چون broker نمی‌تواند بفهمد خود پیام گم شده یا فقط ack آن. چیزی که می‌شود ساخت تحویل at-least-once است به‌علاوه‌ی consumerی که {{< term "idempotency" "idempotent" >}} باشد: شناسه‌ی eventهایی را که پردازش کرده به یاد دارد و تکرار را نادیده می‌گیرد. تحویل دوبار رخ می‌دهد، ولی اثر یک بار.

با عدد نشانش بدهم. دمو ۵۰ event را به یک consumer در JetStream با ack wait برابر ۳۰۰ میلی‌ثانیه می‌فرستد. handler در حدود ۲۰٪ تحویل‌های اول بعد از اثر جانبی و پیش از ack «crash» می‌کند (با مولد تصادفی seedدار، پس هر بار یکسان است). دو شمارنده کنار هم کار می‌کنند: یکی هر اثر جانبی را می‌شمارد و دیگری هر شناسه‌ی event را فقط بار اول می‌شمارد، که کار جدول dedupe است.

```
events=50 deliveries=59 redelivered=9
side effects without dedupe=59, with dedupe table=50
```

۵۰ event بود و ۵۹ تحویل: ۹ event بار اول ack نشدند، JetStream ۳۰۰ میلی‌ثانیه صبر کرد و دوباره فرستادشان. بدون محافظت، handler اثر جانبی را ۵۹ بار انجام داد که ۹ تایش تکراری بود. با جدولی که کلیدش شناسه‌ی event است ۵۰ بار انجام داد، یک بار برای هر event. نتیجه در اجراهای دوباره‌ام با Go 1.27 هم همین بود. در سرویس واقعی این جدول باید در همان transaction پایگاه‌داده‌ی اثر نوشته شود، وگرنه باز هم یک crash می‌تواند بین این دو بیفتد؛ ببینید [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) و [الگوی outbox](/fa/posts/go-outbox-pattern-nats/).

## ترتیب

چیز دوم که broker قولش را نمی‌دهد ترتیب است. تا جایی که می‌دانم، stream در JetStream پیام‌ها را به ترتیبی که منتشر شده‌اند نگه می‌دارد، ولی ترتیب برای یک consumer باز هم می‌تواند به هم بخورد و مشکل ack بالا برای این کار کافی است. سه event برای یک سفارش را در نظر بگیرید: v1 created و v2 paid و v3 shipped. consumer بار اول v2 را ack نمی‌کند. چیزی که می‌بیند:

```
arrived v1 created  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#1 applied-by-version-check=true
arrived v3 shipped  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#2 applied-by-version-check=false
last-arrival-wins state="paid", version-checked state="shipped" (v3)
```

`delivery#N` یعنی این پیام چندمین بار تحویل شده است. وقتی اولین تحویل v2 ack نگرفت، broker سراغ v3 رفت و ۳۰۰ میلی‌ثانیه بعد v2 را دوباره تحویل داد، بعد از v3. handlerی که eventها را به ترتیب رسیدن اعمال می‌کند به `paid` می‌رسد که غلط است، چون سفارش قبلاً ارسال شده. روش دوم یک شماره‌ی نسخه کنار سفارش نگه می‌دارد و هر eventی را که جدیدتر نیست نادیده می‌گیرد. v2 دیررسیده را رد می‌کند (`applied-by-version-check=false`) و به `shipped` می‌رسد که درست است. با چند worker، eventهای یک سفارش را روی یک subject بر اساس id آن نگه دارید؛ این را اجرا نکردم.

## تغییر schema

eventها بیشتر از کدی که منتشرشان می‌کند عمر می‌کنند و ناشر و consumer در زمان‌های مختلف deploy می‌شوند. فرض کنید نسخه‌ی ۲ یک event دو فیلد `currency` و `coupon` اضافه می‌کند، در حالی که consumerی که برای نسخه‌ی ۱ نوشته شده هنوز اجرا می‌شود. consumerی که فیلدهای ناشناخته را نادیده می‌گیرد، یک {{< term "tolerant-reader" "tolerant reader" >}}، به کار ادامه می‌دهد. consumer سخت‌گیر می‌شکند:

```
tolerant v1 reader on v2 event: {OrderID:o-9 Amount:120} err=<nil>
strict v1 reader on v2 event:   err=json: unknown field "currency"
```

این دو خواننده همان struct Go هستند. خواننده‌ی tolerant از `json.Unmarshal` ساده استفاده می‌کند که فیلدهای ناشناخته را نادیده می‌گیرد. خواننده‌ی strict از decoder با `DisallowUnknownFields` استفاده می‌کند و روی اولین فیلد تازه خطا می‌دهد. پس قاعده برای ناشر: فقط فیلد اضافه کنید و هرگز نام فیلد یا معنایش را عوض نکنید. این‌ها همان قاعده‌های [نسخه‌بندی API](/fa/posts/eng-api-design-versioning-pagination/) است.

## event چاق، event لاغر، request/reply

یک event چقدر باید داده داشته باشد؟ یک انتخاب event **چاق** است که همه‌ی داده را دارد (به آن event-carried state transfer می‌گویند): consumer به چیز دیگری نیاز ندارد. انتخاب دیگر event **لاغر** است، اعلانی که فقط می‌گوید «سفارش o-5 عوض شد» با id آن، و consumer برای جزئیات یک بار برمی‌گردد و می‌پرسد. در دمو همان سفارش به شکل event چاق ۶۲۴ بایت است و به شکل لاغر ۱۷۵ بایت. ولی event لاغر هر consumer را وادار می‌کند یک request برگرداند و آن فراخوانی timeout می‌خواهد ([timeout و retry](/fa/posts/ds-timeouts-retries-backoff/)). سه نتیجه‌ی ممکن این فراخوانی:

```
callback with responder: 622 bytes, err=<nil>
callback, responder gone: err=nats: no responders available for request (no-responders=true)
callback, slow responder: err=nats: timeout (timeout=true)
```

وقتی سرویس orders جواب می‌دهد، consumer سفارش کامل را می‌گیرد (۶۲۲ بایت). وقتی دیگر کسی subscribe نیست، NATS به‌جای اینکه caller را تا timeout منتظر بگذارد «no responders» گزارش می‌کند. وقتی پاسخ‌دهنده زنده است ولی کند (بعد از ۶۰۰ میلی‌ثانیه جواب می‌دهد و caller ۲۰۰ میلی‌ثانیه صبر می‌کند)، فراخوانی با timeout تمام می‌شود. پس: eventهای چاق داده را در چند جا کپی می‌کنند و eventهای لاغر سرویس‌ها را در زمان اجرا به هم وابسته می‌کنند.

## خطرها

{{< term "eventual-consistency" "Eventual consistency" >}} در کاربری دیده می‌شود که همین الان پرداخت کرده و هنوز «pending» می‌بیند، چون event هنوز پردازش نشده. صادقانه «در حال پردازش» نشان دهید و وانمود نکنید.

بدترین مشکل حلقه است: دو سرویس که هرکدام به event دیگری با یک event تازه جواب می‌دهند. در دمو سرویس A و B دقیقاً همین کار را می‌کنند. بدون محدودیت تا وقتی kill switch من در ۲۰۰ پیام متوقفش کرد ادامه داد. با شمارنده‌ی `hops` در envelope، که هر سرویس آن را یکی زیاد می‌کند و از یک حداکثر جلوتر نمی‌رود، خودش متوقف شد:

```
no hop limit  handled=200 dropped-by-hop-limit=0 killed-by-switch=true
max hops=5    handled=5 dropped-by-hop-limit=1 killed-by-switch=false
```

خط اول حلقه‌ای است که kill switch بعد از ۲۰۰ پیام قطعش کرد. در خط دوم، پنج hop اول پردازش شد و پیام ششم دور ریخته شد چون به سقف رسیده بود.

{{< term "poison-message" "poison message" >}} مشکل خواهر آن است: پیامی که consumer را هر بار به شکست می‌کشاند، پس تحویل دوباره کمکی نمی‌کند. تعداد تحویل را محدود کنید و پیام را به یک {{< term "dlq" "dead-letter queue" >}} بفرستید ([retry و DLQ](/fa/posts/nats-jetstream-retry-dlq/)).

## دام‌های پیام‌رسانی

- **تکرار و به‌هم‌ریختگی ترتیب را فرض کنید.** با شناسه‌ی event تکراری‌زدایی کنید و پیش از اعمال هر event نسخه‌ها را مقایسه کنید.
- **correlation id و causation id را از روز اول در هر envelope بگذارید.** بعداً نمی‌شود آن‌ها را به eventهایی که قبلاً رخ داده‌اند اضافه کرد، و بدون آن‌ها اشکال‌یابی یک جریان میان سرویس‌ها حدس زدن است.
- **هر حلقه را محدود کنید.** از شمارنده‌ی hop یا TTL استفاده کنید و تعداد retryها را هم محدود کنید.
- **پیش‌فرض را رویدادمحور نگذارید.** طبق تجربه‌ی من، اگر یک تیم هر دو طرف را دارد و یک فراخوانی ساده کافی است، سراغ event نروید؛ جداسازی می‌خرید که شاید لازم نباشد.

تست‌ها unit test برای dedupe و نسخه‌ها هستند و یک تست با سرور توکار برای محدودیت hop، با `go test -race` ([تست JetStream](/fa/posts/nats-jetstream-testing/)).

## تمرین

eventای به نام `PaymentFailed` به choreography اضافه کنید تا orders سفارش را لغو کند.

## قدم بعدی

[service discovery و load balancing](/fa/posts/ds-service-discovery-load-balancing/): فراخوانی مستقیم، برخلاف پیام از طریق bus، اول باید بداند سرویس مقابل کجاست.
