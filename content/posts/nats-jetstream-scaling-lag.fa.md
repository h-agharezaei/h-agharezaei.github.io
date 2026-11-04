+++
date = '2026-10-25T10:00:00+03:30'
draft = false
title = 'چند Worker روی یک Consumer و مانیتورینگ lag در JetStream'
seoTitle = 'چند Worker و مانیتورینگ lag در JetStream'
description = 'چند Worker را روی یک Consumer پایدار JetStream اجرا کنید، ببینید اگر یکی crash کند چه می‌شود، و با ConsumerInfo میزان عقب‌ماندگی (lag) را زیر نظر بگیرید.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "scaling", "monitoring"]
cover = { image = "/images/covers/nats-jetstream-scaling-lag.fa.png", alt = "چند Worker روی یک Consumer و مانیتورینگ lag در JetStream", hiddenInSingle = true }
+++

یک Worker تا وقتی کافی است که پیام‌ها کندتر از توانش برسند. فرض کنید هر کار ۲۰۰ میلی‌ثانیه طول بکشد. یک Worker در ثانیه ۵ کار انجام می‌دهد. اگر ۳۰ پیام یک‌دفعه برسد، آخرین پیام ۶ ثانیه بعد پردازش می‌شود، و اگر هر ثانیه ۱۰ پیام برسد، صف هیچ‌وقت خالی نمی‌شود. آن‌وقت دو سؤال پیش می‌آید: چطور Worker اضافه کنیم بدون اینکه چیزی دو بار پردازش شود؟ و از کجا بفهمیم صف دارد انباشته می‌شود، پیش از آن‌که مشتری شکایت کند؟ [مقاله‌ی قبل](/fa/posts/nats-jetstream-retry-dlq/) هر دو را باز گذاشته بود.

> همه‌ی مثال‌ها را با یک `nats-server` توکار (نسخه‌ی 2.15.1، JetStream روشن، پوشه‌ی موقت برای ذخیره‌سازی) و `nats.go` نسخه‌ی v1.54.0 اجرا کردم. اجرای اولیه‌ی این مقاله روی Go 1.26 بود و برای این بازنویسی همه‌ی اجراها را دوباره با Go 1.27 انجام دادم. کد یک مثال محلی است. زمان‌ها و این‌که کدام Worker کدام پیام را می‌گیرد در هر اجرا کمی فرق می‌کند.

## چند Worker، یک consumer ماندگار

جواب اولی ساده است: ترفندی وجود ندارد. هر Worker به **همان** {{< term "durable-consumer" "consumer ماندگار" >}} وصل می‌شود، و سرور هر پیام را فقط به یکی از آن‌ها می‌دهد. می‌توانید consumer را مثل یک دفترچه‌ی شماره‌ی نوبت فکر کنید که چند باجه از آن استفاده می‌کنند: هر نوبت را فقط یک باجه صدا می‌زند و دفتر یکی است.

چون consumer از نوع {{< term "pull-consumer" "pull" >}} است، هر Worker خودش پیام می‌خواهد و سرور فقط به درخواست‌ها جواب می‌دهد. کد هر Worker:

```go
sub, err := js.PullSubscribe("jobs.new", "workers", nats.Bind("JOBS", "workers"))
// ...
msgs, err := sub.Fetch(1, nats.MaxWait(500*time.Millisecond))
// process msgs[0], then m.Ack()
```

`nats.Bind("JOBS", "workers")` یعنی «به consumer موجود به نام `workers` در stream به نام `JOBS` وصل شو و چیز تازه نساز».

برنامه‌ی آزمایشی یک فایل Go است که سرور توکار را بالا می‌آورد، stream به نام `JOBS` و consumer ماندگار `workers` با `AckExplicitPolicy` را می‌سازد و Workerها را به‌صورت goroutine اجرا می‌کند. هر حالت آزمایش را با یک آرگومان انتخاب می‌کنم.

**آزمایش اول:** سه goroutine (`w1`، `w2`، `w3`)، هرکدام با subscription جدا، هرکدام ۲۰۰ میلی‌ثانیه برای هر کار. ۳۰ پیام منتشر کردم. شش خط اول لاگ، و خط آخر که برنامه چاپ می‌کند:

```
  0.0s w3 got job-01 (stream seq 1, delivery #1)
  0.0s w1 got job-02 (stream seq 2, delivery #1)
  0.0s w2 got job-03 (stream seq 3, delivery #1)
  0.2s w3 got job-06 (stream seq 6, delivery #1)
  0.2s w1 got job-04 (stream seq 4, delivery #1)
  0.2s w2 got job-05 (stream seq 5, delivery #1)
  ...
deliveries=30 unique=30 pending=0 ackPending=0 redelivered=0
```

هر خط یعنی: چند ثانیه بعد از شروع، کدام Worker کدام کار را گرفت، شماره‌ی آن در stream، و شماره‌ی تحویل (`delivery #1` یعنی بار اول). در همان لحظه‌ی صفر، هر سه Worker یک کار گرفتند و در ۰٫۲ ثانیه سه کار بعدی را. خط آخر می‌گوید ۳۰ تحویل انجام شد، ۳۰ کار متفاوت بود (`unique`)، چیزی باقی نماند و چیزی دوباره تحویل نشد. یعنی هیچ کاری دو بار انجام نشد.

کل ۳۰ کار حدود ۲ ثانیه طول کشید: ۳۰ × ۰٫۲ ثانیه تقسیم بر ۳ Worker. یک Worker تنها به ۶ ثانیه نیاز داشت. یک نکته‌ی ظریف هم در لاگ هست: ترتیب سخت‌گیرانه نیست. در ثانیه‌ی ۰٫۲ کار شماره‌ی ۶ زودتر از شماره‌ی ۴ شروع شد.

## وقتی یک Worker وسط کار می‌میرد

حالا بدترین حالت. `AckWait` را ۲ ثانیه گذاشتم، ۱۰ کار منتشر کردم و `w2` را طوری برنامه‌ریزی کردم که روی دومین پیامش «کرش کند»، یعنی بدون ack متوقف شود. لاگ کامل:

```
  0.0s w1 got job-02 (stream seq 2, delivery #1)
  0.0s w2 got job-01 (stream seq 1, delivery #1)
  0.0s w3 got job-03 (stream seq 3, delivery #1)
  0.1s w1 got job-06 (stream seq 6, delivery #1)
  0.1s w2 got job-04 (stream seq 4, delivery #1)
  0.1s w2 CRASHED while holding job-04 (no ack)
  0.1s w3 got job-05 (stream seq 5, delivery #1)
  0.2s w1 got job-07 (stream seq 7, delivery #1)
  0.2s w3 got job-08 (stream seq 8, delivery #1)
  0.3s w3 got job-09 (stream seq 9, delivery #1)
  0.3s w1 got job-10 (stream seq 10, delivery #1)
  2.1s w3 got job-04 (stream seq 4, delivery #2)
deliveries=11 unique=10 pending=0 ackPending=0 redelivered=0
```

(این‌که کدام Worker کرش می‌کند و روی کدام کار، در هر اجرا فرق می‌کند. این اجرا `w2` و `job-04` بود.)

`w2` کار شماره‌ی ۴ را گرفت و مرد، بدون ack. بقیه‌ی کارها تا ۰٫۳ ثانیه تمام شدند. بعد سکوت تا ۲٫۱ ثانیه. حساب ساده است: کار حدود ۰٫۱ ثانیه تحویل شد و `AckWait` برابر ۲ ثانیه است، پس ۰٫۱ + ۲ = ۲٫۱. سرور بعد از این مدت فرض کرد Worker مرده و همان پیام را به Workerی که هنوز زنده بود (`w3`) با `delivery #2` داد. خط آخر: ۱۱ تحویل برای ۱۰ کار متفاوت. تحویل اضافه همین دوباره‌فرستادن است.

این تمام شبکه‌ی ایمنی است: ack نیامده یعنی پیام گم نشده، دوباره می‌آید. دو نتیجه دارد:

- **تحویل از نوع {{< term "at-least-once-delivery" "at-least-once" >}} است.** یعنی هر پیام یک بار یا بیشتر می‌رسد. Worker کرش‌کرده شاید نصف کار را کرده بود و شاید همه‌اش را، پس پردازش باید تکرارشدنی باشد.
- **ترتیب بین Workerها تضمین نمی‌شود.** `job-04` خیلی بعد از `job-10` پردازش شد. اگر برای هر کلید ترتیب سخت‌گیرانه می‌خواهید، طراحی دیگری لازم است، مثلاً یک consumer با یک Worker، یا تقسیم کار بر اساس subject.

## خواندن lag با ConsumerInfo

حالا سؤال دوم: چطور بفهمیم صف دارد انباشته می‌شود؟ از خود سرور درباره‌ی consumer بپرسیم. مانیتور کوچک من فقط یک تایمر است که هر ثانیه این را صدا می‌زند:

```go
i, err := js.ConsumerInfo("JOBS", "workers")
fmt.Printf("pending=%d ackPending=%d redelivered=%d delivered=%d ackFloor=%d\n",
    i.NumPending, i.NumAckPending, i.NumRedelivered,
    i.Delivered.Consumer, i.AckFloor.Consumer)
```

معنی هر عدد:

- `NumPending`: تعداد پیام‌هایی که در stream هستند و هنوز به consumer تحویل نشده‌اند. عددی که برای «lag» باید رویش هشدار گذاشت همین است.
- `NumAckPending`: پیام‌هایی که تحویل شده‌اند ولی هنوز ack نشده‌اند، یعنی همین الآن در دست کارند. با دو Worker مشغول این عدد ۲ است.
- `NumRedelivered`: پیام‌هایی که دارند دوباره تحویل می‌شوند.
- `Delivered.Consumer`: شماره‌ی ترتیب آخرین تحویل، از دید consumer. تحویل دوباره‌ها را هم می‌شمارد.
- `AckFloor.Consumer`: شماره‌ای که همه‌ی تحویل‌های زیر آن ack شده‌اند.

برای این اجرا دو Worker کند گذاشتم (۵۰۰ میلی‌ثانیه برای هر کار). ۴۰ کار را در ثانیه‌ی ۱٫۵ منتشر کردم، `AckWait` را ۳ ثانیه گذاشتم و `w2` را طوری تنظیم کردم که روی پنجمین پیامش کرش کند. خروجی:

```
  1.0s pending=0   ackPending=0  redelivered=0  delivered=0   ackFloor=0
  1.5s publishing 40 jobs
  2.0s pending=38  ackPending=2  redelivered=0  delivered=2   ackFloor=0
  3.0s pending=34  ackPending=2  redelivered=0  delivered=6   ackFloor=4
  3.6s w2 CRASHED while holding job-09 (no ack)
  4.0s pending=30  ackPending=2  redelivered=0  delivered=10  ackFloor=8
  5.0s pending=28  ackPending=2  redelivered=0  delivered=12  ackFloor=8
  6.0s pending=26  ackPending=2  redelivered=0  delivered=14  ackFloor=8
  7.0s pending=25  ackPending=1  redelivered=1  delivered=16  ackFloor=8
  8.0s pending=23  ackPending=1  redelivered=0  delivered=18  ackFloor=17
  9.0s pending=21  ackPending=1  redelivered=0  delivered=20  ackFloor=19
 ...
 19.0s pending=1   ackPending=1  redelivered=0  delivered=40  ackFloor=39
 20.0s pending=0   ackPending=0  redelivered=0  delivered=41  ackFloor=41
```

(خط‌های ۱۰ تا ۱۸ ثانیه را برای کوتاهی حذف کرده‌ام؛ همان الگو بود: `pending` دو تا دو تا کم می‌شود. برنامه تا ثانیه‌ی ۲۵ همان خط صفر را ادامه داد.)

از بالا بخوانیم:

- در ثانیه‌ی ۱٫۵ ناگهان ۴۰ پیام می‌رسد. `pending` در ۲٫۰ برابر ۳۸ است: ۴۰ پیام منهای ۲ پیامی که الآن دست دو Worker است (`ackPending=2`).
- با دو Worker، هرکدام ۲ کار در ثانیه (۵۰۰ میلی‌ثانیه برای هر کار)، صف با نرخ ۴ پیام در ثانیه خالی می‌شود: ۳۸ ← ۳۴ ← ۳۰.
- در ۳٫۶ `w2` کرش می‌کند و کار `job-09` را در دست دارد. از این به بعد فقط `w1` کار می‌کند و `pending` ثانیه‌ای ۲ تا کم می‌شود (۳۰ ← ۲۸ ← ۲۶).
- کرش در دو جا دیده می‌شود. اول، `AckFloor` روی ۸ ماند، چون پیام گیرکرده ack نشده بود و کف تأییدها نمی‌تواند از آن رد شود. دوم، `ackPending` ثابت ۲ ماند (یکی کار `w1` و یکی پیام گیرکرده‌ی `w2`).
- چون `AckWait` ۳ ثانیه است، مهلت پیام گیرکرده حدود ۳٫۶ + ۳ = ۶٫۶ ثانیه تمام می‌شود. در ۷٫۰ شمارنده‌ی `redelivered` یک است و `ackPending` از ۲ به ۱ آمده: سرور دیگر پیام را «در دست کار» حساب نمی‌کند و منتظر دوباره‌فرستادنش است. در ۸٫۰ دوباره `redelivered` صفر است و `AckFloor` از ۸ به ۱۷ پریده، یعنی پیام دوباره‌تحویل‌شده ack شد و حالا همه‌ی تحویل‌ها تا ۱۷ تأیید شده‌اند. دقیق‌تر از این، یعنی دقیقاً کدام لحظه‌ی بین ۷ و ۸ ثانیه، را اندازه نگرفتم.
- در پایان `delivered` برابر ۴۱ است برای ۴۰ کار: همان تحویل اضافه.

## همان اعداد از طریق HTTP

اگر سرور با پورت مانیتورینگ HTTP اجرا شود، همین اعداد را بدون هیچ کلاینتی می‌توانید بخوانید. سرور توکار را با یک پورت HTTP آزاد بالا آوردم، ۵ پیام در stream گذاشتم که هیچ‌کس نمی‌خواند و این را اجرا کردم:

```bash
curl 'localhost:<port>/jsz?consumers=true'
```

در JSON برگشتی، consumer مربوط به stream به نام `JOBS` این را نشان داد: `num_pending` برابر ۵، `num_ack_pending` برابر ۰ و `num_redelivered` برابر ۰. برای جمع‌کردن با Prometheus یا یک بررسی سریع از شل خوب است.

## خواندن درست این اعداد

- روی **رشد** `NumPending` در طول زمان هشدار بگذارید، نه روی یک مقدار بزرگ. هجوم ناگهانی عادی است؛ خطی که پیوسته بالا می‌رود مشکل است.
- اگر `NumAckPending` بالا برود و `AckFloor` ثابت بماند، Workerها گیر کرده‌اند یا کرش می‌کنند، حتی اگر `pending` خوب به نظر برسد.
- {{< term "ack-wait" "AckWait" >}} باید از کندترین کار معمولی شما بلندتر باشد. وگرنه پیام Worker سالم، وسط کارش، به Worker دیگری داده می‌شود و کار دو بار انجام می‌شود. برای کارهای بلند، طبق مستندات `nats.go` می‌توانید با `m.InProgress()` مهلت را تمدید کنید.
- Worker بیشتر فقط وقتی کمک می‌کند که گلوگاه خود کار باشد. بررسی کنید دیتابیس یا APIی که پشت Workerهاست همزمانیِ بیشتر را تحمل کند.
- `NumRedelivered` در اجرای من فقط برای لحظه‌ای دیده شد، پس مانیتوری که هر چند دقیقه یک‌بار می‌خواند ممکن است آن را از دست بدهد. آن را راهنما بدانید، نه شمارنده‌ی کل تلاش‌های مجدد.

## قدم بعدی

دوباره‌فرستادن یعنی یک کار ممکن است دو بار اجرا شود. «Idempotency و معنای exactly-once در JetStream» دقیقاً درباره‌ی همین است: `Nats-Msg-Id`، پنجره‌ی تشخیص تکراری و consumerهای خودتوان.
