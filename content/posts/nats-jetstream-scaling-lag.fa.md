+++
date = '2026-10-25T10:00:00+03:30'
draft = false
title = 'چند Worker روی یک Consumer و مانیتورینگ lag در JetStream'
seoTitle = 'چند Worker و مانیتورینگ lag در JetStream'
description = 'چند Worker را روی یک Consumer پایدار JetStream اجرا کنید، ببینید اگر یکی crash کند چه می‌شود، و با ConsumerInfo میزان عقب‌ماندگی (lag) را زیر نظر بگیرید.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "scaling", "monitoring"]
cover = { image = "/images/covers/nats-jetstream-scaling-lag.fa.png", alt = "چند Worker روی یک Consumer و مانیتورینگ lag در JetStream", hiddenInSingle = true, hiddenInList = true }
+++

آخر [مقاله‌ی قبل](/fa/posts/nats-jetstream-retry-dlq/) دو موضوع را وعده داده بودم: اجرای بیش از یک Worker و زیر نظر گرفتن میزان عقب‌ماندگی. تا وقتی پیام‌ها کندتر از توان یک Worker می‌رسند همه‌چیز خوب است، اما بعدش دو سؤال پیش می‌آید: چطور Worker اضافه کنیم بدون اینکه چیزی دوبار پردازش شود، و از کجا بفهمیم صف دارد انباشته می‌شود؟

> همه‌ی مثال‌های زیر را با یک `nats-server` تعبیه‌شده (با JetStream و یک پوشه‌ی موقت برای ذخیره‌سازی) و `nats.go` نسخه‌ی v1.54.0 روی Go 1.26 اجرا کرده‌ام و خروجی‌ها از همان اجراها هستند.

## چند Worker، یک Consumer پایدار

نکته‌ی خاصی وجود ندارد. هر Worker به همان **durable consumer** وصل می‌شود و سرور هر پیام را فقط به یکی از آن‌ها می‌دهد:

```go
sub, err := js.PullSubscribe("jobs.new", "workers", nats.Bind("JOBS", "workers"))
// ...
msgs, err := sub.Fetch(1, nats.MaxWait(500*time.Millisecond))
// process msgs[0], then m.Ack()
```

Consumer یک بار با `AckExplicitPolicy` ساخته شده بود. سه goroutine (`w1`، `w2` و `w3`) راه انداختم که هرکدام Pull Subscription خودش را دارد و هر کار را در ۲۰۰ میلی‌ثانیه انجام می‌دهد، و ۳۰ پیام منتشر کردم. بخشی از لاگ:

```
  0.0s w3 got job-01 (stream seq 1, delivery #1)
  0.0s w2 got job-02 (stream seq 2, delivery #1)
  0.0s w1 got job-03 (stream seq 3, delivery #1)
  0.2s w2 got job-06 (stream seq 6, delivery #1)
  0.2s w3 got job-04 (stream seq 4, delivery #1)
  0.2s w1 got job-05 (stream seq 5, delivery #1)
  ...
deliveries=30 unique=30 pending=0 ackPending=0 redelivered=0
```

۳۰ تحویل، ۳۰ کار یکتا و هیچ تحویل مجددی. کل کار حدود ۲ ثانیه طول کشید، در حالی‌که یک Worker تنها به ۶ ثانیه نیاز داشت. به ترتیب هم دقت کن: `job-06` قبل از `job-04` شروع شد.

## وسط کار یک Worker می‌میرد

حالا بخش جالب. `AckWait` را ۲ ثانیه گذاشتم، ۱۰ کار منتشر کردم و کاری کردم که `w2` روی پیام دومش «crash» کند، یعنی بدون ack متوقف شود:

```
  0.1s w2 got job-06 (stream seq 6, delivery #1)
  0.1s w2 CRASHED while holding job-06 (no ack)
  ...
  2.1s w1 got job-06 (stream seq 6, delivery #2)
deliveries=11 unique=10 pending=0 ackPending=0 redelivered=0
```

سرور به اندازه‌ی `AckWait` صبر کرد و بعد `job-06` را به Workerی که هنوز زنده بود (`w1`) داد. شبکه‌ی ایمنی همین است: ack نیامد یعنی پیام گم نمی‌شود. دو نتیجه دارد:

- **تحویل at-least-once است.** Workerِ مرده ممکن است نصف کار یا کل آن را انجام داده باشد، پس پردازش باید در برابر تکرار ایمن باشد. موضوع مقاله‌ی بعد همین است.
- **ترتیب بین Workerها تضمین نمی‌شود.** `job-06` خیلی بعد از `job-10` پردازش شد. اگر ترتیب سخت‌گیرانه لازم داری، باید طراحی دیگری (مثلاً یک Consumer با یک Worker، یا تقسیم کار بر اساس subject) انتخاب کنی.

## خواندن lag با ConsumerInfo

برای دیدن صف انباشته‌شده از سرور درباره‌ی Consumer می‌پرسیم. مانیتور کوچک من فقط یک ticker است:

```go
i, err := js.ConsumerInfo("JOBS", "workers")
fmt.Printf("pending=%d ackPending=%d redelivered=%d delivered=%d ackFloor=%d\n",
    i.NumPending, i.NumAckPending, i.NumRedelivered,
    i.Delivered.Consumer, i.AckFloor.Consumer)
```

