+++
date = '2027-02-27T10:00:00+03:30'
draft = false
title = 'NATS JetStream از Node.js'
description = 'NATS JetStream از Node.js: publish با msgID، pull consumer ماندگار، ack، nak، term، backoff، drain تمیز و تعامل با Go، همه با اجرای واقعی.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "nats", "jetstream", "messaging", "graceful-shutdown"]
cover = { image = "/images/covers/node-nats-jetstream.fa.png", alt = "NATS JetStream از Node.js", hiddenInSingle = true }
+++

در مقاله‌ی قبل، [Postgres از Node.js با pg](/fa/posts/node-postgres-pg/)، با دیتابیس حرف زدیم. حالا ستون دوم یک backend: پیام‌رسانی. از Node.js سراغ **{{< term "jetstream" "JetStream" >}}** می‌روم و با [یک Publisher و Worker ساده با NATS JetStream در Go](/fa/posts/nats-jetstream-go/) مقایسه می‌کنم. ایده‌ها همان‌هایی است که در [Retry و Dead-Letter Queue](/fa/posts/nats-jetstream-retry-dlq/)، [Idempotency](/fa/posts/nats-jetstream-idempotency/)، [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) و [کلاینت async NATS JetStream در Rust](/fa/posts/rust-nats-async-client/) دیدیم؛ فقط کلاینت عوض می‌شود.

> Node نسخه‌ی v20.13.1، `nats` نسخه‌ی 2.29.3 (در `package.json` آن Node >= 14 خواسته شده). سرور یک برنامه‌ی کوچک Go با nats-server توکار است که جدا و روی 127.0.0.1 اجرا شد. اسکریپت‌ها مثال محلی‌اند، خروجی‌ها واقعی‌اند و زمان‌بندی نگرفته‌ام.

## Publish و دو بار msgID یکسان

`connect` اتصال را می‌دهد، `jetstreamManager()` stream و consumer می‌سازد و `jetstream()` publish و consume می‌کند. با `msgID` سرور تکراری‌ها را در بازه‌ی duplicate window خود stream دور می‌ریزد:

```js
const nc = await connect({ servers: process.env.NATS_URL });
const jsm = await nc.jetstreamManager();
const js = nc.jetstream();
await jsm.streams.add({ name: 'ORDERS', subjects: ['orders.>'] });
const h = headers(); h.set('Trace-Id', 'abc-123');
const a1 = await js.publish('orders.created', jc.encode({ id: 1 }), { msgID: 'order-1', headers: h });
const a2 = await js.publish('orders.created', jc.encode({ id: 1 }), { msgID: 'order-1' });
console.log(a1.stream, a1.seq, a1.duplicate, a2.seq, a2.duplicate);
```

```text
ORDERS 1 false 1 true
```

PubAck سه فیلد `stream`، `seq` و `duplicate` دارد. publish دوم همان شماره‌ی ترتیب را گرفت و `duplicate: true` بود. این فقط محافظ سمت publish است و **{{< term "idempotency" "idempotency" >}}** کامل نیست؛ consumer باید باز هم تحمل ارسال دوباره را داشته باشد.

## یک pull consumer ماندگار

یک **{{< term "pull-consumer" "pull consumer" >}}** {{< term "durable-consumer" "ماندگار" >}} با ack صریح و **{{< term "ack-wait" "AckWait" >}}** کوتاه ساخته شد و با `consumers.get` و `next()` پیام گرفتیم:

```text
subject orders.created seq 1 trace abc-123
via codec { id: 1, total: 42 } | via JSON.parse { id: 1, total: 42 }
deliveryCount 1 redelivered false
again: deliveryCount 2 redelivered true
```

عمداً اولین تحویل را ack نکردم. بعد از AckWait همان پیام با `deliveryCount` برابر ۲ و `redelivered` برابر true برگشت. headerها با `m.headers.get(...)` خوانده می‌شوند. این نسخه `JSONCodec` دارد، اما `JSON.parse(m.string())` همان شیء را می‌دهد؛ پس codec اختیاری است. هیچ‌کدام اعتبارسنجی نمی‌کنند: payload هنوز ورودی غیرقابل‌اعتماد است (مقاله‌ی بعد درباره‌ی همین است).

