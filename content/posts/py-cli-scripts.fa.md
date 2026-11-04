+++
date = '2027-05-13T10:00:00+03:30'
draft = false
title = 'ابزار خط فرمان و اسکریپت‌نویسی با Python'
description = 'ابزار خط فرمان با Python: زیردستور argparse، کد خروج، pipe و BrokenPipeError، subprocess امن، Ctrl-C، Typer، اسکریپت PEP 723 و تست.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "cli", "argparse", "typer", "scripts"]
cover = { image = "/images/covers/py-cli-scripts.fa.png", alt = "ابزار خط فرمان و اسکریپت‌نویسی با Python", hiddenInSingle = true }
+++

`python3 emit.py | head -2` را اجرا کردم. اسکریپت ۱۰۰٬۰۰۰ عدد چاپ می‌کند و `head -2` دو خط اولش را نگه می‌دارد. `0` و `1` آمد و بعد یک traceback بلند از `BrokenPipeError`. برنامه کار اشتباهی نکرده بود، ولی ظاهرش مثل این بود که خراب شده.

همین جزئیات است که اسکریپت را از ابزار جدا می‌کند. اسکریپت وقتی کار می‌کند که همان‌طور که تصور کرده‌اید اجرایش کنید. ابزار وقتی هم درست رفتار می‌کند که کسی آن را در یک {{< term "pipe" "pipe" >}} بگذارد، آرگومان غلط بدهد، Ctrl-C بزند، یا از برنامه‌ی دیگری صدایش کند که کد خروجی‌اش را نگاه می‌کند. در این پست خودِ برنامه‌ای را می‌نویسیم که پشت entry point از نوع console-script در [پست قبل](/fa/posts/py-packaging-publishing/) قرار می‌گیرد. نسخه‌ی Go را در [ابزار خط فرمان در Go](/fa/posts/go-cli-tool/) ساخته بودم و بخش مربوط به process به [process و سیگنال](/fa/posts/linux-processes-signals/) تکیه دارد.

> همه‌چیز را دوباره با Python 3.14.0 و uv 0.10.9 در یک نسخه‌ی موقت از دمو اجرا کردم. Typer 0.20.0 (با Click 8.5.0) در یک venv یک‌بارمصرف بود که از cache آفلاین uv نصب شد و بعد پاکش کردم. ماشین شلوغ بود، پس زمانی نشان نمی‌دهم. دمو یک نمونه‌ی محلی است. متن usage به عرض ترمینال می‌شکند، پس ممکن است در ترمینال شما خطها جور دیگری بشکنند.

## argparse: پارسر کتابخانه‌ی استاندارد

ابزار خط فرمان باید متنی مثل `wc.py count --limit 5 notes.txt` را به مقدارهایی تبدیل کند که برنامه بتواند به کار ببرد، و چیزهای بی‌معنی را با پیام روشن رد کند. {{< term "argparse" "argparse" >}} این کار را می‌کند و همراه Python می‌آید.

دموی من، `wc.py`، یک شمارنده‌ی ساده‌ی کلمه است. یک زیرفرمان `count` دارد (مثل `git commit`: کلمه‌ی اول تعیین می‌کند چه کاری انجام شود)، یک آرگومان فایل که اختیاری است (`-` یا هیچ چیز یعنی از ورودی استاندارد بخوان)، یک گزینه‌ی `int`، یک گزینه که به چند `choices` محدود است و یک گروه ناسازگار (`--lines` یا `--words`، هرگز هر دو). این‌ها خط‌های کلیدی‌اند؛ کد کامل در دموی محلی است:

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

`type=int` باعث می‌شود argparse مقدار را خودش تبدیل و بررسی کند، و `choices` گزینه‌ها را محدود می‌کند. `--help` را هم مفت می‌گیرید، ساخته‌شده از همین توصیف:

```text
usage: wc.py count [-h] [--limit LIMIT] [--lines | --words]
                   [--format {text,json}]
                   [file]
```

(این چند خط اول `python3 wc.py count --help` است؛ بقیه هر گزینه را با متن راهنمایش فهرست می‌کند.) در `[--lines | --words]` خط عمودی یعنی «یکی از این‌ها». حالا بخش مفید: استفاده‌ی غلط چه می‌شود. دو فرمان غلط اجرا کردم. هرکدام خط‌های usage را چاپ می‌کند، بعد یک خطا روی **stderr** (جریان خطا، جدا از خروجی عادی)، و با {{< term "exit-status" "کد خروج" >}} ۲ تمام می‌شود. خط‌های تکراری usage را اینجا نیاورده‌ام:

```text
$ python3 wc.py count --lines --words t.txt
wc.py count: error: argument --words: not allowed with argument --lines
rc=2
$ python3 wc.py count --format xml t.txt
wc.py count: error: argument --format: invalid choice: 'xml' (choose from text, json)
rc=2
```

کد خروج چیزی است که برنامه‌ی صدازننده بررسی می‌کند. قرارداد من این است:

- `0` یعنی موفقیت.
- `1` یعنی شکست در زمان اجرا. شمردن فایلی که وجود ندارد (`nope.txt`) عبارت `wc.py: nope.txt: not found` را چاپ کرد و rc=1 داد.
- `2` یعنی خطای استفاده. argparse خودش این کار را می‌کند.

`main()` یک عدد برمی‌گرداند و خط آخر، `sys.exit(main())`، آن را به shell می‌دهد. برگرداندن عدد، به‌جای صدا زدن `sys.exit` در عمق کد، تست‌کردن `main` را هم آسان می‌کند، که بعداً می‌بینیم.

## تنظیمات، متغیر محیطی و logging

ابزار معمولاً چند جا برای گرفتن تنظیم دارد. در اسکریپت من مقدار `format` این‌طور انتخاب می‌شود: اول {{< term "environment-variable" "متغیر محیطی" >}} `WC_FORMAT`، بعد فایل `--config file.toml` که با `tomllib` استاندارد خوانده می‌شود، بعد مقداری که از خط فرمان می‌آید (یا پیش‌فرضش). فایل یک خط داشت: `format = "json"`:

```text
$ python3 wc.py count t.txt                           ->  2 5
$ python3 wc.py --config c.toml count t.txt           ->  {"lines": 2, "words": 5}
$ WC_FORMAT=text python3 wc.py --config c.toml ...    ->  2 5
```

بدون config خروجی `2 5` بود (دو خط، پنج کلمه). با config خروجی JSON شد و متغیر محیطی فایل را بی‌اثر کرد و دوباره متن برگشت. `--config c.toml count --format text t.txt` را هم اجرا کردم و باز JSON گرفتم. این یک عیب دموی من است: flag خط فرمان کمترین اولویت را دارد، برعکس چیزی که کاربران معمولاً انتظار دارند. در ابزار واقعی معمولاً باید flag صریح اول بیاید، بعد محیط، بعد فایل، بعد پیش‌فرض.

دو عادت کوچک‌تر. `logging.basicConfig(stream=sys.stderr)` که با `-v` به DEBUG می‌رود، پیام‌های تشخیصی را روی stderr نگه می‌دارد، تا stdout برای هر چیزی که در pipe بعد می‌آید تمیز بماند (با `-v` دمو پیش از نتیجه روی stderr عبارت `DEBUG format=text cfg={}` را چاپ کرد). و `pathlib.Path` به‌عنوان نوع آرگومان یک شیء مسیر می‌دهد که `read_text()` دارد.

## pipe و SIGPIPE

برگردیم به traceback ابتدای پست. pipe خروجی یک برنامه را به ورودی برنامه‌ی دیگر وصل می‌کند. در `emit.py | head -2`، `head` دو خط می‌گیرد و بعد تمام می‌شود و سر خودش از pipe را می‌بندد. وقتی `emit.py` دوباره می‌نویسد، سیستم‌عامل با {{< term "signal" "سیگنال" >}} {{< term "sigpipe" "SIGPIPE" >}} به آن خبر می‌دهد که خواننده رفته است. بیشتر ابزارهای خط فرمان همین‌جا بی‌سروصدا می‌میرند. تا آنجا که می‌دانم Python هنگام شروع SIGPIPE را نادیده می‌گیرد، پس نوشتن به‌جای آن با exception شکست می‌خورد. خروجی واقعی این است:

```text
0
1
Traceback (most recent call last):
  File "<tmp>/emit.py", line 3, in <module>
    print(i)
    ~~~~~^^^
BrokenPipeError: [Errno 32] Broken pipe
Exception ignored while flushing sys.stdout:
BrokenPipeError: [Errno 32] Broken pipe
status=120 0
```

