+++
date = '2026-12-16T10:00:00+03:30'
draft = false
title = 'خاموشی تمیز Workerها در Go'
description = 'چطور Worker جاب‌های JetStream در Go را تمیز خاموش کنیم: SIGTERM با signal.NotifyContext، تمام کردن پیام‌های در حال اجرا، timeout و Drain، با سیگنال واقعی.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "shutdown", "context", "signals"]
cover = { image = "/images/covers/go-graceful-shutdown-workers.fa.png", alt = "خاموشی تمیز Workerها در Go", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/nats-jetstream-idempotency/) با این جمله تمام شد که تحویل مجدد هنگام deploy رایج‌ترین جایی است که با پیام‌های تکراری روبه‌رو می‌شویم. deploy به Worker قدیمی یک سیگنال می‌فرستد و یک Worker جدید بالا می‌آورد. اگر قدیمی همین‌طوری بمیرد، هر کاری که وسط‌اش بوده بعداً دوباره تحویل داده می‌شود. در این مقاله این را با سیگنال واقعی آزمایش می‌کنم و بعد درستش می‌کنم. اگر `context` برایت تازه است اول [sync، select و context](/fa/posts/go-sync-select-context/) را بخوان.

> همه‌چیز روی Go 1.26 با `nats-server` تعبیه‌شده‌ی v2.15.1 و `nats.go` نسخه‌ی v1.54.0 اجرا شده است. برای فرستادن سیگنال واقعی، دمو یک باینری ساخته‌شده با دو حالت است: `server` (سرور تعبیه‌شده، یک stream به نام `JOBS`، یک consumer با `AckWait` پنج‌ثانیه‌ای و دو جاب منتشرشده) و `worker`، هر کدام در پروسه‌ی جدا. با یک اسکریپت shell دستور `kill -TERM <pid>` را می‌فرستم. زمان‌ها ساعت دیواری هستند و عدد داخل کروشه PID است.

## Worker ساده‌لوحانه

یک پیام می‌گیرد، ۳ ثانیه کار می‌کند و ack می‌زند. هیچ مدیریتی برای سیگنال ندارد. یک ثانیه بعد از شروع `SIGTERM` فرستادم و بعد یک Worker جدید بالا آوردم (خروجی کوتاه شده):

```
23:41:38.900 [78489] start  job-1 (delivery #1), takes 3s
23:41:38.949 [78388] server: consumer pending=1 ackPending=1 redelivered=0
--- kill -TERM 78489
worker exit status: 143
23:41:40.918 [78620] start  job-2 (delivery #1), takes 3s
23:41:43.920 [78620] acked  job-2
23:41:43.920 [78620] start  job-1 (delivery #2), takes 3s
23:41:43.959 [78388] server: consumer pending=0 ackPending=1 redelivered=1
23:41:46.925 [78620] acked  job-1
```

بدون handler، رفتار پیش‌فرض Go برای `SIGTERM` پایان دادن به پروسه است، پس جاب نصفه ماند و ack نشد. سرور تا تمام شدن `AckWait` آن را pending نگه داشت (از ۳۸.۹ تا ۴۳.۹، پنج ثانیه) و بعد به‌عنوان delivery #2 دوباره تحویل داد. exit status ‏143 یعنی ۱۲۸ به‌اضافه‌ی شماره‌ی سیگنال، یعنی ۱۵. چیزی گم نشد، ولی جاب دوبار اجرا شد و دیر شد.

## سیگنال را با context بگیر

`signal.NotifyContext` یک context برمی‌گرداند که با رسیدن یکی از سیگنال‌های فهرست‌شده cancel می‌شود:

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
```

حالا سیگنال پروسه را نمی‌کشد؛ فقط `ctx.Done()` بسته می‌شود. بقیه‌اش دست خودمان است و کل ماجرا همین است.

## ترتیب خاموش‌شدن

ترتیب مهم است:

1. گرفتن پیام جدید را متوقف کن.
2. منتظر handlerهای در حال اجرا بمان، ولی فقط تا یک سقف.
3. مطمئن شو ackها فرستاده شده‌اند.
4. `nc.Drain()` و خروج.

```go
for ctx.Err() == nil { // stop fetching once the signal arrives
    msgs, err := sub.Fetch(1, nats.MaxWait(time.Second))
    if err != nil {
        continue
    }
    m := msgs[0]
    wg.Add(1)
    go func() {
        defer wg.Done()
        if err := handle(jobCtx, m, work); err != nil {
            return // not acked, will be redelivered
        }
        m.AckSync()
    }()
}

