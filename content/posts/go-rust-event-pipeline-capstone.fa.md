+++
date = '2027-03-08T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS'
seoTitle = 'Pipeline رویدادمحور با Go، Rust و NATS'
description = 'Postgres، الگوی outbox، JetStream، یک worker با Rust و یک read model در NATS KV را به هم وصل می‌کنیم و بعد اجزا را می‌کشیم تا ببینیم نتیجه درست می‌ماند.'
contentType = 'engineering'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "nats", "jetstream", "outbox", "capstone", "postgres"]
cover = { image = "/images/covers/go-rust-event-pipeline-capstone.fa.png", alt = "پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS", hiddenInSingle = true }
+++

مشتری یک سفارش می‌فرستد. سیستم شما جواب می‌دهد «پذیرفته شد». درست بعد از آن چیزی crash می‌کند: پروسه‌ای که سفارش‌ها را ذخیره می‌کند، پروسه‌ای که رویداد را منتشر می‌کند، یا worker که قیمت را حساب می‌کند. وقتی دوباره همه‌چیز اجرا می‌شود، کدام‌یک از این‌ها هنوز باید درست باشد؟

- سفارش پذیرفته‌شده گم نشده است.
- قیمت یک بار حساب و اعمال شده، نه دو بار، حتی اگر یک پیام دو بار تحویل شود.
- مشتری می‌تواند بپرسد «وضعیت سفارش من چیست؟» و جواب درست بگیرد.

این نوشته آخرین نوشته‌ی سری Go و Rust است و دور همین پرسش ساخته شده. در طول سال قطعه‌ها را یکی‌یکی ساختیم. این‌جا کنار هم می‌گذارمشان: سرویس‌های Go در لبه‌ها، یک worker به زبان Rust که قاعده‌ی کسب‌وکار را دارد، و NATS در میانه. هیچ چیزش فناوری تازه نیست. مقصود این است که **قطعه‌ها چطور به هم جفت می‌شوند و وقتی یکی می‌میرد چه می‌شود.** همه‌چیز را با یک اسکریپت به اسم `run.sh` راه می‌اندازم و بعد عمداً قطعه‌ها را می‌کشم.

سری تا این‌جا از [Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) (یک فراخوانی شبکه‌ای بین دو زبان) به [گذاشتن Rust داخل پردازه‌ی Go](/fa/posts/go-calls-rust-ffi/) (یک فراخوانی کتابخانه‌ای) رسید. پروژه‌ی پایانی از هیچ‌کدام استفاده نمی‌کند. دو زبان را با پیام به هم وصل می‌کند، که سومین راه رایج است.

> همه‌چیز را دوباره با Go 1.27، Rust 1.90، Postgres 18.3 (با launcherی که آن را توکار می‌کند)، nats-server 2.15.1 توکار در یک برنامه‌ی Go و macOS (arm64) اجرا کردم. این یک دموست: یک node، بدون احراز هویت و بدون TLS. در [JetStream در production](/fa/posts/nats-jetstream-production/) آمده که یک استقرار واقعی چه چیزهایی لازم دارد. دمو پورت‌هایش را ثابت نوشته، پس یک نسخه‌ی کپی را با پورت‌های آزاد اجرا کردم و پایین‌تر `<port>` می‌نویسم. زمان‌بندی در نوشته نیست.

## نقشه

پنج برنامه داریم. چهارتا Go هستند (یک باینری با چند زیرفرمان؛ زیرفرمان پنجم، `report`، فقط می‌شمارد چه چیزی ذخیره شده) و یکی Rust:

| برنامه | زبان | تنها کارش |
|---|---|---|
| `infra` | Go | Postgres و NATS را بالا می‌آورد و streamها و KV bucket را می‌سازد. |
| `api` | Go | `POST /orders` را می‌پذیرد و `GET /orders/{id}/status` را جواب می‌دهد. |
| `relay` | Go | رویدادها را از جدول `outbox` در Postgres به NATS می‌برد. |
| `pricer` | Rust | رویداد سفارش را می‌خواند، قاعده‌ی کسب‌وکار را اعمال می‌کند و نتیجه را منتشر می‌کند. |
| `projector` | Go | نتیجه‌ها را می‌خواند و آخرین وضعیت هر سفارش را در NATS KV نگه می‌دارد. |

