+++
date = '2027-03-18T10:00:00+03:30'
draft = false
title = 'پروژه‌ی پایانی Rust: یک سرویس کامل'
description = 'سرویس سفارش‌ها در Rust با Axum، SQLx، thiserror، tracing و NATS JetStream، همراه با graceful shutdown، تست روی Postgres واقعی و کمبودهای تا production.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "capstone", "axum", "sqlx", "tracing", "nats", "thiserror", "backend"]
cover = { image = "/images/covers/rust-capstone-service.fa.png", alt = "پروژه‌ی پایانی Rust: یک سرویس کامل", hiddenInSingle = true }
+++

هر مقاله‌ی این سری یک تکه را تنها ساخت: API با Axum، لایه‌ی دیتابیس با SQLx، خطاهای دارای نوع، لاگ با span، کلاینت NATS، خاموش شدن تمیز و تست. هر تکه در demo کوچک خودش کار می‌کرد. سؤال واقعی این است که وقتی همه در یک برنامه کنار هم می‌آیند چه می‌شود، چون باگ‌ها همان‌جا پنهان‌اند: در درز بین تکه‌ها، نه داخل هیچ‌کدام.

این آخرین مقاله‌ی فنی چیز تازه‌ای نمی‌سازد. تکه‌های قبلی را در یک سرویس کوچک `orders` به هم وصل می‌کند و نشان می‌دهد در درزها چه می‌گذرد. یک نمونه از درز: یک نویسه‌ی NUL داخل نام مشتری از اعتبارسنجی من رد شد و بعد Postgres آن را نپذیرفت. کلاینت یک 500 کلی گرفت و در لاگ علت واقعی و شناسه‌ی درخواست ثبت شد. پایین عمداً همین را بازتولید می‌کنیم.

API این سرویس همان API نسخه‌ی Go در [ساخت API با net/http در Go](/fa/posts/go-http-api-stdlib/) است: `POST /orders`، `GET /orders/{id}`، `GET /orders`، `/healthz` و `/readyz`. بعد از [Rust و WebAssembly](/fa/posts/rust-wasm/) می‌آید. تقسیم ماژول‌ها از [Module، Crate و Cargo در Rust](/fa/posts/rust-modules-crates-cargo/) پیروی می‌کند و همین ایده در Go در [ساختار پروژه و Clean Architecture در Go](/fa/posts/go-project-layout-clean-architecture/) آمده.

> همه‌چیز را برای این نسخه‌ی مقاله دوباره اجرا کردم، با `rustc 1.90.0`، edition 2024 و نسخه‌های قفل‌شده در `Cargo.lock` ‏demo: `axum 0.8.9`، `sqlx 0.8.6`، `async-nats 0.50.0`، `tokio 1.54.1`، `tower-http 0.7.1` و `tracing-subscriber 0.3.23`. دیتابیس یک PostgreSQL 18.3 واقعی بود و broker یک nats-server 2.15.1 واقعی، هرکدام با یک برنامه‌ی کوچک Go (توکار، بدون Docker) به‌صورت یک پروسه‌ی جدا روی یک پورت محلی تصادفی بالا آمد. هر دو را در پایان متوقف کردم و بررسی کردم پروسه‌ای از من باقی نمانده باشد. `RUST_LOG` برابر `info` بود؛ زمان‌ها را از لاگ‌ها حذف کرده‌ام و پورت در آدرس (`<port>` پایین) هر بار فرق می‌کند.

## نقشه: هر تکه از کدام مقاله می‌آید

پیش از کد ببینیم تکه‌ها چطور کنار هم می‌نشینند. درخواست از بالا وارد می‌شود و پایین می‌رود:

| تکه | فایل | کارش | کجا دیدیمش |
|---|---|---|---|
| config | `config.rs` | محیط را می‌خواند و بررسی می‌کند | اینجا تازه است؛ ایده‌ی Go در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) |
| type خطا | `error.rs` | یک `AppError` که در یک جا به HTTP نگاشت می‌شود | [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/) |
| مسیرها | `routes.rs` | `Router`، handlerها، لایه‌های timeout و شناسه‌ی درخواست | [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/) |
| لاگ | `routes.rs` | یک span برای هر درخواست | [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/) |
| store | `store.rs` | Postgres با connection pool | [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/) |
| رویداد | `events.rs` | `order.created` را به JetStream می‌فرستد | [کلاینت async NATS JetStream در Rust](/fa/posts/rust-nats-async-client/) |
| خاموش شدن | `main.rs` | با SIGTERM تمیز متوقف می‌شود | [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/)، با `select!` از [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) |
| تست | `tests/api.rs` | router را بی‌باز کردن پورت صدا می‌زند | [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/) و `oneshot` از مقاله‌ی Axum |

مسیر یک `POST /orders` این است: router به درخواست یک شناسه می‌دهد و یک span باز می‌کند، handler ورودی را اعتبارسنجی می‌کند، store یک سطر در Postgres می‌نویسد و فقط بعد از آن `events` رویداد را منتشر می‌کند. اگر چیزی شکست بخورد، `AppError` کد وضعیت را تعیین می‌کند.

## ساختار

```text
orders-service
├── Cargo.toml
├── migrations/0001_create_orders.sql
├── src
│   ├── lib.rs      (فقط خط‌های `pub mod`)
│   ├── config.rs   Config دارای نوع، خطاها با هم گزارش می‌شوند
│   ├── error.rs    AppError + IntoResponse
│   ├── store.rs    PgPool، query_as، migration
│   ├── events.rs   publisher برای JetStream
│   ├── routes.rs   Router، handlerها، شناسه‌ی درخواست، tracing
│   └── main.rs     سیم‌کشی، خاموش شدن، anyhow
└── tests/api.rs
```

`main.rs` نازک است: config را می‌خواند، به Postgres و NATS وصل می‌شود و سرور را راه می‌اندازد. بقیه‌ی همه‌چیز در crate کتاب‌خانه‌ای است تا تست‌های `tests/` مثل یک کاربر بیرونی آن را import کنند.

## config که بلند شکست می‌خورد

سرویسی که با تنظیمات خراب بالا بیاید و بعداً وسط یک درخواست شکست بخورد بدترین نوع است. پس config یک بار هنگام شروع بررسی می‌شود و همه‌ی مشکل‌ها با هم گزارش می‌شوند. اگر تا حالا یک متغیر محیطی را درست کرده‌اید و بعد دیده‌اید بعدی غلط است، می‌دانید چرا.

`Config::from_lookup` به‌جای خواندن مستقیم محیط یک closure می‌گیرد، تا unit testها به وضعیت سراسری پروسه دست نزنند. `Debug` را دستی نوشته‌ام تا رمز داخل `DATABASE_URL` هرگز به لاگ نرسد. این یک شروع با سه مقدار غلط است:

```text
$ DATABASE_URL=mysql://x:pw@h/db ORDERS_ADDR=nope NATS_URL=http://x ./orders-service
Error: invalid configuration:
  - ORDERS_ADDR="nope": invalid socket address syntax
  - DATABASE_URL is required and must start with postgres://
  - NATS_URL="http://x": must start with nats://
```

هر سه مشکل در یک پیام‌اند و کد خروج ۱ بود. در شروع عادی، اولین خط لاگ config را با رمز پنهان نشان می‌دهد: `starting cfg=Config { addr: 127.0.0.1:<port>, database_url: "<redacted>", nats_url: "nats://127.0.0.1:<port>" }`.

## یک type خطا، یک نگاشت

مثل [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/)، کتاب‌خانه type خطای دارای نوع دارد و `anyhow` فقط در `main` می‌آید. این‌ها variantها هستند و تنها جایی که آن‌ها را به HTTP تبدیل می‌کند:

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

handlerها `Result<_, AppError>` برمی‌گردانند و `?` می‌گذارند؛ `#[from]` یک `sqlx::Error` را خودکار تبدیل می‌کند. این نگاشت یک قاعده دارد که برای امنیت مهم است: جزئیات خطای دیتابیس به لاگ می‌رود و کلاینت فقط `{"error":"internal error"}` می‌گیرد. [مقاله‌ی Axum](/fa/posts/rust-http-axum-api/) extractorها و `State` را توضیح داده؛ اینجا `AppState` یک `Store` و یک `Events` دارد و هر دو ارزان clone می‌شوند.