shutCtx, cancel := context.WithTimeout(context.Background(), grace)
defer cancel()
done := make(chan struct{})
go func() { wg.Wait(); close(done) }()
select {
case <-done:
case <-shutCtx.Done():
    cancelJobs() // jobCtx: ask handlers to give up
    wg.Wait()
    code = 1
}
nc.Drain()
os.Exit(code)
```

دو نکته. handlerها `jobCtx` می‌گیرند نه `ctx`: سیگنال نباید کاری را که می‌خواهیم تمام شود cancel کند، فقط timeout این کار را می‌کند. و `AckSync` منتظر تأیید سرور می‌ماند، پس ack هنگام خروج در یک بافر جا نمی‌ماند. بعد `Drain` اجازه می‌دهد اتصال درست flush و بسته شود.

با shutdown timeout برابر ۱۰ ثانیه و `SIGTERM` یک ثانیه بعد از شروع (هر دو جاب ۳ ثانیه طول می‌کشند و هم‌زمان اجرا می‌شوند):

```
23:41:54.845 [79434] start  job-1 (delivery #1), takes 3s
23:41:54.845 [79434] start  job-2 (delivery #1), takes 3s
--- kill -TERM 79434
23:41:55.845 [79434] signal received, no more fetching; waiting for in-flight jobs
23:41:57.846 [79434] acked  job-1
23:41:57.846 [79434] acked  job-2
23:41:57.846 [79434] all in-flight jobs finished
23:41:57.846 [79434] drained, exit code 0
worker exit status: 0
23:41:57.862 [79388] server: consumer pending=0 ackPending=0 redelivered=0
```

جاب‌ها بعد از سیگنال تمام و ack شدند، پروسه با کد ۰ خارج شد، و سرور `redelivered=0` و هیچ pending نشان می‌دهد. Worker دومی که بعداً بالا آوردم کاری پیدا نکرد.

## وقتی handler از timeout بیشتر طول می‌کشد

حالا جاب‌ها ۸ ثانیه طول می‌کشند و shutdown timeout برابر ۱٫۵ ثانیه است:

```
23:42:08.264 [80234] start  job-1 (delivery #1), takes 8s
--- kill -TERM 80234
23:42:09.264 [80234] signal received, no more fetching; waiting for in-flight jobs
23:42:10.765 [80234] shutdown timeout: true, cancelling jobs
23:42:10.765 [80234] abort  job-1: context canceled (not acked)
23:42:10.766 [80234] drained, exit code 1
23:42:13.266 [80428] start  job-1 (delivery #2), takes 1s
23:42:13.309 [80227] server: consumer pending=0 ackPending=2 redelivered=2
```

Worker سر وقت دست کشید، ack نزد و با کد ۱ خارج شد. پیام‌ها با تمام شدن `AckWait` (۰۸.۳ به‌اضافه‌ی ۵ ثانیه) به‌صورت delivery #2 برگشتند. پس خاموشی تمیز تضمین نیست؛ فقط پنجره‌ی خطا را کوچک می‌کند، و handler idempotent مقاله‌ی قبل هنوز لازم است.

## کد خروج و Kubernetes

کد خروج غیر صفر به هر که پروسه را مدیریت می‌کند می‌گوید خاموشی تمیز نبوده؛ برای همین هنگام timeout عدد ۱ را برمی‌گردانم. در Kubernetes، تا جایی که از رفتار مستندش می‌دانم، pod اول `SIGTERM` می‌گیرد و بعد از `terminationGracePeriodSeconds` یک `SIGKILL` که قابل گرفتن نیست. اینجا Kubernetes را اجرا نکردم و درباره‌ی مقدار پیش‌فرضش هم ادعایی ندارم. قاعده‌ای که از آن برمی‌دارم: shutdown timeout را کمتر از grace period بگذار و grace period را بلندتر از کندترین جاب معمولی.

## چند نکته‌ی مهم

- `Fetch` با `MaxWait` یعنی حلقه حداکثر ظرف یک ثانیه سیگنال را می‌فهمد. این مدت را کوتاه نگه دار.
- اگر می‌خواهی handlerها تمام کنند، context سیگنال را به آن‌ها نده. از یک context جدا استفاده کن که فقط timeout آن را cancel می‌کند.
- handlerهای طولانی باید context را چک کنند، وگرنه timeout نمی‌تواند متوقف‌شان کند و `wg.Wait()` بعد از آن گیر می‌کند.
- `SIGKILL` همه‌ی این‌ها را دور می‌زند. خاموشی تمیز تحویل مجدد را کم می‌کند، حذف نمی‌کند.
- اگر پروسه HTTP هم سرو می‌کند، آن را هم در همین ترتیب خاموش کن.

## قدم بعدی

Worker حالا درست خاموش می‌شود، ولی وقتی چیزی خراب شود هنوز بیشتر حدس می‌زنیم. مقاله‌ی بعد درباره‌ی observability برای JetStream است: متریک، لاگ و trace.
