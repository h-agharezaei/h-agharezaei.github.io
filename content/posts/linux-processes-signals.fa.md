+++
date = '2027-04-03T10:00:00+03:30'
draft = false
title = 'پروسه و سیگنال'
description = 'پروسه و سیگنال در Linux با اجرای واقعی: کد خروج 128+N، trap و پاک‌سازی، SIGKILL، zombie، گروه پروسه، SIGPIPE و خاموشی تمیز در Go.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "processes", "signals", "trap", "shell", "graceful-shutdown"]
cover = { image = "/images/covers/linux-processes-signals.fa.png", alt = "پروسه و سیگنال", hiddenInSingle = true }
+++

سروری که وسط درخواست قطع می‌شود، یا اسکریپتی که فایل موقت جا می‌گذارد، معمولاً مشکل سیگنال دارد. این سومین پست سری Linux است، بعد از [سیستم فایل و مجوزها](/fa/posts/linux-filesystem-permissions/) و [پوسته‌ی کاربردی](/fa/posts/linux-shell-practical/). این بار سراغ پروسه‌ها و سیگنال‌هایشان می‌رویم.

> توضیح صادقانه: همه‌چیز روی **macOS** اجرا شده (Darwin، bash 3.2، Python 3.14، Go 1.26)، نه Linux. `/proc`، `strace`، cgroups و systemd را اجرا نکردم و فهرست سیگنال‌ها روی Linux ممکن است فرق کند. pidها را نشان نمی‌دهم (به‌جایش رابطه‌ها را چاپ می‌کنم).

## یک پروسه و فرزندانش

یک {{< term "process" "پروسه" >}} (**process**) برنامه‌ی در حال اجراست با یک pid و یک والد. در اسکریپت، `$$` شناسه‌ی خود شل و `$!` شناسه‌ی آخرین کار پس‌زمینه است.

```sh
sleep 30 &
c1=$!
```

با `ps -o pid,ppid,pgid,stat` از اسکریپت و فرزندش پرسیدم و فقط مقایسه‌ها را چاپ کردم:

```
is_script=yes parent_is_script=no  same_group_as_script=yes state=S
is_script=no  parent_is_script=yes same_group_as_script=yes state=S
```

والد فرزند همان اسکریپت است و هر دو در یک گروه پروسه‌اند. `wait $c1` کد خروج فرزند را برمی‌گرداند.

## سیگنال و کد خروج

{{< term "signal" "سیگنال" >}} (**signal**) پیام کوچک و ناهمگام به یک پروسه است. `kill` لزوماً نمی‌کشد، فقط سیگنال می‌فرستد. اینجا `kill -l` سی‌ویک سیگنال نشان داد، از جمله `SIGEMT` و `SIGINFO`؛ شماره‌ی `SIGUSR1` اینجا ۳۰ است و گمان می‌کنم در Linux فرق دارد، پس از نام استفاده کنید.

وقتی سیگنالی پروسه را تمام می‌کند، شل `128 + N` گزارش می‌دهد. به یک sleep پس‌زمینه `kill` (یعنی {{< term "sigterm" "SIGTERM" >}}، سیگنال ۱۵) فرستادم و `wait` عدد `143` داد؛ `kill -INT` روی یک اسکریپت `130` (128+2) و `kill -KILL` عدد `137` داد. این همان {{< term "exit-status" "کد خروج" >}} است، حالا با معنا.

یک غافلگیری: اولین `kill -INT` گیر کرد، چون شل غیرتعاملی کارهای `&` را با SIGINT نادیده‌گرفته‌شده شروع می‌کند (تا جایی که می‌دانم طبق POSIX). `set -m` درستش کرد.

## trap: پاک‌سازی که همیشه اجرا می‌شود

`trap` یک handler ثبت می‌کند. این اسکریپت یک پوشه‌ی کاری می‌سازد و موقع خروج پاکش می‌کند:

```sh
tmp=$(mktemp -d "$PWD/work.XXXXXX")
cleanup() { echo "cleanup: removing temp dir ($1)"; rm -rf "$tmp"; }
trap 'cleanup EXIT' EXIT
trap 'echo "got TERM"; exit 143' TERM
trap 'echo "got USR1"' USR1
trap 'echo "got HUP"' HUP
echo ready
while :; do sleep 0.2; done
```

در پس‌زمینه اجرایش کردم و USR1، HUP و TERM فرستادم:

```
ready
got HUP
got USR1
got TERM
cleanup: removing temp dir (EXIT)
exit=143
```

بعد `exit` ترپ EXIT را فعال کرد. با `kill -INT` پیام `got INT` چاپ شد، پاک‌سازی انجام شد و کد `130` آمد.

## SIGKILL گرفته نمی‌شود

```
ready
KILL exit=137
```

هیچ خط handler و هیچ پاک‌سازی نبود: پوشه‌ی کاری روی دیسک ماند (پاکش کردم). {{< term "sigkill" "SIGKILL" >}} و SIGSTOP را نمی‌شود گرفت یا نادیده گرفت.

## zombie، گروه‌ها و nohup

فرزندی که تمام می‌شود تا وقتی والد `wait` نزند در جدول پروسه‌ها می‌ماند؛ این باقی‌مانده یک {{< term "zombie-process" "zombie" >}} است. با Python عمداً یکی ساختم: fork، فرزند با کد ۷ خارج می‌شود.

```
before wait: Z (Z = zombie)
reaped: 7
after wait: ps shows ''
```

بعد از `os.waitpid` zombie ناپدید شد و کد ۷ را گرفتم. هزاران zombie یعنی والدی که جمع نمی‌کند.

پروسه‌ها در یک {{< term "process-group" "گروه پروسه" >}} هستند و می‌شود سیگنال را به کل گروه فرستاد. `setsid` روی این مک نیست، پس از `start_new_session` در Python استفاده کردم. شل `sleep 30 & sleep 30 & wait` را اجرا کرد و `ps -g` سه پروسه شمرد. بعد از `os.killpg(pgid, SIGTERM)` (شکل شل: `kill -- -PGID`) صفر شمرد و وضعیت leader برابر `-15` بود.

طبق man page، `nohup` SIGHUP را نادیده می‌گیرد. کاری کوتاه زیر `nohup` از HUP من جان به در برد و با ۰ تمام شد؛ `trap` خودش برای HUP چاپ نکرد، که با این قاعده‌ی POSIX جور است که سیگنال نادیده‌گرفته‌شده در شروع را نمی‌شود trap کرد. روی Linux نسنجیدم.

## SIGPIPE

`yes | head -1` حرف `y` را چاپ می‌کند و می‌ایستد. `head` خارج می‌شود، نوشتن بعدی `yes` به pipe بسته می‌خورد و {{< term "sigpipe" "SIGPIPE" >}} می‌گیرد. `PIPESTATUS` عدد `141 0` را نشان داد: 128+13 برای `yes`. برای همین `pipefail` روی یک pipeline سالم هم می‌تواند 141 بدهد.

## خاموشی تمیز در Go

سرویس باید با SIGTERM کارهای در حال اجرا را تمام کند. در Go، `signal.NotifyContext` سیگنال را به یک context لغوشده تبدیل می‌کند. دموی من کارهای ۰٫۶ ثانیه‌ای دارد، context را فقط بین کارها چک می‌کند و من وسط کار ۲ سیگنال TERM فرستادم:

```
ready
job 1 start
job 1 done
job 2 start
job 2 done
stop requested, not taking new jobs
exit=0
```

کار ۲ تمام شد، کار ۳ شروع نشد و خروج ۰ بود. با `kill -KILL` همین برنامه بعد از `job 2 start` قطع شد و `137` داد. سرویس واقعی timeout هم می‌خواهد؛ [خاموشی تمیز برای workerهای Go](/fa/posts/go-graceful-shutdown-workers/) و [JetStream از Node.js](/fa/posts/node-nats-jetstream/) را ببینید. زمان‌بند کانتینر و systemd اول TERM و بعد KILL می‌فرستند. هیچ‌کدام را اجرا نکردم.

## چند نکته‌ی مهم

- اول TERM بفرستید و KILL را آخرین راه بدانید.
- پاک‌سازی را در `trap ... EXIT` بگذارید.
- ۱۴۳ یعنی TERM، ۱۳۰ یعنی INT، ۱۳۷ یعنی KILL.
- zombie را نمی‌شود کشت؛ والدش باید جمعش کند.

## تمرین

اسکریپتی بنویسید که فایل موقت می‌سازد، EXIT و INT و TERM را trap می‌کند و حلقه می‌زند. هر سیگنال و بعد `-KILL` را بفرستید و ببینید کدام اجراها فایل را جا می‌گذارند.

## قدم بعدی

پست بعدی «/proc و مشاهده‌ی سیستم» است.
