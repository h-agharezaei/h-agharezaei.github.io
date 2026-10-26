+++
date = '2026-10-31T10:00:00+03:30'
draft = false
title = 'نوع‌ها، متغیرها و کنترل جریان در Go'
description = 'متغیرها، zero value، نوع‌های پایه، ثابت‌ها با iota، تبدیل صریح نوع و if و for و switch در Go، همه با مثال‌های واقعی و اجراشده.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/go-types-control-flow.fa.png", alt = "نوع‌ها، متغیرها و کنترل جریان در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-getting-started/) Go را نصب کردیم، یک module ساختیم و اولین برنامه را اجرا کردیم. حالا سراغ اجزای پایه‌ای می‌رویم که هر برنامه‌ای از آن‌ها استفاده می‌کند: متغیرها، نوع‌ها و کنترل جریان. Go در این بخش‌ها ابزار کمتری از بیشتر زبان‌ها دارد و این عمدی است.

> همه‌ی مثال‌های زیر با Go 1.26.0 روی macOS اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## var و :=

دو راه برای تعریف متغیر داریم:

```go
var count int = 3   // صریح
var name = "Roham"  // نوع استنباط می‌شود
price := 2.5        // فرم کوتاه، فقط داخل تابع
```

`:=` هم تعریف می‌کند و هم مقدار می‌دهد، و داخل تابع تقریباً همیشه همین را می‌نویسید. در سطح package باید از `var` استفاده کنید. متغیر محلیِ استفاده‌نشده خطای کامپایل است، نه هشدار.

## Zero value

متغیری که بدون مقدار تعریف شود هیچ‌وقت «مقداردهی‌نشده» نیست. مقدار صفرِ نوعش (**zero value**) را می‌گیرد:

```go
var i int
var s string
var b bool
var f float64
var p *int
var sl []int
var m map[string]int

fmt.Printf("int:     %v\n", i)
fmt.Printf("string:  %q\n", s)
fmt.Printf("bool:    %v\n", b)
fmt.Printf("float64: %v\n", f)
fmt.Printf("pointer: %v\n", p)
fmt.Printf("slice:   %v (nil: %t, len: %d)\n", sl, sl == nil, len(sl))
fmt.Printf("map:     %v (nil: %t, len: %d)\n", m, m == nil, len(m))
```

```text
int:     0
string:  ""
bool:    false
float64: 0
pointer: <nil>
slice:   [] (nil: true, len: 0)
map:     map[] (nil: true, len: 0)
```

این ویژگی یک دسته کامل از باگ‌ها را حذف می‌کند. slice با مقدار nil هم قابل استفاده است (`len` و `append` روی آن کار می‌کنند)، پس معمولاً لازم نیست دستی مقداردهی‌اش کنید.

## نوع‌های پایه

- عددهای صحیح: `int` و `uint` (هم‌اندازه‌ی معماری سیستم؛ روی سیستم من ۶۴ بیت) و نوع‌هایی با اندازه‌ی مشخص مثل `int8` و `int32` و `int64`. اگر دلیلی ندارید از همان `int` استفاده کنید.
- اعشاری: `float64` پیش‌فرض است؛ `float32` هم هست ولی کم لازم می‌شود.
- `string` دنباله‌ای تغییرناپذیر از بایت‌هاست، معمولاً UTF-8. `byte` نام دیگر `uint8` است و `rune` نام دیگر `int32` که یک code point یونیکد را نگه می‌دارد.

تفاوت بایت و rune وقتی از ASCII بیرون بروید مهم می‌شود:

```go
s := "سلام"
fmt.Println(len(s), len([]rune(s)))   // 8 4

for i, r := range "hé" {
    fmt.Println(i, r, string(r))
}
// 0 104 h
// 1 233 é
```

`len` بایت می‌شمارد (اینجا ۸) و تبدیل به `[]rune` تعداد کاراکتر را می‌دهد (۴). `range` روی string، rune به rune جلو می‌رود و اندیس به اندازه‌ی عرض بایتیِ هر rune می‌پرد.

## ثابت‌ها و iota

ثابت‌ها با `const` تعریف می‌شوند. برای مقدارهای مرتبط، **iota** شمارنده‌ای است که در هر بلوک `const` از صفر شروع می‌کند و در هر خط یکی زیاد می‌شود:

```go
type Weekday int

const (
    Sunday Weekday = iota
    Monday
    Tuesday
)

const (
    _  = iota
    KB = 1 << (10 * iota)
    MB
    GB
)
```

