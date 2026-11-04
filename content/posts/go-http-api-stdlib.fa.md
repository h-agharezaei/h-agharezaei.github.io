+++
date = '2027-01-03T10:00:00+03:30'
draft = false
title = 'ساخت API با net/http در Go'
description = 'ساخت API با net/http در Go بدون فریم‌ورک: ServeMux، middleware، خواندن امن JSON، timeout‌های سرور، graceful shutdown و تست handler‌ها با httptest.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "http", "api", "net-http", "middleware"]
cover = { image = "/images/covers/go-http-api-stdlib.fa.png", alt = "ساخت API با net/http در Go", hiddenInSingle = true }
+++

کوتاه‌ترین راه برای بالا آوردن سرور وب در Go یک خط است: `http.ListenAndServe(":8080", handler)`. کار می‌کند و مشکل هم همین است، چون تصمیم‌هایی را پنهان می‌کند که هنوز نگرفته‌اید. این خط از سروری استفاده می‌کند که همه‌ی تنظیماتش صفر است و برای timeout، صفر یعنی «بدون محدودیت». کلاینتی که هدرهای درخواست را بایت‌به‌بایت بفرستد می‌تواند یک اتصال و goroutineِ سرویس‌دهنده‌اش را هر قدر بخواهد باز نگه دارد. باگی که داخل handler panic کند هم درست گزارش نمی‌شود. و deployای که پروسه را دوباره راه بیندازد می‌تواند درخواست‌ها را نصفه قطع کند.

بعد از [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/)، سرور `orders` هنوز همین‌قدر حداقلی است: یک read timeout، بدون محافظت در برابر panic، بدون سقف برای بدنه‌ی درخواست و بدون shutdown. این نوشته این‌ها را یکی‌یکی درست می‌کند. از Go 1.22 به بعد router استاندارد متد HTTP و wildcard مسیر را می‌فهمد، برای همین برای یک API کوچک سراغ فریم‌ورک وب نمی‌روم. در [URL shortener](/fa/posts/go-mini-project-url-shortener/) هم از `net/http` استفاده کردیم؛ اینجا middleware، خواندن امن JSON، timeout و تست را اضافه می‌کنیم، فقط با کتاب‌خانه‌ی استاندارد.

> همه‌چیز دوباره با Go 1.27 روی macOS (arm64) و فقط با کتاب‌خانه‌ی استاندارد اجرا شده است. دمو همان ماژول نوشته‌ی قبل است که تکامل پیدا کرده. در لاگ‌های زیر فیلد `time=` حذف شده. شناسه‌ی درخواست و مدت‌ها از اجرا به اجرا فرق می‌کنند؛ از پورت‌های محلی آزادِ تصادفی استفاده کردم.

## الگوهای ServeMux

اول ببینیم یک درخواست چطور handler‌اش را پیدا می‌کند. **handler** تابعی است که درخواست را می‌گیرد و پاسخ را می‌نویسد. router (در `net/http` همان `ServeMux`) انتخاب می‌کند برای کدام درخواست کدام handler اجرا شود. ثبت مسیرها این‌طور است:

```go
mux := http.NewServeMux()
mux.HandleFunc("POST /orders", /* decode, validate, create */)
mux.HandleFunc("GET /orders/{id}", func(w http.ResponseWriter, r *http.Request) {
	o, err := orders.Get(r.Context(), r.PathValue("id"))
	// ...
})
```

متد HTTP جزو الگوست و `{id}` یک wildcard است که مقدارش را با `r.PathValue` می‌خوانید. اثر جانبی خوبش این است که mux خودش به درخواست‌های غلط جواب می‌دهد. یک متد غلط روی مسیر موجود و یک مسیر ناموجود را امتحان کردم (هدرها به موارد مهم خلاصه شده‌اند):

```
$ curl -si -X DELETE localhost:8095/orders/1
HTTP/1.1 405 Method Not Allowed
Allow: GET, HEAD
Content-Type: text/plain; charset=utf-8

$ curl -si localhost:8095/nope
HTTP/1.1 404 Not Found
Content-Type: text/plain; charset=utf-8
```

مسیر موجود با متد غلط `405` می‌گیرد، همراه هدر `Allow` که فهرست متدهای مجاز را می‌دهد. مسیر ناموجود `404` می‌گیرد. هر دو بدنه متن ساده است، نه JSON ما؛ در بخش آخر به این برمی‌گردیم. (پورت در این دستورها `8095` نوشته شده؛ اجراهای واقعی پورت آزادِ تصادفی داشتند.)