خط آخر کد خروج دو برنامه‌ی pipeline را نشان می‌دهد: `emit.py` با ۱۲۰ و `head` با ۰ تمام شد. ۱۲۰ از این می‌آید که مفسر هنگام خروج نتوانست خروجی را flush کند، که همان خط‌های «Exception ignored» است. راه‌حل الگویی از مستندات Python است:

```python
except BrokenPipeError:
    devnull = os.open(os.devnull, os.O_WRONLY)
    os.dup2(devnull, sys.stdout.fileno())
    sys.exit(141)
```

وقتی pipe می‌شکند، کد خروجی استاندارد را به `/dev/null` وصل می‌کند، پس flush نهایی هنگام خروج جایی برای شکست ندارد، و بعد بی‌سروصدا خارج می‌شود. با این کد در `emit2.py` خروجی فقط `0` و `1` بود و کد `141 0`. بدون traceback. و ۱۴۱ همان عددی است که shell برای process کشته‌شده با SIGPIPE نشان می‌دهد (۱۲۸ + ۱۳)، پس مثل یک ابزار بومی رفتار می‌کند.

## subprocess بدون shell

ابزار اغلب برنامه‌های دیگر را اجرا می‌کند. راه پرخطر این است که فرمان را به‌شکل رشته بسازید و به shell بدهید. برای نشان دادن دلیلش فایلی به نام `my file.txt` با فاصله در نام ساختم:

```text
shell=True  : 1 'wc: my: open: No such file or directory\nwc: file.txt: open: No such file or directory'
list args   : 0 1
shlex.quote : 'my file.txt'
check=True  : 1 'ls: missing.txt: No such file or directory'
```

خط به خط:

- با `shell=True` شل نام را سر فاصله شکست و `wc -l my file.txt` را اجرا کرد، که دو فایل ناموجود می‌خواهد. کد خروج ۱. اگر این متن از یک کاربر می‌آمد می‌توانست چیزی بسیار بدتر از یک فاصله داشته باشد.
- با فهرست آرگومان‌ها (`["wc", "-l", name]`) هیچ shellی در کار نیست و نام یک آرگومان واحد می‌رسد. کار کرد: کد خروج ۰ و شمارش `1`.
- `shlex.quote` نشان می‌دهد quote کردن درست برای shell چه شکلی است: نام داخل نقل‌قول.
- `check=True` باعث می‌شود `subprocess.run` وقتی فرمان با کد غیرصفر تمام شد `CalledProcessError` پرتاب کند، نه اینکه بتوانید نادیده‌اش بگیرید. اینجا `ls` شکست خورد و exception کد ۱ و متن خطا را داشت.

اگر ناچارید رشته‌ی shell بسازید، هر تکه را با `shlex.quote` بپیچید. فهرست بهتر است و باید انتخاب پیش‌فرض باشد.

## Ctrl-C

Ctrl-C سیگنال SIGINT را می‌فرستد و Python آن را به‌شکل `KeyboardInterrupt` بالا می‌آورد. دو اسکریپت کوچک را امتحان کردم که ۳۰ ثانیه می‌خوابند. یک اسکریپت والد هرکدام را اجرا کرد، یک ثانیه صبر کرد و SIGINT فرستاد:

```text
sig.py returncode 130 | stderr tail: interrupted
sig2.py returncode -2 | stderr tail: KeyboardInterrupt
```

`sig.py` عبارت `except KeyboardInterrupt: sys.exit(130)` را دارد، پس یک پیام کوتاه چاپ کرد و ۱۳۰ برگرداند. `sig2.py` handler ندارد، پس Python traceback را چاپ کرد (آخرین خطش `KeyboardInterrupt` است) و بعد خود process با سیگنال تمام شد. `subprocess` آن را `-2` گزارش می‌کند، شماره‌ی سیگنال با علامت منفی، که shell آن را ۱۳۰ نشان می‌دهد (۱۲۸ + ۲). هر دو برای shell یک کد دارند، ولی نسخه‌ی با handler traceback ندارد.

## Typer

argparse صریح است: برای همه‌چیز `add_argument` صدا می‌زنید. Typer همان رابط را از type hint می‌سازد و زیرش Click است. همان CLI با حدود ۱۵ خط منطق درآمد:

```python
@app.command()
def count(file: Optional[Path] = None, limit: int = 0,
          fmt: Annotated[Fmt, typer.Option("--format")] = Fmt.text): ...
```

