+++
date = '2026-12-28T10:00:00+03:30'
draft = false
title = 'کانفیگ، لاگ ساختاریافته و خطا در Go'
description = 'کانفیگ تایپ‌دار از متغیرهای محیطی، slog با handler متنی و JSON همراه با request ID، و تبدیل خطاهای domain به status کد HTTP در یک نقطه.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "slog", "config", "errors"]
cover = { image = "/images/covers/go-config-logging-errors.fa.png", alt = "کانفیگ، لاگ ساختاریافته و خطا در Go", hiddenInSingle = true }
+++

فرض کنید سرویس `orders` در production اجرا می‌شود و چیزی خراب می‌شود. سه سؤال تعیین می‌کند آن شب چقدر بد بگذرد. آیا سرویس با همان تنظیماتی بالا آمده که فکر می‌کنید؟ آیا از لاگ‌هایش می‌شود فهمید موقع خرابی چه می‌کرده؟ و وقتی درخواستی شکست می‌خورد، آیا مشتری جواب درستی می‌گیرد، بی‌آنکه چیزی را ببیند که نباید ببیند، مثل آدرس دیتابیس؟

کانفیگ، لاگ و خطا سه جایی هستند که سرویس یا به اپراتور می‌گوید چه خبر است، یا بی‌صدا گمراهش می‌کند و گاهی رمز را هم لو می‌دهد. سرویس `orders` در [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/) هنوز `:8080` ثابت و یک `log` ساده دارد. در این نوشته هر دو را درست می‌کنیم و برای خطاها یک سیاست آگاهانه می‌گذاریم. کد همان ماژول است، فقط با کتاب‌خانه‌ی استاندارد، و درجا تکامل پیدا کرده (برای همین خطاهای domain اینجا کمی غنی‌تر از نوشته‌ی قبل‌اند).

یک مثال کوچک از اینکه چرا مهم است، که بعداً درست آزمایشش می‌کنیم: اگر به نوع رمز عبور یک متد `LogValue` بدهید، `slog` به‌جای رمز `[REDACTED]` چاپ می‌کند. ولی همان مقدار را داخل یک struct ساده بگذارید، یا به `fmt.Println` بدهید، و رمز واقعی در خروجی می‌آید.

> همه‌چیز دوباره با Go 1.27 روی macOS (arm64) اجرا شده است. آدرس‌ها و شناسه‌های درخواست در خروجی‌ها از اجرا به اجرا فرق می‌کنند؛ هر بار سرور را روی یک پورت محلی آزادِ تصادفی بالا آوردم.

## کانفیگ: یک struct، یک‌بار بارگذاری

از ساده‌ترین چیزی که سرویس لازم دارد شروع کنیم: تنظیماتش. از کجا می‌آیند؟ جواب رایج {{< term "environment-variable" "متغیرهای محیطی" >}} است: رشته‌های نام‌دار که پروسه از کسی که آن را راه انداخته (مثلاً ابزار deploy) به ارث می‌برد. بدون ساخت دوباره‌ی برنامه می‌توانید تنظیم را عوض کنید.

خطر این است که متغیرهای محیطی رشته‌ی بدون نوع هستند و وسوسه می‌شویم هر جا لازم شد با `os.Getenv` بخوانیمشان. آن‌وقت یک غلط تایپی در مقدار، مدت‌ها بعد از شروع برنامه و عمق کد به‌شکل یک خرابی عجیب بیرون می‌زند. قاعده‌ای که من به جایش دارم این است: **محیط را فقط در یک جا بخوان، در یک struct تایپ‌دار، و اگر چیزی غلط بود همان موقع شروع شکست بخور.**

```go
type Config struct {
	Addr        string
	LogLevel    slog.Level
	LogFormat   string // "text" or "json"
	ReadTimeout time.Duration
	MaxCents    int64
	DBPassword  Secret
}
```

بقیه‌ی برنامه یک `Config` می‌گیرد که در آن timeout از قبل `time.Duration` است و سقف مبلغ از قبل عدد صحیح. تابع `Load` از `os.LookupEnv` استفاده می‌کند، مقدار پیش‌فرض می‌گذارد، هر مقدار را parse می‌کند و همه‌ی مشکل‌ها را جمع می‌کند، نه فقط اولی را:

```go
fail := func(key string, err error) { errs = append(errs, fmt.Errorf("%s: %w", key, err)) }
// ...
if c.ReadTimeout, err = time.ParseDuration(str("ORDERS_READ_TIMEOUT", "5s")); err != nil {
	fail("ORDERS_READ_TIMEOUT", err)
}
// ...
return c, errors.Join(errs...)
```