و جریان داده بینشان این است:

```text
 curl POST /orders
        |
   [Go api] --one tx--> Postgres: orders + outbox
                                    |
                       [Go relay] polls outbox
                                    | Nats-Msg-Id = outbox-<id>
                                    v
                         stream ORDERS (orders.created)
                                    |
                    [Rust pricer] pull consumer, validates + prices
                                    | Nats-Msg-Id = priced-<order>
                                    v
                 stream RESULTS (results.priced.<order>)
                                    |
                      [Go projector] consumer
                                    v
                     KV bucket ORDER_STATUS
                                    ^
 curl GET /orders/{id}/status ---[Go api]
```

یک سفارش را از سمت چپ پایین دنبال کنید. API آن را در Postgres می‌نویسد. relay برش می‌دارد و یک رویداد در stream به اسم `ORDERS` منتشر می‌کند. pricer مربوط به Rust آن رویداد را می‌خواند، قیمت را تعیین می‌کند و نتیجه را در stream به اسم `RESULTS` منتشر می‌کند. projector نتیجه را به یک bucket کلید-مقدار کپی می‌کند. و وقتی مشتری می‌پرسد، API وضعیت را از همان bucket می‌خواند.

چرا این‌همه گام؟ چون هر گام یک شکست را قابل‌تحمل می‌کند، که بخش بعد نشان می‌دهد. **stream** در {{< term "jetstream" "JetStream" >}} (لایه‌ی ماندگار NATS) لاگی از پیام‌هاست که روی دیسک ذخیره می‌شود؛ دمو هر دو stream و bucket را روی **file storage** گذاشته تا بعد از راه‌اندازی دوباره بمانند.

قطعه‌ها از نوشته‌های قبل می‌آیند: تراکنش و relay از [مقاله‌ی outbox](/fa/posts/go-outbox-pattern-nats/) با [pgx](/fa/posts/go-postgres-pgx-sqlc/)، مصرف‌کننده‌ی async از [کلاینت async NATS در Rust](/fa/posts/rust-nats-async-client/)، bucket از [KV و Object Store](/fa/posts/nats-kv-object-store/) و مدیریت سیگنال مثل [graceful shutdown](/fa/posts/go-graceful-shutdown-workers/).

## سه ایده که این را سرپا نگه می‌دارند

پیش از کد، سه ایده، هرکدام در یک بند:

۱. **outbox.** API نمی‌تواند در یک تراکنش هم در Postgres و هم در NATS بنویسد، چون هیچ تراکنشی هر دو را در بر نمی‌گیرد. پس سفارش *و* یک ردیف رویداد را در یک تراکنش در Postgres می‌نویسد. بعداً یک پروسه‌ی جدا (relay) آن ردیف را منتشر می‌کند. این همان {{< term "outbox-pattern" "الگوی outbox" >}} است.
۲. **تحویل at-least-once.** اگر مصرف‌کننده پیامی را به‌موقع تأیید (ack) نکند، JetStream دوباره می‌فرستدش. این خوب است: چیزی گم نمی‌شود. ولی ممکن است یک پیام دو بار برسد. این {{< term "at-least-once-delivery" "تحویل at-least-once" >}} است.
۳. **گام‌های idempotent.** به‌خاطر ایده‌ی دوم، هر گام باید تکرارش بی‌خطر باشد. این {{< term "idempotency" "idempotency" >}} است. «دقیقاً یک بار» را از broker نمی‌گیریم؛ آن را از گام‌هایی می‌سازیم که تکرارشان همان نتیجه را می‌دهد، و تکراری‌ها را با شناسه‌ی پیام حذف می‌کنیم.

## سمت نوشتن: یک تراکنش

API هرگز با NATS حرف نمی‌زند. سفارش و رویداد را با هم می‌نویسد، پس یا هر دو هستند یا هیچ‌کدام:

```go
err := pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
	if _, err := tx.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ($1,$2,$3)`,
		in.ID, in.Customer, in.Cents); err != nil {
		return err
	}
	payload, _ := json.Marshal(map[string]any{"order_id": in.ID, "cents": in.Cents})
	_, err := tx.Exec(ctx, `INSERT INTO outbox (payload) VALUES ($1)`, payload)
	return err
})
```

relay در یک حلقه اجرا می‌شود، با یک تراکنش برای هر دسته. ردیف‌های منتشرنشده را با `FOR UPDATE SKIP LOCKED` برمی‌دارد ({{< term "skip-locked" "skip locked" >}}: ردیف‌هایی که relay دیگری قفل کرده رد می‌شوند، پس دو relay ردیف‌های یکسان برنمی‌دارند). هر ردیف را با شناسه‌ی پیام `outbox-<id>` منتشر می‌کند و فقط بعد از آن `UPDATE outbox SET published_at` را اجرا می‌کند. فاصله‌ی بین «منتشر شد» و «علامت منتشرشده خورد» جایی است که ممکن است بمیرد، و دقیقاً همان را آزمایش می‌کنیم.

## worker مربوط به Rust

قاعده‌ی کسب‌وکار یک تابع خالص است: سفارش داخل می‌رود و نتیجه بیرون می‌آید. این آزمودنش را آسان می‌کند و ربطی به NATS ندارد:

```rust
fn price(o: &Order) -> Priced {
    if o.cents <= 0 || o.cents > 1_000_000 {
        return Priced { order_id: o.order_id.clone(), status: "rejected", total_cents: 0, checksum: String::new() };
    }
    let total = o.cents + (o.cents * 9 + 50) / 100; // 9% tax, rounded
    let checksum = format!("{:08x}", fnv1a(format!("{}:{}", o.order_id, total).as_bytes()));
    Priced { order_id: o.order_id.clone(), status: "priced", total_cents: total, checksum }
}
```

سفارشی با مبلغ صفر یا کمتر، یا بیشتر از ۱٬۰۰۰٬۰۰۰ سنت، رد می‌شود. در غیر این صورت worker ۹٪ مالیات را گردشده به نزدیک‌ترین سنت اضافه می‌کند و یک checksum کوچک می‌چسباند تا بعداً بتوانیم نتیجه‌ها را مقایسه کنیم.

دور این تابع، حلقه‌ی worker از یک {{< term "pull-consumer" "pull consumer" >}} پیام می‌خواند (worker پیام می‌خواهد و سرور فشارش نمی‌دهد). برای هر پیام سه کار می‌کند: اگر سفارش از قبل نتیجه دارد آن را رد می‌کند، نتیجه را با شناسه‌ی پیام خودش منتشر می‌کند و فقط بعد از تأیید publish ack می‌زند:

```rust
let subject = format!("results.priced.{}", order.order_id);
if results.get_last_raw_message_by_subject(&subject).await.is_ok() {
    msg.ack().await.map_err(|e| anyhow!("{e}"))?; // already processed
    continue;
}
// ... price, publish_with_headers(subject, Nats-Msg-Id: priced-<id>).await?.await?;
msg.ack().await.map_err(|e| anyhow!("{e}"))?;
```

subject شناسه‌ی سفارش را دارد، پس پرسش «آیا این سفارش نتیجه دارد؟» جست‌وجو در خود stream است، نه در حافظه‌ی worker. این مهم است: workerای که کشته و دوباره راه‌اندازی شده حافظه ندارد، ولی stream به یاد دارد. این همان ایده‌ی [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) است. {{< term "ack-wait" "ack wait" >}} مصرف‌کننده ۵ ثانیه است: اگر worker در این مدت ack نزند، JetStream پیام را دوباره تحویل می‌دهد.

projector آخرین گام است. برای هر نتیجه `kv.Put(orderID, result)` می‌زند و ack می‌کند. گذاشتن یک مقدار یکسان دو بار چیزی را عوض نمی‌کند، پس این گام تکرارش بی‌خطر است.

## مسیر خوشحال

اول هیچ‌چیز شکست نمی‌خورد. دو سفارش می‌فرستم و وضعیتشان را می‌خوانم. سفارش دوم از سقف بیشتر است، پس باید رد شود. بعد `o-1` را بار دوم می‌فرستم. (`curl` و خروجی مثل `run.sh` است، با پورت حذف‌شده.)

```text
$ curl -X POST localhost:<port>/orders -d '{"id":"o-1","customer":"ali","cents":2500}'
{"id":"o-1","accepted":true}
$ curl localhost:<port>/orders/o-1/status
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
$ curl -X POST localhost:<port>/orders -d '{"id":"o-2","customer":"sara","cents":5000000}'
$ curl localhost:<port>/orders/o-2/status
{"order_id":"o-2","status":"rejected","total_cents":0,"checksum":""}
```

۲۵۰۰ به‌علاوه‌ی ۹٪ می‌شود ۲۷۲۵، همان‌طور که انتظار داشتیم. سفارش دوم را قاعده‌ی Rust رد می‌کند. فرستادن دوباره‌ی `o-1` از Postgres خطا می‌گیرد (`duplicate key value violates unique constraint "orders_pkey"`) که API آن را به 409 تبدیل می‌کند، و هیچ ردیف outbox ساخته نمی‌شود چون تراکنش برگشت خورد. بعد فرمان `report` همه‌چیز را در Postgres و NATS می‌شمارد:

```text
report: orders=2 outbox=2 (unpublished=0) ORDERS msgs=2 RESULTS msgs=2 KV keys=2
```

دو سفارش، دو ردیف outbox (هیچ‌کدام منتظر نیست)، دو رویداد، دو نتیجه و دو کلید. بعد از هر شکست همین خط را مقایسه می‌کنیم.

## کشتن worker وسط پیام

حالا اولین شکست. worker یک کلید آزمایشی دارد: با `STALL=before` بعد از گرفتن پیام و پیش از publish می‌خوابد تا لحظه‌ی امنی برای کشتنش داشته باشم. چنین workerای را راه می‌اندازم، `o-3` را می‌فرستم و تا وقتی پیام دستش است `kill -9` می‌کنمش. بعد وضعیت را می‌پرسم: هنوز چیزی نیست. بعد یک worker عادی راه می‌اندازم:

```text
killed worker2 (SIGKILL)
{"id":"o-3","status":"unknown"}
(a normal worker is started; the message is redelivered once the 5 s ack wait expires)
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
```

خط‌های لاگ خود worker نشان می‌دهند چه دیده است:

```text
worker: stalling before publish, kill me now
worker: o-3 delivered=2 -> priced total=1090
```

پیام دو بار تحویل شد (`delivered=2`): بار اول به workerای که مُرد و بار دوم به worker تازه. یک بار پردازش شد. جمع، ۱۰۹۰، همان ۱۰۰۰ به‌علاوه‌ی ۹٪ است. (در زمان‌های لاگ اجرای من، نتیجه‌ی `o-3` حدود پنج ثانیه بعد از انتشار آن توسط relay آمد، که با ack wait پنج‌ثانیه‌ای جور است.)

حالت سخت‌تر `STALL=after` است: worker نتیجه‌ی `o-4` را منتشر می‌کند و پیش از ack می‌میرد. حالا نتیجه از قبل هست و پیام هنوز دوباره تحویل می‌شود. worker بعدی چه باید بکند؟ نباید دوباره منتشر کند:

```text
worker: o-4 delivered=1 -> priced total=1089
worker: stalling after publish, kill me now
--- worker killed, a new worker started ---
worker: o-4 delivered=2 already processed, skipping
report: orders=4 outbox=4 (unpublished=0) ORDERS msgs=4 RESULTS msgs=4 KV keys=4
```

worker اول منتشر کرد و خوابید. worker تازه پیام را بار دوم گرفت (`delivered=2`)، نتیجه‌ی موجود `o-4` را در stream به اسم `RESULTS` پیدا کرد و ردش کرد. گزارش چهار سفارش و چهار نتیجه می‌گوید: تحویل دوباره رخ داد، ولی اثر یک بار اعمال شد.

## کشتن relay بین publish و علامت‌زدن

حالا طرف دیگر. `CRASH_AFTER_PUBLISH=1` باعث می‌شود relay درست بعد از موفقیت publish و پیش از به‌روزرسانی دیتابیس خارج شود. Postgres هنوز ردیف را منتشرنشده نشان می‌دهد، در حالی که NATS رویداد را دارد:

```text
relay: outbox id=5 published seq=5 duplicate=false
relay: CRASH between publish and mark-published
report: orders=5 outbox=5 (unpublished=1) ORDERS msgs=5 ...
--- normal relay started ---
relay: outbox id=5 published seq=5 duplicate=true
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