## درخواست‌ها، خطاها و لاگ‌ها

هر درخواست یک {{< term "request-id" "شناسه‌ی درخواست" >}} می‌گیرد (`req-1` و `req-2` و همین‌طور ادامه، از یک شمارنده‌ی ساده) و یک span که آن را با خود دارد، پس هر خط لاگ داخل درخواست هم آن را دارد. راه‌اندازی span همان است که در [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/) دیدیم. لایه‌ها همان‌هایی‌اند که در مقاله‌ی Axum بودند. از پایین به بالا اضافه می‌شوند و آخری که اضافه شود اول اجرا می‌شود: `SetRequestIdLayer` شناسه را می‌سازد، بعد `TraceLayer` آن را برای span می‌خواند و `PropagateRequestIdLayer` آن را در header پاسخ به نام `x-request-id` کپی می‌کند. دور همه‌ی این‌ها یک `TimeoutLayer` ده‌ثانیه‌ای هم هست. چون شناسه در پاسخ هم هست، کاربر می‌تواند `req-6` را برایتان بفرستد و شما خط‌های دقیق لاگ را پیدا کنید.

سرویس را راه انداختم و درخواست‌های پایین را به همین ترتیب زدم. اول دو ساخت موفق و یک فهرست (`req-1` تا `req-3`)، بعد سه شکست. پاسخ‌ها، با headerهای `date` و `content-length` حذف‌شده:

```text
$ curl -i localhost:<port>/orders/999
HTTP/1.1 404 Not Found
x-request-id: req-4
{"error":"order not found"}

$ curl -i -X POST localhost:<port>/orders -d '{"customer":" ","cents":0}' -H 'content-type: application/json'
HTTP/1.1 422 Unprocessable Entity
x-request-id: req-5
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -i -X POST localhost:<port>/orders -d '{"customer":"bad\u0000name","cents":100}' ...
HTTP/1.1 500 Internal Server Error
x-request-id: req-6
{"error":"internal error"}
```

اولی سفارش ناموجود است: `404`. دومی هر دو قاعده‌ی اعتبارسنجی را هم‌زمان می‌شکند و پاسخ همه‌ی فیلدها را فهرست می‌کند، نه فقط اولی را. سومی همان نویسه‌ی NUL ابتدای مقاله است: JSON سالم است، اعتبارسنجی رد می‌شود (نام خالی نیست) و Postgres از ذخیره‌ی بایت NUL در متن سر باز می‌زند. خط‌های لاگ متناظر:

```text
WARN request{method=GET path=/orders/999 request_id="req-4"}: orders_service::error: not found error=order 999 not found
WARN request{method=POST path=/orders request_id="req-5"}: orders_service::error: validation failed fields={"cents": "must be positive", "customer": "is required"}
ERROR request{method=POST path=/orders request_id="req-6"}: orders_service::error: request failed error=error returned from database: invalid byte sequence for encoding "UTF8": 0x00
```

دو طرف `req-6` را مقایسه کنید. کلاینت فقط `internal error` دید و بس، و لاگ علت واقعی را با همان شناسه‌ی درخواست دارد. (لاگ برای هر درخواست خط معمول `finished processing request` را هم دارد، و برای `req-6` یک خط `ERROR` دوم از لایه‌ی trace که می‌گوید پاسخ با وضعیت 500 شکست طبقه‌بندی شد؛ آن‌ها را نیاورده‌ام.) این 500 همان شکست واقعی ابتدای مقاله است. درست کردن اعتبارسنجی یک تغییر تک‌خطی است که عمداً نکردم تا همین مسیر را نشان بدهم.

## store، بعد رویداد

`Store` همان handle ‏`PgPool` از [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/) است: یک {{< term "connection-pool" "connection pool" >}}، `query_as`، `fetch_optional` و `sqlx::migrate!("./migrations")` موقع شروع، که {{< term "migration" "migration" >}} ساخت جدول `orders` را اعمال می‌کند. بخش جالب handler است، چون به دو سیستم دست می‌زند:

```rust
let order = st.store.create(&input.customer, input.cents).await?;
// Publish only after the row is committed. A failure here must not fail the request.
match st.events.order_created(&order).await {
    Ok(duplicate) => tracing::info!(order_id = order.id, duplicate, "published order.created"),
    Err(e) => tracing::warn!(order_id = order.id, error = %e, "event not published"),
}
```

ترتیب این دو قدم یک تصمیم است. رویداد را فقط بعد از ذخیره‌ی سطر منتشر می‌کنیم، پس هرگز سفارشی را اعلام نمی‌کنیم که وجود ندارد. و شکست publish به‌صورت هشدار لاگ می‌شود، نه خطای برگردانده‌شده، چون سفارش از قبل در دیتابیس است و گفتن «شکست خورد» به کلاینت او را به تلاش دوباره دعوت می‌کند که سفارش دومی می‌سازد. هزینه‌ی این انتخاب در کمبودهای production پایان مقاله آمده.

`Events` مثل [کلاینت async NATS JetStream در Rust](/fa/posts/rust-nats-async-client/) از `async-nats` استفاده می‌کند، با header به شکل `Nats-Msg-Id: order-{id}-created`. یک subscriber کوچک Go نشان داد هنگام ساخت دو سفارش چه چیزی روی stream رسید:

```text
event seq=1 subject=order.created msg-id=order-1-created body={"id":1,"customer":"roham","cents":1990,"status":"new"}
event seq=2 subject=order.created msg-id=order-2-created body={"id":2,"customer":"sara","cents":500,"status":"new"}
```

یک رویداد برای هر سفارش ساخته‌شده، هرکدام با شناسه‌ای که سرویس انتخاب کرده. همین شناسه تلاش دوباره را امن می‌کند. از Go دوباره `order-2-created` را دو بار منتشر کردم:

```text
publish order-2-created: seq=2 duplicate=true, stream messages=2
publish order-2-created: seq=2 duplicate=true, stream messages=2
```

سرور شماره‌ی ترتیب اصلی را جواب داد، `duplicate=true` زد و stream هنوز ۲ پیام داشت. پس‌زمینه‌ی این {{< term "idempotency" "idempotency" >}} در [Idempotency و معنای exactly-once در JetStream](/fa/posts/nats-jetstream-idempotency/) است.

## خاموش شدن تمیز

وقتی پلتفرم سرویس را متوقف می‌کند `SIGTERM` می‌فرستد و می‌خواهیم درخواست‌هایی که الان در جریان‌اند تمام شوند. `axum::serve(...).with_graceful_shutdown(...)` منتظر futureای می‌ماند که با `tokio::signal` به Ctrl+C و `SIGTERM` گوش می‌دهد، مثل [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/) (`select!`ای که منتظر هر کدام از دو سیگنال می‌ماند همان است که در [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) بود). بعد از خالی شدن سرور، `main` pool را می‌بندد و `stopped` لاگ می‌کند.

برای آزمودنش درخواستی لازم داشتم که لحظه‌ی رسیدن سیگنال واقعاً در جریان باشد. یک اسکریپت کوچک کلاینت نوشتم که یک POST با headerهای کامل می‌فرستد، ۳ ثانیه صبر می‌کند و تازه بعد بدنه را می‌فرستد، پس handler منتظر بدنه گیر می‌کند. (اولین تلاشم با `nc` روی این ماشین درخواست را نرساند، پس از چند خط Python با socket استفاده کردم.) یک ثانیه بعد `SIGTERM` فرستادم و بعد یک اتصال تازه امتحان کردم:

```text
SIGTERM at 17:58:25
new connection during drain: 000
service gone at 17:58:28
HTTP/1.1 201 Created
x-request-id: req-1
{"id":3,"customer":"in-flight","cents":700,"status":"new"}
```

```text
INFO orders_service: shutdown requested, draining in-flight requests
INFO request{... request_id="req-1"}: ... published order.created order_id=3 duplicate=false
INFO request{... request_id="req-1"}: ... finished processing request latency=3010 ms status=201
INFO orders_service: stopped
```