## ack، nak، term و backoff

consumer مقدار `max_deliver: 3` و `backoff` با ۱۰۰ و سپس ۲۰۰ میلی‌ثانیه داشت. چهار پیام فرستادم و هرکدام را جور دیگری مدیریت کردم: `ack`، در بار اول `nak(100)`، `term()` و بدون هیچ پاسخی:

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

**{{< term "acknowledgement" "تأیید دریافت" >}}** سرنوشت پیام را تعیین می‌کند: `paid` و `poison` دیگر دیده نشدند؛ `flaky` بعد از `nak` یک بار برگشت و ack شد؛ `broken` طبق برنامه‌ی backoff برگشت و به‌خاطر `max_deliver` در تحویل سوم تمام شد. بعد از آن چیزی pending نبود. ترتیب خط‌های `flaky` و `broken` به زمان‌بندی بستگی دارد، پس رویش حساب نکنید. مثل مقاله‌ی retry، پیامی که تحویل‌هایش تمام شود خودبه‌خود جایی نگه داشته نمی‌شود؛ {{< term "dlq" "DLQ" >}} چیزی است که خودتان دورش می‌سازید.

## خاموشی تمیز با drain

با SIGTERM، worker دریافت را متوقف می‌کند، منتظر کار در حال اجرا می‌ماند و بعد `drain()` را صدا می‌زند که ackهای معلق را flush و سپس اتصال را می‌بندد:

```js
process.once('SIGTERM', async () => {
  it.stop();
  await inflight;
  await nc.drain();
  process.exit(0);
});
```

```text
start job-1
SIGTERM: stop fetching
acked job-1
in-flight done, draining
closed
exit code 0
```

سیگنال وسط اجرای `job-1` (یک کار ساختگی ۱٫۵ ثانیه‌ای) رسید، کار تمام و ack شد و exit code برابر ۰ بود. ایده‌ی همان **{{< term "graceful-shutdown" "خاموشی تمیز" >}}** مقاله‌ی Go است، این بار با [event loop](/fa/posts/node-event-loop/) و [promiseهای](/fa/posts/node-promises-async-await/) Node به‌جای context.

## تعامل با Go

Node پیام `{"id":7,"total":99}` را با header به نام `Trace-Id` روی `orders.interop` publish کرد و یک برنامه‌ی کوتاه Go با nats.go آن را گرفت:

```text
node published ORDERS 7
go got subject=orders.interop data={"id":7,"total":99} header[Trace-Id]=abc-123 stream_seq=7
```

آنچه روی سیم می‌رود فقط بایت و header است، پس زبان مهم نیست.

## مقایسه با nats.go

چیزهایی که مطمئنم: nats.go هم `js.Publish` و `PullSubscribe` با `Fetch` دارد و ack متد خود پیام است (`Ack`، `Nak`، `Term`)، مثل اینجا. در Node همه‌چیز Promise برمی‌گرداند و `consume()` یک async iterator است؛ کلیدهای کانفیگ snake_case سرور هستند (`max_deliver`، `ack_wait`) و مدت‌ها بر حسب نانوثانیه‌اند، پس از helper به نام `nanos()` استفاده کنید.

## چند نکته‌ی مهم

- همیشه `max_deliver` محدود و `backoff` بگذارید، وگرنه پیام خراب تا ابد می‌چرخد.
- `m.ack()` بدون انتظار است؛ `await m.ackAck()` تأیید می‌کند سرور آن را گرفته.
- نگذارید handler از نوع `async` بی‌صدا خطا بدهد: [خطا و unhandled rejection در Node.js](/fa/posts/node-errors-unhandled-rejections/) را ببینید.
- قبل از `process.exit` حتماً `drain()`، نه `close()` عجولانه.
- ارسال تکراری ممکن است، پس handlerها را idempotent کنید.

## تمرین

handlerی بنویسید که وقتی `m.info.deliveryCount` به سقف رسید، پیام را روی `orders.dlq` publish و بعد `term()` کند. با یک consumer دوم بررسی کنید که dead letter رسیده است.

## قدم بعدی

مقاله‌ی بعدی «اعتبارسنجی ورودی با Zod» است.
