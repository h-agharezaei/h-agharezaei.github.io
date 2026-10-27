+++
date = '2027-01-10T10:00:00+03:30'
draft = false
title = 'جست‌وجوی دودویی و invariant'
description = 'جست‌وجوی دودویی در Go با invariant: LowerBound و UpperBound، باگ‌های واقعی سرریز نقطه‌ی وسط و off-by-one، تست جامع و جست‌وجو روی جواب.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "binary-search", "go", "invariants", "testing"]
cover = { image = "/images/covers/algo-binary-search-invariants.fa.png", alt = "جست‌وجوی دودویی و invariant", hiddenInSingle = true }
+++

در مقاله‌ی قبلی، [heap و priority queue](/fa/posts/algo-heaps-priority-queues/)، برای درست ماندن heap به یک invariant تکیه کردم. {{< term "binary-search" "جست‌وجوی دودویی" >}} جایی است که این عادت بیشترین سود را دارد: ایده‌اش در یک جمله جا می‌شود، ولی کدش به غلط‌نوشته‌شدن معروف است. روی یک slice مرتب کار می‌کند، مثل [آرایه‌ی پویا و slice از درون](/fa/posts/algo-dynamic-arrays/)، از [Generics در Go](/fa/posts/go-generics/) استفاده می‌کند و هزینه‌اش همان لگاریتمی است که در [تحلیل Big-O با اندازه‌گیری واقعی](/fa/posts/algo-big-o-measured/) دیدیم.

> Go 1.26، مثال محلی. ماشین مشغول بود، پس فقط تعداد عملیات (قطعی) را منتشر می‌کنم و زمانی نمی‌دهم.

## اول invariant را بنویسید

{{< term "invariant" "invariant" >}} جمله‌ای است که در هر دور حلقه درست می‌ماند. من بازه‌ی نیم‌باز `[lo, hi)` را جست‌وجو می‌کنم و این جمله را در خود کد می‌نویسم:

```go
// Invariant: a[i] < x for every i < lo; a[i] >= x for every i >= hi.
// The unknown part is [lo, hi).
func LowerBound[T cmp.Ordered](a []T, x T) int {
	lo, hi := 0, len(a)
	for lo < hi {
		mid := lo + (hi-lo)/2
		if a[mid] < x {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo // lo == hi: nothing unknown is left
}
```

در شروع چیزی معلوم نیست، پس برقرار است. هر شاخه یک مرز را از روی عنصری رد می‌کند که همین الان دسته‌بندی شده، پس برقرار می‌ماند. بازه کوچک می‌شود، پس حلقه تمام می‌شود و آن‌وقت `lo == hi` دقیقاً همان {{< term "lower-bound" "lower bound" >}} است. `UpperBound` همین است با `<=`. از این دو: اولین و آخرین وقوع و `Count = UpperBound - LowerBound`.

```
a = [1 3 3 3 5 8 8 13]
x=3  lower=1 upper=4 first=1 last=3 count=3
x=4  lower=4 upper=4 first=-1 last=-1 count=0
x=8  lower=5 upper=7 first=5 last=6 count=2
```

invariant را می‌شود assert هم کرد: نسخه‌ای قبل از هر دور `a[lo-1] < x` و `a[hi] >= x` را چک می‌کند. روی همه‌ی حالت‌های پایین ۵۳۴۴ چک اجرا شد و هیچ‌وقت panic نکرد.

## کتابخانه‌ی استاندارد

`slices.BinarySearch` مقدار `(index, found)` برمی‌گرداند که index همان lower bound است. `sort.Search(n, f)` کوچک‌ترین اندیسی را برمی‌گرداند که `f` در آن درست است؛ یعنی همین ایده با predicate خودتان:

```
x=3  slices.BinarySearch=(1,true)  sort.Search=1
x=4  slices.BinarySearch=(4,false) sort.Search=4
```

## باگ‌های کلاسیک، واقعی

**سرریز نقطه‌ی وسط.** `(lo+hi)/2` قبل از تقسیم جمع می‌کند. با `int8` و اندیس‌های ۱۰۰ و ۱۲۰، و با `int32`:

```
(lo+hi)/2     = -18 (lo+hi wrapped to -36)
lo+(hi-lo)/2  = 110
int32 (lo+hi)/2    = -97483648
int32 lo+(hi-lo)/2 = 2050000000
```

