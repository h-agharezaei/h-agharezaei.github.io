+++
date = '2026-12-10T10:00:00+03:30'
draft = false
title = 'ساخت ابزار خط فرمان با Go'
description = 'ساخت wordstat، یک ابزار خط فرمان واقعی با Go: پکیج flag، زیردستور، خواندن stdin، exit code، تابع run قابل‌تست، نسخه‌گذاری و cross-compile.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "cli", "flag", "build"]
cover = { image = "/images/covers/go-cli-tool.fa.png", alt = "ساخت ابزار خط فرمان با Go", hiddenInSingle = true }
+++

یک چیز کوچک و غافلگیرکننده درباره‌ی برنامه‌های Go: اگر در `main` بنویسید `defer f.Close()` و بعدتر `os.Exit(1)` را صدا بزنید، آن فراخوانیِ deferشده هرگز اجرا نمی‌شود. `os.Exit` پروسه را همان لحظه تمام می‌کند. همین یک نکته تعیین می‌کند ابزار خط فرمانِ درست در Go چطور ساخته شود، و آخرش با یک برنامه‌ی ریز نشانش می‌دهم.

ولی اول بیایید چیزی بسازیم. بعد از [کار با فایل، io.Reader/Writer و JSON در Go](/fa/posts/go-file-io-json/) تکه‌های لازم برای یک ابزار واقعی را داریم. `wordstat` را می‌نویسیم: برنامه‌ای که یک فایل متنی (یا ورودی استاندارد) را می‌خواند، تعداد خط‌ها، کلمه‌ها و بایت‌ها را چاپ می‌کند و پرتکرارترین کلمه‌ها را فهرست می‌کند. نتیجه را می‌تواند به شکل متن ساده یا JSON بدهد. در مسیر با پکیج `flag` برای گزینه‌ها، زیردستورها، {{< term "exit-status" "کد خروج" >}}، ساختاری که تستش آسان است و ساخت یک باینری برای هر سیستم‌عامل آشنا می‌شویم.

> همه‌چیز را با Go 1.27 روی یک مک arm64 اجرا کرده‌ام. همه‌ی خروجی‌های زیر از اجرای واقعی کپی شده‌اند. کد یک مثال محلی است، نه مخزن منتشرشده.

## آرگومان‌ها و پکیج flag

وقتی `wordstat -top 5 notes.txt` را اجرا می‌کنید، کلمه‌های بعد از نام برنامه در Go به شکل `os.Args` می‌رسند، یک `[]string` ساده که عنصر صفرش نام برنامه است. می‌توانید خودتان تکه‌تکه‌اش کنید و تشخیص بدهید کدام گزینه است و کدام نام فایل. ولی گزینه، مقدار پیش‌فرض و متن راهنمای `-h` مسئله‌ی حل‌شده‌ای است و پکیج `flag` آن را حل کرده.

ایده این است: هر گزینه را با نام، مقدار پیش‌فرض و متن راهنما اعلام می‌کنید و `flag` خط فرمان را برایتان تجزیه می‌کند. هرچه بعد از گزینه‌ها بماند (اینجا نام فایل) **آرگومان موقعیتی** (positional) است که با `fs.Arg(0)` و `fs.NArg()` می‌خوانیدش. شروع `wordstat` این‌طور است:

```go
fs := flag.NewFlagSet("wordstat", flag.ContinueOnError)
fs.SetOutput(stderr)
top := fs.Int("top", 3, "number of top words to show")
asJSON := fs.Bool("json", false, "print JSON instead of text")
showVersion := fs.Bool("version", false, "print version and exit")
fs.Usage = func() {
	fmt.Fprintln(stderr, "usage: wordstat [flags] [file]")
	fmt.Fprintln(stderr, "reads stdin when no file is given")
	fs.PrintDefaults()
}
if err := fs.Parse(args); err != nil {
	if err == flag.ErrHelp {
		return 0
	}
	return 2
}
```

هر فراخوانی مثل `fs.Int("top", 3, "...")` یک گزینه ثبت می‌کند و یک پوینتر به مقدارش برمی‌گرداند (برای همین بعداً می‌نویسید `*top`). من به‌جای `FlagSet` سراسری که `flag.Int` به کار می‌برد، `FlagSet` خودم را ساخته‌ام تا تابع قابل‌تست باشد و به state سراسری دست نزند. `ContinueOnError` باعث می‌شود `Parse` به‌جای بستن کل برنامه خطا برگرداند و `fs.Usage` متن راهنمای پیش‌فرض را عوض می‌کند. یک قاعده را یادتان نگه دارید: گزینه‌ها باید قبل از آرگومان‌های موقعیتی بیایند، چون تجزیه از اولین آرگومانی که گزینه نیست متوقف می‌شود.

