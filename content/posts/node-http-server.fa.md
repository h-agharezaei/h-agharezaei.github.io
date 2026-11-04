+++
date = '2026-12-27T10:00:00+03:30'
draft = false
title = 'سرور HTTP با node:http'
description = 'سرور HTTP با node:http و اجرای واقعی: routing دستی، محدودیت حجم بدنه با 413، timeout، keep-alive، خاموشی تمیز و تست با node:test.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "http", "node-http", "graceful-shutdown", "node-test"]
cover = { image = "/images/covers/node-http-server.fa.png", alt = "سرور HTTP با node:http", hiddenInSingle = true }
+++

یک وب‌سرور واقعاً چه کار می‌کند؟ منتظر پیام یک کلاینت می‌ماند، آن را می‌خواند، تصمیم می‌گیرد کلاینت چه می‌خواهد و یک پیام برمی‌گرداند. بقیه‌ی چیزها، مثل فریم‌ورک، router و middleware، راحتی‌هایی هستند که روی همین حلقه سوار شده‌اند. پیش از رفتن سراغ Fastify در مقاله‌ی بعد، می‌خواهم این حلقه را دستی و فقط با چیزهایی که همراه خود Node.js می‌آید بسازم تا بعداً بدانید فریم‌ورک دقیقاً چه کاری را از دوش شما برمی‌دارد.

سرور یک API کوچک سفارش‌هاست، هم‌شکل [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/): ساخت سفارش، گرفتن سفارش و یک health check. در راه با مشکل‌هایی روبه‌رو می‌شویم که هر سرور واقعی باید حلشان کند: کلاینتی که بدنه‌ی غول‌آسا می‌فرستد، کلاینتی که آشغال می‌فرستد، کلاینتی که عمداً کند است، و deployای که نباید درخواست‌ها را وسط کار ببُرد.

اینجا همان داده‌ی تکه‌تکه‌ی [stream و backpressure در Node.js](/fa/posts/node-streams-backpressure/) واقعاً مهم می‌شود، چون request یک stream خواندنی و response یک stream نوشتنی است. کد روی [event loop](/fa/posts/node-event-loop/)، [async/await](/fa/posts/node-promises-async-await/) و [مدیریت خطا](/fa/posts/node-errors-unhandled-rejections/) تکیه دارد.

> Node نسخه‌ی v20.13.1. کد یک مثال محلی است (`app.js`، `main.js` و چند اسکریپت دمو)؛ همه‌ی خروجی‌های زیر از اجرای واقعی روی loopback (آدرس 127.0.0.1) و با یک پورت آزاد تصادفی کپی شده‌اند. در دستورها برای کوتاه ماندن پورت 3000 را نوشته‌ام.

## سرور و routing دستی

`http.createServer` یک تابع می‌گیرد و Node آن را برای هر درخواست ورودی یک بار صدا می‌زند، با دو شیء: `req` (درخواست، یک stream خواندنی) و `res` (پاسخ، یک stream نوشتنی). router وجود ندارد. برای تصمیم‌گیری خودم `req.url` را می‌خوانم و به method و مسیر نگاه می‌کنم.

مسیرها `GET /health`، `POST /orders` و `GET /orders/:id` هستند و سفارش‌ها در یک `Map` داخل حافظه می‌مانند (پس با ری‌استارت سرور از بین می‌روند). برای اینکه handlerها ساده بمانند، وقتی چیزی اشتباه است یک `HttpError` همراه با کد وضعیت **پرتاب** می‌کنند و یک جا در بالا آن را به پاسخ تبدیل می‌کند:

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

چرا `.catch`؟ چون `handle` تابع `async` است و خطای پرتاب‌شده در آن یک promise ردشده می‌شود. اگر کسی آن را مدیریت نکند، یک {{< term "unhandled-rejection" "unhandled rejection" >}} است و همان‌طور که در مقاله‌های قبل دیدیم process را می‌کشد، یعنی یک درخواست بد همه‌ی کلاینت‌های دیگر را هم از کار می‌اندازد. در خط آخر `.catch` یک قاعده‌ی دیگر هم هست: خطای غیرمنتظره (وضعیت 500) روی سرور لاگ می‌شود، اما کلاینت فقط عبارت «internal error» را می‌بیند، نه پیام واقعی را.

