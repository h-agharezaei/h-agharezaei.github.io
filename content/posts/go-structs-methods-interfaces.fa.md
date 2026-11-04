+++
date = '2026-11-10T10:00:00+03:30'
draft = false
title = 'Struct، متد و Interface در Go'
description = 'Go داده و رفتار را چطور مدل می‌کند: struct، embedding، receiver از نوع value و pointer، interface ضمنی، type switch و تله‌ی nil در interface.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "struct", "interface", "methods"]
cover = { image = "/images/covers/go-structs-methods-interfaces.fa.png", alt = "Struct، متد و Interface در Go", hiddenInSingle = true }
+++

فرض کنید می‌خواهید در برنامه‌تان «کاربر» را نشان بدهید: یک اسم و سنی و چند چیز دیگر، و کارهایی که می‌شود با کاربر کرد. در زبانی که کلاس دارد، یک `class` می‌نویسید و هر دو را داخلش می‌گذارید. Go کلاس، وراثت و کلمه‌ی `implements` ندارد. به‌جایش سه تکه‌ی ساده دارد: **struct** برای داده، **متد** برای رفتار و **interface** برای انتزاع. این سه تکه با هم بیشتر کار کلاس را انجام می‌دهند، و interface هم بی‌آنکه نوعی اسمش را ببرد برقرار می‌شود.

بعد از [slice، map و string](/fa/posts/go-slices-maps-strings/) که نوع‌های آماده‌ی زبان بودند، نوبت نوع‌های خودمان است. اول struct و متد را می‌بینیم، بعد interface، و آخر هم یک تله‌ی معروف را که تقریباً هر کسی که Go یاد می‌گیرد یک بار در آن می‌افتد.

> همه‌ی مثال‌های این مقاله را با Go 1.26 اجرا کرده‌ام و خروجی‌ها از همان اجرای واقعی برداشته شده‌اند.

## Struct، literal و zero value

**Struct** مجموعه‌ای از فیلدهای نام‌دار است، مثل یک رکورد یا یک شیء بدون رفتار. نمونه‌ای از آن را با یک **literal** می‌سازید و بهتر است فیلدها را با اسم بنویسید: خواناتر است و اگر ترتیب فیلدها عوض شود، کدتان خراب نمی‌شود.

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

(`%+v` در `Printf` یعنی struct را با نام فیلدها چاپ کن.) در خط اول، دو فیلد را مقدار دادیم و بقیه را نه. خروجی نشان می‌دهد فیلدهای بی‌مقدار هم خالی نیستند: `Admin` برابر `false` است و `City` یک رشته‌ی خالی. این همان **zero value** است که در مقاله‌ی نوع‌ها دیدیم و برای struct فیلد به فیلد اعمال می‌شود. خط دوم نشان می‌دهد `var z User` بدون هیچ مقداردهی، یک `User` کامل و قابل استفاده می‌سازد. به همین دلیل در Go برای نوع‌های ساده معمولاً constructor لازم نیست.

## Embedding: ترکیب به‌جای وراثت

خط `Address` را در `User` ببینید: نوعی که بدون نام فیلد نوشته شده، **embed** شده است. فیلدها و متدهای آن نوع به نوع بیرونی **promote** می‌شوند، یعنی انگار مال خود آن هستند. این‌طور می‌شود:

```go
func (a Address) Describe() string { return "city=" + a.City }

u.Address = Address{City: "Tehran"}
fmt.Println(u.City, u.Describe())
```

```
Tehran city=Tehran
```

(خط اول یک متد تعریف می‌کند؛ ساختارش را در بخش بعد توضیح می‌دهم.) با اینکه `City` و `Describe` در `Address` تعریف شده‌اند، آن‌ها را مستقیم روی `u` صدا زدیم. `User` زیرنوعِ `Address` نیست، فقط یکی را در خودش دارد و فراخوانی را به آن می‌سپارد. این همان ترکیب (**composition**) است: رفتار را بدون ساختن سلسله‌مراتب نوع‌ها دوباره استفاده می‌کنید.

## متد: receiver از نوع value یا pointer

**متد** تابعی است که به یک نوع وصل شده. بین کلمه‌ی `func` و اسم متد یک پارامتر اضافه می‌آید که به آن **receiver** می‌گویند و مشخص می‌کند متد روی چه چیزی کار می‌کند. receiver دو شکل دارد: **value** (یک نسخه از مقدار) یا **pointer** (آدرس خودِ مقدار؛ مقاله‌ی بعدی کامل درباره‌ی اشاره‌گرهاست و این‌جا فقط همین‌قدر لازم داریم). فرقشان مهم است. دو متد می‌سازیم که هر دو کار یکسانی می‌کنند، فقط نوع receiver‌شان فرق دارد:

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

