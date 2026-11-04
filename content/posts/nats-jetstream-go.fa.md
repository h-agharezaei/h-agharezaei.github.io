+++
date = '2026-10-18T12:00:00+03:30'
draft = false
title = 'یک Publisher و Worker ساده با NATS JetStream در Go'
description = 'ساخت Publisher و Worker با NATS JetStream در Go و Docker Compose: ساخت stream، انتشار پیام و پردازش آن با pull consumer از نوع durable.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging"]
cover = { image = "/images/covers/nats-jetstream-go.fa.png", alt = "یک Publisher و Worker ساده با NATS JetStream در Go", hiddenInSingle = true }
+++

فرض کنید سرویس شما بعد از هر خرید یک پیام می‌فرستد: «سفارش ۱۲ ثبت شد». سرویس دیگری، یک Worker، باید این پیام را بگیرد و فاکتور بسازد. ساده‌ترین روش این است که Worker به یک سرور پیام وصل شود و منتظر بماند. ولی اگر در همان لحظه‌ای که پیام می‌رسد Worker در حال ری‌استارت شدن باشد، چه می‌شود؟ در بسیاری از سیستم‌های پیام‌رسانی جوابش این است: پیام گم می‌شود، چون کسی گوش نمی‌داد.

وقتی می‌خواهم یک مفهوم را واقعاً بفهمم، کوچک‌ترین نمونه‌ی قابل‌اجرای آن را می‌سازم. این‌بار نوبت **NATS JetStream** بود، چون جواب همین سؤال است: پیام را ذخیره می‌کند تا Worker هر وقت برگشت، از همان‌جا که مانده ادامه دهد. نتیجه‌ی کار، پروژه‌ی [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo) است: یک Publisher، یک Worker و خود NATS، همه با Docker Compose.

این اولین مقاله‌ی این مجموعه است و فرض نمی‌کند NATS یا JetStream را می‌شناسید. فقط کمی Go بلد باشید کافی است.

> کدِ Publisher و Worker از همان پروژه‌ی go-nats-demo است. چون روی این ماشین Docker ندارم، فایل Compose را اجرا نکردم. به‌جایش همان کد را با Go 1.27 و `nats.go` نسخه‌ی 1.54.0 روی یک `nats-server` توکار (نسخه‌ی 2.15.1) اجرا کردم که روی 127.0.0.1 و یک پورت تصادفی بالا آمد. تنها تفاوت کد این بود که آدرس سرور را از خط فرمان می‌گرفت و پیام‌ها به‌جای زمان، `event-1`، `event-2` و... بودند تا خروجی خواناتر شود. خروجی‌های زیر از همان اجرا هستند و ساعت‌ها در هر اجرا فرق می‌کنند.

## چرا JetStream؟

NATS معمولی مثل یک بلندگوی همگانی کار می‌کند. پیامی که به یک **subject** فرستاده می‌شود (subject یک نام نقطه‌دار است، مثل `events.created`) فقط به برنامه‌هایی می‌رسد که همان لحظه به آن subject گوش می‌دهند. اگر Worker پایین باشد، پیام از دست می‌رود. این رفتار سریع و ساده است و برای خیلی از کارها همان لازم است، ولی برای «فاکتور باید حتماً ساخته شود» کافی نیست.

{{< term "jetstream" "JetStream" >}} لایه‌ی ماندگاری روی NATS است. با آن سه مفهوم تازه وارد می‌شود:

- **stream**: یک دفتر ثبت نام‌دار که پیام‌های مربوط به چند subject را روی دیسک نگه می‌دارد. هر پیام ذخیره‌شده یک شماره‌ی ترتیب می‌گیرد: ۱، ۲، ۳ و...
- **consumer**: یک خواننده‌ی نام‌دار از یک stream. سرور به یاد دارد این خواننده تا کجا خوانده است.
- **{{< term "acknowledgement" "ack" >}}** (تأیید): جواب Worker بعد از تمام شدن کار روی یک پیام، یعنی «این یکی را انجام دادم». تا ack نرسد، سرور فرض می‌کند پیام هنوز کار نشده و آن را دوباره می‌فرستد.

پس تفاوت اصلی این است: پیام اول در stream ذخیره می‌شود و بعد consumer آن را می‌خواند. Worker پایین باشد، پیام در stream منتظر می‌ماند.

## ساختار پروژه

```
go-nats-demo/
├── docker-compose.yml
├── publisher/   (Dockerfile + main.go)
└── worker/      (Dockerfile + main.go)
```