امتحانش کنیم. دستورها `curl` روی سرور در حال اجرا هستند (`-s` یعنی بی‌صدا، `-i` هدرهای پاسخ را هم چاپ می‌کند و هدرها را به خطوط مفید خلاصه کرده‌ام):

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

دستور اول یک سفارش می‌سازد و سرور `201 Created` جواب می‌دهد، با هدر `Location` که می‌گوید سفارش تازه کجاست. شناسه (`c0b3df24`) تصادفی است و شما شناسه‌ی دیگری می‌بینید. بقیه‌ی خط‌ها نشان می‌دهند هر نوع اشتباه برای کلاینت چه شکلی است:

- **404**: چنین سفارشی (یا چنین مسیری) نیست.
- **405**: مسیر هست ولی برای این method نه، و هدر `Allow` می‌گوید کدام method پذیرفته است.
- **400**: بدنه JSON معتبر نیست.
- **422**: JSON معتبر است ولی محتوا نه (اینجا `qty` نیست).
- **500**: باگ سمت ما.

`/boom` مسیری است که اضافه کردم و عمداً خطا پرتاب می‌کند. لاگ سرور `internal error: unexpected bug` را نشان داد، کلاینت همان 500 کلی را گرفت و درخواست بعدی به `/health` باز هم جواب داد؛ پس یک شکست سرور را از کار نینداخت. همه‌ی این‌ها را برای این مقاله در یک نسخه‌ی scratch دوباره اجرا کردم و کدهای وضعیت و بدنه‌ها یکی بودند.

## خواندن بدنه با سقف حجم

حالا اولین خطر واقعی. بدنه‌ی درخواست تکه‌تکه می‌رسد و کلاینت هر تعداد تکه بخواهد می‌تواند بفرستد. اگر همه را جمع کنید، یک کلاینت می‌تواند حافظه‌ی شما را پر کند. پس کد بایت‌ها را هم‌زمان با رسیدن تکه‌ها می‌شمارد و بیش از ۱۰۲۴ بایت نگه نمی‌دارد:

```js
req.on('data', (chunk) => {
  if (tooBig) return;
  size += chunk.length;
  if (size > max) { tooBig = true; reject(new HttpError(413, 'body too large')); return; }
  chunks.push(chunk);
});
```

وضعیت «بدنه‌ات بزرگ است» `413 Payload Too Large` است. یک گیر هست که راحت از چشم می‌افتد. کار طبیعی، یعنی destroy کردن درخواست (`req.destroy()`) به‌محض رد شدن از سقف، اتصال را هم نابود می‌کند. آن‌وقت کلاینت هیچ‌وقت 413 شما را نمی‌گیرد. نسخه‌ی اول من دقیقاً همین کار را کرد و `curl` به‌جای وضعیت یک پاسخ خالی چاپ کرد (کد خروج 52). راه درست این است که اول 413 را بنویسید، به کلاینت بگویید اتصال بسته می‌شود (`Connection: close`) و درخواست را فقط بعد از اینکه پاسخ فرستاده شد destroy کنید، روی رویداد `finish` پاسخ:

```js
if (status === 413) {
  res.on('finish', () => req.destroy());
  return send(res, status, { error: err.message }, { Connection: 'close' });
}
```

حالا یک بدنه‌ی ۵۰۰۰ بایتی جواب درست می‌گیرد:

```text
HTTP/1.1 413 Payload Too Large
Connection: close

{"error":"body too large"}
```

## پیش‌فرض‌هایی که باید بدانید

سرور HTTP در Node چند timeout دارد که برای امنیت مهم‌اند. این چیزی است که یک سرور تازه در Node 20.13.1 چاپ می‌کند (زمان‌ها میلی‌ثانیه‌اند):

```text
keepAliveTimeout  5000
headersTimeout    60000
requestTimeout    300000
timeout           0
maxHeadersCount   null
```

به زبان ساده:

- `keepAliveTimeout`: یک اتصال بی‌کار را برای درخواست بعدی چقدر باز نگه دارد، ۵ ثانیه.
- `headersTimeout`: کلاینت چقدر وقت دارد ارسال هدرهای درخواست را تمام کند، ۶۰ ثانیه.
- `requestTimeout`: کلاینت چقدر وقت دارد کل درخواست را بفرستد، ۳۰۰ ثانیه.
- `timeout`: timeout قدیمی بی‌فعالیتی سوکت؛ صفر یعنی خاموش.
- `maxHeadersCount`: محدودیتی روی تعداد هدرها نیست (`null`).

مورد اول یک تصویر لازم دارد. باز کردن یک اتصال TCP یک رفت‌وبرگشت هزینه دارد، برای همین HTTP اجازه می‌دهد کلاینت از یک اتصال برای چند درخواست استفاده کند. اسمش {{< term "keep-alive" "keep-alive" >}} است. در دمو، کلاینتی با agent از نوع keep-alive پنج درخواست را روی ۱ اتصال TCP فرستاد؛ وقتی keep-alive خاموش بود همان پنج درخواست ۵ اتصال گرفت.

## کلاینت کند

timeoutها به خاطر کلاینت‌هایی هستند که عمداً کند می‌فرستند. مثال کلاسیکش حمله‌ی {{< term "slowloris" "slowloris" >}} است: اتصال‌های زیادی باز کن و هر درخواست را خیلی آهسته بفرست تا سرور همه‌ی آن اتصال‌ها را مشغول نگه دارد و برای کاربر واقعی جایی نماند.

برای آزمودن دفاع، یک کلاینت خام با `node:net` نوشتم که درخواست را خط‌به‌خطِ هدر می‌فرستد، هر ۳۰۰ میلی‌ثانیه یک خط. سروری که با آن حرف می‌زند timeoutهای کوتاه‌شده دارد تا دمو سریع باشد: `headersTimeout = 500`، `requestTimeout = 1000` و `connectionsCheckingInterval = 100` (هر چند وقت Node دنبال درخواست‌های منقضی می‌گردد). کلاینت چاپ می‌کند چند تکه توانسته بفرستد و خط اول پاسخ سرور چه بوده:

```text
header chunks sent: 2 of 6 (one every 300 ms, headersTimeout 500 ms)
server replied: "HTTP/1.1 408 Request Timeout"
```

سرور پیش از کامل شدن هدرها کوتاه آمد و `408 Request Timeout` جواب داد. وقتی دوباره اجرا کردم ماشین شلوغ بود (میانگین بار یک‌دقیقه‌ای بالای ۲۰) و تعداد تکه‌های فرستاده‌شده بین اجراها فرق کرد: در یک اجرا ۲ و در دیگری ۳. خود 408 هر دو بار یکی بود. برای همین دمو شمارش را چاپ می‌کند ولی من مدت زمانی ادعا نمی‌کنم. هر دو timeout تنظیم شده بود ولی timeout هدرها اول فعال شد و حالت بدنه را جداگانه نیازمودم.

## خاموشی تمیز

وقتی نسخه‌ی تازه deploy می‌شود، process قدیمی `SIGTERM` می‌گیرد («لطفاً بایست»). اگر فوراً خارج شود، هر درخواستِ در حال انجام بریده می‌شود. روش مؤدبانه {{< term "graceful-shutdown" "graceful shutdown" >}} است: پذیرفتن اتصال تازه را متوقف کن، اتصال‌های بی‌کار را ببند، بگذار درخواست‌های در حال اجرا تمام شوند و بعد خارج شو.

برای آزمودنش یک مسیر `/slow` اضافه کردم که ۱٫۵ ثانیه طول می‌کشد، یک `curl` روی آن شروع کردم و ۰٫۵ ثانیه بعد یک `kill -TERM` واقعی به سرور فرستادم. handler در `main.js` این است:

```js
let shuttingDown = false;
process.on('SIGTERM', () => {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log('SIGTERM: closing');
  server.close(() => { console.log('server closed, exiting 0'); process.exit(0); });
  server.closeIdleConnections();
  setTimeout(() => { console.log('forced exit'); process.exit(1); }, 5000).unref(); // safety net
});
```

