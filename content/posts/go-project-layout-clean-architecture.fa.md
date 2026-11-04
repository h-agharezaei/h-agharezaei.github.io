+++
date = '2026-12-18T10:00:00+03:30'
draft = false
title = 'ساختار پروژه و Clean Architecture در Go'
description = 'یک API کوچک سفارش‌ها در ساختار لایه‌ای Go: domain، service، store و transport، با وصل‌کردن دستی، بررسی واقعی import‌ها، تست با store جعلی و اجرای curl.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "architecture", "clean-architecture", "backend"]
cover = { image = "/images/covers/go-project-layout-clean-architecture.fa.png", alt = "ساختار پروژه و Clean Architecture در Go", hiddenInSingle = true }
+++

نسخه‌ی اول تقریباً هر سرویس کوچکی را به یاد بیاورید. یک handler بدنه‌ی JSON را می‌خواند، چک می‌کند مبلغ مثبت باشد، یک `INSERT` اجرا می‌کند و پاسخ را می‌نویسد. سی خط است، کار می‌کند و کسی هم شکایتی ندارد. بعد یک قانون عوض می‌شود و می‌خواهید برایش تست بنویسید. ولی برای تست «مبلغ باید مثبت باشد» باید یک دیتابیس بالا بیاورید، چون قانون در همان تابعی است که SQL دارد. کمی بعد کسی می‌خواهد همین قانون از یک consumer صف هم اجرا شود، و می‌بینید قانون به `http.ResponseWriter` چسبیده است.

هیچ‌کدام از این‌ها باگ نیست. کد فقط سه کار متفاوت را قاطی کرده: قانون‌های کسب‌وکار، ذخیره‌سازی و حرف‌زدن با HTTP. وقتی این سه در یک جا باشند، نمی‌شود یکی را عوض یا تست کرد، بی‌آنکه آن دوتای دیگر هم همراهش بیایند.

در این نوشته یک سرویس کوچک `orders` می‌سازیم که هر کار جای خودش را دارد، و قاعده‌ای را می‌گویم که تعیین می‌کند چه کسی اجازه دارد چه کسی را import کند. نکته‌ی جالبش این است که این قاعده را با چشم بررسی نمی‌کنیم: خود ابزار Go آن را برایمان چاپ می‌کند. در [پکیج‌ها و ماژول‌ها](/fa/posts/go-packages-modules/) و [پروژه‌ی کوچک URL shortener](/fa/posts/go-mini-project-url-shortener/) همه‌چیز در چند فایل جا می‌شد، پس این اولین بار است که سؤال «این کد کجا برود؟» واقعاً مهم می‌شود.

> همه‌ی مثال‌ها دوباره با Go 1.27 روی macOS (arm64) اجرا شده‌اند و ماژول `go 1.26` اعلام می‌کند. ماژول `example.com/orders` است و فقط از کتاب‌خانه‌ی استاندارد استفاده می‌کند. کد یک مثال محلی است، نه مخزن منتشرشده.

## ایده‌ی اصلی: فلش‌ها به سمت داخل

سرویس را مثل چند حلقه‌ی تو در تو تصور کنید. در مرکز **قانون‌های کسب‌وکار** هستند: سفارش چیست و کدام سفارش معتبر است. دورش **use caseها** هستند: «سفارش بساز»، «سفارش را پیدا کن». در بیرون چیزهایی هستند که ممکن است عوض شوند: دیتابیس و لایه‌ی HTTP.

قاعده یک جمله است: **وابستگی‌ها به سمت داخل اشاره می‌کنند.** پکیجِ حلقه‌ی داخلی نباید پکیجی از حلقه‌ی بیرونی را import کند. کد داخلی نمی‌داند کد بیرونی وجود دارد. کد بیرونی اجازه دارد کد داخلی را بشناسد.

دلیلش عملی است. دیتابیس و فریم‌ورک وب چیزهایی هستند که احتمال دارد عوضشان کنید یا نسخه‌شان را ارتقا بدهید. اگر قانون‌ها آن‌ها را import نکنند، با تغییر آن‌ها هیچ‌وقت لازم نیست قانون‌ها عوض شوند. و پکیجی که چیز سنگینی import نمی‌کند، بدون چیز سنگین هم تست می‌شود.

در Go این می‌شود چهار پکیج و یک `main`:

```
orders/
  cmd/api/main.go                  // composition root
  internal/domain/order.go         // entities and rules
  internal/service/service.go      // use cases
  internal/store/memory/store.go   // one implementation of storage
  internal/transport/http/handler.go // thin HTTP handlers
```

