+++
date = '2027-05-21T10:00:00+03:30'
draft = false
title = 'کار با کد legacy'
description = 'کار با کد legacy در Go: کاوش با git و coverage، ثبت رفتار با تست golden، ساخت seam، رفع باگ و جایگزینی تدریجی با strangler در shadow mode.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["legacy-code", "refactoring", "golden-master", "strangler-fig", "software-engineering", "go"]
cover = { image = "/images/covers/eng-legacy-code.fa.png", alt = "کار با کد legacy", hiddenInSingle = true }
+++

پست قبل، [postmortem بدون سرزنش](/fa/posts/eng-postmortems-blameless/)، به action itemها رسید و خیلی‌هایشان در کدی می‌افتند که کسی جرأت دست زدن به آن را ندارد. تعریف کاری من: {{< term "legacy-code" "کد legacy" >}} کدی است که تست ندارد (ایده از کتاب *Working Effectively with Legacy Code* نوشته‌ی مایکل فدرز است). مرتبط: [refactoring امن](/fa/posts/eng-refactoring-safely/)، [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/)، [تست در Go](/fa/posts/go-testing-basics/).

**پکیج «legacy» ساخته‌ی خودم است**: 80 خط، global state، `time.Now`، `os.Getenv`، یک باگ پنهان و 12 commit ساختگی (Go 1.26، دموی محلی). خروجی‌ها اجرای واقعی‌اند و نظرها مشخص شده‌اند.

## 1. قبل از تغییر، بفهمید

کد `country|sku:qty,...` را parse می‌کند، قیمت می‌زند و به یک `Ledger` سراسری اضافه می‌کند. اول فقط خواندن:

```text
$ git blame -L '/q > 10/,+1' shop.go
3a6b62b6 (Dev C 2026-04-14 10:00:00 +0000 42) 		if q > 10 {
$ git log -L '/q > 10/,+1:shop.go' -s --format='%h %an %s'
3a6b62b Dev C tweak bulk threshold
0c05928 Dev B bulk discount
798d5ea Dev A first version of pricing
$ go vet ./...            # clean
$ go test -cover ./...
	example.com/legacy		coverage: 0.0% of statements
```

`git log -L` یک خط را در تاریخچه دنبال می‌کند. کامنت می‌گوید «10 or more» ولی commit «tweak bulk threshold» از `>=` به `>` رفته: سرنخ است، نه حکم. `go vet` ساکت است و coverage برابر 0.0% نقطه‌ی شروع واقعی است. `go list -f '{{.Imports}}'` پکیج‌های `time` و `os` را نشان می‌دهد: ورودی‌های پنهان ساعت و محیط‌اند.

## 2. اول رفتار را ثبت کنید

{{< term "characterization-test" "تست characterization" >}} آنچه کد انجام می‌دهد را با باگ‌هایش ثبت می‌کند. ساعتِ غیرقابل‌کنترل این را ناممکن می‌کند، پس اولین ویرایش یک خط است: `var now = time.Now`، یک {{< term "seam" "seam" >}}. تست 120 ورودی seed‌دار را در سه حالت (جمعه، دوشنبه، `SHOP_TAX=7`) با `testdata/golden.txt` مقایسه می‌کند؛ `go test -update` بازنویسی‌اش می‌کند:

```text
$ go test -update ./... && go test -race -cover ./...
ok  	example.com/legacy	1.330s	coverage: 97.6% of statements
```

نسخه‌ی اول فقط مقدار برگشتی را ثبت می‌کرد. بعد `discountLog` سراسری را اضافه کردم، روی commit قدیمی دوباره ثبت کردم و مرحله‌ی بعدی refactoring شکست خورد (`apple:7` به‌جای `apple:9`): شمارش آیتم‌های قبل از خطای parse را حذف کرده بودم. **globalها هم خروجی‌اند.**

## 3. seam، هر بار یک ویرایش

مرحله‌های کوچک، هر بار `go test -race`:

- `var getenv = os.Getenv`.
- استخراج `parse` و یک `compute(country, items, friday, taxPct)` خالص؛ `Process` اثرهای جانبی را نگه می‌دارد.
- `var record = func(country string, total float64){...}` برای ledger، همان «دیتابیس».

```text
ok  	example.com/legacy	1.317s      # getenv
ok  	example.com/legacy	1.489s      # parse + compute
ok  	example.com/legacy	1.451s	coverage: 97.9% of statements   # record
```