`str` یک تابع کمکی کوچک است که متغیر را برمی‌گرداند، یا اگر تنظیم نشده یا خالی بود مقدار پیش‌فرضش را. چرا همه‌ی خطاها را جمع می‌کنیم؟ برای دیدنش، سرویس را با چهار مقدار غلط و بدون رمز بالا آوردم. `main` یک گزارش چاپ می‌کند و با کد ۲ خارج می‌شود:

```
$ ORDERS_LOG_LEVEL=loud ORDERS_LOG_FORMAT=yaml ORDERS_READ_TIMEOUT=5 ORDERS_MAX_CENTS=lots ./orders
invalid configuration:
ORDERS_LOG_LEVEL: slog: level string "loud": unknown name
ORDERS_LOG_FORMAT: must be text or json, got "yaml"
ORDERS_READ_TIMEOUT: time: missing unit in duration "5"
ORDERS_MAX_CENTS: strconv.ParseInt: parsing "lots": invalid syntax
ORDERS_DB_PASSWORD: required
```

هر خط اسم متغیر را می‌گوید و اینکه چه مشکلی دارد. به خط timeout دقت کنید: `5` رد شده چون duration در Go واحد می‌خواهد، مثل `5s`. `errors.Join` پیام‌ها را در خط‌های جدا می‌گذارد، پس اپراتور همه‌چیز را در یک deploy درست می‌کند، نه اینکه مشکل‌ها را یکی‌یکی کشف کند. به هیچ کتاب‌خانه‌ی کانفیگ هم نیاز نشد.

## رمزهایی که لو نمی‌روند

کانفیگ رمز دارد و کانفیگ اولین چیزی است که موقع شروع لاگ می‌کنیم. پس رمز نوع خودش را لازم دارد. `Secret` یک نوع رشته‌ای با متد `LogValue` است که آن را یک `slog.LogValuer` می‌کند: وقتی `slog` می‌خواهد مقدار را چاپ کند، از خودِ مقدار می‌پرسد چطور چاپ شود.

```go
type Secret string

func (Secret) LogValue() slog.Value { return slog.StringValue("[REDACTED]") }
```

این کمک می‌کند ولی حد دارد، و با یک برنامه‌ی موقت که همان رمز را به سه شکل لاگ می‌کند آزمودمش:

```
level=INFO msg=direct pw=[REDACTED]
level=INFO msg="in struct" cfg="{User:app Pw:s3cr3t-pw}"
Println: s3cr3t-pw
```

(فیلد `time=` را از دو خط اول برداشته‌ام.) خط اول همان است که می‌خواهیم. خط دوم و سوم حد کار را نشان می‌دهند: پنهان‌کردن فقط وقتی کار می‌کند که `slog` خودِ `Secret` را ببیند. اگر در یک struct ساده باشد، `slog` همان‌طور که خروجی نشان می‌دهد کل struct را چاپ می‌کند و از فیلد داخلی نمی‌پرسد چطور چاپ شود. با `Println` هم فقط یک رشته است.

برای همین فقط به آن تکیه نمی‌کنم. `Config` هم خودش `LogValue` دارد و فیلدهایش را صریح فهرست می‌کند. پس فیلد تازه هیچ‌وقت سهواً لاگ نمی‌شود؛ باید عمداً به فهرست اضافه‌اش کنید. لاگ شروع برنامه از همین متد استفاده می‌کند.

## slog: handler، سطح و attribute

`log/slog` پکیج {{< term "structured-logging" "لاگ ساختاریافته" >}} کتاب‌خانه‌ی استاندارد است. به‌جای یک جمله که مقدارها لابه‌لایش چسبانده شده، هر رکورد یک پیام دارد به‌علاوه‌ی جفت‌های کلید/مقدار جدا (**attribute**)، تا سیستم لاگ بتواند بدون parse کردن زبان طبیعی روی `status=500` فیلتر کند. هر رکورد یک **سطح** هم دارد: debug، info، warn یا error.

`slog` کار را دو تکه می‌کند. API که صدا می‌زنید (`Info`، `With`، `Group`) رکورد می‌سازد. یک **handler** تصمیم می‌گیرد چطور فرمت شود و کجا نوشته شود. کانفیگ handler را انتخاب می‌کند و `SetDefault` لاگر ما را سراسری می‌کند (پکیج قدیمی `log` را هم به آن هدایت می‌کند):

```go
func New(w io.Writer, format string, level slog.Level) *slog.Logger {
	opts := &slog.HandlerOptions{Level: level}
	var h slog.Handler = slog.NewTextHandler(w, opts)
	if format == "json" {
		h = slog.NewJSONHandler(w, opts)
	}
	return slog.New(ctxHandler{h})
}
```