چاپ `Sunday, Monday, Tuesday` خروجی `0 1 2` و چاپ `KB, MB, GB` خروجی `1024 1048576 1073741824` می‌دهد.

## تبدیل ضمنی نداریم

Go هیچ‌وقت بین نوع‌های عددی خودکار تبدیل نمی‌کند. تبدیل را خودتان می‌نویسید:

```go
count := 3
price := 2.5
fmt.Println(float64(count) * price)  // 7.5
fmt.Println(count * price)
```

خط آخر کامپایل نمی‌شود. این خطای دقیقی است که `go run` داد:

```text
./main.go:9:14: invalid operation: count * price (mismatched types int and float64)
```

اول سخت‌گیرانه به نظر می‌رسد، اما جلوی باگ‌های بی‌صدای دقت عددی را می‌گیرد.

## if و for و switch

`if` می‌تواند init statement داشته باشد و متغیرش فقط داخل زنجیره‌ی `if`/`else` زندگی می‌کند:

```go
if n, err := strconv.Atoi("42x"); err != nil {
    fmt.Println("error:", err)
} else {
    fmt.Println(n)
}
// error: strconv.Atoi: parsing "42x": invalid syntax
```

`for` تنها حلقه است، در چند شکل:

```go
for i := 0; i < 3; i++ { }          // کلاسیک
for n < 3 { n++ }                    // مثل while
for { if done { break } }            // بی‌نهایت
for i, v := range []string{"a", "b"} { }  // range
for i := range 3 { }                 // 0 1 2 (از Go 1.22)
```

`switch` به case بعدی نمی‌افتد: فقط case منطبق اجرا می‌شود و `break` لازم نیست. اگر واقعاً خواستید، صریحاً `fallthrough` بنویسید. به‌جای زنجیره‌ی بلند `if/else if` از `switch` بدون عبارت (معادل `switch true`) استفاده کنید. هر case می‌تواند چند مقدار داشته باشد، مثل `case 1, 2:`.

`break` و `continue` مثل همیشه کار می‌کنند. برای حلقه‌های تو در تو، جلوی حلقه‌ی بیرونی یک label می‌گذارید و با نامش می‌نویسید: `continue outer` یا `break outer`.

## کنار هم گذاشتن

یک جدول دما که از حلقه، تبدیل نوع و switch بدون عبارت استفاده می‌کند:

```go
for c := -10; c <= 40; c += 10 {
    f := float64(c)*9/5 + 32

    var label string
    switch {
    case c < 0:
        label = "freezing"
    case c < 20:
        label = "cool"
    case c < 30:
        label = "warm"
    default:
        label = "hot"
    }
    fmt.Printf("%4d C = %6.1f F  %s\n", c, f, label)
}
```

```text
 -10 C =   14.0 F  freezing
   0 C =   32.0 F  cool
  10 C =   50.0 F  cool
  20 C =   68.0 F  warm
  30 C =   86.0 F  hot
  40 C =  104.0 F  hot
```

## چند نکته‌ی مهم

- `:=` داخل بلوک داخلی یک متغیر جدید می‌سازد و متغیر بیرونی را shadow می‌کند. منبع کلاسیکِ «چرا مقدارم عوض نشد» است.
- از map برابر nil می‌شود خواند، اما نوشتن در آن panic می‌دهد؛ اول با `make(map[string]int)` بسازیدش.
- `len(s)` روی string بایت می‌شمارد، نه کاراکتر.
- متغیر و import استفاده‌نشده خطای کامپایل هستند.
- `fallthrough` بدون بررسی شرطِ case بعدی به آن می‌پرد.

## تمرین

۱. برنامه‌ای بنویسید که ۱ تا ۳۰ را چاپ کند، اما برای مضرب ۳ «Fizz»، برای مضرب ۵ «Buzz» و برای هر دو «FizzBuzz» بنویسد. از `switch` بدون عبارت استفاده کنید.
۲. دو نوع جدا به نام‌های `Celsius` و `Fahrenheit` بر پایه‌ی `float64` تعریف کنید و سعی کنید آن‌ها را با هم جمع کنید. خطای کامپایلر را بخوانید.
۳. نوع `Level` را با ثابت‌های `iota` به نام‌های `Debug` و `Info` و `Warn` تعریف کنید و هر کدام را چاپ کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ توابع، `defer` و مدیریت خطا در Go می‌رویم؛ جایی که سبک شناخته‌شده‌ی Go بیشتر خودش را نشان می‌دهد.
