+++
date = '2027-05-13T10:00:00+03:30'
draft = false
title = 'ابزار خط فرمان و اسکریپت‌نویسی با Python'
description = 'ابزار خط فرمان با Python: زیردستور argparse، کد خروج، pipe و BrokenPipeError، subprocess امن، Ctrl-C، Typer، اسکریپت PEP 723 و تست.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "cli", "argparse", "typer", "scripts"]
cover = { image = "/images/covers/py-cli-scripts.fa.png", alt = "ابزار خط فرمان و اسکریپت‌نویسی با Python", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/py-packaging-publishing/) پروژه را بسته‌بندی کردیم و با entry point از نوع console-script آشنا شدیم. این‌جا خودِ برنامه‌ای را می‌نویسیم که پشت چنین entry point ای است. نسخه‌ی Go را در [ابزار خط فرمان در Go](/fa/posts/go-cli-tool/) ساخته بودم و بخش مربوط به پروسه به [پروسه‌ها و سیگنال‌ها](/fa/posts/linux-processes-signals/) تکیه دارد.

> Python 3.14.0 و uv 0.10.9 در یک پوشه‌ی موقت. Typer 0.20.0 (با Click 8.5.0) در یک venv بود که بعداً پاکش کردم. بار این ماشین بالا بود، پس زمان‌سنجی ندارم. دمو یک نمونه‌ی محلی است.

## argparse: زیردستور، نوع و choices

{{< term "argparse" "argparse" >}} در کتابخانه‌ی استاندارد است. `wc.py` من زیردستور `count` دارد با مسیر فایل یا `-`، یک گزینه‌ی `int`، یک گزینه‌ی `choices` و یک گروه دوبه‌دو ناسازگار (کد کامل در دموی محلی است؛ خطوط اصلی):

```python
sub = p.add_subparsers(dest="cmd", required=True)
c = sub.add_parser("count", help="count lines and words")
c.add_argument("file", nargs="?", default="-")
c.add_argument("--limit", type=int, default=0)
g = c.add_mutually_exclusive_group()
g.add_argument("--lines", action="store_true")
g.add_argument("--words", action="store_true")
c.add_argument("--format", choices=["text", "json"], default="text")
```

خروجی `python3 wc.py count --help`:

```text
usage: wc.py count [-h] [--limit LIMIT] [--lines | --words] [--format {text,json}]
                   [file]
```

استفاده‌ی غلط پیام را در stderr می‌نویسد و {{< term "exit-status" "کد خروج" >}} ۲ می‌دهد:

```text
$ python3 wc.py count --lines --words t.txt
wc.py count: error: argument --words: not allowed with argument --lines
rc=2
$ python3 wc.py count --format xml t.txt
wc.py count: error: argument --format: invalid choice: 'xml' (choose from text, json)
rc=2
```

قرارداد من: ۰ موفقیت، ۱ خطای زمان اجرا (نبودن `nope.txt` کد ۱ داد)، ۲ خطای استفاده. `main()` یک عدد برمی‌گرداند و `sys.exit(main())` آن را منتقل می‌کند.

## تنظیمات، متغیر محیطی و logging

اولویت در اسکریپت من: {{< term "environment-variable" "متغیر محیطی" >}} `WC_FORMAT`، بعد `--config file.toml` که با `tomllib` کتابخانه‌ی استاندارد خوانده می‌شود، بعد مقدار پیش‌فرض گزینه. با `format = "json"` در فایل خروجی `{"lines": 2, "words": 5}` شد و `WC_FORMAT=text` دوباره آن را به `2 5` برگرداند. `logging.basicConfig(stream=sys.stderr)` همراه `-v` برای سطح DEBUG، پیام‌های تشخیصی را از stdout دور نگه می‌دارد؛ stdout باید برای pipe تمیز بماند. اگر نوع آرگومان `pathlib.Path` باشد، مستقیم `read_text()` دارید.

## pipe و SIGPIPE

`emit.py` صد هزار عدد چاپ می‌کند. خروجی `python3 emit.py | head -2`:

```text
0
1
Traceback (most recent call last):
  ...
    print(i)
BrokenPipeError: [Errno 32] Broken pipe
status=120 0
```

