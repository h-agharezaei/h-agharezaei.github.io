+++
date = '2026-12-11T10:00:00+03:30'
draft = false
title = 'خطا و unhandled rejection در Node.js'
description = 'مدیریت خطا در Node.js با اجرای واقعی: Error و زنجیره‌ی cause، محدودیت try/catch، خطای EventEmitter، حالت‌های unhandled rejection و handler خطای مرگبار.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "errors", "unhandled-rejection", "javascript", "error-handling"]
cover = { image = "/images/covers/node-errors-unhandled-rejections.fa.png", alt = "خطا و unhandled rejection در Node.js", hiddenInSingle = true }
+++

مقاله‌ی قبل، [Promise و async/await در Node.js](/fa/posts/node-promises-async-await/)، با یک rejection که کسی handle نکرده بود تمام شد. اینجا خطا را درست بررسی می‌کنیم: خطا چیست، `try/catch` کجا از کار می‌افتد و Node با شکست‌های دست‌نخورده چه می‌کند. این مقاله روی [event loop](/fa/posts/node-event-loop/) بنا شده است. اگر از Go می‌آیید، [خطا به‌عنوان مقدار](/fa/posts/go-functions-defer-errors/) مدل دیگری است که آخر مقاله مقایسه می‌شود.

> همه‌چیز با Node نسخه‌ی v20.13.1 اجرا شده است. اسکریپت‌ها مثال‌های محلی هستند؛ خروجی‌ها از اجرای واقعی کپی شده‌اند و مسیر فایل‌ها و stackهای طولانی کوتاه شده‌اند.

## شیء Error و زنجیره‌ی cause

یک `Error` سه چیز دارد: `name`، `message` و `stack`. جاوااسکریپت اجازه می‌دهد هر چیزی را `throw` کنید، اما رشته‌ی throw شده stack ندارد:

```js
try { throw 'just a string'; } catch (x) { console.log(typeof x, x.stack); }
```

```text
string undefined
```

پس همیشه شیء `Error` بیندازید. یک کلاس سفارشی می‌تواند `code` داشته باشد و `new Error(msg, { cause })` خطای اصلی را نگه می‌دارد:

```js
class AppError extends Error {
  constructor(message, { code, status, cause } = {}) {
    super(message, { cause });
    this.name = 'AppError';
    this.code = code;
    this.status = status;
  }
}
```

دو بار wrap کردن خطای `JSON.parse` و پیمایش `err.cause`:

```text
AppError [E_START]: cannot start
  AppError [E_CONFIG]: bad config
    SyntaxError [-]: Expected property name or '}' in JSON at position 1
```

## جایی که try/catch نمی‌رسد

`try/catch` فقط کدی را می‌بیند که همزمان داخلش اجرا شود یا بعد از یک `await` بیاید:

```js
try { setTimeout(() => { throw new Error('thrown in a timer'); }, 10); }
catch (e) { console.log('never printed'); }
```

callback تایمر بعداً و از event loop اجرا می‌شود، وقتی `try` خیلی وقت است تمام شده. process با `Error: thrown in a timer`، بعد `Node.js v20.13.1` و exit code برابر 1 crash کرد. دور `await` کار می‌کند و APIهای callback قرارداد error-first دارند:

```text
caught around await: rejected promise
error-first: ENOENT undefined
```

(`fs.readFile` روی فایل ناموجود: `err` مقدار دارد و `data` برابر `undefined` است.) همیشه اول `err` را چک کنید.

## EventEmitter: خطای بدون listener

خیلی از اشیای Node از نوع **{{< term "event-emitter" "EventEmitter" >}}** هستند. emit کردن `'error'` بدون listener، throw می‌کند:

```js
em.on('data', (x) => console.log('data', x));
em.emit('data', 1);
em.emit('error', new Error('no listener for me'));
```

```text
data 1
node:events:497
      throw er; // Unhandled 'error' event
Error: no listener for me
Emitted 'error' event at: ...
Node.js v20.13.1
```

exit code برابر 1. با `em.on('error', ...)` همان emit چاپ کرد `handled: with a listener` و برنامه ادامه داد (exit 0). سرور و stream هم emitter هستند، پس برایشان listener برای `'error'` بگذارید.

## Unhandled rejection و حالت‌ها

در Node 20 یک promise ردشده‌ی بدون handler خطا و stack را چاپ می‌کند، بعد `Node.js v20.13.1` و با کد 1 خارج می‌شود، پیش از آنکه تایمر 100 میلی‌ثانیه‌ای اجرا شود. فلگ `--unhandled-rejections` این را تغییر می‌دهد. همان اسکریپت در هر حالت:

| حالت | رفتار | exit code |
|---|---|---|
| پیش‌فرض | خطا را چاپ می‌کند و خارج می‌شود | 1 |
| `strict` | آن را uncaught exception می‌کند | 1 |
| `throw` | throw می‌کند، مگر handler وجود داشته باشد | 1 |
| `warn` | `UnhandledPromiseRejectionWarning` چاپ می‌کند و ادامه می‌دهد | 0 |
| `none` | بی‌صدا ادامه می‌دهد (`timer fired`) | 0 |

