+++
date = '2027-02-27T10:00:00+03:30'
draft = false
title = 'NATS JetStream از Node.js'
description = 'NATS JetStream از Node.js: publish با msgID، pull consumer ماندگار، ack، nak، term، backoff، drain تمیز و تعامل با Go، همه با اجرای واقعی.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "nats", "jetstream", "messaging", "graceful-shutdown"]
cover = { image = "/images/covers/node-nats-jetstream.fa.png", alt = "NATS JetStream از Node.js", hiddenInSingle = true }
+++

مشتری برای یک سفارش پول می‌دهد. سرویس شما سفارش را ذخیره می‌کند و پیام «سفارش ۱ ساخته شد» را می‌فرستد تا انبار بسته‌بندی را شروع کند. دو چیز باید برقرار باشد. پیام نباید گم شود، حتی اگر worker انبار همان لحظه از کار افتاده باشد. و worker نباید سفارش را دو بار بسته‌بندی کند، حتی اگر پیام دو بار برسد. یک فراخوانی ساده‌ی تابع هیچ‌کدام را تضمین نمی‌کند. یک سیستم پیام‌رسانی که ذخیره‌سازی دارد، می‌تواند.

در [Postgres از Node.js با pg](/fa/posts/node-postgres-pg/) سراغ دیتابیس رفتیم، ستون اول یک backend. پیام‌رسانی ستون دوم است. این‌جا از Node.js با {{< term "jetstream" "JetStream" >}} کار می‌کنم، لایه‌ی ذخیره‌سازی سرور پیام NATS. اگر نسخه‌های Go و Rust را خوانده باشید، یعنی [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/)، [Retry و Dead-Letter Queue در NATS JetStream با Go](/fa/posts/nats-jetstream-retry-dlq/)، [Idempotency در NATS JetStream](/fa/posts/nats-jetstream-idempotency/)، [Graceful shutdown برای workerهای Go](/fa/posts/go-graceful-shutdown-workers/) و [کلاینت async برای NATS JetStream در Rust](/fa/posts/rust-nats-async-client/)، ایده‌ها همان است و فقط کتابخانه‌ی کلاینت عوض می‌شود. ولی همه‌چیز این‌جا از اول توضیح داده می‌شود و لازم نیست آن‌ها را خوانده باشید.

> همه‌چیز را با Node نسخه‌ی v20.13.1 و `nats` نسخه‌ی 2.29.3 اجرا کردم (`package.json` آن Node نسخه‌ی ۱۴ به بالا می‌خواهد). سرور یک برنامه‌ی کوچک Go با nats-server توکار (نسخه‌ی 2.15.1) است که به‌صورت یک process جدا روی 127.0.0.1 و یک پورت آزاد تصادفی اجرا شد. برای دموی interop یک کلاینت کوچک Go با nats.go نسخه‌ی 1.54.0 ساختم. اسکریپت‌ها مثال محلی‌اند و خروجی‌ها واقعی‌اند. زمان‌بندی نشان نمی‌دهم.

## چهار کلمه که لازم دارید

NATS یک سرور پیام است. برنامه‌ها به آن وصل می‌شوند و پیام رد و بدل می‌کنند، و هر پیام به یک **subject** فرستاده می‌شود، نامی نقطه‌دار مثل `orders.created`. NATS ساده پیام را به هر که همان لحظه گوش می‌دهد می‌رساند و فراموشش می‌کند. سریع است، ولی چیزی نگه نمی‌دارد.

JetStream ذخیره‌سازی اضافه می‌کند و سه کلمه‌ی دیگر می‌آورد:

- **stream** یک log نام‌دار است که هر پیامِ منتشرشده به subjectهای مشخص را ذخیره می‌کند. مال ما `ORDERS` نام دارد و `orders.>` را نگه می‌دارد (`>` یعنی «هر subject زیر `orders.`»). هر پیام ذخیره‌شده یک شماره‌ی ترتیب می‌گیرد: ۱، ۲، ۳...
- **consumer** یک خواننده‌ی نام‌دار از یک stream است. به یاد می‌سپارد تا کجا خوانده، پس workerی که دوباره راه بیفتد از همان‌جا که ایستاده ادامه می‌دهد. مال ما {{< term "durable-consumer" "durable" >}} است (جایش را حتی وقتی هیچ برنامه‌ای وصل نیست حفظ می‌کند) و {{< term "pull-consumer" "pull" >}} (worker پیام می‌خواهد و سرور هلش نمی‌دهد).
- **ack** (تأیید) جواب worker بعد از رسیدگی به یک پیام است: «تمام شد». پیامی که ack نشود دوباره تحویل داده می‌شود. همین ترفند احتمال گم‌شدن را کم می‌کند. دو جواب دیگر هم هست: `nak` («شکست خورد، دوباره بفرست»، اگر بخواهید بعد از یک تأخیر) و `term` («دیگر هرگز نفرست»).

