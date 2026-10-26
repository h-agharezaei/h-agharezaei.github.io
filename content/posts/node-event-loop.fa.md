+++
date = '2026-11-11T10:00:00+03:30'
draft = false
title = 'event loop در Node.js'
description = 'event loop در Node.js با اجرای واقعی: فازها، ترتیب nextTick و promise و timer، بلاک شدن loop، گرسنگی microtask و thread pool کتابخانه‌ی libuv.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "event-loop", "javascript", "async", "libuv"]
cover = { image = "/images/covers/node-event-loop.fa.png", alt = "event loop در Node.js", hiddenInSingle = true }
+++

این مقاله اولین مقاله‌ی سری Node.js است. اگر در پروداکشن Node.js می‌نویسید، مفیدترین مدل ذهنی همین **{{< term "event-loop" "event loop" >}}** است: کد JavaScript شما روی یک thread اجرا می‌شود و هرچیزی که منتظر می‌ماند (timer، socket، فایل) به سیستم سپرده می‌شود و به شکل callback برمی‌گردد. اگر از Go می‌آیید، آن را با [goroutine و channel](/fa/posts/go-goroutines-channels/) و [زمان‌بند runtime در Go](/fa/posts/go-scheduler-gc-internals/) مقایسه کنید: آنجا runtime کد شما را روی چند thread پخش می‌کند، اینجا JavaScript شما موازی اجرا نمی‌شود.

> همه‌ی کدهای زیر با Node نسخه‌ی v20.13.1 اجرا شده‌اند. اسکریپت‌ها مثال‌های محلی هستند و خروجی‌ها از اجرای واقعی کپی شده‌اند.

## فازها، به زبان ساده

هر دور از loop (که **{{< term "libuv" "libuv" >}}** پیاده‌اش می‌کند) از این فازها می‌گذرد:

1. **timers**: callbackهای `setTimeout` و `setInterval` که موعدشان رسیده.
2. **pending callbacks**: چند callback سیستمیِ به‌تأخیر‌افتاده.
3. **poll**: منتظر I/O (socket، فایل) می‌ماند و callbackهایش را اجرا می‌کند.
4. **check**: callbackهای `setImmediate`.
5. **close**: callbackهای `close`، مثلاً بسته شدن یک socket.

بین callbackها، Node اول صف `process.nextTick` و بعد صف **{{< term "microtask" "microtask" >}}**‌های promise را خالی می‌کند.

## چه چیزی زودتر اجرا می‌شود؟

```js
const fs = require('fs');
console.log('1 sync start');
setTimeout(() => console.log('6 setTimeout 0'), 0);
setImmediate(() => console.log('7 setImmediate'));
fs.readFile(__filename, () => console.log('8 readFile callback'));
process.nextTick(() => console.log('3 nextTick'));
Promise.resolve().then(() => console.log('4 promise then'));
queueMicrotask(() => console.log('5 queueMicrotask'));
console.log('2 sync end');
```

خروجی:

```text
1 sync start
2 sync end
3 nextTick
4 promise then
5 queueMicrotask
6 setTimeout 0
7 setImmediate
8 readFile callback
```

اول کد همگام (sync)، بعد `nextTick`، بعد microtaskها و بعد فازهای loop. ترتیب ۶ و ۷ و ۸ همان چیزی است که در این اجرا دیدم، و همان‌طور که بخش بعد نشان می‌دهد ترتیب timeout و immediate در سطح بالای اسکریپت تضمین‌شده نیست.

## setTimeout(0) در برابر setImmediate

در سطح بالای اسکریپت، ترتیب به این بستگی دارد که process با چه سرعتی به loop می‌رسد. این کد را ۱۲ بار اجرا کردم:

```js
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
```

نتیجه: ۱۰ بار `immediate timeout` و ۲ بار `timeout immediate`. به هیچ‌کدام تکیه نکنید. داخل یک callback مربوط به I/O ترتیب ثابت است، چون بعد از poll نوبت check است:

```js
fs.readFile(__filename, () => {
  setTimeout(() => console.log('timeout'), 0);
  setImmediate(() => console.log('immediate'));
});
```

در ۶ اجرا از ۶: `immediate timeout`.

## بلاک کردن loop

