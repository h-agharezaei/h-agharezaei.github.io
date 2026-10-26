+++
date = '2027-01-03T10:00:00+03:30'
draft = false
title = 'ساخت API با net/http در Go'
description = 'ساخت API با net/http در Go بدون فریم‌ورک: ServeMux، middleware، خواندن امن JSON، timeout‌های سرور، graceful shutdown و تست handler‌ها با httptest.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "http", "api", "net-http", "middleware"]
cover = { image = "/images/covers/go-http-api-stdlib.fa.png", alt = "ساخت API با net/http در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-config-logging-errors/) سرویس `orders` یک `Config` تایپ‌دار از متغیرهای محیطی گرفت، `slog` با handler متنی و JSON، یک شناسه‌ی درخواست که در context می‌ماند، و یک تابع (`statusOf`) که خطاها را به status کد HTTP تبدیل می‌کند. خود سرور هنوز ساده بود: یک read timeout، بدون محافظ panic، بدون سقف بدنه و بدون خاموش‌شدن مرتب. حالا لایه‌ی HTTP را رویش می‌سازیم، فقط با کتاب‌خانه‌ی استاندارد. از Go 1.22 router متد و wildcard را می‌فهمد، پس برای API کوچک سراغ فریم‌ورک نمی‌روم. در [پروژه‌ی URL shortener](/fa/posts/go-mini-project-url-shortener/) هم از `net/http` استفاده کرده بودیم؛ اینجا **middleware**، خواندن امن درخواست، timeout و تست را اضافه می‌کنیم.

> همه‌ی مثال‌ها با Go 1.26 روی macOS (arm64) و فقط با کتاب‌خانه‌ی استاندارد اجرا شده‌اند. نمونه همان ماژول مقاله‌ی قبل است. در لاگ‌ها فیلد `time=` حذف شده است.

## الگوهای ServeMux

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /orders", /* decode, validate, create */)
mux.HandleFunc("GET /orders/{id}", func(w http.ResponseWriter, r *http.Request) {
	o, err := orders.Get(r.Context(), r.PathValue("id"))
	// ...
})
```

متد جزو الگو است و `{id}` یک **wildcard** است که با `r.PathValue` خوانده می‌شود. درخواست‌های اشتباه را هم خود mux جواب می‌دهد:

```
$ curl -si -X DELETE localhost:8095/orders/1
HTTP/1.1 405 Method Not Allowed
Allow: GET, HEAD
Content-Type: text/plain; charset=utf-8

$ curl -si localhost:8095/nope
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8
```

مسیر شناخته‌شده با متد اشتباه `405` همراه با هدر `Allow` می‌دهد و مسیر ناشناخته `404`. بدنه‌ی هر دو متن ساده است، نه JSON خودمان.

## Middleware

middleware یعنی `func(http.Handler) http.Handler`: handler بعدی را می‌گیرد و یکی تازه برمی‌گرداند. این تابع آن‌ها را ترکیب می‌کند:

```go
func Chain(h http.Handler, mws ...Middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

return Chain(mux, RequestID, AccessLog, Recover)
```

اولی که نوشته شود بیرونی‌ترین است. `RequestID` همان کد مقاله‌ی قبل است که به یک middleware رفته: شناسه را با `logging.WithRequestID` در context می‌گذارد و هدر `X-Request-ID` را ست می‌کند. چون handler مربوط به `slog` به هر رکوردِ دارای شناسه `request_id` اضافه می‌کند، `AccessLog` نیازی به شناسه ندارد؛ فقط `ResponseWriter` را wrap می‌کند تا status را یادداشت کند و بعد از handler لاگ بنویسد. `Recover` تازه است و به‌جای نوشتن پاسخ جدا، از همان مسیر خطا استفاده می‌کند:

```go
defer func() {
	if v := recover(); v != nil {
		writeErr(w, r, fmt.Errorf("panic: %v", v))
	}
}()
next.ServeHTTP(w, r)
```

`writeErr` تابع مقاله‌ی قبل است: خطای ناشناخته می‌شود `500` با متن ثابت و جزئیات فقط به لاگ می‌رود. مسیر `/boom` فقط برای نمونه panic می‌کند:

```
$ curl -si localhost:8095/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: 2d45c299

{"error":"internal error"}

level=ERROR msg="request failed" method=GET path=/boom status=500 error="panic: something broke" request_id=2d45c299
level=INFO msg=request method=GET path=/boom status=500 dur=96.25µs request_id=2d45c299
```

بدون آن، `net/http` panic را می‌گیرد اما فقط اتصال را قطع می‌کند؛ curl با exit code 52 («empty reply») تمام می‌شود (`cmd/barepanic`).

## خواندن امن JSON

```go
func decode(w http.ResponseWriter, r *http.Request, dst any) error {
	r.Body = http.MaxBytesReader(w, r.Body, maxBody) // 1 MiB
	dec := json.NewDecoder(r.Body)
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		var tooBig *http.MaxBytesError
		if errors.As(err, &tooBig) {
			return fmt.Errorf("%w: %v", errTooBig, err)
		}
		return fmt.Errorf("%w: %v", errBadJSON, err)
	}
	return nil
}
```

`MaxBytesReader` بدنه را محدود می‌کند و `DisallowUnknownFields` غلط تایپی مثل `"vip":true` را به‌جای نادیده‌گرفتن بی‌صدا، خطا می‌کند. هر دو خطا یک sentinel را wrap می‌کنند، پس `statusOf` یک حالت تازه می‌گیرد: `errTooBig` می‌شود `413`. برای `422` فیلد خطادار را از `ValidationError` موجود به پاسخ اضافه کردم:

```
$ curl -si -X POST localhost:8095/orders -d '{"customer":"a","cents":1,"vip":true}'
HTTP/1.1 400 Bad Request
{"error":"bad json"}

$ curl -si -X POST localhost:8095/orders -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"invalid order: customer is required","fields":{"customer":"is required"}}
```

دلیل دقیق (`unknown field "vip"`) در لاگ می‌ماند. بدنه‌ی ۲ مگابایتی `413` گرفت. domain فقط اولین قانون شکسته را گزارش می‌کند، پس تا `customer` درست نشود از `cents` حرفی نیست.

## Timeout‌های سرور

`http.ListenAndServe` یک `http.Server` با مقدار صفر استفاده می‌کند و صفر یعنی بدون محدودیت. کلاینت می‌تواند هدرها را بایت‌به‌بایت بفرستد و یک goroutine و یک file descriptor را تا ابد نگه دارد؛ این همان حمله‌ی **slowloris** است. دفعه‌ی قبل `Config` فقط یک `ReadTimeout` داشت که به‌جای `ReadHeaderTimeout` می‌رفت. حالا هر چهار مورد را دارد، با پیش‌فرض، تابعی که صفر را رد می‌کند و یک بررسی متقابل:

```go
positive := func(key, def string) time.Duration {
	d, err := time.ParseDuration(str(key, def))
	if err == nil && d <= 0 {
		err = errors.New("must be positive")
	}
	if err != nil {
		fail(key, err)
	}
	return d
}
c.ReadHeaderTimeout = positive("ORDERS_READ_HEADER_TIMEOUT", "2s")
c.ReadTimeout = positive("ORDERS_READ_TIMEOUT", "5s")
c.WriteTimeout = positive("ORDERS_WRITE_TIMEOUT", "10s")
c.IdleTimeout = positive("ORDERS_IDLE_TIMEOUT", "60s")
if c.ReadHeaderTimeout > c.ReadTimeout {
	fail("ORDERS_READ_HEADER_TIMEOUT", errors.New("must not exceed ORDERS_READ_TIMEOUT"))
}
```

`main` فقط آن‌ها را در سرور می‌گذارد:

```go
srv := &http.Server{
	Addr:              cfg.Addr,
	Handler:           transport.NewHandler(svc),
	ReadHeaderTimeout: cfg.ReadHeaderTimeout,
	ReadTimeout:       cfg.ReadTimeout,
	WriteTimeout:      cfg.WriteTimeout,
	IdleTimeout:       cfg.IdleTimeout,
}
```

با `ORDERS_WRITE_TIMEOUT=0s ORDERS_READ_HEADER_TIMEOUT=9s` راه‌اندازی هر دو مشکل را چاپ کرد و با کد ۲ خارج شد. `cmd/slowheader` خط درخواست و هدر `Host` را می‌فرستد و بعد هر ۵۰۰ میلی‌ثانیه یک بایت اضافه می‌فرستد، بدون تمام‌کردن هدرها. آن را روی همین سرور (پیش‌فرض‌ها) و روی سرور دومی با `http.ListenAndServe` ساده زدم:

```
$ slowheader localhost:8095
server reacted after 2.0s: read 103 bytes, err=<nil>
"HTTP/1.1 400 Bad Request\r\n...\r\n\r\n400 Bad Request"