## خواندن از فایل یا stdin

خیلی از ابزارهای یونیکس اگر فایلی بدهید از آن می‌خوانند و اگر ندهید از **ورودی استاندارد** (stdin). به همین دلیل در یک {{< term "pipe" "pipe" >}} هم کار می‌کنند، مثل `cat x | tool`. ما هم همین را تقریباً بدون کد اضافه داریم، چون تابع شمارش یک `io.Reader` می‌گیرد، یعنی همان ایده‌ی نوشته‌ی قبل. اینکه این reader چیست را فراخواننده تعیین می‌کند:

```go
in := stdin
if fs.NArg() > 0 {
	f, err := os.Open(fs.Arg(0))
	if err != nil {
		fmt.Fprintln(stderr, "wordstat:", err)
		return 1
	}
	defer f.Close()
	in = f
}
st, err := count(in, *top)
```

اگر نام فایل داده شده باشد، بازش می‌کنیم و به کار می‌بریم؛ وگرنه همان `stdin` می‌ماند. خودِ `count` با `bufio.Reader` خط‌به‌خط می‌خواند، خط‌ها، کلمه‌ها و بایت‌ها را می‌شمارد و یک map از فراوانی کلمه‌ها پر می‌کند. تکرارش نمی‌کنم، چون کد ساده‌ای از نوشته‌های قبل است. این فایل سه‌خطی را به کار می‌بریم:

```text
$ cat sample.txt
Go is fun. Go is small.
Small tools are fun to build.
The go tool builds one binary.
```

حالا دو اجرا. اولی گزارش متنی پیش‌فرض را چاپ می‌کند. دومی فقط پرتکرارترین کلمه را به شکل JSON می‌خواهد و `head -3` خروجی را بعد از سه خط می‌برد:

```text
$ ./wordstat sample.txt
lines=3 words=18 bytes=85
    3  go
    2  fun
    2  is
$ ./wordstat -top 1 -json < sample.txt | head -3
{
  "lines": 3,
  "words": 18,
  "bytes": 85,
```

خط اول می‌گوید ۳ خط، ۱۸ کلمه و ۸۵ بایت. زیرش فهرست سه کلمه‌ی برتر است: `go` سه بار آمده (کد کلمه‌ها را کوچک‌حرف می‌کند و نقطه‌گذاری را برمی‌دارد، پس «Go» و «go.» با هم حساب می‌شوند)، بعد `fun` و `is` که هرکدام دو بار آمده‌اند. کلمه‌های هم‌تعداد به ترتیب الفبا می‌آیند و برای همین `fun` قبل از `is` است. در اجرای دوم `< sample.txt` فایل را به stdin می‌دهد، پس اصلاً آرگومان نام فایل نداریم.

همین ابزار آخر یک pipe هم کار می‌کند:

```text
$ printf 'a b a\nc a b\n' | ./wordstat -top 2
lines=2 words=6 bytes=12
    3  a
    2  b
```

## خطاها، stderr و کد خروج

برنامه دو جریان خروجی دارد. **stdout** برای نتیجه است و **stderr** برای پیام خطا. فایده‌ی جدا نگه داشتنشان این است که `wordstat file > out.txt` فقط stdout را تغییر مسیر می‌دهد و پیام خطا داخل فایل شما نمی‌رود.

کانال سومی هم هست: **کد خروج** (exit code)، عددی که برنامه هنگام پایان برمی‌گرداند. اسکریپت‌ها و CI با آن می‌فهمند چه شده. طبق قرارداد ۰ یعنی موفقیت، ۱ یعنی شکست در زمان اجرا و ۲ یعنی خطای استفاده (ابزار را غلط صدا زده‌اید). اینجا یک فایل ناموجود، همان با دور ریختن stderr و یک مقدار بد برای فلگ را می‌بینید:

```text
$ ./wordstat missing.txt; echo "exit=$?"
wordstat: open missing.txt: no such file or directory
exit=1
$ ./wordstat missing.txt 2>/dev/null; echo "exit=$?"
exit=1
$ ./wordstat -top abc sample.txt; echo "exit=$?"
invalid value "abc" for flag -top: parse error
usage: wordstat [flags] [file]
reads stdin when no file is given
  -json
    	print JSON instead of text
  -top int
    	number of top words to show (default 3)
  -version
    	print version and exit
exit=2
```

