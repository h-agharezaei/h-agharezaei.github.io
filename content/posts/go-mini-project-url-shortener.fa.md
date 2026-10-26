+++
date = '2026-12-14T10:00:00+03:30'
draft = false
title = 'پروژه‌ی کوچک: URL shortener با Go'
description = 'یک URL shortener کوچک فقط با کتاب‌خانه‌ی استاندارد: مسیریابی net/http، store با RWMutex، کد تصادفی با crypto/rand، JSON، اعتبارسنجی و تست با httptest.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "project", "http"]
cover = { image = "/images/covers/go-mini-project-url-shortener.fa.png", alt = "پروژه‌ی کوچک: URL shortener با Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-cli-tool/) یک ابزار خط فرمان ساختیم. این آخرین مقاله‌ی سری Go Fundamentals است و به‌جای مبحث تازه، تکه‌ها را کنار هم می‌گذاریم: یک سرویس HTTP کوچک که URL را کوتاه می‌کند، فقط با کتاب‌خانه‌ی استاندارد. آدرس بلند را به‌صورت JSON با POST می‌فرستید، یک کد کوتاه می‌گیرید و با باز کردن `/<code>` به آدرس اصلی منتقل می‌شوید. همه‌چیز را با Go 1.26 روی macOS اجرا کرده‌ام و خروجی‌ها از اجرای واقعی کپی شده‌اند.

## ساختار

مثل [مقاله‌ی پکیج‌ها](/fa/posts/go-packages-modules/)، ماژول `example.com/shortener` سه بخش کوچک دارد: `store` (داده)، `server` (handlerهای HTTP) و `main.go` (سیم‌کشی و خاموش شدن). `server` به `store` وابسته است و برعکسش نه.

## Store

store یک map است که با `sync.RWMutex` محافظت می‌شود، همان چیزی که در [مقاله‌ی sync](/fa/posts/go-sync-select-context/) دیدیم. بیشتر درخواست‌ها فقط می‌خوانند؛ آن‌ها قفل خواندن می‌گیرند و می‌توانند همزمان اجرا شوند و فقط `Add` قفل انحصاری لازم دارد:

```go
type Store struct {
	mu    sync.RWMutex
	links map[string]string
}

func (s *Store) Get(code string) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()
	target, ok := s.links[code]
	if !ok {
		return "", ErrNotFound
	}
	return target, nil
}
```

کدها از `crypto/rand` می‌آیند و روی الفبای base62 نگاشت می‌شوند. باقی‌مانده‌ی تقسیم یک بایت بر ۶۲ کمی به‌نفع اولین کاراکترها اریب است؛ برای لینک کوتاه مهم نیست، اما برای یک secret مهم می‌شود. `Add` قفل را نگه می‌دارد و اگر (به‌ندرت) کد تکراری شد دوباره تلاش می‌کند:

```go
func newCode(n int) (string, error) {
	b := make([]byte, n)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	for i := range b {
		b[i] = alphabet[int(b[i])%len(alphabet)]
	}
	return string(b), nil
}
```

ذخیره‌سازی یک جفت `Save(path)` و `Load(path)` است که map را به JSON تبدیل می‌کنند؛ همان کارهای `encoding/json` و `os.WriteFile` که در [مقاله‌ی فایل و JSON](/fa/posts/go-file-io-json/) دیدیم. `Load` با `errors.Is(err, os.ErrNotExist)` نبودن فایل را یعنی «خالی شروع کن».

## Handlerها

از Go 1.22 به بعد `ServeMux` استاندارد متد و wildcard مسیر را می‌فهمد، پس به کتاب‌خانه‌ی router نیازی نیست:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /shorten", srv.shorten)
mux.HandleFunc("GET /{code}", srv.redirect)
```

handler مربوط به `shorten` JSON را decode می‌کند، اعتبارسنجی می‌کند، ذخیره می‌کند و `201 Created` برمی‌گرداند. اعتبارسنجی با `net/url` است: باید parse شود، scheme باید `http` یا `https` باشد و host داشته باشد.

```go
func validate(raw string) error {
	u, err := url.Parse(raw)
	if err != nil {
		return errors.New("url is not valid")
	}
	if u.Scheme != "http" && u.Scheme != "https" {
		return errors.New("url must start with http:// or https://")
	}
	if u.Host == "" {
		return errors.New("url must have a host")
	}
	return nil
}
```

handler ریدایرکت wildcard را با `r.PathValue("code")` می‌خواند و خطای sentinel مربوط به store را به status code تبدیل می‌کند:

```go
func (s *Server) redirect(w http.ResponseWriter, r *http.Request) {
	target, err := s.store.Get(r.PathValue("code"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "unknown code")
		return
	}
	// ...
	http.Redirect(w, r, target, http.StatusFound)
}
```

عمداً ۳۰۲ گذاشتم: مرورگرها ۳۰۱ را برای همیشه cache می‌کنند و بعداً نمی‌شود لینک را عوض کرد یا شمرد.

## خاموش شدن و ذخیره

`main` فایل `links.json` را load می‌کند، سرور را در یک goroutine بالا می‌آورد و با `signal.NotifyContext` منتظر Ctrl+C یا SIGTERM می‌ماند. بعد `srv.Shutdown` را با timeout پنج‌ثانیه‌ای صدا می‌زند تا درخواست‌های در حال انجام تمام شوند و تازه بعد فایل را ذخیره می‌کند. ترتیب مهم است: اگر اول ذخیره کنیم، لینکی که حین خاموش شدن ساخته شده از قلم می‌افتد.

## تست با httptest

با `httptest.NewRequest` و `httptest.NewRecorder` handler را مستقیم صدا می‌زنیم و پورتی لازم نیست. مثل [مقاله‌ی تست](/fa/posts/go-testing-basics/)، ورودی‌های نامعتبر یک جدول‌اند:

```go
func TestShortenInvalid(t *testing.T) {
	tests := []struct{ name, body string }{
		{"not json", `hello`},
		{"empty url", `{"url":""}`},
		{"no scheme", `{"url":"example.com"}`},
		{"bad scheme", `{"url":"ftp://example.com/file"}`},
		{"no host", `{"url":"https://"}`},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if rec := post(newTestServer(), tt.body); rec.Code != http.StatusBadRequest {
				t.Errorf("status = %d, want 400", rec.Code)
			}
		})
	}
}
```

تست‌های دیگر ساخت و ریدایرکت، کد ناشناخته، ۴۰۵ برای متد اشتباه، رفت‌وبرگشت save/load و ۵۰ درخواست POST همزمان را پوشش می‌دهند. اجرای معمولی و با race detector:

```text
$ go test -count=1 ./...
?   	example.com/shortener	[no test files]
ok  	example.com/shortener/server	0.289s
ok  	example.com/shortener/store	0.192s
$ go test -race -count=1 ./...
ok  	example.com/shortener/server	1.315s
ok  	example.com/shortener/store	1.297s
```

## اجرای واقعی

```text
$ curl -i -X POST localhost:8080/shorten -d '{"url":"https://go.dev/doc/"}'
HTTP/1.1 201 Created
Content-Type: application/json
Content-Length: 63

