+++
date = '2027-02-12T10:00:00+03:30'
draft = false
title = 'Rate limit و cache در Go'
description = 'Rate limit و cache در Go: محافظت از API با token bucket برای هر کلاینت و پاسخ 429، سپس سریع کردن GetOrder با cache، singleflight و سقف LRU.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "rate-limiting", "caching", "singleflight", "middleware"]
cover = { image = "/images/covers/go-rate-limiting-caching.fa.png", alt = "Rate limit و cache در Go", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/go-grpc-service/) به سرویس `orders` یک در ورودی gRPC داد. سرویسی که در دسترس است باید از مشتری‌هایش هم جان سالم به در ببرد: یک کلاینت پرسر و صدا نباید سهم بقیه را بخورد و یک سفارش پربازدید نباید هزار بار در ثانیه به دیتابیس برسد. این مقاله هر دو محافظ را به نسخه‌ی REST از [مقاله‌ی net/http](/fa/posts/go-http-api-stdlib/) اضافه می‌کند: یک middleware برای rate limit در زنجیره‌اش و یک cache جلوی `GetOrder`. کد، کپی همان نمونه است به‌علاوه‌ی متد `Pay` که برای invalidation لازم داریم.

> Go 1.26 روی macOS (arm64)، نسخه‌ی `golang.org/x/time` v0.16.0، `golang.org/x/sync` v0.24.0 و `golang-lru/v2` v2.0.7.

## Token bucket

**Token bucket** حداکثر `burst` توکن نگه می‌دارد و با سرعت `rate` توکن در ثانیه پر می‌شود. هر درخواست یک توکن برمی‌دارد؛ اگر توکنی نماند، درخواست رد یا به تأخیر می‌افتد. پس `rate` میانگین بلندمدت است و `burst` اندازه‌ی جهشی که تحمل می‌کنید. `rate.NewLimiter(2, 3)` را با متدهای زمان‌صریح `...N(time, n)` اجرا کردم:

```go
lim := rate.NewLimiter(2, 3)
lim.AllowN(t0, 1)                          // true x3, then false x2
lim.AllowN(t0.Add(500*time.Millisecond), 1) // true: one token refilled
r := lim.ReserveN(t0.Add(500*time.Millisecond), 1)
r.DelayFrom(t0.Add(500*time.Millisecond))   // 500ms
lim.Wait(ctx)                               // ctx has a 10ms deadline
```

```
Allow #1..#3: true   Allow #4, #5: false   Allow at t+0.5s: true
Reserve delay: 500ms
Wait: rate: Wait(n=1) would exceed context deadline
```

`Allow` همان لحظه جواب می‌دهد. `Reserve` همیشه توکن را برمی‌دارد و می‌گوید تا رسیدنش چقدر باید صبر کرد. `Wait` بلاک می‌شود و اگر deadline‌ی context زودتر از زمان لازم برسد، فوراً خطا می‌دهد. در API ما درخواست را صف نمی‌کنیم و رد می‌کنیم، پس `Allow` مناسب است.

## یک limiter برای هر کلاینت

یک bucket سراسری به یک کلاینت اجازه می‌دهد همه‌چیز را بخورد؛ پس برای هر کلید یک bucket در یک map با mutex نگه می‌داریم. کلید، هدر `X-API-Key` است و اگر نبود IP همتا (نه `X-Forwarded-For` که کلاینت می‌تواند جعلش کند). `Take` یک توکن خرج می‌کند و اگر خالی بود، رزرو را پس می‌دهد تا تأخیر را بفهمد:

```go
res := e.lim.ReserveN(now, 1)
if d := res.DelayFrom(now); d > 0 {
	res.CancelAt(now) // no token now: give the reservation back
	return false, 0, d
}
return true, int(e.lim.TokensAt(now)), 0
```

تله، خود map است. هیچ‌چیز کلیدی را پاک نمی‌کند و هر IP تازه برای همیشه می‌ماند. `cmd/leak` از ۱۰۰٬۰۰۰ آدرس متفاوت یک درخواست می‌فرستد:

```
entries after 100000 one-off clients: 100000
cleanup right away removed: 0 - still 100000
cleanup after 11 idle minutes removed: 99999 - still 1
```

هر entry زمان آخرین دیده‌شدن را دارد و `Cleanup(idle)` قدیمی‌تر از `idle` را حذف می‌کند (یک کلاینت برگشته بود، پس ماند). یک goroutine با ticker آن را صدا می‌زند:

```go
go limiter.Run(ctx, time.Minute, 10*time.Minute)
```

## Middleware

`RateLimit` آخر زنجیره می‌آید تا شناسه‌ی درخواست و access log درخواست‌های ردشده را هم پوشش دهند. رد کردن از مسیر خطا استفاده می‌کند: `errLimited` تازه در همان تابع `statusOf` به `429` تبدیل می‌شود.

