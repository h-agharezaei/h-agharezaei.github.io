+++
date = '2027-01-25T10:00:00+03:30'
draft = false
title = 'الگوهای concurrency: worker pool و errgroup'
description = 'worker pool محدود، errgroup با لغو در اولین خطا، SetLimit، pipeline، نشتی goroutine، حفظ ترتیب نتایج و semaphore وزن‌دار، با اجرای واقعی و -race.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "concurrency", "errgroup", "worker-pool", "semaphore"]
cover = { image = "/images/covers/go-concurrency-patterns.fa.png", alt = "الگوهای concurrency: worker pool و errgroup", hiddenInSingle = true }
+++

handlerای را تصور کنید که یک سرویس کند را صدا می‌زند. برای اطمینان بعد از ۱۰ میلی‌ثانیه دست می‌کشد و بدون آن نتیجه به کاربر جواب می‌دهد. فراخواننده می‌رود پی کارش و همه‌چیز خوب به نظر می‌رسد. اما goroutineای که فراخوانی را انجام می‌داد هنوز زنده است و وقتی بالاخره تمام می‌شود و می‌خواهد نتیجه را تحویل بدهد، کسی گوش نمی‌دهد. برای همیشه منتظر می‌ماند. این handler را ۳۰۰ بار صدا بزنید تا ۳۰۰ goroutine داشته باشید که هرگز تمام نمی‌شوند. چیزی crash نمی‌کند و تازه وقتی می‌فهمید که حافظه چند روز است مدام بالا می‌رود.

این مشکل اول این نوشته است. مشکل دوم نقطه‌ی مقابلش است: حلقه‌ای که برای هر آیتم یک goroutine راه می‌اندازد. با ۱۰٬۰۰۰ آیتم، ۱۰٬۰۰۰ فراخوانی هم‌زمان به دیتابیس یا یک API می‌رود و pool اتصال دیتابیس یا سهمیه‌ی API، برخلاف goroutine، ارزان نیست. مشکل سوم گروهی از goroutineهاست که یکی‌شان شکست می‌خورد و بقیه برای نتیجه‌ای که کسی نمی‌خواهد به کار ادامه می‌دهند.

هر سه یک درمان دارند: **کار را هم‌زمان اجرا کنید، اما محدود، و وقتی دیگر لازم نیست وادارش کنید متوقف شود.** Go برای این چند الگوی کوچک و شناخته‌شده دارد: worker pool، `errgroup`، pipeline با cancellation و semaphore وزن‌دار. این نوشته هرکدام را در یک برنامه‌ی کوچک می‌سازد و نشان می‌دهد چه چاپ می‌کند. مثال‌ها Go ساده‌اند و دیتابیس ندارند و پایه‌شان [goroutine و channel](/fa/posts/go-goroutines-channels/) و [sync، select و context](/fa/posts/go-sync-select-context/) است. نوشته‌ی قبل، [تراکنش و الگوی Repository](/fa/posts/go-transactions-patterns/)، درباره‌ی هم‌زمانی بین کلاینت‌های دیتابیس بود و این یکی درباره‌ی هم‌زمانی داخل خود پروسه‌ی Go است.

> همه‌چیز دوباره با Go 1.27 روی macOS (arm64)، با race detector (`go run -race`) و `golang.org/x/sync` نسخه‌ی v0.24.0 اجرا شده است. زمان نشان نمی‌دهم، فقط تعداد و ترتیب. وقتی چند goroutine هم‌زمان کار می‌کنند، ترتیب بعضی خط‌ها از اجرایی به اجرای دیگر عوض می‌شود. هر جا مهم بود گفته‌ام. کد یک مثال محلی است و ریپوی منتشرشده ندارد.

## واژه‌هایی که لازم داریم

چهار چیز از نوشته‌های قبل، هرکدام در یک جمله، تا ادامه روان خوانده شود:

- **{{< term "goroutine" "goroutine" >}}** تابعی است که هم‌زمان با بقیه‌ی برنامه اجرا می‌شود. `go f()` یکی راه می‌اندازد.
- **{{< term "channel" "channel" >}}** لوله‌ای بین goroutineهاست. ارسال روی channel بدون بافر صبر می‌کند تا goroutine دیگری دریافت کند و دریافت صبر می‌کند تا کسی بفرستد. channel بافردار چند مقدار را نگه می‌دارد، پس ارسال فقط وقتی صبر می‌کند که بافر پر باشد.
- `sync.WaitGroup` شمارنده‌ای است برای صبرکردن تا تمام شدن گروهی از goroutineها.
- **{{< term "context" "context" >}}** پیام «همین حالا بایست» را حمل می‌کند. کدی که حاضر است متوقف شود `ctx.Done()` را زیر نظر دارد، channelی که با لغو context یا رسیدن deadline بسته می‌شود. لغو در Go همکارانه است: چیزی کشته نمی‌شود و خود کد باید نگاه کند.

## نشت goroutine: اول نسخه‌ی خراب

این همان handler مقدمه است. `slow` یک فراخوانی شبیه‌سازی‌شده است که ۳۰ میلی‌ثانیه طول می‌کشد. `leaky` آن را در یک goroutine راه می‌اندازد و حداکثر ۱۰ میلی‌ثانیه برای نتیجه صبر می‌کند:

```go
func leaky() (int, bool) {
	ch := make(chan int)
	go func() { ch <- slow(context.Background()) }()
	select {
	case v := <-ch:
		return v, true
	case <-time.After(10 * time.Millisecond):
		return 0, false
	}
}
```

زمان‌سنج ۱۰ میلی‌ثانیه‌ای همیشه برنده است. `leaky` مقدار `false` برمی‌گرداند و کسی هرگز از `ch` نمی‌خواند. حدود بیست میلی‌ثانیه بعد goroutine از `slow` بیرون می‌آید و `ch <- 42` را اجرا می‌کند. channel بدون بافر است، پس ارسال منتظر گیرنده‌ای می‌ماند که هرگز نمی‌آید. goroutine تا آخر عمر برنامه گیر می‌کند. این یک {{< term "goroutine-leak" "نشت goroutine" >}} (goroutine leak) است.

`leaky` را ۳۰۰ بار صدا زدم و بعد از هر صد فراخوانی `runtime.NumGoroutine()` را چاپ کردم:

```
start: 1
leaky after 100 calls: 101 goroutines
leaky after 200 calls: 201 goroutines
leaky after 300 calls: 301 goroutines
```

برنامه با یک goroutine شروع می‌شود (`main`). بعد از ۱۰۰ فراخوانی ۱۰۱ تا داریم، بعد ۲۰۱ و بعد ۳۰۱. هر فراخوانی دقیقاً یکی نشت داد.

راه‌حل دو بخش دارد و هر دو کوچک‌اند:

```go
func fixed() (int, bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	ch := make(chan int, 1)
	go func() { ch <- slow(ctx) }()
	select {
	case v := <-ch:
		return v, true
	case <-ctx.Done():
		return 0, false
	}
}
```

اول اینکه channel بافر ۱ دارد، پس ارسال goroutine همیشه موفق می‌شود، حتی اگر کسی نخواند. دوم اینکه کار یک context با همان timeout می‌گیرد، پس `slow` زود متوقف می‌شود و نتیجه‌ای را که کسی نمی‌خواهد تا آخر نمی‌رود. بعد `fixed` را ۳۰۰ بار روی همان goroutineهای نشت‌کرده اجرا کردم:

```
fixed after 300 calls: 301 goroutines (added 0)
```

عدد ۳۰۱ همان goroutineهای نشت‌کرده‌ی قبلی (و `main`) است. بخش مهم «added 0» است. قاعده‌ای که باید با خودتان ببرید: **هر goroutineای که راه می‌اندازید باید راهی تضمین‌شده برای تمام شدن داشته باشد.** برای هرکدام بپرسید «چه چیزی باعث می‌شود این goroutine return کند؟»

## worker pool محدود

