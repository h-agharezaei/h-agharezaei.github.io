+++
date = '2026-12-18T10:00:00+03:30'
draft = false
title = 'ساختار پروژه و Clean Architecture در Go'
description = 'یک API کوچک سفارش‌ها در ساختار لایه‌ای Go: domain، service، store و transport، با وصل‌کردن دستی، بررسی واقعی import‌ها، تست با store جعلی و اجرای curl.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "architecture", "clean-architecture", "backend"]
cover = { image = "/images/covers/go-project-layout-clean-architecture.fa.png", alt = "ساختار پروژه و Clean Architecture در Go", hiddenInSingle = true }
+++

این مقاله شروع سری Go Backend است. سری Go Fundamentals با [پکیج‌ها و ماژول‌ها](/fa/posts/go-packages-modules/) و [پروژه‌ی کوچک URL shortener](/fa/posts/go-mini-project-url-shortener/) تمام شد، یعنی جاهایی که همه‌چیز در چند فایل جا می‌شد. وقتی سرویس دیتابیس، لایه‌ی HTTP و قوانین کسب‌وکار واقعی پیدا کند، سؤال این می‌شود که هر چیز کجا باشد و چه کسی اجازه دارد چه کسی را import کند. اینجا یک سرویس کوچک `orders` را در ساختار لایه‌ای می‌سازیم و قانون‌های وابستگی را با ابزار خود Go بررسی می‌کنیم، نه با چشم.

> همه‌ی مثال‌ها با Go 1.26 روی macOS (arm64) اجرا شده‌اند. ماژول `example.com/orders` است و فقط از کتاب‌خانه‌ی استاندارد استفاده می‌کند.

## ساختار پوشه‌ها

```
orders/
  cmd/api/main.go                  // composition root
  internal/domain/order.go         // entities and rules
  internal/service/service.go      // use cases
  internal/store/memory/store.go   // one implementation of storage
  internal/transport/http/handler.go // thin HTTP handlers
```

قانون یک جمله است: وابستگی‌ها به سمت داخل اشاره می‌کنند. `domain` هیچ‌کس را نمی‌شناسد، `service` فقط `domain` را می‌شناسد و پکیج‌های بیرونی (`store` و `transport`) لایه‌های داخلی را می‌شناسند. فقط `main` همه را می‌شناسد.

## Domain: بدون زیرساخت

```go
func NewOrder(id, customer string, cents int64) (Order, error) {
	if customer == "" || cents <= 0 {
		return Order{}, fmt.Errorf("%w: customer and positive amount required", ErrInvalidOrder)
	}
	return Order{ID: id, Customer: customer, Cents: cents, Status: "new"}, nil
}
```

struct به نام `Order`، سازنده‌ای که **invariant**‌هایش را تضمین می‌کند و خطاهای ثابت (`ErrNotFound` و `ErrInvalidOrder`) اینجا هستند. نه تگ JSON دارد، نه SQL و نه `net/http`.

## Service: interface در سمت مصرف‌کننده

سرویس جایی برای ذخیره‌ی سفارش‌ها لازم دارد، برای همین خودش interface را تعریف می‌کند، آن هم به کوچکی چیزی که use case‌ها نیاز دارند:

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

این همان ضرب‌المثل Go یعنی «interface بگیر، struct برگردان» در مرز پکیج‌هاست: interface مال کدی است که از آن استفاده می‌کند، نه کدی که پیاده‌اش می‌کند. store درون‌حافظه‌ای (یک map با mutex) آن را برآورده می‌کند و هر چیز دیگری هم که این سه متد را داشته باشد. پکیج HTTP هم همین کار را می‌کند: یک interface دومتدی به نام `Orders` تعریف می‌کند و handler‌هایش فقط decode می‌کنند، سرویس را صدا می‌زنند، خطا را به status تبدیل می‌کنند و encode می‌کنند.

## محافظ زمان کامپایل

interface در Go ضمنی برآورده می‌شود، پس غلط تایپی در امضای یک متد فقط در جایی که store برای اولین بار استفاده می‌شود پیدا می‌شود. یک خط محافظ این خطا را کنار خود پیاده‌سازی می‌آورد:

```go
var _ service.Repository = (*Store)(nil)
```

از یک کپی از store (در پوشه‌ی `_broken` دموی من) متد `NextID` را برداشتم و build کردم:

```
$ go build ./_broken/
_broken/store.go:10:28: cannot use (*Store)(nil) (value of type *Store) as service.Repository value in variable declaration: *Store does not implement service.Repository (missing method NextID)
```

