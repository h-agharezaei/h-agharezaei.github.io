+++
date = '2026-11-30T10:00:00+03:30'
draft = false
title = 'Generics در Go'
description = 'type parameter، constraint، تابع و type جنریک، type inference و پکیج‌های slices و maps و cmp؛ با خروجی واقعی کامپایلر و توصیه‌ی صادقانه برای استفاده.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "generics", "slices", "maps"]
cover = { image = "/images/covers/go-generics.fa.png", alt = "Generics در Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-sync-select-context/) با goroutine، channel و context کار کردیم. این مقاله درباره‌ی **generics** است که از Go 1.18 آمده. با آن می‌شود یک تابع یا type نوشت که برای چند type کار کند و کامپایلر باز هم همه‌چیز را چک کند. می‌بینیم چه مشکلی را حل می‌کند، سینتکس constraint چیست، چند تابع و container جنریک می‌نویسیم، سراغ پکیج‌های استاندارد می‌رویم و در آخر می‌گوییم کِی نباید سراغش رفت.

> همه‌ی مثال‌ها را با Go 1.26 روی macOS (arm64) اجرا کرده‌ام.

## مشکل: یک کد، چند type

بدون generics، `Min` برای int و `Min` برای float دو کپی از یک منطق‌اند:

```go
func MinInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func MinFloat(a, b float64) float64 { /* identical body */ }
```

استفاده از `any` و type assertion هم type safety را از بین می‌برد. **type parameter** این مشکل را حل می‌کند.

## type parameter و constraint

لیست type parameter داخل کروشه و قبل از پارامترهای معمولی می‌آید. هر پارامتر یک **constraint** دارد که می‌گوید چه typeهایی مجازند. `any` همه‌چیز را قبول می‌کند، ولی آن‌وقت فقط کارهایی را می‌توانید بکنید که همه‌ی typeها پشتیبانی می‌کنند. `comparable` یعنی typeهایی که `==` دارند. برای `<` به `cmp.Ordered` از کتاب‌خانه‌ی استاندارد نیاز داریم:

```go
func Min[T cmp.Ordered](a, b T) T {
	if a < b {
		return a
	}
	return b
}

fmt.Println(Min(3, 2), Min(1.5, 2.5), Min("b", "a"))
fmt.Println(Min[float64](1, 2.5))
```

```
2 1.5 a
1
```

**type inference** باعث شد بتوانیم `Min(3, 2)` را بدون `[int]` بنویسیم. اگر بخواهید type را صریح بدهید هم می‌شود، مثل `Min[float64](1, 2.5)` که `1`ِ untyped را float می‌کند.

## constraint یک interface است

constraint سفارشی یک interface است که لیستی از typeها دارد. علامت `~` یعنی «هر typeای که underlying type آن این است»، پس typeهای نام‌دار خودتان هم قبول می‌شوند:

```go
type Number interface {
	~int | ~int64 | ~float64
}

func Sum[T Number](s []T) T {
	var total T
	for _, v := range s {
		total += v
	}
	return total
}

type Cents int

fmt.Println(Sum([]float64{1.5, 2.5}), Sum([]Cents{100, 250}))
```

```
4 350
```

بدون `~`، `Cents` رد می‌شد، چون type آن `Cents` است نه `int`.

## تابع‌های کمکی جنریک

تابع می‌تواند چند type parameter داشته باشد. این سه تابع کلاسیک را به‌علاوه‌ی `Keys` ببینید:

```go
func Map[T, U any](s []T, f func(T) U) []U { /* ... */ }
func Filter[T any](s []T, keep func(T) bool) []T { /* ... */ }
func Reduce[T, A any](s []T, init A, f func(A, T) A) A { /* ... */ }
func Keys[K comparable, V any](m map[K]V) []K { /* ... */ }
```

```go
nums := []int{1, 2, 3, 4, 5}
fmt.Println(Map(nums, func(n int) string { return "#" + strconv.Itoa(n) }))
fmt.Println(Filter(nums, func(n int) bool { return n%2 == 0 }))
fmt.Println(Reduce(nums, 0, func(a, n int) int { return a + n }))
```

```
[#1 #2 #3 #4 #5]
[2 4]
15
```

کلید map باید `comparable` باشد، برای همین `Keys` این constraint را روی `K` می‌خواهد. ترتیب پیمایش map تصادفی است، پس اگر چاپ می‌کنید نتیجه را sort کنید.

## type جنریک

type هم می‌تواند پارامتر داشته باشد. متدها پارامتر را تکرار می‌کنند ولی نمی‌توانند پارامتر جدید اضافه کنند:

```go
type Stack[T any] struct{ items []T }

func (s *Stack[T]) Push(v T) { s.items = append(s.items, v) }

func (s *Stack[T]) Pop() (T, bool) {
	var zero T
	if len(s.items) == 0 {
		return zero, false
	}
	v := s.items[len(s.items)-1]
	s.items = s.items[:len(s.items)-1]
	return v, true
}

type Set[T comparable] map[T]struct{}

func (s Set[T]) Add(v T)      { s[v] = struct{}{} }
func (s Set[T]) Has(v T) bool { _, ok := s[v]; return ok }
```

```
b true
0 false
true false
```

خط اول `Pop` روی یک `Stack[string]` است که "a" و "b" در آن گذاشته‌ایم؛ خط دوم `Pop` روی `Stack[int]` خالی؛ خط سوم `Has("go")` و `Has("rust")` روی set ای که فقط "go" دارد. `var zero T` راه برگرداندن zero value است وقتی type را نمی‌دانیم. type جنریک را بدون مشخص کردن پارامتر نمی‌شود استفاده کرد: باید `Stack[string]` بنویسید.

## کتاب‌خانه‌ی استاندارد موارد رایج را دارد

قبل از نوشتن تابع کمکی خودتان به `slices`، `maps` و `cmp` نگاه کنید:

```go
fmt.Println(slices.Contains(nums, 3), slices.Index(nums, 4), slices.Max(nums))
fmt.Println(slices.Sorted(maps.Keys(ages)))
keys := slices.Collect(maps.Keys(ages))
slices.Sort(keys)
fmt.Println(cmp.Compare(2, 5))
```

```
true 3 5
[ali reza sara]
-1
```

از Go 1.23 به بعد `maps.Keys` یک iterator برمی‌گرداند نه slice. با `slices.Collect` آن را به slice تبدیل کنید، یا با `slices.Sorted` هم جمع کنید و هم sort.

## وقتی constraint رعایت نشود

اگر type شرط را نداشته باشد، کامپایلر همان‌جا که تابع را صدا زده‌اید خطا می‌دهد. ما `Min(User{"a"}, User{"b"})` را صدا زدیم:

```
badconstraint/main.go:18:17: User does not satisfy cmp.Ordered (User missing in ~int | ~int8 | ~int16 | ~int32 | ~int64 | ~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 | ~uintptr | ~float32 | ~float64 | ~string)
```

خطا در زمان کامپایل است و همین هدف اصلی است.

## چند نکته‌ی احتیاط

- از کد concrete شروع کنید. اول تابع را برای یک type بنویسید؛ وقتی کاربرد دوم واقعاً آمد جنریکش کنید.
- اگر فقط رفتار مهم است، معمولاً interface ساده‌تر است. `io.Reader` به type parameter نیازی ندارد.
- فقط برای حذف چند خط تکرار چیزی را جنریک نکنید؛ نسخه‌ی جنریک را بخوانید و ببینید فهمیدنش سخت‌تر شده یا نه.
- متد نمی‌تواند type parameter مخصوص خودش را داشته باشد، فقط خودِ type می‌تواند.
- وقتی inference شکست بخورد خطایی مثل `cannot infer S` می‌گیرید؛ type argumentها را صریح بدهید.

## تمرین

۱. تابع `Max[T cmp.Ordered](s []T) (T, bool)` را بنویسید که برای slice خالی false برگرداند.
۲. به `Stack[T]` متد `Len() int` و `Peek() (T, bool)` اضافه کنید.
۳. تابع `Uniq[T comparable](s []T) []T` را با استفاده از `Set[T]` بنویسید که تکراری‌ها را حذف کند و ترتیب را نگه دارد.

## قدم بعدی

در مقاله‌ی بعد سراغ تست در Go می‌رویم: table-driven test با پکیج `testing`، subtest و benchmark.