(`ctxHandler` یک wrapper است که در بخش بعد می‌بینیمش.) `main` تابع `slog.SetDefault(logger)` را صدا می‌زند و به سرویس `logger.With("component", "service")` می‌دهد، پس هر خطی که از آن لایه می‌آید `component=service` دارد. درون سرویس ساخته‌شدن سفارش این‌طور لاگ می‌شود:

```go
s.log.LogAttrs(ctx, slog.LevelInfo, "order created",
	slog.Group("order", slog.String("id", o.ID), slog.Int64("cents", o.Cents)))
```

`LogAttrs` فقط مقدار `Attr` تایپ‌دار می‌گیرد، پس از اشتباه کلاسیکِ تعداد فرد آرگومان در فهرست کلید/مقدار دور می‌ماند. `slog.Group` attributeهای مرتبط را زیر یک نام تو در تو می‌کند. این هم خط شروع برنامه در حالت text، که رمز را `Config.LogValue` پنهان کرده (بدون `time=` برای کوتاه‌شدن):

```
level=INFO msg=starting config.addr=127.0.0.1:54402 config.log_level=INFO config.log_format=text config.read_timeout=5s config.max_cents=1000000 config.db_password=[REDACTED]
```

پیشوند `config.` از group می‌آید. در حالت JSON همان رکورد group را به‌شکل یک شیء تو در تو می‌نویسد. به این توجه کنید که duration آنجا به نانوثانیه چاپ می‌شود:

```
{"time":"...","level":"INFO","msg":"starting","config":{"addr":"127.0.0.1:54402","log_level":"INFO","log_format":"json","read_timeout":5000000000,"max_cents":1000000,"db_password":"[REDACTED]"}}
```

سطح‌ها دلیل دوم وجود کانفیگ‌اند: با `ORDERS_LOG_LEVEL=warn` یک سفارش ساختم و سفارشی ناموجود را خواستم. خط «order created» (سطح info) ظاهر نشد و فقط هشدار سفارش ناموجود چاپ شد.

## شناسه‌ی درخواست از راه context

وقتی چند درخواست هم‌زمان اجرا می‌شوند، خط‌های لاگشان در هم می‌روند. برای جداکردن خط‌های یک درخواست باید روی هر کدام یک شناسه باشد. این همان {{< term "request-id" "شناسه‌ی درخواست" >}} (request ID) است.

نقشه دو بخش دارد. یک **middleware** کوچک (تابعی که handler را می‌پوشاند و برای هر درخواست اجرا می‌شود) یک شناسه می‌سازد، آن را در {{< term "context" "context" >}} درخواست می‌گذارد و همچنین در هدر `X-Request-ID` برای مشتری برمی‌گرداند. بعد یک wrapper دور handler خود slog، به نام `ctxHandler`، به هر رکوردی که context‌اش شناسه دارد `request_id` اضافه می‌کند:

```go
func (h ctxHandler) Handle(ctx context.Context, r slog.Record) error {
	if id := RequestID(ctx); id != "" {
		r.AddAttrs(slog.String("request_id", id))
	}
	return h.Handler.Handle(ctx, r)
}
```

wrapper باید `WithAttrs` و `WithGroup` را هم override کند و نتیجه‌شان را دوباره بپوشاند. وگرنه `logger.With(...)` handler داخلی را برمی‌گرداند و wrapper بی‌صدا ناپدید می‌شود. و برای اینکه کار کند باید موقع لاگ، context را بدهید: `LogAttrs(ctx, ...)` یا `InfoContext(ctx, ...)`، نه `Info` ساده.

## خطا در مرز سیستم

مبانی خطا در Go در [توابع، defer و خطا در Go](/fa/posts/go-functions-defer-errors/) آمده. اینجا سیاست یک سرویس را می‌گویم. خطاها از لایه‌ها بالا می‌روند و جایی باید یک تابع تصمیم بگیرد: مشتری چه ببیند و لاگ چه ببیند؟ می‌خواهم این تصمیم دقیقاً در یک جا باشد.

domain صاحب مقدارهای خطای آماده (**sentinel**، مثل `ErrNotFound`) و یک نوع سفارشی است که می‌گوید کدام فیلد غلط است:

```go
type ValidationError struct{ Field, Reason string }

func (e *ValidationError) Error() string { return fmt.Sprintf("invalid order: %s %s", e.Field, e.Reason) }
func (e *ValidationError) Unwrap() error { return ErrInvalidOrder }
```

`Unwrap` مقدار `ErrInvalidOrder` را برمی‌گرداند، پس `errors.Is(err, ErrInvalidOrder)` برایش هنوز درست است، و `errors.As` می‌تواند فیلد و دلیل را بیرون بکشد.

