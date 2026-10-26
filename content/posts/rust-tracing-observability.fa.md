+++
date = '2027-03-04T10:00:00+03:30'
draft = false
title = 'Observability در Rust با tracing'
description = 'رویداد و span ساخت‌یافته، EnvFilter، خروجی JSON و تله‌ی گم شدن span در tokio::spawn: چطور crate به نام tracing سرویس async را قابل عیب‌یابی می‌کند.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "tracing", "observability", "async", "logging"]
cover = { image = "/images/covers/rust-tracing-observability.fa.png", alt = "Observability در Rust با tracing", hiddenInSingle = true }
+++

[مقاله‌ی قبل](/fa/posts/rust-pin-future-internals/) درون async را باز کرد. حالا سؤال عملی این است: وقتی سرویس هزاران task هم‌زمان دارد، چطور ببینیم برای یک درخواست مشخص چه اتفاقی افتاده؟ در این مقاله روی کدی شبیه [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) از crate به نام `tracing` استفاده می‌کنیم؛ همین ایده‌ها برای سرویسی مثل [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/) هم صدق می‌کند. آخر مقاله آن را با `slog` در [کانفیگ، لاگ ساخت‌یافته و خطا در Go](/fa/posts/go-config-logging-errors/) مقایسه می‌کنم.

> Rust 1.90 با edition 2024، نسخه‌های `tracing 0.1.44`، `tracing-subscriber 0.3.23` (با featureهای `env-filter` و `json`) و `tokio 1.54.1`. همه‌ی خروجی‌ها از اجرای واقعی کپی شده‌اند (رنگ با `NO_COLOR=1` خاموش بود).

## چرا لاگ ساده کافی نیست

سه task که هرکدام سه خط با `println!` چاپ می‌کنند:

```text
start
start
start
charging card
charging card
done
done
charging card
done
```

کدام `done` مال کدام سفارش است؟ معلوم نیست. thread و `.await` خط‌ها را قاطی می‌کنند و ترتیب از اجرایی به اجرای دیگر فرق دارد. می‌شود دستی به اول هر خط یک شناسه چسباند، ولی یک بار فراموشی کافی است.

## رویداد و span

**رویداد** (event) یک نقطه در زمان است: `info!`، `warn!`، `debug!`. **span** یک بازه‌ی زمانی با فیلدهای خودش است و هر رویدادی داخلش اتفاق بیفتد، زمینه‌ی آن را خودکار می‌گیرد. فیلدها ساخت‌یافته‌اند و داخل متن پیام جا نمی‌شوند:

```rust
let order = Order { id: 42, total: 19.5 };   // derives Debug
let user = "roham";
info!(order_id = order.id, "created");
info!(%user, ?order, "details");
debug!(step = "validate", "checking stock");
warn!(retry_in = ?Duration::from_millis(250), "payment slow");
```

`%x` مقدار را با `Display` و `?x` با `Debug` ثبت می‌کند. تا **subscriber** نصب نکنید چیزی چاپ نمی‌شود:

```rust
tracing_subscriber::fmt()
    .with_env_filter(EnvFilter::from_default_env())
    .init();
```

بدون `RUST_LOG` فیلتر خالی است و این برنامه اصلاً چیزی چاپ نکرد. با `RUST_LOG=info` فقط خط‌های `info` و `warn` آمدند. با `RUST_LOG=info,basic=debug` (سطح debug برای crate با نام `basic`):

```text
2026-10-23T21:26:02.055509Z  INFO basic: created order_id=42
2026-10-23T21:26:02.055634Z  INFO basic: details user=roham order=Order { id: 42, total: 19.5 }
2026-10-23T21:26:02.055669Z DEBUG basic: checking stock step="validate"
2026-10-23T21:26:02.055694Z  WARN basic: payment slow retry_in=250ms
2026-10-23T21:26:02.055723Z DEBUG basic::other: inside module other
2026-10-23T21:26:02.055744Z  INFO basic::other: module other done
```

خط `trace!` هیچ‌وقت نیامد، چون trace پایین‌تر از debug است. فیلتر موقع شروع خوانده می‌شود، پس بدون کامپایل دوباره می‌توانید جزئیات را کم و زیاد کنید.

## span روی تابع‌های async

`#[instrument]` تابع را در یک span هم‌نام آن می‌پیچد و آرگومان‌ها را فیلد می‌کند:

```rust
#[instrument(skip(token), fields(user = "roham", amount_cents = field::Empty), err)]
async fn charge(order_id: u32, token: &str) -> Result<(), PaymentError> {
    sleep(Duration::from_millis(10)).await;
    Span::current().record("amount_cents", 1000 + order_id as u64);
    info!("charging card");
    if order_id == 3 { return Err(PaymentError("card declined")); }
    Ok(())
}

#[instrument]
async fn handle(order_id: u32) { /* info!("start"); sleep; charge(...).await; info!("done") */ }
```

