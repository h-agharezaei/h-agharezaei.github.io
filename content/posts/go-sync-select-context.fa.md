+++
date = '2026-11-26T10:00:00+03:30'
draft = false
title = 'sync، select و context در Go'
description = 'حافظه‌ی مشترک را با Mutex و atomic و Once ایمن کنید، با select روی چند channel منتظر بمانید و با context کار را لغو کنید؛ با خروجی واقعی race detector.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "context", "sync", "select"]
cover = { image = "/images/covers/go-sync-select-context.fa.png", alt = "sync، select و context در Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-goroutines-channels/) goroutine راه انداختیم و از طریق channel با آن‌ها حرف زدیم. دو سؤال باز ماند: وقتی goroutineها مجبورند حافظه‌ی مشترک داشته باشند چه کنیم، و چطور به یک goroutine بگوییم متوقف شود؟ این مقاله جواب هر دو را با پکیج `sync`، دستور `select` و `context` می‌دهد.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام.

## یک race و رفعش با mutex

شمارنده‌ی خراب کلاسیک: ۱۰۰۰ goroutine که یک متغیر را زیاد می‌کنند.

```go
counter := 0
for i := 0; i < 1000; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		counter++ // بدون محافظ
	}()
}
```

اجراهای معمولی در دو بار امتحان `counter: 850` و `counter: 984` چاپ کردند؛ هیچ‌وقت عدد قابل اعتمادِ ۱۰۰۰ نبود. **race detector** (با `go run -race`) مشکل را اسم می‌برد؛ این گزارش کوتاه‌شده است:

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

**sync.Mutex** در هر لحظه فقط یک goroutine را به بخش بحرانی راه می‌دهد:

```go
var mu sync.Mutex
mu.Lock()
counter++
mu.Unlock()
```

با قفل، `-race` ساکت است و `mutex counter: 1000` می‌گیریم. وقتی خواندن خیلی بیشتر از نوشتن است، **sync.RWMutex** اجازه می‌دهد چند خواننده (`RLock`) یا یک نویسنده (`Lock`) داشته باشیم. در متدها قفل را با `defer` آزاد کنید تا یک return زودهنگام آن را قفل نگذارد:

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

## atomic و Once

برای یک عدد ساده، `sync/atomic` سبک‌تر از mutex است. **sync.Once** یک تابع را دقیقاً یک بار اجرا می‌کند، هر چند goroutine صدایش بزنند؛ برای مقداردهی اولیه‌ی تنبل مناسب است:

```go
var hits atomic.Int64
var once sync.Once

once.Do(func() { fmt.Println("init runs once") })
hits.Add(1)
```

اجرای هر سه با ۱۰۰۰ goroutine (باز هم زیر `-race`):

```
init runs once
mutex counter: 1000
atomic counter: 1000
rwmutex map: 1000
```

## select: انتظار روی چند channel

**select** مثل `switch` برای عملیات channel است: صبر می‌کند تا یکی از caseها بتواند پیش برود. با `default` هیچ‌وقت block نمی‌شود و با `time.After` timeout می‌گیریم.

```go
select {
case m := <-fast:
	fmt.Println("got", m)
case m := <-slow:
	fmt.Println("got", m)
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

اگر چند case همزمان آماده باشند، Go یکی را تصادفی انتخاب می‌کند.

## context: لغو و deadline

یک **context.Context** سیگنال لغو را بین goroutineها حمل می‌کند. `ctx.Done()` channelی است که با پایان context بسته می‌شود و `ctx.Err()` دلیلش را می‌گوید. workerی که با لغو متوقف می‌شود، و بررسی اینکه واقعاً متوقف شده:

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

سه خط آخر مربوط به `WithCancel` (مقدار `context.Canceled`) و `WithTimeout` و `WithDeadline` (هر دو `context.DeadlineExceeded`) است. بعد از ساختن هر کدام حتماً `defer cancel()` بزنید تا منابعش آزاد شود.

## fetch با timeout

کار کند را با `time.Sleep` شبیه‌سازی کرده‌ام، پس به شبکه نیازی نیست. طبق قرارداد، `ctx` **پارامتر اول** است:

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

یک بار با timeout ‏۱۰۰ms و یک بار با ۱ ثانیه:

```
error: context deadline exceeded
is deadline exceeded: true
result: user-2 err: <nil>
```

channel بافر ۱ دارد تا goroutine رهاشده بتواند ارسالش را تمام کند و leak نشود.

## چند نکته‌ی احتیاط

- `sync.Mutex` را بعد از اولین استفاده کپی نکنید؛ struct را با اشاره‌گر پاس بدهید.
- بخش بحرانی را کوتاه نگه دارید و موقع I/O کند قفل را نگه ندارید.
- context را داخل struct ذخیره نکنید؛ آن را پارامتر اول و با نام `ctx` بدهید.
- `context.WithValue` برای داده‌ی وابسته به درخواست مثل request ID است، نه برای پارامتر اختیاری، config یا اتصال دیتابیس.
- `time.After` در حلقه‌ی پرتکرار در هر دور یک timer می‌سازد؛ آنجا از `time.NewTimer` یا context استفاده کنید.

## تمرین

۱. mutex شمارنده را با `atomic.Int64` عوض کنید و مطمئن شوید `-race` ساکت می‌ماند.
۲. کاری کنید `fetch` در ۵۰ms جواب بدهد و ببینید timeout ‏۱۰۰ms دیگر فعال نمی‌شود.
۳. workerی بنویسید که هر ۱۰۰ms یک tick چاپ کند و با `context.WithTimeout` بعد از ۳۵۰ms متوقف شود.

## قدم بعدی

در مقاله‌ی بعد سراغ generics در Go می‌رویم: type parameter، constraint و اینکه کِی ارزش استفاده دارند.
