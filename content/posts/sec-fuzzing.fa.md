+++
date = '2027-05-27T10:00:00+03:30'
draft = false
title = 'fuzzing برای پیدا کردن باگ امنیتی'
description = 'fuzzing در Go: سه باگ عمدی parser (محدوده، سرریز int32، حلقه‌ی بی‌پایان) را با go test -fuzz پیدا می‌کنیم، ورودی‌ها را دوباره اجرا و باگ‌ها را رفع می‌کنیم.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "fuzzing", "go", "testing", "parser"]
cover = { image = "/images/covers/sec-fuzzing.fa.png", alt = "fuzzing برای پیدا کردن باگ امنیتی", hiddenInSingle = true }
+++

مقاله‌ی قبلی، [امنیت حافظه: C در برابر Rust](/fa/posts/sec-memory-safety-c-vs-rust/)، نشان داد یک اندیس بد چه می‌کند. امروز می‌گذارم ماشین دنبال چنین ورودی‌های بدی بگردد. parser بایت‌هایی را می‌خواند که دیگری کنترل می‌کند، پس جایی است که یک بررسی جاافتاده به {{< term "denial-of-service" "حمله‌ی انکار سرویس" >}} یا بدتر تبدیل می‌شود. {{< term "fuzzing" "fuzzing" >}} ورودی‌های جهش‌یافته می‌دهد تا چیزی بشکند. مکمل [تست مبتنی بر ویژگی](/fa/posts/eng-property-based-testing/) است.

> فقط دفاعی. parser ۶۰ خطی خودم را، در تست خودم، با Go 1.26 fuzz کردم و به چیز دیگری دست نزدم. سه باگ عمدی‌اند. دمو یک مثال محلی است.

## parser

قالب: `TLV1` و بعد رکوردهایی با نوع (۱ بایت)، طول (۲ بایت) و مقدار. نوع ۱ بایت خام است، نوع ۲ «تکرار» (تعداد، اندازه، بایت پر‌کننده) و نوع ۳ متن با escape با بک‌اسلش. هدف fuzz کوچک است:

```go
func FuzzParse(f *testing.F) {
	f.Add([]byte("TLV1\x01\x00\x03abc"))
	f.Add([]byte("TLV1\x02\x00\x06\x00\x00\x00\x03\x02x"))
	f.Add([]byte("TLV1\x03\x00\x04a\\nb"))
	f.Fuzz(func(t *testing.T, b []byte) { Parse(b) })
}
```

فراخوانی‌های `f.Add` همان {{< term "seed-corpus" "corpus اولیه" >}} هستند. نمونه‌های واقعی بهترین seed را می‌سازند. این fuzzer {{< term "coverage-guided-fuzzing" "هدایت‌شده با پوشش" >}} است: ورودی‌ای که به کد تازه برسد نگه داشته و بیشتر جهش داده می‌شود. شمارنده‌ی `new interesting` همین را نشان می‌دهد.

## باگ ۱: اعتماد به طول

```
$ go test -fuzz=FuzzParse -fuzztime=200000x
fuzz: elapsed: 0s, execs: 251 (2132/sec), new interesting: 1 (total: 4)
--- FAIL: FuzzParse (0.12s)
  panic: runtime error: slice bounds out of range [:12343] with capacity 16
  Failing input written to testdata/fuzz/FuzzParse/a3c431880a157b71
```

حدود ۲۵۰ اجرا طول کشید. فایل ورودی کمینه‌شده را دارد: `[]byte("TLV1\x0200")`. بایت‌های طول همان دو نویسه‌ی `00` هستند، یعنی ۱۲۳۳۶، خیلی بیشتر از انتهای داده. حالا `go test` ساده این فایل را دوباره اجرا می‌کند و تا رفع باگ شکست می‌خورد:

```go
if n > len(b)-pos-3 { return nil, ErrFormat }
```

ورودی ذخیره‌شده در `testdata/fuzz` یک تست {{< term "regression" "رگرسیون" >}} دائمی می‌ماند؛ آن را commit کنید.

## باگ ۲: محاسبه با int32

اجرای بعدی، همان فرمان:

```
--- FAIL: FuzzParse (0.12s)
  panic: runtime error: makeslice: len out of range
  Failing input written to testdata/fuzz/FuzzParse/1461c70ced3bd442
[]byte("TLV1\x02\x00\x06A00020")
```

