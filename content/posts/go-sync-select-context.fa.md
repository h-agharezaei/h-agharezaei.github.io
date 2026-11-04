+++
date = '2026-11-26T10:00:00+03:30'
draft = false
title = 'sync، select و context در Go'
description = 'حافظه‌ی مشترک را با Mutex و atomic و Once ایمن کنید، با select روی چند channel منتظر بمانید و با context کار را لغو کنید؛ با خروجی واقعی race detector.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "context", "sync", "select"]
cover = { image = "/images/covers/go-sync-select-context.fa.png", alt = "sync، select و context در Go", hiddenInSingle = true }
+++

در [Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/) دو مشکل را دیدیم و نیمه‌کاره رها کردیم. اول: وقتی چند goroutine مجبورند یک حافظه‌ی مشترک را دست بزنند، چه کنیم؟ (شمارنده‌ی ۱۰۰۰ goroutine که جواب غلط می‌داد را یادتان هست.) دوم: چطور به یک goroutine بگوییم «کارت را رها کن»؟ بدون جواب اولی race داریم، و بدون جواب دومی goroutineهایی داریم که هیچ‌وقت تمام نمی‌شوند و نشت می‌کنند.

این مقاله جواب هر دو را می‌دهد، با سه ابزار: پکیج `sync` برای محافظت از حافظه‌ی مشترک، دستور `select` برای انتظار روی چند چیز هم‌زمان، و پکیج `context` برای لغو کار و timeout.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام. مسیر فایل‌ها را در خروجی‌ها کوتاه کرده‌ام.

## یک race و رفعش با mutex

اول مشکل را دوباره ببینیم. شمارنده‌ی خراب کلاسیک: ۱۰۰۰ goroutine که همه یک متغیر را زیاد می‌کنند، بدون هیچ محافظی:

```go
counter := 0
for i := 0; i < 1000; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		counter++ // unprotected
	}()
}
```

چرا خراب است؟ چون `counter++` از سه قدم ساخته شده (بخوان، یکی اضافه کن، بنویس) و دو goroutine می‌توانند هر دو قدم اول را قبل از قدم آخر دیگری انجام دهند. اجراهای عادی عددی مثل `counter: 850` و `counter: 984` دادند (در دو اجرای اولیه‌ی من)، و وقتی برای این متن دوباره اجرا کردم `counter: 972` شد. هیچ‌وقت عدد قابل اعتماد ۱۰۰۰ نبود. **race detector** (با `go run -race`) مشکل را اسم می‌برد. این گزارش کوتاه‌شده است:

```
WARNING: DATA RACE
Read at 0x00c000094048 by goroutine 11:
  main.main.func1()
      racy/main.go:15 +0x68

Previous write at 0x00c000094048 by goroutine 7:
  main.main.func1()
      racy/main.go:15 +0x78
...
Found 2 data race(s)
exit status 66
```

گزارش می‌گوید یک goroutine از همان آدرسی می‌خواند که goroutine دیگری قبلاً در آن نوشته، هر دو در خط ۱۵، یعنی `counter++`. (شماره‌ی goroutineها در هر اجرا فرق می‌کند.)

راه‌حل اول **sync.Mutex** است. {{< term "mutex" "Mutex" >}} یک قفل است: در هر لحظه فقط یک goroutine را به بخش بحرانی (critical section)، یعنی کدی که بین `Lock` و `Unlock` است، راه می‌دهد. بقیه روی `Lock` منتظر می‌مانند.

```go
var mu sync.Mutex
mu.Lock()
counter++
mu.Unlock()
```

با قفل، `-race` ساکت است و `mutex counter: 1000` می‌گیریم.

گاهی داده‌ای را بیشتر می‌خوانیم تا بنویسیم (مثلاً یک map که به‌ندرت تغییر می‌کند). آن‌جا **sync.RWMutex** مفید است: اجازه می‌دهد هم‌زمان چند خواننده (`RLock`) داشته باشیم، یا فقط یک نویسنده (`Lock`) و بدون هیچ خواننده. در متدها قفل را با `defer` آزاد کنید تا یک `return` زودهنگام آن را قفل نگذارد:

```go
type SafeCounter struct {
	mu sync.RWMutex
	n  map[string]int
}

func (c *SafeCounter) Inc(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.n[key]++
}

func (c *SafeCounter) Get(key string) int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.n[key]
}
```

اینجا قفل داخل struct کنار داده‌ای است که محافظت می‌کند، و متدها را با pointer receiver نوشته‌ایم، چون قفل نباید کپی شود (بخش آخر مقاله).

## atomic و Once

