+++
date = '2026-12-31T10:00:00+03:30'
draft = false
title = 'heap و priority queue'
description = 'heap دودویی و priority queue در Go: Heap[T] جنریک، heapify در برابر n بار push، top-K روی stream، container/heap با Fix و scheduler پایدار.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "heap", "priority-queue"]
cover = { image = "/images/covers/algo-heaps-priority-queues.fa.png", alt = "heap و priority queue", hiddenInSingle = true }
+++

در مقاله‌ی قبلی، [stack، queue و deque](/fa/posts/algo-stacks-queues-deques/)، آیتم‌ها به همان ترتیبی که آمده بودند بیرون می‌رفتند. اغلب این درست نیست: کار فوری‌تر، کوچک‌ترین فاصله یا بزرگ‌ترین امتیاز را می‌خواهیم. این همان {{< term "priority-queue" "priority queue" >}} است و تقریباً همیشه روی یک {{< term "binary-heap" "heap دودویی" >}} ساخته می‌شود. heap در یک slice معمولی زندگی می‌کند، مثل [آرایه‌ی پویا و slice از درون](/fa/posts/algo-dynamic-arrays/)، کانتینر از [Generics در Go](/fa/posts/go-generics/) استفاده می‌کند و هزینه‌ها را مثل [تحلیل Big-O با اندازه‌گیری واقعی](/fa/posts/algo-big-o-measured/) با {{< term "big-o" "Big-O" >}} می‌گوییم.

> Go 1.26، مثال محلی. تعداد عملیات (فراخوانی `less`) را منتشر می‌کنم که قطعی است، و هیچ زمان واقعی‌ای نمی‌دهم.

## heap در یک slice

heap یک درخت دودویی کامل است که در آن هیچ والدی از فرزندانش بزرگ‌تر نیست (min-heap). اشاره‌گر لازم نیست: فرزندان اندیس `i` برابر `2i+1` و `2i+2` هستند و والد برابر `(i-1)/2`. کوچک‌ترین عنصر همیشه در اندیس ۰ است. `Push` در انتها اضافه می‌کند و بالا می‌برد؛ `Pop` آخرین عنصر را به ریشه می‌آورد و پایین می‌برد:

```go
func (h *Heap[T]) up(i int) {
	for i > 0 {
		p := (i - 1) / 2
		if !h.less(h.data[i], h.data[p]) {
			break
		}
		h.data[i], h.data[p] = h.data[p], h.data[i]
		i = p
	}
}

func (h *Heap[T]) down(i int) {
	n := len(h.data)
	for {
		l := 2*i + 1
		if l >= n {
			return
		}
		m := l
		if r := l + 1; r < n && h.less(h.data[r], h.data[l]) {
			m = r
		}
		if !h.less(h.data[m], h.data[i]) {
			return
		}
		h.data[i], h.data[m] = h.data[m], h.data[i]
		i = m
	}
}
```

`Heap[T]` یک `less func(a, b T) bool` می‌گیرد. هر دو عمل یک مسیر ریشه تا برگ را طی می‌کنند، پس O(log n) هستند؛ `Peek` برابر O(1) است. تست‌ها شامل یک property test هستند: ۵۰۰ ورودی تصادفی (با تکرار زیاد) وارد و خارج می‌شوند و با `slices.Sort` مقایسه می‌شوند، به‌علاوه‌ی بررسی invariant بعد از هر قدم و heapهای مستقل در goroutineها. همه با `go test -race` سبز هستند.

## مقایسه با container/heap

کتابخانه‌ی استاندارد از شما می‌خواهد روی نوع خودتان `Len`، `Less`، `Swap`، `Push(any)` و `Pop() any` را پیاده کنید و بعد `heap.Push`، `heap.Pop`، `heap.Fix` و `heap.Remove` را صدا بزنید. ۲۰ عدد تصادفی را به هر دو دادم:

```
mine: [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
std:  [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
equal: true
```

ترتیب یکسان است. نسخه‌ی استاندارد مقدارها را در `any` بسته‌بندی می‌کند؛ نسخه‌ی من typed است ولی نمی‌تواند آیتم را در جا به‌روز کند، و همین‌جا `container/heap` می‌درخشد (پایین‌تر).

## heapify از n بار push بهتر است