هر دو متد `N` را یکی زیاد می‌کنند. ولی بعد از `IncValue` هنوز `N` برابر ۰ است و بعد از `IncPointer` برابر ۱. دلیلش این است که receiver از نوع value روی یک **کپی** از struct کار می‌کند، پس تغییرش وقتی متد تمام می‌شود از بین می‌رود. receiver از نوع pointer به خودِ struct دسترسی دارد. نتیجه: وقتی متد باید struct را تغییر دهد، یا struct بزرگ است و نمی‌خواهید هر بار کپی شود، از pointer receiver استفاده کنید. برای یکدستی هم اگر یکی از متدهای یک نوع pointer receiver لازم دارد، بقیه را هم pointer بگیرید.

## Interface به‌صورت ضمنی برقرار می‌شود

حالا برسیم به مهم‌ترین ایده. **Interface** مجموعه‌ای از امضای متدهاست، یعنی «هر چیزی که این کارها را بلد باشد». و در Go هیچ‌جا نمی‌نویسید که «این نوع آن interface را پیاده می‌کند». هر نوعی که متدهای لازم را داشته باشد، خودبه‌خود آن interface را برآورده می‌کند.

مثالش اشکال هندسی است. می‌خواهیم مجموع مساحت چند شکل را حساب کنیم، بدون اینکه تابع بداند شکل‌ها از چه نوعی هستند:

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

`Shape` فقط یک شرط دارد: متدی به اسم `Area` که یک `float64` برگرداند. `Rect` و `Circle` اصلاً اسمی از `Shape` نمی‌برند، ولی هر دو `Area()` دارند، پس هر دو `Shape` هستند و می‌توانیم در یک slice از `Shape` کنار هم بگذاریمشان. `TotalArea` هم فقط `Area()` را صدا می‌زند. جواب هم درست است: مساحت مستطیل ۳ در ۴ برابر ۱۲ است و مساحت دایره‌ی شعاع ۱ برابر π، یعنی حدود ۳٫۱۴؛ جمعشان ۱۵٫۱۴. نکته‌ی طراحی این است که مصرف‌کننده interface مورد نیازش را تعریف می‌کند و هر نوعی که جور باشد پذیرفته می‌شود، بدون اینکه نوع‌ها به آن وابسته باشند.

پرکاربردترین interface استاندارد `fmt.Stringer` است، با متد `String() string`. اگر نوعی آن را داشته باشد، `fmt` هنگام چاپ از آن استفاده می‌کند:

```go
func (r Rect) String() string { return fmt.Sprintf("Rect(%gx%g)", r.W, r.H) }

fmt.Println(shapes[0]) // Rect(3x4)
fmt.Println(Circle{R: 2}) // {2}, no String method
```

```
Rect(3x4)
{2}
```

`Rect` متد `String` دارد، پس چاپش به شکل `Rect(3x4)` درمی‌آید. `Circle` ندارد و `fmt` با روش پیش‌فرض فقط فیلدش را چاپ می‌کند: `{2}`.

## `any`، type assertion و type switch

گاهی تابعی باید مقداری از هر نوعی بگیرد. برای این کار `any` را داریم، که نام دیگر interface خالی (`interface{}`) است. چون هیچ متدی نمی‌خواهد، همه‌ی نوع‌ها آن را برآورده می‌کنند. مشکل این است که بعد از گرفتن مقدار از یک interface، دیگر نمی‌دانید نوع واقعی‌اش چیست. دو ابزار برای پس‌گرفتن نوع اصلی داریم: **type assertion** (می‌پرسید «آیا این از نوع X است؟») و **type switch** (چند نوع را پشت هم امتحان می‌کنید).

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