## Middleware

بعضی کارها باید برای هر درخواست انجام شوند، هر مسیری که باشد: شناسه دادن، لاگ‌کردن، جان به در بردن از panic. نوشتن این‌ها در هر handler تکرار است، برای همین در Go از **middleware** استفاده می‌شود: تابعی از نوع `func(http.Handler) http.Handler`. handler بعدی را می‌گیرد و handler تازه‌ای برمی‌گرداند که پیش و/یا پس از صدا زدن آن کاری می‌کند. لایه‌های یک پیاز را تصور کنید که handler اصلی در مرکز آن است.

یک تابع کمکی کوچک آن‌ها را روی هم می‌چیند:

```go
func Chain(h http.Handler, mws ...Middleware) http.Handler {
	for i := len(mws) - 1; i >= 0; i-- {
		h = mws[i](h)
	}
	return h
}

return Chain(mux, RequestID, AccessLog, Recover)
```

اولین middleware فهرست بیرونی‌ترین لایه است، پس درخواست را اول می‌بیند و پاسخ را آخر. هر سه چه می‌کنند:

- `RequestID` همان کد نوشته‌ی قبل است که به یک middleware رفته: شناسه را با `logging.WithRequestID` در context می‌گذارد و هدر `X-Request-ID` را تنظیم می‌کند. چون handler مربوط به `slog` از قبل به هر رکوردی که context‌اش شناسه دارد `request_id` اضافه می‌کند، middleware دیگر لازم نیست شناسه را بشناسد.
- `AccessLog` بعد از برگشتن handler برای هر درخواست یک خط می‌نویسد. برای چاپ کد وضعیت، `ResponseWriter` را در یک struct کوچک می‌پیچد که کدی را که به `WriteHeader` داده می‌شود به خاطر می‌سپارد.
- `Recover` تازه است. handlerی که panic کند، بدون آن درخواست را با خودش پایین می‌کشد. `Recover` panic را می‌گیرد و به‌جای نوشتن پاسخ مخصوص خودش، از مسیر خطای نوشته‌ی قبل استفاده می‌کند:

```go
defer func() {
	if v := recover(); v != nil {
		writeErr(w, r, fmt.Errorf("panic: %v", v))
	}
}()
next.ServeHTTP(w, r)
```

`writeErr` همان تابع نوشته‌ی قبل است: خطای ناشناخته می‌شود `500` با متن ثابت و جزئیات فقط به لاگ می‌رود. به ترتیب دقت کنید: `Recover` داخل `AccessLog` است، پس حتی `500` حاصل از panic هم در access log ثبت می‌شود. برای امتحانش یک مسیر فقط‌دمو به نام `/boom` اضافه کردم که panic می‌کند:

```
$ curl -si localhost:8095/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: 4a899758

{"error":"internal error"}
```

سرور برای این درخواست دو خط نوشت، با همان `request_id` که در هدر به کلاینت رسید:

```
level=ERROR msg="request failed" method=GET path=/boom status=500 error="panic: something broke" request_id=4a899758
level=INFO msg=request method=GET path=/boom status=500 dur=170µs request_id=4a899758
```

خط اول خطا را با علتش نشان می‌دهد. خط دوم access log است، با کد وضعیت و مدت درخواست.

بدون `Recover` چه می‌شود؟ با سروری امتحانش کردم که در یک `http.ListenAndServe` ساده panic می‌کند (`cmd/barepanic`). خود `net/http` panic را می‌گیرد و پروسه زنده می‌ماند، و در لاگ سرور stack trace چاپ می‌کند. ولی کلاینت اصلاً پاسخی نمی‌گیرد: اتصال فقط بسته می‌شود و `curl` با کد ۵۲ («empty reply from server») خارج می‌شود.

## خواندن امن JSON

بدنه‌ی درخواست ورودیِ بیرونی است و باید بهش بدبین بود. دو چیز ممکن است خراب شود: بدنه‌ای که بزرگ است (حافظه را پر می‌کند) و بدنه‌ای که فیلد غیرمنتظره دارد (غلط تایپی که بی‌صدا هیچ کاری نمی‌کند). یک تابع کوچک هر دو را پوشش می‌دهد:

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