`report` وسط حالت خطرناک را نشان می‌دهد: یک ردیف منتشرنشده، در حالی که stream الان ۵ رویداد دارد. یک relay عادی بالا می‌آید، ردیف را منتشرنشده می‌بیند و دوباره منتشرش می‌کند. این بار NATS با `duplicate=true` و همان شماره‌ی ترتیب ۵ جواب می‌دهد. stream شناسه‌ی پیام `outbox-5` را شناخت و نسخه‌ی دوم را دور ریخت. پس pricer هرگز `o-5` را دو بار نمی‌بیند و گزارش نهایی یکدست است.

## راه‌اندازی دوباره‌ی همه‌چیز

آخر، کل سیستم. API، relay، projector و worker را متوقف کردم، بعد خود `infra` را هم متوقف کردم و دوباره روی همان پوشه‌ی داده بالا آوردم. اگر داده فقط در حافظه بود، از بین رفته بود:

```text
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
{"order_id":"o-5","status":"priced","total_cents":4578,"checksum":"7d5392b2"}
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

وضعیت‌ها و شمارش‌ها مثل پیش از راه‌اندازی دوباره‌اند: Postgres ردیف‌هایش را نگه داشت و JetStream فایل‌هایش را. بعد یک سفارش تازه به اسم `o-6` (۱۰۰ سنت، با قیمت ۱۰۹) مثل همیشه از همه‌ی مرحله‌ها گذشت و آخرین گزارش از هر چیز شش تا می‌گفت.

## محدودیت‌های این طراحی

- **بررسی «قبلاً پردازش شده» از نوع check-then-act است.** اگر چند worker روی یک سفارش باشند، دو تا از آن‌ها می‌توانند پیش از اینکه هرکدام منتشر کند هر دو از بررسی رد شوند. شناسه‌ی پیام `priced-<order>` و پنجره‌ی حذف تکراری stream (این‌جا ۵ دقیقه) تا مدتی این را پوشش می‌دهد، ولی راه‌حل واقعی یک کلید یکتا در انبار خودتان است.
- **همه‌چیز at-least-once است.** درستی از گام‌های idempotent می‌آید، نه از کلیدی به اسم «دقیقاً یک بار».
- **`ack_wait` زمان بازیابی را تعیین می‌کند.** بازیابی بعد از crash کردن worker منتظر آن می‌ماند، پس آن را نسبت به کندترین پیامتان تنظیم کنید: خیلی کوتاه باشد پیام‌های کند دو بار تحویل می‌شوند و خیلی بلند باشد بازیابی کند است.
- **این دمو چیزی درباره‌ی سرعت اندازه نمی‌گیرد.** نه متریکی دارد و نه عدد throughput. پیش از اعتماد به آن زیر بار واقعی، متریک‌های [observability برای JetStream](/fa/posts/nats-jetstream-observability/) را اضافه کنید.
- **پیام جواب نیست.** NATS بین سرویس‌ها ماندگاری و تحویل دوباره می‌خرد، ولی فراخواننده‌ی `POST /orders` فقط می‌فهمد «پذیرفته شد». اگر جواب هم‌زمان لازم دارید، از gRPC استفاده کنید، مثل [Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/).

## قدم بعدی

این نوشته سری Go و Rust را می‌بندد. قدم بعدی در تقویم «Docker، CI و release سرویس Rust» است که یک سرویس Rust را فراتر از اجرای محلی مثل این‌جا می‌برد.
