+++
date = '2026-11-12T10:00:00+03:30'
draft = false
title = 'اشاره‌گرها و مدل حافظه در Go'
description = 'اشاره‌گرها، pass-by-value، nil، escape analysis و متغیر حلقه در Go 1.22 واقعاً چطور کار می‌کنند؛ با مثال‌های اجراشده و خروجی واقعی کامپایلر.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "pointers", "memory"]
cover = { image = "/images/covers/go-pointers-memory.fa.png", alt = "اشاره‌گرها و مدل حافظه در Go", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-structs-methods-interfaces/) به متدها **pointer receiver** دادیم، بدون اینکه درباره‌ی خودِ اشاره‌گر زیاد حرف بزنیم. این مقاله همان خلأ را پر می‌کند: `&` و `*` چطور کار می‌کنند، چرا Go همه‌چیز را کپی می‌کند، اشاره‌گر nil با برنامه چه می‌کند و کامپایلر چطور تصمیم می‌گیرد یک مقدار کجا زندگی کند.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام.

## `&`، `*` و pass-by-value

عبارت `&x` آدرس `x` را می‌دهد و `*p` اشاره‌گر را دنبال می‌کند و به مقدار پشتش می‌رسد. مهم‌ترین قاعده این است: **Go همیشه by value پاس می‌دهد**. یعنی تابع از هر آرگومان یک کپی می‌گیرد. خودِ اشاره‌گر هم کپی می‌شود، اما هر دو کپی به یک مقدار اشاره می‌کنند.

```go
func incValue(n int) { n++ }
func incPtr(n *int)  { *n++ }

func birthdayCopy(u User) { u.Age++ }
func birthday(u *User)    { u.Age++ }
```

```
after incValue: 10
after incPtr:   11
after copy:     {Ali 30}
after pointer:  {Ali 31}
```

`incValue` فقط کپیِ خودش را تغییر داد. struct هم دقیقاً مثل int رفتار می‌کند.

## اشاره‌گر به struct، `new` و `&T{}`

با اشاره‌گر به struct می‌نویسیم `p.Age` و Go خودش dereference می‌کند؛ نیازی به `(*p).Age` نیست. هر دوی `new(T)` و `&T{}` یک `*T` می‌دهند؛ `new` همیشه zero value می‌دهد ولی `&T{...}` اجازه می‌دهد فیلدها را مقدار بدهیم.

```go
p := &u
p.Age = 40 // معادل (*p).Age = 40
a := new(User)
b := &User{Name: "Sara"}
fmt.Printf("%+v %+v\n", *a, *b)
```

```
{Ali 40} Ali
{Name: Age:0} {Name:Sara Age:0}
```

در عمل تقریباً همه‌جا `&T{...}` را می‌بینید.

## اشاره‌گر nil

zero value اشاره‌گر `nil` است. مقایسه با nil مشکلی ندارد، اما dereference کردنش panic می‌دهد:

```go
var np *User
fmt.Println(np == nil)
fmt.Println(np.Name)
```

```
true
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x2 addr=0x0 pc=0x102868f48]
goroutine 1 [running]:
main.main()
	.../go-pointers-memory/main.go:58 +0x5a8
```

فایل و شماره‌ی خط در trace دقیقاً به محل dereference اشاره می‌کند، پس پیدا کردن این panicها آسان است. راه‌حل این است که قبل از استفاده از اشاره‌گری که ممکن است واقعاً وجود نداشته باشد، nil بودنش را چک کنیم.

## slice و map: مقدارهایی که reference دارند

slice یک struct کوچک است (اشاره‌گر به آرایه، طول و ظرفیت) و map و channel هم خودشان reference به داده‌ی runtime هستند. وقتی پاسشان می‌دهیم همان header کوچک کپی می‌شود، نه داده:

```go
grow := func(s []int) { s[0] = 99; s = append(s, 4) }
grow(s) // s := []int{1, 2, 3}
func(m map[string]int) { m["a"] = 1 }(m)
```

```
[99 2 3] 3
map[a:1]
```

