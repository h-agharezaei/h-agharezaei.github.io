+++
date = '2026-11-22T10:00:00+03:30'
draft = false
title = 'Goroutine و Channel در Go'
description = 'آشنایی عملی با همزمانی در Go: goroutine، WaitGroup، channel بافردار و بدون بافر، deadlock، یک pipeline با worker و race detector، با خروجی واقعی.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "goroutines", "channels"]
cover = { image = "/images/covers/go-goroutines-channels.fa.png", alt = "Goroutine و Channel در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-packages-modules/) کد را به package و module تقسیم کردیم. حالا به ویژگی‌ای می‌رسیم که Go بیشتر با آن شناخته می‌شود: همزمانی. در این مقاله goroutine، `sync.WaitGroup`، channel، خطای deadlock که هرکسی یک بار می‌بیند، یک pipeline کوچک با producer و worker و در آخر race detector را می‌بینیم. مقاله‌ی بعد سراغ `sync`، `select` و `context` می‌رود.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام. خروجی‌هایی که به زمان‌بندی بستگی دارند، مشخص شده‌اند.

## همزمانی با موازی‌سازی فرق دارد

**Concurrency** (همزمانی) یعنی برنامه را به کارهای مستقل تقسیم کنیم که در بازه‌های زمانی هم‌پوشان پیش می‌روند. **Parallelism** (موازی‌سازی) یعنی واقعاً در یک لحظه روی چند هسته اجرا شوند. Go با ارزان کردن کارها اولی را به ما می‌دهد و runtime هر جا بتواند آن‌ها را روی هسته‌ها پخش می‌کند. ما کد همزمان می‌نویسیم و scheduler تصمیم می‌گیرد چقدر موازی اجرا شود.

## `go f()` و خروج main

گذاشتن `go` قبل از فراخوانی تابع، آن را به صورت یک **goroutine** شروع می‌کند؛ کاری سبک که runtime مدیریتش می‌کند. فراخوانی بلافاصله برمی‌گردد.

```go
func main() {
	go func() {
		time.Sleep(100 * time.Millisecond)
		fmt.Println("hello from goroutine")
	}()
	fmt.Println("main is done")
}
```

```
main is done
```

goroutine هیچ‌وقت چیزی چاپ نکرد. وقتی `main` برمی‌گردد برنامه تمام می‌شود و بقیه‌ی goroutineها، تمام‌شده یا نه، کشته می‌شوند. پس به راهی برای منتظر ماندن نیاز داریم.

## `sync.WaitGroup`

**WaitGroup** یک شمارنده است: قبل از شروع `Add`، بعد از پایان `Done` و `Wait` تا صفر شدنِ شمارنده بلاک می‌ماند.

```go
var wg sync.WaitGroup
for i := 1; i <= 3; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		time.Sleep(time.Duration(i) * 50 * time.Millisecond)
		fmt.Println("worker", i, "done")
	}()
}
wg.Wait()
fmt.Println("all done")
```

```
worker 1 done
worker 2 done
worker 3 done
all done
```

اینجا `Sleep`ها ترتیب را قطعی کرده‌اند؛ بدونشان ترتیب از اجرایی به اجرای دیگر فرق می‌کند. `Add` را در goroutine شروع‌کننده صدا بزنید نه داخل goroutine جدید، وگرنه ممکن است `Wait` زودتر اجرا شود.

## channel بدون بافر

**Channel** لوله‌ای تایپ‌دار بین goroutineهاست: `ch <- v` می‌فرستد و `<-ch` دریافت می‌کند. channel بدون بافر (`make(chan int)`) جایی برای نگه‌داشتن مقدار ندارد، پس ارسال و دریافت باید همدیگر را ببینند و هرکس زودتر برسد بلاک می‌شود. برای دیدنش زمان را (گردشده به ۱۰۰ میلی‌ثانیه) چاپ کردم:

```go
ch := make(chan int)
go func() {
	time.Sleep(300 * time.Millisecond)
	fmt.Println(ts(), "receiver: ready to receive")
	fmt.Println(ts(), "receiver: got", <-ch)
}()
fmt.Println(ts(), "sender: sending")
ch <- 42
fmt.Println(ts(), "sender: send finished")
```

```
   0ms sender: sending
 300ms receiver: ready to receive
 300ms receiver: got 42
 300ms sender: send finished
```

فرستنده ۳۰۰ میلی‌ثانیه گیر کرد تا گیرنده برسد. ترتیب دو خط آخر ممکن است در اجراهای مختلف جابه‌جا شود، چون هر دو درست بعد از تحویل اتفاق می‌افتند.

## channel بافردار

`make(chan string, 2)` جا برای دو مقدار اضافه می‌کند. ارسال فقط وقتی بلاک می‌شود که بافر پر باشد.

```go
ch := make(chan string, 2)
ch <- "a"
ch <- "b"
select {
case ch <- "c":
	fmt.Println("sent c")
default:
	fmt.Println("a third send would block")
}
```

```
sent a, len 1 cap 2
sent b, len 2 cap 2
a third send would block
a b
```

(`select` با `default` اینجا فقط راهی برای تست بدون بلاک شدن است؛ مقاله‌ی بعد درست‌وحسابی سراغش می‌رویم.)

## بستن channel، `range` و comma-ok

فرستنده با `close(ch)` می‌گوید «دیگر مقداری نمی‌آید». حلقه‌ی `for v := range ch` تا بسته و خالی شدن channel می‌خواند. دریافت از channel بسته هیچ‌وقت بلاک نمی‌شود: zero value برمی‌گرداند و مقدار دوم می‌گوید مقدار واقعی بوده یا نه.

```go
for v := range ch {
	fmt.Println("got", v)
}
v, ok := <-ch
fmt.Println("after close:", v, ok)
```

```
got 10
got 20
got 30
after close: 0 false
```

فقط فرستنده باید ببندد و فقط یک بار؛ ارسال روی channel بسته panic می‌دهد.

## deadlock

ارسال روی channel بدون بافر وقتی کسی نیست که دریافت کند:

```go
ch := make(chan int)
ch <- 1
fmt.Println(<-ch)
```

```
fatal error: all goroutines are asleep - deadlock!

goroutine 1 [chan send]:
main.main()
	.../deadlock/main.go:7 +0x38
exit status 2
```

runtime فهمید هیچ goroutine‌ای دیگر نمی‌تواند جلو برود و برنامه را متوقف کرد. نشان می‌دهد هر goroutine کجا گیر کرده (`chan send`). توجه کنید این تشخیص فقط وقتی کار می‌کند که *همه‌ی* goroutineها بلاک باشند؛ در برنامه‌ی بزرگ‌تر یک goroutine گیرکرده می‌تواند بی‌صدا پنهان بماند.

## یک pipeline ساده با worker

یک producer، سه worker و یک جمع‌کننده. workerها از `jobs` می‌خوانند و در `results` می‌نویسند؛ یک goroutine کمکی بعد از پایان همه‌ی workerها `results` را می‌بندد. ترتیب نتایج به زمان‌بندی بستگی دارد، پس قبل از چاپ مرتب‌شان کردم.

```go
for w := 0; w < 3; w++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		for n := range jobs {
			results <- result{n, n * n}
		}
	}()
}
go func() { for n := 1; n <= 9; n++ { jobs <- n }; close(jobs) }()
go func() { wg.Wait(); close(results) }()
```

```
1^2 = 1
2^2 = 4
...
9^2 = 81
```

(خط‌های ۳ تا ۸ حذف شده‌اند؛ همان الگو را دارند.) نکته‌ای که باید یادتان بماند مالکیت است: producer مالک `jobs` است و آن را می‌بندد، و کسی که می‌داند همه‌ی workerها تمام کرده‌اند `results` را می‌بندد.

## متغیر حلقه و race detector

قبل از Go 1.22، goroutineهایی که داخل حلقه‌ی `for i` شروع می‌شدند همگی یک `i` مشترک داشتند و باگ کلاسیک این بود که همه‌جا مقدار آخر دیده می‌شد. از Go 1.22 به بعد (خط `go` در `go.mod` اینجا 1.25 است) هر تکرار `i` خودش را دارد و تست من `[0 1 2]` چاپ کرد. رفتار قدیمی را اجرا نکردم.

حالا یک شمارنده‌ی عمداً خراب: ۱۰۰۰ goroutine که بدون محافظت `count++` می‌کنند، با `go run -race`:

```
WARNING: DATA RACE
Read at 0x00c000094048 by goroutine 10:
  main.main.func1()
      .../racy/main.go:15 +0x68

Previous write at 0x00c000094048 by goroutine 7:
  main.main.func1()
      .../racy/main.go:15 +0x78
...
count: 853
Found 2 data race(s)
exit status 66
```

detector آن را پیدا کرد و شمارش نهایی هم غلط بود (اینجا ۸۵۳ و در هر اجرا فرق می‌کند؛ اجرای معمولی ۹۶۵ و ۹۷۰ داد). با محافظت `count++` توسط `sync.Mutex`، خروجی `count: 1000` شد و اجرای `-race` تمیز بود. pipeline و بقیه‌ی demoها هم زیر `-race` تمیز بودند.

## چند نکته‌ی احتیاط

- همیشه بدانید یک goroutine چطور تمام می‌شود، وگرنه نشت می‌کند.
- `wg.Add` قبل از `go` و `defer wg.Done()` داخل goroutine.
- channel را از سمت فرستنده ببندید، نه گیرنده.
- روی channel با مقدار nil، ارسال و دریافت برای همیشه بلاک می‌شود.
- تست‌ها و demoها را مرتب با `-race` اجرا کنید؛ خروجیِ درست‌نما چیزی را ثابت نمی‌کند.

## تمرین

۱. تعداد workerها را یک و بعد پنج کنید. آیا خروجیِ مرتب‌شده فرق می‌کند؟ و خروجیِ مرتب‌نشده؟
۲. `jobs` را با ظرفیت ۹ بافردار کنید و goroutine‌ی producer را حذف کنید (در `main` پرش کنید و ببندید). چرا کار می‌کند؟
۳. شمارنده‌ای بنویسید که به‌جای mutex از channel استفاده کند: goroutineها `+1` می‌فرستند و یک goroutine مالک مجموع است.

## قدم بعدی

در مقاله‌ی بعد درباره‌ی `sync`، `select` و `context` در Go می‌نویسم: mutex، timeout، لغو (cancellation) و اینکه goroutineها را چطور تمیز متوقف کنیم.
