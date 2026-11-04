+++
date = '2026-10-18T14:00:00+03:30'
draft = false
title = 'Retry و Dead-Letter Queue در NATS JetStream با Go'
description = 'ادامه‌ی مقاله‌ی قبل: چطور پیام‌های ناموفق را با MaxDeliver و BackOff دوباره امتحان کنیم و در نهایت به یک صف dead-letter بفرستیم.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "retry"]
cover = { image = "/images/covers/nats-jetstream-retry-dlq.fa.png", alt = "Retry و Dead-Letter Queue در NATS JetStream با Go", hiddenInSingle = true }
+++

فرض کنید پیامی در صف دارید که پردازشش هر بار خطا می‌دهد، مثلاً JSON خراب است یا به رکوردی اشاره می‌کند که وجود ندارد. Workerِ [مقاله‌ی قبل](/fa/posts/nats-jetstream-go/) این را نادیده می‌گرفت: فرضش این بود که پردازش همیشه موفق می‌شود و بعد از هر پیام ack می‌زد. حالا اگر به‌جای ack نزنیم و پیام را شکست‌خورده حساب کنیم، دو اتفاق بد ممکن است بیفتد. یا JetStream همان پیام را تا ابد دوباره می‌فرستد و Worker را گرفتار یک چرخه‌ی بی‌پایان می‌کند، یا پیام بی‌صدا گم می‌شود و هیچ‌کس نمی‌فهمد.

برای اینکه نه این شود نه آن، سه چیز لازم داریم:

1. سقف برای تعداد تلاش‌ها: `MaxDeliver`
2. فاصله بین تلاش‌ها: `BackOff` و `NakWithDelay`
3. جایی برای پیام‌هایی که بعد از همه‌ی تلاش‌ها هنوز شکست می‌خورند: یک صف **dead-letter**

این مقاله این سه را یکی‌یکی می‌سازد و هر کدام را با یک اجرای واقعی نشان می‌دهد.

> همه‌ی اجراها با Go 1.27، `nats.go` نسخه‌ی 1.54.0 و یک `nats-server` توکار (نسخه‌ی 2.15.1) روی 127.0.0.1 و یک پورت تصادفی انجام شده‌اند. کد یک مثال محلی است، نه مخزن منتشرشده. زمان‌ها را کمی گرد کرده‌ام (۰٫۰ یعنی «همان لحظه») و بعضی مقدارها، مثل id و ساعت advisory، در هر اجرا فرق می‌کنند.

## یک پیام، سه تلاش: Consumer با تنظیمات صریح

در مقاله‌ی قبل `PullSubscribe` یک consumer با تنظیمات پیش‌فرض ساخت و دیدیم سقف تحویلش `-1` است، یعنی نامحدود. این‌بار consumer را خودمان با تنظیمات دلخواه می‌سازیم:

```go
_, err = js.AddConsumer("EVENTS", &nats.ConsumerConfig{
    Durable:       "worker-consumer",
    AckPolicy:     nats.AckExplicitPolicy,
    AckWait:       30 * time.Second,
    MaxDeliver:    3,
    BackOff:       []time.Duration{500 * time.Millisecond, time.Second},
    FilterSubject: "events.created",
})
```

- `AckPolicy: AckExplicitPolicy` یعنی هر پیام را Worker باید جداگانه و صریح ack کند.
- `MaxDeliver: 3` یعنی هر پیام حداکثر ۳ بار تحویل داده می‌شود: یک تحویل اول و دو تحویل دوباره.
- {{< term "ack-wait" "AckWait" >}} مدتی است که سرور برای ack صبر می‌کند. وقتی ack نرسد، سرور فرض می‌کند Worker مرده یا گیر کرده و پیام را دوباره می‌فرستد.
- `BackOff` فهرستی از فاصله‌هاست: برای تحویل دوباره‌ی اول ۵۰۰ میلی‌ثانیه، برای دومی ۱ ثانیه.

