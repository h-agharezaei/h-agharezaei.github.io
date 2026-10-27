+++
date = '2027-03-03T10:00:00+03:30'
draft = false
title = 'refactor امن'
description = 'refactor امن در Go: ثبت رفتار کد legacy با تست golden-master، تغییر در گام‌های کوچک، گرفتن یک اشتباه تک‌نویسه و تغییر امضای تابع به روش parallel change.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["refactoring", "testing", "legacy-code", "software-engineering", "go"]
cover = { image = "/images/covers/eng-refactoring-safely.fa.png", alt = "refactor امن", hiddenInSingle = true }
+++

در پست قبل، [تست خاصیت‌محور](/fa/posts/eng-property-based-testing/)، کد را با قاعده‌هایش توصیف کردیم. امروز کد قاعده‌ی نوشته‌شده‌ای ندارد، فقط رفتار دارد. {{< term "refactoring" "refactor" >}} یعنی تغییر ساختار بدون تغییر رفتار، و این قول را بدون تستی که رفتار را از قبل ثابت کند نمی‌شود داد. عادت گام‌های کوچک سبز در {{< term "tdd" "TDD" >}} اینجا هم می‌آید؛ مبانی تست: [تست در Go](/fa/posts/go-testing-basics/). قضاوت‌ها با **نظر من** مشخص شده‌اند و بقیه‌ی چیزها اجرا شده‌اند.

> Go 1.26 و `go test -race`، مثال محلی؛ تابع legacy را خودم ساخته‌ام.

## تابع legacy

`PriceOrder(qty, unit, tier, coupon, country, express)` جمع کل را به سنت برمی‌گرداند، یا برای ورودی نامعتبر -1. ۸۹ خط `if`/`else` تو در تو با عددهای جادویی: تخفیف حجمی از ۱۰ و ۵۰ عدد، امتیاز tier، سه کوپن، مالیات هر کشور، ارسال و قاعده‌ای که هر جمعی را که به ۹ ختم شود یکی بالا می‌برد. چند عجیب‌گی هم عمداً کاشته‌ام: امتیاز gold از ۵۰ عدد به بالا ناپدید می‌شود و فقط آلمان مالیات را رو به بالا گرد می‌کند.

## گام صفر: اول characterization

قبل از دست زدن، یک {{< term "characterization-test" "تست characterization" >}} نوشتم: ۳۰۰۰ ورودی از `rand.NewSource(42)`، هر خروجی در `testdata/golden.txt`، هر مورد یک خط:

```text
50 2143 "basic" "HALF" "DE" true => 111027
```

تست خطوط را دوباره می‌سازد و مقایسه می‌کند. ضبط با `go test -run Golden -update .` یک بار روی کد دست‌نخورده انجام شد:

```text
$ go test -race -cover .
ok  	example.com/pricing	1.351s	coverage: 100.0% of statements
```

عجیب‌گی‌ها هم عمداً ثبت می‌شوند. **نظر من:** فایل golden عکس است، نه spec؛ این که یک رفتار باگ هست یا نه بعداً تصمیم گرفته می‌شود.

## گام ۱ تا ۳: حرکت‌های کوچک، تست بعد از هرکدام

هر گام یک commit بود؛ بعد از هرکدام `go vet` و تست golden اجرا شد.

1. **بازنویسی مکانیکی با `gofmt -r`**: دستور `gofmt -r 'a * b / 100 -> percentOf(a, b)' -w price.go` چهار عبارت را عوض کرد (۶ خط اضافه، ۴ حذف). الگو باید عبارت باشد: `a = a + b` با خطای `expected '=='` رد شد.
2. **early return و `switch`**: هرم `else { if ... }` به guard و switch تبدیل شد (۶۰ خط اضافه، ۷۸ حذف).
3. **استخراج و نام‌گذاری**: `discountPercent`، `couponOff`، `taxFor`، `shipping` و ثابت‌هایی مثل `wholesaleQty = 50` و `halfCouponCap = 2000` (۷۳ خط اضافه، ۳۵ حذف).

همه سبز ماند و عجیب‌گی‌ها ماندند.

## ساده‌تر شد؟

