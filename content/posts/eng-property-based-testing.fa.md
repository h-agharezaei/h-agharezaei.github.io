+++
date = '2027-02-19T10:00:00+03:30'
draft = false
title = 'تست خاصیت‌محور'
description = 'تست خاصیت‌محور در Go با testing/quick و rapid: shrinking تا کوچک‌ترین مثال نقض، تست مبتنی بر مدل، یک باگ واقعی در Dedupe و fuzzing در Go.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "property-based-testing", "software-engineering", "go"]
cover = { image = "/images/covers/eng-property-based-testing.fa.png", alt = "تست خاصیت‌محور", hiddenInSingle = true }
+++

در [هرم تست و TDD](/fa/posts/eng-testing-pyramid-tdd/) هر تست یک مثال بود: یک ورودی و یک خروجی مورد انتظار. مثال‌ها خوانا هستند ولی فقط حالت‌هایی را می‌سنجند که من به ذهنم رسیده. {{< term "property-based-testing" "تست خاصیت‌محور" >}} قاعده‌ای می‌نویسد که باید برای همه‌ی ورودی‌ها برقرار باشد و ساختن ورودی‌ها را به ماشین می‌سپارد. مبانی `go test` در [تست در Go](/fa/posts/go-testing-basics/) آمده و جدولی که پایین تست می‌کنم از [hash table از صفر](/fa/posts/algo-hash-tables/) است.

> دموها با Go 1.26، `go test -race` و `pgregory.net/rapid` نسخه‌ی v1.3.0 اجرا شده‌اند و مثال‌های محلی‌اند.

## خاصیت در برابر مثال

مثال: `Reverse([1,2,3]) == [3,2,1]`. خاصیت: برای هر slice مثل `s`، `Reverse(Reverse(s))` برابر `s` است و طول عوض نمی‌شود. کتابخانه‌ی استاندارد `testing/quick` را دارد:

```go
f := func(s []int) bool { return slices.Equal(Reverse(Reverse(s)), s) }
if err := quick.Check(f, nil); err != nil { t.Error(err) }
```

پاس می‌شود، اما `testing/quick` شکست را کوچک نمی‌کند و کنترل کمی به شما می‌دهد. برای بقیه از `rapid` استفاده می‌کنم:

```go
rapid.Check(t, func(t *rapid.T) {
	s := rapid.SliceOf(rapid.Int()).Draw(t, "s")
	got := InsertionSort(s)
	if !slices.IsSorted(got) { t.Fatal("not ordered") }
	want := slices.Clone(s); slices.Sort(want)
	if !slices.Equal(got, want) { t.Fatal("different elements") }
	if !slices.Equal(InsertionSort(got), got) { t.Fatal("not idempotent") }
})
```

این سه خاصیت کلاسیک مرتب‌سازی است: مرتب بودن، عناصر یکسان، و idempotent بودن. ابزار پرکاربرد دیگر رفت‌وبرگشت (round trip) است: `Decode(Encode(v)) == v` برای هر `uint64` روی varint دست‌نویس من. هر دو پاس شدند:

```text
props_test.go:57: [rapid] OK, passed 100 tests
```

## باگی که مثال‌ها ندیدند

`Dedupe` باید تکراری‌ها را حذف کند و اولین رخدادها را با همان ترتیب نگه دارد. نسخه‌ی اول من هر مقدار را فقط با آخرین مقدار نگه‌داشته‌شده مقایسه می‌کرد. تست‌های مثالی (`nil`، `[1]`، `[1,1,2]`، `[1,2,3]`) همه پاس می‌شوند. خاصیت «خروجی تکراری ندارد و چیزی گم نشده» روی عددهای کوچک آن را پیدا می‌کند:

```text
--- FAIL: TestDedupeProps (0.03s)
    props_test.go:94: [rapid] failed after 0 tests: duplicate 0 in [0 1 0]
        To reproduce, specify -run="TestDedupeProps" -rapid.failfile="testdata/rapid/TestDedupeProps/TestDedupeProps-20261027092037-19116.fail" (or -rapid.seed=11724099063003310201)
    props_test.go:95: [rapid] draw s: []int{0, 1, 0}
```

