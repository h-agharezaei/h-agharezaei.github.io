+++
date = '2026-12-07T10:00:00+03:30'
draft = false
title = 'لیست پیوندی و چرا کم‌کاربرد است'
description = 'لیست پیوندی در Go: List[T] جنریک، سربار حافظه‌ی node، شمارش allocation، محلیت cache در مقایسه با slice و جایی که کش LRU به آن نیاز دارد.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "linked-list", "cache"]
cover = { image = "/images/covers/algo-linked-lists.fa.png", alt = "لیست پیوندی و چرا کم‌کاربرد است", hiddenInSingle = true }
+++

در مقاله‌ی قبلی، [آرایه‌ی پویا و slice از درون](/fa/posts/algo-dynamic-arrays/)، آرایه تقریباً در همه‌چیز برنده بود. رقیب کتاب‌های درسی‌اش {{< term "linked-list" "لیست پیوندی" >}} است: درج در زمان ثابت و بدون کپی هنگام رشد. پس چرا کمتر کسی سراغش می‌رود؟ این بار اندازه گرفتم. برای کانتینر از [Generics در Go](/fa/posts/go-generics/) استفاده می‌کنیم، بحث حافظه در [اشاره‌گرها و مدل حافظه در Go](/fa/posts/go-pointers-memory/) است و جایی که لیست واقعاً به کار می‌آید در [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/) پیدا می‌شود.

> Go 1.26، macOS arm64، مثال محلی. تعدادها و اندازه‌ها قطعی‌اند. زمان‌ها همراه با load زمان اندازه‌گیری برچسب خورده‌اند.

## لیست پیوندی ساده‌ی جنریک

هر node یک مقدار و یک اشاره‌گر به node بعدی دارد. `List[T]` متدهای `PushFront`، `PushBack` (با اشاره‌گر tail برابر O(1))، `Find`، `Remove` و `Reverse` دارد:

```go
type Node[T any] struct {
	Val  T
	Next *Node[T]
}

func (l *List[T]) PushFront(v T) {
	nd := &Node[T]{Val: v, Next: l.head}
	l.head = nd
	if l.tail == nil {
		l.tail = nd
	}
	l.n++
}

func (l *List[T]) Reverse() {
	var prev *Node[T]
	l.tail = l.head
	for c := l.head; c != nil; {
		next := c.Next
		c.Next = prev
		prev, c = c, next
	}
	l.head = prev
}
```

تست‌ها push، find، remove، reverse (از جمله اینکه بعد از آن `PushBack` هنوز درست کار می‌کند، چون `Reverse` باید tail را اصلاح کند)، لیست خالی و لیست‌های مستقل در goroutineها را پوشش می‌دهند و با `go test -race` سبز هستند.

| عملیات | لیست پیوندی | آرایه‌ی پویا |
|---|---|---|
| درج در ابتدا | O(1) | O(n) |
| اضافه در انتها | O(1) با tail | O(1) سرشکن |
| عنصر i‌ام | O(n) | O(1) |
| حذف nodeای که در دست داریم | O(1) در دوپیوندی؛ در یک‌پیوندی node قبلی لازم است | O(n) جابه‌جایی |

تعداد nodeهایی که `Find` در لیست ۱۰۰۰تایی دید: عنصر اول ۱ قدم، وسط ۵۰۱، آخر ۱۰۰۰. O(n) دقیقاً همین است.

## هزینه‌ی یک node

```
sizeof Node[int]: 16  elem int: 8
sizeof Node[byte]: 16 elem byte: 1
sizeof Node[big]: 136 elem big: 128
```

هر node یک اشاره‌گر ۸ بایتی دارد و alignment هم padding اضافه می‌کند. برای عنصرهای کوچک، سربار غالب است. این‌ها اندازه‌ی struct هستند؛ allocator ممکن است بیشتر گرد کند (آن را اندازه نگرفتم).

تعداد allocation برای ۱۰۰۰ عنصر با `testing.AllocsPerRun`:

```
list 1000, presized slice 1, append-grown slice 9
```

لیست برای هر عنصر یک allocation می‌خواهد و slice با اندازه‌ی از پیش تعیین‌شده در کل یکی.

## nodeها کجا هستند

اختلاف آدرس nodeهای پشت‌سرهم را چاپ کردم. وقتی پشت‌سرهم ساخته شدند:

```
[16 16 16 16 16 16 16 16 16 16 16 16]
```

بعد همان ۱۰۰۰ node را shuffle و دوباره به هم وصل کردم:

```
[-304 1648 -8736 5408 -27696 23536 6720 -1040 1744 -16 -27136 -2432]
```

در این اجرا nodeهای تازه کنار هم بودند و بعد از shuffle پیمایش لیست بین نقاط دور حافظه می‌پرد. این همان فرق {{< term "cache-locality" "محلیت cache" >}} خوب و بد است. برنامه‌ی واقعی که در طول زمان اضافه و حذف می‌کند بیشتر شبیه حالت دوم است، ولی این را اینجا ثابت نکردم.

## benchmark زمانی

جمع همه‌ی عنصرها: slice، لیستِ به‌ترتیب ساخته‌شده و لیستِ shuffle‌شده در حافظه. میانه‌ی ۷ اجرای `testing.Benchmark`، باینری از قبل build شده و با قفل، تنها اجرا شده. **اندازه‌گیری روی همین ماشین، load برابر ۱٫۹ در شروع و ۲٫۳ در پایان** (بالاتر از چیزی که می‌خواستم، پس آن را تقریبی بدانید):

```
n         slice ns   list(ordered) ns   list(shuffled) ns
1000           323             1261               1260
100000       40997           128347             546201
1000000     418855          1318309           27327167
```

لیست مرتب در همه‌ی اندازه‌ها حدود ۳ برابر کندتر از slice است. لیست shuffle‌شده در ۱۰۰۰ عنصر (که همه‌چیز در cache جا می‌شود) ۳٫۹ برابر است، ولی در ۱۰۰ هزار ۱۳ برابر و در یک میلیون ۶۵ برابر. چیزی که می‌توانم ادعا کنم: فاصله دقیقاً وقتی بزرگ می‌شود که داده بزرگ و ترتیب به‌هم‌ریخته باشد. توضیح محتمل cache miss است، اما شمارنده‌های سخت‌افزاری را نخواندم، پس این یک فرضیه است. روی ماشین شما اعداد فرق می‌کند.

## جایی که لیست مناسب است

لیست دوپیوندی اجازه می‌دهد nodeای را که در دست داریم بدون جست‌وجو در O(1) حذف کنیم. `container/list` استاندارد این کار را می‌کند:

```
0 1 3 4 (removed known element 2 in O(1))
```

کاربرد کلاسیک آن {{< term "lru-cache" "کش LRU" >}} است: یک map از کلید به عنصر لیست و یک لیست مرتب بر اساس تازگی.

```go
func (c *LRU) Get(k string) (int, bool) {
	e, ok := c.items[k]
	if !ok {
		return 0, false
	}
	c.ll.MoveToFront(e)
	return e.Value.(*entry).val, true
}

func (c *LRU) Put(k string, v int) {
	if e, ok := c.items[k]; ok {
		e.Value.(*entry).val = v
		c.ll.MoveToFront(e)
		return
	}
	c.items[k] = c.ll.PushFront(&entry{k, v})
	if c.ll.Len() > c.cap {
		last := c.ll.Back()
		c.ll.Remove(last)
		delete(c.items, last.Value.(*entry).key)
	}
}
```

با ظرفیت ۳، ورود `a b c`، خواندن `a` و ورود `d`، کلیدها `[d a c]` شدند: `b` حذف شد. تست هم سبز است. map عنصر را در O(1) پیدا می‌کند و لیست جابه‌جایی و حذف را در O(1) انجام می‌دهد؛ هیچ‌کدام تنها هر دو را نمی‌تواند.

## چند نکته‌ی مهم

- پیش‌فرض slice باشد. فقط وقتی سراغ لیست بروید که nodeها را در دست دارید و زیاد splice می‌کنید.
- هر node یک allocation جدا است، یعنی کار بیشتر برای garbage collector هم هست.
- درج در ابتدا O(1) است، ولی پیدا کردن جای درج O(n) است.
- `container/list` مقدار را به‌صورت `any` نگه می‌دارد و type assertion می‌خواهد؛ `List[T]` جنریک ما نمی‌خواهد.
- این نسبت‌ها را برای سخت‌افزار یا اندازه‌ی عنصر دیگر تعمیم ندهید.

## تمرین

`List[T]` را دوپیوندی کنید و `Remove(node)` بنویسید که خود node را می‌گیرد. بعد حذف یکی‌درمیان nodeها در لیست یک‌میلیونی را تست کنید و با `slices.DeleteFunc` روی slice مقایسه کنید. قبل از اجرا برنده را حدس بزنید.

## قدم بعدی

hash table از صفر