حالا مشکل دوم: کارهای زیاد، ظرفیت محدود. **{{< term "worker-pool" "worker pool" >}}** (استخر کارگر) تعداد ثابتی goroutine راه می‌اندازد، کارگرها. همه از یک channel کار می‌خوانند و کارها بینشان تقسیم می‌شود. هر کارگر نتیجه‌اش را در channel دوم می‌نویسد. پخش‌کردن کار بین کارگرها را fan-out می‌گویند و جمع‌کردن نتیجه‌ها در یک channel را fan-in ({{< term "fan-out-fan-in" "fan-out و fan-in" >}}).

نکته‌ی ظریف این است که چه کسی کدام channel را می‌بندد. تولیدکننده وقتی کاری ندارد `jobs` را می‌بندد و حلقه‌ی `range` کارگرها تمام می‌شود. یک goroutine جدا با `WaitGroup` منتظر همه‌ی کارگرها می‌ماند و بعد از آن `results` را می‌بندد تا `range` خواننده‌ی نتایج هم تمام شود:

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

(از Go 1.22 هر دور حلقه `w` خودش را دارد، پس هر goroutine شماره‌ی کارگر خودش را می‌بیند.) با ۳ کارگر و ۹ کار، `go run -race` این را چاپ کرد:

```
jobs done: [1 2 3 4 5 6 7 8 9]
workers used: 3 total: 9
```

هر ۹ کار تمام شد و هر ۳ کارگر کار کردند. نتایج به ترتیب تمام‌شدن کارها می‌رسند که از اجرایی به اجرای دیگر فرق می‌کند، برای همین برنامه پیش از چاپ آن‌ها را مرتب می‌کند. پایین‌تر می‌بینیم چطور ترتیب ورودی را نگه داریم.

## errgroup: اولین خطا بقیه را متوقف می‌کند

pool بالا کلی لوله‌کشی است: دو channel، یک `WaitGroup` و قاعده‌های بستن. بیشتر وقت‌ها چیز ساده‌تری می‌خواهیم: این تابع‌ها را اجرا کن، منتظر همه بمان و اولین خطا را بگو. کار **{{< term "errgroup" "errgroup" >}}** (از `golang.org/x/sync`) همین است. `errgroup.WithContext` یک context هم برمی‌گرداند که به‌محض اینکه هر تابعی خطا برگرداند (یا وقتی `Wait` برگردد) لغو می‌شود، تا بقیه‌ی تابع‌ها بفهمند و متوقف شوند.

برای دیدنش، پنج کار قرار است در ۴۰، ۸۰، ۱۲۰، ۱۶۰ و ۲۰۰ میلی‌ثانیه تمام شوند و کار سوم وقتی نوبتش می‌رسد شکست می‌خورد. کارها با یک `select` منتظر می‌مانند: یا وقتشان می‌رسد، یا context لغو می‌شود. دمو برای هر رویداد یک خط را در یک slice محافظت‌شده با mutex ثبت می‌کند و آخر چاپ می‌کند تا خروجی goroutineهای مختلف قاطی نشود:

```go
g, ctx := errgroup.WithContext(context.Background())
for i := 1; i <= 5; i++ {
	g.Go(func() error {
		d := time.Duration(i) * 40 * time.Millisecond
		select {
		case <-time.After(d):
			if i == 3 {
				note("job 3 failed")
				return errors.New("job 3: upstream returned 500")
			}
			note(fmt.Sprintf("job %d finished", i))
			return nil
		case <-ctx.Done():
			note(fmt.Sprintf("job %d cancelled: %v", i, context.Cause(ctx)))
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
job 5 cancelled: job 3: upstream returned 500
job 4 cancelled: job 3: upstream returned 500
Wait returned: job 3: upstream returned 500
```

