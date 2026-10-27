+++
date = '2027-03-17T10:00:00+03:30'
draft = false
title = 'code review مؤثر'
description = 'code review مؤثر در Go: اول gofmt، vet، race detector و staticcheck، بعد آنچه فقط آدم می‌بیند و روش گفتن مؤدبانه‌ی آن، همراه با اجرای واقعی.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["code-review", "software-engineering", "testing", "go", "collaboration"]
cover = { image = "/images/covers/eng-code-review.fa.png", alt = "code review مؤثر", hiddenInSingle = true }
+++

در [refactor امن](/fa/posts/eng-refactoring-safely/) شبکه‌ی ایمنی یک تست بود. {{< term "code-review" "code review" >}} شبکه‌ی دیگری است که از آدم‌ها ساخته شده و گران است: توجه reviewer کمیاب‌ترین چیز در تیم است. قاعده‌ی من این است که اول ماشین‌ها بروند و آدم‌ها فقط چیزی را ببینند که ماشین نمی‌بیند. مبانی تست: [تست در Go](/fa/posts/go-testing-basics/)؛ لایه‌بندی: [ساختار پروژه و clean architecture](/fa/posts/go-project-layout-clean-architecture/). نظرها با **به تجربه‌ی من** مشخص شده‌اند و یافته‌های زیر اجرا شده‌اند.

> Go 1.26، یک repo محلی git با دو commit و یک branch؛ کد را خودم و عمداً معیوب نوشته‌ام.

## یک PR معیوب

روی `main` یک تابع `Page` با تست هست. branch با نام `add-bulk-check` یک link checker اضافه می‌کند:

```text
$ git diff main --stat
 check.go      | 54 ++++++++++++++++++++++++++++++++++++++++++++++++++++++
 check_test.go | 25 +++++++++++++++++++++++++
 2 files changed, 79 insertions(+)
```

عیب‌های کاشته‌شده: یک خط با تورفتگی اشتباه، فعل `Printf` نادرست، نوشتن هم‌زمان در map، خطای نادیده‌گرفته‌شده، body بسته‌نشده‌ی پاسخ، goroutine نشت‌کرده و `LastPage` که `total / size` برمی‌گرداند. هسته‌ی diff:

```go
func Status(url string) (int, error) {
	resp, err := http.Get(url)
	if err != nil {
		return 0, err
	}
	return resp.StatusCode, nil
}

go func() {
	defer wg.Done()
	code, _ := Status(u)
	fmt.Printf("checked %s: %s\n", u, code)
	out[u] = code
}()
```

## اول ماشین‌ها

```text
$ gofmt -l .
check.go

$ go vet ./...
check.go:27:29: fmt.Printf format %s has arg code of wrong type int
```

`go test -race` (با `-vet=off`، چون `go test` ساده یک زیرمجموعه‌ی vet را اجرا می‌کند و روی همین خط Printf می‌ایستد) پیام `WARNING: DATA RACE` را چاپ کرد، با دو stack که به نوشتن map در خط ۲۸ اشاره می‌کنند، و بعد `--- FAIL: TestCheckAll`. {{< term "race-condition" "race" >}} فقط گرفته شد چون تست دو URL را هم‌زمان می‌زند.

staticcheck را با `go run honnef.co/go/tools/cmd/staticcheck@2025.1.1 ./...` با نسخه‌ی ثابت اجرا کردم و فقط یک مورد گزارش کرد، همان Printf (`SA5009`). خطای نادیده‌گرفته، body بسته‌نشده، نشت و مرز را **نگفت**. {{< term "static-analysis" "تحلیلگر ایستا" >}} فقط الگوهایش را می‌شناسد. هر چهار را در {{< term "ci" "CI" >}} بگذارید تا آدم برای این‌ها کامنت خرج نکند.

## آنچه فقط آدم می‌گیرد

`go test -vet=off` ساده سبز است. پوشش دلیلش را نشان می‌دهد:

```text
Status    75.0%
CheckAll  100.0%
FirstOK   0.0%
LastPage  66.7%
```

سه یافته‌ی باقی‌مانده که هیچ‌کدام از ابزارهای بالا نگفتند:

- body بسته‌نشده: `Status` هیچ‌وقت `resp.Body.Close()` را صدا نمی‌زند. تست با این حال می‌گذرد.
- goroutine نشت‌کرده: در یک تست موقت `FirstOK` را با سه URL صدا زدم؛ بعد از ۲۰۰ میلی‌ثانیه goroutineها از ۳ به ۱۱ رسیدند (احتمالاً بعضی goroutine اتصال‌اند که جدایشان نکردم). بازنده‌ها روی channel بدون بافر برای همیشه گیر می‌کنند.
- مرز: `LastPage(11, 5)` عدد ۲ داد؛ یازده مورد سه صفحه می‌خواهد. تنها تست ۱۰ و ۵ را زده بود، موردی که اتفاقاً درست است.

بعد چیزهایی که ابزار نمی‌تواند قضاوت کند: `Status` و `FirstOK` تابع `http.Get` را پنهان می‌کنند، پس بدون سرور زنده تست‌پذیر نیستند، و client پیش‌فرض timeout ندارد. این طراحی است و جایش review است.

## به شکل what / why / suggestion بگویید

```text
check.go:11  What: resp.Body is never closed.
             Why: connections are not reused and leak under load.
             Suggestion: defer resp.Body.Close() after the err check.

check.go:49  What: LastPage(11, 5) returns 2.
             Why: integer division rounds down, the last partial page is lost.
             Suggestion: (total+size-1)/size, plus a test with 11 and 5.
```

**به تجربه‌ی من** کامنتی که دلیل و راه‌حل دارد در یک دور درست می‌شود؛ «این غلط است» خالی بحث راه می‌اندازد. لحن هم کمک می‌کند: بپرسید («اگر فراخوانی اول شکست بخورد این بلاک نمی‌شود؟»)، موارد کوچک را با `nit:` شروع کنید و کار خوب را تعریف کنید.

## سمت نویسنده

- قبل از اینکه از کسی بخواهید، diff خودتان را بخوانید؛ **به تجربه‌ی من** چند مشکل را خودتان پیدا می‌کنید.
- PR کوچک. دو branch موقت ساختم، با ۴۰ و ۹۰۰ خط اضافه، فقط برای نشان دادن آمار: `1 file changed, 40 insertions(+)` در برابر `6 files changed, 900 insertions(+)`. **به تجربه‌ی من** دومی را کسی نمی‌خواند؛ سرسری می‌گذرد و تأیید می‌کند.
- توضیح کوتاه: چه عوض شد، چرا، چطور تست کردم، چه چیزی را تست نکردم.

## وقتی موافق نیستید

از سلیقه به شواهد بروید: تست شکست‌خورده، اندازه‌گیری، راهنمای سبک خود پروژه. اگر باز سلیقه بود، نویسنده تصمیم می‌گیرد و reviewer `nit:` می‌نویسد. اگر طراحی بود، حضوری یا تماسی صحبت کنید و نتیجه را در PR بنویسید.

## مفاهیمی که اجرا نکردم

فایل {{< term "codeowners" "CODEOWNERS" >}} از صاحبان یک مسیر review می‌خواهد و {{< term "branch-protection" "branch protection" >}} می‌تواند پیش از merge تأیید و CI سبز را اجباری کند. هر دو روی پلتفرم میزبان تنظیم می‌شوند؛ اینجا هیچ‌کدام را راه نینداختم.

## چند نکته‌ی مهم

- سبک کد را دستی review نکنید؛ خودکارش کنید.
- اول تست‌ها را بخوانید: اگر روی باگ شکست نمی‌خورند، کد زیرشان review نشده است.
- review را در نشست‌های کوتاه انجام دهید؛ **به تجربه‌ی من** توجه بعد از حدود یک ساعت افت می‌کند، اندازه‌گیری نیست.
- وقتی چیزی مانع نیست، با کامنت تأیید کنید.

## تمرین

آخرین PR merge‌شده‌ی خودتان را بردارید. `gofmt -l`، `go vet`، `go test -race` و staticcheck را روی آن اجرا کنید و برای چیزی که هیچ‌کدام نگفتند یک کامنت what / why / suggestion بنویسید.

## قدم بعدی

پست بعدی «طراحی API: نسخه‌بندی و pagination» است.