`gocyclo` را اینجا اجرا نکردم: دانلود و اجرایش در این محیط مسدود شد، پس خروجی‌اش را ندارم. یک شمارنده‌ی کوچک با `go/ast` و همان قاعده نوشتم ({{< term "cyclomatic-complexity" "پیچیدگی سیکلوماتیک" >}} یعنی یک به‌علاوه‌ی هر `if`، `for`، `case` غیر default، `&&` و `||`). این عددها از آن قاعده‌اند، نه از gocyclo:

```text
before: PriceOrder 26
after:  Price 7, discountPercent 7, couponOff 6, taxFor 5, shipping 5, percentOf 1
```

بدترین تابع از ۲۶ به ۷ رسید؛ منطق همان است، فقط به تکه‌های خواندنی تقسیم شده.

## شبکه‌ی ایمنی یک اشتباه را می‌گیرد

یک نویسه را عوض کردم، `>=` به `>` در شرط wholesale، و تست golden را اجرا کردم:

```text
--- FAIL: TestGolden (0.00s)
    golden_test.go:49: case 76 differs:
          want 50 2143 "basic" "HALF" "DE" true => 111027
          got  50 2143 "basic" "HALF" "DE" true => 119954
```

اولین ورودی متفاوت را نشان می‌دهد. اشتباه دوم، `+ 50` به `+ 49` در گرد کردن آلمان، در مورد ۵۹ شکست خورد (`5081` در برابر `5080`). هر دو برگردانده شدند.

## Parallel change برای امضای تابع

شش پارامتر پشت‌سرهم بوی بد می‌داد و `Price(Order)` می‌خواستم. با فراخواننده‌های زیاد نمی‌شود همه را یک‌جا عوض کرد. {{< term "expand-contract" "Parallel change (expand/contract)" >}} آن را در چهار commit سبز انجام می‌دهد؛ نسخه‌ی دیتابیسی همین ایده در [migration بدون downtime](/fa/posts/db-zero-downtime-migrations/) است:

```go
// Expand: add the new API, make the old one a thin wrapper.
// Deprecated: use Price.
func PriceOrder(qty, unit int, tier, coupon, country string, express bool) int {
	return Price(Order{qty, unit, tier, coupon, country, express})
}
```

بعد فراخواننده‌ها را یکی‌یکی منتقل کردم و آخر contract: حذف `PriceOrder` و به‌روز کردن تست. فایل golden بعد از ساخته شدن عوض نشد (`git diff --stat` خالی). محدودیت: سه فراخواننده‌ی دمو را تست golden پوشش نمی‌دهد؛ در پروژه‌ی واقعی اول باید برایشان تست نوشت.

## refactor یا بازنویسی؟

**نظر من:** refactor را ترجیح بدهید. شاهدش فایل golden است: ۳۰۰۰ خط آن رفتار دقیق کد قدیمی است، با عجیب‌گی‌هایی که شاید کسی به آن‌ها تکیه کرده. بازنویسی از spec توی ذهن آدم‌ها شروع می‌کند و این‌ها را از دست می‌دهد.

## چند نکته‌ی مهم

- commit مربوط به refactor را از commit تغییر رفتار جدا نگه دارید (**توصیه‌ی من**)؛ reviewer می‌تواند «چیزی عوض نشده» را مکانیکی بررسی کند.
- فایل golden به اندازه‌ی ورودی‌هایش خوب است. ۱۰۰٪ پوشش statement درباره‌ی مرزها چیز زیادی نمی‌گوید؛ {{< term "mutation-testing" "تست جهش" >}} این را بهتر می‌سنجد (اینجا اجرایش نکردم).
- seed را ثابت کنید و خروجی map را مرتب کنید، وگرنه فایل golden پرش می‌کند.
- عجیب‌گی را وسط refactor «درست» نکنید؛ در commit خودش تغییرش دهید.
- تست {{< term "regression" "regression" >}} یک باگ شناخته‌شده را نگه می‌دارد؛ تست characterization همه‌چیز را.

## تمرین

تابعی را از کد خودتان بردارید که کسی دلش نمی‌خواهد دست بزند. ۵۰۰ ورودی با seed ثابت در فایل golden ضبط کنید، یک تابع استخراج کنید، تست را اجرا کنید، بعد یک عملگر را خراب کنید و پیام شکست را بخوانید.

## قدم بعدی

پست بعدی «code review مؤثر» است.