`skip(token)` راز را از فیلدها بیرون نگه می‌دارد، `fields(...)` فیلد اضافه می‌کند، `field::Empty` جایی برای `record` بعدی رزرو می‌کند و `err` مقدار `Err` را به صورت رویداد `ERROR` ثبت می‌کند. اجرای هم‌زمان سه `handle` با `JoinSet`:

```text
INFO handle{order_id=3}: start
INFO handle{order_id=1}: start
INFO handle{order_id=2}: start
INFO handle{order_id=1}:charge{order_id=1 user="roham" amount_cents=1001}: charging card
INFO handle{order_id=1}: done
INFO handle{order_id=2}:charge{order_id=2 user="roham" amount_cents=1002}: charging card
INFO handle{order_id=2}: done
INFO handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: charging card
ERROR handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: error=card declined
WARN handle{order_id=3}: order failed error=card declined
```

(زمان‌ها حذف شده). خط‌ها هنوز قاطی‌اند، اما حالا هر خط می‌گوید مال کدام درخواست است و `charge` داخل `handle` تو در تو آمده. این است ثمره‌ی اصلی: span در هر `.await` همراه task می‌ماند.

## خروجی JSON

برای سامانه‌های جمع‌آوری لاگ، `.init()` را با `.json().init()` عوض کنید. یک خط نمونه:

```text
{"timestamp":"2026-10-23T21:25:56.264438Z","level":"ERROR","fields":{"error":"card declined"},"span":{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"},"spans":[{"order_id":3,"name":"handle"},{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"}]}
```

زنجیره‌ی کامل span‌ها در `spans` است و می‌شود بر اساس `order_id` فیلتر کرد.

## تله‌ی tokio::spawn

task ساخته‌شده با spawn یک task مستقل است و span فعلی را به ارث نمی‌برد:

```rust
let span = info_span!("request", request_id = "req-7");
async {
    info!("handling");
    tokio::spawn(background_audit()).await.unwrap();   // lost context
    info!("responded");
}.instrument(span).await;
```

```text
INFO request{request_id="req-7"}: handling
INFO audit written
INFO request{request_id="req-7"}: responded
```

خط «audit written» شناسه‌ی درخواست ندارد. راه‌حل `Instrument::instrument` با span فعلی است:

```rust
tokio::spawn(background_audit().instrument(tracing::Span::current()))
```

```text
INFO request{request_id="req-7"}: handling
INFO request{request_id="req-7"}: audit written
INFO request{request_id="req-7"}: responded
```

## زمان‌سنجی span

`.with_span_events(FmtSpan::CLOSE)` موقع بسته شدن span یک خط چاپ می‌کند. برای تابعی که ۵۰ میلی‌ثانیه خوابید و ۲۰ میلی‌ثانیه CPU را مشغول کرد، روی همین ماشین (میانگین load حدود ۳، پس تقریبی بدانید):

```text
INFO work: close time.busy=20.1ms time.idle=52.9ms
```

busy زمانی است که future در حال poll شدن بوده و idle زمان انتظار بین pollها.

## فراتر از کنسول

ارسال span‌ها به Jaeger یا هر backend مبتنی بر OpenTelemetry با افزودن یک layer دیگر به نام `tracing-opentelemetry` به همین subscriber انجام می‌شود. اینجا فقط اشاره می‌کنم و اجرایش نکردم.

مقایسه با Go: `log/slog` لاگ ساخت‌یافته‌ی key-value و `With` برای چسباندن فیلد به logger می‌دهد، اما مفهوم span ندارد؛ برای ربط دادن خط‌ها بین goroutineها باید خودتان logger یا context را پاس بدهید. در `tracing` حامل این زمینه خود span است.

## چند نکته برای دقت

- `tokio::spawn` span را گم می‌کند؛ از `.instrument(Span::current())` استفاده کنید.
- `#[instrument]` پیش‌فرض همه‌ی آرگومان‌ها را با `Debug` ثبت می‌کند؛ برای رازها و مقدارهای بزرگ `skip` بگذارید.
- نگه داشتن guard مربوط به `Span::enter()` در طول `.await` در کد async اشتباه است؛ از `#[instrument]` یا `.instrument(span)` استفاده کنید.
- بدون `RUST_LOG` (یا یک directive پیش‌فرض) فیلتر `EnvFilter` چیزی چاپ نمی‌کند و شبیه باگ به نظر می‌رسد.
- زمان `FmtSpan::CLOSE` را برای سرنخ بدانید، نه برای benchmark.

## تمرین

دور handler خودتان یک span با فیلد `request_id` بگذارید، از داخلش یک task پس‌زمینه spawn کنید و ببینید خط‌هایش شناسه را دارند. بعد به JSON تغییر دهید و خروجی را با همان شناسه فیلتر کنید.

## قدم بعدی

مقاله‌ی بعد درباره‌ی الگوی type-state و طراحی API در Rust است: کد کردن حالت‌های معتبر در type تا استفاده‌ی غلط اصلاً کامپایل نشود.
