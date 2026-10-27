+++
date = '2027-04-10T10:00:00+03:30'
draft = false
title = '/proc و مشاهده‌ی سیستم'
description = 'مشاهده‌ی سیستم با /proc در Linux: فایل‌های مهم، ابزارهای معادل در macOS که اجرا شدند، و برنامه‌ی Go با build tag برای خواندن /proc.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "proc", "observability", "debugging", "go", "macos"]
cover = { image = "/images/covers/linux-proc-observability.fa.png", alt = "/proc و مشاهده‌ی سیستم", hiddenInSingle = true }
+++

«سرور کند است» یا «پروسه نشت دارد» وقتی به درد می‌خورد که بتوانید داخل سیستم در حال اجرا را ببینید. این چهارمین پست سری Linux است، بعد از [پروسه و سیگنال](/fa/posts/linux-processes-signals/). این بار می‌بینیم Linux وضعیتش را چطور نشان می‌دهد و همین واقعیت‌ها را در جاهای دیگر با چه ابزاری می‌شود دید.

> توضیح صادقانه: روی این مک هسته‌ی Linux نیست. `/proc` و `/sys` و `strace` و `perf` اینجا وجود ندارند، `free` و `vmstat` هم همین‌طور. بخش‌های علامت‌خورده با **مستندات** از man pageها (`proc(5)` و صفحه‌های فرعی‌اش در man7.org) آمده‌اند، نه از اجرا. هرچه **اجرا شد** روی macOS اجرا شده (Go 1.26، ابزارهای BSD) و شناسه‌ها پنهان شده‌اند.

## /proc چیست (مستندات، اینجا اجرا نشد)

{{< term "procfs" "/proc" >}} یک فایل‌سیستم مجازی است: کرنل فایل‌ها را هنگام خواندن می‌سازد. طبق man pageها این‌ها مفیدترند:

- `/proc/self`: لینکی به پوشه‌ی خود پروسه‌ای که آن را باز می‌کند.
- `/proc/<pid>/status`: فیلدهای خوانا مثل `VmPeak`، `VmRSS`، `Threads` و `FDSize`. خود صفحه هشدار می‌دهد مقدارهای `Vm*` ممکن است دقیق نباشند.
- `/proc/<pid>/fd/`: به‌ازای هر {{< term "file-descriptor" "فایل دسکریپتور" >}} باز یک symbolic link. pipe و سوکت به شکل `type:[inode]` دیده می‌شوند.
- `/proc/loadavg`: سه فیلد اول همان {{< term "load-average" "میانگین بار" >}} (**load average**) است و Linux کارهای آماده‌ی اجرا یا منتظر دیسک را می‌شمارد.
- `/proc/meminfo`: حافظه‌ی سیستم، از جمله `MemAvailable` که تخمین حافظه‌ی در دسترس برنامه‌های جدید بدون swap است.

هیچ‌کدام را نتوانستم اجرا کنم.

## آنچه روی macOS دیدم (اجرا شد)

همین پرسش‌ها جواب BSD دارند. در سطح سیستم، `top -l 1 -n 0` این را چاپ کرد (کوتاه‌شده):

```
Processes: 473 total, 10 running, 463 sleeping
Load Avg: 11.94, 7.03, 6.74
PhysMem: 7177M used (1493M wired, 2007M compressor)
```

`sysctl` هشت CPU و حدود ۸ گیگابایت حافظه را گزارش کرد و `vm_stat` صفحه‌های ۱۶۳۸۴ بایتی می‌شمارد. بار ۱۱٫۹۴ روی ۸ هسته یعنی ماشین شلوغ بود، پس اینجا زمان‌بندی منتشر نمی‌کنم، فقط شمارش.

برای یک پروسه برنامه‌ی کوچک Go نوشتم (`main.go`). پوشه‌ی `/dev/fd` را که روی macOS هست فهرست می‌کند، ۵ فایل باز و بسته می‌کند، بعد ۶۴ مگابایت می‌گیرد و لمس می‌کند و `runtime.ReadMemStats` و `syscall.Getrusage` را می‌خواند:

```
fds: after-before = 5
fds: after close, back to start = true
heap grew by at least 64 MiB: true
sys memory from OS, MiB (rounded up to 16): 80
max RSS >= 64 MiB: true
```

