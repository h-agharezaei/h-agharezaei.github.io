+++
date = '2027-03-02T10:00:00+03:30'
draft = false
title = 'زمان‌بند runtime و GC در Go'
description = 'درون runtime زبان Go را ببینید: مدل G-M-P، schedtrace، تردها و syscall مسدودکننده، preemption، gctrace، GOGC، GOMEMLIMIT و sync.Pool با اجرای واقعی.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "runtime", "scheduler", "gc", "performance"]
cover = { image = "/images/covers/go-scheduler-gc-internals.fa.png", alt = "زمان‌بند runtime و GC در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-docker-ci-deploy/) سرویس را به‌شکل کانتینر تحویل دادیم. حالا به درون runtime همان پروسه نگاه می‌کنیم: goroutineها چطور روی CPU می‌نشینند و حافظه چطور پاک می‌شود. مقاله روی [goroutine و channel](/fa/posts/go-goroutines-channels/)، [پروفایلینگ با pprof](/fa/posts/go-profiling-pprof/) و [escape analysis و heap](/fa/posts/go-pointers-memory/) بنا شده است.

> Go 1.26 روی macOS (arm64) با ۸ CPU. load average حدود ۱٫۶ بود، ولی **هیچ زمانی** نشان نمی‌دهم؛ فقط شمارش و اندازه‌ی تقریبی.

## مدل G-M-P با زبان ساده

مستندات سه چیز را توصیف می‌کنند. **G** همان goroutine است. **M** یک thread سیستم‌عامل است. **P** یک «پردازنده» است، یعنی توکنی که thread باید برای اجرای کد Go در دست داشته باشد؛ به تعداد `GOMAXPROCS` وجود دارد. هر P یک صف اجرای محلی دارد، یک صف سراسری هم هست و Pِ بیکار می‌تواند از بقیه کار بدزدد (**work stealing**).

```go
fmt.Println("NumCPU       =", runtime.NumCPU())
fmt.Println("GOMAXPROCS   =", runtime.GOMAXPROCS(0)) // 0 = query only
fmt.Println("NumGoroutine =", runtime.NumGoroutine())
```

```
NumCPU       = 8
GOMAXPROCS   = 8
NumGoroutine = 1
NumGoroutine = 51 after starting 50
GOMAXPROCS   = 2 (was 8 )
```

## تماشا: schedtrace

`GODEBUG=schedtrace=1000` هر ثانیه یک خط چاپ می‌کند. برنامه‌ام ۲۰۰ goroutine را بالا می‌آورد که هرکدام مدتی CPU را مشغول نگه می‌دارند. دو خط (انتهای `schedticks` را حذف کرده‌ام):

```
SCHED 0ms: gomaxprocs=8 idleprocs=6 threads=3 spinningthreads=1 ... runqueue=0 [ 0 0 0 0 0 0 0 0 ]
SCHED 1010ms: gomaxprocs=8 idleprocs=0 threads=9 spinningthreads=0 ... runqueue=82 [ 12 1 11 14 10 1 0 61 ]
```

`gomaxprocs` تعداد Pهاست. `idleprocs=0` یعنی همه‌ی Pها مشغول‌اند. `threads=9` تعداد Mهاست. `runqueue=82` صف سراسری است و داخل کروشه صف محلی هر یک از ۸ P آمده. وقتی کار تمام شد، trace نشان داد `idleprocs=8` و `threads=9`: تردها بعد از پایان کار می‌مانند.

## تردها: syscall مسدودکننده در برابر انتظار در Go

goroutineِ مسدود یک thread خرج می‌کند؟ بستگی دارد چطور مسدود شود. ۱۰۰ goroutine راه می‌اندازم و تردهای ساخته‌شده را با `pprof.Lookup("threadcreate").Count()` می‌شمارم.

```go
case "syscall":
	r, _, _ := os.Pipe() // nothing is ever written
	go func() { buf := make([]byte, 1); syscall.Read(int(r.Fd()), buf) }()
case "sleep":
	go time.Sleep(time.Minute)
case "chan":
	c := make(chan int)
	go func() { <-c }()
```

```
syscall  threadcreate before=5 after=103
sleep    threadcreate before=5 after=6
chan     threadcreate before=5 after=5
```

goroutineای که در یک syscall خام مسدود است thread خودش را نگه می‌دارد: حدود ۹۸ thread اضافه ساخته شد. goroutineهای منتظر channel یا timer را scheduler پارک می‌کند و thread نمی‌خواهند.

## Preemption

با `GOMAXPROCS(1)` یک goroutine حلقه‌ی `for {}` اجرا می‌کند و goroutine اصلی منتظر ticker با فاصله‌ی ۱۰۰ms می‌ماند:

```
tick 1
tick 2
tick 3
tick 4
tick 5
```

ticker گرسنه نمی‌ماند: از Go 1.14 به بعد runtime از **asynchronous preemption** برای قطع چنین حلقه‌ای استفاده می‌کند. پیش از آن preemption فقط **cooperative** و هنگام فراخوانی تابع بود، پس حلقه‌ی بدون فراخوانی می‌توانست بقیه را مسدود کند. نسخه‌های قدیمی را اجرا نکردم؛ این تاریخچه‌ی مستند است.

## garbage collector

طبق مستندات، GC در Go یک collector هم‌روند (concurrent)، بدون نسل‌بندی و از نوع **tri-color mark-and-sweep** است. در حالی که کد شما اجرا می‌شود، اشیای قابل‌دسترس را علامت می‌زند، فقط با وقفه‌های stop-the-world بسیار کوتاه، و بعد حافظه‌ی غیرقابل‌دسترس را جارو می‌کند. `GODEBUG=gctrace=1` برای هر چرخه یک خط چاپ می‌کند:

```
gc 3 @0.006s 2%: 0.020+0.25+0.023 ms clock, 0.16+0.054/0.21/0.021+0.18 ms cpu, 15->16->8 MB, 16 MB goal, 0 MB stacks, 0 MB globals, 8 P
```

فیلد به فیلد: چرخه‌ی ۳، ۰٫۰۰۶ ثانیه بعد از شروع، تا این لحظه ۲٪ CPU صرف GC شده؛ سه عدد clock به‌ترتیب وقفه‌ی sweep-termination، mark هم‌روند و وقفه‌ی mark-termination‌اند؛ اعداد cpu همین کار را به‌تفکیک نقش نشان می‌دهند؛ `15->16->8 MB` اندازه‌ی heap در شروع، در پایان و زنده‌ی بعد از آن است؛ `16 MB goal` هدف بعدی است؛ `8 P` همان GOMAXPROCS است. از زمان‌ها نتیجه‌ای نمی‌گیرم.

در کد، `runtime.ReadMemStats` مقدار `NumGC` و `HeapAlloc` را می‌دهد.

## GOGC و GOMEMLIMIT

بار آزمایشی ۲۰۰٬۰۰۰ slice چهار کیلوبایتی می‌سازد و حدود ۸ مگابایت را زنده نگه می‌دارد. فقط `GOGC` بین اجراها عوض می‌شود (شمارش‌ها بین اجراها کمی فرق می‌کنند، پس بازه می‌دهم):

| GOGC | تعداد چرخه‌ی GC | اوج HeapAlloc (نمونه‌برداری) |
|---|---|---|
| 50 | ~170-180 | ~16-20 MiB |
| 100 | ~90 | ~20-24 MiB |
| 400 | ~21 | ~48-54 MiB |
| off | 0 | ~777 MiB |

`GOGC` بالاتر یعنی چرخه‌ی کمتر و حافظه‌ی بیشتر؛ این معاوضه است. **GOMEMLIMIT** سقف نرم حافظه است و GC برای ماندن زیر آن سخت‌تر کار می‌کند. با `GOGC=off GOMEMLIMIT=24MiB` حدود ۱۰۰ چرخه و اوج نزدیک ۱۹ مگابایت دیدم، به‌جای ۷۷۷ مگابایت. سقف نزدیک به heap زنده خطرناک است: با `GOMEMLIMIT=12MiB` همان برنامه حدود ۱۱۰۰ تا ۱۸۰۰ چرخه داشت (حدود ۸ مگابایت زنده است). سقف نرم است و تضمین نیست.

## sync.Pool

**sync.Pool** اشیای موقت را دوباره استفاده می‌کند. benchmarkی که در یک `bytes.Buffer` رندر می‌کند (`-benchmem`، ۲۰٬۰۰۰ تکرار):

```
BenchmarkNoPool-8   20000   1984 B/op   5 allocs/op
BenchmarkPool-8     20000      0 B/op   0 allocs/op
```

allocation کمتر یعنی چرخه‌ی GC کمتر. runtime ممکن است در هر GC اشیای pool را دور بریزد؛ پس pool کش است، نه انبار.

## چند نکته‌ی احتیاط

- `NumGoroutine` و تعداد thread دو سؤال متفاوت‌اند؛ در production هر دو را زیر نظر بگیرید.
- پیش از پروفایل کردن `GOGC` را دست نزنید؛ اول allocationها را کم کنید.
- از `runtime.SetFinalizer` پرهیز کنید: زمان اجرایش نامعلوم است یا هرگز اجرا نمی‌شود.
- شیء pool را قبل از استفاده‌ی دوباره reset کنید و بعد از `Put` به آن دست نزنید.

## تمرین

1. برنامه‌ی تردها را با ۱۰۰۰ goroutine در حالت `syscall` اجرا کنید و تعداد را مقایسه کنید.
2. `gcdemo` را با `GOGC=200` اجرا کنید و در جدول جا بدهید.

## قدم بعدی

این آخرین مقاله‌ی سری Go Backend است. مقاله‌ی بعدیِ تقویم: observability در Rust با tracing. مرور پایان سال سری Go هم بعداً در ماه مارس می‌آید.
