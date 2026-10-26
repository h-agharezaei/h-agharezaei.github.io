+++
date = '2026-12-10T10:00:00+03:30'
draft = false
title = 'ساخت ابزار خط فرمان با Go'
description = 'ساخت wordstat، یک ابزار خط فرمان واقعی با Go: پکیج flag، زیردستور، خواندن stdin، exit code، تابع run قابل‌تست، نسخه‌گذاری و cross-compile.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "cli", "flag", "build"]
cover = { image = "/images/covers/go-cli-tool.fa.png", alt = "ساخت ابزار خط فرمان با Go", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/go-file-io-json/) با `io.Reader` و `io.Writer` فایل خواندیم و JSON نوشتیم. حالا همان را در چیزی به کار می‌بریم که واقعاً می‌شود نصبش کرد: یک ابزار خط فرمان. ابزاری به نام `wordstat` می‌سازیم که یک فایل (یا stdin) را می‌خواند و تعداد خط، کلمه و بایت و N کلمه‌ی پرتکرار را به صورت متن یا JSON چاپ می‌کند. در مسیر با پکیج `flag`، زیردستورها، exit code، ساختاری که تست‌کردنش آسان است و ساختن یک باینری برای هر پلتفرم آشنا می‌شویم.

> همه‌چیز را با Go 1.26 روی یک مک arm64 اجرا کرده‌ام و خروجی‌ها از اجراهای واقعی کپی شده‌اند.

## os.Args در برابر flag

`os.Args` فقط یک `[]string` است و عنصر صفرمش نام برنامه است. می‌توانید خودتان پارس کنید، اما فلگ، مقدار پیش‌فرض و `-h` در پکیج **flag** از قبل حل شده‌اند. آرگومان‌های موقعیتی (positional) هم با `fs.Arg(0)` و `fs.NArg()` در دسترس‌اند. شکل `wordstat` این است:

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

به جای `FlagSet` سراسری، یکی از خودم ساخته‌ام تا تابع قابل‌تست بماند. `ContinueOnError` باعث می‌شود `Parse` به جای خروج از برنامه خطا برگرداند و `fs.Usage` متن راهنمای پیش‌فرض را عوض می‌کند. فلگ‌ها باید قبل از آرگومان‌های موقعیتی بیایند؛ پارس در اولین آرگومانِ غیرفلگ متوقف می‌شود.

## خواندن فایل یا stdin

تابع شمارنده یک `io.Reader` می‌گیرد، دقیقاً همان ایده‌ی مقاله‌ی قبل. اینکه این reader چیست را فراخواننده تعیین می‌کند:

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

خودِ `count` با `bufio.Reader` خط‌به‌خط می‌خواند، خط و کلمه و بایت را می‌شمارد و یک map فراوانی پر می‌کند. چون کدی ساده از مقاله‌های قبل است اینجا تکرارش نمی‌کنم. با این فایل:

```text
$ cat sample.txt
Go is fun. Go is small.
Small tools are fun to build.
The go tool builds one binary.
```

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

همین ابزار در pipe هم کار می‌کند:

```text
$ printf 'a b a\nc a b\n' | ./wordstat -top 2
lines=2 words=6 bytes=12
    3  a
    2  b
```

## خطا، stderr و exit code

نتیجه به stdout می‌رود و پیام خطا به stderr؛ پس `wordstat file > out.txt` خطا را داخل فایل شما نمی‌ریزد. exit code به اسکریپت‌ها می‌گوید چه شد. قرارداد رایج: ۰ موفقیت، ۱ خطای زمان اجرا و ۲ اشتباه در نحوه‌ی استفاده:

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

## os.Exit کارهای defer را اجرا نمی‌کند

دلیل اینکه `main` باید کوچک باشد همین است. `os.Exit` فرایند را بلافاصله تمام می‌کند و `defer`های معلق هرگز اجرا نمی‌شوند. یک برنامه‌ی کوچک نشانش می‌دهد:

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

(آن را از باینری ساخته‌شده اجرا کنید؛ `go run` exit code واقعی را پنهان می‌کند و خودش `exit status 3` چاپ می‌کند.) راه‌حل همان ساختاری است که بالا استفاده کردیم: همه‌ی منطق در `run` است که یک int برمی‌گرداند و `main` یک خط است:

```go
func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int { /* ... */ }

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
```

چون `run` عادی برمی‌گردد، `defer f.Close()` آن پیش از اینکه `os.Exit` کد را ببیند اجرا می‌شود.

## تست کردن run

چون `run` ورودی و خروجی را پارامتر می‌گیرد، تست نه فایل می‌خواهد نه فرایند واقعی:

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
ok  	example.com/wordstat	0.263s
```

## زیردستورها

برای ابزاری مثل `git` می‌خواهید `tool hello -name X` کار کند. به هر زیردستور یک `FlagSet` جدا بدهید و روی `os.Args[1]` switch کنید:

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

## یک باینری، هر پلتفرم

`go build` یک باینری مستقل می‌سازد. با `-ldflags "-X main.version=..."` مقدار یک متغیر رشته‌ای در زمان link تعیین می‌شود؛ روش معمول نسخه‌گذاری. متغیر باید در سطح پکیج و از جنس `string` باشد (اینجا `var version = "dev"`):

```text
$ go build -ldflags "-X main.version=1.2.0" -o wordstat . && ./wordstat -version
wordstat 1.2.0
$ go build -o wordstat . && ./wordstat -version
wordstat dev
```

cross-compile فقط دو متغیر محیطی می‌خواهد:

```text
$ GOOS=linux GOARCH=amd64 go build -o wordstat-linux .
$ file wordstat-linux wordstat
wordstat-linux: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, ...
wordstat:       Mach-O 64-bit executable arm64
```

باینری لینوکس را روی این مک نتوانستم اجرا کنم؛ فقط ساختمش و بررسی‌اش کردم. باینری بومی حدود ۳٫۰ مگابایت بود و با `-ldflags "-s -w"` (حذف symbolها) حدود ۲٫۰ مگابایت شد.

## چند نکته که باید حواستان باشد

- `flag` در اولین آرگومان موقعیتی می‌ایستد؛ پس در `wordstat file -json` مقدار `-json` نام فایل حساب می‌شود.
- `os.Exit` را عمیق داخل تابع‌های کمکی صدا نزنید؛ خطا را برگردانید و exit code را فقط یک جا تعیین کنید.
- خطا را به stderr و داده را به stdout بنویسید تا pipe و redirect درست کار کنند.
- `-X` فقط روی متغیر `string` در پکیج مشخص‌شده کار می‌کند (بدون مقدار اولیه یا با رشته‌ی ثابت)؛ اگر مسیر را اشتباه بنویسید بی‌سروصدا هیچ اتفاقی نمی‌افتد.
- `go run` exit code دقیق را عبور نمی‌دهد؛ exit code را با باینری ساخته‌شده تست کنید.

## تمرین

۱. فلگ `-min` اضافه کنید که کلمه‌های کوتاه‌تر از N حرف را نادیده بگیرد و تست را برای آن گسترش دهید.
۲. `wordstat` را طوری تغییر دهید که چند فایل بگیرد و برای هر کدام یک خلاصه چاپ کند. کدام بخش `run` باید عوض شود؟
۳. برای `windows/amd64` بسازید و نتیجه را با `file` بررسی کنید.

## قدم بعدی

در مقاله‌ی بعد همه‌ی این‌ها را در پروژه‌ی کوچک پایانی سری به کار می‌بریم: یک URL shortener با Go.
