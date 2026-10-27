+++
date = '2027-05-02T10:00:00+03:30'
draft = false
title = 'حافظه، page cache و OOM killer'
description = 'حافظه در Linux از روی man pageها: free و available، page cache، overcommit، امتیاز OOM و سقف cgroup، همراه با برنامه‌ی Go که روی مک اجرا شد.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "memory", "page-cache", "oom-killer", "go", "macos"]
cover = { image = "/images/covers/linux-memory-page-cache-oom.fa.png", alt = "حافظه، page cache و OOM killer", hiddenInSingle = true }
+++

این را روی یک مک نوشتم؛ هیچ‌چیز اینجا روی Linux اجرا نشده است. این هفتمین پست سری Linux است، بعد از [cgroup و namespace: پایه‌ی کانتینر](/fa/posts/linux-cgroups-namespaces/). پرسش این است که چرا `free` تقریباً هیچ حافظه‌ی آزادی نشان نمی‌دهد و چرا یک سرویس با کد خروج ۱۳۷ مُرد. واقعیت‌ها از man pageها و مستندات کرنل است؛ متن Linux‌مانند با عبارت «نمونه‌ی تصویری، ضبط‌نشده» علامت خورده است.

## خواندن free و /proc/meminfo

طبق proc_meminfo(5) فیلد `MemAvailable` تخمینی از حافظه‌ی قابل استفاده برای برنامه‌های تازه بدون swap است و `Cached` کش حافظه‌ای فایل‌های خوانده‌شده از دیسک، یعنی {{< term "page-cache" "page cache" >}}. free(1) ستون `used` را کل منهای available تعریف می‌کند، `free` را حافظه‌ی بی‌استفاده (`MemFree`) و `buff/cache` را جمع buffers و cache.

پس ستون `free` کوچک عادی است: کرنل RAM اضافه را کش می‌کند و هر وقت لازم شد پس می‌دهد. ستون `available` را بسنجید. خواندن دوباره‌ی یک فایل هم همین‌طور فرق دارد: بار اول کش از دیسک پر می‌شود و بار دوم می‌تواند از حافظه بیاید.

نوشتن اول در کش انجام می‌شود. `Dirty` حافظه‌ای است که منتظر نوشتن روی دیسک است و `Writeback` حافظه‌ای که همین حالا نوشته می‌شود. sysctlهای `vm.dirty_background_ratio` و `vm.dirty_ratio` زمان شروع نوشتن را تعیین می‌کنند.

## swap، overcommit و اندازه‌ها

{{< term "swap" "swap" >}} صفحه‌های کم‌استفاده را روی دیسک می‌برد (`SwapTotal` و `SwapFree`). {{< term "overcommit" "overcommit" >}} با `vm.overcommit_memory` تنظیم می‌شود؛ مستندات ۰ را حالت پیش‌فرض تخمینی که overcommitهای آشکار را رد می‌کند، ۱ را همیشه اجازه بده و ۲ را هرگز overcommit نکن توصیف می‌کنند. `CommitLimit` و `Committed_AS` حسابداری‌اش‌اند.

سه اندازه برای یک پروسه:

| نام | معنی | کجا |
|---|---|---|
| VSZ | اندازه‌ی مجازی، بیشترش لمس نشده | `VmSize` در `/proc/<pid>/status` |
| {{< term "rss" "RSS" >}} | صفحه‌های حاضر در RAM | `VmRSS` |
| PSS | RSS با تقسیم صفحه‌های مشترک بین کاربرانشان | `Pss` در `/proc/<pid>/smaps` |

## تخصیص‌یافته یعنی حاضر نیست

برنامه‌ای در Go نوشتم که چهار slice ۶۴ مگابایتی می‌گیرد، بعد به همه‌ی صفحه‌ها می‌نویسد و شمارنده‌های runtime و RSS اوج را از `getrusage` چاپ می‌کند. واقعاً روی macOS اجرا شد؛ فقط بایت، بدون زمان:

```
start                  HeapAlloc=   0 MiB  HeapSys=   7 MiB  Sys=  11 MiB  maxRSS=   4 MiB
allocated 4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=   5 MiB
touched   1 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS=  69 MiB
touched   4 x 64 MiB   HeapAlloc= 256 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
after drop + GC        HeapAlloc=   0 MiB  HeapSys= 263 MiB  Sys= 268 MiB  maxRSS= 261 MiB
```

