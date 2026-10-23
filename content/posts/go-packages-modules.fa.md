+++
date = '2026-11-18T10:00:00+03:30'
draft = false
title = 'پکیج‌ها و ماژول‌ها: ساختار پروژه‌ی Go'
description = 'پکیج و ماژول در Go چطور کار می‌کنند: نام‌های exported، internal/، ترتیب init، import cycle، go.mod و go.sum و یک ساختار پروژه‌ی معقول، با خروجی واقعی.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "modules", "packages"]
cover = { image = "/images/covers/go-packages-modules.fa.png", alt = "پکیج‌ها و ماژول‌ها: ساختار پروژه‌ی Go", hiddenInSingle = true, hiddenInList = true }
+++

تا اینجا همه‌ی مثال‌ها در یک فایل جا می‌شدند. پروژه‌ی واقعی جا نمی‌شود و Go برای تقسیم‌کردنش دو مفهوم دارد که معمولاً با هم قاطی می‌شوند. بعد از [اشاره‌گرها و مدل حافظه](/fa/posts/go-pointers-memory/)، در این مقاله یک پروژه‌ی کوچک چندپکیجی می‌سازیم و می‌بینیم کامپایلر چه چیزهایی را اجباری می‌کند: دسترسی، `internal/`، ترتیب مقداردهی اولیه، import cycle و وابستگی‌های بیرونی.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام.

## پکیج در برابر ماژول

**پکیج** (package) یک دایرکتوری از فایل‌های `.go` است که همه خط `package name` یکسان دارند؛ واحد کامپایل و واحد دسترسی است. **ماژول** (module) درختی از پکیج‌هاست که با هم نسخه‌بندی می‌شوند و با فایل `go.mod` در ریشه‌اش توصیف می‌شود. module path داخل `go.mod` پیشوند همه‌ی import pathهای درون آن ماژول است.

ماژول نمونه‌ی ما `example.com/shop` است:

```
shop/
  go.mod                  // module example.com/shop
  cmd/app/main.go         // package main
  internal/store/store.go // package store
  internal/audit/audit.go // package audit
  pkg/slug/slug.go        // package slug
```

import path برابر است با module path به‌علاوه‌ی دایرکتوری: `example.com/shop/internal/store`. نام دایرکتوری و نام پکیج معمولاً یکی‌اند، اما فقط دایرکتوری جزو path است. تا وقتی آزمایش می‌کنید module path لازم نیست آدرس واقعی باشد؛ برای کتاب‌خانه‌ای که منتشر می‌کنید همان آدرس repository است.

## exported و unexported

نامی که با حرف بزرگ شروع شود exported است و هر نام دیگری فقط داخل پکیج خودش دیده می‌شود. کلیدواژه‌ی `public` یا `private` وجود ندارد. در `slug` تابع `Make` (exported) و `clean` (unexported) را داریم. استفاده از `clean` از ماژولی دیگر:

```go
import "example.com/shop/pkg/slug"

func main() { _ = slug.clean(" x ") }
```

```
$ go build .
./main.go:5:24: undefined: slug.clean
```

پیام می‌گوید `undefined`، نه «unexported»، که اول کمی گیج‌کننده است. اگر این خطا را دیدید املای بزرگ/کوچک حرف اول را چک کنید.

## قاعده‌ی `internal/`

پکیجی که زیر دایرکتوری‌ای به نام `internal` باشد فقط توسط کدی قابل import است که ریشه‌اش والدِ آن `internal` است. اینجا والد، ریشه‌ی `example.com/shop` است. ماژولی دیگر که بخواهد `store` را import کند:

```
$ go build .
package example.com/outsider
	main.go:3:8: use of internal package example.com/shop/internal/store not allowed
```

این را toolchain اجباری می‌کند، نه قرارداد. با آن جزئیات پیاده‌سازی را خصوصی نگه می‌دارید و در عین حال داخل ماژول آزادانه به اشتراک می‌گذارید.

## `init()` و ترتیب مقداردهی اولیه

هر پکیج اول متغیرهای سطح پکیج را مقدار می‌دهد، بعد تابع‌های `init()` را اجرا می‌کند (یک پکیج می‌تواند چند `init` داشته باشد؛ به ترتیبی که فایل‌ها و تعریف‌ها به کامپایلر داده می‌شوند). پکیج فقط بعد از همه‌ی پکیج‌هایی که import می‌کند مقداردهی می‌شود و `main` آخر اجرا می‌شود. `main` ما `store` و `slug` را import می‌کند و `store` هم `audit` را:

```
$ go run ./cmd/app
var: audit.Prefix
init: audit
init: store (first)
init: store (second)
init: slug
init: main
main starts
[audit] added Blue Mug
1 blue-mug
```

