+++
date = '2027-02-20T10:00:00+03:30'
draft = false
title = 'پروفایلینگ با pprof در Go'
description = 'نقطه‌ی داغ یک سرویس Go را با pprof پیدا کنید: پروفایل CPU، heap و goroutine روی سرویس زنده، رفع مشکل با benchstat و allocs/op و پروفایل داخل تست.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "pprof", "profiling", "performance", "benchmark"]
cover = { image = "/images/covers/go-profiling-pprof.fa.png", alt = "پروفایلینگ با pprof در Go", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/go-rate-limiting-caching/) درباره‌ی rate limiting و caching بود. حالا سؤال دیگری داریم: سرویس کند است، دقیقاً چه چیزی را عوض کنیم؟ حدس زدن راه مطمئنی برای بهینه کردن خط اشتباه است. **pprof** ابزار **profiler** خودِ Go است و این‌جا روی یک سرویس کوچک `net/http` استفاده‌اش می‌کنیم که عمداً کندش کرده‌ام. مقاله روی [benchmark](/fa/posts/go-testing-basics/) و [مبانی حافظه](/fa/posts/go-pointers-memory/) از مقاله‌های قبل بنا شده است.

> Go 1.26 روی macOS (arm64). این ماشین مشترک است و load average در زمان اجراها بین ۳ و ۱۰ بود؛ پس **ns/op نشان نمی‌دهم** و ادعای نسبت سرعت ندارم. به allocs/op، B/op و سهم هر خط در پروفایل تکیه می‌کنم که به بار ماشین بستگی ندارند.

## سرویس کند

یک handler سه اشتباه کلاسیک دارد: در هر درخواست یک **regexp** کامپایل می‌کند، رشته را با `+=` در حلقه می‌سازد و ۵۰۰ struct را JSON می‌کند.

```go
func Handler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	re := regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
	if !re.MatchString(q) { http.Error(w, "bad q", 400); return }
	s := ""
	for i := 0; i < 200; i++ {
		s += fmt.Sprintf("%s-%d,", q, i)
	}
	body, _ := json.Marshal(catalog[:500])
	w.Header().Set("X-Len", fmt.Sprint(len(s)))
	w.Write(body)
}
```

pprof روی یک **پورت admin جدا** و فقط روی loopback بالا می‌آید:

```go
admin := http.NewServeMux()
admin.HandleFunc("/debug/pprof/", pprof.Index)
admin.HandleFunc("/debug/pprof/profile", pprof.Profile)
admin.HandleFunc("/debug/pprof/trace", pprof.Trace)
log.Fatal(http.ListenAndServe("127.0.0.1:6060", admin))
```

import کردنِ `net/http/pprof` به‌خاطر اثر جانبی‌اش handlerها را روی `http.DefaultServeMux` ثبت می‌کند. اگر سرور عمومی‌تان از mux پیش‌فرض استفاده کند، محتوای heap و stack گوروتین‌ها را به اینترنت داده‌اید. handlerها را مثل بالا روی یک mux خصوصی ثبت کنید و هرگز این پورت را عمومی نکنید.

load generator یک برنامه‌ی کوچک Go است: N گوروتین با یک شمارنده‌ی atomic درخواست می‌فرستند تا به تعداد ثابتی برسند.

```
$ ./load -c 8 -n 30000
requests=30000 ok=30000
```

## پروفایل CPU

دستور `curl 'http://127.0.0.1:6060/debug/pprof/profile?seconds=12'` را هم‌زمان با بار اجرا کردم و فقط خروجی متنی دیدم (graphviz نصب نیست):

```
$ go tool pprof -top -nodecount=4 svc slow.prof
Duration: 12.12s, Total samples = 15.14s (124.90%)
      flat  flat%   sum%        cum   cum%
    2650ms 17.50% 17.50%     2650ms 17.50%  runtime.usleep
    2230ms 14.73% 32.23%     2230ms 14.73%  syscall.rawsyscalln
    1400ms  9.25% 41.48%     1400ms  9.25%  runtime.madvise
    1140ms  7.53% 49.01%     1140ms  7.53%  runtime.pthread_kill
```

نمای flat بیشتر runtime و syscall است، یعنی نویز GC و scheduler که خودش اشاره‌ای به allocation است. ابزار مفید `-list` است که هزینه‌ی هر خطِ تابع خودتان را نشان می‌دهد:

```
$ go tool pprof -list='app.Handler' svc slow.prof
         .      680ms     31:	re := regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
         .      1.26s     39:		s += fmt.Sprintf("%s-%d,", q, i)
         .      2.03s     42:	body, _ := json.Marshal(catalog[:500])
         .      1.55s     44:	w.Write(body)
```

`app.Handler` در مجموع ۵٫۶۰ ثانیه است، یعنی ۳۶٫۹۹٪ همه‌ی sampleها. هر سه مظنون این‌جا هستند. (`w.Write` همان I/O سوکت است.)

## رفع مشکل و مقایسه

