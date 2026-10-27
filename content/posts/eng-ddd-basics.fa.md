+++
date = '2027-05-28T10:00:00+03:30'
draft = false
title = 'مبانی DDD'
description = 'مبانی DDD با Go: value object، aggregate که invariantهایش را نگه می‌دارد، رویداد دامنه، bounded context و تستی که وابستگی‌های لایه‌ها را می‌سنجد.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ddd", "domain-driven-design", "software-engineering", "go", "architecture"]
cover = { image = "/images/covers/eng-ddd-basics.fa.png", alt = "مبانی DDD", hiddenInSingle = true }
+++

پست قبل، [کار با کد legacy](/fa/posts/eng-legacy-code/)، به مرز میان مدل قدیم و جدید رسید. {{< term "domain-driven-design" "طراحی دامنه‌محور" >}} (DDD) بیشترِ حرفش درباره‌ی همین مرز است. ایده‌ها از کتاب «Domain-Driven Design» نوشته‌ی Eric Evans می‌آیند و کتاب «Implementing Domain-Driven Design» از Vaughn Vernon ادامه‌ی عملی آن است. مرتبط: [ساختار پروژه و clean architecture در Go](/fa/posts/go-project-layout-clean-architecture/) و [تست در Go](/fa/posts/go-testing-basics/). نظرها مشخص شده‌اند؛ بقیه اجرا شده است.

> Go 1.26 و `go test -race`. دمو نمونه‌ی محلی و ساختگی است: سفارش در Sales و گیرنده در Shipping.

## زبان و value object

قاعده‌ی {{< term "ubiquitous-language" "زبان فراگیر" >}}: نام‌ها در کد همان نام‌ها در گفتگوست. اگر تیم می‌گوید «ثبت سفارش»، متد `Place` است. واژه‌های دموی من: order، line، place، pay، ship، cancel.

{{< term "value-object" "value object" >}} تغییرناپذیر است و با مقدار مقایسه می‌شود. `Money` فیلد غیرصادرشده و سازنده‌ی اعتبارسنج دارد، پس `Money == Money` کار می‌کند و مقدار نامعتبر ساخته نمی‌شود. `Add` ترکیب ارزهای متفاوت را رد می‌کند. تست مقدارهای بد هم می‌سازد:

```text
domain_test.go:36: rejected: email: invalid "not-an-email"
```

تعداد صفر و پول منفی هم همین‌طور رد می‌شوند. در مقابل، entity هویت دارد: `Order` با تغییر وضعیت همان سفارش می‌ماند.

## aggregate از قواعد محافظت می‌کند

{{< term "aggregate" "aggregate" >}} مجموعه‌ای است که یکجا تغییر می‌کند و ریشه‌اش قواعد را اجرا می‌کند. `Order` من این‌ها را دارد: بعد از ثبت نمی‌شود خط را عوض کرد، حداکثر ۵۰ خط، جمع کل هرگز منفی نمی‌شود، و یک state machine. `Customer` فقط با `CustomerID` ارجاع داده می‌شود، نه با اشاره‌گر. انتقال غیرمجاز `*IllegalTransition` برمی‌گرداند. تست جدولی هر action را از هر وضعیت امتحان می‌کند (`ok` یعنی مجاز):

```text
          place   pay     ship    cancel  
draft     ok      ERR     ERR     ERR     
placed    ERR     ok      ERR     ok      
paid      ERR     ERR     ok      ok      
shipped   ERR     ERR     ERR     ERR     
cancelled ERR     ERR     ERR     ERR     
```

قاعده‌ی سرانگشتی: یک {{< term "transaction" "تراکنش" >}} برای هر aggregate ([تراکنش و ACID](/fa/posts/db-transactions-acid/)). اگر یک use case باید دو aggregate را عوض کند، احتمالاً مرز غلط است، یا تغییر دوم باید رویداد باشد.

### طراحی بد، اجرا شده

نسخه‌ی anemic فیلدهای صادرشده دارد و قاعده در service است: `AddItem` وضعیت را چک می‌کند. بعداً کسی برای کار import تابع `CopyItems` را اضافه می‌کند و چک را فراموش می‌کند. یک تست می‌گوید سفارش ثبت‌شده هرگز آیتم تازه نمی‌گیرد. آن را پشت build tag گذاشتم تا اجرای معمول سبز بماند و `go test -tags anemic` را اجرا کردم:

```text
--- FAIL: TestNoItemsAfterPlaced (0.00s)
    anemic_test.go:16: placed order gained 1 item(s) through CopyItems
FAIL
```

در `Order` غنی همین وعده برقرار است چون `lines` غیرصادرشده است و `AddLine` تنها در است. تستش می‌گذرد. **به نظر من** این مفیدترین ایده‌ی تاکتیکی است: قاعده را جایی بگذار که هیچ مسیر کدی نتواند از آن بگذرد.

## رویداد، repository و use case

`Place` یک رویداد {{< term "domain-event" "OrderPlaced" >}} را داخل aggregate ثبت می‌کند. interface‌ی `Repository` در بسته‌ی domain است و `MemRepo` در `infra` آن را پیاده می‌کند. application service فقط هماهنگ می‌کند: بخوان، `Place`، ذخیره، بعد انتشار. دو تست با publisher ضبط‌کننده و repo که طبق دستور خطا می‌دهد:

```text
--- PASS: TestPublishAfterSave
--- PASS: TestNoEventWhenSaveFails
```

اگر ذخیره شکست بخورد چیزی منتشر نمی‌شود. این یک fake درون‌حافظه است، نه پایگاه‌داده‌ی واقعی. «ذخیره و انتشار» اتمی روی پایگاه‌داده‌ی واقعی همان [الگوی outbox](/fa/posts/go-outbox-pattern-nats/) است؛ اینجا اجرایش نکردم.

## bounded context

در Sales، `Customer` ایمیل و سقف اعتبار دارد. در Shipping، `Customer` نام و نشانی دارد. این دو نوع در دو بسته‌اند و یک مترجم وصلشان می‌کند:

```go
func FromSales(c sales.Customer, name, address string) shipping.Customer
```

این ایده‌ی {{< term "bounded-context" "bounded context" >}} است: برای هر زبان یک مدل، با ترجمه‌ی صریح میان آن‌ها. همین شکل از سیستم قدیمی هم محافظت می‌کند، مثل پست [کد legacy](/fa/posts/eng-legacy-code/): `FromLegacy` سطری ساختگی با `CustNm` و `Addr1` و `Addr2` می‌گیرد و مشتری تمیز Shipping برمی‌گرداند. این یک {{< term "anti-corruption-layer" "لایه‌ی ضدفساد" >}} است؛ تست `{ID:c2 Name:Bob Address:2 Side Rd}` را لاگ می‌کند.

**به نظر من** بخش راهبردی (contextها، زبان، مالکیت) ارزشمندترین بخش DDD است. الگوهای تاکتیکی اختیاری‌اند. **Event storming** کارگاهی است که در آن آدم‌ها رویدادها را روی دیوار می‌چسبانند تا contextها را پیدا کنند؛ این را می‌شناسم ولی برای این پست اجرا نکردم.

## لایه‌ها را صادق نگه دارید

ساختار: `internal/sales/{domain,app,infra}` و `internal/shipping/{domain,acl}`. یک تست برای هر دو بسته‌ی domain دستور `go list -deps` را اجرا می‌کند و اگر به `net/http`، `database/sql`، `/infra` یا `/app` وابسته باشند شکست می‌خورد. می‌گذرد. بعد عمداً `net/http` را به domain import کردم:

```text
--- FAIL: TestDomainPurity (0.15s)
    arch_test.go:22: ./internal/sales/domain depends on net/http
```

خروجی واقعی چند زیربسته‌ی `net/http/...` را هم فهرست کرد؛ حذفشان کردم. بعد از برگرداندن تغییر، دوباره می‌گذرد.

## چند نکته‌ی مهم

- DDD برای CRUD زیادی است. جدولی با یک فرم aggregate نمی‌خواهد.
- aggregateهای بزرگ رقابت قفل می‌سازند؛ کوچکشان نگه دارید.
- event sourcing و CQRS را اینجا اجرا نکردم.

## تمرین

یک entity سرویس خودتان را بردارید. قواعدش را فهرست کنید، هر کدام را به متدی در ریشه ببرید، فیلدها را غیرصادرشده کنید و تستی بنویسید که اگر قاعده‌ای دور زده شود شکست بخورد.

## قدم بعدی

پست بعدی «monorepo یا polyrepo؟» است.
