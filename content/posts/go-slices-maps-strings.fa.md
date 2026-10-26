+++
date = '2026-11-06T10:00:00+03:30'
draft = false
title = 'Slice، Map و String در Go'
description = 'مروری عملی بر slice، map و string در Go: مشکل backing array مشترک، map از نوع nil، تفاوت بایت و rune در UTF-8 و یک شمارنده‌ی تکرار کلمه.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "slice", "map", "string"]
cover = { image = "/images/covers/go-slices-maps-strings.fa.png", alt = "Slice، Map و String در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-functions-defer-errors/) درباره‌ی تابع‌ها، `defer` و مدیریت خطا در Go حرف زدیم. حالا سراغ سه نوعی می‌رویم که تقریباً در هر برنامه‌ی Go استفاده می‌شوند: **slice**، **map** و **string**. هر کدام رفتاری دارند که تازه‌کارها را غافلگیر می‌کند، برای همین کد را اجرا می‌کنیم و خروجی واقعی را می‌بینیم.

> همه‌ی کدها با Go 1.26 و به‌صورت یک مثال محلی اجرا شده‌اند. مقدار دقیق رشد `cap` جزئیات پیاده‌سازی است و تضمین زبان نیست.

## آرایه و slice

**آرایه** طولش را در نوعش دارد (`[3]int`) و موقع انتساب کپی می‌شود. **Slice** یک هدر کوچک با سه فیلد است: اشاره‌گر به یک آرایه‌ی پشتیبان (backing array)، `len` و `cap`. تقریباً همیشه از slice استفاده می‌کنید.

```go
arr := [3]int{1, 2, 3}
b := arr // آرایه کپی می‌شود
b[0] = 99
fmt.Println(arr, b)

var s []int
for i := 0; i < 10; i++ {
    s = append(s, i)
    fmt.Printf("len=%d cap=%d\n", len(s), cap(s))
}
```

```
[1 2 3] [99 2 3]
len=1 cap=4
len=2 cap=4
len=3 cap=4
len=4 cap=4
len=5 cap=8
...
len=9 cap=16
len=10 cap=16
```

وقتی ظرفیت `append` تمام شود، آرایه‌ی بزرگ‌تری ساخته و داده کپی می‌شود. برای همین باید بنویسید `s = append(s, ...)`؛ نتیجه ممکن است به آرایه‌ی دیگری اشاره کند.

## مشکل کلاسیک: backing array مشترک

برش زدن (slicing) کپی نمی‌کند. دو slice می‌توانند به یک حافظه نگاه کنند.

```go
a := []int{1, 2, 3, 4, 5}
b := a[1:3]
fmt.Println(b, len(b), cap(b))
b[0] = 99
fmt.Println(a, b)
b = append(b, 77) // در cap جا می‌شود: a[3] بازنویسی می‌شود
fmt.Println(a, b)
c := append(a[:2:2], 1000) // full slice expression آرایه‌ی جدید می‌سازد
c[0] = -1
fmt.Println(a, c)
```

```
[2 3] 2 4
[1 99 3 4 5] [99 3]
[1 99 3 77 5] [99 3 77]
[1 99 3 77 5] [-1 99 1000]
```

تغییر `b[0]` روی `a` اثر گذاشت. بدتر اینکه `append` روی `b` بی‌سروصدا `a[3]` را بازنویسی کرد، چون `b` هنوز ظرفیت خالی داشت. شکل سه‌اندیسی `a[:2:2]` ظرفیت را محدود می‌کند، پس `append` مجبور به ساخت آرایه‌ی جدید می‌شود و `a` دست‌نخورده می‌ماند.

## copy، make و تفاوت nil با خالی

```go
var nilS []int
empty := []int{}
fmt.Println(nilS == nil, empty == nil, len(nilS), len(empty))

m := make([]int, 2, 5) // len 2, cap 5
fmt.Println(m, len(m), cap(m))

src := []int{1, 2, 3}
dst := make([]int, len(src))
n := copy(dst, src)
dst[0] = 100
fmt.Println(n, src, dst)
```

```
true false 0 0
[0 0] 2 5
3 [1 2 3] [100 2 3]
```

slice از نوع nil و slice خالی هر دو طول ۰ دارند و با `append` و `range` کار می‌کنند؛ فقط در مقایسه با `nil` فرق دارند. `copy` یک slice مستقل می‌دهد.

## Map

```go
ages := map[string]int{"ali": 30, "sara": 25}
ages["reza"] = 41
v, ok := ages["nobody"]
fmt.Println(v, ok)
if age, ok := ages["sara"]; ok {
    fmt.Println("sara", age)
}
delete(ages, "ali")
delete(ages, "ghost") // بدون اثر
fmt.Println(len(ages), ages)

alias := ages
alias["sara"] = 26
fmt.Println(ages["sara"])
```

```
0 false
sara 25
2 map[reza:41 sara:25]
26
```

کلید ناموجود مقدار صفر برمی‌گرداند؛ پس برای تشخیص «وجود ندارد» از «صفر است» از فرم **comma-ok** استفاده کنید. حذف کلید ناموجود اتفاقی نمی‌اندازد. انتساب map فقط یک reference را کپی می‌کند، پس `alias` و `ages` یک map هستند.

خواندن از map نوع nil مشکلی ندارد، اما نوشتن panic می‌دهد:

```go
var m map[string]int
m["a"] = 1
```

```
panic: assignment to entry in nil map
```

map را با `make` یا literal بسازید. ترتیب پیمایش هم مشخص نیست (unspecified). من یک map هشت‌کلیدی را در دو اجرا پیمایش کردم و یک بار `0 1 2 3 4 5 6 7` و بار دیگر `6 7 0 1 2 3 4 5` گرفتم. هیچ‌وقت به ترتیب تکیه نکنید.

## String

string دنباله‌ای تغییرناپذیر از بایت‌هاست، معمولاً UTF-8. `len` بایت می‌شمارد؛ `utf8.RuneCountInString` تعداد کاراکتر (**rune**) را می‌دهد؛ و `range` روی string، rune برمی‌گرداند.

```go
for _, w := range []string{"hello", "سلام", "🚀"} {
    fmt.Println(w, len(w), utf8.RuneCountInString(w))
}
for i, r := range "سلام" {
    fmt.Printf("%d:%c(%U) ", i, r, r)
}
```

```
hello 5 5
سلام 8 4
🚀 4 1
0:س(U+0633) 2:ل(U+0644) 4:ا(U+0627) 6:م(U+0645)
```

کلمه‌ی فارسی ۴ rune ولی ۸ بایت دارد، و موشک ۱ rune ولی ۴ بایت. ببینید اندیس بایت‌ها دوتا‌دوتا جلو می‌رود. `s[0]` یک بایت می‌دهد (برای `سلام` عدد 216)، نه یک کاراکتر.

برای ساختن string در حلقه از `strings.Builder` استفاده کنید و `Split`، `Join` و `Fields` را بشناسید:

```go
var sb strings.Builder
for i := 0; i < 3; i++ {
    fmt.Fprintf(&sb, "item%d,", i)
}
sb.WriteString("end")
fmt.Println(sb.String())

parts := strings.Split("a,b,,c", ",")
fmt.Printf("%q\n", parts)
fmt.Println(strings.Join(parts, "-"))
fmt.Printf("%q\n", strings.Fields("  go   is \t fun\n"))
```

```
item0,item1,item2,end
["a" "b" "" "c"]
a-b--c
["go" "is" "fun"]
```

`Split` تکه‌های خالی را نگه می‌دارد؛ `Fields` روی هر دنباله از فاصله‌ها می‌شکند و خالی‌ها را حذف می‌کند.

## برنامه‌ی کوچک: شمارش تکرار کلمه

```go
text := "the quick brown fox jumps over the lazy dog the fox"
counts := map[string]int{}
for _, w := range strings.Fields(strings.ToLower(text)) {
    counts[w]++
}
keys := make([]string, 0, len(counts))
for k := range counts {
    keys = append(keys, k)
}
sort.Slice(keys, func(i, j int) bool {
    if counts[keys[i]] != counts[keys[j]] {
        return counts[keys[i]] > counts[keys[j]]
    }
    return keys[i] < keys[j]
})
for _, k := range keys {
    fmt.Printf("%-6s %d\n", k, counts[k])
}
```

```
the    3
fox    2
brown  1
dog    1
jumps  1
lazy   1
over   1
quick  1
```

چون ترتیب map مشخص نیست، کلیدها را در یک slice می‌ریزیم و مرتب می‌کنیم: اول بر اساس تعداد (نزولی)، بعد الفبایی.

## چند نکته که باید حواستان باشد

- نتیجه‌ی `append` را همیشه انتساب بدهید و یادتان باشد ممکن است با slice اصلی حافظه‌ی مشترک داشته باشد یا نه.
- زیر-slice‌ها backing array را share می‌کنند؛ برای استقلال از `copy` یا `a[:n:n]` استفاده کنید.
- نوشتن در map نوع nil panic می‌دهد، خواندن نه.
- به ترتیب پیمایش map تکیه نکنید؛ برای خروجی ثابت کلیدها را مرتب کنید.
- `len(s)` بایت است نه کاراکتر. برای متن از `utf8.RuneCountInString` یا `range` استفاده کنید.

## تمرین

۱. تابع `func removeAt(s []int, i int) []int` را بنویسید و ببینید محتوای slice اصلی چه می‌شود.
۲. شمارنده‌ی کلمه را طوری گسترش بدهید که جمله‌ی فارسی بخواند و تعداد rune هر کلمه را هم چاپ کند.

## قدم بعدی

در مقاله‌ی بعد سراغ struct، متد و interface در Go می‌رویم؛ بلوک‌های ساختن نوع‌های خودمان.
