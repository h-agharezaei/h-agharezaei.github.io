+++
date = '2027-05-09T10:00:00+03:30'
draft = false
title = 'I/O و epoll'
description = 'I/O و epoll در Linux از روی man pageها: blocking و non-blocking، select و poll و epoll، level و edge، همراه با دموهای واقعی kqueue و goroutine روی مک.'
categories = ["Linux"]
series = ["Linux"]
tags = ["linux", "epoll", "kqueue", "io", "go", "macos"]
cover = { image = "/images/covers/linux-io-epoll.fa.png", alt = "I/O و epoll", hiddenInSingle = true }
+++

این را روی یک مک نوشتم، جایی که معادل کار {{< term "kqueue" "kqueue" >}} است؛ خود epoll اینجا اجرا نشد. این هشتمین پست سری Linux است، بعد از [حافظه، page cache و OOM killer](/fa/posts/linux-memory-page-cache-oom/). پرسش: یک thread چطور هزاران اتصال را سرویس می‌دهد؟ واقعیت‌های epoll از man pageها (epoll(7) و select(2)) است؛ هر چیزی که «اجرا شد» دارد روی macOS با Go و Python و فقط روی loopback اجرا شده است.

## blocking و non-blocking

پیش‌فرض این است که `read` روی یک {{< term "socket" "socket" >}} {{< term "thread" "thread" >}} را تا رسیدن داده بلاک می‌کند. ساده است، ولی هر کلاینت کند یک thread خرج دارد. با `O_NONBLOCK` (fcntl(2)) فراخوانی‌ها وقتی کاری نیست فوراً با `EAGAIN` برمی‌گردند. {{< term "non-blocking-io" "I/O غیرمسدودکننده" >}} به‌تنهایی شما را به حلقه‌ی busy-wait می‌اندازد؛ چیزی لازم است که بگوید کِی تلاش کنید.

## select و poll و epoll

طبق select(2)، `select` روی bitmap کار می‌کند که با `FD_SETSIZE` (۱۰۲۴) محدود است و هر بار کل مجموعه را می‌دهید. `poll` این سقف را برمی‌دارد ولی هر بار آرایه‌ی همه‌ی descriptorها را می‌دهید و کرنل پیمایشش می‌کند. این همان مسئله‌ی «C10K» است: ده هزار اتصال این هزینه را دیدنی کرد.

epoll(7) کار را تقسیم می‌کند. یک interest list با `epoll_ctl` یک بار ساخته می‌شود و `epoll_wait` از ready list برمی‌گرداند که کرنل با رخ دادن رویدادها پر می‌کند. پس هزینه به تعداد {{< term "file-descriptor" "descriptorهای" >}} آماده بستگی دارد، نه ثبت‌شده. بنچمارکش نکردم.

| API | ورودی هر فراخوانی | سقف |
|---|---|---|
| `select` | bitmap همه‌ی fdها | `FD_SETSIZE` |
| `poll` | آرایه‌ی همه‌ی fdها | طبق طراحی ندارد |
| {{< term "epoll" "epoll" >}} | بعد از ثبت هیچ | حافظه |

## level یا edge

{{< term "edge-level-triggered" "Level-triggered" >}} تا وقتی داده‌ی نخوانده هست در هر انتظار descriptor را آماده می‌گوید. Edge-triggered فقط یک بار به ازای هر تغییر می‌گوید؛ epoll(7) می‌گوید باید تا `EAGAIN` بخوانید. kqueue همین ایده را دارد: طبق `man kqueue` پرچم `EV_CLEAR` بعد از دریافت وضعیت را ریست می‌کند. روی یک socketpair یونیکسی اجرا کردم: ۱۰ بایت نوشتم، سه بار `kevent` بدون خواندن، ۴ بایت خواندم، و یک بایت دیگر نوشتم:

```
level-like (EV_ADD): poll1=1 poll2=1 poll3=1 | after partial read: 1 | after new write: 1
edge-like  (EV_ADD|EV_CLEAR): poll1=1 poll2=0 poll3=0 | after partial read: 0 | after new write: 1
```

