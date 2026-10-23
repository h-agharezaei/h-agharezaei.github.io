+++
date = '2027-03-08T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS'
seoTitle = 'Pipeline رویدادمحور با Go، Rust و NATS'
description = 'Postgres، الگوی outbox، JetStream، یک worker با Rust و یک read model در NATS KV را به هم وصل می‌کنیم و بعد اجزا را می‌کشیم تا ببینیم نتیجه درست می‌ماند.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "nats", "jetstream", "outbox", "capstone", "postgres"]
cover = { image = "/images/covers/go-rust-event-pipeline-capstone.fa.png", alt = "پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبلی](/fa/posts/go-calls-rust-ffi/) Rust را داخل پردازه‌ی Go گذاشت. این آخرین مقاله‌ی سری، قطعه‌های کل این مجموعه را کنار هم می‌گذارد: سرویس‌های Go در لبه‌ها، یک worker با Rust برای قانون کسب‌وکار، و NATS در وسط. هیچ‌چیز تازه‌ای نیست؛ موضوع این است که اجزا چطور به هم وصل می‌شوند و وقتی یکی می‌میرد چه می‌شود. همه را با یک `run.sh` اجرا می‌کنم و بعد عمداً خرابش می‌کنم.

> Go 1.26، Rust 1.90، Postgres 18.3 (با launcher توکار)، nats-server 2.15 توکار، macOS arm64. همه‌چیز محلی اجرا شده است. این یک دموست: یک node، بدون auth و بدون TLS. در [JetStream در production](/fa/posts/nats-jetstream-production/) آمده که یک استقرار واقعی چه لازم دارد.

## شکل کلی

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

قطعه‌هایی که دوباره استفاده می‌کنم: تراکنش و relay از [مقاله‌ی outbox](/fa/posts/go-outbox-pattern-nats/) با [pgx](/fa/posts/go-postgres-pgx-sqlc/)، consumer ناهمگام از [کلاینت async NATS در Rust](/fa/posts/rust-nats-async-client/)، bucket از [KV و Object Store](/fa/posts/nats-kv-object-store/) و مدیریت signal مثل [graceful shutdown](/fa/posts/go-graceful-shutdown-workers/). دستور `infra` هم Postgres و هم NATS را روی پوشه‌های داده‌ی ثابت بالا می‌آورد و هر دو stream و bucket روی **file storage** هستند.

## سمت نوشتن: یک تراکنش

API هیچ‌وقت با NATS حرف نمی‌زند. سفارش و رویداد را با هم می‌نویسد، پس یا هر دو هستند یا هیچ‌کدام:

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

relay ردیف‌های منتشرنشده را با `FOR UPDATE SKIP LOCKED` می‌خواند، هرکدام را با `Nats-Msg-Id` برابر `outbox-<id>` publish می‌کند و فقط بعد از آن `UPDATE outbox SET published_at` را اجرا می‌کند. همان فاصله جایی است که ممکن است بمیرد.

## worker با Rust

قانون کسب‌وکار یک تابع خالص است؛ تست‌کردنش آسان است و ربطی به NATS ندارد:

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

دور آن، حلقه سه کار می‌کند: سفارش‌هایی را که قبلاً نتیجه داده‌اند رد می‌کند، نتیجه را با `Nats-Msg-Id` خودش publish می‌کند و فقط بعد از تأیید publish ack می‌زند:

```rust
let subject = format!("results.priced.{}", order.order_id);
if results.get_last_raw_message_by_subject(&subject).await.is_ok() {
    msg.ack().await.map_err(|e| anyhow!("{e}"))?; // already processed
    continue;
}
// ... price, publish_with_headers(subject, Nats-Msg-Id: priced-<id>).await?.await?;
msg.ack().await.map_err(|e| anyhow!("{e}"))?;
```

subject شامل شناسه‌ی سفارش است، پس پرسش «این سفارش نتیجه دارد؟» یک جست‌وجو در خود stream است و به حافظه‌ی worker وابسته نیست. این همان ایده‌ی [idempotency در JetStream](/fa/posts/nats-jetstream-idempotency/) است. projector آخرین مرحله است: برای هر نتیجه `kv.Put(orderID, result)` می‌زند و ack می‌کند. دو بار نوشتن همان مقدار بی‌ضرر است.

## مسیر موفق

```text
$ curl -X POST localhost:18080/orders -d '{"id":"o-1","customer":"ali","cents":2500}'
{"id":"o-1","accepted":true}
$ curl localhost:18080/orders/o-1/status
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
$ curl -X POST localhost:18080/orders -d '{"id":"o-2","customer":"sara","cents":5000000}'
$ curl localhost:18080/orders/o-2/status
{"order_id":"o-2","status":"rejected","total_cents":0,"checksum":""}
```

۲۵۰۰ به‌علاوه‌ی ۹ درصد می‌شود ۲۷۲۵. ارسال دوباره‌ی `o-1` از Postgres خطای ۴۰۹ (`duplicate key`) می‌گیرد و چون تراکنش rollback شده، ردیف outbox ساخته نمی‌شود. بعد `report` همه‌چیز را می‌شمارد:

```text
report: orders=2 outbox=2 (unpublished=0) ORDERS msgs=2 RESULTS msgs=2 KV keys=2
```

## کشتن worker وسط پیام

با `STALL=before` worker بعد از دریافت `o-3` و قبل از publish می‌خوابد. همان‌جا `kill -9` می‌زنم:

```text
killed worker2 (SIGKILL)
{"id":"o-3","status":"unknown"}
(restarted worker; redelivery arrives once the 5 s ack_wait expires)
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
worker: o-3 delivered=2 -> priced total=1090
```

پیام دوباره تحویل شد (`delivered=2`) و یک بار پردازش شد. حالت سخت‌تر `STALL=after` است: نتیجه‌ی `o-4` از قبل publish شده و worker می‌میرد، پس ack هرگز نمی‌رسد:

```text
worker: o-4 delivered=1 -> priced total=1089
worker: stalling after publish, kill me now
--- restarted worker ---
worker: o-4 delivered=2 already processed, skipping
report: orders=4 outbox=4 (unpublished=0) ORDERS msgs=4 RESULTS msgs=4 KV keys=4
```

چهار سفارش، چهار نتیجه. redelivery اتفاق افتاد ولی اثر فقط یک بار اعمال شد.

## کشتن relay بین publish و mark

با `CRASH_AFTER_PUBLISH=1` relay درست بعد از publish موفق خارج می‌شود. Postgres هنوز ردیف را منتشرنشده نشان می‌دهد، در حالی که stream رویداد را دارد:

```text
relay: outbox id=5 published seq=5 duplicate=false
relay: CRASH between publish and mark-published
report: orders=5 outbox=5 (unpublished=1) ORDERS msgs=5 ...
--- normal relay started ---
relay: outbox id=5 published seq=5 duplicate=true
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

تلاش دوباره `duplicate=true` با همان sequence شماره‌ی ۵ گرفت. stream آن را با `Nats-Msg-Id` دور ریخت و worker هیچ‌وقت نسخه‌ی دوم را ندید.

## راه‌اندازی دوباره‌ی همه‌چیز

API، relay، projector و worker را متوقف کردم، بعد خود `infra` را هم و دوباره روی همان پوشه‌ی داده بالا آوردم. ردیف‌های Postgres و فایل‌های JetStream سر جایشان بودند:

```text
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
{"order_id":"o-5","status":"priced","total_cents":4578,"checksum":"7d5392b2"}
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

بعد یک `o-6` تازه مثل همیشه از همه‌ی مرحله‌ها گذشت.

## چند نکته‌ی مهم

- بررسی «قبلاً پردازش شده» از نوع check-then-act است. اگر چند worker روی یک سفارش باشند، ممکن است هر دو از آن رد شوند. پنجره‌ی ۵ دقیقه‌ای dedup روی `Nats-Msg-Id` این را می‌پوشاند، اما راه‌حل واقعی یک کلید یکتا در store خودتان است.
- همه‌چیز at-least-once است؛ درستی از مراحل idempotent می‌آید، نه از «exactly once».
- `ack_wait` دلیل این است که بازیابی حدود پنج ثانیه طول کشید. آن را با کندترین پیامتان تنظیم کنید.
- سرعت یا throughput را اندازه نگرفتم و دمو متریک ندارد. اول متریک‌های [observability برای JetStream](/fa/posts/nats-jetstream-observability/) را اضافه کنید.
- NATS بین سرویس‌ها durability و redelivery می‌دهد. اگر پاسخ همگام می‌خواهید، از gRPC مثل [Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) استفاده کنید.

## قدم بعدی

بعدی در تقویم: Docker، CI و انتشار یک سرویس Rust.