برای یک عدد ساده، قفل کردن زیادی است. پکیج `sync/atomic` عملیاتی دارد که در یک قدم و بدون قطع‌شدن انجام می‌شوند، مثل `hits.Add(1)`. معمولاً از mutex سبک‌تر است. و **sync.Once** یک تابع را دقیقاً یک بار اجرا می‌کند، هر چند goroutine هم‌زمان صدایش بزنند؛ برای مقداردهی اولیه‌ی تنبل (lazy)، یعنی «اولین باری که لازم شد بساز»، مناسب است.

این قطعه‌ها را در همان برنامه‌ی ۱۰۰۰ goroutineی کنار هم گذاشتم، یکی با mutex، یکی با atomic، یکی با RWMutex روی یک map، و یک `once.Do`:

```go
var hits atomic.Int64
var once sync.Once

once.Do(func() { fmt.Println("init runs once") })
hits.Add(1)
```

```
init runs once
mutex counter: 1000
atomic counter: 1000
rwmutex map: 1000
```

۱۰۰۰ goroutine `once.Do` را صدا زدند و `init runs once` فقط یک بار چاپ شد. هر سه شمارنده دقیقاً ۱۰۰۰ شدند (باز هم زیر `-race`، و بی‌هشدار).

## select: انتظار روی چند channel

حالا سراغ سؤال دوم برویم، ولی اول به ابزاری نیاز داریم: چطور روی چند channel همزمان منتظر بمانیم؟ **select** مثل `switch` است، برای عملیات channel. صبر می‌کند تا یکی از caseها بتواند پیش برود و همان را اجرا می‌کند. با شاخه‌ی `default` هیچ‌وقت بلاک نمی‌شود، و با `time.After` می‌توان timeout گرفت.

برنامه‌ی نمونه سه `select` دارد. در اولی دو goroutine هستند که یکی بعد از ۵۰ و دیگری بعد از ۲۰۰ میلی‌ثانیه چیزی می‌فرستد؛ حلقه دو بار `select` می‌زند. دومی روی channelی که کسی نمی‌فرستد، با `default`. سومی روی channelی که هیچ‌وقت چیزی نمی‌گیرد، با timeout ۱۰۰ میلی‌ثانیه:

```go
for i := 0; i < 2; i++ {
	select {
	case m := <-fast:
		fmt.Println("got", m)
	case m := <-slow:
		fmt.Println("got", m)
	}
}

select {
case v := <-ch:
	fmt.Println("got", v)
default:
	fmt.Println("nothing ready")
}

select {
case v := <-never:
	fmt.Println("got", v)
case <-time.After(100 * time.Millisecond):
	fmt.Println("timeout")
}
```

```
got fast
got slow
nothing ready
timeout
```

دو خط اول مال حلقه‌اند: `select` اول روی هر کدام که زودتر آماده شد پیش رفت (`fast`) و بار دوم روی دیگری (`slow`). خط سوم: چون `ch` چیزی ندارد، `default` اجرا شد و بلاک نشد. خط آخر: `never` هیچ‌وقت چیزی نمی‌فرستد، پس بعد از ۱۰۰ میلی‌ثانیه case مربوط به `time.After` پیش رفت. اگر چند case هم‌زمان آماده باشند، Go یکی را تصادفی انتخاب می‌کند.

## context: لغو و deadline

حالا به سؤال دوم می‌رسیم: چطور به goroutine بگوییم متوقف شود؟ **{{< term "context" "context" >}}.Context** سیگنال لغو را بین goroutineها حمل می‌کند. از آن یک channel می‌گیرید، `ctx.Done()`، که وقتی context تمام شود بسته می‌شود، و `ctx.Err()` دلیل را می‌گوید. goroutine فقط باید در `select` به `ctx.Done()` گوش بدهد. context‌ها یک درخت می‌سازند: لغو یک context والد، فرزندانش را هم لغو می‌کند.

workerی که زیر نظر context کار می‌کند این‌طور است. هر ۲۰ میلی‌ثانیه یک tick چاپ می‌کند، و وقتی context لغو شد، دلیل را چاپ می‌کند و برمی‌گردد. یک `atomic.Bool` هم دارد تا بتوانیم از بیرون بپرسیم واقعاً متوقف شده یا نه:

```go
func worker(ctx context.Context, stopped *atomic.Bool) {
	defer stopped.Store(true)
	t := time.NewTicker(20 * time.Millisecond)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			fmt.Println("worker: stopping:", ctx.Err())
			return
		case <-t.C:
			fmt.Println("worker: tick")
		}
	}
}
```

`main` این worker را شروع می‌کند، ۷۰ میلی‌ثانیه صبر می‌کند، وضعیت را می‌پرسد، `cancel()` را صدا می‌زند، ۵۰ میلی‌ثانیه دیگر صبر می‌کند و دوباره می‌پرسد. بعد `Err` را بعد از `WithCancel` و `WithTimeout` و `WithDeadline` چاپ می‌کند:

```
worker: tick
worker: tick
worker: tick
stopped before cancel: false
worker: stopping: context canceled
stopped after cancel: true
Err after cancel: context canceled true
timeout Err: context deadline exceeded true
deadline Err: context deadline exceeded
```

سه tick در ۷۰ میلی‌ثانیه (تعداد دقیق به زمان‌بندی بستگی دارد)، و `stopped before cancel: false`: worker هنوز زنده است. بعد از `cancel()` پیام `worker: stopping: context canceled` آمد و `stopped after cancel: true`: واقعاً متوقف شد. سه خط آخر دلیل‌ها را نشان می‌دهند: `WithCancel` مقدار `context.Canceled` می‌دهد، و `WithTimeout` و `WithDeadline` هر دو `context.DeadlineExceeded` (`true` آخر خط یعنی با آن مقدار برابر است). بعد از ساختن هر کدام حتماً `defer cancel()` بزنید تا منابعش آزاد شود.

## fetch با timeout

حالا یک مثال واقع‌بینانه‌تر: تابعی که کاری کند را انجام می‌دهد (مثلاً یک درخواست شبکه) و باید در زمان مشخص تمام شود. کار کند را با `time.Sleep` شبیه‌سازی کرده‌ام، پس به شبکه نیازی نیست. طبق قرارداد، `ctx` **پارامتر اول** تابع است. کار در یک goroutine انجام می‌شود، و تابع با `select` یا منتظر نتیجه می‌ماند یا منتظر لغو:

```go
func fetch(ctx context.Context, id int) (string, error) {
	result := make(chan string, 1)
	go func() {
		time.Sleep(300 * time.Millisecond)
		result <- fmt.Sprintf("user-%d", id)
	}()
	select {
	case r := <-result:
		return r, nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}
```

یک بار آن را با timeout ‏۱۰۰ میلی‌ثانیه صدا می‌زنیم، که کار (۳۰۰ میلی‌ثانیه) به آن نمی‌رسد، و یک بار با ۱ ثانیه:

```
error: context deadline exceeded
is deadline exceeded: true
result: user-2 err: <nil>
```

بار اول timeout قبل از نتیجه رسید: `context deadline exceeded`. و `errors.Is(err, context.DeadlineExceeded)` برابر `true` است، پس می‌شود نوع خطا را تشخیص داد. بار دوم یک ثانیه فرصت بود و `user-2` رسید. چرا channel بافر ۱ دارد؟ فرض کنید بافر نداشت و تابع به‌خاطر timeout برگشته بود. goroutine کار بعد از ۳۰۰ میلی‌ثانیه می‌خواست نتیجه را بفرستد و هیچ‌کس گوش نمی‌داد، پس برای همیشه گیر می‌کرد (نشت). با بافر ۱، ارسال بدون گیرنده هم تمام می‌شود و goroutine می‌رود.

## استفاده‌ی نادرست از قفل و context

- **`sync.Mutex` را بعد از اولین استفاده کپی نکنید.** طبق مستندات `sync` نباید کپی شود. کپی قفل وضعیت جداگانه‌ی خودش را دارد، پس دو goroutine که هرکدام یک کپی را قفل می‌کنند مانع هم نمی‌شوند. struct را با اشاره‌گر پاس بدهید.
- **بخش بحرانی را کوتاه نگه دارید.** موقع I/O کند (شبکه، دیسک) قفل را نگه ندارید، چون بقیه‌ی goroutineها همه منتظر می‌مانند.
- **context را داخل struct ذخیره نکنید.** طبق مستندات `context`، آن را پارامتر اول تابع و با نام `ctx` بدهید.
- **`context.WithValue` برای داده‌ی وابسته به درخواست است**، مثل request ID. برای پارامتر اختیاری، config یا اتصال دیتابیس نیست، چون وابستگی را از دید خواننده پنهان می‌کند.
- **`time.After` در حلقه‌ی پرتکرار** در هر دور یک timer تازه می‌سازد. آن‌جا از `time.NewTimer` که می‌شود دوباره استفاده‌اش کرد، یا از context استفاده کنید.

## تمرین

۱. mutex شمارنده را با `atomic.Int64` عوض کنید و مطمئن شوید `-race` ساکت می‌ماند.
۲. کاری کنید `fetch` در ۵۰ میلی‌ثانیه جواب بدهد و ببینید timeout ‏۱۰۰ میلی‌ثانیه‌ای دیگر فعال نمی‌شود.
۳. workerی بنویسید که هر ۱۰۰ میلی‌ثانیه یک tick چاپ کند و با `context.WithTimeout` بعد از ۳۵۰ میلی‌ثانیه متوقف شود.

## قدم بعدی

«Generics در Go». بعد از همزمانی نوبت نوشتن یک کد برای چند نوع است: type parameter و constraint، و اینکه کِی واقعاً ارزش استفاده دارند.
