+++
date = '2026-12-11T10:00:00+03:30'
draft = false
title = 'خطا و unhandled rejection در Node.js'
description = 'مدیریت خطا در Node.js با اجرای واقعی: Error و زنجیره‌ی cause، محدودیت try/catch، خطای EventEmitter، حالت‌های unhandled rejection و handler خطای مرگبار.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "errors", "unhandled-rejection", "javascript", "error-handling"]
cover = { image = "/images/covers/node-errors-unhandled-rejections.fa.png", alt = "خطا و unhandled rejection در Node.js", hiddenInSingle = true }
+++

یک غافلگیری: یک فراخوانی `setTimeout` را داخل `try/catch` می‌گذارید و callbackی که داخلش است خطا پرتاب می‌کند. `catch` اجرا نمی‌شود و کل process از کار می‌افتد. ایرادی در `try/catch` شما نیست؛ فقط آن‌قدر دور را نمی‌بیند. اینکه بدانید `try/catch` از کجا به بعد کار نمی‌کند و Node با شکستی که کسی نگرفته چه می‌کند، تعیین می‌کند یک باگ در یک درخواست کل سرور شما را زمین بزند یا نه.

ایده‌ی اصلی ساده است. `try/catch` فقط از کدی محافظت می‌کند که *داخل* آن و روی همان call stack اجرا می‌شود، از جمله کد بعد از یک `await`. شکستی که بعداً از یک timer یا یک رویداد می‌آید، یک call stack تازه شروع می‌کند که `try` شما دیگر در آن وجود ندارد. Node برای چنین شکست‌هایی یک قاعده لازم دارد و قاعده‌اش سخت است: اگر کسی مهارشان نکند، process متوقف می‌شود. این مقاله مرور می‌کند خطاها از کجا می‌آیند، کجا گم می‌شوند، Node چطور واکنش نشان می‌دهد و یک سرور در آخرین لحظه باید چه کند.

[Promise و async/await در Node.js](/fa/posts/node-promises-async-await/) با کشته شدن process توسط یک unhandled rejection تمام شد؛ اینجا خطاها را درست بررسی می‌کنیم، با تکیه بر [event loop](/fa/posts/node-event-loop/). اگر از Go می‌آیید، [خطا به‌عنوان مقدار](/fa/posts/go-functions-defer-errors/) مدل دیگر است که آخر مقاله مقایسه‌اش می‌کنم.

> همه‌چیز با Node نسخه‌ی v20.13.1 اجرا شده است. اسکریپت‌ها مثال‌های محلی هستند و خروجی‌ها از اجرای واقعی کپی شده‌اند، با مسیر فایل‌ها و stackهای طولانی که کوتاه شده‌اند.

## شیء Error و زنجیره‌ی cause

`Error` شیئی است با `name` و `message` و `stack`، یعنی فهرست فراخوانی‌هایی که به خطا رسیدند. JavaScript اجازه می‌دهد هر مقداری را `throw` کنید، حتی یک رشته، ولی آن‌وقت stack را از دست می‌دهید:

```js
try { throw 'just a string'; } catch (x) { console.log(typeof x, x.stack); }
```

```text
string undefined
```

رشته‌ی پرتاب‌شده `.stack` ندارد، پس وقتی در لاگ ظاهر شود نمی‌توانید بفهمید از کجا آمده. همیشه شیء `Error` پرتاب کنید.

می‌توانید `Error` را با کلاس خودتان هم گسترش دهید تا فیلدهای اضافه داشته باشد، مثل `code` برای اینکه برنامه‌ها بررسی‌اش کنند و `status` برای HTTP. و وقتی خطایی را می‌گیرید و خطای تازه‌ای پرتاب می‌کنید، اصلی را به‌عنوان `cause` بدهید تا شکست اول گم نشود:

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

دمو یک `JSON.parse` ناموفق را داخل `AppError('bad config')` می‌پیچد و آن را داخل یکی دیگر، `AppError('cannot start')`. بعد از بیرون به داخل لینک‌های `cause` را دنبال می‌کند و برای هر سطح یک خط چاپ می‌کند:

```text
AppError [E_START]: cannot start
  AppError [E_CONFIG]: bad config
    SyntaxError [-]: Expected property name or '}' in JSON at position 1
```

از بالا به پایین بخوانیدش: برنامه نتوانست شروع شود، چون تنظیمات بد بود، چون JSON نامعتبر بود. هر سطح زمینه‌ای اضافه می‌کند و هیچ‌کدام علت اصلی را گم نمی‌کند. (`[-]` یعنی خطا `code` نداشت.)

## جایی که try/catch به آن نمی‌رسد

`try/catch` کدی را می‌بیند که همگام داخلش اجرا می‌شود و کدی که بعد از `await` می‌آید (چون تابع داخل همان `try` ادامه پیدا می‌کند). کدی را که بعداً از event loop اجرا می‌شود نمی‌بیند. این دمو یک `try` دور یک timer دارد که callbackاش خطا پرتاب می‌کند:

```js
try { setTimeout(() => { throw new Error('thrown in a timer'); }, 10); }
catch (e) { console.log('never printed'); }
```

خود فراخوانی `setTimeout` همان لحظه موفق می‌شود و `try` تمام می‌شود. ده میلی‌ثانیه بعد loop callback را روی یک stack تازه و بدون هیچ `try`ای دور آن اجرا می‌کند. هیچ‌چیز خطا را نمی‌گیرد، process با `Error: thrown in a timer` و بعد `Node.js v20.13.1` از کار می‌افتد و exit code برابر ۱ است. (**exit code** عددی است که process به والدش برمی‌گرداند؛ ۰ یعنی موفقیت و هر چیز دیگر یعنی شکست.)

همین فایل دو حالتی را هم نشان می‌دهد که کار می‌کنند: `await`، و سبک قدیمی‌تر callback که خطا آرگومان اول است («error-first»):

```text
caught around await: rejected promise
error-first: ENOENT undefined
```

خط اول یک `try/catch` دور `await` یک promise ردشده است و می‌گیرد. دومی `fs.readFile` روی فایلی است که وجود ندارد: callback مقدار `err` با کد `ENOENT` را می‌گیرد و `data` برابر `undefined` است. همیشه اول `err` را بررسی کنید.

## EventEmitter: خطای بی‌شنونده

خیلی از شیءهای Node، مثل سرورها و streamها، **{{< term "event-emitter" "EventEmitter" >}}** هستند: با emit کردن رویدادهای نام‌دار چیزی را اعلام می‌کنند و شما listener وصل می‌کنید. یک اسم رویداد خاص است. اگر چیزی `'error'` را emit کند و کسی گوش ندهد، Node آن را throw می‌کند. این اسکریپت یک رویداد عادی و بعد یک `'error'` بدون listener را emit می‌کند:

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

رویداد `data` مشکلی نداشت. رویداد `error` listener نداشت، پس Node خطا را throw کرد و process از کار افتاد (exit code برابر ۱). بیشتر خط‌های stack را بریده‌ام. در اسکریپت دوم با `em.on('error', ...)` همین emit چاپ کرد `handled: with a listener`، برنامه `still running` چاپ کرد و exit code برابر ۰ بود. به هر emitterی که مال خودتان است یک listener برای `'error'` بدهید.

## unhandled rejectionها و حالت‌هایشان

نسخه‌ی promise را در مقاله‌ی قبل دیدیم. روی Node 20 یک promise ردشده بدون handler خطا و stack را چاپ می‌کند، بعد `Node.js v20.13.1` و پیش از اینکه یک timer صدمیلی‌ثانیه‌ای فرصت شلیک پیدا کند با کد ۱ خارج می‌شود. این رفتار **{{< term "unhandled-rejection" "unhandled rejection" >}}** است. پرچم `--unhandled-rejections` آن را عوض می‌کند. همان اسکریپت (یک promise ردشده به‌علاوه‌ی timerی که `timer fired` چاپ می‌کند) را در همه‌ی حالت‌ها اجرا کردم:

| حالت | رفتار | exit code |
|---|---|---|
| پیش‌فرض | خطا را چاپ می‌کند و خارج می‌شود | 1 |
| `strict` | آن را به‌صورت uncaught exception بالا می‌برد | 1 |
| `throw` | throw می‌کند، مگر handler وجود داشته باشد | 1 |
| `warn` | `UnhandledPromiseRejectionWarning` چاپ می‌کند و ادامه می‌دهد | 0 |
| `none` | بی‌صدا ادامه می‌دهد (`timer fired`) | 0 |

طبق مستندات Node.js حالت پیش‌فرض `throw` است و برای همین سطر اول و سوم یکسان رفتار می‌کنند. در `warn` و `none` برنامه به کارش ادامه می‌دهد (timer در هر دو شلیک کرد) و در `none` حتی پیامی هم چاپ نمی‌شود. این دو حالت باگ‌های واقعی را پنهان می‌کنند، پس پیش‌فرض را نگه دارید.

`Promise.any` به این موضوع مربوط است: وقتی همه‌ی ورودی‌هایش شکست بخورند با یک **{{< term "aggregate-error" "AggregateError" >}}** که همه‌ی دلیل‌ها را نگه می‌دارد reject می‌شود. دمو نامش، اینکه واقعاً `AggregateError` هست یا نه، پیامش و فهرست دلیل‌ها را چاپ می‌کند:

```text
AggregateError true All promises were rejected
[ 'x', 'y' ]
```

## handlerها برای لاگ و خروج‌اند

Node اجازه می‌دهد به شکست‌هایی که کسی نگرفته گوش بدهید: `process.on('unhandledRejection', ...)` برای promiseها و `process.on('uncaughtException', ...)` برای خطاهای پرتاب‌شده. این اسکریپت هر دو را می‌گذارد و بعد از هر کدام یکی ایجاد می‌کند:

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

هر دو handler اجرا شدند و process به کارش ادامه داد و با کد ۰ تمام شد. این همان تله است. مهربان به نظر می‌رسد، ولی بعد از یک خطای غیرمنتظره ممکن است برنامه‌ی شما نیمه‌به‌روز شده باشد: شمارنده‌ای عوض شده، فایلی نیمه‌نوشته مانده، اتصالی در حالتی عجیب است. ادامه دادن انگار هیچ اتفاقی نیفتاده می‌تواند داده را خراب کند. پس این handlerها باید سه کار بکنند: خطا را لاگ کنند، پذیرفتن کار تازه را متوقف کنند و با کد غیرصفر خارج شوند. این یک نسخه‌ی حداقلی برای یک سرور HTTP است:

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

چه می‌کند: پرچم تضمین می‌کند فقط یک بار اجرا شود. شکست را لاگ می‌کند. timer یک مهلت سخت است: اگر بستن بیشتر از ۵ ثانیه طول کشید، به‌هرحال خارج شو (`unref()` یعنی این timer به‌تنهایی process را زنده نگه نمی‌دارد). `server.close` پذیرفتن اتصال تازه را متوقف می‌کند و وقتی اتصال‌های قدیمی تمام شدند خارج می‌شود، و `closeAllConnections` باقی‌مانده‌ها را می‌بندد به‌جای اینکه منتظرشان بماند.

در سرور دمو، یک کار پس‌زمینه بعد از ۶۰۰ میلی‌ثانیه یک rejection فراموش‌شده شلیک می‌کند. چاپ شد `FATAL unhandledRejection: background job failed` و process سرور با کد ۱ خارج شد. در پروداکشن یک supervisor (مثل systemd یا Kubernetes) متوجه می‌شود و process تازه‌ای راه می‌اندازد.

## یک جا برای نگاشت خطا به HTTP

