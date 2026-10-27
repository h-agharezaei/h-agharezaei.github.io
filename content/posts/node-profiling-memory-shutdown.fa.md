+++
date = '2027-04-05T10:00:00+03:30'
draft = false
title = 'پروفایل، حافظه و خاموشی تمیز در Node.js'
description = 'پروفایل Node.js: --cpu-prof، heap snapshot، نشت حافظه و OOM واقعی، تأخیر event loop و خاموشی تمیز سرور HTTP با SIGTERM، همه با اجرای واقعی.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "profiling", "memory", "heap-snapshot", "graceful-shutdown"]
cover = { image = "/images/covers/node-profiling-memory-shutdown.fa.png", alt = "پروفایل، حافظه و خاموشی تمیز در Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [worker thread و cluster در Node.js](/fa/posts/node-worker-threads-cluster/)، کار را روی چند thread و پروسه پخش کردیم. قبل از اینکه بیشترش کنید، باید بدانید زمان و حافظه واقعاً کجا می‌رود و پروسه می‌تواند بدون از دست دادن درخواست‌ها متوقف شود. این همان داستان [پروفایل Go با pprof](/fa/posts/go-profiling-pprof/) و [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) است، با زبان Node.js و روی [event loop](/fa/posts/node-event-loop/) و [سرور HTTP](/fa/posts/node-http-server/).

> Node نسخه‌ی v20.13.1. اسکریپت‌ها مثال محلی‌اند و خروجی‌ها واقعی. ماشین شلوغ بود، پس تعداد و اندازه می‌آورم نه زمان. heap snapshotها و پروفایل‌ها بعداً پاک شدند. DevTools و `--inspect` را نشان نمی‌دهم و اجرا نکردم.

## CPU کجا می‌رود

`node --cpu-prof script.js` یک **{{< term "cpu-profile" "پروفایل CPU" >}}** در فایل JSON با پسوند `.cpuprofile` می‌نویسد. Chrome DevTools آن را به‌شکل flame graph باز می‌کند؛ من به‌جایش با یک اسکریپت کوتاه خواندمش. برنامه‌ی پروفایل‌شده عمداً CPU-سنگین است: `fib(34)` بازگشتی و ۳۰۰۰۰۰ بار `JSON.stringify`. اسکریپت نمونه‌ها را به‌ازای بالاترین فریم می‌شمارد:

```text
total samples 145
    70 render cpu.js:2
    50 fib cpu.js:1
    12 (garbage collector) :0
     2 compileForInternalLoader realm:383
```

نکته رتبه‌بندی است (`render`، بعد `fib`، بعد **{{< term "garbage-collector" "garbage collector" >}}**)؛ عددها از اجرایی به اجرای دیگر فرق می‌کنند. اول پروفایل بگیرید، بعد فقط خط اول را بهینه کنید.

## نشتی که می‌شود دید

سرور زیر یک `Map` در سطح module نگه می‌دارد و در حالت leak برای هر درخواست یک ورودی اضافه می‌کند و هیچ‌وقت پاک نمی‌کند. ۵۰۰۰۰ درخواست روی اتصال‌های keep-alive فرستادم و پیش از خواندن `process.memoryUsage().heapUsed` تابع `global.gc()` را صدا زدم (نیاز به `--expose-gc` دارد):

```text
ok before: 3 MB, cache 0
ok after 50000 requests: 4 MB, cache 0
leak before: 3 MB, cache 0
leak after 50000 requests: 31 MB, cache 50000
```

حتی بعد از GC کامل، اجرای نشت‌دار ۳۱ مگابایت نگه داشته است: **{{< term "memory-leak" "نشت حافظه" >}}** یعنی حافظه‌ای که هنوز قابل دسترسی است. بعد `v8.writeHeapSnapshot()` یک **{{< term "heap-snapshot" "heap snapshot" >}}** نوشت (حدود ۵۹ مگابایت روی دیسک). DevTools می‌تواند بازش کند؛ من JSON را خواندم:

```text
nodes 854741 edges 2455453 self size MB 31
  18.3 MB concatenated string
   4.6 MB string
   2.5 MB array
   2.1 MB code
```

stringها غالب‌اند و این به ورودی‌های cache اشاره می‌کند. در سرویس واقعی می‌توانید پروسه را با `--heapsnapshot-signal=SIGUSR2` بالا بیاورید تا هر وقت خواستید snapshot بدهد؛ این گزینه را اجرا نکردم.

## سقف حافظه و لاگ GC

با `--max-old-space-size=20` و حلقه‌ای که مدام allocate می‌کند، پروسه می‌میرد:

```text
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
exit 134
```

exit code اینجا ۱۳۴ بود. `--trace-gc` برای هر جمع‌آوری یک خط چاپ می‌کند؛ اولین خط‌های یک اسکریپت کوچک و اسکریپت محکوم:

```text
Scavenge 3.7 (4.0) -> 3.5 (5.0) MB
Mark-Compact 18.8 (50.3) -> 18.0 (51.0) MB
```

scavenge objectهای جوان را پاک می‌کند؛ mark-compact تقریباً چیزی کم نکرد چون همه‌چیز هنوز قابل دسترسی بود.

## تأخیر event loop

`perf_hooks.monitorEventLoopDelay` می‌سنجد timerها چقدر دیر اجرا می‌شوند. event loop را با یک `while` مشغول به مدت ۲۰۰ میلی‌ثانیه بستم:

```text
samples > 0: true
max delay >= 150 ms: true  | median < 50 ms: true
```

به‌خاطر بار بالا به‌جای میلی‌ثانیه، boolean چاپ کردم. یک فراخوانی مسدودکننده در max به‌شکل عدد بزرگ دیده می‌شود ولی median کوچک می‌ماند؛ پس max و یک percentile بالا را زیر نظر بگیرید.

## خاموش کردن سرور HTTP

با **{{< term "sigterm" "SIGTERM" >}}**، `server.close()` پذیرش اتصال تازه را می‌بندد و وقتی همه‌ی اتصال‌ها تمام شدند callback را صدا می‌زند. روی 20.13.1 هم `closeIdleConnections` و هم `closeAllConnections` وجود دارند (اسکریپت برای هر دو `function` چاپ کرد). یک درخواست یک‌ثانیه‌ای به سرور فرستادم، از کلاینتی با اتصال **{{< term "keep-alive" "keep-alive" >}}**:

```text
SIGTERM: server.close()
timeout: closeAllConnections()
close callback, err = null
client: in-flight -> slow done
```

درخواست در حال اجرا تمام شد، اما سوکت keep-alive آن بعدش باز ماند و callback تا timeout سخت ۳ ثانیه‌ای من منتظر شد. اتصال گرم‌کردنی که هنگام SIGTERM بی‌کار بود مشکلی نساخت: در این نسخه `close()` خودش آن را بست و پروسه فوراً تمام شد. صدا زدن `closeIdleConnections()` هر ۱۰۰ میلی‌ثانیه بعد از `close()` انتظار را برطرف کرد: پروسه درست بعد از پاسخ خارج شد، timeout هرگز اجرا نشد و exit code برابر ۰ بود. کلاینتی که نصف درخواست را فرستاد و ساکت شد فقط با `closeAllConnections()` در timeout حذف شد.

این دستور پخت **{{< term "graceful-shutdown" "خاموشی تمیز" >}}** است: پذیرش را ببند، بگذار کارهای در حال اجرا تمام شوند، سوکت‌های بی‌کار را ببند و یک timeout سخت نگه دار تا کلاینت گیرکرده جلوی deploy را نگیرد. در Go تابع `http.Server.Shutdown` سه کار اول را برایتان انجام می‌دهد و deadline در `context` نقش timeout را دارد.

## چند نکته‌ی مهم

- زیر بار واقع‌گرایانه پروفایل بگیرید و هر بار فقط یک چیز را عوض کنید.
- heap را بعد از GC اجباری بخوانید؛ پیش از آن زباله را اندازه می‌گیرید.
- هر cache را محدود کنید (اندازه یا TTL)، وگرنه نشت می‌شود.
- heap snapshot ممکن است به بزرگی heap باشد و راز داشته باشد: پاکش کنید.
- `process.exit()` داخل handler سیگنال مسیر تمیز را دور می‌زند؛ وقتی callback مربوط به `close` رسید خارج شوید.

## تمرین

به سروری که در مقاله‌ی HTTP ساختید `/leak` اضافه کنید، با یک اسکریپت بارش بدهید، دو heap snapshot بگیرید و اندازه‌ی stringها را مقایسه کنید. بعد به cache سقف بدهید و تکرار کنید.

## قدم بعدی

مقاله‌ی بعدی «Node.js یا Go؟ هرکدام برای چه کاری» است، آخرین مقاله‌ی سری Node.js.
