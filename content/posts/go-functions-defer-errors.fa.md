+++
date = '2026-11-04T10:00:00+03:30'
draft = false
title = 'توابع، defer و مدیریت خطا در Go'
description = 'توابع Go با چند مقدار برگشتی، variadic و closure، به‌همراه اینترفیس error، wrap با %w، errors.Is و errors.As، defer و اینکه چرا panic برای خطا نیست.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "functions", "errors", "defer"]
cover = { image = "/images/covers/go-functions-defer-errors.fa.png", alt = "توابع، defer و مدیریت خطا در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-types-control-flow/) با نوع‌ها، متغیرها و کنترل جریان آشنا شدیم. حالا به بخشی می‌رسیم که شکل بیشترِ کدهای Go را تعیین می‌کند: توابع و مدیریت خطا. در Go استثنا (exception) وجود ندارد. تابع‌ها خطا را مثل یک مقدار معمولی برمی‌گردانند و کارِ پاک‌سازی با `defer` انجام می‌شود. وقتی این دو را بفهمید، خیلی از سلیقه‌های Go معنی پیدا می‌کند.

> همه‌ی مثال‌های زیر را با Go 1.26 اجرا کرده‌ام و خروجی‌ها از همان اجراها کپی شده‌اند.

## تابع و چند مقدار برگشتی

نوع پارامترها بعد از نامشان می‌آید و تابع می‌تواند بیش از یک مقدار برگرداند:

```go
func divmod(a, b int) (int, int) { return a / b, a % b }

func sum(nums ...int) int {
	total := 0
	for _, n := range nums {
		total += n
	}
	return total
}

func counter() func() int {
	n := 0
	return func() int { n++; return n }
}
```

تابع `sum` از نوع **variadic** است: داخل آن `nums` یک `[]int` است. می‌شود بدون آرگومان، با چند آرگومان، یا با یک slice آماده و علامت `...` صدایش زد. تابع‌ها خودشان هم مقدارند. `counter` یک **closure** برمی‌گرداند که متغیر `n` را بین فراخوانی‌ها نگه می‌دارد.

```go
q, r := divmod(17, 5)
fmt.Println(q, r)                                   // 3 2
fmt.Println(sum(), sum(1, 2, 3), sum([]int{4, 5}...)) // 0 6 9
next := counter()
fmt.Println(next(), next(), next())                 // 1 2 3
```

مقادیر برگشتی را می‌شود **نام‌دار** کرد (`func f() (n int, err error)`). این‌ها با مقدار صفر شروع می‌شوند و `return` خالی همین‌ها را برمی‌گرداند. با `defer` به کار می‌آید (پایین‌تر می‌بینیم)، اما `return` خالی در یک تابع بلند باعث می‌شود خواننده دنبال جایی بگردد که مقدارها ست شده‌اند. من نام‌دار کردن را فقط برای تابع‌های کوتاه یا وقتی که یک تابع deferred باید نتیجه را عوض کند استفاده می‌کنم.

## اینترفیس error

`error` فقط یک اینترفیس با یک متد است: `Error() string`. قرارداد این است که خطا آخرین مقدار برگشتی باشد و فراخواننده بلافاصله آن را چک کند:

```go
n, err := strconv.Atoi(s)
if err != nil {
	return 0, err
}
```

`if err != nil` را زیاد خواهید نوشت و این عمدی است: مسیر شکست در کد دیده می‌شود.

## ساختن، wrap کردن و بررسی خطا

`errors.New` یک خطای ساده می‌سازد. `fmt.Errorf` با فعل `%w` یک خطا را **wrap** می‌کند، یعنی به آن زمینه (context) اضافه می‌کند و خطای اصلی همچنان در دسترس می‌ماند. بعد `errors.Is` بررسی می‌کند که یک خطای مشخص جایی در زنجیره هست یا نه، و `errors.As` خطایی از یک نوع مشخص را پیدا می‌کند و به شما می‌دهد.

این برنامه‌ی کوچکی است که اجرا کردم. یک **sentinel error** دارد (مقداری در سطح پکیج که با آن مقایسه می‌کنیم) و یک نوع خطای سفارشی با متد `Unwrap`:

```go
var ErrDivideByZero = errors.New("divide by zero")

type ParseError struct {
	Input string
	Err   error
}

func (e *ParseError) Error() string { return fmt.Sprintf("parse %q: %v", e.Input, e.Err) }
func (e *ParseError) Unwrap() error { return e.Err }

func parse(s string) (int, error) {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return 0, &ParseError{Input: s, Err: err}
	}
	return n, nil
}

func divide(a, b string) (int, error) {
	x, err := parse(a)
	if err != nil {
		return 0, fmt.Errorf("divide: left operand: %w", err)
	}
	y, err := parse(b)
	if err != nil {
		return 0, fmt.Errorf("divide: right operand: %w", err)
	}
	if y == 0 {
		return 0, fmt.Errorf("divide %d by %d: %w", x, y, ErrDivideByZero)
	}
	return x / y, nil
}
```

`main` چهار ورودی را اجرا می‌کند و برای هر خطا پیام و نتیجه‌ی `errors.Is` و `errors.As` را چاپ می‌کند:

```text
result: 42
error: divide 10 by 0: divide by zero
  is ErrDivideByZero: true
  is strconv.ErrSyntax: false
  as *ParseError: no
error: divide: left operand: parse "abc": strconv.Atoi: parsing "abc": invalid syntax
  is ErrDivideByZero: false
  is strconv.ErrSyntax: true
  as *ParseError: input="abc"
error: divide: right operand: parse " x1": strconv.Atoi: parsing "x1": invalid syntax
  is ErrDivideByZero: false
  is strconv.ErrSyntax: true
  as *ParseError: input=" x1"
```

پیام چاپ‌شده مثل یک زنجیره خوانده می‌شود و هر لایه زمینه‌ای اضافه کرده است. همچنین `errors.Is(err, strconv.ErrSyntax)` درست است، با اینکه خودمان هیچ‌جا اسمی از آن نیاوردیم: این تابع از میان `ParseError` ما (به‌لطف `Unwrap`) تا خطایی که `strconv` برگردانده پایین می‌رود.

## defer

`defer` یک فراخوانی را برای لحظه‌ی بازگشت تابع زمان‌بندی می‌کند. روش رایج برای آزاد کردن منابع درست کنار جایی است که آن‌ها را گرفته‌ایم:

```go
f, err := os.Open(path)
if err != nil {
	return err
}
defer f.Close()
```

دو قاعده مهم است. فراخوانی‌های deferred به ترتیب **LIFO** (آخرین ثبت‌شده، اولین اجرا) اجرا می‌شوند و آرگومان‌ها در لحظه‌ی خودِ دستور `defer` محاسبه می‌شوند، نه وقتی که فراخوانی اجرا می‌شود:

```go
func demoDefer() {
	for i := 1; i <= 3; i++ {
		defer fmt.Println("deferred", i)
	}
	x := 10
	defer fmt.Println("x at defer time:", x)
	x = 20
	fmt.Println("x now:", x)
}
```

```text
x now: 20
x at defer time: 10
deferred 3
deferred 2
deferred 1
```

## کوتاه درباره‌ی panic و recover

`panic` اجرای عادی را متوقف می‌کند، تابع‌های deferred را اجرا می‌کند و برنامه را می‌اندازد، مگر اینکه داخل یک تابع deferred کسی `recover` صدا بزند. مثلاً نوشتن در یک map برابر nil باعث panic می‌شود و با یک مقدار برگشتی نام‌دار می‌توانیم آن را به error تبدیل کنیم:

```go
func safeName() (name string, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recovered: %v", r)
		}
	}()
	var m map[string]int
	m["a"] = 1
	return "ok", nil
}
// prints:  recovered: assignment to entry in nil map
```

برای شکست‌های قابل انتظار مثل ورودی بد یا فایل ناموجود از panic استفاده نکنید و error برگردانید. panic برای باگ و حالت‌های غیرممکن است و `recover` بیشتر در مرزها کاربرد دارد، مثلاً سرور HTTP که نمی‌خواهد یک درخواست خراب کل برنامه را بیندازد.

## چند نکته که باید حواستان باشد

- خطا را با `_` نادیده نگیرید، مگر اینکه بتوانید دلیل امن بودنش را بگویید.
- اگر فراخواننده ممکن است به `errors.Is` یا `errors.As` نیاز داشته باشد، با `%w` wrap کنید، نه `%v`. `%v` فقط متن را نگه می‌دارد.
- وقتی wrap در کار است، خطاها را با `errors.Is` مقایسه کنید، نه `==`.
- `defer` داخل حلقه در پایان تابع اجرا می‌شود، نه در پایان هر تکرار. اگر فایل‌های زیادی باز می‌کنید، بدنه را به یک تابع جدا ببرید.
- آرگومان‌های فراخوانی deferred همان لحظه محاسبه می‌شوند. اگر آخرین مقدار را می‌خواهید از closure (`defer func() { ... }()`) استفاده کنید.

## تمرین

۱. یک sentinel به نام `ErrNegative` به `divide` اضافه کنید و وقتی یکی از عملوندها منفی است آن را (wrap‌شده) برگردانید. با `errors.Is` بررسی‌اش کنید.
۲. تابع `func average(nums ...float64) (float64, error)` را بنویسید که برای ورودی خالی خطا برگرداند.
۳. تابعی بنویسید که سه `defer` با چاپ دارد؛ قبل از اجرا خروجی را حدس بزنید.

## قدم بعدی

در مقاله‌ی بعد سراغ slice، map و string در Go می‌رویم: اینکه واقعاً چطور کار می‌کنند و دام‌هایی که مبتدی‌ها را می‌گیرد.