```js
const t0 = Date.now();
setTimeout(() => console.log('timer callback ran, after the loop finished:', done), 10);
let done = false;
console.log('busy loop starts');
while (Date.now() - t0 < 200) {}
done = true;
console.log('busy loop ends');
```

```text
busy loop starts
busy loop ends
timer callback ran, after the loop finished: true
```

یک timer ده‌میلی‌ثانیه‌ای منتظر یک حلقه‌ی همگام ۲۰۰ میلی‌ثانیه‌ای ماند. در یک سرور یعنی بقیه‌ی درخواست‌ها منتظرند. عدد تأخیر نمی‌آورم، چون هنگام تست ماشین مشغول بود.

## گرسنگی microtask

microtaskها پیش از رفتن loop به مرحله‌ی بعد کامل خالی می‌شوند، پس زنجیره‌ای از microtask می‌تواند timerها را بلاک کند. با شمارنده‌ی محدود:

```js
let n = 0;
setTimeout(() => console.log('timer ran, microtasks so far:', n), 0);
function spin() { if (++n < 100000) queueMicrotask(spin); }
spin();
```

```text
timer ran, microtasks so far: 100000
```

timer فقط بعد از هر ۱۰۰۰۰۰ microtask اجرا شد. در نسخه‌ی نامحدود، timer هیچ‌وقت اجرا نمی‌شد.

## thread pool کتابخانه‌ی libuv

همه‌چیز تک‌threaded نیست: بعضی کارها (`crypto.pbkdf2`، خیلی از فراخوانی‌های `fs`، و `dns.lookup`) به یک **{{< term "thread-pool" "thread pool" >}}** می‌روند که طبق مستندات Node اندازه‌ی پیش‌فرضش ۴ است (`UV_THREADPOOL_SIZE`). ۸ کار `pbkdf2` را شروع کردم و زمان پایان هرکدام را بر زمان اولین تقسیم کردم:

```text
default (4):        1.0 1.0 1.0 1.0 2.1 2.1 2.1 2.1
UV_THREADPOOL_SIZE=8: 1.0 1.1 1.1 1.1 1.1 1.1 1.1 1.1
UV_THREADPOOL_SIZE=1: 1.0 2.0 3.2 4.3 5.6 6.5 7.5 8.5
```

با ۴ thread، کارها در دو دسته‌ی چهارتایی تمام می‌شوند. با ۸ یک دسته است و با ۱ یکی‌یکی اجرا می‌شوند. نسبت‌ها تقریبی‌اند و به ماشین بستگی دارند.

## اندازه‌گیری lag

`perf_hooks.monitorEventLoopDelay` اندازه می‌گیرد loop چقدر دیر بیدار می‌شود. آن را ۳۰۰ میلی‌ثانیه بلاک کردم و histogram را بررسی کردم:

```text
max lag > 250ms: true
min lag < 100ms: true
```

مقدار مطلق به ماشین بستگی دارد، برای همین فقط مقایسه را نشان دادم. در پروداکشن p99 این histogram را به‌عنوان متریک export کنید.

## چند نکته‌ی مهم

- کار سنگین همگام (parse کردن JSON بزرگ، فراخوانی‌های `*Sync` از `fs`، حلقه‌های CPU) را داخل handler درخواست اجرا نکنید.
- `process.nextTick` و microtaskهای بازگشتی می‌توانند I/O و timerها را گرسنه نگه دارند.
- در سطح بالای اسکریپت به ترتیب `setTimeout(0)` و `setImmediate` تکیه نکنید.
- thread pool بین `fs`، `crypto` و DNS مشترک است و کارهای کند می‌توانند هم را عقب بیندازند. کار CPU جایش worker thread است.

## تمرین

اسکریپتی بنویسید با یک `setInterval` پنجاه‌میلی‌ثانیه‌ای و یک حلقه‌ی همگام ۳۰۰ میلی‌ثانیه‌ای که بعد از ۱۲۰ میلی‌ثانیه شروع می‌شود. پیش‌بینی کنید چند tick چاپ می‌شود، اجرا کنید و با `monitorEventLoopDelay` آن وقفه را تأیید کنید.

## قدم بعدی

مقاله‌ی بعدی «ماژول‌ها: ESM و CommonJS» است.
