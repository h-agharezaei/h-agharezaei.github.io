+++
date = '2027-02-05T10:00:00+03:30'
draft = false
title = 'هرم تست و TDD'
description = 'هرم تست و TDD در Go: red-green-refactor روی یک مثال واقعی، mockهای بیش‌ازحد دقیق، test double، تست flaky و این‌که چرا coverage هدف نیست.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "tdd", "software-engineering", "go"]
cover = { image = "/images/covers/eng-testing-pyramid-tdd.fa.png", alt = "هرم تست و TDD", hiddenInSingle = true }
+++

این مقاله شروع سری Software Engineering است. بخش بزرگی از این سری قضاوت است، نه سینتکس؛ پس نظرهای شخصی را با **نظر من** مشخص می‌کنم و هر ادعا درباره‌ی رفتار کد را با اجرای واقعی نشان می‌دهم. امروز درباره‌ی {{< term "test-pyramid" "هرم تست" >}} و حس {{< term "tdd" "TDD" >}} در عمل می‌گوییم، و چهار راهی که تست‌ها خراب می‌شوند.

مکانیک `go test` در [تست در Go](/fa/posts/go-testing-basics/) آمده و ساختار سرویسی که پایین استفاده می‌کنم از [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/) است. همین ایده‌ها در [node:test](/fa/posts/node-testing-builtin/) و [تست در Rust](/fa/posts/rust-testing-docs/) هم هست.

> همه‌ی دموها با Go 1.26 و `go test -race` اجرا شده‌اند و مثال‌های محلی‌اند.

## هرم تست یک مدل هزینه است

تست واحد زیاد، {{< term "integration-test" "تست یکپارچگی" >}} کمتر، و تست سرتاسری (end-to-end) خیلی کم. دلیلش هزینه است: هرچه تست بالاتر باشد کندتر است، آماده‌سازی بیشتری می‌خواهد و بیشتر بی‌دلیل می‌شکند. در دامنه‌ی سفارش‌ها سه سطح داریم:

- واحد: `cart.Total`، یک تابع خالص بدون I/O؛
- یکپارچگی: `orders.Service` با یک repository ساختگی (fake)، که پایین می‌آید؛
- سرتاسری: یک درخواست HTTP واقعی به سیستم در حال اجرا. اینجا اجرایش نکرده‌ام.

**نظر من:** بیشتر منطق را در توابع خالص بگذارید و آن‌ها را زیاد تست کنید، هر نقطه‌ی اتصال را یک بار با fake تست کنید، و یکی دو تست سرتاسری برای مسیرهایی نگه دارید که پول درمی‌آورند.

## TDD: red، green، refactor

تابع `Total(items, code)` (قیمت‌ها به سنت، با کد تخفیف) را در گام‌های کوچک ساختم. گام ۱: تست سبد خالی. red یک خطای کامپایل است:

```text
cart_test.go:6:14: undefined: Total
```

با برگرداندن ۰ سبز شد. گام ۲: جمع آیتم‌ها؛ شکست از نوع درست است:

```text
--- FAIL: TestTotalSumsItems (0.00s)
    cart_test.go:16: Total = 0, want 1500
```

یک حلقه آن را درست کرد. گام ۳: کد `SAVE10`؛ red (`Total = 1000, <nil>; want 900, nil`) و بعد یک `if code == "SAVE10"` ساده: green. گام ۴: کد ناشناخته باید `ErrUnknownCode` بدهد؛ red و بعد یک `else if`. گام ۵، refactor: زنجیره‌ی `if` به map تبدیل شد و یک تست `SAVE25` اضافه شد:

```go
var discounts = map[string]int{"SAVE10": 10, "SAVE25": 25}

percent, ok := discounts[code]
if !ok {
	return 0, ErrUnknownCode
}
return sum * (100 - percent) / 100, nil
```

```text
=== RUN   TestTotalEmpty
--- PASS: TestTotalEmpty (0.00s)
=== RUN   TestTotalSumsItems
--- PASS: TestTotalSumsItems (0.00s)
=== RUN   TestTotalWithDiscountCode
--- PASS: TestTotalWithDiscountCode (0.00s)
=== RUN   TestTotalUnknownCode
--- PASS: TestTotalUnknownCode (0.00s)
=== RUN   TestTotalSecondCode
--- PASS: TestTotalSecondCode (0.00s)
PASS
```

refactor امن بود چون تست‌ها از قبل بودند. **نظر من:** TDD را برای منطقی با قانون روشن (قیمت‌گذاری، parse) به کار می‌برم، نه برای کاوش در یک API ناشناخته.