fmt.Println(describe(42))
fmt.Println(describe("hi"))
fmt.Println(describe(Circle{R: 1}))
fmt.Println(describe(3.5))
```

```
is Rect: 2 5
is Circle: false
int 42
string hi
shape with area 3.1
unknown float64
```

دو خط اول: `s` در واقع یک `Rect` است، پس `s.(Rect)` موفق می‌شود و `r` مستطیل اصلی را با فیلدهایش می‌دهد. `s.(Circle)` موفق نمی‌شود و `ok` برابر `false` می‌شود. چهار خط آخر به ترتیب چهار فراخوانی `describe` هستند: عدد ۴۲ به شاخه‌ی `int` می‌رسد، `"hi"` به `string`، دایره‌ی شعاع ۱ چون متد `Area` دارد به `Shape` می‌رسد (مساحتش ۳٫۱ با یک رقم اعشار)، و ۳٫۵ به هیچ‌کدام نمی‌خورد و به `default` می‌رود، که با `%T` نوعش را چاپ می‌کند: `float64`.

همیشه از شکل دومقداری (`v, ok := ...`) استفاده کنید، مگر اینکه واقعاً بخواهید در صورت عدم تطابق panic رخ دهد.

## تله‌ی nil در interface

حالا تله‌ای که در ابتدا قولش را دادم. مقدار یک interface در واقع دو چیز نگه می‌دارد: نوع و مقدار. آن را مثل جعبه‌ای تصور کنید که یک برچسب نوع و یک محتوا دارد. interface فقط وقتی `nil` است که هر دو خالی باشند، یعنی هم برچسب و هم محتوا. حالا اگر یک pointer با مقدار `nil` را از طریق یک interface برگردانید، برچسب نوع پر می‌شود و جعبه دیگر خالی حساب نمی‌شود، با اینکه محتوایش `nil` است:

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

`bad()` یک pointer از نوع `*MyErr` با مقدار `nil` را به‌عنوان `error` برمی‌گرداند. خروجی نشان می‌دهد نتیجه با `nil` برابر نیست. پس `if err != nil` در فراخواننده‌ی `bad()` درست درمی‌آید و برنامه فکر می‌کند خطایی رخ داده، در حالی که کسی خطا نداشته است. `good()` مستقیماً `nil` برمی‌گرداند و همه‌چیز درست است. راه‌حل ساده است: در مسیر موفق مستقیماً `nil` برگردانید.

## Accept interfaces, return structs

یک قاعده‌ی رایج در Go این است که تابع‌ها interface بگیرند و نوع مشخص (struct) برگردانند. گرفتن interface تابع را انعطاف‌پذیر و تست‌پذیر نگه می‌دارد، چون فراخواننده می‌تواند هر نوعی با متدهای لازم، حتی یک نمونه‌ی جعلی برای تست (fake)، بدهد. برگرداندن struct مشخص، همه‌ی فیلدها و متدها را در اختیار فراخواننده می‌گذارد و انتخاب اینکه با کدام interface به آن نگاه کند را به خودش می‌سپارد. interfaceها را کوچک (یک یا دو متد) و در پکیجی تعریف کنید که از آن‌ها استفاده می‌کند، نه پکیجی که پیاده‌شان می‌کند.

## Exported و unexported

در Go سطح دسترسی را حروف بزرگ و کوچک مشخص می‌کنند. `User` و `Name` و `Describe` با حرف بزرگ شروع می‌شوند و پکیج‌های دیگر می‌توانند از آن‌ها استفاده کنند (به این‌ها exported می‌گویند). `user` و `name` و `describe` با حرف کوچک‌اند و فقط داخل همان پکیج دیده می‌شوند. کلمه‌ی `public` یا `private` وجود ندارد.

## اشتباه‌های رایج با receiver و interface

- **مقدارِ value متدهای pointer receiver را ندارد.** اگر `Inc` یک pointer receiver باشد، `var i Incer = C{}` کامپایل نمی‌شود. من همین را امتحان کردم و کامپایلر گفت: `C does not implement Incer (method Inc has pointer receiver)`. به‌جایش `&C{}` بدهید.
- **هرگز pointer از نوع typed-nil را به‌عنوان `error` یا interface دیگر برنگردانید.** همان تله‌ی بالا. مستقیم `nil` برگردانید.
- **از سر عادت سراغ `any` نروید.** `any` بررسی نوع در زمان کامپایل را کنار می‌گذارد؛ یک interface کوچک بهتر است.
- **embedding متدها را promote می‌کند، اما وراثت نیست.** نوع بیرونی تبدیل به `Address` نمی‌شود و جای آن به‌عنوان `Address` هم پذیرفته نمی‌شود.
- **ترکیب receiver از نوع value و pointer روی یک نوع گیج‌کننده است.** یکی را انتخاب کنید.

## تمرین

۱. متد `Perimeter() float64` را به `Rect` و `Circle` اضافه کنید، `Shape` را گسترش دهید و مجموع محیط را چاپ کنید.
۲. یک interface با نام `Notifier` و متد `Send(msg string) error` بسازید و دو struct با نام‌های `EmailNotifier` و `SMSNotifier` بنویسید. یک تابع بنویسید که `Notifier` بگیرد.
۳. نسخه‌ی خودتان از تله‌ی nil در interface را بنویسید و بعد درستش کنید.

## قدم بعدی

«اشاره‌گرها و مدل حافظه در Go»: این‌جا از «کپی» و «pointer» فقط به اندازه‌ی نیاز حرف زدم؛ آن مقاله نشان می‌دهد واقعاً چه اتفاقی می‌افتد.