```go
ok, remaining, retry := t.Take(clientKey(r))
w.Header().Set("X-RateLimit-Limit", strconv.Itoa(burst))
w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(remaining))
if !ok {
	w.Header().Set("Retry-After", strconv.Itoa(ratelimit.Seconds(retry)))
	writeErr(w, r, errLimited)
	return
}
```

`cmd/burst` یک سرور واقعی روی `httptest` با ساعتی که خودمان کنترل می‌کنیم (rate برابر ۱ در ثانیه، burst برابر ۵) و یک کلاینت HTTP واقعی را اجرا می‌کند:

```
  first 429: Retry-After=1 Limit=5 Remaining=0
burst of 20 at t+0s:  5 passed, 15 denied
10 more at t+3s:      3 passed, 7 denied
10 with an API key:   5 passed, 5 denied
```

دقیقاً ۵ درخواست، بعد از سه ثانیه‌ی ساختگی ۳ توکن تازه، و کلید دیگر bucket خودش را دارد. تست‌ها همین عددها را بدون sleep بررسی می‌کنند. limiter داخل همین process است: با N replica هر کدام bucketهای خودش را دارد و کلاینت تا N برابر سقف می‌گیرد. سقف مشترک به state مشترک نیاز دارد، مثلاً Redis (اینجا اجرا نشد).

## Cache برای GetOrder

`cache.TTL` یک map ژنریک با `RWMutex` (چند خواننده، یک نویسنده)، انقضا برای هر entry، ساعت تزریق‌پذیر و شمارنده‌ی اتمیک hit و miss است. `cached.Service` سرویس اصلی را wrap می‌کند: `Get` از cache رد می‌شود و `Pay` بعد از update موفق، entry را پاک می‌کند. ده GET، یک پرداخت، و یک GET دیگر:

```
after 10 GETs:        hits=9 misses=1
pay -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
get -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
after pay and 1 GET:  hits=9 misses=2
```

GET آخر عمداً miss شد و وضعیت تازه را برگرداند؛ بدون `Delete` تا پایان TTL همان `new` را می‌داد.

## Stampede و singleflight

وقتی کلید پربازدیدی منقضی می‌شود، همه‌ی درخواست‌های هم‌زمان با هم miss می‌کنند و همه به دیتابیس می‌روند. `cmd/stampede` پنجاه goroutine را روی یک کلید نبوده با loader ۵۰ میلی‌ثانیه‌ای می‌فرستد؛ یک بار با get/load/set ساده و یک بار با `singleflight`:

```
naive          50 requests -> 50 loader calls
singleflight   50 requests -> 1 loader calls
```

`GetOrLoad` تابع loader را داخل `singleflight.Group.Do` اجرا می‌کند: فراخوانی‌های هم‌کلید منتظر اولی می‌مانند و نتیجه‌اش را مشترک می‌گیرند. callerها با یک sleep کوتاهِ واقعی هم‌زمان می‌شوند، پس تست کاملاً قطعی نیست؛ ۲۰ اجرا زیر `-race` گذشت.

## سقف اندازه

TTL ما فقط وقتی entry منقضی را بخوانیم آن را دور می‌اندازد، پس می‌تواند بزرگ شود. برای سقف قطعی از `hashicorp/golang-lru/v2` استفاده کردم که کم‌استفاده‌ترین (least recently used) را بیرون می‌اندازد. ظرفیت ۳، بعد از درج `a b c` و خواندن `a`:

```
add d:
  evicted b=2
add e:
  evicted c=3
keys oldest to newest: [a d e] len: 3
```

`a` ماند چون خواندنش آن را تازه کرد.

## چند نکته

- cache یعنی معاوضه با تازگی. TTL بلندتر یعنی load کمتر و داده‌ی کهنه‌ی بیشتر؛ روی نوشتن‌هایی که خودتان کنترل می‌کنید invalidate کنید و برای تغییرهای دیگر TTL را بدترین حالت بدانید.
- invalidation می‌تواند با load کندی که زودتر شروع شده رقابت کند و بعد از `Delete` مقدار قدیمی را برگرداند. این را بازتولید نکردم؛ TTL را کوتاه نگه دارید تا شبکه‌ی ایمنی باشد.
- با `singleflight` همه context و خطای اولین فراخواننده را شریک می‌شوند. اگر او لغو شود، بقیه هم می‌بینند.
- rate limit بر پایه‌ی IP کلاینت‌های پشت یک NAT را تنبیه می‌کند؛ جایی که API key دارید از آن استفاده کنید.

## قدم بعدی

مقاله‌ی بعد: پروفایل کردن Go با pprof، تا به‌جای حدس زدن ببینیم زمان و حافظه واقعاً کجا می‌روند.
