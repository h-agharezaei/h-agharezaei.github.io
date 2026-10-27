+++
date = '2027-01-20T10:00:00+03:30'
draft = false
title = 'مرتب‌سازی: quick، merge و heap'
description = 'مرتب‌سازی در Go: quicksort، merge sort و heap sort با شمارش دقیق مقایسه‌ها، بدترین حالت O(n^2)، پایداری و انتخاب در عمل.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "sorting", "go", "quicksort", "merge-sort", "heap-sort"]
cover = { image = "/images/covers/algo-sorting.fa.png", alt = "مرتب‌سازی: quick، merge و heap", hiddenInSingle = true }
+++

در مقاله‌ی قبلی، [جست‌وجوی دودویی و invariant](/fa/posts/algo-binary-search-invariants/)، داده از قبل مرتب بود. حالا خودمان آن ترتیب را می‌سازیم. سه الگوریتم کلاسیک به O(n log n) می‌رسند ({{< term "big-o" "Big-O" >}}، مثل [تحلیل Big-O با اندازه‌گیری واقعی](/fa/posts/algo-big-o-measured/)): {{< term "quicksort" "quicksort" >}}، {{< term "merge-sort" "merge sort" >}} و {{< term "heap-sort" "heap sort" >}}. آخری همان heap مقاله‌ی [heap و priority queue](/fa/posts/algo-heaps-priority-queues/) را به کار می‌برد. فرقشان در بدترین حالت، حافظه و یک ویژگی است که خیلی‌ها را غافلگیر می‌کند: {{< term "stable-sort" "پایداری (stability)" >}}.

> Go 1.26، مثال محلی. وقتی خواستم زمان بگیرم، load average یک‌دقیقه‌ای این ماشین ۱۰٫۶۱ بود، خیلی بالاتر از سقف ۲٫۰ من؛ پس هیچ نانوثانیه‌ای منتشر نمی‌کنم. هرچه پایین می‌بینید قطعی است: تعداد فراخوانی `less` و تعداد allocation.

## سه پیاده‌سازی

هر سه جنریک‌اند و `less func(a, b T) bool` می‌گیرند؛ wrapperهای نازک برای نوع‌های `cmp.Ordered` از `cmp.Less` استفاده می‌کنند. هر کدام در برابر `slices.Sort` روی ورودی تصادفی، مرتب، معکوس و پر از تکرار (seed ثابت، اندازه‌ی ۰ تا ۵۰۰۰) تست شده‌اند، به‌علاوه‌ی `less` نزولی و تست پایداری. همه با `go test -race` سبز هستند.

quicksort میانه‌ی عنصر اول، وسط و آخر را pivot می‌گیرد، کنار انتها پارک می‌کند و افراز می‌کند. سمت کوچک‌تر را بازگشتی و سمت بزرگ‌تر را با حلقه می‌رود، پس عمق stack حداکثر log2 n است، و بازه‌های ۱۲ عنصر یا کمتر به insertion sort می‌روند:

```go
func Quick[T any](a []T, less func(x, y T) bool) {
	for len(a) > cutoff {
		p := partition(a, less)
		if p < len(a)-p-1 {
			Quick(a[:p], less)
			a = a[p+1:]
		} else {
			Quick(a[p+1:], less)
			a = a[:p]
		}
	}
	insertion(a, less)
}
```

merge sort نصف می‌کند، دو نیمه را مرتب می‌کند و با یک بافر به اندازه‌ی n که از اول ساخته می‌شود ادغام می‌کند. جزئیاتی که آن را پایدار می‌کند `<` اکید است: وقتی برابرند، سمت چپ اول می‌رود:

```go
if less(buf[j], buf[i]) { // strict: equal keys take the left one first
	a[k] = buf[j]; j++
} else {
	a[k] = buf[i]; i++
}
```

heap sort با heapify یک max-heap می‌سازد، بعد n-1 بار ریشه را به انتها می‌برد و sift down می‌کند. بافر ندارد.

## شمارش مقایسه‌ها

همان اعداد تصادفی را با هر الگوریتم مرتب کردم و فراخوانی‌های `less` را شمردم:

```
n         quick        merge        heap         n*log2(n)
1000      10533        8721         16884        9966
10000     144197       120483       235400       132877
100000    1792110      1536402      3019908      1660964
1000000   21623445     18674250     36795744     19931569
```

