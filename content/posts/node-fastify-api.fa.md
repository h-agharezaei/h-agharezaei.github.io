+++
date = '2027-01-06T10:00:00+03:30'
draft = false
title = 'ساخت API با Fastify'
description = 'ساخت API با Fastify و اجرای واقعی: اعتبارسنجی با JSON Schema، hook، plugin، یک error handler، لاگ pino، تست با inject() و خاموشی تمیز.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "fastify", "api", "json-schema", "pino"]
cover = { image = "/images/covers/node-fastify-api.fa.png", alt = "ساخت API با Fastify", hiddenInSingle = true }
+++

به API سفارش‌ها در [سرور HTTP با node:http](/fa/posts/node-http-server/) نگاه کنید. منطق کسب‌وکار کوچک بود: ذخیره‌ی یک سفارش و گرفتن یک سفارش. ولی دورش کلی لوله‌کشی بود که دستی نوشتم: شکستن URL، شاخه زدن روی method، خواندن بدنه با شمارنده‌ی حجم، بررسی نوع فیلدها، تبدیل خطا به کد وضعیت و بستن مؤدبانه‌ی سرور. در یک API بزرگ‌تر این لوله‌کشی برای هر مسیر تکرار می‌شود و هر نسخه‌اش یک فرصت برای اشتباه است.

