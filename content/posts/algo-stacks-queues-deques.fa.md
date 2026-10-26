+++
date = '2026-12-23T10:00:00+03:30'
draft = false
title = 'stack، queue و deque'
description = 'stack، queue و deque در Go: پیاده‌سازی جنریک با slice و ring buffer، تله‌ی q = q[1:]، شمارش allocation و چهار کاربرد واقعی با خروجی.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "stack", "queue", "deque"]
cover = { image = "/images/covers/algo-stacks-queues-deques.fa.png", alt = "stack، queue و deque", hiddenInSingle = true }
+++

در مقاله‌ی قبلی، [hash table از صفر](/fa/posts/algo-hash-tables/)، ساختاری ساختیم که با کلید چیزها را پیدا می‌کند. stack و queue برعکس‌اند: عمداً دسترسی را محدود می‌کنند و همین محدودیت آن‌ها را سریع و ساده برای استدلال می‌کند. روی آرایه‌هایی که در [آرایه‌ی پویا و slice از درون](/fa/posts/algo-dynamic-arrays/) دیدیم سوارند و جایگزین مبتنی بر node در [لیست پیوندی و چرا کم‌کاربرد است](/fa/posts/algo-linked-lists/) بررسی شد. کد از [Generics در Go](/fa/posts/go-generics/) استفاده می‌کند.

> Go 1.26، macOS arm64، مثال محلی. همه‌ی اعداد زیر تعداد یا اندازه‌اند، نه زمان، پس به load ماشین بستگی ندارند. تست‌ها با `go test -race` سبز هستند.

## سه نوع کوچک

{{< term "stack" "stack" >}} آخرین‌ورودی-اولین‌خروجی است. slice کارش را کامل انجام می‌دهد: push همان `append` است و pop آخرین عنصر را برمی‌دارد.

```go
func (s *Stack[T]) Pop() (T, bool) {
	var zero T
	n := len(s.items)
	if n == 0 {
		return zero, false
	}
	v := s.items[n-1]
	s.items[n-1] = zero // do not keep a reference alive
	s.items = s.items[:n-1]
	return v, true
}
```

{{< term "queue" "queue" >}} اولین‌ورودی-اولین‌خروجی است و {{< term "deque" "deque" >}} اجازه‌ی push و pop از هر دو سر را می‌دهد. هر دو در یک {{< term "ring-buffer" "ring buffer" >}} جا می‌شوند: آرایه‌ی ثابت، یک اندیس `head` و یک شمارنده، و موقعیت‌ها با `%` دور می‌زنند. وقتی آرایه پر شد دو برابر می‌شود.

```go
func (d *Deque[T]) PushBack(v T) {
	if d.n == len(d.buf) {
		d.grow()
	}
	d.buf[(d.head+d.n)%len(d.buf)] = v
	d.n++
}

func (d *Deque[T]) PopFront() (T, bool) {
	var zero T
	if d.n == 0 {
		return zero, false
	}
	v := d.buf[d.head]
	d.buf[d.head] = zero
	d.head = (d.head + 1) % len(d.buf)
	d.n--
	return v, true
}
```

`Queue[T]` پوشش نازکی است که فقط `Enqueue` و `Dequeue` را نشان می‌دهد. تست‌ها deque را روی ۵۰۰۰ عملیات تصادفی با یک مدل slice مقایسه می‌کنند و ترتیب FIFO را حین رشد بررسی می‌کنند.

## تله‌ی `q = q[1:]`

queue وسوسه‌انگیز یک slice است: `append` برای ورود و `q = q[1:]` برای خروج.

```
start      len 8 cap 8
5 dequeues len 3 cap 3
5 enqueues len 8 cap 8 (reallocated)
```

reslice ابتدا را جلو می‌برد و capacity هم کم می‌شود، پس جای جلوی آرایه از دست می‌رود. بدتر اینکه عنصرهای قدیمی هنوز توسط {{< term "backing-array" "backing array" >}} نگه داشته می‌شوند. ۱۰۰۰ اشاره‌گر به مقدارهای ۱ کیلوبایتی وارد کردم، ۹۹۰ تا را خارج کردم، garbage collection اجباری زدم و `HeapAlloc` را خواندم:

```
990 of 1000 items popped with q = q[1:]: ~1000 KB still live
same, but q[0] = nil before reslicing:   ~0 KB still live
```

عنصرهای خارج‌شده تا زمان جایگزین شدن آرایه زنده ماندند. پاک کردن خانه قبل از reslice مشکل را حل می‌کند (`Pop` من همین کار را می‌کند). بعد ۱۰۰۰۰۰ جفت ورود/خروج اجرا کردم که هیچ‌وقت بیش از ۵ عنصر منتظر نبود:

```
slice queue: new arrays allocated = 25000
ring queue: cap = 8 copies = 4
```

queue مبتنی بر slice تقریباً هر ۴ عملیات یک آرایه‌ی تازه می‌سازد؛ ring buffer روی capacity برابر ۸ می‌ماند و فقط یک بار ۴ عنصر کپی کرد.

## allocation و رشد سرشکن

`testing.AllocsPerRun` برای ۱۰۰۰ push و ۱۰۰۰ pop:

```
slice stack 12, presized 1, container/list 1745
```

stack مبتنی بر slice هندسی رشد می‌کند (۱۲ allocation) و نسخه‌ی presize‌شده فقط ۱. `container/list` برای هر عنصر یک node می‌سازد و ۷۴۵ تای اضافه خودِ لیست به‌اضافه‌ی ۷۴۴ int است که boxing می‌شود: push کردن یک مقدار ثابت کوچک یا یک اشاره‌گر فقط ۱۰۰۱ allocation می‌دهد و عدد ۷۴۴ همان مقدارهای ۲۵۶ تا ۹۹۹ است که runtime cache نمی‌کند.

رشد با دو برابر کردن در حالت {{< term "amortized-analysis" "سرشکن" >}} برابر O(1) است. تعداد عنصرهایی را که `grow` کپی کرد شمردم:

```
n=10       cap=16       copies=12       copies/n=1.20
n=1000     cap=1024     copies=1020     copies/n=1.02
n=1000000  cap=1048576  copies=1048572  copies/n=1.05
```

حدود یک کپی به ازای هر push، مستقل از n.

## چهار کاربرد واقعی

**پرانتزهای متوازن** با stack، با به‌خاطر سپردن موقعیت هر بازکننده:

```
"{[()]}"           balanced=true  pos=-1
"f(a[1], {x: 2})"  balanced=true  pos=-1
"(]"               balanced=false pos=1
"((a)"             balanced=false pos=0
"a)"               balanced=false pos=1
```

**undo/redo** با دو stack. ویرایش جدید باید stack مربوط به redo را خالی کند:

```
"hello world" undo "hello" undo "" redo "hello" type ! then redo "hello!"
```

**پیمایش سطح‌به‌سطح** یک درخت کوچک با queue (ایده‌ی پشت {{< term "bfs" "جست‌وجوی breadth-first" >}}). مقدار `size := q.Len()` در ابتدای هر دور دقیقاً یک سطح است:

```
levels: [[1] [2 3] [4 5 6] [7]]
```

**عنصر بزرگ‌تر بعدی** با stack یکنواخت (monotonic). برای هر مقدار، اندیس‌های کوچک‌تر را از stack برمی‌داریم و جوابشان را می‌دهیم:

```
input: [2 1 5 3 4 9 4] next greater: [5 5 9 4 9 -1 -1] pushes 7 pops 7
n=100000 increasing: pushes 100000 pops 100000
n=100000 decreasing: pushes 100000 pops 100000
```

حلقه‌ی داخلی درجه‌دو به نظر می‌رسد، ولی هر اندیس یک بار push و حداکثر یک بار pop می‌شود؛ پس مجموع حداکثر ۲n عملیات است. شمارش‌ها برای دو ورودی حدی این را نشان می‌دهند.

## channel و زبان‌های دیگر

channel بافردار Go خودش یک queue از نوع FIFO و امن برای concurrency است ([Goroutine و Channel در Go](/fa/posts/go-goroutines-channels/))؛ بین goroutineها از آن استفاده کنید و از نوع‌های این مقاله وقتی فقط یک goroutine به داده دست می‌زند. این نوع‌ها برای استفاده‌ی هم‌زمان امن نیستند. طبق مستندات، `std::collections::VecDeque` در Rust یک ring buffer قابل رشد است؛ آن را اینجا اجرا نکردم.

## چند نکته‌ی مهم

- هنگام pop خانه را پاک کنید، وگرنه garbage collector نمی‌تواند مقدار را آزاد کند.
- `q = q[1:]` برای queueهای کوتاه‌عمر خوب است، برای queueهای دائمی نه.
- pop روی ساختار خالی باید `ok == false` برگرداند، نه panic.
- باقی‌مانده (`%`) در ring buffer جای کلاسیک خطای off-by-one است؛ با مدل slice تست کنید.
- وقتی اندازه را می‌دانید با `make([]T, 0, n)` از قبل جا بگیرید.

## تمرین

به `Queue` متد `Peek` اضافه کنید، بعد `Deque` را طوری کنید که وقتی یک‌چهارم پر شد کوچک شود. با شمارنده‌ی کپی بررسی کنید که الگوی push/pop در مرز کوچک‌شدن در هر قدم کپی نمی‌کند.

## قدم بعدی

heap و priority queue
