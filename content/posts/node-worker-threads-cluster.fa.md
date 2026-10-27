+++
date = '2027-03-28T10:00:00+03:30'
draft = false
title = 'worker thread و cluster در Node.js'
description = 'worker thread و cluster در Node.js: بلاک‌کردن event loop از عمد و رفعش با worker، Atomics، pool و cluster، همه با اجرای واقعی و خروجی عددی.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "worker-threads", "cluster", "concurrency", "performance"]
cover = { image = "/images/covers/node-worker-threads-cluster.fa.png", alt = "worker thread و cluster در Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [اعتبارسنجی ورودی با Zod](/fa/posts/node-validation-zod/)، همه‌چیز روی یک thread اجرا می‌شد. برای I/O مشکلی نیست، همان‌طور که در [event loop در Node.js](/fa/posts/node-event-loop/) دیدیم، اما یک تابع همگامِ کند جلوی همه‌ی درخواست‌ها را می‌گیرد. این مقاله این مشکل را عمداً نشان می‌دهد، با **{{< term "worker-threads" "worker thread" >}}** حلش می‌کند و در پایان یک سرور HTTP را با **{{< term "node-cluster" "cluster" >}}** روی چند process پخش می‌کند. ادامه‌ی [سرور HTTP با node:http](/fa/posts/node-http-server/) است.

> Node نسخه‌ی v20.13.1، اسکریپت‌های محلی روی 127.0.0.1. ماشین مشغول بود، پس فقط تعداد می‌دهم، نه زمان. این‌ها را روی Linux و Windows اجرا نکردم.

## event loop بلاک‌شده

یک `setInterval` با فاصله‌ی ۱۰ میلی‌ثانیه شمارنده را زیاد می‌کند. تابع `fib(38)` (یک تابع بازگشتیِ عمداً کند) را اجرا می‌کنم و tickهای حین کار را می‌شمارم:

```text
block:  fib(38) = 39088169 | ticks counted during the job: 0 (the timer could not run)
worker: fib(38) = 39088169 | ticks counted during the job: 52 (>0 means main stayed responsive)
```

در اجرای اول timer در تمام مدتِ کار گرسنه ماند. در دومی همان تابع در یک worker اجرا شد و thread اصلی tick زدن را ادامه داد. تعداد tick به بار ماشین بستگی دارد؛ نکته ۰ در برابر غیر ۰ است.

```js
const w = new Worker(new URL('./fibworker.mjs', import.meta.url), { workerData: { n: 38 } });
w.on('message', (r) => console.log(r));
// fibworker.mjs: parentPort.postMessage(fib(workerData.n))
```

`workerData` هنگام شروع به worker کپی می‌شود و نتیجه با `postMessage` برمی‌گردد.

## کپی و انتقال

`postMessage` به‌طور پیش‌فرض کپی می‌کند. با `transferList` یک `ArrayBuffer` به‌جای کپی، منتقل می‌شود:

```text
before transfer: byteLength = 1024
after transfer:  byteLength = 0
worker got byteLength 1024 first byte 42
```

buffer فرستنده خالی (detached) شد. bufferی که بدون این فهرست فرستادم `byteLength` برابر ۸ را نگه داشت، چون کپی شده بود. انتقال برای bufferهای بزرگ سریع است، اما بعدش نباید به آن دست بزنید.

## حافظه‌ی مشترک با Atomics

یک **{{< term "shared-array-buffer" "SharedArrayBuffer" >}}** بدون کپی برای همه‌ی threadها دیده می‌شود. چهار worker هرکدام صد هزار بار به دو شمارنده در یک `Int32Array` مشترک یک واحد اضافه می‌کنند: یکی با `Atomics.add` و یکی با `v[1]++` ساده:

```text
expected      : 400000
Atomics.add   : 400000
plain v[1]++  : 195040 | lost updates: 204960
```

اجرای دوم برای شمارنده‌ی ساده `154693` داد. شمارنده‌ی atomic هر بار دقیق است؛ شمارنده‌ی ساده به‌روزرسانی گم می‌کند، چون خواندن، جمع و نوشتن مرحله‌های جدا هستند و دو thread روی هم می‌نویسند. این یک **{{< term "race-condition" "race condition" >}}** است، همان خانواده‌ی باگ در [sync، select و context در Go](/fa/posts/go-sync-select-context/). توابع `Atomics` هر مرحله را تقسیم‌ناپذیر می‌کنند.

## یک pool کوچک

ساختن worker برای هر کار هدررفت است، پس یک **{{< term "worker-pool" "pool" >}}** نوشتم: صف کار، فهرست workerهای بیکار و یک promise برای هر کار. دو worker و شش ورودی ثابت:

```text
fib(30) = 832040  (done by worker#1)
fib(31) = 1346269  (done by worker#2)
fib(32) = 2178309  (done by worker#1)
...
fib(35) = 9227465  (done by worker#2)
results are in input order: true
```

نتایج به ترتیب‌اند چون همه‌ی promiseها را به ترتیب ورودی `await` می‌کنم، نه چون workerها به ترتیب تمام می‌کنند. اینکه کدام worker کدام کار را بگیرد ممکن است بین اجراها فرق کند.

## خطا و خروج

```text
throw -> error event: boom in worker
throw -> exit event, code 1
exit3 -> exit event, code 3
ok -> exit event, code 0
```

خطای گرفته‌نشده در worker رویداد `error` را در parent و بعد `exit` را فعال می‌کند؛ `process.exit(3)` در worker فقط `exit` با همان کد می‌دهد. همیشه به هر دو گوش دهید و در pool کارِ جاری را روی `error` رد کنید. pool ساده‌ی من این را می‌کند، اما worker مرده را دوباره نمی‌سازد؛ pool واقعی باید بسازد.

## cluster: یک port، چند process

worker thread برای کار CPU است. برای استفاده از هسته‌های بیشتر در سرور HTTP، `cluster` چند process فرزند می‌سازد که یک port را به اشتراک می‌گذارند. دو worker، ۴۰ درخواست، و پاسخ هر درخواست `process.pid` همان worker (pidهای واقعی را با نام عوض کردم):

```text
40 requests, distinct responders: 2 -> worker#1: 20, worker#2: 20
```

تقسیم ۲۰/۲۰ با مستندات می‌خواند: روی Linux و macOS، primary اتصال‌ها را round-robin پخش می‌کند. هدر `connection: close` فرستادم تا هر درخواست اتصال تازه باشد.

بعد یک worker را با `SIGKILL` کشتم. رویداد `exit` در primary آمد و خودم یکی تازه fork کردم. cluster خودکار worker را بازسازی نمی‌کند:

```text
worker#1 exited (signal SIGKILL)
alive workers now: 2 | killed was worker#1
40 requests after restart, distinct responders: 2 -> worker#2: 20, worker#3: 20
```

(خروجی را با حذف چند کلمه‌ی انتهای یک خط کوتاه کردم.)

## کدام را انتخاب کنیم

- کار CPU داخل یک process: worker thread.
- سرو HTTP روی همه‌ی هسته‌ها: cluster، یا process manager یا orchestratorی که چند نسخه اجرا کند.
- عمدتاً I/O (دیتابیس، شبکه): هیچ‌کدام؛ event loop خودش از پسش برمی‌آید.

## مقایسه با Go

در Go یک **{{< term "goroutine" "goroutine" >}}** را runtime روی هسته‌ها زمان‌بندی می‌کند، پس کار CPU API اضافه نمی‌خواهد ([goroutine و channel در Go](/fa/posts/go-goroutines-channels/)، [scheduler و garbage collector در Go](/fa/posts/go-scheduler-gc-internals/)). در Node خودتان thread یا process را انتخاب می‌کنید و هر worker heap جدا دارد.

## چند نکته‌ی مهم

- هر worker event loop و حافظه‌ی خودش را دارد؛ فقط bufferهای مشترک مشترک‌اند.
- از تعداد هسته‌ها بیشتر worker CPU-bound نسازید.
- همیشه `error` و `exit` را مدیریت کنید.
- به‌روزرسانی ساده‌ی عدد صحیح در حافظه‌ی مشترک ایمن نیست؛ از `Atomics` استفاده کنید.
- workerهای cluster چیزی در حافظه به اشتراک نمی‌گذارند: session و cache را بیرون نگه دارید.

## تمرین

pool را طوری بسازید که بعد از `error` یک worker جدید بسازد، و با کاری که روی ورودی مشخصی پرتاب می‌کند آزمایشش کنید.

## قدم بعدی

مقاله‌ی بعدی «پروفایل، حافظه و خاموشی تمیز در Node.js» است.