این همان مسئله‌ای است که یک فریم‌ورک حل می‌کند. **Fastify** یک فریم‌ورک وب برای Node.js است و ایده‌ی اصلی‌اش این است که شما *توصیف* می‌کنید یک مسیر چه می‌پذیرد و چه برمی‌گرداند، به شکل داده، و فریم‌ورک بررسی، parse و serialize را برایتان انجام می‌دهد. در این مقاله همان API را (`GET /health`، `GET /orders/:id`، `POST /orders` و یک انبار داخل حافظه) با Fastify دوباره می‌سازم و در هر قدم نشان می‌دهم چه کد دستی‌ای را کنار می‌گذارد. نسخه‌ی Go همین تمرین [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است.

> Node نسخه‌ی v20.13.1، Fastify نسخه‌ی 5.12.7 (و pino نسخه‌ی 10.4.0)، از قفل وابستگی دمو. کد یک مثال محلی است (`app.js`، `main.js` و `app.test.js`) و خروجی‌ها از اجرای واقعی روی loopback کپی شده‌اند. یک چیز اول خراب شد: `inject()` در Fastify (پایین‌تر برای تست از آن استفاده می‌کنیم) با `ERR_REQUIRE_ESM` کرش کرد. دلیلش این است که یک `light-my-request` جدید به بسته‌ی `cookie` وابسته است که فقط ES module است و Node 20.13 نمی‌تواند آن را `require()` کند. با یک ورودی `overrides` در npm، `light-my-request` را روی 6.6.0 قفل کردم و هرچه پایین‌تر می‌بینید با همین قفل اجرا شده است. موقع نوشتن دوباره بررسی کردم: یک نصب تازه‌ی بدون قفل (Fastify نسخه‌ی 5.12.8 و light-my-request نسخه‌ی 6.8.0) هم‌اکنون روی Node 20.13.1 باز همان‌طور شکست می‌خورد.

## مسیرها و schema

یک مسیر در Fastify یک method، یک path و یک تابع async است. هرچه تابع برگرداند به JSON تبدیل می‌شود. بخش جالب گزینه‌ی `schema` است. یک {{< term "json-schema" "JSON Schema" >}} به مسیر وصل می‌کند: یک سند JSON کوچک که توصیف می‌کند params، بدنه و پاسخ باید چه شکلی باشند. Fastify داده‌ی ورودی را قبل از اجرای تابع شما با آن می‌سنجد، پس تابع می‌تواند به ورودی‌اش اعتماد کند:

```js
app.post('/orders', {
  schema: {
    body: { type: 'object', required: ['item', 'qty'], additionalProperties: false,
      properties: { item: { type: 'string', minLength: 1 }, qty: { type: 'integer', minimum: 1 } } },
    response: { 201: orderSchema },
  },
}, async (request, reply) => { /* request.body is already valid here */ });
```

این جای خط‌های `if (typeof body.item !== 'string' ...)` در سرور دستی را می‌گیرد. برای دیدن کارش، یک اپ کوچک Fastify بدون هیچ مدیریت خطای سفارشی اجرا کردم و سه بدنه فرستادم: `qty` با نوع اشتباه، `qty` که نیست، و یک بدنه‌ی معتبر با فیلد اضافه‌ی `"extra": true`. این بدنه‌ی خطای خود Fastify است:

```text
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body/qty must be integer"}
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body must have required property 'qty'"}
200 {"item":"book","qty":1}
```

دو مورد اول با 400 و پیامی که اسم فیلد را می‌گوید رد شدند. سومی غافلگیری است. schema می‌گوید `additionalProperties: false` ولی درخواست با 200 پذیرفته شد و `extra` از نتیجه حذف شده است. به‌طور پیش‌فرض validator در Fastify ویژگی‌های ناشناخته را *پاک می‌کند* و رد نمی‌کند. راحت است، ولی باید بدانید: کلاینتی که اسم فیلدی را غلط بنویسد خطا نمی‌گیرد، فیلد فقط ناپدید می‌شود.

schema پاسخ در جهت دیگر کار می‌کند و یک ویژگی ایمنی است. در دموی من handler شیئی با فیلد اضافه‌ی `secretNote` برمی‌گرداند، ولی `GET /orders/:id` فقط `{"id":"c298b17c","item":"pen","qty":3}` فرستاد. serialize فقط همان چیزی را نگه می‌دارد که schema فهرست کرده است، پس یک فیلد داخلی به‌اشتباه نشت نمی‌کند. (شناسه تصادفی است و شما شناسه‌ی دیگری می‌بینید.)

## hookها و شناسه‌ی درخواست

هر درخواست از یک رشته‌ی ثابت از مرحله‌ها رد می‌شود و Fastify اجازه می‌دهد در هر مرحله تابع خودتان را اجرا کنید. این‌ها {{< term "lifecycle-hook" "hook" >}} هستند. برای دیدن ترتیب، در یک اسکریپت scratch روی هر مرحله یک hook گذاشتم و یک `POST /orders` فرستادم. این اسکریپت در پوشه‌ی دمو نیست و در یک نسخه‌ی scratch اجرایش کردم. مرحله‌ها به این ترتیب اجرا شدند:

```text
onRequest -> preParsing -> preValidation -> preHandler -> preSerialization -> onSend -> onResponse
```

تقریباً یعنی: درخواست رسید، بدنه در حال خواندن است، بدنه در حال اعتبارسنجی است، handler شما در شرف اجراست، پاسخ در شرف serialize شدن است، در شرف ارسال است، و ارسال شد. اپ دموی من از دو تایشان استفاده می‌کند: یکی هنگام ورود {{< term "request-id" "شناسه‌ی درخواست" >}} (request id) را روی پاسخ می‌گذارد و دیگری هنگام خروج یک هدر اضافه می‌کند:

```js
genReqId: (req) => req.headers['x-request-id'] || randomUUID().slice(0, 8),
// ...
app.addHook('onRequest', async (request, reply) => { reply.header('x-request-id', request.id); });
app.addHook('onSend', async (request, reply, payload) => { reply.header('x-served-by', 'fastify-demo'); return payload; });
```

شناسه‌ی درخواست یک برچسب کوتاه و یکتاست که به یک درخواست چسبانده می‌شود تا بعداً همه‌ی خط‌های لاگ مربوط به آن پیدا شوند. `genReqId` تصمیم می‌گیرد چطور ساخته شود: اگر کلاینت هدر `x-request-id` فرستاده باشد همان را بردار، وگرنه یکی بساز. با `-H 'x-request-id: req-42'` پاسخ `x-request-id: req-42` داشت؛ بدون آن، یک شناسه‌ی ساخته‌شده مثل `53faa9e5`.

## plugin و جداسازی

وقتی اپ بزرگ می‌شود می‌خواهید آن را به بخش‌هایی تقسیم کنید که روی پای هم نروند. در Fastify این واحد **plugin** است: یک تابع async که اپ را می‌گیرد و مسیر، hook و decorator (ویژگی‌های اضافه روی اپ) اضافه می‌کند. `app.register(plugin)` آن را در یک scope فرزند اجرا می‌کند. در دمو، مسیرهای سفارش و انبار `orders` داخل `ordersPlugin` هستند.

فایده‌ی scope فرزند همین مرز است: چیزی که داخل plugin اضافه می‌کنید داخل آن دیده می‌شود و بیرون نه. یک آزمایش کوچک نشان می‌دهد: decoratorی که داخل یک plugin اضافه شده برای مسیر خود plugin دیده می‌شود و برای مسیری بیرون از آن نه:

```text
{"inside":42} {"outside":"undefined"}
```

مسیر اول، داخل plugin، decorator را می‌بیند (`42`). دومی، بیرون، نوعش را `"undefined"` می‌یابد. به همین دلیل ترکیب plugin‌ها امن است: یک بخش نمی‌تواند به‌طور اتفاقی به درون بخش دیگر وابسته شود یا آن را بازنویسی کند.

## یک جا برای خطاها

در سرور دستی یک `.catch`ی بزرگ داشتیم. Fastify برایش جای درست دارد. handlerها یک `DomainError('not_found' | 'conflict' | 'invalid', ...)` پرتاب می‌کنند، که فقط یک کلاس خطای کوچک خودمان با یک کد است. `setErrorHandler` همه را یک‌جا به کد وضعیت تبدیل می‌کند، همان ایده‌ی `statusOf` در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/). خطاهای 4xx خود Fastify (اعتبارسنجی، JSON خراب، بدنه‌ی بزرگ) هم همان‌جا تبدیل می‌شوند و هر چیز دیگر به یک 500 کلی بدل می‌شود. `setNotFoundHandler` مسیرهای ناشناخته را پوشش می‌دهد. برای هر حالت یک درخواست فرستادم:

```text
GET  /orders/nope1                  -> 404 {"error":"order not found"}
GET  /orders/ab                     -> 400 {"error":"params/id must NOT have fewer than 3 characters"}
POST /orders {"item":"dup","qty":1} (twice) -> 409 {"error":"order already exists"}
POST /orders {"item":"forbidden"..} -> 422 {"error":"this item cannot be ordered"}
POST /orders (2000-byte item)       -> 413 {"error":"Request body is too large"}
GET  /nothing                       -> 404 {"error":"not found"}
GET  /boom                          -> 500 {"error":"internal error"}
```

هر خط یک درخواست و پاسخ آن است. `/orders/ab` به `minLength: 3` در schema مربوط به params نمی‌رسد، پس خطای اعتبارسنجی است. آیتم `dup` همیشه همان شناسه را می‌گیرد، پس بار دوم تداخل می‌کند (409). `forbidden` یک قاعده‌ی کسب‌وکار است (422). گذاشتن `bodyLimit: 1024` روی اپ، بدون هیچ کد stream از من، 413 را داد؛ آن را با `readJson`ی که بایت می‌شمرد در مقاله‌ی قبل مقایسه کنید. و 500 پیام واقعی را از کلاینت پنهان می‌کند، در حالی که لاگ آن را نگه می‌دارد.

## لاگ با pino

Fastify یک logger به اسم pino همراه دارد. با `Fastify({ logger: { level: process.env.LOG_LEVEL || 'info' } })` روشنش می‌کنید. هر خط لاگ {{< term "structured-logging" "ساختاریافته" >}} است: یک شیء JSON با فیلدهای نام‌دار، تا ابزار لاگ بتواند روی فیلد فیلتر کند، نه اینکه در متن بگردد. هر خط شناسه‌ی درخواست را دارد. (`base: null` گذاشتم تا شناسه‌ی process و نام میزبان از هر خط حذف شود.) دو خط از دمو، کوتاه‌شده:

```text
{"level":30,"time":1793078445637,"reqId":"32474994","req":{"method":"GET","url":"/health","host":"127.0.0.1:3000","remoteAddress":"127.0.0.1","remotePort":49603},"msg":"incoming request"}
{"level":50,"time":1793078445676,"reqId":"1c813ba7","err":{"type":"Error","message":"unexpected bug","stack":"Error: unexpected bug\n ...
```

`level` یک عدد است: 30 یعنی info و 50 یعنی error. `time` زمان یونیکس به میلی‌ثانیه است و `reqId` چیزی است که همه‌ی خط‌های یک درخواست را به هم وصل می‌کند. خط دوم شکست `/boom` با stack آن است که کلاینت هرگز ندید. با `LOG_LEVEL=warn` همان دو درخواست (`/boom` و یک مسیر ناشناخته) دقیقاً یک خط تولید کردند، یعنی خطای سطح 50. داخل handlerها به‌جای logger سراسری از `request.log` استفاده کنید تا شناسه‌ی درخواست خودکار همراه شود.