هر سه مثل n log n رشد می‌کنند. merge sort زیر n log2 n می‌ماند، quicksort ۵ تا ۹ درصد بالاتر است و heap sort تقریباً دو برابر merge sort مقایسه می‌خواهد؛ هم‌خوان با نتیجه‌ی مقاله‌ی قبل. اما شمارش مقایسه زمان نیست: الگوی دسترسی به حافظه را نمی‌بیند، پس درباره‌ی سریع‌ترین ادعایی نمی‌کنم.

allocationها با `testing.AllocsPerRun` برای n = 10000 (هر اجرا یک allocation برای clone ورودی دارد): quicksort ۱ و heap sort ۱، یعنی اضافه‌ای ندارند؛ merge sort ۲، یعنی همان بافر.

## بدترین حالت quicksort

ساده‌ترین quicksort را بگیرید: عنصر اول به‌عنوان pivot و بدون cutoff. روی ورودی تصادفی خوب است. روی ورودی مرتب، هر افراز فقط یک عنصر را کم می‌کند. با n = 10,000 و یک شمارنده‌ی عمق (اندازه گرفتم تا stack overflow نگیرم):

```
sorted  comparisons=49995000  n^2/2=50000000  max recursion depth=10000
random  comparisons=156275  n^2/2=50000000  max recursion depth=31
median-of-three quick on the same sorted input: comparisons=107963
```

ورودی مرتب حدود n^2/2 مقایسه و بازگشتی به عمق خود ورودی می‌دهد؛ همان کد روی ورودی تصادفی ۱۵۶٬۲۷۵ مقایسه و عمق ۳۱ دارد. median-of-three حالت مرتب را با ۱۰۷٬۹۶۳ مقایسه سر می‌کند. اما مصون نیست: برای هر قاعده‌ی ثابت انتخاب pivot ورودی بد ساخته می‌شود، و یکی از دلیل‌های fallback در کتابخانه‌هاست.

## پایداری

۲۰۰ رکورد با ۳ کلید متفاوت را مرتب کردم و جفت‌های هم‌کلیدی را شمردم که ترتیبشان با ترتیب ورود فرق کرد:

```
my merge sort                      equal-key pairs out of original order: 0
my quicksort                       equal-key pairs out of original order: 100
my heap sort                       equal-key pairs out of original order: 126
sort.Stable                        equal-key pairs out of original order: 0
slices.SortStableFunc              equal-key pairs out of original order: 0
sort.Slice                         equal-key pairs out of original order: 102
slices.SortFunc                    equal-key pairs out of original order: 102
```

فقط merge sort و توابع پایدار کتابخانه‌ی استاندارد ترتیب را نگه می‌دارند. طبق مستندات `sort.Slice` و `slices.SortFunc` پایدار نیستند، پس هر ترتیبی از آن‌ها می‌بینید اتفاقی است. (با فقط ۱۲ رکورد quicksort من پایدار به نظر می‌رسید، چون بازه‌های زیر cutoff با insertion sort مرتب می‌شوند که پایدار است. مثال کوچک دروغ می‌گوید.)

## کتابخانه‌ی استاندارد چه می‌کند

طبق مستندات و کد Go، `sort.Slice` و `slices.Sort` از Go 1.19 یک pattern-defeating quicksort به کار می‌برند. `sort.Slice` را روی ۱۰۰٬۰۰۰ عدد تصادفی شمردم: ۱٬۷۳۹٬۸۹۲ فراخوانی `less`، نزدیک ۱٬۷۹۲٬۱۱۰ مقایسه‌ی quicksort من.

## چند نکته‌ی مهم

- مگر دلیل داشته باشید `slices.Sort` یا `slices.SortFunc` را بزنید؛ وقتی کلیدهای برابر باید ترتیب بمانند، مثلاً مرتب‌سازی با کلید دوم بعد از اولی، `slices.SortStableFunc` را.
- تابع مقایسه‌ی شما باید ترتیب سازگار باشد. `less`ای که نیست، مثلاً با `<=`، می‌تواند نتیجه را خراب کند.
- قاعده‌ی ثابت pivot ورودی بد دارد؛ pivot تصادفی یا fallback دفاع است.
- merge sort حافظه‌ی اضافه‌ی O(n) می‌خواهد؛ quicksort و heap sort نه.
- مقایسه‌ی کمتر یعنی سریع‌تر نیست. قبل از انتخاب روی داده‌ی خودتان اندازه بگیرید.

## تمرین

merge sort را یک کار کمتر کنید: اگر `!less(a[m], a[m-1])` بود ادغام را رد کنید تا ورودی مرتب حدود n مقایسه بخواهد. فراخوانی‌های `less` را روی ورودی مرتب قبل و بعد بشمارید و تست پایداری را سبز نگه دارید.

## قدم بعدی

درخت جست‌وجو و B-tree.
