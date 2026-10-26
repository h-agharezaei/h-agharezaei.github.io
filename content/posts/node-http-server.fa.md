+++
date = '2026-12-27T10:00:00+03:30'
draft = false
title = 'سرور HTTP با node:http'
description = 'سرور HTTP با node:http و اجرای واقعی: routing دستی، محدودیت حجم بدنه با 413، timeout، keep-alive، خاموشی تمیز و تست با node:test.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "http", "node-http", "graceful-shutdown", "node-test"]
cover = { image = "/images/covers/node-http-server.fa.png", alt = "سرور HTTP با node:http", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [stream و backpressure در Node.js](/fa/posts/node-streams-backpressure/)، دیدیم که داده تکه‌تکه جابه‌جا می‌شود. سرور HTTP اولین جایی است که این مهم می‌شود: request و response هر دو stream هستند. اینجا با کتابخانه‌ی استاندارد یک API کوچک سفارش می‌سازیم، هم‌شکل [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/). این مقاله به [event loop](/fa/posts/node-event-loop/)، [async/await](/fa/posts/node-promises-async-await/) و [مدیریت خطا](/fa/posts/node-errors-unhandled-rejections/) تکیه دارد.

> Node نسخه‌ی v20.13.1. کد یک مثال محلی است (`app.js`، `main.js` و چند اسکریپت دمو)؛ همه‌ی خروجی‌ها از اجرای واقعی روی loopback کپی شده‌اند.

## سرور و routing دستی

`http.createServer` به شما `req` (یک stream خواندنی) و `res` (یک stream نوشتنی) می‌دهد. router وجود ندارد، پس `req.url` را parse می‌کنم و روی method و مسیر شاخه می‌زنم. مسیرها: `GET /health`، `POST /orders` و `GET /orders/:id` با یک `Map` در حافظه. handlerها یک `HttpError` پرتاب می‌کنند و یک `.catch` آن را به پاسخ تبدیل می‌کند:

```js
const server = http.createServer((req, res) => {
  handle(req, res).catch((err) => {
    if (res.headersSent || res.destroyed) { res.destroy(); return; }
    const status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error('internal error:', err.message);
    send(res, status, { error: status === 500 ? 'internal error' : err.message });
  });
});
```

چون `handle` تابع `async` است، خطای پرتاب‌شده یک promise ردشده است. بدون آن `.catch` یک **{{< term "unhandled-rejection" "unhandled rejection" >}}** می‌شد و همان‌طور که دیدیم process را می‌کشت.

اجرای واقعی با curl (هدرها به خطوط مفید خلاصه شده‌اند):

```text
$ curl -si -X POST -d '{"item":"book","qty":2}' 127.0.0.1:3000/orders
HTTP/1.1 201 Created
Location: /orders/c0b3df24
Connection: keep-alive
Keep-Alive: timeout=5

{"id":"c0b3df24","item":"book","qty":2}

$ curl -si 127.0.0.1:3000/orders/nope      ->  404 {"error":"order not found"}
$ curl -si -X DELETE .../orders/<id>       ->  405 with "Allow: GET"
$ curl -si -X POST -d '{bad' .../orders    ->  400 {"error":"invalid JSON"}
$ curl -si -X POST -d '{"item":"x"}' ...   ->  422 (qty missing)
$ curl -si 127.0.0.1:3000/boom             ->  500 {"error":"internal error"}
```

`/boom` عمداً خطا می‌دهد؛ لاگ `internal error: unexpected bug` را نشان داد، کلاینت یک 500 کلی گرفت و `/health` بعدی هنوز جواب داد. `fetch` سراسری هم همان 404 (`application/json; charset=utf-8` و `{ error: 'order not found' }`) و 413 زیر را دید.

## خواندن بدنه با سقف حجم

بدنه تکه‌تکه می‌رسد، پس بایت‌ها را می‌شمارم و بیش از ۱۰۲۴ بایت را buffer نمی‌کنم:

```js
req.on('data', (chunk) => {
  if (tooBig) return;
  size += chunk.length;
  if (size > max) { tooBig = true; reject(new HttpError(413, 'body too large')); return; }
  chunks.push(chunk);
});
```

نسخه‌ی اولم فوراً `req.destroy()` را صدا می‌زد. این کار socket را می‌کُشد و curl پاسخ خالی گرفت (exit code برابر 52)، یعنی 413 هرگز دیده نشد. راه‌حل: 413 را با `Connection: close` بنویس و request را در رویداد `finish` پاسخ destroy کن. حالا بدنه‌ی ۵۰۰۰ بایتی این را می‌دهد:

```text
HTTP/1.1 413 Payload Too Large
Connection: close

{"error":"body too large"}
```

## مقدارهای پیش‌فرض

چاپ‌شده از یک سرور تازه روی Node 20.13.1:

```text
keepAliveTimeout  5000
headersTimeout    60000
requestTimeout    300000
timeout           0
maxHeadersCount   null
```

یک agent با **{{< term "keep-alive" "keep-alive" >}}** برای پنج درخواست فقط ۱ اتصال TCP استفاده کرد؛ با خاموش بودن keep-alive ۵ اتصال.

## کلاینت کند

حمله‌ی کلاسیک **{{< term "slowloris" "slowloris" >}}** اتصال باز می‌کند و درخواست را هرگز تمام نمی‌کند. یک کلاینت خام با `node:net` نوشتم که هر ۳۰۰ میلی‌ثانیه یک خط هدر می‌فرستد، به سروری با `headersTimeout = 500`، `requestTimeout = 1000` و `connectionsCheckingInterval = 100` (همه برای دمو کوتاه شده‌اند):

```text
header chunks sent: 2 of 6 (one every 300 ms, headersTimeout 500 ms)
server replied: "HTTP/1.1 408 Request Timeout"
```

چهار اجرا همین نتیجه را داد. ماشین مشغول بود (load average بالای ۲.۵)، پس مدت‌زمان گزارش نمی‌کنم. `requestTimeout` هم تنظیم شده بود اما `headersTimeout` زودتر عمل کرد؛ حالت بدنه‌ی کند را جدا آزمایش نکردم.

## خاموشی تمیز

با SIGTERM: پذیرش را متوقف کن، اتصال‌های بی‌کار را ببند، بگذار درخواست‌های در حال اجرا تمام شوند و بعد خارج شو. یک مسیر `/slow` که ۱.۵ ثانیه طول می‌کشد اضافه کردم، با curl صدایش زدم و بعد یک `kill -TERM` واقعی فرستادم:

```js
process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
  server.closeIdleConnections();
  setTimeout(() => process.exit(1), 5000).unref(); // safety net
});
```

```text
new request during shutdown: curl exit code 7   (connection refused)
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

درخواست در حال اجرا تمام شد، درخواست‌های تازه رد شدند و کد خروج ۰ بود. طبق مستندات، از Node 19 به بعد `close()` اتصال‌های بی‌کار را هم می‌بندد؛ صدا زدن `closeIdleConnections()` صریح‌تر است. این همان ایده‌ی **{{< term "graceful-shutdown" "graceful shutdown" >}}** است.

## تست با node:test

`server.listen(0)` یک پورت آزاد انتخاب می‌کند، پس تست‌ها با هم برخورد نمی‌کنند:

```js
before(async () => {
  server = createApp();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => { server.closeAllConnections(); server.close(); });
```

سه تست (health، ساخت و خواندن سفارش، و حالت‌های 404/405/400/413) با `fetch` و `node:assert`: `# pass 3` و `# fail 0`.

## مقایسه با Go

`ServeMux` در Go (از Go 1.22) الگوهایی مثل `GET /orders/{id}`، `PathValue` و 405 خودکار با هدر `Allow` می‌دهد؛ اینجا همه را دستی نوشتم. Go برای سقف بدنه `http.MaxBytesReader` و برای تخلیه‌ی تمیز `Server.Shutdown` دارد. Go هر درخواست را در goroutine جدا اجرا می‌کند؛ Node همه‌ی درخواست‌ها را روی یک thread پردازش می‌کند، پس handler مسدودکننده همه‌ی کلاینت‌ها را متوقف می‌کند.

## چند نکته‌ی مهم

- handler غیرهمگام را همیشه `.catch` کنید؛ rejection باید 500 شود، نه crash.
- حجم بدنه را محدود کنید و پیش از destroy کردن socket پاسخ بدهید.
- `headersTimeout` و `requestTimeout` را روشن نگه دارید؛ پشت load balancer `keepAliveTimeout` را خودتان تنظیم کنید.
- SIGTERM را مدیریت کنید و یک timer خروج اجباری بگذارید.

## تمرین

مسیر `DELETE /orders/:id` را اضافه کنید (پاسخ 204 یا 404) و تستی بنویسید که سفارش را حذف می‌کند و بعد انتظار 404 از `GET` دارد. سپس هر `Content-Type` غیر از `application/json` را با 415 رد کنید.

## قدم بعدی

مقاله‌ی بعدی «ساخت API با Fastify» است.