- `domain` هیچ‌کس را نمی‌شناسد. خود سفارش و قانون‌هایش اینجاست.
- `service` فقط `domain` را می‌شناسد. use caseها اینجاست.
- `store` و `transport` حلقه‌ی بیرونی‌اند و پکیج‌های داخلی را می‌شناسند.
- `main` تنها جایی است که همه را می‌شناسد؛ تکه‌ها را می‌سازد و به هم وصل می‌کند.

یک نکته‌ی مخصوص Go: پوشه‌ی `internal/` خاص است. کامپایلر اجازه نمی‌دهد کدی بیرون از این ماژول پکیج‌های زیر آن را import کند، پس کس دیگری نمی‌تواند ناخواسته به درون‌ساخت ما وابسته شود.

## Domain: بدون زیرساخت

درونی‌ترین پکیج نوع `Order`، خطاهای ثابت (`ErrNotFound` و `ErrInvalidOrder`) و یک سازنده دارد. قانون کسب‌وکار در سازنده است:

```go
func NewOrder(id, customer string, cents int64) (Order, error) {
	if customer == "" || cents <= 0 {
		return Order{}, fmt.Errorf("%w: customer and positive amount required", ErrInvalidOrder)
	}
	return Order{ID: id, Customer: customer, Cents: cents, Status: "new"}, nil
}
```

قانون «مشتری و مبلغ مثبت لازم است» یک {{< term "invariant" "invariant" >}} است، یعنی چیزی که برای هر سفارشِ موجود باید درست باشد. چون تنها راه ساختن سفارش معتبر همین سازنده است، قانون فقط یک‌بار نوشته می‌شود و نمی‌شود سهواً از آن رد شد.

به چیزی که نیست نگاه کنید: نه تگ JSON هست، نه SQL و نه import از `net/http`. این پکیج را می‌شود بدون هیچ چیز دیگری کامپایل و تست کرد.

## Service: interface مال کسی است که از آن استفاده می‌کند

سرویس use caseها را پیاده می‌کند. برای ساختن سفارش باید آن را جایی ذخیره کند، ولی نباید بداند کجا. پس چیزی را که لازم دارد به‌شکل یک **interface** اعلام می‌کند، یعنی فهرستی از متدها، و می‌گوید «هر چیزی که این متدها را دارد»:

```go
type Repository interface {
	Save(ctx context.Context, o domain.Order) error
	Get(ctx context.Context, id string) (domain.Order, error)
	NextID(ctx context.Context) string
}

func (s *Service) Create(ctx context.Context, customer string, cents int64) (domain.Order, error) {
	o, err := domain.NewOrder(s.repo.NextID(ctx), customer, cents)
	if err != nil {
		return domain.Order{}, err
	}
	if err := s.repo.Save(ctx, o); err != nil {
		return domain.Order{}, err
	}
	return o, nil
}
```

`Create` را مثل یک داستان بخوانید: از repository یک شناسه‌ی تازه بگیر، سفارش معتبر بساز (قانون domain اینجا اجرا می‌شود) و بعد ذخیره کن. اگر قانون رد شود، زود برمی‌گردیم و چیزی ذخیره نمی‌شود.

ببینید interface کجا تعریف شده: در `service`، کنار کدی که از آن استفاده می‌کند، نه در پکیجی که پیاده‌اش می‌کند. در Go یک نوع فقط با داشتن متدهای درست یک interface را برآورده می‌کند و لازم نیست بگوید «من این را پیاده می‌کنم». برای همین store برای جور شدن با آن اصلاً نیازی ندارد interface سرویس را import کند. این همان ضرب‌المثل Go است، «interface بگیر، struct برگردان»، در مرز بین پکیج‌ها: مصرف‌کننده چیز کوچکی را که لازم دارد توصیف می‌کند و هر نوعی که جور باشد پذیرفته است.

store درون‌حافظه‌ای (یک map با mutex) `Repository` را برآورده می‌کند. یک store دیتابیسی واقعی هم می‌کند. پکیج HTTP همین کار را از طرف دیگر می‌کند: یک interface دومتدی به نام `Orders` برای آنچه از سرویس لازم دارد تعریف می‌کند. handlerهایش چهار کار کوچک می‌کنند: درخواست را decode می‌کنند، سرویس را صدا می‌زنند، خطا را به کد وضعیت تبدیل می‌کنند و پاسخ را encode می‌کنند. هیچ قانونی آنجا نیست.

## محافظ زمان کامپایل

چون interface به‌صورت ضمنی برآورده می‌شود، یک غلط تایپی در امضای متد عارضه‌ی بدی دارد. کامپایلر چیزی نمی‌گوید تا اولین جایی که store واقعاً به‌عنوان `Repository` به کار می‌رود، و این جا ممکن است از store خیلی دور باشد. یک خط محافظ خطا را کنار پیاده‌سازی می‌آورد:

```go
var _ service.Repository = (*Store)(nil)
```

معنایش این است: «یک `*Store`ی nil را به متغیری از نوع `service.Repository` بده و دور بینداز». در زمان اجرا هیچ کاری نمی‌کند. فقط کامپایلر را وادار می‌کند بررسی کند `*Store` همه‌ی متدها را دارد.

برای دیدنش، از یک نسخه‌ی کپی‌شده‌ی store (در پوشه‌ی `_broken` دمو) متد `NextID` را برداشتم و build کردم:

```
$ go build ./_broken/
# example.com/orders/_broken
_broken/store.go:10:28: cannot use (*Store)(nil) (value of type *Store) as service.Repository value in variable declaration: *Store does not implement service.Repository (missing method NextID)
```

پیام به خط محافظ اشاره می‌کند و متدِ گم‌شده را اسم می‌برد.

یک مصالحه هست. برای نوشتن این محافظ، `store/memory` باید `service` را import کند. جهت هنوز به سمت داخل است و قاعده سالم می‌ماند. ولی اگر ترجیح می‌دهید store اصلاً سرویس را نشناسد، محافظ را در `main.go` یا در تست store بگذارید.

## Composition root

کسی باید store واقعی را بسازد، به سرویس بدهد و سرویس را به handler HTTP بدهد. این جا را {{< term "composition-root" "composition root" >}} می‌گویند و در Go همان `main` است. این‌که وابستگی‌ها از بیرون داده شوند، {{< term "dependency-injection" "تزریق وابستگی" >}} (dependency injection) است، آن هم بدون هیچ فریم‌ورکی:

```go
func main() {
	repo := memory.New()
	svc := service.New(repo)
	handler := transport.NewHandler(svc)

	log.Fatal(http.ListenAndServe(":8080", handler))
}
```

وصل‌کردن اینجا سه خط است و در سرویس بزرگ‌تر شاید سی خط شود. باز هم خواندنش آسان است، با `grep` پیدا می‌شود و کامپایلر بررسی‌اش می‌کند. تا اینجا در Go به فریم‌ورک تزریق وابستگی نیاز پیدا نکرده‌ام.

## اثبات جهت وابستگی‌ها

«وابستگی‌ها به سمت داخل‌اند» یک ادعاست و ادعا را باید بررسی کرد. `go list` می‌تواند import‌های هر پکیج را چاپ کند. خروجی را فقط به پکیج‌های همین ماژول فیلتر کردم:

```
$ for p in domain service store/memory transport/http; do
>   echo "== $p"; go list -f '{{join .Imports "\n"}}' ./internal/$p | grep example.com
> done
== domain
== service
example.com/orders/internal/domain
== store/memory
example.com/orders/internal/domain
example.com/orders/internal/service
== transport/http
example.com/orders/internal/domain
```

پکیج به پکیج بخوانید. `domain` چیزی از ماژول import نمی‌کند: فهرستش خالی است. `service` فقط `domain` را import می‌کند. store هم `domain` و `service` را import می‌کند (همان محافظ بخش قبل). `transport/http` هم `domain` را import می‌کند، چون handlerهایش خطاهای domain را ترجمه می‌کنند. هیچ پکیج حلقه‌ی داخلی `store` یا `transport` را import نمی‌کند. `go list -deps ./internal/service` هم حتی برای import‌های غیرمستقیم همین را نشان می‌دهد؛ تنها پکیج ماژول در آن `domain` است. اگر بررسی‌ای مثل این را در CI بگذارید، معماری اجباری می‌شود و فقط به امید رعایتش نمی‌مانید.

## نتیجه‌ی عملی: تست بدون زیرساخت

حالا دلیل همه‌ی این کارها. سرویس یک `Repository` لازم دارد، پس در تست یک نسخه‌ی جعلی به آن می‌دهیم: چند خط در فایل تست که سفارش‌ها را در یک map نگه می‌دارد.

```go
type fakeRepo struct{ saved map[string]domain.Order }

func (f *fakeRepo) Save(_ context.Context, o domain.Order) error { f.saved[o.ID] = o; return nil }
func (f *fakeRepo) NextID(context.Context) string                { return "42" }
// Get omitted here; it looks the id up in f.saved
```

به چنین جایگزینی {{< term "test-double" "test double" >}} می‌گویند. با آن می‌توانیم این قانون را بررسی کنیم: «سفارش نامعتبر هیچ‌وقت ذخیره نمی‌شود»:

```go
func TestCreateInvalidDoesNotSave(t *testing.T) {
	repo := &fakeRepo{saved: map[string]domain.Order{}}
	_, err := service.New(repo).Create(context.Background(), "", 0)
	if !errors.Is(err, domain.ErrInvalidOrder) {
		t.Fatalf("err = %v", err)
	}
	if len(repo.saved) != 0 {
		t.Fatal("saved an invalid order")
	}
}
```