اینجا count برابر `0x41303030` و size برابر `'2'` (یعنی ۵۰) است. کد من `int32(count) * int32(size)` حساب می‌کرد که منفی می‌شود، از بررسی `> maxTotal` رد می‌شود و `make` را از کار می‌اندازد. این {{< term "integer-overflow" "سرریز عدد صحیح" >}} در حساب طول است. اگر به عدد مثبت کوچک می‌پیچید، بافر فقط کوتاه می‌شد. اگر بررسی اصلاً نبود، یک فیلد ۴ بایتی می‌توانست گیگابایت‌ها بخواهد. راه‌حل: حساب با `uint64` و مقایسه با سقف:

```go
total := uint64(count) * uint64(val[4])
if total > maxTotal { return nil, ErrFormat }
```

## باگ ۳: حلقه‌ی بی‌پایان

```
fuzz: elapsed: 12s, execs: 154326 (0/sec), new interesting: 15 (total: 25)
--- FAIL: FuzzParse (12.09s)
  fuzzing process hung or terminated unexpectedly: exit status 2
```

شمارنده‌ی اجرا نزدیک ۱۵۴۳۰۰ ایستاد و Go بعد از حدود ده ثانیه worker را کشت. یک بک‌اسلش در انتها باعث می‌شد `unescape` برای همیشه بچرخد، چون اندیس جلو نمی‌رفت. ورودی ذخیره‌شده کمینه نشد، چون کمینه‌کردن hang کند است. `go test` ساده هم گیر می‌کند، پس هنگام بازتولید از `-timeout 5s` استفاده کنید: خروجی `panic: test timed out after 5s` بود. راه‌حل: همیشه `i += 2`.

## بعد از رفع باگ‌ها

```
$ go test -v          # سه فایل رگرسیون به‌علاوه‌ی seedها
--- PASS: FuzzParse/1461c70ced3bd442
--- PASS: FuzzParse/a3c431880a157b71
--- PASS: FuzzParse/da26de22b41b4c2d
$ go test -fuzz=FuzzParse -fuzztime=2000000x
fuzz: elapsed: 13s, execs: 2000000 (55021/sec), new interesting: 9 (total: 36)
ok
```

دو میلیون اجرا و هیچ crash. این **اثبات درستی** نیست؛ فقط یعنی این جست‌وجو چیزی پیدا نکرد. تعداد اجرا را می‌نویسم نه زمان، چون ماشینم مشغول بود.

## ویژگی‌ها و تفاوت‌ها

fuzzer به یک معیار نیاز دارد. panic معیار رایگان است. معیار بهتر یک ویژگی است. `FuzzRoundTrip` بررسی می‌کند که `Parse(Encode(x))` برای رکورد نوع ۳ برابر `x` باشد. ۵۰۰۰۰۰ اجرا گذشت و باگ منطقی پیدا نکردم. {{< term "differential-testing" "fuzzing تفاضلی" >}} را اجرا نکردم (مقایسه‌ی parser شما با پیاده‌سازی دیگر، مثلاً زیرمجموعه‌ای از JSON با `encoding/json`)، ولی شکلش همین است.

## در پروژه‌های واقعی

- CI: بودجه‌ی کوتاه روی pull request (`-fuzztime=30s`) و بودجه‌ی بلند شبانه؛ [طراحی pipeline برای CI/CD](/fa/posts/eng-ci-cd-pipeline-design/) را ببینید.
- C و C++: libFuzzer، AFL++ و OSS-Fuzz در مقیاس بزرگ؛ Rust ابزار `cargo-fuzz` دارد. فقط نام می‌برم و اجرایشان نکردم.
- fuzzer را با sanitizer مثل {{< term "addresssanitizer" "AddressSanitizer" >}} در C جفت کنید. Go و Rust {{< term "memory-safety" "امنیت حافظه" >}} می‌دهند ولی باز هم panic و hang دارند.
- فرهنگ‌لغت کلمات کلیدی و fuzzing ساختارآگاه برای قالب‌های دارای checksum یا گرامر کمک می‌کند.

## چند نکته‌ی مهم

- فایل‌های `testdata/fuzz` را commit کنید.
- seed از نمونه‌ی واقعی بهتر از seed خالی است.
- parserهای خودتان را fuzz کنید، نه سرویس دیگران را.
- هر تخصیص وابسته به ورودی را سقف بگذارید.
- نبودن crash اثبات نیست.

## تمرین

رکورد نوع ۴ اضافه کنید که طول ۴ بایتی‌اش مستقیم در `make([]byte, n)` می‌رود. بگذارید fuzzer مشکل را پیدا کند، بعد سقف و یک تست رگرسیون اضافه کنید.

## قدم بعدی

مقاله‌ی بعدی «لاگ، audit و واکنش به حادثه» است.