این همان {{< term "dependency-injection" "dependency injection" >}} با کمترین تشریفات است. **نظر من:** در ابتدا متغیر تابعی کافی است؛ interface بعداً هم می‌شود.

## 4. باگ را بعد از ثبت‌شدنش درست کنید

تغییر `bulk` به `q >= 10` تست golden را شکست می‌دهد، که درست است:

```text
--- FAIL: TestGolden
         got  fri	XX|fig:10,melon:6	TOTAL=40.94
         want fri	XX|fig:10,melon:6	TOTAL=41.54
```

بعد `go test -update` چهل خط golden را بازنویسی کرد: 37 سفارش که هر کدام آیتمی با تعداد دقیقاً 10 داشت و 3 خط خلاصه. diff را خواندم و کد و golden را با هم commit کردم. تست هرگز نگفت چه چیزی درست است؛ من گفتم.

## 5. sprout و wrap

برای رفتار جدید به گره دست نزنید. **sprout** یک تابع جدید و تست‌شده است (`ApplyCoupon` با پنج حالت جدول)؛ **wrap** دور تابع قدیمی می‌پیچد (`ProcessAudited` تابع `Process` را صدا می‌زند و بعد hook به نام `audit`). کوپن را به `Process` وصل نکردم.

## 6. strangler fig

برای جایگزینی بزرگ‌تر، الگوی {{< term "strangler-fig" "strangler fig" >}} (از توصیفی از مارتین فاولر، آن‌طور که یادم هست) یک router جلوی کد می‌گذارد. `ProcessV2` از سنت صحیح و بدون global استفاده می‌کند. در {{< term "shadow-mode" "shadow mode" >}} router پاسخ قدیمی را برمی‌گرداند و تفاوت‌ها را روی 10,000 ورودی seed‌دار (یک دوشنبه) می‌شمارد:

```text
inputs=10000 mismatches=3051 (one cent apart: 3040, other: 11, error-vs-total: 0)
served by new: 2141 of 10000 at SHOP_ROUTE=20
```

خطاها یکی‌اند. مبلغ فرق دارد چون legacy برش می‌دهد (`int(total*100)`) و v2 در هر مرحله گرد می‌کند؛ 11 مورد دیگر دو سنت اختلاف دارند. قابل‌قبول بودن یک سنت روی 30٪ سفارش‌ها تصمیم کسب‌وکار است. `SHOP_ROUTE` (مقدار `shadow` یا 0 تا 100) یک {{< term "feature-flag" "feature flag" >}} است و هم‌شکل بودن تابع دو پیاده‌سازی یک {{< term "branch-by-abstraction" "branch by abstraction" >}} سبک است ([feature flag و trunk-based development](/fa/posts/eng-feature-flags-trunk-based/)). سهم 20 تعداد 2141 فراخوانی را به مسیر جدید برد (انتخاب با hash ورودی).

## 7. کد مرده را پاک کنید

`go tool cover -func` تابع `oldTax` را روی 0.0% نشان داد، grep هیچ فراخواننده‌ای پیدا نکرد و با سبز بودن تست‌ها آن را پاک کردم. **staticcheck را اجرا نکردم**، که ابزار معمول این کار است.

## rewrite یا refactor؟ (نظر)

جوئل اسپولسکی مقاله‌ی معروفی علیه بازنویسی از صفر نوشته؛ با کلیت آن موافقم. بازنویسی ریزه‌کاری‌هایی را که کد یاد گرفته (مثل برش سنت) دور می‌ریزد و طبق تجربه‌ام بازنویسی‌های بزرگ کمتر تمام می‌شوند. ماژول‌های کوچک با قرارداد روشن استثنا هستند.

## کار تیمی (نظر)

کد را هر بار کمی بهتر برگردانید (قاعده‌ی boy scout)، یافته‌ها را در [ADR](/fa/posts/eng-adr-documentation/) بنویسید و پاکسازی ناتمام را [بدهی فنی](/fa/posts/eng-technical-debt/) ثبت کنید.

## چند نکته‌ی مهم

- coverage فقط می‌گوید چه اجرا شد.
- همه‌ی خروجی‌ها را ثبت کنید: مقدار برگشتی، globalها، فایل‌ها.
- هر مرحله یک تغییر.
- در commit مربوط به refactoring هرگز باگ را درست نکنید.

## تمرین

`ApplyCoupon` را با یک فیلد سوم در ورودی به `Process` وصل کنید. کدام خط‌های golden عوض می‌شوند و آیا باید عوض شوند؟

## قدم بعدی

پست بعدی «مبانی DDD» است.