تست سفارشی بدون مشتری و با مبلغ صفر می‌خواهد. انتظار دارد خطا `ErrInvalidOrder` باشد و نسخه‌ی جعلی هنوز خالی. اجرایش (زمان سپری‌شده در هر اجرا فرق می‌کند):

```
$ go test -v ./internal/service
=== RUN   TestCreate
--- PASS: TestCreate (0.00s)
=== RUN   TestCreateInvalidDoesNotSave
--- PASS: TestCreateInvalidDoesNotSave (0.00s)
PASS
ok  	example.com/orders/internal/service	2.358s
```

هر دو تست پاس شدند: اولی یک سفارش معتبر را با نسخه‌ی جعلی می‌سازد و می‌بیند با شناسه‌ی `42` ذخیره شده. نه سرور لازم شد، نه دیتابیس و نه کتاب‌خانه‌ی mock. مشکلی که اول نوشته گفتم همین‌جا حل شد.

## اجرای واقعی

دمو پورت `:8080` را ثابت در کد دارد. چون روی ماشین مشترک ممکن است این پورت پر باشد، یک نسخه‌ی موقت را روی پورت محلی دیگری اجرا کردم و دستورهای زیر را برای خوانایی با `localhost:8080` نوشته‌ام. پاسخ‌ها به خط وضعیت و بدنه خلاصه شده‌اند.

```
$ curl -si -X POST localhost:8080/orders -d '{"customer":"ali","cents":1500}'
HTTP/1.1 201 Created
{"id":"1","customer":"ali","cents":1500,"status":"new"}

$ curl -si localhost:8080/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}
```

درخواست اول سفارش `1` را می‌سازد و `201` می‌گیرد. دومی سفارشی را می‌خواهد که وجود ندارد: store مقدار `domain.ErrNotFound` را برمی‌گرداند و handler آن را به `404` تبدیل می‌کند. سفارشی با مشتری خالی و `0` سنت هم فرستادم. پاسخ `422` بود با `{"error":"invalid order: customer and positive amount required"}` و بدنه‌ای که JSON نبود `400` با `{"error":"bad json"}` گرفت. در حالت `422`، خطای domain از سرویس بالا آمد و handler آن را به کد وضعیت ترجمه کرد، که دقیقاً تنها کار handler است.

## آیا این «Clean Architecture» است؟

تقریباً. در نمودار دایره‌های هم‌مرکز معروف «Clean Architecture» از Robert Martin، entityها همان `domain` ما هستند، use caseها `service`، آداپتورهای interface همان `transport` و `store`، و فریم‌ورک‌ها و درایورها همان `main` به‌علاوه‌ی کتاب‌خانه‌های بیرونی. نکته‌ی مخصوص Go این است که interfaceها ضمنی و کوچک‌اند، برای همین معمولاً به پکیج جداگانه‌ای پر از «port» نیاز نیست.

## چه زمانی این ساختار زیاده است

- برای ابزار ۳۰۰ خطی یا سرویس CRUD بدون قانون واقعی، این ساختار زیاده‌روی است. تخت شروع کنید (`main.go` و `store.go`). وقتی پیاده‌سازی دوم پیدا شد، یا بخشی که تستش سخت است، پکیج را جدا کنید.
- لازم نیست هر لایه interface داشته باشد. فقط جایی بگذارید که درز (seam) می‌خواهید، یعنی جایی که بشود چیز واقعی را با نسخه‌ی جعلی عوض کرد: ذخیره‌سازی، ساعت، API‌های بیرونی. سرویسی که یک پیاده‌سازی دارد و تست ندارد به آن نیاز ندارد.
- این درخت پوشه را مثل آیین کپی نکنید. یک شکل معقول است، نه تنها شکل. خیلی از پروژه‌های خوب Go تخت‌تر هستند.
- domain را تمیز نگه دارید. اگر نوع‌های HTTP یا تگ SQL به `Order` نفوذ کنند، جهت‌هایی که بالا بررسی کردیم فقط ظاهر می‌شوند.
- اسم پکیج‌هایی مثل `utils` یا `models` را کنار بگذارید. کدهای نامرتبط را جمع می‌کنند و import cycle می‌آورند، یعنی دو پکیج که به هم نیاز دارند و Go کامپایلشان نمی‌کند.

## قدم بعدی

قدم بعدی «کانفیگ، لاگ ساختاریافته و خطا در Go» است. با دو چیزی شروع می‌شود که اینجا در `main` از کنارشان گذشتیم: `:8080` ثابت و صدا زدنِ ساده‌ی `log`.