حالا کد.

## منتشر کردن و یک msgID تکراری

`connect` یک اتصال برمی‌گرداند. `jetstreamManager()` stream و consumer می‌سازد و `jetstream()` منتشر می‌کند و می‌خواند. این اسکریپت stream را می‌سازد و یک سفارش را دو بار با یک `msgID` منتشر می‌کند. سرور شناسه‌ی پیام‌ها را مدتی به یاد می‌سپارد که اسمش duplicate window است و پیام دومی را که شناسه‌اش را قبلاً دیده کنار می‌گذارد. من این پنجره را ۶۰ ثانیه گذاشتم:

```js
const nc = await connect({ servers: process.env.NATS_URL });
const jsm = await nc.jetstreamManager();
const js = nc.jetstream();
const si = await jsm.streams.add({ name: 'ORDERS', subjects: ['orders.>'], duplicate_window: nanos(60_000) });
const h = headers(); h.set('Trace-Id', 'abc-123');
const ack1 = await js.publish('orders.created', jc.encode({ id: 1, total: 42 }), { msgID: 'order-1', headers: h });
const ack2 = await js.publish('orders.created', jc.encode({ id: 1, total: 42 }), { msgID: 'order-1' });
console.log('ack1', ack1.stream, ack1.seq, ack1.duplicate);
console.log('ack2', ack2.stream, ack2.seq, ack2.duplicate);
```

(`jc` یک `JSONCodec()` است که شیء را به بایت و برعکس تبدیل می‌کند؛ `Trace-Id` یک header است، برچسب کوچکی که همراه پیام می‌رود.) خروجی:

```text
ack1 ORDERS 1 false
ack2 ORDERS 1 true
```

`js.publish` یک «publish ack» برمی‌گرداند با نام stream، شماره‌ی ترتیب و پرچم `duplicate`. اولین انتشار به‌عنوان پیام ۱ ذخیره شد. دومی همان شماره‌ی ترتیب و `duplicate: true` را گرفت: سرور شناسه را شناخت و چیز تازه‌ای ذخیره نکرد.

این فقط از سمت انتشار محافظت می‌کند. اگر یک‌بار منتشر کنید و worker پیام را دو بار بگیرد، `msgID` کمکی نمی‌کند. برای آن {{< term "idempotency" "خودتوان‌بودن" >}} (idempotency) در handler لازم است که در بخش تله‌ها دوباره به آن می‌رسیم.

## یک consumer ماندگار از نوع pull، و پیامی که برمی‌گردد

حالا یک consumer. ack صریح دارد (هر پیام را خودمان باید ack کنیم) و یک {{< term "ack-wait" "AckWait" >}} کوتاه یک‌ثانیه‌ای: سرور چقدر برای ack صبر کند تا پیام را دوباره تحویل دهد. اسکریپت consumer را با `consumers.get` می‌گیرد و یک پیام را با `next()` می‌خواند. عمداً اولین تحویل را ack نمی‌کند:

```js
await jsm.consumers.add('ORDERS', { durable_name: 'node-worker', ack_policy: AckPolicy.Explicit, ack_wait: nanos(1000) });
const c = await js.consumers.get('ORDERS', 'node-worker');
const m = await c.next({ expires: 2000 });
console.log('subject', m.subject, 'seq', m.seq, 'trace', m.headers.get('Trace-Id'));
console.log('via codec', jc.decode(m.data), '| via JSON.parse', JSON.parse(m.string()), '| m.json()', typeof m.json);
console.log('deliveryCount', m.info.deliveryCount, 'redelivered', m.redelivered);
// not acked on purpose: AckWait is 1s
const m2 = await c.next({ expires: 4000 });
console.log('again: deliveryCount', m2.info.deliveryCount, 'redelivered', m2.redelivered);
```

```text
consumer node-worker explicit
subject orders.created seq 1 trace abc-123
via codec { id: 1, total: 42 } | via JSON.parse { id: 1, total: 42 } | m.json() function
deliveryCount 1 redelivered false
again: deliveryCount 2 redelivered true
```