کارهای ۱ و ۲ پیش از شکست تمام شدند. کار ۳ در ۱۲۰ میلی‌ثانیه شکست خورد. این context را لغو کرد و کارهای ۴ و ۵ که هنوز منتظر بودند `ctx.Done()` را دیدند و ایستادند. (ترتیب دو خط «cancelled» ممکن است بین اجراها جابه‌جا شود، چون تقریباً هم‌زمان رخ می‌دهند.) `context.Cause(ctx)` خطایی را برمی‌گرداند که باعث لغو شد، برای همین پیام آن‌ها خطای کار ۳ را دارد. `ctx.Err()` تنها می‌گفت «context canceled». در آخر `Wait` اولین خطا را برمی‌گرداند. کارهای ۴ و ۵ فقط چون `ctx` را زیر نظر داشتند زود ایستادند: هیچ چیز مجبورشان نمی‌کرد. باز هم لغو همکارانه است.

## SetLimit: ثابت‌کردن سقف

`errgroup` می‌تواند خودش pool هم باشد. `g.SetLimit(n)` باعث می‌شود وقتی `n` تابع در حال اجراست `g.Go` بلاک شود تا یکی تمام شود. به‌جای اعتماد، دمو با یک `atomic.Int32` می‌شمارد در هر لحظه چند تابع هم‌زمان اجرا می‌شوند و بیشینه را به خاطر می‌سپارد. هر کدام از ۴۰ کار ۲۰ میلی‌ثانیه می‌خوابد:

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

چهل کار فرستاده شد و در هیچ لحظه‌ای بیشتر از چهار تا هم‌زمان اجرا نشد. توجه کنید که `g.Go` حلقه‌ی فرستنده را بلاک می‌کند، پس خود حلقه هم با سرعت کارگرها کند می‌شود. اینکه تولیدکننده با کندیِ مصرف‌کننده آهسته شود **backpressure** (فشار برگشتی) نام دارد و اینجا مجانی گیرتان می‌آید.

## pipeline با cancellation

**pipeline** زنجیره‌ای از مرحله‌هاست که با channel به هم وصل شده‌اند: یک مرحله مقدار تولید می‌کند، بعدی تبدیلش می‌کند و آخری مصرفش می‌کند. همان ایده‌ی fan-out/fan-in است که در یک خط چیده شده. خطرش همان خطر نشت ابتدای نوشته است: اگر مرحله‌ی آخر خواندن را متوقف کند، مرحله‌های قبلی روی ارسال‌هایشان گیر می‌کنند. قاعده‌ای که جلویش را می‌گیرد این است که **هر ارسال یک `select` در برابر `ctx.Done()` باشد**:

```go
select {
case out <- n * n:
case <-ctx.Done():
	return ctx.Err()
}
```

در دمو یک generator عددهای ۱، ۲، ۳ و ... را تا ابد تولید می‌کند، مرحله‌ی دوم آن‌ها را به توان دو می‌رساند و sink (مرحله‌ی آخر) بعد از دریافت پنج مقدار context را لغو می‌کند:

```
got 1
got 4
got 9
got 16
got 25
Wait: context canceled | all stages exited: true
```

sink پنج مربع را چاپ کرد و لغو کرد. دو مرحله‌ی قبلی که تا ابد اجرا می‌شدند `ctx.Done()` را دیدند و return کردند، پس `Wait` برگشت. `all stages exited: true` بررسی این است که `Wait` در کمتر از یک ثانیه برگشته و معلق نمانده. `Wait` خطای `context canceled` را برمی‌گرداند، چون مرحله‌ها `ctx.Err()` برگرداندند. اگر نمی‌خواهید یک توقف عمدی برای فراخواننده شبیه شکست باشد، همان یک خطا را هر جا `Wait` را صدا می‌زنید موفقیت حساب کنید.

## نگه‌داشتن ترتیب ورودی

کارگرها به هر ترتیبی تمام می‌کنند، اما اغلب نتیجه‌ها را به ترتیب ورودی می‌خواهید. ترفند ساده: پیش از شروع یک slice با یک جا برای هر ورودی بسازید و بگذارید هر goroutine فقط در جای خودش بنویسد:

```go
out := make([]string, len(inputs))
for i, s := range inputs {
	g.Go(func() error {
		out[i] = strings.ToUpper(s)
		return nil
	})
}
```