ساخت heap از n آیتم با n بار push در بدترین حالت O(n log n) است. {{< term "heapify" "Heapify" >}} از آخرین والد پایین می‌آورد و O(n) است. شمارش فراخوانی `less` روی داده‌ی تصادفی:

```
n         heapify      n pushes     ratio
1000      1856         2248         1.21
10000     18778        22509        1.20
100000    188354       228196       1.21
1000000   1882279      2284797      1.21
```

اینجا هر دو خطی‌اند: push داده‌ی تصادفی کم بالا می‌رود و فاصله فقط ۲۱٪ است. بدترین حالت برای min-heap ورودی نزولی است:

```
1000      heapify 1982      pushes 7987
100000    heapify 199978    pushes 1468946
1000000   heapify 1999974   pushes 17951445
```

heapify نزدیک 2n می‌ماند؛ pushها در یک میلیون به حدود ۱۸ مقایسه برای هر آیتم می‌رسند. اگر همه‌ی داده را دارید، heapify کنید.

## top-K روی یک stream

۱۰ عدد بزرگ‌تر از میان یک میلیون عدد را بدون ذخیره‌ی همه نگه می‌داریم: یک min-heap به اندازه‌ی K که ریشه‌اش کوچک‌ترین عضو top-K فعلی است. مقدار جدید فقط اگر بزرگ‌تر باشد جای ریشه می‌نشیند:

```
N = 1000000 K = 10
max heap size: 10 | heap replaced top 134 times
less calls: heap 654 | full sort 20985383
same top-K: true
```

heap هیچ‌وقت بیشتر از ۱۰ آیتم نداشت و ۶۵۴ مقایسه خرج کرد؛ مرتب‌کردن همه حدود ۲۱ میلیون (`sort.Slice`). نتیجه یکسان است. زمان‌گیری نکردم.

## scheduler و tie-break

jobها اولویت دارند (عدد کمتر زودتر اجرا می‌شود). هشت job با نام‌های `a..h`، اولویت ۰ برای `a c e g` و ۱ برای بقیه، به همین ترتیب push شدند:

```
tie-break = false [a(p0) e(p0) g(p0) c(p0) b(p1) d(p1) f(p1) h(p1)]
tie-break = true  [a(p0) c(p0) e(p0) g(p0) b(p1) d(p1) f(p1) h(p1)]
```

بدون tie-break، `c` بعد از `g` اجرا شد: heap پایدار (stable) نیست. با یک شماره‌ی ترتیب (`x.Seq < y.Seq` وقتی اولویت‌ها برابرند) ترتیب FIFO بین برابرها برمی‌گردد.

## عوض‌کردن اولویت

`container/heap` اجازه می‌دهد اندیس هر آیتم را نگه دارید و بعد از تغییر کلید `heap.Fix(h, i)` را صدا بزنید؛ `heap.Remove(h, i)` از وسط حذف می‌کند. هر دو O(log n) هستند:

```
top before: a
after d.Prio=1 and Fix: d
after Remove(d), rest: [a b c e]
```

## heap sort

heapify کنید و n بار pop. O(n log n) است و ساختار اضافه نمی‌خواهد، اما در شمارش من مقایسه‌ی بیشتری از `sort.Slice` داشت: ۳٬۰۱۹٬۵۳۶ در برابر ۱٬۷۵۴٬۷۹۳ برای ۱۰۰٬۰۰۰ عدد. در مقاله‌ی بعدی «Sorting: quick, merge and heap» دقیق‌تر به آن می‌پردازم. الگوریتم Dijkstra هم در مقاله‌ای بعدی از همین heap استفاده می‌کند.

## چند نکته‌ی مهم

- heap مرتب نیست؛ فقط ریشه تضمین‌شده است.
- جست‌وجوی یک مقدار دلخواه O(n) است.
- اولویت‌های برابر ترتیب تضمین‌شده ندارند: شماره‌ی ترتیب اضافه کنید.
- برای top-K بزرگ‌ترین‌ها، min-heap به اندازه‌ی K بگیرید.
- heap بدون قفل برای استفاده‌ی هم‌زمان امن نیست.

## تمرین

متد `Fix(i int)` و یک map از کلید به اندیس به `Heap[T]` اضافه کنید تا بتوانید آیتم را با کلید به‌روز کنید. با property test آن را در برابر `container/heap` بیازمایید.

## قدم بعدی

جست‌وجوی دودویی و invariant.