`warn` و `none` باگ واقعی را پنهان می‌کنند؛ پیش‌فرض را نگه دارید.

`Promise.any` هم مرتبط است: وقتی همه‌ی ورودی‌ها fail شوند با یک **{{< term "aggregate-error" "AggregateError" >}}** که همه‌ی دلیل‌ها را دارد reject می‌شود:

```text
AggregateError true All promises were rejected
[ 'x', 'y' ]
```

## handlerها برای لاگ و خروج‌اند

می‌توانید به چیزی که کسی نگرفته گوش بدهید:

```js
process.on('unhandledRejection', (reason) => console.log('unhandledRejection:', reason.message));
process.on('uncaughtException', (err, origin) => console.log('uncaughtException:', err.message, origin));
Promise.reject(new Error('r1'));
setTimeout(() => { throw new Error('t1'); }, 10);
setTimeout(() => console.log('carried on (this is the danger)'), 50);
```

```text
unhandledRejection: r1
uncaughtException: t1 uncaughtException
carried on (this is the danger)
```

exit code برابر 0: process زنده ماند و این همان تله است. بعد از یک خطای غیرمنتظره ممکن است state نیمه‌کاره باشد، پس این handlerها باید لاگ کنند، پذیرش کار جدید را متوقف کنند و با کد غیرصفر خارج شوند. نسخه‌ی حداقلی برای یک سرور HTTP:

```js
let shuttingDown = false;
function fatal(kind, err) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.error(`FATAL ${kind}:`, err && err.message);
  const t = setTimeout(() => process.exit(1), 5000); t.unref(); // hard deadline
  server.close(() => process.exit(1));
  server.closeAllConnections();
}
process.on('uncaughtException', (err) => fatal('uncaughtException', err));
process.on('unhandledRejection', (reason) => fatal('unhandledRejection', reason));
```

یک rejection فراموش‌شده در یک job پس‌زمینه این را چاپ کرد: `FATAL unhandledRejection: background job failed` و process سرور با کد 1 خارج شد. یک supervisor (مثل systemd یا Kubernetes) دوباره آن را بالا می‌آورد.

## یک جا برای نگاشت خطا به HTTP

تصمیم را در یک `errors.js` نگه دارید؛ معادل Node تابع `statusOf` در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/):

```js
function statusOf(err) {
  if (err instanceof AppError) return [err.status, { error: err.expose ? err.message : 'internal error', code: err.code }];
  return [500, { error: 'internal error', code: 'E_INTERNAL' }];
}
```

`expose` فقط برای statusهای کمتر از 500 درست است، پس جزئیات 5xx به کلاینت نمی‌رسد. درخواست‌های واقعی به سرور روی `127.0.0.1`:

```text
GET /          -> 422 {"error":"id is required","code":"E_VALIDATION"}
GET /?id=1     -> 200 {"user":"alice"}
GET /?id=9     -> 404 {"error":"user not found","code":"E_NOT_FOUND"}
GET /?id=boom  -> 500 {"error":"internal error","code":"E_INTERNAL"}
GET /?id=bug   -> 500 {"error":"internal error","code":"E_INTERNAL"}
```

`boom` یک **{{< term "operational-error" "خطای عملیاتی" >}}** است (یک `AppError` برای خرابی وابستگی) و `bug` یک `TypeError` از اشتباه برنامه‌نویس. هر دو از کلاینت پنهان و لاگ می‌شوند؛ تفاوتشان در نحوه‌ی برخورد در review است.

## مقایسه با Go

در Go تابع `error` را مثل یک مقدار معمولی برمی‌گرداند و `if err != nil` شما را وادار می‌کند همان‌جا رسیدگی کنید؛ `panic` برای باگ‌های استثنایی است. جاوااسکریپت throw می‌کند، پس نبودِ handler تا زمان اجرا دیده نمی‌شود. wrap کردن در هر دو هست: اینجا `cause`، آنجا `%w`.

## چند نکته‌ی مهم

- شیء `Error` (یا زیرکلاس) بیندازید، نه رشته.
- `try/catch` callback و تایمر را پوشش نمی‌دهد؛ `await` را پوشش می‌دهد.
- برای هر emitter یک listener برای `'error'` بگذارید.
- handlerهای سراسری لاگ می‌کنند و با کد غیرصفر خارج می‌شوند؛ جبران نمی‌کنند.
- نگاشت خطا به HTTP را در یک جا نگه دارید و پیام 5xx را پنهان کنید.

خطا در stream و `pipeline` در مقاله‌ی بعد می‌آید.

## تمرین

یک `TimeoutError` به `errors.js` اضافه کنید که به 504 نگاشت شود و با `curl` ثابت کنید handlerی که منتظر یک فراخوانی کند است همین را برمی‌گرداند.

## قدم بعدی

مقاله‌ی بعد «stream و backpressure در Node.js» است.