پیام اول همان subjectی را دارد که به آن منتشر کردیم، شماره‌ی ترتیب ۱ و headerی که گذاشتیم (`m.headers.get('Trace-Id')`). payload را هم با codec می‌شود decode کرد و هم با `JSON.parse(m.string())` ساده؛ هر دو همان شیء را می‌دهند، پس codec اختیاری است. دقت کنید که هیچ‌کدام بررسی نمی‌کنند شیء شکل درستی دارد. payload هنوز ورودیِ بیرونی است و مقاله‌ی بعد درباره‌ی همین است.

دو خط آخر اصل مطلب‌اند. تحویل اول `deliveryCount` برابر ۱ داشت. آن را ack نکردم و بعد از یک ثانیه سرور همان پیام را دوباره تحویل داد: `deliveryCount` برابر ۲ و `redelivered` برابر true. اگر یک worker وسط کار کرش کند دقیقاً همین اتفاق می‌افتد، و پیام این‌طور زنده می‌ماند.

## ack، nak، term و backoff

handlerهای واقعی بیشتر از «ack یا هیچ» لازم دارند. consumer بعدی حداکثر ۳ بار تحویل می‌دهد (`max_deliver: 3`) و بین تحویل‌های دوباره اول ۱۰۰ و بعد ۲۰۰ میلی‌ثانیه صبر می‌کند (`backoff`). از `deliver_policy: New` استفاده می‌کند، پس پیام‌های قدیمی stream را نادیده می‌گیرد و فقط آنچه بعد از ساخته‌شدنش منتشر شود می‌بیند. چهار پیام منتشر کردم و به هرکدام جواب متفاوتی دادم:

```js
if (name === 'paid') m.ack();
else if (name === 'flaky') n === 1 ? m.nak(100) : m.ack();
else if (name === 'poison') m.term();
// 'broken': never acked, the backoff decides when it comes back
```

یعنی `paid` ack می‌شود، `flaky` یک‌بار شکست می‌خورد و بار دوم موفق می‌شود (`nak(100)` یعنی «بعد از ۱۰۰ میلی‌ثانیه دوباره بفرست»)، `poison` متوقف می‌شود (term)، و به `broken` هیچ جوابی داده نمی‌شود. consumer چه دید؟

```text
paid    delivery 1
flaky   delivery 1
poison  delivery 1
broken  delivery 1
broken  delivery 2
flaky   delivery 2
broken  delivery 3
ack_pending 0 pending 0 redelivered 1
```

پیام‌به‌پیام بخوانید. `paid` و `poison` فقط یک‌بار آمدند و دیگر نیامدند: {{< term "acknowledgement" "تأیید" >}}، چه `ack` چه `term`، ماجرا را تمام می‌کند. `flaky` بعد از `nak` یک‌بار برگشت و ack شد. `broken` طبق برنامه‌ی backoff برمی‌گردد و در تحویل ۳ متوقف می‌شود، چون `max_deliver` برابر ۳ است. بعدش `ack_pending` و `pending` صفرند: چیزی منتظر جواب نیست. (عدد آخر شمارنده‌ی خود سرور برای تحویل دوباره است؛ به آن تکیه نمی‌کنم.) ترتیب خط‌های `flaky` و `broken` به زمان‌بندی بستگی دارد و ممکن است از اجرایی به اجرای دیگر فرق کند.

پیامی که همه‌ی تحویل‌هایش را مصرف کرده، دیگر به این consumer داده نمی‌شود. چیزی هم آن را جایی نمی‌برد. {{< term "dlq" "صف نامه‌های مرده" >}} (dead-letter queue)، جایی که پیام‌های شکست‌خورده برای بررسی یک آدم کنار گذاشته می‌شوند، چیزی است که خودتان می‌سازید، مثل مقاله‌ی retry.

## خاموشی تمیز با drain

workerی که وسط یک کار کشته شود پیامی را بدون ack رها می‌کند؛ پس پیام دوباره تحویل می‌شود و ممکن است کار دو بار اجرا شود. {{< term "graceful-shutdown" "خاموشی تمیز" >}} این را جلو می‌گیرد: با `SIGTERM` worker گرفتن پیام تازه را متوقف می‌کند، می‌گذارد کار در حال اجرا تمام شود و بعد `drain()` را صدا می‌زند. طبق مستندات nats.js، `drain()` می‌گذارد پیام‌هایی که در حال پردازش‌اند و داده‌ای که منتظر ارسال است عبور کنند و بعد اتصال بسته شود.