معنی هر عدد:

- `NumPending`: پیام‌هایی که در stream هستند و هنوز به Consumer تحویل داده نشده‌اند. برای «lag» روی همین عدد هشدار بگذار.
- `NumAckPending`: تحویل داده شده ولی هنوز ack نشده، یعنی همین الان در حال پردازش. با دو Worker مشغول، این عدد روی ۲ می‌ماند.
- `NumRedelivered`: پیام‌هایی که دارند دوباره تحویل داده می‌شوند.
- `Delivered.Consumer`: شماره‌ی ترتیبیِ آخرین تحویل در Consumer. تحویل‌های مجدد را هم می‌شمارد.
- `AckFloor.Consumer`: شماره‌ای که همه‌ی تحویل‌های زیر آن ack شده‌اند.

برای این اجرا دو Worker کند (هر کار ۵۰۰ میلی‌ثانیه) گذاشتم، ۴۰ کار را در ثانیه‌ی ۱٫۵ منتشر کردم و `w2` را روی پیام پنجمش crash دادم. `AckWait` برابر ۳ ثانیه بود.

```
  1.0s pending=0   ackPending=0  redelivered=0  delivered=0   ackFloor=0
  1.5s publishing 40 jobs
  2.0s pending=38  ackPending=2  redelivered=0  delivered=2   ackFloor=0
  3.0s pending=34  ackPending=2  redelivered=0  delivered=6   ackFloor=4
  3.5s w2 CRASHED while holding job-09 (no ack)
  4.0s pending=30  ackPending=2  redelivered=0  delivered=10  ackFloor=8
  5.0s pending=28  ackPending=2  redelivered=0  delivered=12  ackFloor=8
  6.0s pending=26  ackPending=2  redelivered=0  delivered=14  ackFloor=8
  7.0s pending=25  ackPending=1  redelivered=1  delivered=16  ackFloor=8
  8.0s pending=23  ackPending=1  redelivered=0  delivered=18  ackFloor=17
 ...
 19.0s pending=1   ackPending=1  redelivered=0  delivered=40  ackFloor=39
 20.0s pending=0   ackPending=0  redelivered=0  delivered=41  ackFloor=41
```

با رسیدن موج پیام‌ها `pending` به ۳۸ می‌پرد و با دو Worker حدود ۴ تا در ثانیه کم می‌شود. بعد از crash سرعت به حدود ۲ تا در ثانیه می‌رسد، چون فقط یک Worker مانده. خودِ crash در دو جا دیده می‌شود: `AckFloor` روی ۸ ثابت ماند تا پیام گیرکرده منتظر بماند، و `NumRedelivered` در ثانیه‌ی ۷٫۰، بعد از تمام شدن `AckWait`، عدد ۱ را نشان داد و وقتی پیام ack شد به ۰ برگشت و floor به ۱۷ پرید. در پایان `delivered` برابر ۴۱ است برای ۴۰ کار: یکی اضافه همان تحویل مجدد است.

## Endpoint مانیتورینگ HTTP

اگر سرور با پورت مانیتورینگ HTTP اجرا شود، همین اعداد را بدون کلاینت هم می‌شود خواند. سرور تعبیه‌شده را با `HTTPPort: 8222` بالا آوردم، ۵ پیام مصرف‌نشده در stream گذاشتم و `curl 'localhost:8222/jsz?consumers=true'` زدم. در JSON، Consumer مربوط به stream با نام `JOBS` این مقادیر را داشت: `num_pending` برابر ۵، و `num_ack_pending` و `num_redelivered` برابر ۰. برای scrape کردن با Prometheus یا یک چک سریع از شل مناسب است.

## چند نکته‌ی مهم

- روی رشد مداوم `NumPending` هشدار بگذار، نه روی یک مقدار بالا. موج ناگهانی عادی است، خطِ پیوسته صعودی مشکل است.
- اگر `NumAckPending` بالا برود و `AckFloor` ثابت بماند، Workerها گیر کرده‌اند یا crash می‌کنند، حتی اگر `pending` خوب به نظر برسد.
- `AckWait` باید از کندترین کار معمولی شما بیشتر باشد، وگرنه پیام Workerهای سالم به دیگری داده می‌شود. برای کارهای طولانی از `m.InProgress()` استفاده کن.
- Worker بیشتر فقط وقتی کمک می‌کند که گلوگاه خودِ پردازش باشد. مطمئن شو دیتابیس یا APIای که Workerها صدا می‌زنند همزمانی بیشتر را تحمل می‌کند.
- `NumRedelivered` در اجرای من فقط برای یک لحظه دیده شد، پس scrape هر چند دقیقه ممکن است آن را از دست بدهد. آن را نشانه بدان، نه شمارنده‌ی کل تلاش‌های مجدد.

## قدم بعدی

تحویل مجدد یعنی ممکن است یک کار دوبار اجرا شود. مقاله‌ی بعد درباره‌ی idempotency و معنی واقعی «exactly-once» در JetStream است: `Nats-Msg-Id`، پنجره‌ی duplicate و Consumerهای idempotent.