`MaxBytesReader` سقف مقداری از بدنه را که می‌شود خواند تعیین می‌کند. `DisallowUnknownFields` غلط تایپی مثل `"vip":true` را به‌جای نادیده‌گرفتن بی‌صدا، تبدیل به خطا می‌کند. هر دو شکست یک sentinel را wrap می‌کنند (`errTooBig` و `errBadJSON`)، پس `statusOf` نوشته‌ی قبل یک حالت تازه می‌گیرد: `errTooBig` می‌شود `413`. برای `422` فیلد خطادار را هم به بدنه‌ی پاسخ اضافه کردم که از `ValidationError`ی می‌آید که domain از قبل برمی‌گرداند. دو درخواست:

```
$ curl -si -X POST localhost:8095/orders -d '{"customer":"a","cents":1,"vip":true}'
HTTP/1.1 400 Bad Request
{"error":"bad json"}

$ curl -si -X POST localhost:8095/orders -d '{"customer":"","cents":0}'
HTTP/1.1 422 Unprocessable Entity
{"error":"invalid order: customer is required","fields":{"customer":"is required"}}
```

اولی فیلد ناشناخته دارد، پس `400` است. کلاینت فقط `bad json` می‌بیند و لاگ دلیل را نگه می‌دارد (`bad json: json: unknown field "vip"`). دومی JSON درستی است که قانون کسب‌وکار را می‌شکند، پس `422` است و `fields` به کلاینت می‌گوید کدام فیلد را درست کند. بدنه‌ی ۲ مگابایتی `413 Request Entity Too Large` با `{"error":"body too large"}` گرفت. یک نکته‌ی دیگر: domain فقط اولین قانونِ شکسته را گزارش می‌کند، پس در درخواست دوم تا وقتی `customer` درست نشود اسمی از `cents` نمی‌آید. وقتی `{"customer":"a","cents":0}` فرستادم، پاسخ `cents` را نام برد.

## timeoutهای سرور

حالا برگردیم به مشکل ابتدای نوشته. timeout صفر یعنی بدون محدودیت و کلاینتی که هدرها را بایت‌به‌بایت می‌فرستد از آن سوءاستفاده می‌کند. به این **{{< term "slowloris" "slowloris" >}}** می‌گویند: هر اتصال کند یک goroutine و یک {{< term "file-descriptor" "file descriptor" >}} را نگه می‌دارد و به اندازه‌ی کافی از آن‌ها سرور را از پا درمی‌آورد.

`http.Server` چهار timeout دارد و هر کدام از یک مرحله‌ی درخواست محافظت می‌کند:

- `ReadHeaderTimeout`: مهلت کلاینت برای فرستادن هدرهای درخواست.
- `ReadTimeout`: مهلت خواندن کل درخواست، هدرها و بدنه.
- `WriteTimeout`: مهلت نوشتن پاسخ.
- `IdleTimeout`: مدتی که یک اتصال {{< term "keep-alive" "keep-alive" >}} بیکار برای درخواست بعدی باز می‌ماند.

دفعه‌ی قبل `Config` یک `ReadTimeout` داشت که `main` به‌عنوان `ReadHeaderTimeout` می‌داد. حالا `Config` هر چهار تا را دارد، هر کدام با مقدار پیش‌فرض، با parserی که صفر را رد می‌کند (چون صفر دوباره یعنی «بدون محدودیت») و با یک بررسی تقاطعی:

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

بررسی تقاطعی می‌گوید مهلت هدر نمی‌تواند از مهلت کل درخواست بیشتر باشد، چون بی‌معنی می‌شود. `main` فقط این چهار مقدار را در سرور می‌گذارد:

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

با `ORDERS_WRITE_TIMEOUT=0s ORDERS_READ_HEADER_TIMEOUT=9s`، شروع برنامه هر دو مشکل را چاپ کرد و با کد ۲ خارج شد:

```
invalid configuration:
ORDERS_WRITE_TIMEOUT: must be positive
ORDERS_READ_HEADER_TIMEOUT: must not exceed ORDERS_READ_TIMEOUT
```

برای دیدن کار timeout یک کلاینت کوچک نوشتم، `cmd/slowheader`. یک خط درخواست و هدر `Host` می‌فرستد، بعد هر ۵۰۰ میلی‌ثانیه یک بایت اضافه، و هیچ‌وقت هدرها را تمام نمی‌کند. بعد از ۸ ثانیه دست می‌کشد. آن را به همین سرور (با مقدارهای پیش‌فرض) و به سرور دومی که از `http.ListenAndServe` ساده استفاده می‌کند، یعنی سرور با مقدار صفر، وصل کردم:

```
$ slowheader localhost:8095
server reacted after 2.0s: read 103 bytes, err=<nil>
"HTTP/1.1 400 Bad Request\r\n...\r\n\r\n400 Bad Request"

$ slowheader localhost:8081
still connected after 8.0s
```