اتصال تازه در حین خالی شدن جوابی نگرفت (`000` کد curl برای «پاسخ HTTP نیامد» است). درخواست کند بعد از حدود ۳ ثانیه با `201` تمام شد، همان‌طور که `latency` نشان می‌دهد، و رویدادش پیش از توقف پروسه منتشر شد. اجرا را با سرویس به‌عنوان فرزند shell تکرار کردم تا کد خروجش را بخوانم: ۰ بود. latency و شناسه‌ی سفارش از اجرایی به اجرای دیگر فرق می‌کنند. نسخه‌ی Go همین ایده [خاموشی تمیز Workerها در Go](/fa/posts/go-graceful-shutdown-workers/) است و اصطلاحش {{< term "graceful-shutdown" "خاموش شدن تمیز" >}} است.

## تست‌ها

مثل [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/)، {{< term "rust-integration-test" "تست‌های integration" >}} مستقیم `Router` را با `tower::ServiceExt::oneshot` صدا می‌زنند، پس پورتی باز نمی‌شود ولی دیتابیس همان Postgres واقعی است. (`Events::disabled()` NATS را رد می‌کند.) آن‌ها را با `TEST_DATABASE_URL` اشاره‌کننده به Postgres توکار اجرا کردم:

```text
$ TEST_DATABASE_URL=postgres://... cargo test
test config::tests::reports_all_problems_together ... ok
test config::tests::debug_hides_the_password ... ok
test invalid_input_is_422_with_all_fields ... ok
test missing_order_is_404 ... ok
test create_then_get_then_list ... ok
```

دو تست اول unit test داخل `config.rs`‌اند؛ سه‌تای دیگر در `tests/api.rs`. هر دو دستور `cargo clippy --all-targets -- -D warnings` و `cargo fmt --check` بدون خروجی پاس شدند.

## چه چیزی برای production کم است

- احراز هویت و مجوزدهی ندارد.
- rate limiting ندارد؛ ایده‌هایش در [Rate limit و cache در Go](/fa/posts/go-rate-limiting-caching/) هست.
- نوشتن سطر و انتشار دو قدم جدا هستند: کرش بین آن‌ها رویداد را از دست می‌دهد. راهش {{< term "outbox-pattern" "الگوی outbox" >}} است و [Outbox Pattern با Postgres و NATS در Go](/fa/posts/go-outbox-pattern-nats/) آن را نشان می‌دهد.
- `sqlx::migrate!` هنگام شروع اینجا خوب است، ولی با چند replica به یک راهبرد migration واقعی نیاز دارید.
- شناسه‌ی درخواست یک شمارنده است، پس بعد از هر راه‌اندازی دوباره از `req-1` شروع می‌شود و بین replicaها تکراری می‌شود. برای demo خوب است، نه برای یک ناوگان.
- متریک ندارد و سمت JetStream (retention، replica، امنیت) در [JetStream در پروداکشن: cluster، retention و امنیت](/fa/posts/nats-jetstream-production/) است.

## جاهایی که شکست‌ها ساکت می‌مانند

- **منبع خطا را لاگ کنید، بدنه‌ی کلی برگردانید.** هرگز متن دیتابیس را برای کلاینت نفرستید؛ `req-6` همین الگو را نشان می‌دهد.
- **ردشدن‌های خود extractorهای Axum بدنه‌ی متنی ساده‌ی خودشان را دارند،** نه `AppError`: JSON خراب یا id غیرعددی پیام Axum را می‌گیرد، نه شکل JSON ما را.
- **بعد از commit منتشر کنید، و شکست publish را فقط وقتی هشدار حساب کنید که کمبود بالا را می‌پذیرید.**
- **تست‌های integration وقتی `TEST_DATABASE_URL` تنظیم نشده ساکت رد می‌شوند.** یک بار بدون آن اجرایشان کردم: هر سه تست `api` بی‌آنکه به دیتابیس دست بزنند `ok` چاپ کردند و تنها ردش یک خط `skipping` در stderr است که `cargo test` پنهانش می‌کند. متغیر را در CI تنظیم کنید، وگرنه تست‌ها چیزی را ثابت نمی‌کنند.

## قدم بعدی

«مرور سری Rust و جمع‌بندی سال ۱۴۰۵» سری را با نقشه‌ی همه‌ی مقاله‌هایش می‌بندد.