این همان {{< term "shrinking" "shrinking" >}} است: rapid یک slice تصادفی خراب را به `[0 1 0]` رساند، کوچک‌ترین ورودی که هنوز شکست می‌خورد. با دادن `-rapid.seed` یا `-rapid.failfile` که چاپ شده، همان حالت دقیقاً دوباره اجرا می‌شود (هر دو را اجرا کردم و همان شکست را دیدم). فایل `testdata/rapid` را commit کنید تا تست رگرسیون شود.

نکته: `testing/quick` با ۱۰٬۰۰۰ `[]int` تصادفی روی تابع خراب **پاس شد**. عددهای ۶۴ بیتی تصادفی تقریباً هرگز تکرار نمی‌شوند، پس هیچ‌وقت تکراری ساخته نشد. generator مهم است؛ من rapid را به `IntRange(0, 5)` محدود کردم تا برخورد زیاد باشد. بعد از تغییر به map از `seen`، خاصیت پاس می‌شود.

## تست مبتنی بر مدل

برای کد دارای state، دنباله‌های تصادفی از عملیات را روی نسخه‌ی واقعی و روی یک مدل ساده اجرا کنید. جدول open-addressing من در برابر `map[int]int`، با `put`، `get`، `delete` و بررسی این‌که `Len` یکی است:

```go
t.Repeat(map[string]func(*rapid.T){
	"put":    func(t *rapid.T) { /* m.Put(k,v); model[k]=v */ },
	"delete": func(t *rapid.T) { /* compare return value, then delete(model,k) */ },
	"get":    func(t *rapid.T) { /* compare value and ok */ },
	"":       func(t *rapid.T) { /* m.Len() == len(model) */ },
})
```

`Delete` جدول (با tombstone) روی ۱۰۰ دنباله پاس شد. اما `DeleteNaive` همان مقاله، که راه غلط نشان داده بودم، شکست می‌خورد و به چهار گام کوچک می‌شود:

```text
[rapid] failed after 8 tests: Len 2 != model 1
  put k=1; put k=17; delete k=1; put k=17
```

کلیدهای ۱ و ۱۷ برخورد دارند، حذف ۱ زنجیره‌ی probe را می‌شکند و `put 17` دوم یک تکراری درج می‌کند. این مثال را دستی نمی‌نوشتم.

## تعداد حالت‌ها، seed و fuzzing

پیش‌فرض ۱۰۰ حالت برای هر خاصیت است؛ با `-rapid.checks=10000` تست `TestSort` را ۱۰٬۰۰۰ بار اجرا کردم. تا آنجا که می‌دانم rapid هر بار seed تصادفی تازه می‌گیرد، پس یک باگ ممکن است فقط در بعضی اجراها دیده شود. این شبیه یک {{< term "flaky-test" "تست flaky" >}} است ولی باگ واقعی است: seed یا failfile چاپ‌شده را نگه دارید تا بازتولید شود.

{{< term "fuzzing" "fuzzing" >}} خود Go مرتبط ولی متفاوت است: بر اساس coverage هدایت می‌شود و تا وقتی متوقفش کنید ادامه می‌دهد. `go test -fuzz FuzzEncodeDecode -fuzztime 5s` روی رفت‌وبرگشت varint، ۵۱۲٬۵۵۱ اجرا انجام داد و چیزی پیدا نکرد. روی parserها عالی است؛ جنبه‌ی امنیتی‌اش در مقاله‌ی بعدی «Fuzzing to find security bugs» می‌آید. Hypothesis در Python همین ایده است؛ آن را اجرا نکردم.

## چند نکته‌ی مهم

- نوشتن خاصیت سخت‌ترین بخش است. اگر فقط خود کد را دوباره بنویسد چیزی ثابت نمی‌کند؛ رفت‌وبرگشت، invariant و مدل ساده را ترجیح بدهید.
- خروجی generator را بسنجید (خالی، تکراری، مقدار بزرگ، یونیکد با `rapid.String()`)، نه فقط این‌که اجرا می‌شود.
- خاصیت‌ها را سریع و قطعی نگه دارید؛ بدون ساعت و شبکه.
- **نظر من:** برای کد چسب، UI یا CRUD ساده ارزشش را ندارد؛ چند مثال خواناتر است. برای parser، encoder، ساختار داده و محاسبات پولی استفاده کنید.

## تمرین

برای `slices.Compact` و یک تابع `Max` خاصیت بنویسید، بعد عمداً باگ بگذارید و ببینید کدام اول شکست می‌خورد.

## قدم بعدی

بعدی: «refactor امن»، جایی که این تست‌ها تور ایمنی می‌شوند.