یک نکته که در اجرا دیدم و انتظارش را نداشتم: وقتی `BackOff` گذاشته شود، سرور `AckWait` را نادیده می‌گیرد. من ۳۰ ثانیه خواستم، ولی وقتی وضعیت consumer را از سرور پرسیدم این را برگرداند:

```
config: ackWait=500ms maxDeliver=3 backoff=[500ms 1s]
```

یعنی `AckWait` برابر اولین عنصر `BackOff` شد. این را در مستندات NATS پیدا نکردم؛ فقط همین است که `ConsumerInfo` در این اجرا نشان داد. هر دو حالت `AckWait` برابر ۲ و ۳۰ ثانیه را امتحان کردم و زمان‌بندی تحویل‌ها دقیقاً یکی بود.

بعد از ساخت consumer، Worker مثل قبل به آن وصل می‌شود:

```go
sub, _ := js.PullSubscribe("events.created", "worker-consumer")
```

## وقتی کار شکست خورد: Nak یا سکوت؟

Worker وقتی پردازش شکست خورد دو راه دارد. یا ack نمی‌زند و می‌گذارد سرور بعد از انتظار پیام را دوباره بفرستد. یا صریح می‌گوید «این پیام را دوباره بده» با `Nak`. یک نوع `Nak` هم هست که تأخیر می‌گیرد: `NakWithDelay`.

برای مقایسه، یک پیام «poison» فرستادم، یعنی پیامی که هر بار شکست می‌خورد (این اصطلاح یعنی {{< term "poison-message" "poison message" >}}). Worker هر بار آن را بدون ack یا با یکی از دو نوع `Nak` برگرداند و من ثانیه‌ی هر تحویل را نسبت به تحویل اول یادداشت کردم. consumer همان بالا بود (`MaxDeliver: 3` و `BackOff` از ۰٫۵ و ۱ ثانیه):

| واکنش Worker | تحویل ۱ | تحویل ۲ | تحویل ۳ |
| --- | --- | --- | --- |
| `m.Nak()` | ۰٫۰ ثانیه | ۰٫۰ ثانیه | ۰٫۰ ثانیه |
| `m.NakWithDelay(1 * time.Second)` | ۰٫۰ ثانیه | ۱٫۰ ثانیه | ۲٫۵ ثانیه |
| هیچ (ack یا nak نزدن) | ۰٫۰ ثانیه | ۰٫۵ ثانیه | ۱٫۵ ثانیه |

سه ردیف سه داستان متفاوت‌اند:

- **`Nak()` ساده** بلافاصله پیام را برمی‌گرداند و `BackOff` هیچ اثری ندارد. هر سه تلاش در همان ثانیه‌ی صفر تمام شدند. اگر خطا موقتی باشد (مثلاً دیتابیس برای یک ثانیه در دسترس نیست)، هر سه تلاش پشت‌سر هم و در یک لحظه انجام می‌شود و هر سه شکست می‌خورد، بی‌آنکه دیتابیس فرصتی برای برگشتن داشته باشد.
- **`NakWithDelay(1s)`** پیام را بعد از تأخیر خواسته‌شده برمی‌گرداند. تحویل ۲ درست در ثانیه‌ی ۱٫۰ آمد. تحویل ۳ در ۲٫۵ ثانیه آمد، نه ۲٫۰. همین آزمایش را بدون `BackOff` هم تکرار کردم و آنجا زمان‌ها دقیقاً ۰، ۱٫۰ و ۲٫۰ شدند. پس نیم ثانیه‌ی اضافه به `BackOff` برمی‌گردد، ولی نفهمیدم سرور دقیقاً چطور آن را حساب می‌کند و حدس نمی‌زنم.
- **سکوت** تابع `BackOff` است و حساب ساده‌ای دارد. وقتی Worker جواب نمی‌دهد، سرور بعد از ۰٫۵ ثانیه تحویل ۲ را می‌فرستد. تحویل ۳ یک ثانیه بعد از تحویل ۲ می‌آید، یعنی در ۰٫۵ + ۱ = ۱٫۵ ثانیه. فهرست `BackOff` دو عنصر دارد و ما بعد از تحویل ۳ سقف را رسیده‌ایم.