`audit` قبل از `store` اجرا شد چون `store` به آن وابسته است و همه‌چیز پیش از شروع `main` تمام شد. ترتیب نسبی پکیج‌های مستقل از هم (اینجا `store` و `slug`) چیزی نیست که رویش حساب کنم. در کل از منطق پیچیده در `init()` پرهیز کنید: ضمنی اجرا می‌شود، نمی‌تواند error برگرداند و تست‌کردنش سخت است. سازنده‌ی صریح مثل `store.New()` بهتر است.

## import cycle خطاست

اگر `a` پکیج `b` را import کند و `b` هم `a` را، Go کامپایل نمی‌کند:

```
$ go build ./...
package example.com/cyc/a
	imports example.com/cyc/b from a.go
	imports example.com/cyc/a from b.go: import cycle not allowed
```

راه‌حل معمول این است که type مشترک را به پکیج سومی ببریم، یا interface را در پکیجی تعریف کنیم که به آن رفتار نیاز دارد، به‌جای import کردن پکیج پیاده‌ساز. cycle اغلب علامت این است که مرز پکیج‌ها جای درستی نیست.

## افزودن وابستگی بیرونی

در `main.go` پکیج `github.com/google/uuid` را import کردم و `go mod tidy` را اجرا کردم؛ این دستور requirementهای جاافتاده را اضافه و موارد بی‌استفاده را حذف می‌کند. یک نکته‌ی صادقانه: proxy ماژولِ تنظیم‌شده‌ی من با خطای TLS handshake timeout شد، پس با `GOPROXY=off` و `GOSUMDB=off` و نسخه‌ی `v1.6.0` که از قبل در module cache محلی بود اجرا کردم. روی اتصال سالم همان `go mod tidy` کافی است و بهتر است بررسی checksum روشن بماند. نتیجه:

```
$ cat go.mod
module example.com/shop

go 1.26

require github.com/google/uuid v1.6.0

$ cat go.sum
github.com/google/uuid v1.6.0 h1:NIvaJDMOsjHA8n1jAhLSgzrAzy1Hgr+hNrb57e+94F0=
github.com/google/uuid v1.6.0/go.mod h1:TIyPZe4MgqvfeYDBFedMoGGpEw/LqOeaOT+nhxU+yHo=

$ go list -m all
example.com/shop
github.com/google/uuid v1.6.0
```

`go.mod` ثبت می‌کند چه چیزی لازم دارید. `go.sum` هش‌های رمزنگاری‌شده‌ی همان نسخه‌ها را نگه می‌دارد تا build بعدی بفهمد دانلود تغییر کرده یا نه؛ هر دو فایل را commit کنید. `go list -m all` کل وابستگی‌ها را نشان می‌دهد، از جمله indirectها (اینجا هیچ‌کدام نیست).

## ساختار پیشنهادی بدون جزم‌اندیشی

- با `main.go` و `go.mod` شروع کنید. جدی می‌گویم: ابزار کوچک بیشتر نمی‌خواهد.
- وقتی ماژول بیش از یک باینری دارد یا می‌خواهید `main` نازک بماند، `cmd/<name>/main.go` اضافه کنید.
- کدی که نمی‌خواهید دیگران import کنند زیر `internal/` بگذارید.
- پکیج را وقتی بسازید که هدف روشن و اسمی یک‌کلمه‌ای دارد، نه چون نمودار قشنگ شده است.
- `pkg/` اختیاری است. بعضی پروژه‌ها برای کتاب‌خانه‌های قابل import استفاده‌اش می‌کنند و خیلی‌ها نه. هیچ ساختاری را مقدس نکنید.

## چند نکته‌ی احتیاط

- ساختار بیش‌ازحد رایج‌ترین تله‌ی مبتدی‌هاست: ده پکیج با یک تابع باعث cycle و importهای زشتی مثل `utils` و `common` می‌شود.
- نام پکیج کوتاه، با حروف کوچک و مفرد باشد و در نام‌ها تکرار نشود (`store.Store` خوب است، `store.StoreItem` تکرار است).
- تغییر حرف اول یک نام، API عمومی شما را عوض می‌کند؛ نام exported یعنی تعهد.
- `go.sum` را دستی ویرایش نکنید؛ به `go mod tidy` بسپارید.
- کار سنگین در `init()` نکنید.

## تمرین

۱. پکیج `internal/config` با تابع exported `Load() Config` بسازید و از `main` استفاده کنید. ترتیب چاپ `init`ها را ببینید.
۲. عمداً یک import cycle بسازید و خطایش را بخوانید.
۳. وابستگی دیگری اضافه کنید، `go mod tidy` بزنید و `go.mod` و `go list -m all` را قبل و بعد مقایسه کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ چیزی می‌رویم که Go بیشتر به آن شناخته می‌شود: goroutine و channel، و اینکه چطور کارها را هم‌زمان اجرا کنیم بی‌آنکه درهم بپیچند.