یک مصالحه هست: این محافظ باعث می‌شود `store/memory` پکیج `service` را import کند. جهتش هنوز به سمت داخل است، ولی اگر نمی‌خواهید store سرویس را بشناسد، محافظ را در `main.go` یا در تست store بگذارید.

## Composition root

```go
func main() {
	repo := memory.New()
	svc := service.New(repo)
	handler := transport.NewHandler(svc)

	log.Fatal(http.ListenAndServe(":8080", handler))
}
```

وصل‌کردن دستی اینجا سه خط است و در سرویس بزرگ‌تر شاید سی خط شود. باز هم خوانا است، با grep پیدا می‌شود و کامپایلر بررسی‌اش می‌کند؛ تا اینجا در Go به فریم‌ورک DI نیاز پیدا نکرده‌ام.

## اثبات جهت وابستگی‌ها

`go list` import‌های هر پکیج را چاپ می‌کند. خروجی را فقط به همین ماژول فیلتر کردم:

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

`domain` هیچ چیزی از ماژول import نمی‌کند، `service` فقط `domain` را import می‌کند و هیچ‌کدام `store` یا `transport` را import نمی‌کنند. `go list -deps ./internal/service` هم، حتی به‌صورت غیرمستقیم، همین را نشان داد. اگر این را در CI بگذارید، معماری اجباری می‌شود و فقط به امید رعایتش نمی‌مانید.

## نتیجه‌ی عملی: تست بدون زیرساخت

نسخه‌ی جعلی در فایل تست است و همان سه متد را دارد:

```go
type fakeRepo struct{ saved map[string]domain.Order }

func (f *fakeRepo) Save(_ context.Context, o domain.Order) error { f.saved[o.ID] = o; return nil }
func (f *fakeRepo) NextID(context.Context) string                { return "42" }
// Get omitted here; it looks the id up in f.saved
```

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

```
$ go test -v ./internal/service
=== RUN   TestCreate
--- PASS: TestCreate (0.00s)
=== RUN   TestCreateInvalidDoesNotSave
--- PASS: TestCreateInvalidDoesNotSave (0.00s)
PASS
ok  	example.com/orders/internal/service	0.250s
```

نه سرور لازم شد، نه دیتابیس و نه کتاب‌خانه‌ی mock.

## اجرای واقعی

پاسخ‌ها به خط status و بدنه خلاصه شده‌اند.

```
$ curl -si -X POST localhost:8080/orders -d '{"customer":"ali","cents":1500}'
HTTP/1.1 201 Created
{"id":"1","customer":"ali","cents":1500,"status":"new"}

$ curl -si localhost:8080/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}
```

بدنه‌ی نامعتبر هم `422` با `{"error":"invalid order: customer and positive amount required"}` برگرداند: خطای domain از سرویس بالا آمد و handler آن را به status تبدیل کرد.

## آیا این Clean Architecture است؟

تقریباً. دایره‌های معروف در Go این‌طور نگاشت می‌شوند: entity‌ها همان `domain` هستند، use case‌ها `service`، آداپتورها `transport` و `store`، و فریم‌ورک‌ها و درایورها همان `main` به‌علاوه‌ی کتاب‌خانه‌های بیرونی. نکته‌ی مخصوص Go این است که interface‌ها ضمنی و کوچک‌اند، برای همین معمولاً به پکیج جداگانه‌ی «ports» نیاز نیست.

## چند نکته که باید حواستان باشد

- برای ابزار ۳۰۰ خطی یا سرویس CRUD بدون قانون واقعی، این ساختار زیاده‌روی است. تخت شروع کنید (`main.go` و `store.go`) و وقتی پیاده‌سازی دوم یا بخشی سخت‌تست پیدا شد، پکیج را جدا کنید.
- لازم نیست هر لایه interface داشته باشد. فقط جایی که درز (seam) می‌خواهید بگذارید: ذخیره‌سازی، ساعت، API‌های بیرونی. سرویسی که یک پیاده‌سازی دارد و تست ندارد به آن نیاز ندارد.
- این درخت پوشه را مثل آیین کپی نکنید. یک شکل معقول است، نه «تنها راه»؛ خیلی از پروژه‌های خوب Go تخت‌تر هستند.
- domain را تمیز نگه دارید. اگر handler یا تگ SQL به `Order` نفوذ کند، جهت‌هایی که بالا اثبات کردیم فقط ظاهر می‌شوند.
- اسم پکیج‌هایی مثل `utils` یا `models` را کنار بگذارید؛ import cycle می‌آورند.

## قدم بعدی

در مقاله‌ی بعد: پیکربندی، لاگ ساخت‌یافته و مدیریت خطا در Go، که در آن `:8080` ثابت و `log.Println` همین سرویس را عوض می‌کنیم.