```js
process.once('SIGTERM', async () => {
  it.stop();
  await inflight;
  await nc.drain();
  process.exit(0);
});
```

`it.stop()` گرفتن پیام را متوقف می‌کند، `await inflight` منتظر کار فعلی می‌ماند و `drain()` اتصال را تمیز می‌بندد. اسکریپت یک پیام به اسم `job-1` را پردازش می‌کند که یک کار ساختگی ۱٫۵ ثانیه‌ای است. اجرایش کردم، وقتی کار در جریان بود `SIGTERM` فرستادم و خروجی این بود:

```text
start job-1
SIGTERM: stop fetching
acked job-1
in-flight done, draining
closed
exit code 0
```

سیگنال بعد از شروع `job-1` رسید. worker گرفتن پیام را متوقف کرد ولی کار باز هم تمام و ack شد، بعد اتصال drain شد و process با کد ۰ بیرون رفت. این همان ایده‌ی مقاله‌ی Go است که این‌جا به‌جای context با [event loop](/fa/posts/node-event-loop/) و [promise](/fa/posts/node-promises-async-await/) در Node ساخته شده.

## Node و Go روی یک stream

پیام‌ها فقط بایت‌اند به‌اضافه‌ی header، پس زبان کلاینت اهمیتی ندارد. Node پیام `{"id":7,"total":99}` را با header به اسم `Trace-Id` به `orders.interop` منتشر کرد و بعد یک برنامه‌ی کوچک Go با nats.go آن را گرفت:

```text
node published ORDERS 7
go got subject=orders.interop data={"id":7,"total":99} header[Trace-Id]=abc-123 stream_seq=7
```

شماره‌ی ترتیب ۷ است چون اسکریپت‌های قبلی همین مقاله شش پیام در همین stream گذاشته بودند. داده و header بدون تغییر رسیدند.

## مقایسه با nats.go

چیزهایی که از آن‌ها مطمئنم: nats.go هم `js.Publish` و `PullSubscribe` با `Fetch` دارد و ack‌ها متد خود پیام‌اند (`Ack`، `Nak`، `Term`)، مثل این‌جا. در Node همه‌چیز promise برمی‌گرداند و `consume()` یک async iterator است که با `for await` می‌خوانید. کلیدهای تنظیمات از snake_case خود سرور پیروی می‌کنند (`max_deliver`، `ack_wait`) و مدت‌ها بر حسب نانوثانیه‌اند؛ برای همین اسکریپت‌ها از تابع کمکی `nanos()` استفاده می‌کنند.

## چطور پیام‌ها دور می‌زنند یا ناپدید می‌شوند

- **بدون سقف تحویل.** همیشه `max_deliver` محدود و یک `backoff` بگذارید، وگرنه پیامی که همیشه شکست می‌خورد تا ابد دوباره امتحان می‌شود.
- **ackی که شاید نرسد.** `m.ack()` را می‌فرستد و رها می‌کند. اگر باید بدانید سرور آن را گرفته، از `await m.ackAck()` استفاده کنید.
- **handlerی که throw می‌کند.** handler از نوع `async` که بدون catch خطا بدهد به unhandled rejection تبدیل می‌شود و می‌تواند worker را بیندازد. [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/) را ببینید.
- **بستن با عجله.** پیش از `process.exit` از `drain()` استفاده کنید، نه `close()`، تا ack‌ها و کار در جریان نیمه‌کاره نمانند.
- **تکراری‌ها.** یک پیام ممکن است بیش از یک بار برسد، ویژگی‌ای به اسم {{< term "at-least-once-delivery" "تحویل at-least-once" >}}؛ پس handler را خودتوان کنید: دوبار انجام‌دادن باید اثری مثل یک‌بار داشته باشد.

## تمرین

handlerی بنویسید که وقتی `m.info.deliveryCount` به سقف رسید، پیام را به `orders.dlq` منتشر کند و بعد `term()` صدا بزند. با یک consumer دوم بررسی کنید که نامه‌ی مرده رسیده است.

## قدم بعدی

مقاله‌ی بعد «اعتبارسنجی ورودی با Zod» است. payloadی که از یک stream می‌رسد هنوز ورودی بیرونی است و آن مقاله نشان می‌دهد پیش از استفاده چطور بررسی‌اش کنیم.
