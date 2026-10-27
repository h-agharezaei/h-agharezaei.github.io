+++
date = '2027-04-26T10:00:00+03:30'
draft = false
title = 'cgroup و namespace: پایه‌ی کانتینر'
description = 'cgroup و namespace در Linux از روی man pageها: کانتینر یعنی پروسه‌ای با دید و منبع محدود، همراه با دو برنامه‌ی Go که فقط کامپایل شدند.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "cgroups", "namespaces", "containers", "go", "macos"]
cover = { image = "/images/covers/linux-cgroups-namespaces.fa.png", alt = "cgroup و namespace: پایه‌ی کانتینر", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. این ششمین پست سری Linux است، بعد از [systemd: واحدها و timerها](/fa/posts/linux-systemd-units-timers/). پرسش این است که کانتینر واقعاً چیست. جواب از man pageها و مستندات کرنل می‌آید، به‌علاوه‌ی دو برنامه‌ی Go که برای Linux کامپایل کردم و **هرگز اجرا نکردم**. هر چیز Linux‌مانند پایین با عبارت «نمونه‌ی تصویری، ضبط‌نشده» علامت خورده است.

> توضیح صادقانه: این مک هسته‌ی Linux ندارد، ماشین مجازی هم ندارد و daemon داکر را خاموش نگه داشتم. تا آنجا که می‌دانم Docker Desktop روی مک کانتینرها را داخل یک ماشین مجازی Linux اجرا می‌کند؛ برای همین چیزی نتوانستم امتحان کنم. پست قبلی [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/) هم اعتراف کرد که build واقعی Docker نکرده است.

## دید محدود و منبع محدود

کانتینر یک پروسه‌ی معمولی با دو محدودیت است. {{< term "namespace" "namespace" >}} تعیین می‌کند پروسه چه چیزی را **ببیند** و {{< term "cgroup" "cgroup" >}} (**control group**) تعیین می‌کند چقدر **مصرف** کند. این دو، با یک root filesystem، همان {{< term "container" "کانتینر" >}} است؛ در کرنل «شیء کانتینر» وجود ندارد.

طبق namespaces(7) این نوع‌ها هستند:

| چه چیزی جدا می‌شود | flag | نمونه‌ی تصویری، ضبط‌نشده |
|---|---|---|
| hostname | `CLONE_NEWUTS` | `hostname` داخل نام دیگری نشان می‌دهد |
| شناسه‌ی پروسه | `CLONE_NEWPID` | اولین پروسه خودش را PID 1 می‌بیند |
| نقطه‌های mount | `CLONE_NEWNS` | mountهای آن روی میزبان اثر ندارد |
| شبکه | `CLONE_NEWNET` | اینترفیس و پورت‌های خودش |
| IPC | `CLONE_NEWIPC` | IPC سیستم V خودش |
| شناسه‌ی کاربر و گروه | `CLONE_NEWUSER` | داخل root، بیرون بدون دسترسی |
| ریشه‌ی cgroup | `CLONE_NEWCGROUP` | ریشه‌ی cgroup متفاوت |
| ساعت‌ها | `CLONE_NEWTIME` | ساعت boot و monotonic |

وارد شدن با `clone(2)` یا `unshare(2)` یا `setns(2)` انجام می‌شود و ابزارهای خط فرمانش `unshare(1)` و `nsenter(1)` هستند. هر پروسه در `/proc/<pid>/ns/` لینک‌هایی دارد؛ دو پروسه در یک namespace شناسه‌ی یکسانی مثل `uts:[...]` نشان می‌دهند. صفحه می‌گوید ساخت بیشتر namespaceها `CAP_SYS_ADMIN` می‌خواهد ولی از Linux 3.8 به بعد user namespace نیازی به دسترسی ویژه ندارد؛ این پایه‌ی مستند کانتینر بدون root (**rootless**) است.

## سقف‌ها با cgroups v2

طبق مستندات کرنل، cgroup v2 یک سلسله‌مراتب یکپارچه است که معمولاً در `/sys/fs/cgroup` mount می‌شود. هر گروه یک پوشه است:

| هدف | فایل | نمونه‌ی تصویری، ضبط‌نشده |
|---|---|---|
| انتقال پروسه | `cgroup.procs` (نوشتن PID) | PID در فایل دیده می‌شود |
| سقف حافظه | `memory.max` | در سقف OOM killer عمل می‌کند |
| سقف تعداد پروسه | `pids.max` | بیشتر از آن fork شکست می‌خورد |
| سقف CPU | `cpu.max` (`$MAX $PERIOD`) | حداکثر MAX در هر PERIOD |
| شمارش OOM | `memory.events`، فیلد `oom_kill` | شمارنده بالا می‌رود |

مستندات می‌گویند وقتی مصرف به `memory.max` برسد و کم نشود، {{< term "oom-killer" "OOM killer" >}} در همان cgroup فعال می‌شود. فعال شدن یک controller برای فرزندان از راه `cgroup.subtree_control` پدر انجام می‌شود.

## دو برنامه، کامپایل شد ولی اجرا نشد

در `~/Documents/work/blog-series/linux-cgroups-namespaces` یک module نوشتم. حالت `ns` دستور را با `syscall.SysProcAttr{Cloneflags: CLONE_NEWUTS | CLONE_NEWPID | CLONE_NEWNS}` اجرا می‌کند، همان نمونه‌ی کلاسیک. حالت `cg` پوشه‌ی `/sys/fs/cgroup/blogdemo` را می‌سازد، `+memory +pids` را در پدر فعال می‌کند، `memory.max` (۶۴ مگابایت) و `pids.max` (۳۲) را می‌نویسد، دستور را اجرا و PID آن را در `cgroup.procs` می‌نویسد. هر دو اول root و cgroup v2 را بررسی می‌کنند. ضعف: فرزند لحظه‌ای قبل از ورود به cgroup اجرا می‌شود.

```go
//go:build linux
cmd.SysProcAttr = &syscall.SysProcAttr{
	Cloneflags: syscall.CLONE_NEWUTS | syscall.CLONE_NEWPID | syscall.CLONE_NEWNS,
}
```

{{< term "build-tag" "build tag" >}} این کد را از مک دور نگه می‌دارد، مثل [/proc و مشاهده‌ی سیستم](/fa/posts/linux-proc-observability/). برای Linux فقط `GOOS=linux GOARCH=arm64 go vet ./... && go build` را زدم و هر دو گذشتند؛ **باینری را هرگز اجرا نکردم**. روی مک `go run . ns /bin/sh` از stub استفاده کرد و چاپ کرد:

```
Linux only: namespaces and cgroups do not exist on this OS
```

## runtime چه اضافه می‌کند

محتاطانه و از مستندات: image مجموعه‌ای از لایه‌هاست که معمولاً با {{< term "overlayfs" "overlayfs" >}} mount می‌شود و runtime با `pivot_root` پروسه را به آن ریشه می‌برد. ابزارهایی مثل Docker و containerd و runc image و لایه و پیکربندی runtime اضافه می‌کنند؛ تا جایی که می‌دانم مشخصات OCI runtime آن پیکربندی را تعریف می‌کند.

## چند نکته‌ی مهم

- کانتینر ماشین مجازی نیست: کرنل میزبان را به اشتراک می‌گذارد.
- namespace پنهان می‌کند، cgroup محدود می‌کند. هر دو لازم‌اند.
- هر دو برنامه روی Linux root می‌خواهند؛ از یک ماشین قابل‌دورریختن استفاده کنید.
- رسیدن به `memory.max` در گروه به OOM kill می‌رسد، نه یک خطای مؤدبانه.

## تمرین

روی یک ماشین Linux قابل‌دورریختن `unshare(1)` را بخوانید و `unshare --uts --pid --fork --mount-proc /bin/sh` را امتحان کنید. `readlink /proc/self/ns/uts` را قبل و بعد مقایسه کنید، بعد حالت `cg` را اجرا کنید و `memory.events` را بخوانید.

## قدم بعدی

پست بعدی «حافظه، page cache و OOM killer» است.