نتیجه‌ی عملی: `Nak()` ساده برای خطای موقتی خطرناک است، چون Worker را در یک حلقه‌ی تلاش سریع می‌اندازد. برای خطاهایی که احتمالاً با کمی صبر درست می‌شوند از `NakWithDelay` استفاده کنید. یک حلقه‌ی کامل‌تر برای Worker:

```go
for _, m := range msgs {
    if err := process(m.Data); err != nil {
        log.Println("process failed:", err)
        m.NakWithDelay(time.Second)
        continue
    }
    m.Ack()
}
```

## وقتی تلاش‌ها تمام شد: advisory

پیام poison سه بار آمد و سه بار شکست خورد. بعدش چه؟ بعد از رسیدن به `MaxDeliver` سرور دیگر پیام را به این consumer نمی‌دهد. خود پیام داخل stream می‌ماند، ولی JetStream یک **advisory** منتشر می‌کند، یعنی یک اعلان کوچک روی این subject:

```
$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.<stream>.<consumer>
```

محتوای اعلان را در اجرای DLQ پایین‌تر چاپ کردم. این است (JSON یک خطی است و در یک خط چاپ شد):

```json
{"type":"io.nats.jetstream.advisory.v1.max_deliver","id":"6Hz2NBCGpth11TGJ05piQy","timestamp":"2026-11-04T17:21:20.971697Z","stream":"EVENTS","consumer":"worker-consumer","stream_seq":2,"deliveries":3}
```

دو فیلد برای ما مهم‌اند: `stream_seq`، شماره‌ی پیام در stream، و `deliveries`، تعداد تحویل‌ها. با شماره‌ی پیام می‌شود پیام اصلی را از stream بیرون کشید.

## ساخت صف dead-letter

حالا ایده‌ی ساده‌ی {{< term "dlq" "صف dead-letter" >}} این است: یک stream جدا برای پیام‌های ناموفق می‌سازیم و یک تکه‌کد کوچک به advisory گوش می‌دهد. هر وقت اعلانی رسید، پیام اصلی را با شماره‌اش از `EVENTS` می‌خواند و در stream تازه می‌گذارد:

```go
js.AddStream(&nats.StreamConfig{
    Name:     "DLQ",
    Subjects: []string{"dlq.events"},
})

nc.Subscribe("$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.EVENTS.worker-consumer",
    func(m *nats.Msg) {
        var adv struct {
            Stream     string `json:"stream"`
            StreamSeq  uint64 `json:"stream_seq"`
            Deliveries int    `json:"deliveries"`
        }
        json.Unmarshal(m.Data, &adv)

        raw, err := js.GetMsg(adv.Stream, adv.StreamSeq)
        if err != nil {
            log.Println("getmsg:", err)
            return
        }
        // MsgId جلوی ذخیره‌ی تکراری را می‌گیرد
        js.Publish("dlq.events", raw.Data,
            nats.MsgId(fmt.Sprintf("dlq-%d", adv.StreamSeq)))
    })
```

`MsgId` یک شناسه است که روی پیام می‌گذاریم تا سرور بتواند پیام تکراری را تشخیص دهد. مقاله‌ی [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/) کامل درباره‌ی آن حرف می‌زند. این‌جا فقط همین لازم است: دو بار منتشر کردن با یک شناسه، فقط یک پیام در stream می‌گذارد، به شرط اینکه بین دو انتشار از «پنجره‌ی تشخیص تکراری» stream بیشتر نگذشته باشد. در این اجرا پنجره‌ی `DLQ` را از سرور پرسیدم و `2m0s` بود.

حالا سه پیام فرستادم: `good-1`، `poison` و `good-2`. Worker پیام poison را با `NakWithDelay(1s)` برمی‌گرداند و بقیه را ack می‌کند. خروجی:

```
  t=0.0s good-1 delivery #1 (stream seq 1)
  t=0.0s poison delivery #1 (stream seq 2)
  t=0.0s good-2 delivery #1 (stream seq 3)
  t=1.0s poison delivery #2 (stream seq 2)
  t=2.5s poison delivery #3 (stream seq 2)
advisory: {"type":"io.nats.jetstream.advisory.v1.max_deliver","id":"6Hz2NBCGpth11TGJ05piQy","timestamp":"2026-11-04T17:21:20.971697Z","stream":"EVENTS","consumer":"worker-consumer","stream_seq":2,"deliveries":3}
second publish with same MsgId: duplicate=true
end: EVENTS msgs=3 pending=0 ackPending=0 redelivered=1 | DLQ msgs=1 advisories=1
```

خط به خط:

- سه پیام اول در ثانیه‌ی صفر رسیدند. `good-1` و `good-2` ack شدند و دیگر برنگشتند، چون هر کدام فقط `delivery #1` دارند.
- `poison` که شماره‌ی ۲ در stream است، در ثانیه‌های ۰٫۰، ۱٫۰ و ۲٫۵ آمد، همان زمان‌بندی جدول بالا.
- بعد از تحویل سوم و شکست، یک advisory آمد و کد ما دقیقاً **یک** پیام در `DLQ` گذاشت. خط `second publish with same MsgId: duplicate=true` از کد آزمایشی من است که برای نشان دادن تشخیص تکراری یک‌بار دیگر همان پیام را با همان شناسه منتشر کرد؛ سرور آن را تکراری شناخت.
- در پایان `EVENTS` هنوز سه پیام دارد (پیام اصلی poison از stream حذف نشده)، `DLQ` یک پیام دارد، و consumer هیچ پیام pending یا ack-pending ندارد. عدد `redelivered=1` شمارنده‌ی خود سرور است؛ به آن تکیه نمی‌کنم.

## `Term`: وقتی تلاش دوباره بی‌فایده است

بعضی خطاها با صبر درست نمی‌شوند. JSON خراب، بار دوم هم خراب است. در این حالت می‌توانید همان لحظه `m.Term()` بزنید، یعنی «این پیام را دیگر هرگز نفرست». در یک اجرا همین کار را کردم: فقط `delivery #1` دیده شد و بعد تا ۶ ثانیه هیچ تحویل دیگری نیامد. پیام هنوز در stream بود (`msgs=1`).

## جاهایی که این DLQ کم می‌آورد

- **Advisory پیام core NATS است، نه JetStream.** طبق چیزی که از مستندات NATS می‌دانم، advisoryها روی subjectهای عادی منتشر می‌شوند و ذخیره نمی‌شوند. اگر سرویس DLQ درست لحظه‌ی انتشار پایین باشد، اعلان را از دست می‌دهد. برای سیستم‌های حساس راه جبرانی لازم است، مثلاً بازبینی دوره‌ی consumer با `ConsumerInfo` یا ذخیره‌ی advisoryها در یک stream.
- **پیام اصلی حذف نمی‌شود.** دیدیم `EVENTS` هنوز هر سه پیام را دارد. ماندنش به سیاست نگهداری (retention) همان stream بستگی دارد.
- **همه‌ی خطاها شایسته‌ی تلاش دوباره نیستند.** اگر خطا را می‌شناسید که دائمی است، `Term` بزنید و سه تلاش را هدر ندهید.
- **جلوگیری از ذخیره‌ی تکراری محدود به پنجره است.** `MsgId` فقط تا وقتی کار می‌کند که از انتشار قبلی کمتر از پنجره‌ی تشخیص تکراری stream گذشته باشد.

## قدم بعدی

DLQ پیام‌های ناموفق را جمع می‌کند، ولی برای صفی که سریع‌تر از توان یک Worker پر می‌شود کاری نمی‌کند. «چند Worker روی یک Consumer و مانیتورینگ lag در JetStream» نشان می‌دهد چطور Worker اضافه کنیم و چطور بفهمیم صف دارد انباشته می‌شود. کد کامل نمونه‌ی پایه در [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo) است.