`head` لوله را بست و Python به‌جای مردن بی‌صدا، {{< term "sigpipe" "SIGPIPE" >}} را به استثنا تبدیل کرد (تا جایی که می‌دانم Python این سیگنال را در شروع نادیده می‌گیرد). کد ۱۲۰ از شکست flush در زمان خروج مفسر می‌آید. راه‌حل، الگوی مستندات Python:

```python
except BrokenPipeError:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    sys.exit(141)
```

حالا traceback نیست و کد ۱۴۱ است، همان عددی که شل برای مرگ با SIGPIPE نشان می‌دهد.

## subprocess بدون شل

نام فایل `my file.txt`:

```text
shell=True  : 1 'wc: my: open: No such file or directory\nwc: file.txt: open: No such file or directory'
list args   : 0 1
shlex.quote : 'my file.txt'
check=True  : 1 'ls: missing.txt: No such file or directory'
```

شل نام را دو تکه کرد. با لیست نیازی به quote نیست و `check=True` در کد غیرصفر `CalledProcessError` می‌دهد. اگر ناچار به ساختن رشته‌ی شل هستید، هر تکه را با `shlex.quote` بپوشانید، ولی لیست بهتر است.

## Ctrl-C

از یک اسکریپت والد SIGINT فرستادم. با `except KeyboardInterrupt: sys.exit(130)` کد بازگشت فرزند ۱۳۰ بود. بدون handler، Python traceback چاپ کرد و `returncode` برابر `-2` بود: پروسه با خود سیگنال می‌میرد که شل آن را ۱۳۰ (یعنی ۱۲۸ + ۲) گزارش می‌کند.

## Typer

همان CLI با Typer، حدود ۱۵ خط منطق، با type hint به‌جای `add_argument`:

```python
@app.command()
def count(file: Optional[Path] = None, limit: int = 0,
          fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.text): ...
```

`--format xml` یک خطای قاب‌دار چاپ کرد، `Invalid value for '--format': 'xml' is not one of 'text', 'json'.`، با کد ۲. `--limit abc` پیام «not a valid integer» داد. Typer گزینه‌ی `--install-completion` را هم به help اضافه کرد. گروه دوبه‌دو ناسازگار را دوباره نساختم.

| | argparse | Click | Typer |
|---|---|---|---|
| نصب | stdlib | وابستگی | وابستگی (روی Click) |
| سبک | فراخوانی صریح | decorator | type hint |
| مناسب | اسکریپت بدون وابستگی | CLI بزرگ‌تر | CLI تایپ‌دار سریع |

جدول نظر خودم است؛ فقط argparse و Typer را اجرا کردم.

## اسکریپت تک‌فایلی و تست

با {{< term "inline-script-metadata" "inline script metadata" >}} اسکریپت وابستگی‌اش را خودش اعلام می‌کند:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["humanize==4.13.0"]
# ///
```

بعد از `chmod +x`، دستور `./size.py 1500000` بسته‌ی `humanize` را نصب کرد و `1.5 MB` چاپ کرد؛ اجرای دوم بدون نصب همان را چاپ کرد. shebang روی macOS کار کرد.

برای تست، `main(argv)` را با `capsys` در pytest صدا بزنید ([تست با pytest](/fa/posts/py-testing-pytest/)) و برای کد خروج واقعی از `subprocess.run` استفاده کنید. سه تست من پاس شد، به‌علاوه‌ی یک تست با `CliRunner` در Typer.

## در مقایسه با Go

در Go یک CLI به یک باینری تبدیل می‌شود که مفسر نمی‌خواهد. بسته‌ی `flag` هم در کتابخانه‌ی استاندارد Go هست. ابزار Python روی ماشین مقصد به مفسر و وابستگی‌هایش نیاز دارد، مگر مثل مقاله‌ی قبل بسته‌بندی شود.

## چند نکته‌ی مهم

- از `main()` عدد برگردانید و خطاها را به stderr بنویسید.
- با متن زیر کنترل کاربر هرگز `shell=True` نزنید.
- اگر ابزارتان زیاد چاپ می‌کند، `BrokenPipeError` را مدیریت کنید.
- نسخه‌ها را در metadata اسکریپت pin کنید.

## تمرین

کاری کنید `--limit` مقدار پیش‌فرضش را از فایل `--config` بخواند و با `capsys` تستش کنید.

## قدم بعدی

مقاله‌ی بعد «پردازش داده‌ی کوچک با csv و sqlite3» است.