مقدار دقیق هر بار فرق می‌کند، پس مقدار منطقی و گردشده چاپ می‌کنم. تله: `ru_maxrss` روی macOS بایت است ولی طبق مستندات روی Linux کیلوبایت، برای همین کد روی Linux ضرب می‌کند. برنامه زنده می‌ماند تا از بیرون ببینمش. `lsof -p <pid>` به تفکیک نوع:

```
0u unix, 1w REG, 2w REG, 3u IPv4, 4u KQUEUE, cwd DIR, txt REG (x2)
```

۰ تا ۲ جریان‌های استاندارد هستند، ۳ سوکت گوش‌دهنده‌ی من و ۴ همان kqueue ران‌تایم (روی Linux معادلش epoll است). `lsof -nP -iTCP:<port>` برنامه را `LISTEN` روی `127.0.0.1:<port>` نشان داد و `netstat -an | grep` همان خط را.

`sample` نصب است ولی شل من اول یک shim پایتونی هم‌نام پیدا کرد، پس `/usr/bin/sample` را صدا زدم. روی پروسه‌ی `sleep` خودم بدون sudo کار کرد؛ خروجی‌اش را منتشر نمی‌کنم. `fs_usage` و `dtruss` را امتحان نکردم و حدس می‌زنم دسترسی ویژه بخواهند.

## همین برنامه برای Linux (کامپایل شد، اجرا نشد)

روی Linux مستقیم `/proc` را می‌خوانید. دو فایل با {{< term "build-tag" "build tag" >}} این کار را می‌کنند:

```go
//go:build linux
package main
// proc_linux.go: opens /proc/self/status, prints VmRSS, VmPeak,
// Threads, FDSize, then reads each link in /proc/self/fd
```

```go
//go:build !linux
package main
import "fmt"
func procReport() { fmt.Println("not Linux: no /proc here") }
```

روی macOS فایل دوم استفاده شد و برنامه `not Linux: no /proc here` چاپ کرد. برای فایل Linux دستورهای `GOOS=linux GOARCH=amd64 go vet ./...` و `go build` را زدم و هر دو گذشتند. **آن باینری را اجرا نکردم**، پس خروجی‌ای از آن نشان نمی‌دهم.

## دستورهای عیب‌یابی

| پرسش | Linux | macOS (اجرا شد) | روی Linux اجرا شد؟ |
|---|---|---|---|
| بار زیاد؟ | `cat /proc/loadavg` | `uptime`، `top -l 1 -n 0` | خیر |
| حافظه | `free -h`، `/proc/meminfo` | `vm_stat`، `top` | خیر |
| نشت fd | `ls /proc/<pid>/fd` | `lsof -p <pid>` | خیر |
| رشد حافظه | `VmRSS` در طول زمان | RSS با `ps -o rss= -p <pid>` | خیر |
| چه کسی روی پورت گوش می‌دهد؟ | `ss -ltnp` | `lsof -nP -iTCP:<port>` | خیر |
| چه می‌کند؟ | `strace -p <pid>` | `sample <pid> 1` | خیر |

ابزار عمومی ردیابی {{< term "syscall" "فراخوان سیستمی" >}} (**system call**) در Linux همان `strace` است که اجرا نکردم. برای رشد حافظه باید {{< term "rss" "RSS" >}} را دنبال کرد؛ موضوعی که در [پروفایل و حافظه در Node.js](/fa/posts/node-profiling-memory-shutdown/) دیدیم.

## چند نکته‌ی مهم

- میانگین بار را با تعداد هسته‌ها مقایسه کنید.
- واحدها را بررسی کنید: `ru_maxrss` روی macOS بایت و طبق مستندات روی Linux کیلوبایت است.
- تعداد descriptor که فقط بالا می‌رود نشت است؛ قبل و بعد را مقایسه کنید.
- مقدارهای `/proc` عکس لحظه‌ای‌اند و بعضی طبق مستندات تقریبی.
- یک shim زودتر در `PATH` می‌تواند ابزار واقعی را پنهان کند.

## تمرین

روی یک ماشین Linux برنامه‌ی ساخته‌شده با `GOOS=linux` را اجرا کنید و `FDSize` و `Threads` و لینک‌های `/proc/self/fd` را با انتظارتان مقایسه کنید. بعد ده فایل دیگر باز کنید و دوباره نگاه کنید.

## قدم بعدی

پست بعدی «systemd: واحدها و timerها» است.