(خط دوم خروجی اول از وسط کوتاه شده.) با `ReadHeaderTimeout` دو ثانیه‌ای، سرور تنظیم‌شده بعد از ۲٫۰ ثانیه `400 Bad Request` جواب داد و اتصال را بست. سرور با مقدار صفر هنوز منتظر بود که کلاینت من در ثانیه‌ی هشتم دست کشید.

## Graceful shutdown

راه‌اندازی دوباره‌ی سرور نباید درخواست‌های در حال اجرا را نصفه ببرد. نوشته‌ی [graceful shutdown برای workerها](/fa/posts/go-graceful-shutdown-workers/) این ایده را برای workerهای پس‌زمینه با جزئیات توضیح داده. برای سرور HTTP چند خط است:

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

سرور در یک goroutine اجرا می‌شود و `main` صبر می‌کند تا یک signal، `ctx` را لغو کند. بعد `Shutdown` پذیرفتن اتصال تازه را متوقف می‌کند و منتظر درخواست‌های در حال اجرا می‌ماند، تا deadline‌ی که به context داده‌ایم. `ListenAndServe` درست بعد از صدا زدن `Shutdown` خطای `http.ErrServerClosed` برمی‌گرداند، پس این خطا حالت عادی است، نه شکست. به دمو `SIGTERM` فرستادم و `shutting down` و بعد `stopped` لاگ کرد. در آن لحظه درخواستی در جریان نبود، پس این اجرا خود صبرکردن را نشان نمی‌دهد؛ فقط نشان می‌دهد مسیر signal کار می‌کند.

## تست handlerها

`httptest.NewServer` زنجیره‌ی واقعی handler را روی یک پورت محلی تصادفی بالا می‌آورد، پس تست با یک کلاینت HTTP معمولی با آن حرف می‌زند:

```go
svc := service.New(memory.New(), quiet, 1_000_000)
srv := httptest.NewServer(transport.NewHandler(svc))
defer srv.Close()
resp, _ := http.Post(srv.URL+"/orders", "application/json", strings.NewReader(body))
```

یک table test هشت حالت شکست را می‌فرستد (فیلد ناشناخته، اعتبارسنجی، بدنه‌ی بزرگ، پیدا نشدن، متد غلط، مسیر ناشناخته، خرابی ذخیره‌سازی، panic) و کد وضعیت هرکدام را بررسی می‌کند. تست دوم مقدارهای پیش‌فرض timeout و اعتبارسنجی کانفیگ را می‌پوشاند. همه را با race detector اجرا کردم (زمان‌ها فرق می‌کنند):

```
$ go test -race ./...
ok  	example.com/orders/internal/config	2.313s
ok  	example.com/orders/internal/service	2.318s
ok  	example.com/orders/internal/transport/http	2.550s
```

## جاهایی که net/http غافلگیرتان می‌کند

- پاسخ‌های `404` و `405` خودِ mux متن ساده‌اند. شناسه‌ی درخواست و خط access log را هم می‌گیرند (بالا هر دو را دیدم)، ولی اگر کلاینت‌هایتان JSON انتظار دارند، آن‌ها را wrap کنید.
- `WriteTimeout` مدت نوشتن پاسخ توسط handler را هم محدود می‌کند، پس دانلود طولانی یا stream به مقدار بزرگ‌تر یا deadline‌های هر درخواست با `http.ResponseController` نیاز دارد. برای نحوه‌ی تعامل آن با handlerهایتان مستندات `net/http` را ببینید.
- `MaxBytesReader` آنچه می‌خوانید را محدود می‌کند. خطایش را بررسی کنید، وگرنه بدنه‌ی بزرگ شبیه یک شکست عمومی decode به نظر می‌رسد.
- ترتیب middleware مهم است. `Recover` داخل `AccessLog` است تا `500` هم لاگ شود؛ اگر جابه‌جا شوند، access log هیچ‌وقت کد وضعیت panic را نمی‌بیند.
- wrapperی که کد وضعیت را ثبت می‌کند interfaceهای اختیاری مثل `http.Flusher` را پنهان می‌کند. متد `Unwrap() http.ResponseWriter` آن باعث می‌شود `http.ResponseController` از میانش کار کند.

## قدم بعدی

قدم بعدی «Postgres با pgx و sqlc در Go» است. همه‌ی داده هنوز در یک map درون‌حافظه است و سرویس واقعی دیتابیس لازم دارد.
