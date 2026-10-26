+++
date = '2026-11-10T10:00:00+03:30'
draft = false
title = 'Struct، متد و Interface در Go'
description = 'Go داده و رفتار را چطور مدل می‌کند: struct، embedding، receiver از نوع value و pointer، interface ضمنی، type switch و تله‌ی nil در interface.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "struct", "interface", "methods"]
cover = { image = "/images/covers/go-structs-methods-interfaces.fa.png", alt = "Struct، متد و Interface در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-slices-maps-strings/) با slice، map و string آشنا شدیم. حالا به راهی نیاز داریم که داده را گروه‌بندی کنیم و رفتار را به آن وصل کنیم. Go کلاس و وراثت ندارد. به‌جایش **struct** برای داده، **متد** برای رفتار و **interface** برای انتزاع دارد، و همین سه تکه‌ی کوچک بیشتر کاری را که با کلاس انجام می‌دادید پوشش می‌دهند.

> همه‌ی مثال‌های این مقاله را با Go 1.26 اجرا کرده‌ام و خروجی‌ها از همان اجرای واقعی کپی شده‌اند.

## Struct، literal و zero value

**Struct** مجموعه‌ای از فیلدهای نام‌دار است. literal را با نام فیلد بنویسید: با عوض شدن ترتیب فیلدها خراب نمی‌شود و خواناتر است.

```go
type Address struct {
	City string
}

type User struct {
	Name  string
	Age   int
	Admin bool
	Address // embedded
}

u := User{Name: "Roham", Age: 30}
fmt.Printf("%+v\n", u)
var z User
fmt.Printf("zero: %+v\n", z)
```

```
{Name:Roham Age:30 Admin:false Address:{City:}}
zero: {Name: Age:0 Admin:false Address:{City:}}
```

هر فیلدی که مقدار ندهید **zero value** می‌گیرد. struct همان لحظه‌ی تعریف قابل استفاده است، برای همین در Go برای نوع‌های ساده معمولاً constructor لازم نیست.

## Embedding: ترکیب به‌جای وراثت

خط `Address` در `User` را ببینید: نوعی که نام فیلد ندارد **embed** شده است. فیلدها و متدهایش به نوع بیرونی **promote** می‌شوند.

```go
func (a Address) Describe() string { return "city=" + a.City }

u.Address = Address{City: "Tehran"}
fmt.Println(u.City, u.Describe())
```

```
Tehran city=Tehran
```

`User` زیرنوعِ `Address` نیست، فقط یکی را در خودش دارد و فراخوانی را به آن می‌سپارد. این همان composition است: رفتار را بدون ساختن سلسله‌مراتب نوع‌ها دوباره استفاده می‌کنید.

## متد: receiver از نوع value یا pointer

متد تابعی است که یک receiver دارد. receiver می‌تواند value یا pointer باشد و تفاوتشان مهم است:

```go
type Counter struct{ N int }

func (c Counter) IncValue()    { c.N++ }
func (c *Counter) IncPointer() { c.N++ }

c := Counter{}
c.IncValue()
fmt.Println("after IncValue:", c.N)
c.IncPointer()
fmt.Println("after IncPointer:", c.N)
```

```
after IncValue: 0
after IncPointer: 1
```

receiver از نوع value روی یک کپی کار می‌کند و تغییر از بین می‌رود. وقتی متد باید struct را تغییر دهد، یا struct بزرگ است، از pointer receiver استفاده کنید. برای یکدستی، اگر یکی از متدها pointer receiver لازم دارد، همه را pointer بگیرید. چرایی رفتار pointerها را در مقاله‌ی بعد می‌بینیم.

## Interface به‌صورت ضمنی برقرار می‌شود

**Interface** مجموعه‌ای از امضای متدهاست. کلمه‌ی `implements` وجود ندارد: هر نوعی که آن متدها را داشته باشد interface را برآورده می‌کند.

```go
type Shape interface {
	Area() float64
}

type Rect struct{ W, H float64 }
type Circle struct{ R float64 }

func (r Rect) Area() float64   { return r.W * r.H }
func (c Circle) Area() float64 { return math.Pi * c.R * c.R }

func TotalArea(shapes []Shape) float64 {
	var t float64
	for _, s := range shapes {
		t += s.Area()
	}
	return t
}

shapes := []Shape{Rect{W: 3, H: 4}, Circle{R: 1}}
fmt.Printf("total: %.2f\n", TotalArea(shapes))
```

```
total: 15.14
```

`Rect` و `Circle` اصلاً اسمی از `Shape` نمی‌برند. مصرف‌کننده interface مورد نیازش را تعریف می‌کند و هر نوعی که جور باشد پذیرفته می‌شود.

پرکاربردترین interface استاندارد `fmt.Stringer` با متد `String() string` است. اگر آن را اضافه کنید، `fmt` هنگام چاپ از آن استفاده می‌کند.

```go
func (r Rect) String() string { return fmt.Sprintf("Rect(%gx%g)", r.W, r.H) }

fmt.Println(shapes[0]) // Rect(3x4)
fmt.Println(Circle{R: 2}) // {2}, no String method
```

```
Rect(3x4)
{2}
```

## `any`، type assertion و type switch

`any` نام دیگر interface خالی یعنی `interface{}` است و همه‌ی نوع‌ها آن را برآورده می‌کنند. برای برگرداندن مقدار اصلی از **type assertion** یا **type switch** استفاده می‌کنیم.

```go
var s Shape = Rect{2, 5}
if r, ok := s.(Rect); ok {
	fmt.Println("is Rect:", r.W, r.H)
}
_, ok := s.(Circle)
fmt.Println("is Circle:", ok)

func describe(v any) string {
	switch x := v.(type) {
	case int:
		return fmt.Sprintf("int %d", x)
	case string:
		return "string " + x
	case Shape:
		return fmt.Sprintf("shape with area %.1f", x.Area())
	default:
		return fmt.Sprintf("unknown %T", x)
	}
}
```

```
is Rect: 2 5
is Circle: false
int 42
string hi
shape with area 3.1
unknown float64
```

همیشه از شکل دومقداری (`v, ok := ...`) استفاده کنید، مگر اینکه panic در صورت عدم تطابق را بخواهید.

## تله‌ی nil در interface

مقدار interface یک جفت (type, value) نگه می‌دارد و فقط وقتی `nil` است که هر دو خالی باشند. اگر یک pointer با مقدار nil را از طریق interface برگردانید، interface غیر nil می‌شود:

```go
type MyErr struct{}

func (*MyErr) Error() string { return "my error" }

func bad() error {
	var p *MyErr = nil
	return p
}

func good() error { return nil }

fmt.Println("bad() == nil:", bad() == nil)
fmt.Println("good() == nil:", good() == nil)
```

```
bad() == nil: false
good() == nil: true
```

پس `if err != nil` برای `bad()` درست است، با اینکه pointer داخلش nil است. راه‌حل: در مسیر موفق مستقیماً `nil` برگردانید.

## Accept interfaces, return structs

یک قاعده‌ی رایج: تابع‌ها interface بگیرند و نوع مشخص برگردانند. گرفتن interface تابع را انعطاف‌پذیر و تست‌پذیر نگه می‌دارد، چون فراخواننده می‌تواند هر نوعی با متدهای لازم، حتی یک fake، بدهد. برگرداندن struct مشخص، همه‌ی فیلدها و متدها را در اختیار فراخواننده می‌گذارد و انتخاب اینکه با کدام interface به آن نگاه کند را به خودش می‌سپارد. interfaceها را کوچک (یک یا دو متد) و در پکیجی تعریف کنید که از آن‌ها استفاده می‌کند، نه پکیجی که پیاده‌شان می‌کند.

## Exported و unexported

حروف بزرگ و کوچک همان سطح دسترسی است. `User`، `Name` و `Describe` با حرف بزرگ شروع می‌شوند و پکیج‌های دیگر می‌توانند از آن‌ها استفاده کنند. `user`، `name` یا `describe` فقط داخل همان پکیج دیده می‌شوند. کلمه‌ی `public` یا `private` وجود ندارد.

## چند نکته که باید حواستان باشد

- مقدار از نوع value، متدهای pointer receiver را در interface ندارد. من `var i Incer = C{}` را امتحان کردم که `Inc` در آن pointer receiver است و کامپایلر گفت: `C does not implement Incer (method Inc has pointer receiver)`. از `&C{}` استفاده کنید.
- هرگز یک pointer از نوع typed-nil را به‌عنوان `error` یا interface دیگر برنگردانید. مستقیم `nil` برگردانید.
- از سر عادت سراغ `any` نروید. بررسی نوع در زمان کامپایل را کنار می‌گذارد؛ interface کوچک بهتر است.
- embedding متدها را promote می‌کند اما وراثت نیست: نوع بیرونی تبدیل به `Address` نمی‌شود.
- ترکیب receiver از نوع value و pointer روی یک نوع گیج‌کننده است. یکی را انتخاب کنید.

## تمرین

1. متد `Perimeter() float64` را به `Rect` و `Circle` اضافه کنید، `Shape` را گسترش دهید و مجموع محیط را چاپ کنید.
2. یک interface با نام `Notifier` و متد `Send(msg string) error` بسازید و دو struct با نام‌های `EmailNotifier` و `SMSNotifier` بنویسید. یک تابع بنویسید که `Notifier` بگیرد.
3. نسخه‌ی خودتان از تله‌ی nil در interface را بنویسید و بعد درستش کنید.

## قدم بعدی

تا اینجا مدام از «کپی» و «pointer» حرف زدم بی‌آنکه درست توضیحشان بدهم. در مقاله‌ی بعد، pointerها و مدل حافظه در Go، می‌بینیم واقعاً چه اتفاقی می‌افتد.