`int` در Go شصت‌وچهار بیتی است و کمتر به این می‌رسید، ولی اگر برسید {{< term "integer-overflow" "سرریز" >}} بی‌صدا اتفاق می‌افتد.

**off-by-one که تمام نمی‌شود.** نوشتن `lo = mid` به‌جای `lo = mid + 1` می‌تواند حلقه را گیر بیندازد. با شمارنده‌ی قدم ۱۰۰۰ محدودش کردم:

```
x=1 finished=true  steps=3
x=5 finished=false steps=1001
x=6 finished=false steps=1001
```

**بازه‌ی بسته‌ای که جا می‌اندازد.** با `[lo, hi]` شرط حلقه باید `lo <= hi` باشد. با `lo < hi` یک عنصر زودتر می‌ایستد: جست‌وجوی `5` در `[1 3 5]` مقدار `-1` داد؛ نسخه‌ی درست `2` داد.

## تست جامع

تست تصادفی ممکن است این باگ‌ها را نبیند. اینجا فضای ورودی آن‌قدر کوچک است که همه‌چیز را می‌شود چک کرد: همه‌ی آرایه‌های مرتب با طول ۰ تا ۷ روی مقدارهای ۰ تا ۳ و هر هدف از ۱- تا ۴:

```
arrays=330 cases=1980 | LowerBound/Count failures=0 | closedOK failures=0 | broken closed failures=217
first failing case of the broken version: a=[0] target=0
```

نسخه‌ی خراب روی آرایه‌ی تک‌عنصری هم شکست می‌خورد. `go test -race` هم سبز است.

## جست‌وجو روی جواب

هر چیز یکنوا (monotone) را می‌شود جست‌وجو کرد: `false false ... true true`. کوچک‌ترین `n` که `ok(n)` درست است، با invariant «`ok` پایین‌تر از `lo` نادرست و از `hi` به بعد درست است»:

```go
func MinTrue(lo, hi int, ok func(int) bool) int {
	for lo < hi {
		mid := lo + (hi-lo)/2
		if ok(mid) { hi = mid } else { lo = mid + 1 }
	}
	return lo
}
```

ظرفیت کشتی: بسته‌ها به ترتیب و با یک ظرفیت در هر روز حمل می‌شوند. ظرفیتی شدنی است که بارگیری حریصانه حداکثر `D` روز لازم داشته باشد و کشتی بزرگ‌تر هیچ‌وقت بدتر نیست، پس شدنی‌بودن یکنواست. وزن‌های ۱ تا ۱۰:

```
days=1 -> capacity 55    days=2 -> capacity 28
days=5 -> capacity 15    days=10 -> capacity 10
```

جذر صحیح: کوچک‌ترین `k` با `k*k > n` منهای یک. predicate اول من یعنی `k*k > n` برای `n` بزرگ سرریز کرد؛ اصلاح `k > n/k` نمی‌کند:

```
isqrt(1099511627776)=1048576 naive=546710704328
```

## چند مقایسه لازم است؟

روی slice مرتب با n عنصر و مقدار غایب، تعداد ارزیابی `a[mid] < x` را شمردم:

```
n=1000    9    n=10000   13
n=100000  16   n=1000000 19
```

هزار برابر شدن n حدود ۱۰ قدم اضافه می‌کند: جدول دو برابرشدن مقاله‌ی Big-O، برعکس.

## چند نکته‌ی مهم

- invariant را قبل از کد به‌صورت کامنت بنویسید.
- `[lo, hi)` یا `[lo, hi]` را انتخاب کنید و شرط‌هایشان را قاطی نکنید.
- از `lo+(hi-lo)/2` استفاده کنید.
- با predicate جست‌وجو کنید و «پیدا کردن x» را از آن بسازید.
- ورودی باید واقعاً مرتب باشد؛ اینکه در غیر این صورت چه می‌شود را تست نکردم.

## تمرین

برای slice مرتب از float، `Floor` و `Ceil` بنویسید و تست جامع در برابر جست‌وجوی خطی بسازید. بعد عمداً کدتان را خراب کنید و حالت شکست‌خورده را بخوانید.

## قدم بعدی

مرتب‌سازی: quick، merge و heap.
