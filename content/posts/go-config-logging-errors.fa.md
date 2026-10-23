+++
date = '2026-12-28T10:00:00+03:30'
draft = false
title = 'کانفیگ، لاگ ساختاریافته و خطا در Go'
description = 'کانفیگ تایپ‌دار از متغیرهای محیطی، slog با handler متنی و JSON همراه با request ID، و تبدیل خطاهای domain به status کد HTTP در یک نقطه.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "slog", "config", "errors"]
cover = { image = "/images/covers/go-config-logging-errors.fa.png", alt = "کانفیگ، لاگ ساختاریافته و خطا در Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-project-layout-clean-architecture/) سرویس کوچک `orders` را ساختیم، با `:8080` ثابت و یک `log.Println` ساده. اینجا هر دو را درست می‌کنیم و سومین چیزی را هم اضافه می‌کنیم که هر سرویس واقعی لازم دارد: سیاست روشن برای خطا در مرز سیستم. کد همان ماژول است، فقط با کتاب‌خانه‌ی استاندارد، و همان‌جا تکامل پیدا کرده.

> همه‌چیز با Go 1.26 روی macOS (arm64) اجرا شده است.

## Config: یک struct، یک‌بار بارگذاری

قاعده این است: محیط (environment) را فقط در یک جا بخوانید، داخل یک struct تایپ‌دار، و اگر چیزی غلط بود همان موقع راه‌اندازی شکست بخورید.

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

تابع `Load` از `os.LookupEnv` استفاده می‌کند، مقدار پیش‌فرض می‌گذارد، parse می‌کند و همه‌ی مشکل‌ها را جمع می‌کند، نه فقط اولی را:

```go
fail := func(key string, err error) { errs = append(errs, fmt.Errorf("%s: %w", key, err)) }
// ...
if c.ReadTimeout, err = time.ParseDuration(str("ORDERS_READ_TIMEOUT", "5s")); err != nil {
	fail("ORDERS_READ_TIMEOUT", err)
}
// ...
return c, errors.Join(errs...)
```

`str` یک helper کوچک است که مقدار متغیر یا پیش‌فرضش را برمی‌گرداند. با چهار مقدار غلط و یک رمز عبور جاافتاده، `main` یک گزارش چاپ می‌کند و با کد ۲ خارج می‌شود:

```
$ ORDERS_LOG_LEVEL=loud ORDERS_LOG_FORMAT=yaml ORDERS_READ_TIMEOUT=5 ORDERS_MAX_CENTS=lots ./orders
invalid configuration:
ORDERS_LOG_LEVEL: slog: level string "loud": unknown name
ORDERS_LOG_FORMAT: must be text or json, got "yaml"
ORDERS_READ_TIMEOUT: time: missing unit in duration "5"
ORDERS_MAX_CENTS: strconv.ParseInt: parsing "lots": invalid syntax
ORDERS_DB_PASSWORD: required
```

`errors.Join` پیام‌ها را با خط جدید به هم می‌چسباند، پس مسئول deploy همه‌چیز را یک‌جا درست می‌کند، نه در پنج دور. به کتاب‌خانه‌ی config هم نیازی نبود.

## رازهایی که نشت نمی‌کنند

`Secret` یک نوع از جنس string است با متد `LogValue`، یعنی یک `slog.LogValuer`:

```go
type Secret string

func (Secret) LogValue() slog.Value { return slog.StringValue("[REDACTED]") }
```

حدود این کار را با یک برنامه‌ی موقت امتحان کردم:

```
level=INFO msg=direct pw=[REDACTED]
level=INFO msg="in struct" cfg="{User:app Pw:s3cr3t-pw}"
Println: s3cr3t-pw
```

پنهان‌سازی فقط وقتی کار می‌کند که slog خودِ `Secret` را ببیند. داخل یک struct معمولی یا با `Println` مقدار نشت می‌کند. برای همین `Config` هم خودش `LogValue` دارد و فیلدها را صریح فهرست می‌کند؛ لاگ شروع برنامه از همین استفاده می‌کند.

## slog: handler، level و attribute

پکیج `log/slog` رابط (`Info`، `With`، `Group`) را از handlerی که رکورد را فرمت می‌کند جدا می‌کند. config نوع handler را انتخاب می‌کند و `SetDefault` آن را logger سراسری می‌کند (پکیج قدیمی `log` را هم به همین handler وصل می‌کند):

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

`main` بعد `slog.SetDefault(logger)` را صدا می‌زند و به سرویس `logger.With("component", "service")` می‌دهد، پس هر خط آن لایه این attribute را دارد. داخل سرویس:

```go
s.log.LogAttrs(ctx, slog.LevelInfo, "order created",
	slog.Group("order", slog.String("id", o.ID), slog.Int64("cents", o.Cents)))
```

`LogAttrs` فقط `Attr` تایپ‌دار می‌گیرد و از اشتباه تعداد فرد آرگومان در لیست key/value جلوگیری می‌کند. با `ORDERS_LOG_LEVEL=warn` خط «order created» دیگر ظاهر نشد و فقط هشدار سفارش ناموجود ماند. لاگ شروع در حالت متنی (راز پنهان است):

```
level=INFO msg=starting config.addr=:8091 config.log_level=INFO config.log_format=text config.read_timeout=5s config.max_cents=1000000 config.db_password=[REDACTED]
```

(فیلد `time=` را برای کوتاه‌شدن خروجی حذف کردم.) در JSON همین رکورد group را تو در تو نشان می‌دهد، ولی دقت کنید که duration به نانوثانیه تبدیل می‌شود: `"read_timeout":5000000000`.

## Request ID از راه context

یک middleware کوچک ID می‌سازد، آن را در context می‌گذارد و در هدر `X-Request-ID` برمی‌گرداند. wrapper به نام `ctxHandler` handler اصلی را embed می‌کند و به هر رکوردی که context آن ID دارد، `request_id` اضافه می‌کند:

```go
func (h ctxHandler) Handle(ctx context.Context, r slog.Record) error {
	if id := RequestID(ctx); id != "" {
		r.AddAttrs(slog.String("request_id", id))
	}
	return h.Handler.Handle(ctx, r)
}
```

متدهای `WithAttrs` و `WithGroup` را هم override می‌کند تا نتیجه را دوباره wrap کند؛ وگرنه `logger.With(...)` بی‌صدا wrapper را از دست می‌دهد. برای کارکردن باید context را پاس بدهید: `LogAttrs(ctx, ...)` یا `InfoContext(ctx, ...)`، نه `Info` ساده.

## خطا در مرز سیستم

مبانی در [توابع، defer و خطاها](/fa/posts/go-functions-defer-errors/) آمده؛ اینجا سیاست را می‌بینیم. domain صاحب sentinel‌ها و یک نوع خطای سفارشی است که می‌گوید کدام فیلد غلط است:

```go
type ValidationError struct{ Field, Reason string }

func (e *ValidationError) Error() string { return fmt.Sprintf("invalid order: %s %s", e.Field, e.Reason) }
func (e *ValidationError) Unwrap() error { return ErrInvalidOrder }
```

سرویس با `%w` زمینه اضافه می‌کند، مثلاً `fmt.Errorf("get order %s: %w", id, err)`. لایه‌ی transport در یک تابع تصمیم می‌گیرد status چه باشد:

```go
func statusOf(err error) (int, string) {
	var ve *domain.ValidationError
	switch {
	case errors.As(err, &ve):
		return http.StatusUnprocessableEntity, ve.Error()
	case errors.Is(err, domain.ErrNotFound):
		return http.StatusNotFound, domain.ErrNotFound.Error()
	default:
		return http.StatusInternalServerError, "internal error"
	}
}
```

پیامی که به کلاینت می‌رسد متن ثابتی است که همین‌جا انتخاب می‌شود، نه `err.Error()` یک زنجیره‌ی دلخواه. زنجیره‌ی کامل به لاگ می‌رود، با level متناسب با status. برای آزمایش یک ۵۰۰، فقط برای دمو یک قلاب گذاشتم: store درون‌حافظه‌ای برای id برابر `boom` یک خطای ساختگی دیتابیس برمی‌گرداند.

```
$ curl -si localhost:8091/orders/boom
HTTP/1.1 500 Internal Server Error
X-Request-Id: cbec0bb8
{"error":"internal error"}
```

```
{"time":"...","level":"ERROR","msg":"request failed","method":"GET","path":"/orders/boom","status":500,"error":"get order boom: dial tcp 10.0.0.5:5432: connect: connection refused","request_id":"cbec0bb8"}
```

کلاینت چیزی درباره‌ی آدرس دیتابیس نمی‌فهمد، ولی لاگ کل زنجیره را دارد، با همان `request_id` که هدر پاسخ برگرداند. سفارش ناموجود یک `WARN` با `"error":"get order 99: order not found"` لاگ می‌کند ولی فقط `{"error":"order not found"}` جواب می‌دهد.

## چند نکته که باید حواستان باشد

- هر خطا را یک‌بار و در مرز لاگ کنید. اگر هر لایه هم لاگ کند و هم برگرداند، یک شکست را پنج بار می‌بینید.
- `%v` به‌جای `%w` متن را نگه می‌دارد ولی `errors.Is` و `errors.As` را خراب می‌کند.
- متغیرهای محیطی رشته‌اند: زود parse کنید و `os.Getenv` را هیچ‌وقت از عمق یک پکیج صدا نزنید.
- پنهان‌سازی با `LogValue` تضمین کامل نیست. آنچه به logger می‌دهید را مرور کنید و config را به‌صورت struct خام لاگ نکنید.
- request ID وقتی کمک می‌کند که کلاینت هم آن را ببیند، پس در هدر پاسخ برگردانید.

## قدم بعدی

در مقاله‌ی بعد: ساخت API با net/http در Go.