هر لایه موقع بالا رفتن خطا با `%w` به آن زمینه اضافه می‌کند، مثلاً `fmt.Errorf("get order %s: %w", id, err)`. فعل `%w` خطای اصلی را درون خطای تازه می‌پیچد، پس پیام بلندتر می‌شود ولی `errors.Is` و `errors.As` هنوز خطای اصلی را می‌بینند. بعد لایه‌ی transport در یک تابع کد وضعیت را تعیین می‌کند:

```go
func statusOf(err error) (int, string) {
	var ve *domain.ValidationError
	switch {
	case errors.As(err, &ve):
		return http.StatusUnprocessableEntity, ve.Error()
	case errors.Is(err, domain.ErrNotFound):
		return http.StatusNotFound, domain.ErrNotFound.Error()
	case errors.Is(err, errBadJSON):
		return http.StatusBadRequest, "bad json"
	default:
		return http.StatusInternalServerError, "internal error"
	}
}
```

پیامی که به مشتری می‌رود متن ثابتی است که همین‌جا انتخاب شده (یا پیام اعتبارسنجی که domain برای مشتری نوشته)، هیچ‌وقت `err.Error()` یک زنجیره‌ی دلخواه نیست. زنجیره‌ی کامل فقط به لاگ می‌رود، با سطحی که از کد وضعیت می‌آید: warn زیر ۵۰۰ و error از ۵۰۰ به بالا.

برای امتحان ۵۰۰ یک قلاب فقط‌دمو اضافه کردم: store درون‌حافظه‌ای برای شناسه‌ی `boom` با یک خطای دیتابیسِ جعلی شکست می‌خورد (آدرس داخلش ساختگی است). مشتری این را می‌بیند:

```
$ curl -si localhost:8091/orders/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: aef11965
{"error":"internal error"}
```

و این خطی است که سرور برای همان درخواست نوشت (حالت text و بدون فیلد `time=`؛ در حالت JSON همین فیلدها را دارد):

```
level=ERROR msg="request failed" method=GET path=/orders/boom status=500 error="get order boom: dial tcp 10.0.0.5:5432: connect: connection refused" request_id=aef11965
```

مشتری هیچ چیزی از آدرس دیتابیس نمی‌فهمد، ولی لاگ کل زنجیره را دارد، با همان `request_id` که هدر پاسخ برگرداند. اپراتور همین‌طور می‌تواند از شکایت مشتری شروع کند و خط را پیدا کند.

حالت‌های دیگر همین مسیر را می‌روند. سفارش ناموجود یک `WARN` با `"error":"get order 99: order not found"` لاگ می‌کند ولی فقط `{"error":"order not found"}` جواب می‌دهد. سفارشی با مبلغ بالاتر از سقف یا مشتری خالی `422` با پیام مشخص می‌گیرد، مثلاً `{"error":"invalid order: cents is above the limit"}`. بدنه‌ای که JSON نباشد `400` می‌گیرد؛ لاگ جزئیات decoder را نگه می‌دارد (`invalid character 'z' looking for beginning of value`) و مشتری فقط `{"error":"bad json"}` می‌بیند.

## اشتباه‌های رایج خطا و لاگ

- **لاگ‌کردن یک خطا در هر لایه.** اگر هر لایه هم لاگ کند و هم خطا را برگرداند، یک شکست پنج‌بار ظاهر می‌شود. یک‌بار و در مرز لاگ کنید و لایه‌های دیگر فقط زمینه اضافه کنند.
- **استفاده از `%v` به‌جای `%w`.** `%v` متن را نگه می‌دارد ولی زنجیره را می‌شکند، پس `errors.Is` و `errors.As` بالاتر کار نمی‌کنند.
- **خواندن متغیر محیطی در عمق کد.** رشته‌اند؛ زود و در یک جا parse‌شان کنید و هیچ‌وقت `os.Getenv` را از درون یک پکیج صدا نزنید.
- **اعتماد زیاد به پنهان‌سازی.** `LogValue` تضمین نیست، همان‌طور که آزمایش نشان داد. آنچه به لاگر می‌دهید را بازبینی کنید و کانفیگ را به‌صورت struct خام لاگ نکنید.
- **شناسه‌ای که مشتری نمی‌بیند.** فقط وقتی کمک می‌کند که مشتری (یا پشتیبان) هم بتواند بخواندش، پس آن را در هدر پاسخ برگردانید.

## قدم بعدی

قدم بعدی «ساخت API با net/http در Go» است. سرور اینجا هنوز حداقلی است و آن نوشته middleware، timeout و تست را رویش می‌سازد.
