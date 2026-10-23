+++
date = '2026-10-18T12:00:00+03:30'
draft = false
title = 'یک Publisher و Worker ساده با NATS JetStream در Go'
description = 'ساخت Publisher و Worker با NATS JetStream در Go و Docker Compose: ساخت stream، انتشار پیام و پردازش آن با pull consumer از نوع durable.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging"]
cover = { image = "/images/covers/nats-jetstream-go.fa.png", alt = "یک Publisher و Worker ساده با NATS JetStream در Go", hiddenInSingle = true, hiddenInList = true }
+++

وقتی می‌خواهم یک مفهوم را واقعاً بفهمم، کوچک‌ترین نمونه‌ی قابل‌اجرا از آن را می‌سازم. این‌بار نوبت **NATS JetStream** بود. نتیجه، پروژه‌ی [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo) است: یک Publisher، یک Worker و خود NATS، همه با Docker Compose.

## چرا JetStream؟

NATS معمولی پیام‌ها را فقط به مشترک‌هایی می‌رساند که همان لحظه متصل‌اند. اگر Worker پایین باشد، پیام از دست می‌رود. **JetStream** لایه‌ی پایداری روی NATS است: پیام‌ها در یک Stream ذخیره می‌شوند و Consumerها می‌توانند بعداً و با ack دریافتشان کنند.

## ساختار

```
go-nats-demo/
├── docker-compose.yml
├── publisher/   (Dockerfile + main.go)
└── worker/      (Dockerfile + main.go)
```

- **NATS** با JetStream و داشبورد مدیریتی روی پورت `8222`
- **Publisher** هر ۲ ثانیه یک پیام روی `events.created` منتشر می‌کند
- **Worker** پیام‌ها را می‌خواند، لاگ می‌گیرد و ack می‌زند

## اتصال با retry

در Docker Compose هیچ تضمینی نیست که NATS قبل از سرویس‌های ما بالا بیاید. پس هر دو سرویس تا ۱۰ بار، با فاصله‌ی ۲ ثانیه، اتصال را امتحان می‌کنند:

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

## Publisher: ساخت Stream و انتشار پیام

Publisher اگر Stream وجود نداشته باشد آن را می‌سازد و بعد در یک حلقه پیام منتشر می‌کند:

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

## Worker: Pull Consumer با نام durable

نکته‌ی اصلی این است که Worker یک نام durable (`worker-consumer`) دارد. یعنی JetStream وضعیت خواندن این Consumer را نگه می‌دارد. اگر Worker ری‌استارت شود، از همان‌جا که مانده ادامه می‌دهد و پیام‌های ازدست‌رفته را دریافت می‌کند:

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

`Fetch(10, ...)` تا ۱۰ پیام را یک‌جا می‌گیرد و `Ack()` به JetStream می‌گوید پردازش تمام شد. پیامی که ack نشود، دوباره تحویل داده می‌شود.

## اجرا

```bash
git clone git@github.com:h-agharezaei/go-nats-demo.git
cd go-nats-demo
docker compose up --build
```

بعد داشبورد NATS را روی `http://localhost:8222/` ببین. برای آزمایش durable بودن، فقط سرویس worker را متوقف و دوباره بالا بیاور و لاگ‌ها را نگاه کن.

## قدم بعدی

این نمونه عمداً ساده است. چیزهایی که برای کار واقعی لازم می‌شوند و می‌خواهم سراغشان بروم: سیاست retry و `MaxDeliver`، dead-letter، چند Worker روی یک Consumer، و مانیتورینگ تأخیر پردازش.
