+++
date = '2027-06-04T10:00:00+03:30'
draft = false
title = 'strace و perf برای عیب‌یابی'
description = 'strace و perf از روی man pageها: خواندن خط فراخوان و errno، خلاصه‌ی -c، perf stat و record، با parser نمونه‌ی Go روی خطوط ساختگی.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "strace", "perf", "troubleshooting", "syscalls", "flame-graph", "go", "macos"]
cover = { image = "/images/covers/linux-strace-perf.fa.png", alt = "strace و perf برای عیب‌یابی", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. `strace` و `perf` فقط روی Linux کار می‌کنند و من هیچ‌کدام را اجرا نکردم. این سیزدهمین پست سری Linux است، بعد از [لاگ‌ها و journalctl](/fa/posts/linux-logs-journalctl/). حقایق از man pageهای strace(1)، ptrace(2)، perf-stat(1)، perf-record(1) و مستندات sysctl کرنل است؛ متن Linux‌مانند با عبارت «نمونه‌ی تصویری، ضبط‌نشده» علامت خورده. مرتبط: [I/O و epoll](/fa/posts/linux-io-epoll/).

## strace چه نشان می‌دهد

{{< term "syscall" "فراخوان سیستمی" >}} (system call) راه برنامه برای خواستن کار از کرنل است. {{< term "strace" "strace" >}} هر کدام را با آرگومان‌ها و نتیجه چاپ می‌کند. مثال‌های خود man page:

```
open("/dev/null", O_RDONLY) = 3
open("/foo/bar", O_RDONLY) = -1 ENOENT (No such file or directory)
```

فراخوان ناموفق -1 برمی‌گرداند و strace نماد {{< term "errno" "errno" >}} را کنارش می‌گذارد. man page می‌گوید از {{< term "ptrace" "ptrace" >}} استفاده می‌کند و پروسه‌ی ردیابی‌شده کندتر اجرا می‌شود؛ پس روی پروسه‌ی شلوغ production احتیاط کن. عددی برای سربار نمی‌دهم؛ طبق مستندات `--seccomp-bpf` هزینه را کم می‌کند.

## گزینه‌هایی که بیشتر استفاده می‌کنم

- `-f` فرزندها و threadها را دنبال می‌کند (`-f -p PID` به همه‌ی threadها وصل می‌شود).
- `-tt` زمان ساعت دیواری با میکروثانیه می‌افزاید؛ `-T` زمان صرف‌شده در هر فراخوان را نشان می‌دهد.
- `-e trace=...` فراخوان‌ها را انتخاب می‌کند، `-p PID` وصل می‌شود، `-o file` در فایل می‌نویسد.
- `-s N` طول رشته (پیش‌فرض 32)؛ `-y` مسیر file descriptorها را چاپ می‌کند.
- `-k` بعد از هر فراخوان stack trace چاپ می‌کند؛ `-c` فقط خلاصه می‌دهد.

خطوط خاص: فراخوان مسدودشده `<unfinished ...>` و بعد `<... select resumed>` است؛ فراخوان قابل‌شروع‌دوباره که سیگنال قطعش کند `ERESTARTSYS (To be restarted)` نشان می‌دهد؛ سیگنال‌ها به شکل `--- SIGALRM ... ---` و پایان به شکل `+++ exited with 1 +++` می‌آیند.

## parser‌ای که توانستم اجرا کنم

چون نمی‌توانم trace بگیرم، یک parser با Go برای این قالب نوشتم، با خلاصه‌ای شبیه `strace -c` و یک detector. ورودی **نمونه‌ای در قالب مستند، ساختگی و ضبط‌نشده** است. `go test -race` موفق بود و برنامه از `GOOS=linux GOARCH=arm64 go vet` و build هم گذشت. خروجی واقعی روی fixture:

```
$ lx13 summary testdata/sample.strace
% time     seconds  usecs/call     calls    errors syscall
 79.15    1.900900     1900900         1           futex
 20.82    0.500038       71434         7         4 read
  0.01    0.000300         300         1           execve
  ...
100.00    2.401624                    17         8 total
(1 unparsed lines skipped)
```

ردیف `futex` یک جفت unfinished و resumed است که یکی شده. `strace -c` واقعی قالب دیگری دارد و این عددها ساختگی‌اند.

```
$ lx13 detect testdata/sample.strace
FLAG: connect: connection refused (nothing listening at ...)
FLAG: 3 EAGAIN in a row on 4001/read: a non-blocking fd polled in a loop? Check for epoll
FLAG: openat "/var/lib/demo/state": EACCES, permission denied
FLAG: search path for app.conf: ENOENT in /etc/demo, /usr/local/etc/demo; found at ./app.conf
```

(آدرس کوتاه شده.) parser متن بازگشتی را بعد از آخرین `) = ` برمی‌دارد؛ پس آرگومان رشته‌ای که این دنباله را داشته باشد گولش می‌زند.

## perf

با {{< term "perf" "perf" >}}، `perf stat` رویدادهای یک دستور را می‌شمارد؛ man page آن cycles، instructions، «insn per cycle» و context switch را نشان می‌دهد. `perf record` از stackها نمونه می‌گیرد (`-g` call graph را روشن می‌کند، `-F` بسامد را تعیین می‌کند، `-p` وصل می‌شود) و `perf report` فایل را می‌خواند؛ `perf top` زنده است. نمونه‌برداری از ردیابی تک‌تک فراخوان‌ها ارزان‌تر است اما ممکن است رویدادهای کوتاه را از دست بدهد. {{< term "flame-graph" "فلیم‌گراف" >}} نمونه‌ها را می‌کشد؛ اسکریپت‌های FlameGraph از Brendan Gregg این کار را از خروجی perf می‌کنند. معادل Go در [پروفایل Go با pprof](/fa/posts/go-profiling-pprof/) است؛ {{< term "cpu-profile" "پروفایل CPU" >}} همان پرسش «زمان کجا می‌رود» را جواب می‌دهد.

دسترسی محدود است. مستندات کرنل می‌گویند پیش‌فرض `perf_event_paranoid` برابر 2 است و پروفایل کرنل را برای کاربران بدون CAP_PERFMON ممنوع می‌کند. ptrace روی پروسه‌ی کاربران دیگر CAP_SYS_PTRACE می‌خواهد (ptrace(2)). در {{< term "container" "کانتینر" >}} ممکن است این {{< term "linux-capabilities" "capabilityها" >}} نباشند و پروفایل seccomp جلوی ptrace را بگیرد؛ پیش‌فرض هیچ runtime را بررسی نکردم. ببین [کاربر، sudo و capability](/fa/posts/linux-users-sudo-capabilities/) و [cgroups و namespaces](/fa/posts/linux-cgroups-namespaces/).

## از علامت تا اولین دستور

| علامت | اولین دستور | دنبال چه باشی |
|---|---|---|
| فایل config پیدا نمی‌شود | `strace -f -e trace=openat,stat` | ENOENT در مسیر جست‌وجو |
| هنگ می‌کند | `strace -p PID` | `futex`، `epoll_wait`، `read`: منتظر چیست |
| اتصال برقرار نمی‌شود | `strace -e trace=connect` | ECONNREFUSED |
| Too many open files | `strace -e trace=openat,accept` | EMFILE |
| شروع کند است | `strace -c -f` | تعداد زیاد `stat` |
| CPU بالاست | `perf record -g` و `perf report` | پهن‌ترین فریم‌ها |

## مک چه نشان می‌دهد

`dtruss` و `fs_usage` را که root می‌خواهند اجرا نکردم. `/usr/bin/time -l` روی خلاصه‌ساز، بیشینه‌ی resident set برابر 4816896 بایت گزارش کرد (macOS؛ تغییر می‌کند).

## چند نکته‌ی مهم

- strace زمان‌بندی را عوض می‌کند و ممکن است race را پنهان کند.
- اولین خطا را بخوان، نه آخرین را: خطاهای بعدی اغلب پیامد هستند.
- ENOENT هنگام جست‌وجوی مسیر عادی است؛ پرسش این است که آخری شکست می‌خورد یا نه.
- trace ممکن است راز (secret) از بافر read/write داشته باشد؛ بی‌فکر paste نکن.

## تمرین

روی یک VM لینوکسی موقت، `strace -f -tt -T -o out.txt` را روی یک دستور کوتاه اجرا کن، بعد `strace -c` را، و `out.txt` را به parser بده. چه چیزی را اشتباه فهمید؟

## قدم بعدی

پست بعدی «اسکریپت‌نویسی ایمن و cron» است.
