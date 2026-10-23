+++
date = '2027-01-25T10:00:00+03:30'
draft = false
title = 'الگوهای concurrency: worker pool و errgroup'
description = 'worker pool محدود، errgroup با لغو در اولین خطا، SetLimit، pipeline، نشتی goroutine، حفظ ترتیب نتایج و semaphore وزن‌دار، با اجرای واقعی و -race.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "concurrency", "errgroup", "worker-pool", "semaphore"]
cover = { image = "/images/covers/go-concurrency-patterns.fa.png", alt = "الگوهای concurrency: worker pool و errgroup", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/go-transactions-patterns/) درباره‌ی تراکنش و الگوی repository بود. مثال‌های این مقاله Go ساده‌اند و دیتابیس نمی‌خواهند. در کد backend اغلب چند کار مستقل داریم (فراخوانی HTTP، query، فایل) که باید هم‌زمان اجرا شوند، ولی نه بی‌حد، و اگر یکی خراب شد بقیه متوقف شوند. این مقاله روی [goroutine و channel](/fa/posts/go-goroutines-channels/) و [sync، select و context](/fa/posts/go-sync-select-context/) بنا شده و الگوهایی را نشان می‌دهد که بیشتر از همه سراغشان می‌روم.

> همه‌چیز با Go 1.26 روی macOS (arm64) و `golang.org/x/sync` نسخه‌ی v0.24.0 اجرا شده، با load average حدود ۱٫۴. زمان نشان نمی‌دهم، فقط تعداد و ترتیب.

## worker pool محدود

**worker pool** تعداد ثابتی goroutine بالا می‌آورد که از یک channel به نام jobs می‌خوانند و در channel نتایج می‌نویسند. نکته این است که چه کسی چه چیزی را می‌بندد: تولیدکننده `jobs` را می‌بندد و یک goroutine جدا منتظر `WaitGroup` می‌ماند و `results` را می‌بندد.

```go
for w := 1; w <= workers; w++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		for j := range jobs {
			fetch(j) // simulated I/O
			results <- result{job: j, worker: w}
		}
	}()
}
go func() { for j := 1; j <= 9; j++ { jobs <- j }; close(jobs) }()
go func() { wg.Wait(); close(results) }()
```

با ۳ worker و ۹ جاب، `go run -race` این را چاپ کرد:

```
jobs done: [1 2 3 4 5 6 7 8 9]
workers used: 3 total: 9
```

نتایج به ترتیب تمام شدن می‌رسند، برای همین مرتب‌شان کردم.

## errgroup: اولین خطا بقیه را لغو می‌کند

**errgroup** حالت رایج را بسته‌بندی کرده: چند تابع اجرا کن، منتظر همه بمان، اولین خطا را برگردان. `errgroup.WithContext` یک context هم می‌دهد که با اولین خطا یا با برگشتن `Wait` لغو می‌شود. پنج جاب در ۴۰، ۸۰، ۱۲۰ و ... میلی‌ثانیه تمام می‌شوند و جاب ۳ خطا می‌دهد:

```go
g, ctx := errgroup.WithContext(context.Background())
for i := 1; i <= 5; i++ {
	g.Go(func() error {
		select {
		case <-time.After(time.Duration(i) * 40 * time.Millisecond):
			if i == 3 { return errors.New("job 3: upstream returned 500") }
			return nil
		case <-ctx.Done():
			return ctx.Err()
		}
	})
}
err := g.Wait()
```

```
job 1 finished
job 2 finished
job 3 failed
job 4 cancelled: job 3: upstream returned 500
job 5 cancelled: job 3: upstream returned 500
Wait returned: job 3: upstream returned 500
```

جاب ۴ و ۵ فقط چون `ctx` را زیر نظر دارند زود متوقف می‌شوند. لغو در Go همکارانه است.

## SetLimit: اثبات محدودیت

`g.SetLimit(n)` باعث می‌شود `g.Go` وقتی `n` تابع در حال اجراست block شود. برای اثبات، کارهای در حال اجرا را با `atomic.Int32` می‌شمارم و بیشینه را ثبت می‌کنم:

```go
g.SetLimit(4)
for i := 0; i < 40; i++ {
	g.Go(func() error {
		n := inflight.Add(1)
		// update max with a CompareAndSwap loop
		time.Sleep(20 * time.Millisecond)
		inflight.Add(-1)
		return nil
	})
}
```

```
jobs: 40, limit: 4, max in flight: 4
```

`Go` خودش caller را block می‌کند، پس back-pressure مجانی می‌گیریم.

## fan-out/fan-in و pipeline با لغو

worker pool همان **fan-out** است (چند worker از یک channel می‌خوانند) به‌علاوه‌ی **fan-in** (یک channel نتایج). **pipeline** مرحله‌ها را با channel به هم وصل می‌کند. قاعده‌ای که جلوی نشتی را می‌گیرد این است که هر ارسال، یک `select` در برابر `ctx.Done()` باشد. اینجا یک generator به مرحله‌ی توان‌دوم می‌دهد و مصرف‌کننده بعد از پنج مقدار لغو می‌کند:

```go
select {
case out <- n * n:
case <-ctx.Done():
	return ctx.Err()
}
```

```
got 1
got 4
got 9
got 16
got 25
Wait: context canceled | all stages exited: true
```

`Wait` مقدار `context canceled` را برمی‌گرداند چون مرحله‌ها `ctx.Err()` برگرداندند. اگر توقف عمدی نباید شکست حساب شود، همین خطا را موفقیت بدان.

## نشتی goroutine

یک باگ کلاسیک: فراخوانی بعد از timeout منصرف می‌شود، ولی goroutineی که کار می‌کرد بعداً روی ارسال به یک channel بدون بافر که کسی نمی‌خواند برای همیشه گیر می‌کند. این نسخه را ۳۰۰ بار صدا زدم و `runtime.NumGoroutine()` را چاپ کردم:

```
start: 1
leaky after 100 calls: 101 goroutines
leaky after 200 calls: 201 goroutines
leaky after 300 calls: 301 goroutines
```

هر فراخوانی یک goroutine نشت داد. نسخه‌ی درست channel را با ظرفیت ۱ بافر می‌کند تا ارسال هیچ‌وقت block نشود، و یک context با timeout به کار می‌دهد. بعد از ۳۰۰ فراخوانی دیگر: `fixed after 300 calls: 301 goroutines (added 0)`.

## حفظ ترتیب ورودی

workerها به هر ترتیبی تمام می‌کنند، ولی اغلب نتیجه را به ترتیب ورودی می‌خواهیم. برای هر ورودی یک خانه در slice از پیش ساخته‌شده بگذار و هر goroutine فقط خانه‌ی خودش را بنویسد:

```go
out := make([]string, len(inputs))
for i, s := range inputs {
	g.Go(func() error {
		out[i] = strings.ToUpper(s)
		return nil
	})
}
```

ورودی‌های آخر کمتر sleep می‌کنند و اول تمام می‌شوند، ولی خروجی `[A B C D E F G H]` است. mutex لازم نیست چون goroutineها در عنصرهای متفاوت، یعنی جاهای متفاوتی از حافظه، می‌نویسند، و `Wait` یک رابطه‌ی happens-before می‌سازد، پس خواندن `out` بعد از آن ایمن است. اجرا با `-race` بود و detector ساکت ماند. اگر از چند goroutine `append` کنی یا روی map بنویسی ایمن نیست.

## محدودیت وزن‌دار با semaphore

گاهی جاب‌ها برابر نیستند: یکی ۱ مگابایت نگه می‌دارد و دیگری ۸. `semaphore.Weighted` مجموع وزن را محدود می‌کند. بودجه‌ی ۱۰ و وزن‌های `5 5 3 3 3 2 8 1 1 4` را گذاشتم و قبل از شروع هر goroutine acquire کردم:

```go
sem := semaphore.NewWeighted(10)
if err := sem.Acquire(ctx, w); err != nil { return err }
g.Go(func() error { defer sem.Release(w); /* work */ return nil })
```

```
budget: 10 peak weight in use: 10
Acquire(11): context deadline exceeded
TryAcquire(11): false
```

اوج مصرف هرگز از ۱۰ بیشتر نشد. درخواستی بزرگ‌تر از کل بودجه هرگز موفق نمی‌شود: `Acquire` تا پایان context منتظر می‌ماند و `TryAcquire` فوراً false می‌دهد.

## چند نکته‌ی احتیاطی

- به تابع‌های `Go` راه خروج بده: در حلقه‌ها و فراخوانی‌های blocking به `ctx.Done()` نگاه کن، وگرنه لغو هیچ کاری نمی‌کند.
- بستن channel کار ارسال‌کننده است؛ با چند ارسال‌کننده، از goroutineی ببند که منتظر همه‌ی آن‌هاست.
- `SetLimit` برابر `n` تعداد goroutine را محدود می‌کند، نه منبع پایین‌دست را. عدد را با pool دیتابیس یا سهمیه‌ی API تنظیم کن.
- وقتی goroutineها در حال اجرا هستند `SetLimit` را صدا نزن و `errgroup` فقط اولین خطا را نگه می‌دارد.
- `go test -race` را روی مسیرهای هم‌زمان اجرا کن.

## تمرین

تابعی به نام `MapOrdered(ctx, inputs, n, fn)` بنویس که `fn` را با حداکثر `n` goroutine روی همه‌ی ورودی‌ها اجرا کند، نتایج را به ترتیب ورودی برگرداند و با اولین خطا متوقف شود. آن را با `-race` تست کن.

## قدم بعدی

وقتی کار از دیتابیس و message broker رد می‌شود، هم‌زمانی سخت‌تر می‌شود. مقاله‌ی بعد الگوی outbox با Postgres و NATS در Go است.
