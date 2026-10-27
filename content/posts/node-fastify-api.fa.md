+++
date = '2027-01-06T10:00:00+03:30'
draft = false
title = 'ساخت API با Fastify'
description = 'ساخت API با Fastify و اجرای واقعی: اعتبارسنجی با JSON Schema، hook، plugin، یک error handler، لاگ pino، تست با inject() و خاموشی تمیز.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "fastify", "api", "json-schema", "pino"]
cover = { image = "/images/covers/node-fastify-api.fa.png", alt = "ساخت API با Fastify", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [سرور HTTP با node:http](/fa/posts/node-http-server/)، routing، محدودیت حجم بدنه و تبدیل خطا را دستی نوشتیم. اینجا همان API کوچک سفارش (`GET /health`، `GET /orders/:id`، `POST /orders` با ذخیره‌ی درون‌حافظه) را با Fastify می‌سازم و با [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) مقایسه می‌کنم.

> Node نسخه‌ی v20.13.1، Fastify نسخه‌ی 5.12.7 (و pino نسخه‌ی 10.4.0). کد یک مثال محلی است (`app.js`، `main.js` و `app.test.js`)؛ همه‌ی خروجی‌ها از اجرای واقعی روی loopback کپی شده‌اند. `inject()` در Fastify اول با `ERR_REQUIRE_ESM` از کار افتاد: تازه‌ترین `light-my-request` یک `cookie` فقط-ESM می‌آورد که Node 20.13 نمی‌تواند با `require()` بارگذاری کند. نسخه‌ی `light-my-request` را با `overrides` در npm روی 6.6.0 ثابت کردم و همه‌ی اجراهای زیر با همین است.

## route و schema

route یعنی یک method، یک مسیر و یک تابع async. هرچه `return` کنید به JSON تبدیل می‌شود. گزینه‌ی `schema` یک **{{< term "json-schema" "JSON Schema" >}}** به params، body و response وصل می‌کند:

```js
app.post('/orders', {
  schema: {
    body: { type: 'object', required: ['item', 'qty'], additionalProperties: false,
      properties: { item: { type: 'string', minLength: 1 }, qty: { type: 'integer', minimum: 1 } } },
    response: { 201: orderSchema },
  },
}, async (request, reply) => { /* request.body is already valid here */ });
```

یک برنامه‌ی Fastify بدون هیچ مدیریت خطای سفارشی ساختم و payload بد فرستادم. این بدنه‌ی خطای خود Fastify است:

```text
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body/qty must be integer"}
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body must have required property 'qty'"}
200 {"item":"book","qty":1}
```

درخواست سوم فیلد اضافه‌ی `"extra": true` داشت و `additionalProperties: false` هم بود، ولی 200 گرفت و فیلد بی‌صدا حذف شد. پیش‌فرض Fastify حذف فیلد ناشناس است، نه رد.

response schema برعکس کار می‌کند: handler شیئی با فیلد `secretNote` برگرداند، اما `GET /orders/:id` فقط `{"id":"c298b17c","item":"pen","qty":3}` فرستاد. serialize فقط همان چیزی را نگه می‌دارد که schema فهرست کرده است.

## hookها و request id

**{{< term "lifecycle-hook" "hookها" >}}** در مرحله‌های ثابت اجرا می‌شوند. ترتیب را برای یک POST چاپ کردم: `onRequest -> preValidation -> preHandler -> onSend`. hookهای من در ورودی یک **{{< term "request-id" "request id" >}}** و در خروجی یک هدر اضافه می‌کنند:

```js
genReqId: (req) => req.headers['x-request-id'] || randomUUID().slice(0, 8),
// ...
app.addHook('onRequest', async (request, reply) => { reply.header('x-request-id', request.id); });
app.addHook('onSend', async (request, reply, payload) => { reply.header('x-served-by', 'fastify-demo'); return payload; });
```

با `-H 'x-request-id: req-42'` پاسخ هدر `x-request-id: req-42` داشت؛ بدون آن، مقداری ساخته‌شده مثل `53faa9e5`.

## plugin و encapsulation

`app.register(plugin)` یک scope فرزند می‌سازد. routeهای سفارش و decorator به نام `orders` درون `ordersPlugin` هستند. decoratorی که داخل plugin اضافه شود بیرون از آن دیده نمی‌شود:

```text
{"inside":42} {"outside":"undefined"}
```

## یک جا برای خطاها

handlerها `DomainError('not_found' | 'conflict' | 'invalid', ...)` پرتاب می‌کنند و `setErrorHandler` همه را یک‌جا به status تبدیل می‌کند؛ همان ایده‌ی `statusOf` در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/). خطاهای 4xx خود Fastify (validation، JSON خراب، 413) هم همان‌جا نگاشت می‌شوند و هر چیز دیگر به یک 500 عمومی تبدیل می‌شود. `setNotFoundHandler` مسیرهای ناشناس را پوشش می‌دهد.