`echo "exit=$?"` کد خروج دستور قبلی را چاپ می‌کند. در حالت اول پیام به stderr می‌رود و کد خروج ۱ است. در حالت دوم `2>/dev/null` stderr را دور می‌ریزد؛ پس چیزی چاپ نمی‌شود ولی کد خروج هنوز ۱ است. در حالت سوم تجزیه‌گر فلگ از `abc` شکایت می‌کند، تابع `Usage` ما راهنما را چاپ می‌کند و کد ۲ است، چون مشکل در طرز صدا زدن ابزار است.

## os.Exit دستورهای defer را رد می‌کند

حالا غافلگیری ابتدای نوشته. `os.Exit` پروسه را فوراً تمام می‌کند؛ پس فراخوانی‌های deferشده اجرا نمی‌شوند. یک برنامه‌ی کوچک نشان می‌دهد. یک چاپ را defer می‌کند و فقط اگر بخواهید زود خارج می‌شود:

```go
func main() {
	defer fmt.Println("deferred: cleanup")
	if len(os.Args) > 1 && os.Args[1] == "exit" {
		os.Exit(3)
	}
	fmt.Println("main returns normally")
}
```

```text
$ ./exitdefer
main returns normally
deferred: cleanup
$ ./exitdefer exit; echo "exit=$?"
exit=3
```

در اجرای عادی `main` برمی‌گردد و خط deferشده آخر چاپ می‌شود. در اجرای دوم `os.Exit(3)` زودتر اتفاق می‌افتد و «deferred: cleanup» هرگز نمی‌آید. در یک ابزار واقعی آن فراخوانی ممکن است فایلی را ببندد، بافری را flush کند یا فایل موقتی را پاک کند؛ پس رد شدنش یک باگ واقعی است. (این را با باینری ساخته‌شده اجرا کنید. `go run` کد خروج واقعی را پنهان می‌کند و پیام خودش یعنی `exit status 3` را چاپ می‌کند.)

راه‌حل این است که `os.Exit` را فقط در یک جا نگه دارید و آن جا را آن‌قدر کوچک کنید که چیزی برای defer نداشته باشد. همه‌ی منطق می‌رود در تابعی به نام `run` که کد خروج را به شکل `int` برمی‌گرداند و `main` یک خط می‌شود:

```go
func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int { /* ... */ }

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
```

چون `run` عادی برمی‌گردد، `defer f.Close()` آن قبل از اینکه `os.Exit` کد را ببیند اجرا می‌شود.

## تست کردن run

این ساختار فایده‌ی دومی هم دارد. `run` آرگومان‌ها، ورودی و خروجی را به‌جای خواندن از متغیرهای سراسری، پارامتر می‌گیرد؛ پس تست نه فایل می‌خواهد و نه پروسه‌ی واقعی. یک string reader به‌جای stdin می‌دهیم و دو بافر به‌جای stdout و stderr:

```go
func TestRunStdin(t *testing.T) {
	var out, errb bytes.Buffer
	in := strings.NewReader("go is fun\nGo is small\n")
	code := run([]string{"-top", "2"}, in, &out, &errb)
	if code != 0 {
		t.Fatalf("exit code = %d, stderr = %q", code, errb.String())
	}
	want := "lines=2 words=6 bytes=22\n    2  go\n    2  is\n"
	if out.String() != want {
		t.Errorf("stdout = %q, want %q", out.String(), want)
	}
}
```

```text
$ go test -count=1 -v .
=== RUN   TestRunStdin
--- PASS: TestRunStdin (0.00s)
=== RUN   TestRunMissingFile
--- PASS: TestRunMissingFile (0.00s)
PASS
ok  	example.com/wordstat	0.355s
```

دو تست داریم: همین که بالا آمد و `TestRunMissingFile` که چک می‌کند فایل ناموجود کد خروج ۱ و پیام خطایی که نام فایل را دارد بدهد. هر دو قبول شدند. زمان آخر خط از اجرایی به اجرای دیگر فرق می‌کند.

## زیردستورها

ابزارهایی مثل `git` زیردستور دارند: `git commit`، `git push`. هرکدام فلگ‌های خودش را دارد. پکیج استاندارد `flag` با یک الگوی ساده از این پشتیبانی می‌کند: به هر زیردستور `FlagSet` مخصوص خودش را بدهید و با نگاه به `os.Args[1]` یکی را انتخاب کنید:

```go
switch os.Args[1] {
case "hello":
	fs := flag.NewFlagSet("hello", flag.ExitOnError)
	name := fs.String("name", "world", "who to greet")
	fs.Parse(os.Args[2:])
	fmt.Println("hello,", *name)
case "bye":
	fmt.Println("bye")
default:
	fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
	os.Exit(2)
}
```

