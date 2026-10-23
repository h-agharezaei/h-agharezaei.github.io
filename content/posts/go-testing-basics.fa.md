+++
date = '2026-12-04T10:00:00+03:30'
draft = false
title = 'تست در Go: table-driven و benchmark'
description = 'نوشتن تست با پکیج testing: فلگ‌های go test، تست‌های table-driven با subtest، helper، coverage، benchmark با b.Loop و نگاهی کوتاه به fuzzing.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "testing", "benchmark"]
cover = { image = "/images/covers/go-testing-basics.fa.png", alt = "تست در Go: table-driven و benchmark", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-generics/) با generics آشنا شدیم. این بار سراغ چیزی می‌رویم که هر روز لازمش دارید: تست. Go ابزار اجرای تست و benchmark را در کتاب‌خانه‌ی استاندارد دارد؛ پس چیزی نصب نمی‌کنید و لازم نیست بین فریم‌ورک‌ها انتخاب کنید. تا آخر مقاله می‌دانید چطور تست **table-driven** بنویسید، فقط یک subtest را اجرا کنید، coverage بگیرید و دو پیاده‌سازی را با benchmark مقایسه کنید.

> همه‌ی مثال‌ها را با Go 1.26 روی یک مک arm64 (Apple M1) اجرا کرده‌ام و خروجی‌ها از همان اجراها کپی شده‌اند.

## مبانی

تست‌ها در فایل‌هایی با پسوند `_test.go` و معمولاً کنار خودِ کد هستند. تست تابعی به نام `TestXxx` است که یک `*testing.T` می‌گیرد. این پکیج کوچک را تست می‌کنیم:

```go
package calc

var ErrDivideByZero = errors.New("divide by zero")

func Divide(a, b int) (int, error) {
	if b == 0 {
		return 0, fmt.Errorf("divide %d by %d: %w", a, b, ErrDivideByZero)
	}
	return a / b, nil
}
```

و تست‌هایش:

```go
func TestDivide(t *testing.T) {
	got, err := Divide(10, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 5 {
		t.Errorf("Divide(10, 2) = %d, want 5", got)
	}
}

func TestDivideByZero(t *testing.T) {
	_, err := Divide(1, 0)
	if !errors.Is(err, ErrDivideByZero) {
		t.Fatalf("err = %v, want ErrDivideByZero", err)
	}
}
```

تفاوت `t.Error` و `t.Fatal`: هر دو تست را شکست‌خورده علامت می‌زنند، اما `Fatal` تست را همان لحظه متوقف می‌کند و `Error` اجازه می‌دهد ادامه پیدا کند. وقتی ادامه دادن بی‌معناست از `Fatal` استفاده کنید؛ مثلاً در چک `err` بالا، اگر خطا داریم `got` بی‌معنی است. تست دوم همان `errors.Is` را از [مقاله‌ی خطاها](/fa/posts/go-functions-defer-errors/) به کار می‌برد: چون `Divide` با `%w` wrap می‌کند، مقایسه با `==` شکست می‌خورد.

تست‌ها را با `go test` اجرا کنید. من `-v` را برای خروجی مفصل و `-count=1` را برای دور زدن cache تست می‌گذارم؛ وگرنه تست پکیجی که کدش عوض نشده دوباره اجرا نمی‌شود. فلگ `-run` یک regular expression می‌گیرد و تست‌ها را با نام انتخاب می‌کند.

## یک تست شکست‌خورده

تست سبز چیز زیادی یاد نمی‌دهد؛ پس یک تست عمداً خراب (در پوشه‌ی جدا در پروژه‌ی دمو):

```go
func add(a, b int) int { return a - b } // bug

func TestAdd(t *testing.T) {
	if got := add(2, 3); got != 5 {
		t.Errorf("add(2, 3) = %d, want 5", got)
	}
}
```

```text
--- FAIL: TestAdd (0.00s)
    b_test.go:9: add(2, 3) = -1, want 5
FAIL
FAIL	example.com/brokentest	0.298s
FAIL
```

قالب `got ..., want ...` باعث می‌شود پیام بدون باز کردن کد خوانا باشد. توجه کنید که exit code ناصفر است و CI به همین تکیه می‌کند.

## تست‌های table-driven و subtest

وقتی برای یک تابع چند حالت دارید، تکرار بدنه‌ی تست شلوغ می‌شود. روش رایج Go یک slice از حالت‌ها و یک حلقه است و `t.Run` برای هر حالت یک **subtest** با نام می‌سازد. مقایسه را هم در یک helper گذاشته‌ام که `t.Helper()` صدا می‌زند تا شکست در خطِ فراخواننده گزارش شود، نه داخل helper:

```go
func Slug(s string) string {
	return strings.Join(strings.Fields(strings.ToLower(s)), "-")
}

func assertSlug(t *testing.T, in, want string) {
	t.Helper()
	if got := Slug(in); got != want {
		t.Errorf("Slug(%q) = %q, want %q", in, got, want)
	}
}

func TestSlug(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{"simple", "Hello World", "hello-world"},
		{"extra spaces", "  Go   is fun ", "go-is-fun"},
		{"empty", "", ""},
		{"single", "Go", "go"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			assertSlug(t, tt.in, tt.want)
		})
	}
}
```

اضافه کردن یک حالت فقط یک خط است. فاصله در نام subtest به underscore تبدیل می‌شود. برای اجرای فقط یک subtest در `-run` از اسلش استفاده کنید:

```text
$ go test -v -count=1 -run 'TestSlug/extra' .
=== RUN   TestSlug
=== RUN   TestSlug/extra_spaces
=== PAUSE TestSlug/extra_spaces
=== CONT  TestSlug/extra_spaces
--- PASS: TestSlug (0.00s)
    --- PASS: TestSlug/extra_spaces (0.00s)
PASS
```

خطوط `PAUSE` و `CONT` از `t.Parallel()` می‌آیند: subtestها می‌توانند همزمان با هم اجرا شوند. از Go 1.22 هر تکرار حلقه `tt` مخصوص خودش را دارد، پس closure امن است. فقط برای تست‌هایی که state قابل‌تغییر مشترک ندارند از آن استفاده کنید.

## Coverage

```text
$ go test -count=1 -cover .
ok  	example.com/testing-basics	0.249s	coverage: 100.0% of statements
```

برای این پکیج کوچک ۱۰۰٪ شد. coverage فقط می‌گوید کدام خط‌ها اصلاً اجرا نشده‌اند و نمی‌گوید assertionهایتان خوب است یا نه؛ پس آن را ابزاری برای پیدا کردن کدِ بدون تست بدانید، نه هدف.

## Benchmark

benchmark تابعی به نام `BenchmarkXxx` است که یک `*testing.B` می‌گیرد. از Go 1.24 حلقه را با `b.Loop()` می‌نویسیم؛ کامپایل و اجرایش را روی 1.26 تأیید کرده‌ام. دو روش چسباندن رشته را مقایسه می‌کنیم:

```go
func ConcatPlus(parts []string) string {
	s := ""
	for _, p := range parts {
		s += p
	}
	return s
}

func ConcatBuilder(parts []string) string {
	var sb strings.Builder
	for _, p := range parts {
		sb.WriteString(p)
	}
	return sb.String()
}

func BenchmarkConcatPlus(b *testing.B) {
	for b.Loop() {
		ConcatPlus(parts)
	}
}
```

(`BenchmarkConcatBuilder` دقیقاً همین است با تابع دیگر، و `parts` یک slice سطح پکیج با ۱۰۰۱ رشته‌ی کوتاه است. یک تست معمولی هم چک می‌کند که هر دو تابع نتیجه‌ی یکسان بدهند.) با `-run xxx` تست‌های عادی را رد می‌کنیم، با `-bench .` همه‌ی benchmarkها را اجرا می‌کنیم و `-benchmem` تعداد allocation را هم نشان می‌دهد:

```text
$ go test -count=1 -run xxx -bench . -benchmem .
goos: darwin
goarch: arm64
cpu: Apple M1
BenchmarkConcatPlus-8      	   10000	    110425 ns/op	 1063869 B/op	     999 allocs/op
BenchmarkConcatBuilder-8   	  296140	      3936 ns/op	    5368 B/op	      10 allocs/op
```

این اعداد از یک اجرا روی ماشین من (macOS با arm64 و Go 1.26) است و روی ماشین شما فرق می‌کند. در همین اجرا نسخه‌ی `+=` حدود ۲۸ برابر کندتر بود و در هر فراخوانی نزدیک هزار allocation داشت، در برابر ده تا، چون هر `+=` کل رشته‌ی ساخته‌شده تا اینجا را کپی می‌کند. پسوند `-8` همان `GOMAXPROCS` است.

## fuzzing در یک پاراگراف

Go fuzzing هم دارد: تابع `FuzzXxx(f *testing.F)` با seedهای `f.Add` و `f.Fuzz`، که با `go test -fuzz FuzzReverse -fuzztime 5s` اجرا می‌شود. من آن را روی تابعی که rune‌های رشته را برعکس می‌کند و با خاصیت «دوبار برعکس کردن همان ورودی را برمی‌گرداند» (با رد کردن UTF-8 نامعتبر) امتحان کردم. در ۵ ثانیه حدود ۳۰۰ هزار اجرا انجام شد و چیزی پیدا نکرد. اگر شکستی پیدا شود زیر `testdata/` ذخیره و با `go test` ساده دوباره اجرا می‌شود.

## چند نکته که باید حواستان باشد

- اگر `-count=1` را فراموش کنید و تعجب کنید چرا چیزی دوباره اجرا نمی‌شود: نتیجه‌ی پکیج‌های بدون تغییر cache می‌شود.
- وقتی خط‌های بعدی به چک قبلی وابسته‌اند `t.Fatal`، و وقتی می‌خواهید همه‌ی شکست‌ها را ببینید `t.Error` بزنید.
- به حالت‌های جدول نام خوب بدهید؛ با همین نام شکست‌خورده را پیدا و اجرا می‌کنید.
- کدی را benchmark نکنید که کامپایلر بتواند حذفش کند: نتیجه را استفاده کنید یا به `b.Loop()` تکیه کنید که برای فراخوانیِ داخل حلقه جلوی این مشکل را می‌گیرد.
- subtestهای موازی نباید state قابل‌تغییر مشترک داشته باشند.

## تمرین

۱. یک تست table-driven برای `Divide` بنویسید با حالت‌های نتیجه‌ی عادی، عدد منفی و تقسیم بر صفر (خطا را با `errors.Is` چک کنید).
۲. تابع `ConcatJoin` را با `strings.Join` بنویسید و benchmark سوم را اضافه کنید. قبل از اجرا حدس بزنید کجا قرار می‌گیرد.
۳. `go test -cover` را اجرا کنید و شاخه‌ای را پیدا کنید که تستش نکرده‌اید.

## قدم بعدی

در مقاله‌ی بعد سراغ خواندن و نوشتن فایل می‌رویم، با `io.Reader` و `io.Writer` آشنا می‌شویم و JSON را در Go encode و decode می‌کنیم.