## تست بدون پورت

در مقاله‌ی قبل تست‌ها یک سرور واقعی روی یک پورت آزاد بالا می‌آوردند. Fastify همان را هم حذف می‌کند: `app.inject()` یک درخواست ساختگی را از کل خط لوله رد می‌کند، با hookها و اعتبارسنجی، بدون باز کردن سوکت:

```js
const app = build({ logger: false });
const created = await app.inject({ method: 'POST', url: '/orders', payload: { item: 'book', qty: 2 } });
assert.equal(created.statusCode, 201);
```

یک تست `node:test` سلامت، ساخت، گرفتن، 404، 400، 422 و 409 را پوشش می‌دهد؛ خلاصه‌اش `# pass 1` و `# fail 0` بود. چون هیچ‌چیز روی پورتی گوش نمی‌دهد، این تست‌ها سریع‌اند و روی پورت با هم تداخل نمی‌کنند.

## خاموشی تمیز

خاموش کردن هم کوتاه‌تر شده است. `app.close()` پذیرفتن اتصال تازه را متوقف می‌کند و منتظر درخواست‌های در حال اجرا می‌ماند:

```js
process.on('SIGTERM', async () => { app.log.info({ sig: 'SIGTERM' }, 'shutting down'); await app.close(); process.exit(0); });
```

مثل قبل، یک درخواست به مسیر `/slow` که ۱٫۵ ثانیه طول می‌کشد شروع کردم و بعد یک `kill -TERM` واقعی فرستادم. درخواستی که وسط خاموشی رسید کد خروج 7 در curl گرفت (اتصال رد شد)، درخواست کند تمام شد و سرور با کد 0 خارج شد:

```text
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

این همان {{< term "graceful-shutdown" "خاموشی تمیز" >}} (graceful shutdown) مقاله‌ی قبل است، حالا با یک `close()`. اینجا timer خروج اجباری نگذاشتم؛ در production باید بگذارید، همان‌طور که آنجا گذاشتیم.

## Fastify جای چه چیزی را گرفت

| دستی در node:http | در Fastify |
|---|---|
| شکستن `req.url` و شاخه زدن روی method | `app.get('/orders/:id')` و `request.params` |
| `readJson` با شمارش حجم | `request.body` و `bodyLimit` |
| بررسی‌های `if (typeof ...)` | `schema.body` |
| تابع `send()` و `JSON.stringify` | `return obj` و `schema.response` |
| یک `.catch`ی بزرگ | `setErrorHandler` |
| `console.error` | `request.log` و pino |
| رقص ۵ ثانیه‌ای `server.close` | `app.close()` |

ادعای کارایی نکردم و چیزی هم اندازه نگرفتم؛ اینجا Fastify را برای ساختارش انتخاب کرده‌ام، نه برای سرعت.

## پیش‌فرض‌های فریم‌ورک که نیش می‌زنند

- **فیلدهای ناشناخته‌ی بدنه به‌طور پیش‌فرض پاک می‌شوند، نه رد.** همان‌طور که فیلد `extra` نشان داد، یک غلط املایی در اسم فیلد می‌تواند بی‌صدا ناپدید شود. اگر رد صریح می‌خواهید گزینه‌های validator را بررسی کنید.
- **schema یک قرارداد است.** schema پاسخ را طوری بنویسید که فیلد داخلی نشت نکند، همان‌طور که `secretNote` نشت نکرد.
- **در handlerها خطای دامنه پرتاب کنید و در یک `setErrorHandler` تبدیلش کنید.** پخش کردن `reply.code(...)` بین handlerها API را ناهماهنگ می‌کند.
- **بررسی کنید وابستگی‌های فریم‌ورک نسخه‌ی Node شما را پشتیبانی کنند.** اینجا `inject()` برای کار کردن روی Node 20.13 به قفل نسخه نیاز داشت.

## تمرین

مسیر `DELETE /orders/:id` را اضافه کنید (204 یا 404 از طریق خطای دامنه) و یک hook از نوع `preHandler` که درخواست بدون هدر `x-api-key` را با 401 رد کند. هر دو را با `inject()` تست کنید.

## قدم بعدی

«تست در Node.js با node:test» مقاله‌ی بعدی است. `inject()` تست را ارزان کرد، پس حالا خود ابزار اجرای تست را می‌بینیم.