در دمو ورودی‌های دیرتر کمتر می‌خوابند و زودتر تمام می‌شوند، اما خروجی `[A B C D E F G H]` است، به ترتیب ورودی. به mutex نیازی نیست، چون goroutineها در عنصرهای مختلف می‌نویسند که جاهای مختلفی از حافظه‌اند و `Wait` هرچه آن‌ها نوشته‌اند را برای کدی که بعد slice را می‌خواند دیدنی می‌کند. با `-race` اجرا کردم و detector ساکت ماند. اما `append` روی یک slice مشترک از چند goroutine یا نوشتن در یک map مشترک امن نیست.

## سقف وزن‌دار با semaphore

`SetLimit` کارها را می‌شمارد و همه را مساوی می‌گیرد. گاهی مساوی نیستند: یک کار ۱ مگابایت حافظه نگه می‌دارد و دیگری ۸ مگابایت. **{{< term "semaphore" "semaphore" >}}** شمارنده‌ی «مجوز» است که goroutineها پیش از کار باید بردارند و بعد از آن پس بدهند و `semaphore.Weighted` اجازه می‌دهد یک کار چند مجوز را یکجا بردارد. اینجا بودجه‌ی ۱۰ و این وزن‌ها را به کار بردم: `5 5 3 3 3 2 8 1 1 4`. حلقه پیش از راه‌انداختن هر goroutine وزنش را می‌گیرد و goroutine وقتی تمام شد آن را پس می‌دهد:

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

برنامه در هر لحظه مجموع وزن در حال استفاده را ثبت کرد و اوجش دقیقاً ۱۰ بود، هرگز بیشتر. دو خط آخر نشان می‌دهند درخواستی سنگین‌تر از کل بودجه چه می‌شود: هرگز موفق نمی‌شود. `Acquire(11)` صبر می‌کند تا context‌اش تمام شود (اینجا timeout پنجاه میلی‌ثانیه‌ای) و `TryAcquire(11)` صبر نمی‌کند و فوراً `false` برمی‌گرداند.

## اشتباه‌های رایج در کد هم‌زمان

- **goroutine بدون راه خروج.** اگر کد داخل goroutine در حلقه‌ها و فراخوانی‌های بلاک‌کننده‌اش هرگز `ctx.Done()` را نگاه نکند، لغو هیچ چیز را عوض نمی‌کند.
- **بستن channel از جای اشتباه.** بستن کار فرستنده است. اگر چند فرستنده دارید، از یک goroutine بیندید که اول منتظر همه‌ی آن‌هاست، همان‌طور که goroutineِ `WaitGroup` بالا کرد.
- **سقف روی goroutine سقف روی منبع نیست.** `SetLimit(n)` goroutineها را محدود می‌کند، نه آنچه پایین‌دست مصرف می‌کنند. سقف را با pool دیتابیس یا سهمیه‌ی API بسنجید.
- **غافلگیری‌های `errgroup`.** تا goroutineها در حال اجرا هستند `SetLimit` را صدا نزنید (طبق مستندات تا وقتی goroutineای فعال است نباید تغییر کند) و یادتان باشد `errgroup` فقط اولین خطا را نگه می‌دارد.
- **اجرا نکردن race detector.** `go test -race` را روی هر مسیر هم‌زمان اجرا کنید.

## تمرین

تابع `MapOrdered(ctx, inputs, n, fn)` را بنویسید که `fn` را روی هر ورودی با حداکثر `n` goroutine اجرا کند، نتیجه‌ها را به ترتیب ورودی برگرداند و با اولین خطا متوقف شود. آن را با `-race` تست کنید.

## قدم بعدی

نوشته‌ی بعد «Outbox Pattern با Postgres و NATS در Go» است. آنجا حلقه‌ای در پس‌زمینه باید یک دیتابیس و یک message broker را هم‌گام نگه دارد و انضباط goroutine از این نوشته همان چیزی است که نمی‌گذارد آن حلقه نشت کند یا معلق بماند.