$ slowheader localhost:8081
still connected after 8.0s
```

با `ReadHeaderTimeout` دو ثانیه‌ای، سرور جواب داد و اتصال را بست. سرور با مقدار صفر وقتی کلاینت من در ثانیه‌ی ۸ منصرف شد هنوز منتظر بود.

## Graceful shutdown

```go
ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
defer stop()
go func() {
	if err := srv.ListenAndServe(); !errors.Is(err, http.ErrServerClosed) {
		slog.Error("server failed", "err", err)
		os.Exit(1)
	}
}()
<-ctx.Done()
slog.Info("shutting down")
shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
defer cancel()
srv.Shutdown(shutdownCtx)
```

`Shutdown` پذیرش اتصال تازه را قطع می‌کند و تا سقف deadline منتظر درخواست‌های در حال انجام می‌ماند. `ListenAndServe` بلافاصله `http.ErrServerClosed` برمی‌گرداند و شکست نیست. worker‌ها در [graceful shutdown با worker‌ها](/fa/posts/go-graceful-shutdown-workers/) آمده‌اند. بعد از `SIGTERM` نمونه `shutting down` و `stopped` را لاگ کرد؛ درخواستی در جریان نبود.

## تست handler‌ها

`httptest.NewServer` زنجیره‌ی واقعی را روی پورتی تصادفی بالا می‌آورد:

```go
svc := service.New(memory.New(), quiet, 1_000_000)
srv := httptest.NewServer(transport.NewHandler(svc))
defer srv.Close()
resp, _ := http.Post(srv.URL+"/orders", "application/json", strings.NewReader(body))
```

یک تست جدولی هشت حالت خطا (فیلد ناشناخته، اعتبارسنجی، بدنه‌ی بزرگ، پیدا نشدن، متد اشتباه، مسیر ناشناخته، خطای ذخیره‌سازی، panic) را می‌فرستد و status code‌ها را چک می‌کند. تست config هم timeout‌ها را پوشش می‌دهد.

```
$ go test -race ./...
ok  	example.com/orders/internal/config
ok  	example.com/orders/internal/service
ok  	example.com/orders/internal/transport/http
```

## چند نکته که باید حواستان باشد

- `404` و `405` خودِ mux متن ساده‌اند. شناسه و خط لاگ می‌گیرند، اما اگر کلاینت‌ها JSON انتظار دارند، wrap‌شان کنید.
- `WriteTimeout` handler‌های کند را هم شامل می‌شود: دانلود یا stream طولانی به مقدار بزرگ‌تر یا `http.ResponseController` نیاز دارد.
- خطای `MaxBytesReader` را چک کنید، وگرنه بدنه‌ی بزرگ شبیه یک خطای عادی decode دیده می‌شود.
- ترتیب middleware مهم است: `Recover` داخل `AccessLog` است تا `500` هم لاگ شود.
- wrapper ثبت status، interface‌های اختیاری مثل `http.Flusher` را پنهان می‌کند؛ متد `Unwrap() http.ResponseWriter` آن، `http.ResponseController` را سرپا نگه می‌دارد.

## قدم بعدی

مقاله‌ی بعد: Postgres با pgx و sqlc در Go، جایی که store در حافظه جایش را به یک دیتابیس واقعی می‌دهد.