برگردیم به handler درخواست؛ سؤال دیگری هست: وقتی چیزی شکست می‌خورد، کلاینت چه می‌بیند؟ این تصمیم را در یک جا نگه دارید. این `errors.js` یک `AppError` پایه دارد، به‌علاوه‌ی `NotFoundError` و `ValidationError`، و تابعی که هر خطا را به یک status و یک body نگاشت می‌کند. معادل Node تابع `statusOf` در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) است:

```js
function statusOf(err) {
  if (err instanceof AppError) return [err.status, { error: err.expose ? err.message : 'internal error', code: err.code }];
  return [500, { error: 'internal error', code: 'E_INTERNAL' }];
}
```

`expose` فقط برای statusهای کمتر از ۵۰۰ درست است، پس جزئیات شکست‌های سمت سرور هیچ‌وقت به کلاینت نمی‌رسد. با `curl` درخواست‌های واقعی به سرور دمو روی `127.0.0.1` (با پورت تصادفی) فرستادم و status داخل کروشه است:

```text
GET /          -> {"error":"id is required","code":"E_VALIDATION"} [422]
GET /?id=1     -> {"user":"alice"} [200]
GET /?id=9     -> {"error":"user not found","code":"E_NOT_FOUND"} [404]
GET /?id=boom  -> {"error":"internal error","code":"E_INTERNAL"} [500]
GET /?id=bug   -> {"error":"internal error","code":"E_INTERNAL"} [500]
```

دو مورد آخر از دو جنس شکست‌اند. `boom` یک **{{< term "operational-error" "operational error" >}}** است: شکستی قابل‌انتظار، اینجا پایگاه داده‌ای که اتصال را رد می‌کند، که داخل `AppError` پیچیده شده. `bug` یک `TypeError` است که از اشتباه برنامه‌نویس می‌آید (`null.x`). در دمو هر دو روی سرور لاگ شدند (`request failed: db password wrong` و `request failed: Cannot read properties of null (reading 'x')`)، هر دو به کلاینت همان ۵۰۰ پنهان را دادند و سرور سر پا ماند. تفاوت در کاری است که باید بکنید: operational error چیزی است که کدتان برایش برنامه داشت، ولی باگ یعنی فرض‌های شما اشتباه بوده، پس وضعیت process مشکوک است و راه‌اندازی دوباره امن‌ترین واکنش است.

## مقایسه با Go

در Go تابع یک `error` را به‌عنوان مقدار معمولی برمی‌گرداند و `if err != nil` در محل فراخوانی وادارتان می‌کند همان‌جا با آن کنار بیایید. `panic` برای باگ‌هاست. JavaScript throw می‌کند، پس نبودن handler تا لحظه‌ای که شکست در زمان اجرا رخ بدهد دیده نمی‌شود. wrap کردن در هر دو زبان هست: اینجا `cause` و آنجا `%w`.

## خطاهایی که از زیر دست در می‌روند

- **پرتاب رشته یا شیء ساده.** stack ندارند. شیء `Error` یا زیرکلاس‌هایش را پرتاب کنید.
- **اعتماد به `try/catch` دور callbackها و timerها.** آن‌ها را پوشش نمی‌دهد. `await` را پوشش می‌دهد.
- **emitter بدون listener برای `'error'`.** یک خطای emitشده process را می‌کشد.
- **استفاده از handlerهای سراسری برای ادامه دادن.** آن‌ها برای لاگ و خروج با کد غیرصفرند، نه برای ادامه.
- **پخش کردن تصمیم نگاشت خطا به HTTP بین handlerها.** در یک جا نگاشت کنید و پیام‌های ۵xx را پنهان کنید.

## تمرین

یک `TimeoutError` به `errors.js` اضافه کنید که به ۵۰۴ نگاشت شود و با `curl` ثابت کنید handlerای که منتظر یک فراخوانی کند است آن را برمی‌گرداند.

## قدم بعدی

«stream و backpressure در Node.js»: خطا داخل streamها و `pipeline` همان‌جا بررسی می‌شود.
