+++
date = '2027-03-18T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی Rust: یک سرویس کامل'
description = 'سرویس سفارش‌ها در Rust با Axum، SQLx، thiserror، tracing و NATS JetStream، همراه با graceful shutdown، تست روی Postgres واقعی و کمبودهای تا production.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "capstone", "axum", "sqlx", "tracing", "nats", "thiserror", "backend"]
cover = { image = "/images/covers/rust-capstone-service.fa.png", alt = "پروژه‌ی پایانی Rust: یک سرویس کامل", hiddenInSingle = true, hiddenInList = true }
+++

[مقاله‌ی قبل](/fa/posts/rust-wasm/) درباره‌ی WebAssembly بود. این آخرین مقاله‌ی فنی سری است و چیز تازه‌ای نمی‌سازد: تکه‌های قبلی را در یک سرویس کوچک به نام `orders` به هم وصل می‌کند. API آن همان API نسخه‌ی Go در [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است: `POST /orders`، `GET /orders/{id}`، `GET /orders`، `/healthz` و `/readyz`. تقسیم به ماژول‌ها از [ماژول، crate و Cargo در Rust](/fa/posts/rust-modules-crates-cargo/) می‌آید و همین ایده در Go در [ساختار پروژه و clean architecture در Go](/fa/posts/go-project-layout-clean-architecture/) آمده است.

> Rust 1.90 با edition 2024، `axum 0.8.9`، `sqlx 0.8.6`، `async-nats 0.50.0`، `tokio 1.54.1` و `tracing-subscriber 0.3.23`. PostgreSQL 18.3 و nats-server 2.15.1 واقعی، هرکدام با یک برنامه‌ی کوچک Go (embedded، بدون Docker) در یک process جدا اجرا شدند و در پایان متوقف شدند. همه‌ی خروجی‌ها از اجرای واقعی است؛ `RUST_LOG` برابر `info` بود و زمان از لاگ‌ها حذف شده است.

## ساختار پروژه

```text
orders-service
├── Cargo.toml
├── migrations/0001_create_orders.sql
├── src
│   ├── lib.rs      (just `pub mod` lines)
│   ├── config.rs   typed Config, errors reported together
│   ├── error.rs    AppError + IntoResponse
│   ├── store.rs    PgPool, query_as, migrations
│   ├── events.rs   JetStream publisher
│   ├── routes.rs   Router, handlers, request id, tracing
│   └── main.rs     wiring, shutdown, anyhow
└── tests/api.rs
```

`main.rs` نازک است و بقیه‌ی کد در کتاب‌خانه (library) می‌ماند تا تست‌های پوشه‌ی `tests/` بتوانند آن را import کنند.

## کانفیگی که بلند شکست می‌خورد

`Config::from_lookup` به‌جای خواندن مستقیم محیط، یک closure می‌گیرد، پس unit testها به وضعیت سراسری process دست نمی‌زنند. همه‌ی مشکل‌ها را جمع می‌کند و یک‌جا برمی‌گرداند. `Debug` را دستی نوشتم تا رمز داخل `DATABASE_URL` هیچ‌وقت به لاگ نرسد.

```text
$ DATABASE_URL=mysql://x:pw@h/db ORDERS_ADDR=nope NATS_URL=http://x ./orders-service
Error: invalid configuration:
  - ORDERS_ADDR="nope": invalid socket address syntax
  - DATABASE_URL is required and must start with postgres://
  - NATS_URL="http://x": must start with nats://
```

exit code برابر ۱ بود. در اجرای عادی لاگ شروع این را نشان می‌دهد: `cfg=Config { addr: 127.0.0.1:8123, database_url: "<redacted>", ... }`.

## یک نوع خطا، یک نقطه‌ی نگاشت

مثل [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/)، کتاب‌خانه خطای تایپ‌دار دارد و `anyhow` فقط در `main` می‌آید. حالت‌ها و تنها جایی که آن‌ها را به HTTP تبدیل می‌کند:

```rust
#[derive(Debug, Error)]
pub enum AppError {
    #[error("order {0} not found")]
    NotFound(i64),
    #[error("validation failed")]
    Validation(BTreeMap<&'static str, &'static str>),
    #[error("database error")]
    Db(#[from] sqlx::Error),
}
// into_response: NotFound -> 404, Validation -> 422,
// Db -> tracing::error!(error = %source) and a generic 500 body
```

handlerها `Result<_, AppError>` برمی‌گردانند و از `?` استفاده می‌کنند؛ `#[from]` تبدیل `sqlx::Error` را مجانی می‌کند. extractorها و `State` در [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/) توضیح داده شدند؛ اینجا `AppState` یک `Store` و یک `Events` نگه می‌دارد که هر دو ارزان clone می‌شوند.

## درخواست، خطا و لاگ

هر درخواست یک span با `request_id` دارد (راه‌اندازی layerها از [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/) است)، پس هر خط داخل آن شناسه را همراه دارد. اجرای واقعی، با خط‌های لاگ متناظر:

```text
$ curl -i localhost:8123/orders/999
HTTP/1.1 404 Not Found
x-request-id: req-4
{"error":"order not found"}

$ curl -i -X POST localhost:8123/orders -d '{"customer":" ","cents":0}' -H 'content-type: application/json'
HTTP/1.1 422 Unprocessable Entity
x-request-id: req-5
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -i -X POST localhost:8123/orders -d '{"customer":"bad\u0000name","cents":100}' ...
HTTP/1.1 500 Internal Server Error
x-request-id: req-6
{"error":"internal error"}
```

```text
WARN request{method=GET path=/orders/999 request_id="req-4"}: orders_service::error: not found error=order 999 not found
WARN request{method=POST path=/orders request_id="req-5"}: orders_service::error: validation failed fields={"cents": "must be positive", "customer": "is required"}
ERROR request{method=POST path=/orders request_id="req-6"}: orders_service::error: request failed error=error returned from database: invalid byte sequence for encoding "UTF8": 0x00
```

خطای ۵۰۰ یک شکست واقعی و پیش‌بینی‌نشده است: کاراکتر NUL در نام مشتری از validation من رد می‌شود و Postgres آن را رد می‌کند. کلاینت بدنه‌ی کلی می‌بیند و لاگ هم علت و هم شناسه را دارد. درست کردن validation یک خط است که عمداً نگذاشتم تا همین مسیر دیده شود.

## اول store، بعد event

`Store` همان دستگیره‌ی `PgPool` از [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/) است: `query_as`، `fetch_optional` و `sqlx::migrate!("./migrations")` موقع شروع. بخش جالب handler است:

```rust
let order = st.store.create(&input.customer, input.cents).await?;
// Publish only after the row is committed. A failure here must not fail the request.
match st.events.order_created(&order).await {
    Ok(duplicate) => tracing::info!(order_id = order.id, duplicate, "published order.created"),
    Err(e) => tracing::warn!(order_id = order.id, error = %e, "event not published"),
}
```

`Events` مثل [کلاینت async برای NATS JetStream در Rust](/fa/posts/rust-nats-async-client/) از `async-nats` استفاده می‌کند و header به شکل `Nats-Msg-Id: order-{id}-created` می‌گذارد. یک subscriber کوچک Go آنچه رسید را چاپ کرد:

```text
event seq=1 subject=order.created msg-id=order-2-created body={"id":2,"customer":"roham","cents":1990,"status":"new"}
event seq=2 subject=order.created msg-id=order-3-created body={"id":3,"customer":"sara","cents":500,"status":"new"}
```

انتشار دوباره‌ی همان شناسه، دو بار، از Go:

```text
publish order-2-created: seq=1 duplicate=true, stream messages=2
publish order-2-created: seq=1 duplicate=true, stream messages=2
```

سرور با sequence اصلی جواب داد، `duplicate=true` زد و stream همچنان ۲ پیام داشت. پیش‌زمینه‌ی idempotency در [Idempotency و معنی exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/) است.

## Graceful shutdown

`axum::serve(...).with_graceful_shutdown(...)` منتظر future‌ای می‌ماند که با `tokio::signal` به Ctrl+C و `SIGTERM` گوش می‌دهد، مثل [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/). برای داشتن درخواستی که واقعاً در جریان است، با `nc` یک POST با header کامل فرستادم و بدنه را ۳ ثانیه عقب انداختم؛ یک ثانیه بعد `SIGTERM` زدم:

```text
SIGTERM at 01:00:57
new connection during drain: 000
service exit code: 0 at 01:00:59
HTTP/1.1 201 Created
{"id":5,"customer":"in-flight","cents":700,"status":"new"}
```

```text
INFO orders_service: shutdown requested, draining in-flight requests
INFO request{... request_id="req-1"}: ... published order.created order_id=5 duplicate=false
INFO request{... request_id="req-1"}: ... finished processing request latency=3004 ms status=201
INFO orders_service: stopped
```

اتصال تازه در زمان تخلیه جواب نگرفت (`000` کد curl برای «پاسخ HTTP نیامد» است)، درخواست کند با ۲۰۱ تمام شد و process با کد ۰ بسته شد. نسخه‌ی Go این ایده در [خاموش شدن تمیز workerهای Go](/fa/posts/go-graceful-shutdown-workers/) است.

## تست

مثل [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/)، تست‌های یکپارچه `Router` را با `tower::ServiceExt::oneshot` صدا می‌زنند، پس هیچ port‌ای باز نمی‌شود، ولی دیتابیس همان Postgres واقعی است (`Events::disabled()` NATS را کنار می‌گذارد):

```text
$ TEST_DATABASE_URL=postgres://... cargo test
test config::tests::debug_hides_the_password ... ok
test config::tests::reports_all_problems_together ... ok
test invalid_input_is_422_with_all_fields ... ok
test missing_order_is_404 ... ok
test create_then_get_then_list ... ok
```

`cargo clippy --all-targets -- -D warnings` و `cargo fmt --check` هر دو بدون هیچ خروجی گذشتند.

## چه چیزی برای production کم است

- احراز هویت و مجوزدهی ندارد.
- rate limiting ندارد؛ ایده‌هایش در [Rate limiting و caching در Go](/fa/posts/go-rate-limiting-caching/) است.
- نوشتن ردیف و publish دو مرحله‌اند: crash بین آن‌ها event را گم می‌کند. راهش [الگوی outbox با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/) است.
- `sqlx::migrate!` موقع شروع اینجا کافی است، ولی با چند replica به راهبرد واقعی migration نیاز دارید.
- متریک ندارد، و سمت JetStream (retention، replica، امنیت) در [JetStream در production](/fa/posts/nats-jetstream-production/) است.

## چند نکته‌ی مهم

- منبع خطا را لاگ کنید و بدنه‌ی کلی برگردانید؛ متن خطای دیتابیس را هیچ‌وقت برای کلاینت نفرستید.
- رد شدن extractorهای خود Axum (JSON خراب، id غیرعددی) بدنه‌ی متنی خودشان را دارد، نه `AppError`.
- بعد از commit منتشر کنید، و شکست publish را فقط وقتی warning بگیرید که حفره‌ی بالا را پذیرفته‌اید.
- تست‌های یکپارچه وقتی `TEST_DATABASE_URL` تنظیم نیست بی‌صدا skip می‌شوند؛ در CI آن را تنظیم کنید.

## قدم بعدی

مقاله‌ی بعد جمع‌بندی پایان سال سری Rust و ۱۴۰۵ است.
