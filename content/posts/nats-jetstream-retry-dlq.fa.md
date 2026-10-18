+++
date = '2026-10-18T14:00:00+03:30'
draft = false
title = 'Retry و Dead-Letter Queue در NATS JetStream با Go'
description = 'ادامه‌ی مقاله‌ی قبل: چطور پیام‌های ناموفق را با MaxDeliver و BackOff دوباره امتحان کنیم و در نهایت به یک صف dead-letter بفرستیم.'
tags = ["go", "nats", "jetstream", "messaging", "retry"]
+++

در [مقاله‌ی قبل](/fa/posts/nats-jetstream-go/) یک Publisher و Worker ساده روی JetStream ساختیم. اما Workerِ آن مقاله فرض می‌کرد پردازش همیشه موفق است. در عمل پیام‌هایی هستند که هر بار fail می‌شوند. اگر کاری نکنیم، یا بی‌نهایت تکرار می‌شوند یا گم می‌شوند.

در این مقاله سه چیز را اضافه می‌کنیم:

1. محدود کردن تعداد تلاش‌ها با `MaxDeliver`
2. فاصله‌ی بین تلاش‌ها با `BackOff` و `NakWithDelay`
3. فرستادن پیام «سوخته» به یک صف **dead-letter**

> همه‌ی رفتارهای زیر را با یک سرور NATS تعبیه‌شده در Go (با JetStream) و کتابخانه‌ی `nats.go` آزمایش کرده‌ام و خروجی‌ها از همان آزمایش‌اند.

## ساخت Consumer با تنظیمات صریح

به‌جای اینکه `PullSubscribe` یک Consumer پیش‌فرض بسازد، خودمان آن را با تنظیمات دلخواه می‌سازیم:

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

- `MaxDeliver: 3` یعنی هر پیام حداکثر ۳ بار تحویل داده می‌شود.
- `AckWait` مدت انتظار برای ack است. اگر Worker در این مدت ack نزند، پیام دوباره تحویل داده می‌شود.
- `BackOff` فاصله‌ی تحویل‌های مجدد را مشخص می‌کند.

بعد Worker مثل قبل به همین Consumer وصل می‌شود:

```go
sub, _ := js.PullSubscribe("events.created", "worker-consumer")
```

## Nak یعنی چه؟

وقتی پردازش fail شد، دو راه داریم: ack نزنیم و منتظر `AckWait` بمانیم، یا صریح بگوییم «این پیام را دوباره بده» با `Nak`. من هر دو را با یک پیام «poison» که همیشه fail می‌شود امتحان کردم:

| روش | رفتار مشاهده‌شده |
| --- | --- |
| `m.Nak()` | **بلافاصله** دوباره تحویل می‌شود. `BackOff` اثری ندارد. هر ۳ تلاش در همان ثانیه‌ی صفر انجام شد. |
| `m.NakWithDelay(1 * time.Second)` | بعد از تأخیر داده‌شده دوباره می‌آید (تلاش‌های ۲ و ۳ حدود ثانیه‌ی ۱ و ۲٫۵). |
| ack نزدن | طبق `BackOff` دوباره تحویل می‌شود (در آزمایش من تلاش‌های ۲ و ۳ در ثانیه‌ی ۰٫۵ و ۱٫۵؛ `AckWait` را برای آزمایش ۲ ثانیه گذاشته بودم). |

نتیجه‌ی عملی: `Nak()` ساده برای خطای موقتی خطرناک است، چون یک Worker را در حلقه‌ی تلاش سریع گیر می‌اندازد. برای خطاهایی که احتمالاً با کمی صبر درست می‌شوند (مثلاً دیتابیس لحظه‌ای در دسترس نیست) از `NakWithDelay` استفاده کن.

یک Worker کامل‌تر:

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

## وقتی تلاش‌ها تمام شد: Advisory

بعد از رسیدن به `MaxDeliver`، JetStream دیگر پیام را به این Consumer نمی‌دهد. پیام داخل Stream می‌ماند، ولی JetStream یک **advisory** روی این subject منتشر می‌کند:

```
$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.<stream>.<consumer>
```

داخل advisory (JSON) شماره‌ی پیام در Stream (`stream_seq`) و تعداد تحویل‌ها (`deliveries`) هست. با همین شماره می‌توانیم پیام اصلی را برداریم.

## ساخت صف dead-letter

یک Stream جدا برای پیام‌های ناموفق می‌سازیم و یک سرویس کوچک به advisory گوش می‌دهد:

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

در آزمایش من، سه پیام فرستادم: `good-1`، `poison` و `good-2`. دو پیام سالم یک‌بار تحویل و ack شدند، پیام `poison` سه بار تحویل شد و بعد در Stream به نام `DLQ` دقیقاً **یک** پیام ثبت شد. Consumer هم در پایان هیچ پیام pending یا ack-pending نداشت.

## چند نکته‌ی مهم

- **Advisoryها پیام‌های core NATS هستند، نه JetStream.** اگر سرویس DLQ در لحظه‌ی انتشار advisory پایین باشد، آن را از دست می‌دهد. برای سیستم‌های حساس باید راه جبرانی داشته باشی، مثلاً بازبینی دوره‌ای Consumer با `ConsumerInfo` یا ذخیره‌ی advisoryها در یک Stream.
- پیام اصلی بعد از رسیدن به `MaxDeliver` از Stream حذف نمی‌شود. مدت نگهداری‌اش به سیاست retention همان Stream بستگی دارد.
- خطاهای دائمی (مثلاً payload خراب) فایده‌ای ندارد چند بار retry شوند. اگر خطا را تشخیص می‌دهی، همان لحظه می‌توانی `m.Term()` بزنی تا JetStream دیگر آن را تحویل ندهد.
- `MsgId` در مثال بالا از ذخیره‌ی تکراری در DLQ جلوگیری می‌کند، به شرطی که Stream در پنجره‌ی duplicate-detection خودش باشد.

## قدم بعدی

دو موضوع می‌ماند که می‌خواهم در مقاله‌ی بعد بنویسم: اجرای چند Worker روی یک Consumer، و مانیتورینگ تأخیر پردازش. کد کامل نمونه‌ی پایه در [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo) است.