{"code":"LcUU3Dk","short_url":"http://localhost:8080/LcUU3Dk"}

$ curl -i localhost:8080/LcUU3Dk
HTTP/1.1 302 Found
Location: https://go.dev/doc/
Content-Length: 42

$ curl -i localhost:8080/zzzzzzz
HTTP/1.1 404 Not Found
{"error":"unknown code"}

$ curl -i -X POST localhost:8080/shorten -d '{"url":"example.com"}'
HTTP/1.1 400 Bad Request
{"error":"url must start with http:// or https://"}
```


(بعضی هدرها مثل `Date` را حذف کرده‌ام.) بعد از Ctrl+C لاگ نوشت `saved links.json, bye` و فایل شامل دو لینکی بود که ساخته بودم. با بالا آمدن دوباره‌ی سرور، کد قدیمی هنوز با ۳۰۲ ریدایرکت می‌کرد.

## چند نکته که باید حواستان باشد

- `GET /{code}` با `GET /shorten` هم می‌خواند، پس آن مسیر «کد ناشناخته» حساب می‌شود. سرویس واقعی چند کلمه را رزرو می‌کند.
- اندازه‌ی body درخواست را همیشه محدود کنید؛ اینجا `http.MaxBytesReader` آن را به ۱ مگابایت می‌رساند.
- فایل فقط هنگام خاموش شدن تمیز نوشته می‌شود. crash یا `kill -9` هر چه بعد از آخرین ذخیره بوده را از بین می‌برد؛ دیتابیس یا ذخیره‌ی دوره‌ای این را حل می‌کند.
- نگه داشتن قفل هنگام ساختن کد ساده است، ولی فقط در این مقیاس مناسب است.
- ریدایرکت به هر URL کاربر یعنی سرویس شما open redirect است؛ سرویس واقعی کنترل سوءاستفاده می‌خواهد.

## تمرین

۱. مسیر `GET /stats/{code}` را اضافه کنید که تعداد بازدیدهای یک کد را برگرداند (راهنما: یک شمارنده در store، زیر همان قفل).
۲. به `POST /shorten` اجازه دهید یک `"code"` دلخواه (alias) بگیرد و اگر قبلاً گرفته شده بود `409 Conflict` برگرداند.

## قدم بعدی

مبانی تمام شد. از این‌جا مقاله‌های Go به موضوع‌های backend می‌روند: اول graceful shutdown برای workerهای Go با NATS و بعد ساختار پروژه و clean architecture.
