+++
date = '2026-11-24T10:00:00+03:30'
draft = false
title = 'Idempotency و معنای exactly-once در JetStream'
description = 'معنای واقعی exactly-once در NATS JetStream: حذف تکراری‌ها هنگام انتشار با Nats-Msg-Id و محدودیت زمانی آن، و Consumer idempotent، با اجرای واقعی.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "idempotency", "exactly-once"]
cover = { image = "/images/covers/nats-jetstream-idempotency.fa.png", alt = "Idempotency و معنای exactly-once در JetStream", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/nats-jetstream-scaling-lag/) با یک واقعیت ناخوشایند تمام شد: وقتی Worker بدون ack می‌میرد پیام دوباره تحویل داده می‌شود و ممکن است یک کار دوبار اجرا شود. جواب رایج این است که «از exactly-once استفاده کن». در این مقاله با آزمایش اجزایی که JetStream در اختیارمان می‌گذارد (حذف تکراری‌ها هنگام انتشار، ack و یک handler ایمن در برابر تکرار) می‌خواهم ببینم این عبارت واقعاً چه معنایی می‌تواند داشته باشد.

> همه‌ی مثال‌های زیر را با یک `nats-server` تعبیه‌شده‌ی نسخه‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 روی Go 1.26 اجرا کرده‌ام و خروجی‌ها از همان اجراها هستند.

## حذف تکراری‌ها هنگام انتشار با Nats-Msg-Id

اگر Publisher دچار timeout شود و دوباره بفرستد، ممکن است دو نسخه در stream بنشیند. برای جلوگیری، با `nats.MsgId` یک شناسه می‌گذاریم که هدر `Nats-Msg-Id` را تنظیم می‌کند. stream شناسه‌ها را به اندازه‌ی **duplicate window** (تنظیم `Duplicates`) به خاطر می‌سپارد. من آن را ۲ ثانیه گذاشتم تا رفتار بیرون از پنجره را هم ببینم:

```go
js.AddStream(&nats.StreamConfig{Name: "PAY", Subjects: []string{"pay.>"}, Duplicates: 2 * time.Second})
ack, err := js.Publish("pay.created", []byte("order-1001"), nats.MsgId("order-1001"))
fmt.Println(ack.Sequence, ack.Duplicate)
```

```
  0.0s publish #1: err=<nil> seq=1 duplicate=false
  0.0s publish #2: err=<nil> seq=1 duplicate=true
  0.0s stream messages: 1
  0.0s same payload, different MsgId: seq=2 duplicate=false
  0.0s stream messages: 2
  3.0s after 3s, same MsgId again: seq=3 duplicate=false
  3.0s stream messages: 3
```

انتشار دوم بدون خطا انجام می‌شود، اما `PubAck` مقدار `Duplicate: true` دارد و به sequence پیام اصلی اشاره می‌کند، و stream هنوز یک پیام دارد. دو نکته: حذف تکراری بر اساس شناسه است نه محتوا (همان payload با شناسه‌ی دیگر ذخیره شد)، و محدود به زمان است: بعد از ۳ ثانیه (بیرون از پنجره‌ی ۲ ثانیه‌ای من) همان شناسه دوباره به‌عنوان پیام جدید ذخیره شد. پس duplicate window یک شبکه‌ی ایمنی برای retryهای سریع است، نه تضمین دائمی یکتایی.

## سمت Consumer: handler را idempotent کن

تحویل مجدد باگ نیست، خودِ قرارداد at-least-once است. پس handler باید چه یک بار اجرا شود و چه دوبار، نتیجه‌ی یکسان بدهد. روش معمول این است که کار را با یک **شناسه‌ی کسب‌وکاری** (شماره‌ی سفارش، شناسه‌ی پرداخت) کلید بزنیم و انجام‌شدنش را ثبت کنیم. در دموی من یک map در حافظه است؛ در محیط واقعی یک unique constraint یا upsert در دیتابیس است که در همان تراکنشِ side effect نوشته می‌شود، وگرنه crash بین این دو مشکل را برمی‌گرداند.

```go
if processed[id] {          // production: INSERT ... ON CONFLICT DO NOTHING
    m.Ack()                 // already done, just acknowledge
    continue
}
balance += amt
processed[id] = true
// ... crash here for order B, before m.Ack()
```

سه پیام منتشر کردم: سفارش A (۱۰۰+)، سفارش B (۵۰+) و یک نسخه‌ی دیگر از سفارش A با `Nats-Msg-Id` متفاوت، که retry یک Publisher را شبیه‌سازی می‌کند و dedup انتشار نمی‌تواند بگیردش. handler بعد از اعمال B و قبل از ack «crash» می‌کند و `AckWait` برابر ۱ ثانیه است:

```
  3.0s apply  order A +100 balance=100 (stream seq 1, delivery #1)
  3.0s apply  order B +50 balance=150 (stream seq 2, delivery #1)
  3.0s CRASH after side effect, before ack
  3.0s skip   order A (stream seq 3, delivery #1)
  4.0s skip   order B (stream seq 2, delivery #2)
  5.5s final balance=150 (expected 150)
```

هر دو نوع تکرار رد شدند: retry سفارش A (پیام دیگری در stream) و تحویل مجدد B (همان پیام، تحویل شماره‌ی ۲). بدون map موجودی ۳۰۰ می‌شد.

## AckSync و ack دوباره چه نشان می‌دهند

`m.Ack()` بدون انتظار فرستاده می‌شود و `m.AckSync()` منتظر تأیید سرور می‌ماند. آنچه دیدم:

```
  5.6s AckSync #1: <nil>
  5.6s AckSync #2: nats: message was already acknowledged
  5.6s Ack     #3: nats: message was already acknowledged
  5.6s ackFloor=1 ackPending=0
```

ack دوباره روی همان شیء `*nats.Msg` را خودِ کتاب‌خانه‌ی کلاینت رد می‌کند، پس بی‌ضرر است. اما یک نسخه‌ی کهنه فرق دارد: گذاشتم `AckWait` تمام شود و پیام دوباره تحویل داده شود، بعد نسخه‌ی قدیمی و بعد نسخه‌ی جدید را ack کردم:

```
  6.9s old delivery #1, new delivery #2
  6.9s AckSync on OLD copy: <nil>
  6.9s ackFloor=2 ackPending=0
  6.9s AckSync on NEW copy: <nil>
```

سرور ack دیرهنگامِ تحویل قدیمی را پذیرفت و ack floor جلو رفت، و ack نسخه‌ی جدید هم خطایی نداد. من فقط همین نتایج را بررسی کرده‌ام، نه درون سرور را. نتیجه این است که ack موفق به معنی «فقط من این پیام را پردازش کردم» نیست، و دقیقاً به همین دلیل handler باید {{< term "idempotency" "idempotent" >}} باشد.

## پس «exactly-once» یعنی چه؟

بر اساس آنچه دیدم، یک کلید نیست، ترکیبی از سه چیز است:

- **dedup هنگام انتشار** (`Nats-Msg-Id`) جلوی پیام‌های تکراری در stream را می‌گیرد، ولی فقط داخل duplicate window.
- **تحویل at-least-once** با ack یعنی پیام گم نمی‌شود و دوباره تحویل می‌شود.
- **پردازش idempotent** تحویل‌های تکراری را بی‌اثر می‌کند، و این بخش را فقط کد خودت می‌تواند انجام دهد.

اثر روی داده‌ها exactly-once است؛ خودِ تحویل نیست. قابلیت دیگری از JetStream را که ادعای بیشتری داشته باشد آزمایش نکرده‌ام، پس درباره‌اش ادعایی ندارم.

## چند نکته‌ی مهم

- شناسه را از داده بردار (شماره‌ی سفارش)، نه از sequence پیام: برای retry تولیدکننده، sequence فرق می‌کند، مثل سفارش A.
- duplicate window را بلندتر از طولانی‌ترین بازه‌ی واقع‌بینانه‌ی retry بگذار، و یادت باشد حافظه‌ی مصرفی‌اش با تعداد شناسه‌های داخل آن بالا می‌رود.
- نشانه‌ی «پردازش شد» و خودِ side effect را در یک تراکنش بنویس. map در حافظه مثل مال من با restart از بین می‌رود.
- side effectهای بیرونی (ایمیل، صدا زدن API شخص ثالث) اگر طرف مقابل پشتیبانی کند کلید idempotency خودشان را می‌خواهند.
- ack را بعد از انجام کار بزن. ack قبل از کار، crash را به پیام گم‌شده تبدیل می‌کند.

## قدم بعدی

تحویل مجدد هنگام deploy رایج‌ترین جایی است که با همه‌ی این‌ها روبه‌رو می‌شویم. مقاله‌ی بعد، `go-graceful-shutdown-workers`، درباره‌ی خاموش‌شدن تمیز Workerها در Go است: context، سیگنال‌ها، `Drain` و تمام کردن کارهای در حال اجرا.