heap فوراً ۲۵۶ مگابایت رشد کرد ولی RSS تا نوشتن روی صفحه‌ها نزدیک ۵ مگابایت ماند: مجازی در برابر حاضر، همان ایده‌ی VSZ و RSS. بعد از {{< term "garbage-collector" "garbage collector" >}} heap خالی بود، ولی `HeapSys` ماند و `maxRSS` یک اوج است. (`ru_maxrss` در macOS بایت است؛ به گمانم در Linux کیلوبایت.)

## چه کسی کشته می‌شود

وقتی حافظه تمام شود، {{< term "oom-killer" "OOM killer" >}} قربانی را انتخاب می‌کند. طبق man pageها `/proc/<pid>/oom_score` امتیاز فعلی است؛ بالاتر یعنی محتمل‌تر، و پایه‌ی آن عمدتاً مصرف حافظه است. `oom_score_adj` از ۱۰۰۰- تا ۱۰۰۰+ است و به امتیاز اضافه می‌شود؛ ۱۰۰۰- کشتن آن پروسه را غیرفعال می‌کند.

## کانتینر: کشته شدن با وجود حافظه‌ی آزاد میزبان

یک {{< term "cgroup" "cgroup" >}} سقف خودش را دارد. مستندات cgroup v2 می‌گویند `memory.max` سقف سخت است و وقتی مصرف به آن برسد و کم نشود OOM killer در همان cgroup فعال می‌شود. `memory.high` فقط کُند می‌کند و هرگز killer را صدا نمی‌زند. `memory.events` از جمله `oom_kill` را می‌شمارد. کانتینر به همین شکل می‌میرد در حالی که میزبان RAM آزاد دارد.

`/proc/pressure/memory` (PSI) سهم توقف `some` و `full` را گزارش می‌کند.

`GOMEMLIMIT` در Go سقف نرم است که heap و حافظه‌ی مدیریت‌شده‌ی runtime را شامل می‌شود، نه حافظه‌ی بیرونی را، طبق مستندات `runtime`. گذاشتنش کمی زیر سقف کانتینر رویه‌ی رایج است؛ [زمان‌بند و garbage collector در Go](/fa/posts/go-scheduler-gc-internals/) را ببینید.

## ابزارهای Linux و آنچه اجرا کردم

| ابزار | نشان می‌دهد | macOS |
|---|---|---|
| `free` | used، available، cache | اجرا نشد (`vm_stat`: اندازه‌ی صفحه ۱۶۳۸۴ بایت) |
| `/proc/meminfo` | فیلدهای بالا | ندارد |
| `vmstat` | شمارنده‌های swap و paging | اجرا نشد |
| `/proc/pressure/memory` | سهم توقف | ندارد |

`sysctl hw.memsize` عدد ۸ گیگابایت را (گرد شده) داد. یک parser به نام `meminfo` روی نمونه‌ای با عددهای ساختگی `go test -race` را گذراند. خواننده‌ی مخصوص Linux فقط با `GOOS=linux GOARCH=arm64 go vet ./... && go build` بررسی شد و **هرگز اجرا نشد**.

## وقتی سرویس مرموز می‌میرد

کد خروج ۱۳۷ یعنی 128+9، یک {{< term "sigkill" "SIGKILL" >}}، مثل [پروسه‌ها و سیگنال‌ها](/fa/posts/linux-processes-signals/). OOM killer می‌تواند علتش باشد، اما آدم یا systemd هم می‌فرستند. `memory.events` و بعد لاگ کرنل را ببینید (نمونه‌ی تصویری، ضبط‌نشده):

```
Memory cgroup out of memory: Killed process 4242 (app)
```

## چند نکته‌ی مهم

- `free` کم عادی است؛ `available` کم نه.
- با سقف‌ها RSS را مقایسه کنید، نه VSZ.
- overcommit شکست را عقب می‌اندازد و به شکل kill می‌آید.
- OOM را روی ماشین مهم امتحان نکنید.

## تمرین

روی یک ماشین Linux قابل‌دورریختن `free` را قبل و بعد از `cat bigfile > /dev/null` اجرا کنید.

## قدم بعدی

پست بعدی «I/O و epoll» است.