نوشتن روی عنصر برای caller دیده می‌شود، ولی `append` دیده نمی‌شود: طولِ جدید در کپیِ header داخل تابع ثبت شد، نه در header ما. همان رفتاری که در مقاله‌ی slice دیدیم، این بار با توضیحش.

## stack، heap و escape analysis

محل زندگی مقدار را Go تعیین می‌کند، نه ما. به زبان ساده: مقدارهایی که بعد از برگشتن تابع کسی به آن‌ها دسترسی ندارد روی **stack** ارزان می‌مانند، و مقدارهایی که بیشتر از تابع زنده‌اند به **heap** می‌روند که garbage collector مدیریتش می‌کند. این تصمیم را **escape analysis** کامپایلر می‌گیرد و `-gcflags=-m` آن را نشان می‌دهد:

```go
func sumLocal() int {
	p := Point{1, 2}
	q := &p // اشاره‌گر هست، ولی از تابع بیرون نمی‌رود
	return q.X + q.Y
}

func newPoint() *Point {
	p := Point{1, 2}
	return &p // caller بعد از برگشت از آن استفاده می‌کند
}
```

```
$ go build -gcflags=-m esc.go
./esc.go:5:6: can inline sumLocal
./esc.go:11:6: can inline newPoint
./esc.go:12:2: moved to heap: p
```

فقط `p` در `newPoint` به heap رفت. برگرداندن `&p` در Go کاملاً امن است. معمولاً لازم نیست نگرانش باشید، اما نشان می‌دهد جمله‌ی «اشاره‌گر کند است چون heap می‌رود» زیادی ساده است.

## متغیر حلقه از Go 1.22

قبل از Go 1.22 همه‌ی iterationهای یک حلقه‌ی `for` یک متغیر مشترک داشتند و closureها همان `i` را capture می‌کردند. از 1.22 هر iteration کپی مخصوص خودش را دارد (به شرطی که در `go.mod` نسخه‌ی `go 1.22` یا بالاتر باشد):

```go
var fs []func() int
for i := 0; i < 3; i++ {
	fs = append(fs, func() int { return i })
}
```

```
0 1 2
```

رفتار قدیمی `3 3 3` چاپ می‌کرد. نسخه‌ی قدیمی را اجرا نکردم و این بخش از release notes ‌ی Go 1.22 است.

## اشاره‌گر یا مقدار؟

- وقتی تابع یا متد باید receiver را تغییر دهد، اشاره‌گر.
- برای struct بزرگ که نمی‌خواهیم در هر فراخوانی کپی شود، اشاره‌گر.
- وقتی «نبودنِ مقدار» معنا دارد، اشاره‌گر (`*string` می‌تواند nil باشد، `string` نمی‌تواند).
- در بقیه‌ی موارد مقدار ساده را ترجیح بدهید: ساده‌تر است و چک nil نمی‌خواهد.

## چند نکته‌ی احتیاط

- روی یک type، receiver مقدار و اشاره‌گر را قاطی نکنید؛ یکی را انتخاب کنید.
- اگر اشاره‌گر ممکن است وجود نداشته باشد، قبل از dereference آن را با nil چک کنید.
- کپی header یک slice عناصر را کپی نمی‌کند، پس دو slice ممکن است داده‌ی مشترک داشته باشند.
- گرفتن اشاره‌گر به متغیر حلقه در Go 1.22 به بعد امن است، اما `go.mod` قدیمی‌تر رفتار قبلی را نگه می‌دارد.
- قبل از اندازه‌گیری با اشاره‌گر «بهینه‌سازی» نکنید؛ escape analysis از حدس ما بهتر است.

## تمرین

۱. تابع `swap(a, b *int)` را بنویسید و صدا بزنید.
۲. تابعی بنویسید که `*User` یا در صورت پیدا نشدن نام، `nil` برگرداند و هر دو حالت را در caller مدیریت کنید.
۳. `go build -gcflags=-m` را روی تابعی از خودتان اجرا کنید و یک خط `moved to heap` پیدا کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ package و module می‌رویم: اینکه یک پروژه‌ی Go را چطور به packageها تقسیم کنیم و وابستگی‌ها را با `go.mod` مدیریت کنیم.