`server.close` پذیرفتن اتصال تازه را متوقف می‌کند و وقتی همه‌ی اتصال‌های موجود تمام شدند callback را صدا می‌زند. timer یک تور ایمنی است: اگر چیزی ۵ ثانیه گیر کرد، به هر حال خارج شو (`unref()` یعنی خود این timer process را زنده نگه نمی‌دارد). اسکریپت بعد یک درخواست تازه را وسط خاموشی امتحان کرد:

```text
new request during shutdown: curl exit code 7   (connection refused)
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

سه خط می‌گویند: درخواست تازه رد شد (کد خروج 7 در curl یعنی نتوانست وصل شود)، درخواستِ در حال اجرا با جواب خودش تمام شد، و سرور با کد 0 خارج شد. طبق مستندات Node، از Node 19 به بعد `close()` اتصال‌های بی‌کار را هم می‌بندد؛ صدا زدن `closeIdleConnections()` آن را صریح می‌کند.

## تست با node:test

آخر اینکه سرور بدون تست یک امید است. ترفند تست یک سرور HTTP `server.listen(0)` است: پورت 0 از سیستم‌عامل یک پورت آزاد می‌خواهد، پس تست‌ها نه با هم تداخل می‌کنند و نه با سرور دیگری که در حال اجراست. خود `node:test` را در مقاله‌ای بعدی می‌بینیم؛ اینجا فقط نحوه‌ی استفاده‌اش را می‌بینید:

```js
before(async () => {
  server = createApp();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => { server.closeAllConnections(); server.close(); });
```

`before` سرور را بالا می‌آورد و آدرسش را نگه می‌دارد و `after` آن را می‌بندد. سه تست (health، ساخت و سپس گرفتن سفارش، و حالت‌های 404/405/400/413) با `fetch` داخلی و `node:assert` نوشته شده‌اند. وقتی اجرایشان کردم خلاصه این بود: `# tests 3`، `# pass 3` و `# fail 0`.

## مقایسه با Go

`ServeMux` در Go (از Go 1.22) الگوهایی مثل `GET /orders/{id}` را می‌فهمد، `PathValue` می‌دهد و 405 را با هدر `Allow` خودش جواب می‌دهد؛ اینجا همه‌ی این‌ها را دستی نوشتم. Go برای سقف بدنه `http.MaxBytesReader` و برای تخلیه `Server.Shutdown` دارد. تفاوت دیگر مدل هم‌زمانی است: Go هر درخواست را در goroutine جدا اجرا می‌کند، اما Node همه‌ی درخواست‌ها را روی یک thread انجام می‌دهد، پس handlerی که بلاک شود همه‌ی کلاینت‌ها را متوقف می‌کند.

## پیش از رفتن به production

- **handler async را همیشه `.catch` کنید.** یک promise ردشده باید برای همان درخواست 500 شود، نه اینکه کل process بمیرد.
- **حجم بدنه را محدود کنید و پیش از destroy کردن سوکت جواب بدهید.** وگرنه کلاینت یا حافظه‌ی شما را پر می‌کند یا به‌جای خطا پاسخ خالی می‌گیرد.
- **`headersTimeout` و `requestTimeout` را روشن نگه دارید.** سپر شما در برابر کلاینت‌های کند هستند. پشت load balancer، `keepAliveTimeout` را هم خودتان مطابق آن تنظیم کنید.
- **SIGTERM را مدیریت کنید و timer خروج اجباری بگذارید.** بدون timer، یک اتصال گیرکرده می‌تواند process قدیمی را برای همیشه زنده نگه دارد.

## تمرین

مسیر `DELETE /orders/:id` را اضافه کنید (204 یا 404) و تستی بنویسید که سفارشی را حذف می‌کند و بعد انتظار 404 برای `GET` دارد. بعد هر `Content-Type` غیر از `application/json` را با 415 رد کنید.

## قدم بعدی

«ساخت API با Fastify» مقاله‌ی بعدی است. هرچه اینجا دستی نوشتیم، از routing تا اعتبارسنجی و خاموشی، آنجا به یک فریم‌ورک سپرده می‌شود.