- **NATS** با JetStream روشن و پورت مانیتورینگ `8222`. این پورت چند صفحه‌ی JSON برای دیدن وضعیت سرور می‌دهد، نه یک داشبورد گرافیکی.
- **Publisher** هر ۲ ثانیه یک پیام روی `events.created` منتشر می‌کند.
- **Worker** پیام‌ها را می‌خواند، لاگ می‌گیرد و ack می‌زند.

## اتصال با تلاش مجدد

در Docker Compose تضمینی نیست که NATS آماده باشد وقتی سرویس‌های ما بالا می‌آیند. `depends_on` فقط ترتیب شروع را مشخص می‌کند، نه آماده‌بودن را. برای همین هر دو سرویس تا ۱۰ بار و با فاصله‌ی ۲ ثانیه سعی می‌کنند وصل شوند:

```go
func connectNATS(url string) *nats.Conn {
    for i := 0; i < 10; i++ {
        nc, err := nats.Connect(url)
        if err == nil {
            return nc
        }
        log.Println("Waiting for NATS to be ready...", err)
        time.Sleep(2 * time.Second)
    }
    log.Fatal("Failed to connect to NATS after 10 attempts")
    return nil
}
```

(در پروژه‌ی اصلی همین منطق با کمی لاگ بیشتر نوشته شده.)

## Publisher: ساخت stream و انتشار پیام

Publisher اول stream را می‌سازد. اسمش `EVENTS` است و فقط پیام‌های subject به نام `events.created` را نگه می‌دارد. بعد در یک حلقه، هر ۲ ثانیه یک پیام منتشر می‌کند:

```go
js, _ := nc.JetStream()

_, err := js.AddStream(&nats.StreamConfig{
    Name:     "EVENTS",
    Subjects: []string{"events.created"},
})
if err != nil && err != nats.ErrStreamNameAlreadyInUse {
    log.Fatal(err)
}

for {
    msg := []byte(time.Now().Format(time.RFC3339))
    if _, err := js.Publish("events.created", msg); err != nil {
        log.Println("publish error:", err)
    }
    time.Sleep(2 * time.Second)
}
```

`js.Publish` فرق مهمی با publish معمولی NATS دارد: تا سرور پیام را در stream ذخیره نکند و تأیید نفرستد، جواب نمی‌دهد. پس اگر خطایی برنگردد، یعنی پیام ذخیره شده است.

## Worker: consumer ماندگار از نوع pull

حالا قسمت اصلی. Worker به stream وصل می‌شود و یک consumer با نام `worker-consumer` می‌گیرد:

```go
sub, err := js.PullSubscribe("events.created", "worker-consumer")
if err != nil {
    log.Fatal(err)
}

for {
    msgs, err := sub.Fetch(10, nats.MaxWait(5*time.Second))
    if err != nil && err != nats.ErrTimeout {
        log.Println("fetch error:", err)
        continue
    }
    for _, m := range msgs {
        log.Println("Received:", string(m.Data))
        m.Ack()
    }
}
```

دو کلمه‌ی این کد توضیح می‌خواهد.

اول، {{< term "durable-consumer" "ماندگار" >}} (durable). چون consumer اسم دارد (`worker-consumer`)، سرور جایگاه خواندنش را حتی وقتی هیچ Workerی وصل نیست نگه می‌دارد. اگر Worker ری‌استارت شود، با همان اسم برمی‌گردد و از همان‌جا که مانده ادامه می‌دهد.

دوم، {{< term "pull-consumer" "pull" >}}. Worker خودش پیام می‌خواهد و سرور پیام را به زور نمی‌فرستد. `Fetch(10, ...)` یعنی «تا ۱۰ پیام بده، ولی بیشتر از ۵ ثانیه منتظر نمان». اگر در این مدت هیچ پیامی نرسد، `ErrTimeout` برمی‌گردد. برای همین حلقه‌ی ما `ErrTimeout` را خطا حساب نمی‌کند: فقط یعنی فعلاً پیامی نیست.

بعد از هر پیام، `m.Ack()` به سرور می‌گوید کار تمام شد. پیامی که ack نشود، دوباره تحویل داده می‌شود.

## دیدن durable بودن در عمل

ادعای «از همان‌جا که مانده ادامه می‌دهد» را باید دید. سرور و Publisher را بالا آوردم و Worker را کمی بعد. بعد از حدود ۷ ثانیه Worker را متوقف کردم، ۷ ثانیه صبر کردم و دوباره راهش انداختم. خروجی لاگ‌ها این بود (خط‌های `---` را خودم برای راهنمایی اضافه کرده‌ام):