```go
var validQ = regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
var catalogJSON, _ = json.Marshal(catalog[:500]) // catalog is static
// in the handler:
var sb strings.Builder
for i := 0; i < 200; i++ { fmt.Fprintf(&sb, "%s-%d,", q, i) }
```

cache کردن JSON فقط چون catalog هرگز عوض نمی‌شود درست است؛ در حالت عادی باید داخل یک buffer از pool encode کرد. دستور `go test -bench . -benchmem -count 10` را قبل و بعد اجرا کردم و با `benchstat` (از `golang.org/x/perf/cmd/benchstat`، نصب‌شده در یک GOBIN خصوصی) مقایسه کردم. به‌خاطر بار ماشین، ستون زمان را فیلتر کردم:

```
Handler-8   249.80Ki ± 0%   41.81Ki ± 0%  -83.26% (p=0.000 n=10)   B/op
Handler-8   998.0 ± 0%      226.0 ± 0%    -77.35% (p=0.000 n=10)   allocs/op
```

با همان بار ۳۰۰۰۰ درخواستی روی سرویس اصلاح‌شده، مجموع CPU sampleها ۲٫۹۴ ثانیه شد، به‌جای ۱۵٫۱۴. حالا بزرگ‌ترین خط در `-list` همان `w.Write` با ۱٫۱۷ ثانیه است، یعنی باقی‌مانده بیشتر شبکه است. به‌خاطر بار ماشین نسبت سرعت نمی‌دهم.

## پروفایل heap و goroutine

پروفایل heap دو نگاه به یک داده دارد. handler به نام `/cache` در هر درخواست ۱۶ کیلوبایت allocate می‌کند و هر شانزدهمین buffer را نگه می‌دارد. بعد از ۲۰۰۰۰ درخواست:

```
$ go tool pprof -sample_index=inuse_space -top -nodecount=1 svc heap.prof
16121.29kB 83.91%  main.cache
$ go tool pprof -sample_index=alloc_space -top -nodecount=1 svc heap.prof
  294.46MB 89.10%  main.cache
```

`inuse_space` می‌گوید «همین الان چه چیزی نگه داشته شده»، یعنی نشتی و نگه‌داری بی‌جا را پیدا می‌کند. `alloc_space` می‌گوید «در کل چقدر allocate شده»، یعنی فشار روی GC را حتی وقتی چیزی نگه داشته نشده نشان می‌دهد. هر دو تخمین‌های نمونه‌برداری‌شده‌اند.

برای goroutine، handler به نام `/leak` گوروتینی می‌سازد که روی channelی منتظر می‌ماند که کسی در آن نمی‌نویسد. بعد از ۵۰۰ درخواست، `?debug=1` متنی می‌دهد که در ترمینال خوانا است:

```
$ curl 'http://127.0.0.1:6060/debug/pprof/goroutine?debug=1'
goroutine profile: total 504
500 @ 0x102341aac ...
#	0x102508de3	main.leak.func1+0x23	.../cmd/svc/main.go:52
```

۵۰۰ گوروتین گیرکرده روی یک خط، نشانه‌ی کلاسیک نشتی است.

## پروفایل در تست و tracing

```
go test ./app -bench . -benchmem -cpuprofile cpu.prof -memprofile mem.prof
go tool pprof -sample_index=alloc_space -top app.test mem.prof
```

همان `-list` این‌جا هم کار می‌کند و روی کد کند، برای کل اجرا ۱٫۸۳ گیگابایت allocation روی خط `regexp.MustCompile` و ۱۱٫۰۲ گیگابایت روی خط `+=` نشان داد. دستور دوم به باینری `app.test` نیاز دارد که اجرای تست باقی می‌گذارد. `/debug/pprof/trace` و `go tool trace` با `runtime/trace` یک خط زمانی از گوروتین‌ها، GC و scheduler می‌دهند و به سؤال‌هایی مثل «چرا هیچ‌چیز اجرا نمی‌شود» جواب می‌دهند که نمونه‌برداری نمی‌تواند. من فقط بررسی کردم که endpoint یک trace برمی‌گرداند؛ رابط کاربری را باز نکردم.

## چند نکته

- پروفایل CPU نمونه‌برداری است (حدود ۱۰۰ بار در ثانیه)، پس سربار دارد و رویدادهای کوتاه را از دست می‌دهد. روی بار واقعی پروفایل بگیرید، نه روی پروسه‌ی بیکار.
- قبل و بعد را با بار یکسان پروفایل کنید و هر بار فقط یک چیز را عوض کنید.
- مجموع sampleها می‌تواند از زمان واقعی بیشتر باشد (بالا ۱۲۴٫۹۰٪) چون چند CPU هم‌زمان کار می‌کنند.
- پورت pprof را هرگز عمومی نکنید؛ روی loopback ببندید یا محافظتش کنید.
- benchmark با `httptest.NewRecorder` allocationهای خودِ recorder را هم شامل می‌شود.

## قدم بعدی

در مقاله‌ی بعد درباره‌ی Docker، CI و دیپلوی یک سرویس Go حرف می‌زنیم.