با پیش‌فرض داده‌ی نخوانده مدام گزارش می‌شود، حتی بعد از خواندن ناقص. با `EV_CLEAR` یک رویداد گرفتم و بعد سکوت تا رسیدن داده‌ی تازه. اگر descriptor edge-triggered را تخلیه نکنید گیر می‌کند.

## حلقه‌ی رویدادی که اجرا شد

دموی Go یک echo server تک‌threaded است: یک listening socket و socketهای پذیرفته‌شده، همه non-blocking و همه در یک kqueue. سه کلاینت وصل می‌شوند، یک خط می‌فرستند و پسش می‌گیرند. خروجی (فقط شمارش):

```
accepts=3 reads=3 eofs=3 goroutines_in_server_loop=1
```

همین شکل در Python با `selectors.DefaultSelector`:

```
KqueueSelector
accepts=3 reads=3
```

روی macOS پیش‌فرض `KqueueSelector` است. طبق مستندات بهترین پیاده‌سازی موجود را انتخاب می‌کند، پس انتظار دارم روی Linux `EpollSelector` باشد؛ آن را ندیدم.

## thread، goroutine و netpoller

۱۰۰۰ اتصال بیکار loopback را دو جور باز کردم و شمردم: یک goroutine برای هر اتصال (پکیج `net`) و یک حلقه‌ی kqueue:

```
goroutines connections=1000 goroutines=1002 os_threads_created=7
kqueue     connections=1000 goroutines=1 os_threads_created=5
```

۱۰۰۲ goroutine ولی فقط دو thread سیستم‌عامل بیشتر، چون runtime در Go goroutine را روی انتظار شبکه می‌خواباند و با API پلتفرم poll می‌کند. در سورس Go فایل `runtime/netpoll_epoll.go` برچسب `//go:build linux` دارد و `netpoll_kqueue.go` darwin و BSDها را پوشش می‌دهد (با `ls` و `head` دیدم). این‌طور [زمان‌بند Go](/fa/posts/go-scheduler-gc-internals/) کد سبک blocking را روی یک event loop می‌دهد. {{< term "libuv" "libuv" >}} برای Node همین کار را می‌کند، طبق مستنداتش با epoll روی Linux و kqueue روی macOS؛ [event loop در Node.js](/fa/posts/node-event-loop/) را ببینید. این‌ها شمارش‌اند نه زمان؛ ماشین مشغول بود.

## epoll در کد، هرگز اجرا نشد

نسخه‌ی epoll را با پکیج `syscall` پشت `//go:build linux` نوشتم: `EpollCreate1`، `EpollCtl`، `EpollWait` و `Accept4`. فقط با `GOOS=linux GOARCH=arm64 go vet . && go build` بررسی شد و **هرگز اجرا نشد**.

## چند منتظر

اگر چند پروسه روی یک listening socket منتظر باشند، یک اتصال ممکن است همه را بیدار کند و فقط یکی ببرد: {{< term "thundering-herd" "thundering herd" >}}. صفحه‌ی epoll(7) برای این `EPOLLEXCLUSIVE` و برای غیرفعال کردن descriptor بعد از یک رویداد `EPOLLONESHOT` را نام می‌برد؛ هیچ‌کدام را آزمایش نکردم.

## چند نکته‌ی مهم

- نتیجه‌ی Linux نیست: همه‌ی خروجی‌ها kqueue است.
- API آمادگی می‌گوید تلاش کنید، نه اینکه موفق می‌شود؛ `EAGAIN` را مدیریت کنید.
- Edge-triggered به descriptor غیرمسدودکننده و تخلیه تا `EAGAIN` نیاز دارد.
- یک handler کند کل حلقه را بلاک می‌کند.

## تمرین

روی یک ماشین Linux قابل‌دورریختن، دموی kqueue را به `epoll` ببرید و با ۳ کلاینت `strace -c` بزنید (من اجرا نکردم).

## قدم بعدی

پست بعدی «شبکه در Linux: ip، ss و nftables» است.