```
20:48:58 Published: event-1
20:48:58 Received: event-1
20:49:00 Published: event-2
20:49:00 Received: event-2
20:49:02 Published: event-3
20:49:02 Received: event-3
20:49:04 Published: event-4
20:49:04 Received: event-4
--- worker stopped
20:49:06 Published: event-5
20:49:08 Published: event-6
20:49:10 Published: event-7
20:49:12 Published: event-8
--- worker restarted
20:49:12 Received: event-5
20:49:12 Received: event-6
20:49:12 Received: event-7
20:49:12 Received: event-8
20:49:14 Published: event-9
20:49:14 Received: event-9
```

تا قبل از `worker stopped`، هر پیام همان لحظه‌ی انتشار می‌رسد. وقتی Worker نیست، Publisher همچنان پیام‌های ۵ تا ۸ را منتشر می‌کند و هیچ‌کدام `Received` ندارند. به محض بازگشت Worker، هر چهار پیام در یک ثانیه می‌رسند، به همان ترتیب، و `Fetch(10)` همه را یک‌جا گرفته است. بعد دوباره رفتار عادی برمی‌گردد.

برای اینکه ببینیم سرور واقعاً جایگاه را نگه داشته بود، وضعیت consumer را از سرور پرسیدم. این دو خط درست بعد از ۷ ثانیه غیبت Worker و قبل از برگشتنش است:

```
stream EVENTS: messages=8 first=1 last=8
consumer worker-consumer: delivered=4 ackFloor=4 pending=4 ackPending=0 ackPolicy=AckExplicit ackWait=30s maxDeliver=-1
```

stream هشت پیام دارد. consumer تا شماره‌ی ۴ تحویل گرفته و ack کرده (`delivered=4`، `ackFloor=4`) و ۴ پیام منتظر مانده‌اند (`pending=4`). یعنی نیازی نیست Worker چیزی به یاد داشته باشد؛ جایگاه روی سرور است. بعد از برگشتن Worker همین پرسش `delivered=10 ackFloor=10 pending=0` داد.

دو عدد آخر خط consumer هم جالب‌اند: چون ما consumer را فقط با اسم ساختیم، سرور تنظیمات پیش‌فرض را گذاشت. `ackWait=30s` یعنی اگر ۳۰ ثانیه ack نرسد پیام دوباره می‌آید و `maxDeliver=-1` یعنی سقفی برای تعداد تحویل‌ها نیست. همین «سقف ندارد» مشکلی است که مقاله‌ی بعد حلش می‌کند.

## اجرا با Docker Compose

روی ماشین شما اجرا کردنش این است (من این مرحله را اجرا نکردم، چون Docker ندارم):

```bash
git clone git@github.com:h-agharezaei/go-nats-demo.git
cd go-nats-demo
docker compose up --build
```

بعد صفحه‌ی مانیتورینگ NATS را روی `http://localhost:8222/` ببینید. برای دیدن durable بودن، فقط سرویس worker را متوقف کنید، چند ثانیه صبر کنید و دوباره بالا بیاورید، مثل آنچه بالا کردم.

## جاهایی که این نمونه ضعیف است

نمونه عمداً ساده است، پس چند چیز آن را برای کار واقعی ناکافی می‌کند:

- **ترتیب بالا آمدن مهم است.** فقط Publisher stream را می‌سازد. وقتی Worker را روی سرور خالی و پیش از Publisher اجرا کردم، بعد از اتصال با `nats: no stream matches subject` متوقف شد، چون `PullSubscribe` هنوز streamی پیدا نمی‌کرد. در Compose این‌که کدام زودتر بالا بیاید تضمین‌شده نیست.
- **Worker همه‌چیز را ack می‌کند.** کار واقعی ممکن است شکست بخورد و این Worker برای شکست برنامه‌ای ندارد.
- **سقف تحویل نیست.** چنان‌که دیدید `maxDeliver=-1` است.
- **خطای `Fetch` بدون مکث تکرار می‌شود.** در حلقه‌ی Worker، هر خطایی غیر از timeout فوراً دوباره `Fetch` می‌زند. اگر خطا ماندگار باشد، حلقه بی‌وقفه و با سرعت می‌چرخد و لاگ می‌ریزد.

## قدم بعدی

این Worker هر پیامی را ack می‌کند و برای پیامی که مدام شکست می‌خورد برنامه‌ای ندارد. «Retry و Dead-Letter Queue در NATS JetStream با Go» نشان می‌دهد چطور تعداد تلاش‌ها را محدود کنیم، بین تلاش‌ها فاصله بیندازیم و پیام‌های «سوخته» را کنار بگذاریم.
