+++
date = '2027-06-07T10:00:00+03:30'
draft = false
title = 'اسکریپت‌نویسی ایمن و cron'
description = 'اسکریپت‌نویسی ایمن در shell و cron روی macOS: quoting، تله‌های set -e، نوشتن اتمی، قفل mkdir و پارسر cron به Go با تست.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "shell", "cron", "scripting", "locking", "go"]
cover = { image = "/images/covers/linux-scripting-cron-safely.fa.png", alt = "اسکریپت‌نویسی ایمن و cron", hiddenInSingle = true }
+++

این آخرین پست سری Linux است. بعد از [strace و perf برای عیب‌یابی](/fa/posts/linux-strace-perf/) می‌دانیم چطور داخل یک پردازش در حال اجرا را ببینیم؛ حالا می‌خواهیم اسکریپت‌های کوچک دور سرویس‌هایمان ساعت ۳ شب خراب نشوند. این پست بر [پوسته‌ی کاربردی](/fa/posts/linux-shell-practical/)، [پروسه و سیگنال](/fa/posts/linux-processes-signals/) (برای `trap`) و [systemd: واحدها و timerها](/fa/posts/linux-systemd-units-timers/) بنا شده است.

> توضیح صادقانه: همه‌چیز روی **macOS** اجرا شد (`/bin/sh`، `/bin/bash` نسخه‌ی 3.2 و ابزارهای BSD). `flock`، `timeout` و `shellcheck` نصب نیستند (`command -v` چیزی چاپ نکرد)، پس اجرایشان نکردم. به crontab واقعی‌ام دست نزدم. الگوهای خطرناک فقط با `echo` یا در یک پوشه‌ی موقت اجرا شدند.

## باگ‌های کلاسیک با اجرای واقعی

متغیر خالی به‌علاوه‌ی glob فاجعه‌ی معروف است. من فقط `echo` کردم:

```sh
dir=""; echo rm -rf $dir/*
```
```
rm -rf /Applications /Library /System ...
```

`$dir/*` شد `/*`، یعنی پوشه‌های واقعی سطح بالا. `set -u` و `${dir:?}` جلویش را می‌گیرند.

```sh
sh -c 'set -u; echo "$undefined_v"'     # /bin/sh: undefined_v: unbound variable
sh -c 'dir=""; echo "${dir:?dir is empty}/x"'   # /bin/sh: dir: dir is empty
```

هر دو با کد 127 خارج شدند. expansion بدون quote همان {{< term "word-splitting" "word splitting" >}} است؛ به‌جای `ls` روی glob حلقه بزنید:

```sh
for f in $(ls data); do echo "[$f]"; done    # [a] [b] [c]  (فایل "b c" شکسته شد)
for f in data/*;     do echo "[$f]"; done    # [data/a] [data/b c]
```

`cd` ناموفق اسکریپت را متوقف نمی‌کند: `cd nodir; echo "now in: $(basename "$PWD")"` چاپ کرد `now in: sandbox`. بنویسید `cd nodir || exit 1`.

`read l` متن `  lead  ` را به `[lead]` کوتاه کرد؛ `IFS= read -r l` همان را نگه داشت. با `v` خالی، `[ $v = x ]` با `unary operator expected` (کد 2) شکست خورد، ولی `[[ $v = x ]]` در bash تمیز 1 برگرداند؛ `[[ ]]` استاندارد POSIX نیست. برای نام‌هایی که با خط تیره شروع می‌شوند `rm -- -n` بنویسید.

## غافلگیری‌های set -e

استثناهای `set -e`، اجرای واقعی:

```sh
set -e; false && echo no; echo "reached"     # reached, exit 0
set -e; f() { false; echo "in f"; }; f || echo failed   # in f  (داخل f، set -e خاموش است)
set -e; ( false; echo inner ) || echo handled           # inner, handled
set -e; false | true; echo "pipe hidden"                # pipe hidden
set -eo pipefail; false | true; echo no                 # exit 1
```

پس `-e` فقط تور ایمنی است: دستورهای مهم را صریح چک کنید.

## فایل موقت و نوشتن اتمی

نام‌های قابل‌پیش‌بینی مثل `/tmp/foo` به {{< term "race-condition" "race" >}} دعوت می‌کنند؛ از `mktemp -d` و `trap` استفاده کنید. برای جایگزینی فایل، فایل موقت بنویسید و `mv` کنید: یک {{< term "atomic-write" "نوشتن اتمی" >}}. آزمایش من: یک writer فایل `cfg.txt` را ۳۰۰ بار بازنویسی می‌کند و reader در حلقه می‌خواند.

```
naive:  reads=9   bad_reads=3
atomic: reads=220 bad_reads=0
```

روش truncate-و-بنویس فایل خالی به reader نشان داد؛ rename هرگز.

## یک قفل قابل‌حمل

برای اجراهای هم‌پوشان، `flock -n` (از util-linux) جواب Linux است. من اینجا `mkdir` اتمی را با فایل PID و تشخیص {{< term "lockfile" "قفل کهنه" >}} به کار بردم:

```
08:10:17Z pid 94781: got the lock, working for 3s
08:10:18Z pid 94786: already running as pid 94781, exiting      (exit 75)
```

قفلی که PID مرده داشت، کهنه گزارش و تصاحب شد. محدودیت‌ها: دو پردازش هنوز می‌توانند سر تصاحب race کنند و PIDها دوباره استفاده می‌شوند. برای cron کافی است.

## خود cron

از `man 5 crontab` همین مک (صفحه‌ی سبک Vixie):

- پنج فیلد (دقیقه تا روز هفته؛ ۰ و ۷ یکشنبه‌اند) با بازه، لیست و گام؛ ثانیه ندارد.
- اگر هر دو فیلد روز محدود شده باشند، فرمان وقتی اجرا می‌شود که **یکی** از آن‌ها بخواند: `30 4 1,15 * 5` یعنی اول، پانزدهم و هر جمعه.
- `%` به newline تبدیل می‌شود مگر `\%` نوشته شود.
- خروجی ایمیل می‌شود (`MAILTO`) مگر redirect کنید.
- تغییر DST طبق بخش BUGS می‌تواند اجرا را جا بیندازد یا تکرار کند.
- محیط حداقلی است (`SHELL=/bin/sh`، `HOME`، `LOGNAME`)؛ `PATH` خودتان را تنظیم کنید.
- اجراهای از دست‌رفته‌ی زمان خاموشی جبران نمی‌شوند؛ طبق مستندات، `Persistent=true` در systemd جبران می‌کند.

یک پارسر، ماشین‌حساب اجراهای بعدی و linter به Go نوشتم (`go test -race` با همین مثال‌های man page گذشت). اجراهای بعدی، UTC، از دوشنبه 2027-06-07 ساعت 10:00:

```
"30 4 1,15 * 5"   Fri 06-11 04:30, Tue 06-15, Fri 06-18, Fri 06-25, Thu 07-01
"0 0 31 2 *"      never runs
"@daily"          Tue 06-08 00:00, Wed 06-09 ...
```

linter کارهای هر‌دقیقه، تاریخ‌های ناممکن، `%` بدون escape، مسیر نسبی و خروجی بدون redirect را گرفت. دقیقه‌ی `0` باعث شروع هم‌زمان کارهای زیاد می‌شود ({{< term "thundering-herd" "thundering herd" >}})؛ دقیقه‌های فرد یا jitter بگذارید.

## جایگزین‌ها

timerهای systemd `OnCalendar=`، `Persistent=` و `RandomizedDelaySec=` دارند؛ اجرایشان نکردم. CronJob در Kubernetes برای هم‌پوشانی فیلد `concurrencyPolicy` دارد، طبق مستندات.

## الگویی که همه را ترکیب می‌کند

`template.sh` (حدود ۳۰ خط) دارد: `set -eu`، `PATH` ثابت، `umask 077`، `getopts`، حالت `-n` برای dry run، قفل `mkdir`، `mktemp -d` با `trap` و لاگ UTC روی stderr. اجراهای واقعی:

```
$ sh template.sh
usage: <demo>/template.sh [-n] [-o outdir] [--] input...      (exit 2)
$ sh template.sh -n -o res in1.log "in 2.log"
2027-... dry run: would write 2 files to res                  (exit 0, no res dir)
$ sh template.sh missing.log
... cannot read missing.log                                    (exit 1, temp and lock removed)
```

## چند نکته‌ی مهم

- مسیر مطلق، `PATH` تنظیم‌شده و کاربر با کمترین دسترسی ([سیستم فایل و مجوزها](/fa/posts/linux-filesystem-permissions/)).
- هرگز راز (secret) را در اسکریپت یا خط crontab نگذارید؛ [مدیریت راز و کلید](/fa/posts/sec-secrets-management/).
- خروجی را در لاگ بریزید و کد خروج را مانیتور کنید. یک {{< term "dead-mans-switch" "dead man's switch" >}} اضافه کنید: بعد از موفقیت به یک مانیتور ping بزنید و وقتی ping نیامد هشدار بگیرید.
- کارها را {{< term "idempotency" "idempotent" >}} کنید. روی Linux از `timeout` در GNU استفاده کنید.
- اسکریپت‌های deploy همین قواعد را دارند: [طراحی pipeline برای CI/CD](/fa/posts/eng-ci-cd-pipeline-design/).

## تمرین

`lock.sh` را دو بار اجرا کنید، بعد دارنده را با `kill -9` بکشید و نسخه‌ی سوم را اجرا کنید؛ پیام قفل کهنه را بخوانید.

## قدم بعدی

سری Linux اینجا تمام می‌شود. بعدی سری سیستم‌های توزیع‌شده است، با «چرا سیستم توزیع‌شده سخت است» ([لینک](/fa/posts/ds-why-distributed-is-hard/)). پوشش داده نشد: همه‌چیز از یک Mac آمد، پس هسته‌ی واقعی Linux، کانتینر یا systemd اجرا نکردم؛ بخش‌های ویژه‌ی Linux از مستندات‌اند و برچسب خورده‌اند.