`Fmt` یک `Enum` با `text` و `json` است، و Typer از همین می‌فهمد گزینه‌های مجاز کدام‌اند. با `--format xml` Typer یک خطای قاب‌دار چاپ کرد، `Invalid value for '--format': 'xml' is not one of 'text', 'json'.`، با کد خروج ۲. `--limit abc` پیام `'abc' is not a valid integer.` داد، آن هم با کد ۲. Typer `--install-completion` و `--show-completion` را هم به help اضافه کرد. گروه ناسازگار را دوباره نساختم.

| | argparse | Click | Typer |
|---|---|---|---|
| نصب | کتابخانه‌ی استاندارد | وابستگی | وابستگی (از Click استفاده می‌کند) |
| سبک | فراخوانی صریح | decorator | type hint |
| مناسب | اسکریپت، بدون وابستگی | CLI بزرگ‌تر | CLI تایپ‌دار سریع |

این جدول نظر خودم است؛ فقط argparse و Typer را اجرا کردم.

## اسکریپت تک‌فایلی و تست

گاهی یک اسکریپت کافی است ولی وابستگی دارد. {{< term "inline-script-metadata" "inline script metadata" >}} اجازه می‌دهد اسکریپت نیازهایش را در یک بلوک کامنت اعلام کند و `uv run --script` آن را بخواند:

```python
#!/usr/bin/env -S uv run --script
# /// script
# dependencies = ["humanize==4.13.0"]
# ///
```

(`size.py` واقعی یک خط `requires-python` هم دارد.) بعد از `chmod +x`، دستور `./size.py 1500000` پکیج `humanize` را در محیطی که uv مدیریت می‌کند نصب کرد و `1.5 MB` چاپ کرد. اجرای دوم همان را بدون نصب چیزی چاپ کرد. خط shebang روی macOS کار کرد.

برای تست، این طراحی ثمر می‌دهد. چون `main(argv)` آرگومان‌ها را به‌شکل فهرست می‌گیرد و کد خروج را برمی‌گرداند، تست می‌تواند آن را مستقیم با `capsys` در pytest صدا بزند ([تست در Python با pytest](/fa/posts/py-testing-pytest/)) و خروجی و کد را بررسی کند. برای کد خروج واقعی process، اسکریپت را با `subprocess.run` اجرا کنید. سه تست من برای `wc.py` پاس شدند (شمارش با `capsys`، خروج با کد ۲ برای گزینه‌ی غلط، و subprocess که برای فایل ناموجود ۱ برمی‌گرداند)، و یکی هم برای نسخه‌ی Typer با `CliRunner` خود Typer: در کل 4 passed.

## در مقایسه با Go

در Go یک CLI به یک باینری کامپایل می‌شود که مفسر نمی‌خواهد، و `flag` هم در کتابخانه‌ی استاندارد هست. ابزار Python روی ماشین مقصد مفسر و وابستگی‌هایش را می‌خواهد، مگر اینکه مثل پست قبل بسته‌بندی شود.

## تله‌های CLI

- از `main()` عدد برگردانید و خطاها را به stderr بفرستید، تا صدازننده بتواند موفقیت را از شکست تشخیص دهد و pipeها تمیز بمانند.
- هرگز `shell=True` را با متنی که کاربر کنترل می‌کند به کار نبرید. فهرست آرگومان هم از باگ quote کردن جلوگیری می‌کند هم از injection.
- اگر ابزارتان زیاد چاپ می‌کند `BrokenPipeError` را مدیریت کنید؛ وگرنه `| head` ابزار سالم را به ابزاری تبدیل می‌کند که خراب به نظر می‌رسد.
- اولویت flag، متغیر محیطی و فایل config را آگاهانه تعیین کنید و بنویسید. دموی من آن را برعکس داشت.
- نسخه‌ها را در metadata اسکریپت pin کنید تا سال بعد هم همین‌طور رفتار کند.

## تمرین

کاری کنید که `--limit` مقدار پیش‌فرضش را از فایل `--config` بخواند، و با `capsys` تستش کنید.

## قدم بعدی

قدم بعد: «پردازش داده‌ی کوچک با csv و sqlite3»، چون خیلی از اسکریپت‌های واقعی آخرش باید CSVای را بخوانند که کسی فرستاده.