```text
GET  /orders/nope1                  -> 404 {"error":"order not found"}
GET  /orders/ab                     -> 400 {"error":"params/id must NOT have fewer than 3 characters"}
POST /orders {"item":"dup","qty":1} (twice) -> 409 {"error":"order already exists"}
POST /orders {"item":"forbidden"..} -> 422 {"error":"this item cannot be ordered"}
POST /orders (2000-byte item)       -> 413 {"error":"Request body is too large"}
GET  /nothing                       -> 404 {"error":"not found"}
GET  /boom                          -> 500 {"error":"internal error"}
```

`bodyLimit: 1024` بدون هیچ کد stream‌ای همین 413 را داد، و 500 پیام واقعی را از کلاینت پنهان می‌کند در حالی که لاگ آن را نگه می‌دارد.

## لاگ با pino

لاگ توکار است: `Fastify({ logger: { level: process.env.LOG_LEVEL || 'info' } })`. هر خط یک **{{< term "structured-logging" "JSON ساختاریافته" >}}** با request id است (`base: null` گذاشتم تا pid و hostname ماشین در لاگ نیاید):

```text
{"level":30,"time":1793078445637,"reqId":"32474994","req":{"method":"GET","url":"/health","host":"127.0.0.1:3000","remoteAddress":"127.0.0.1","remotePort":49603},"msg":"incoming request"}
{"level":50,"time":1793078445676,"reqId":"1c813ba7","err":{"type":"Error","message":"unexpected bug","stack":"Error: unexpected bug\n ...
```

با `LOG_LEVEL=warn` همان دو درخواست (`/boom` و یک مسیر ناشناس) دقیقاً یک خط تولید کردند، یعنی خطای سطح 50. داخل handler از `request.log` استفاده کنید تا id همراه بماند.

## تست بدون باز کردن پورت

`app.inject()` یک درخواست را بدون باز کردن socket از کل pipeline رد می‌کند:

```js
const app = build({ logger: false });
const created = await app.inject({ method: 'POST', url: '/orders', payload: { item: 'book', qty: 2 } });
assert.equal(created.statusCode, 201);
```

یک تست `node:test` سلامت، ساخت، خواندن، 404، 400، 422 و 409 را پوشش می‌دهد (`# pass 1` و `# fail 0`).

## خاموشی تمیز

```js
process.on('SIGTERM', async () => { app.log.info({ sig: 'SIGTERM' }, 'shutting down'); await app.close(); process.exit(0); });
```

یک درخواست `/slow` با ۱٫۵ ثانیه تأخیر شروع کردم و بعد `kill -TERM` واقعی فرستادم. درخواستی که حین خاموشی آمد کد خروج 7 در curl گرفت (رد شد)، درخواست کند تمام شد و سرور با کد 0 بیرون آمد:

```text
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

این همان **{{< term "graceful-shutdown" "خاموشی تمیز" >}}** مقاله‌ی قبل است، این بار با یک `close()`. timer خروج اجباری نگذاشتم؛ شما بگذارید.

## Fastify چه چیزی را جایگزین کرد

| دستی در node:http | در Fastify |
|---|---|
| شکستن `req.url` و شاخه زدن روی method | `app.get('/orders/:id')` و `request.params` |
| `readJson` با شمارش حجم | `request.body` و `bodyLimit` |
| شرط‌های `if (typeof ...)` | `schema.body` |
| تابع `send()` و `JSON.stringify` | `return obj` و `schema.response` |
| یک `.catch` بزرگ | `setErrorHandler` |
| `console.error` | `request.log` و pino |
| رقص `server.close` با ۵ ثانیه | `app.close()` |

performance را اندازه نگرفتم و ادعایی ندارم.

## چند نکته‌ی مهم

- فیلدهای ناشناس بدنه به‌طور پیش‌فرض حذف می‌شوند، نه رد.
- schema یک قرارداد است: response schema بنویسید تا فیلد داخلی بیرون نرود.
- در handler خطای دامنه پرتاب کنید و در یک `setErrorHandler` نگاشت کنید.
- بررسی کنید نسخه‌ی Fastify و وابستگی‌هایش با نسخه‌ی Node شما سازگار باشد؛ اینجا `inject()` به pin نیاز داشت.

## تمرین

`DELETE /orders/:id` را اضافه کنید (204 یا 404 با خطای دامنه) و یک hook از نوع `preHandler` بنویسید که درخواست بدون هدر `x-api-key` را با 401 رد کند. هر دو را با `inject()` تست کنید.

## قدم بعدی

مقاله‌ی بعدی «تست در Node.js با node:test» است.