```text
$ go run ./sub hello -name Roham
hello, Roham
$ go run ./sub hello
hello, world
```

کلمه‌ی بعد از نام برنامه شاخه را انتخاب می‌کند و بقیه‌ی آرگومان‌ها (`os.Args[2:]`) به flag set خودِ آن زیردستور می‌رسند. اینجا `ExitOnError` اشکالی ندارد، چون این مثال کوچک چیزی برای پاک‌سازی ندارد.

## یک باینری برای هر پلتفرم

`go build` یک باینری مستقل و کامل می‌سازد؛ پس نصب ابزار شما یعنی کپی یک فایل. نیاز رایج این است که نسخه روی خروجی منتشرشده درج شود. linker می‌تواند یک متغیر رشته‌ای را برایتان مقدار بدهد: `-ldflags "-X main.version=..."`. متغیر باید یک `string` در سطح پکیج باشد (اینجا `var version = "dev"`):

```text
$ go build -ldflags "-X main.version=1.2.0" -o wordstat . && ./wordstat -version
wordstat 1.2.0
$ go build -o wordstat . && ./wordstat -version
wordstat dev
```

cross-compile، یعنی ساختن برای سیستم‌عامل یا CPU دیگر، فقط دو متغیر محیطی لازم دارد:

```text
$ GOOS=linux GOARCH=amd64 go build -o wordstat-linux .
$ file wordstat-linux wordstat
wordstat-linux: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, ...
wordstat:       Mach-O 64-bit executable arm64
```

دستور `file` می‌گوید هر فایل چیست: `wordstat-linux` یک فایل اجرایی لینوکس برای x86 ۶۴ بیتی است و `wordstat` فایل اجرایی بومیِ macOS. نتوانستم باینری لینوکس را روی این مک اجرا کنم، فقط ساختم و بررسی‌اش کردم (برای `windows/amd64` هم همین کار را کردم و `file` یک فایل اجرایی ویندوز گزارش داد). با Go 1.27 باینری بومی حدود ۳٫۹ مگابایت شد و اضافه کردن `-ldflags "-s -w"` (که جدول symbol و اطلاعات دیباگ را حذف می‌کند) آن را به حدود ۲٫۶ مگابایت رساند. اندازه‌ها به نسخه‌ی Go و پلتفرم بستگی دارند.

## دام‌های flag و کد خروج

- **`flag` در اولین آرگومان موقعیتی می‌ایستد.** در `wordstat sample.txt -json` ابزار گزارش متنی ساده چاپ می‌کند: `-json` بعد از نام فایل آمده، پس به‌عنوان فلگ تجزیه نمی‌شود و `wordstat` بی‌صدا نادیده‌اش می‌گیرد. فلگ‌ها را اول بگذارید.
- **`os.Exit` را عمیق داخل تابع‌های کمکی صدا نزنید.** خطا برگردانید و کد خروج را فقط در یک جا تعیین کنید. این کار پاک‌سازیِ defer را سالم نگه می‌دارد و تابع‌های کمکی را قابل‌تست.
- **خطا به stderr، داده به stdout.** آن‌وقت pipe و تغییر مسیر همان‌طور که کاربر انتظار دارد رفتار می‌کنند.
- **`-X` به‌راحتی بی‌صدا غلط کار می‌کند.** فقط متغیرهای `string` را مقدار می‌دهد و مسیر پکیج باید دقیق باشد. غلط املایی (`main.versoin`) را امتحان کردم؛ build موفق شد و باینری همچنان `dev` چاپ کرد. طبق مستندات linker، اگر متغیر با فراخوانی تابع مقداردهی شده باشد هم اثری ندارد.
- **`go run` کد خروج دقیق را رد نمی‌کند.** کد خروج را با باینری ساخته‌شده تست کنید.

## تمرین

۱. فلگ `-min` را اضافه کنید که کلمه‌های کوتاه‌تر از N حرف را نادیده بگیرد و تست را برایش گسترش دهید.
۲. `wordstat` را طوری کنید که چند فایل بگیرد و برای هر فایل یک خلاصه چاپ کند. کدام بخش `run` باید عوض شود؟
۳. برای `windows/amd64` بسازید و نتیجه را با `file` بررسی کنید.

## قدم بعدی

«پروژه‌ی کوچک: URL shortener با Go»: فایل و JSON، تست، همزمانی و خاموشی تمیز را در یک سرویس HTTP کوچک کنار هم می‌گذارد.