## Test double: stub، fake، mock

{{< term "test-double" "Test double" >}} جای یک وابستگی را می‌گیرد. برای interface مربوط به `Repository` از هر نوع یکی نوشتم (به {{< term "dependency-injection" "تزریق وابستگی" >}} نگاه کنید):

- **Stub**: جواب‌های از پیش تعیین‌شده. `failingRepo{err}` از `Save` خطا برمی‌گرداند و تست می‌بیند سرویس آن را بالا می‌فرستد.
- **Fake**: یک پیاده‌سازی ساده ولی واقعاً کارکن، اینجا یک map. تست سفارش می‌دهد و دوباره می‌خواندش.
- **Mock**: فراخوانی‌ها را ثبت می‌کند تا تست راستی‌آزمایی کند. وقتی خودِ فراخوانی نتیجه است (ایمیل فرستاده شد) به کار می‌آید، وگرنه پرخطر است.

## تست بیش‌ازحد دقیق

کنار تست مبتنی بر fake، یک تست mock نوشتم که دنباله‌ی فراخوانی `[Count Save]` را ثابت می‌کند. هر دو سبز بودند. بعد `Place` را refactor کردم تا شناسه‌ها را با شمارنده‌ی داخل سرویس بسازد و از repository نخواهد بشمارد (جایگزینی برای یک تغییر داخلی بی‌خطر؛ این طراحی را خودم منتشر نمی‌کنم). رفتار بیرونی عوض نشد:

```text
--- PASS: TestPlaceStoresOrder (0.00s)
--- PASS: TestPlaceReturnsSaveError (0.00s)
    service_test.go:42: calls = [Save], want [Count Save]
--- FAIL: TestPlaceCallSequence (0.00s)
```

تست mock شکست خورد و تست‌های رفتاری نه. **نظر من:** چیزی را assert کنید که فراخواننده می‌بیند، نه مسیری که کد برای رسیدن به آن رفته.

## یک تست flaky

این تست فرض می‌کند ۱ms کار هیچ‌وقت بیشتر از ۱.۲۵ms طول نمی‌کشد، آن هم روی sessionی که واقعاً از `time.Now` استفاده می‌کند:

```go
s := New(1250 * time.Microsecond)
time.Sleep(time.Millisecond) // the "work"
if s.Expired() { t.Fatal("session expired too early") }
```

`go test -count=50` را چهار بار روی لپ‌تاپی که زیر بار بود (load average حدود ۵) اجرا کردم: ۰، ۸، ۱ و ۰ شکست. کد یکی، نتیجه‌ها متفاوت؛ تعریف {{< term "flaky-test" "تست flaky" >}} همین است. راه‌حل تزریق ساعت است (`New(ttl, now func() time.Time)`) و جلو بردن یک ساعت ساختگی با دست. سه بار اجرای `-race -count=50` همه سبز شد، چون دیگر چیزی به زمان واقعی وابسته نیست.

## Coverage یک نشانه است

```go
func BulkPrice(unit, qty int) int {
	if qty >= 10 {
		return unit * qty * 10 / 100 // bug: should be * 90 / 100
	}
	return unit * qty
}
```

تستی که فقط `BulkPrice(100, 1)` و `BulkPrice(100, 10)` را بدون assert صدا می‌زند `coverage: 100.0% of statements` می‌دهد و باگ زنده می‌ماند. با یک assert:

```text
price_test.go:12: BulkPrice(100, 10) = 100, want 900
```

{{< term "code-coverage" "Coverage" >}} می‌گوید چه چیزی هرگز اجرا نشده؛ نمی‌گوید چه چیزی راستی‌آزمایی شده.

## چند نکته‌ی مهم

- مگر خودِ تعامل الزام باشد، به‌جای mock از fake و stub استفاده کنید.
- تست flaky را باگ بدانید، نه نویز. زمان و تصادف را با تزریق حذف کنید.
- درصد coverage را هدف نکنید.
- TDD ابزار است؛ refactor زیر تست‌های سبز بخشی است که حتی اگر بقیه را کنار بگذارم نگهش می‌دارم.

## تمرین

کد `FREESHIP` را اضافه کنید که فقط برای جمع بالای ۵۰۰۰ سنت معتبر است، با red-green-refactor. بعد یک تست mock و یک تست fake برایش بنویسید، اسم یک helper داخلی را عوض کنید و ببینید کدام‌یک می‌شکند.

## قدم بعدی

مقاله‌ی بعدی «تست خاصیت‌محور» است؛ جایی که خود کامپیوتر ورودی‌های تست را می‌سازد.
