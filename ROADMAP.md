# رودمپ و تقویم انتشار بلاگ

این فایل برنامه‌ی انتشار ۷۴ پست تا پایان سال ۱۴۰۵ است. Hugo آن را منتشر نمی‌کند چون خارج از `content/` است. هر بار که پستی نوشته یا منتشر شد، ستون وضعیت را به‌روز کنید.

وضعیت‌ها: ✅ منتشر شده · ✍️ نوشته شده و زمان‌بندی‌شده · 📝 برنامه‌ریزی‌شده

## قواعد زمان‌بندی

- شروع از ۳ آبان ۱۴۰۵ (۲۵ اکتبر ۲۰۲۶) و پایان در ۲۹ اسفند ۱۴۰۵ (۲۰ مارس ۲۰۲۷).
- هر دو روز یک پست، ساعت ۱۰:۰۰ به وقت تهران (`+03:30`).
- تاریخ پست در front matter همان تاریخ جدول است. Hugo پست‌های با تاریخ آینده را build نمی‌کند و workflow هر روز اجرا می‌شود، پس پست در روز خودش منتشر می‌شود.
- پیش‌نمایش پست‌های آینده: `hugo server -F`.

## سری‌ها

| سری (`series`) | دسته (`categories`) | تعداد | محتوا |
|---|---|---|---|
| Go Fundamentals | Go | 14 | مقدماتی، از نصب تا یک پروژه‌ی کوچک |
| Go Backend | Go | 12 | معماری، دیتابیس، concurrency، پروداکشن، runtime و gRPC |
| NATS JetStream | Go | 9 | دو پست منتشرشده + 7 پست جدید (A3 تا A9) |
| Rust | Rust | 30 | از مقدماتی تا پیشرفته: ownership تا async، macro، unsafe و wasm |
| Go + Rust | Go, Rust | 4 | مقایسه، gRPC، FFI و پروژه‌ی پایانی مشترک |
| آزاد | Security / Meta | 7 | 5 هشدار امنیتی و 2 مرور پایان سال |

هشدارهای امنیتی (`security-advisory-N`) جای خالی‌اند. موضوعشان در روز انتشار از آسیب‌پذیری‌های واقعی همان هفته انتخاب می‌شود. اگر موضوع مناسبی نبود، از پست‌های ذخیره‌ی همین رودمپ استفاده می‌کنیم.

## تقویم

| # | تاریخ میلادی | تاریخ شمسی | شناسه | slug | مسیر | سطح | وضعیت |
|---|---|---|---|---|---|---|---|
| 1 | 2026-10-25 | 1405/08/03 | A3 | `nats-jetstream-scaling-lag` | NATS | میانی | ✍️ |
| 2 | 2026-10-27 | 1405/08/05 | G1 | `go-getting-started` | Go | مقدماتی | ✍️ |
| 3 | 2026-10-29 | 1405/08/07 | R1 | `rust-getting-started` | Rust | مقدماتی | ✍️ |
| 4 | 2026-10-31 | 1405/08/09 | G2 | `go-types-control-flow` | Go | مقدماتی | ✍️ |
| 5 | 2026-11-02 | 1405/08/11 | R2 | `rust-types-control-flow` | Rust | مقدماتی | ✍️ |
| 6 | 2026-11-04 | 1405/08/13 | G3 | `go-functions-defer-errors` | Go | مقدماتی | ✍️ |
| 7 | 2026-11-06 | 1405/08/15 | G4 | `go-slices-maps-strings` | Go | مقدماتی | ✍️ |
| 8 | 2026-11-08 | 1405/08/17 | R3 | `rust-ownership` | Rust | مقدماتی | ✍️ |
| 9 | 2026-11-10 | 1405/08/19 | G5 | `go-structs-methods-interfaces` | Go | مقدماتی | ✍️ |
| 10 | 2026-11-12 | 1405/08/21 | G6 | `go-pointers-memory` | Go | مقدماتی | ✍️ |
| 11 | 2026-11-14 | 1405/08/23 | R4 | `rust-borrowing-references` | Rust | مقدماتی | ✍️ |
| 12 | 2026-11-16 | 1405/08/25 | X5 | `security-advisory-1` | آزاد | - | 📝 |
| 13 | 2026-11-18 | 1405/08/27 | G7 | `go-packages-modules` | Go | مقدماتی | ✍️ |
| 14 | 2026-11-20 | 1405/08/29 | R5 | `rust-structs-enums-pattern-matching` | Rust | مقدماتی | ✍️ |
| 15 | 2026-11-22 | 1405/09/01 | G8 | `go-goroutines-channels` | Go | مقدماتی | ✍️ |
| 16 | 2026-11-24 | 1405/09/03 | A4 | `nats-jetstream-idempotency` | NATS | میانی | ✍️ |
| 17 | 2026-11-26 | 1405/09/05 | G9 | `go-sync-select-context` | Go | مقدماتی | ✍️ |
| 18 | 2026-11-28 | 1405/09/07 | R6 | `rust-collections-strings` | Rust | مقدماتی | ✍️ |
| 19 | 2026-11-30 | 1405/09/09 | G10 | `go-generics` | Go | مقدماتی | ✍️ |
| 20 | 2026-12-02 | 1405/09/11 | R7 | `rust-error-handling-result` | Rust | مقدماتی | ✍️ |
| 21 | 2026-12-04 | 1405/09/13 | G11 | `go-testing-basics` | Go | مقدماتی | ✍️ |
| 22 | 2026-12-06 | 1405/09/15 | G12 | `go-file-io-json` | Go | مقدماتی | ✍️ |
| 23 | 2026-12-08 | 1405/09/17 | R8 | `rust-modules-crates-cargo` | Rust | مقدماتی | ✍️ |
| 24 | 2026-12-10 | 1405/09/19 | G13 | `go-cli-tool` | Go | مقدماتی | ✍️ |
| 25 | 2026-12-12 | 1405/09/21 | R9 | `rust-generics-traits` | Rust | مقدماتی | ✍️ |
| 26 | 2026-12-14 | 1405/09/23 | G14 | `go-mini-project-url-shortener` | Go | مقدماتی | ✍️ |
| 27 | 2026-12-16 | 1405/09/25 | A5 | `go-graceful-shutdown-workers` | NATS | میانی | ✍️ |
| 28 | 2026-12-18 | 1405/09/27 | GA1 | `go-project-layout-clean-architecture` | Go | پیشرفته | ✍️ |
| 29 | 2026-12-20 | 1405/09/29 | X6 | `security-advisory-2` | آزاد | - | 📝 |
| 30 | 2026-12-22 | 1405/10/01 | R10 | `rust-lifetimes` | Rust | مقدماتی | ✍️ |
| 31 | 2026-12-24 | 1405/10/03 | R11 | `rust-closures-iterators` | Rust | مقدماتی | ✍️ |
| 32 | 2026-12-26 | 1405/10/05 | X1 | `go-vs-rust-when-to-use` | Go + Rust | میانی | ✍️ |
| 33 | 2026-12-28 | 1405/10/07 | GA2 | `go-config-logging-errors` | Go | پیشرفته | ✍️ |
| 34 | 2026-12-30 | 1405/10/09 | R12 | `rust-smart-pointers` | Rust | مقدماتی | ✍️ |
| 35 | 2027-01-01 | 1405/10/11 | A6 | `nats-jetstream-observability` | NATS | میانی | ✍️ |
| 36 | 2027-01-03 | 1405/10/13 | GA3 | `go-http-api-stdlib` | Go | پیشرفته | ✍️ |
| 37 | 2027-01-05 | 1405/10/15 | R13 | `rust-testing-docs` | Rust | مقدماتی | ✍️ |
| 38 | 2027-01-07 | 1405/10/17 | R14 | `rust-concurrency-threads` | Rust | میانی | ✍️ |
| 39 | 2027-01-09 | 1405/10/19 | GA4 | `go-postgres-pgx-sqlc` | Go | پیشرفته | ✍️ |
| 40 | 2027-01-11 | 1405/10/21 | R15 | `rust-async-tokio` | Rust | میانی | ✍️ |
| 41 | 2027-01-13 | 1405/10/23 | X7 | `security-advisory-3` | آزاد | - | 📝 |
| 42 | 2027-01-15 | 1405/10/25 | R16 | `rust-serde-json` | Rust | میانی | ✍️ |
| 43 | 2027-01-17 | 1405/10/27 | A7 | `nats-jetstream-testing` | NATS | میانی | ✍️ |
| 44 | 2027-01-19 | 1405/10/29 | GA5 | `go-transactions-patterns` | Go | پیشرفته | ✍️ |
| 45 | 2027-01-21 | 1405/11/01 | R17 | `rust-http-axum-api` | Rust | میانی | ✍️ |
| 46 | 2027-01-23 | 1405/11/03 | R18 | `rust-database-sqlx` | Rust | میانی | ✍️ |
| 47 | 2027-01-25 | 1405/11/05 | GA6 | `go-concurrency-patterns` | Go | پیشرفته | ✍️ |
| 48 | 2027-01-27 | 1405/11/07 | R19 | `rust-thiserror-anyhow` | Rust | میانی | ✍️ |
| 49 | 2027-01-29 | 1405/11/09 | A8 | `nats-kv-object-store` | NATS | میانی | ✍️ |
| 50 | 2027-01-31 | 1405/11/11 | GA7 | `go-outbox-pattern-nats` | Go | پیشرفته | ✍️ |
| 51 | 2027-02-02 | 1405/11/13 | R20 | `rust-nats-async-client` | Rust | میانی | ✍️ |
| 52 | 2027-02-04 | 1405/11/15 | GA12 | `go-grpc-service` | Go | پیشرفته | ✍️ |
| 53 | 2027-02-06 | 1405/11/17 | X2 | `go-rust-grpc-interop` | Go + Rust | پیشرفته | ✍️ |
| 54 | 2027-02-08 | 1405/11/19 | R21 | `rust-trait-objects-dyn` | Rust | میانی | ✍️ |
| 55 | 2027-02-10 | 1405/11/21 | X8 | `security-advisory-4` | آزاد | - | 📝 |
| 56 | 2027-02-12 | 1405/11/23 | GA8 | `go-rate-limiting-caching` | Go | پیشرفته | ✍️ |
| 57 | 2027-02-14 | 1405/11/25 | R22 | `rust-macros` | Rust | میانی | ✍️ |
| 58 | 2027-02-16 | 1405/11/27 | A9 | `nats-jetstream-production` | NATS | میانی | ✍️ |
| 59 | 2027-02-18 | 1405/11/29 | R23 | `rust-unsafe-ffi` | Rust | میانی | ✍️ |
| 60 | 2027-02-20 | 1405/12/01 | GA9 | `go-profiling-pprof` | Go | پیشرفته | ✍️ |
| 61 | 2027-02-22 | 1405/12/03 | R24 | `rust-performance-criterion` | Rust | میانی | ✍️ |
| 62 | 2027-02-24 | 1405/12/05 | X3 | `go-calls-rust-ffi` | Go + Rust | پیشرفته | ✍️ |
| 63 | 2027-02-26 | 1405/12/07 | R25 | `rust-pin-future-internals` | Rust | پیشرفته | ✍️ |
| 64 | 2027-02-28 | 1405/12/09 | GA10 | `go-docker-ci-deploy` | Go | پیشرفته | ✍️ |
| 65 | 2027-03-02 | 1405/12/11 | GA11 | `go-scheduler-gc-internals` | Go | پیشرفته | ✍️ |
| 66 | 2027-03-04 | 1405/12/13 | R26 | `rust-tracing-observability` | Rust | پیشرفته | ✍️ |
| 67 | 2027-03-06 | 1405/12/15 | R27 | `rust-typestate-patterns` | Rust | پیشرفته | ✍️ |
| 68 | 2027-03-08 | 1405/12/17 | X4 | `go-rust-event-pipeline-capstone` | Go + Rust | پیشرفته | ✍️ |
| 69 | 2027-03-10 | 1405/12/19 | X9 | `security-advisory-5` | آزاد | - | 📝 |
| 70 | 2027-03-12 | 1405/12/21 | R28 | `rust-docker-ci-release` | Rust | پیشرفته | ✍️ |
| 71 | 2027-03-14 | 1405/12/23 | R29 | `rust-wasm` | Rust | پیشرفته | ✍️ |
| 72 | 2027-03-16 | 1405/12/25 | X10 | `year-1405-go-recap` | آزاد | - | ✍️ |
| 73 | 2027-03-18 | 1405/12/27 | R30 | `rust-capstone-service` | Rust | پیشرفته | ✍️ |
| 74 | 2027-03-20 | 1405/12/29 | X11 | `year-1405-rust-recap` | آزاد | - | ✍️ |

پست‌های منتشرشده‌ی قبلی: `nats-jetstream-go` (A1) و `nats-jetstream-retry-dlq` (A2) در ۱۸ اکتبر ۲۰۲۶، و دو پست هشدار امنیتی (PHP و GitLab).

## عنوان‌ها

| شناسه | عنوان فارسی | عنوان انگلیسی |
|---|---|---|
| A3 | چند Worker روی یک Consumer و مانیتورینگ lag در JetStream | Multiple workers on one consumer and monitoring lag in JetStream |
| G1 | شروع کار با Go: نصب، ماژول و ابزارها | Getting started with Go: install, modules, tooling |
| R1 | شروع کار با Rust: نصب، Cargo و اولین برنامه | Getting started with Rust: install, Cargo and a first program |
| G2 | نوع‌ها، متغیرها و کنترل جریان در Go | Types, variables and control flow in Go |
| R2 | نوع‌ها، متغیرها و کنترل جریان در Rust | Types, variables and control flow in Rust |
| G3 | توابع، defer و مدیریت خطا در Go | Functions, defer and error handling in Go |
| G4 | Slice، Map و String در Go | Slices, maps and strings in Go |
| R3 | Ownership در Rust | Ownership in Rust |
| G5 | Struct، متد و Interface در Go | Structs, methods and interfaces in Go |
| G6 | اشاره‌گرها و مدل حافظه در Go | Pointers and the memory model in Go |
| R4 | Borrowing و Reference در Rust | Borrowing and references in Rust |
| X5 | هشدار امنیتی ۱ | Security advisory 1 |
| G7 | پکیج‌ها و ماژول‌ها: ساختار پروژه‌ی Go | Packages and modules: structuring a Go project |
| R5 | Struct، Enum و Pattern Matching در Rust | Structs, enums and pattern matching in Rust |
| G8 | Goroutine و Channel در Go | Goroutines and channels in Go |
| A4 | Idempotency و معنای exactly-once در JetStream | Idempotency and the meaning of exactly-once in JetStream |
| G9 | sync، select و context در Go | sync, select and context in Go |
| R6 | Collectionها و String در Rust | Collections and strings in Rust |
| G10 | Generics در Go | Generics in Go |
| R7 | مدیریت خطا با Result و Option در Rust | Error handling with Result and Option in Rust |
| G11 | تست در Go: table-driven و benchmark | Testing in Go: table-driven tests and benchmarks |
| G12 | کار با فایل، io.Reader/Writer و JSON در Go | Files, io.Reader/Writer and JSON in Go |
| R8 | Module، Crate و Cargo در Rust | Modules, crates and Cargo in Rust |
| G13 | ساخت ابزار خط فرمان با Go | Building a command-line tool in Go |
| R9 | Generics و Trait در Rust | Generics and traits in Rust |
| G14 | پروژه‌ی کوچک: URL shortener با Go | Mini project: a URL shortener in Go |
| A5 | خاموشی تمیز Workerها در Go | Graceful shutdown for Go workers |
| GA1 | ساختار پروژه و Clean Architecture در Go | Project layout and clean architecture in Go |
| X6 | هشدار امنیتی ۲ | Security advisory 2 |
| R10 | Lifetime در Rust | Lifetimes in Rust |
| R11 | Closure و Iterator در Rust | Closures and iterators in Rust |
| X1 | Go یا Rust؟ هرکدام برای چه کاری | Go or Rust? When to use which |
| GA2 | کانفیگ، لاگ ساختاریافته و خطا در Go | Config, structured logging and errors in Go |
| R12 | Smart Pointerها: Box، Rc و RefCell | Smart pointers: Box, Rc and RefCell |
| A6 | Observability برای JetStream: متریک، لاگ و trace | Observability for JetStream: metrics, logs and traces |
| GA3 | ساخت API با net/http در Go | Building an API with net/http in Go |
| R13 | تست و مستندسازی در Rust | Testing and documentation in Rust |
| R14 | Concurrency با Thread در Rust | Concurrency with threads in Rust |
| GA4 | Postgres با pgx و sqlc در Go | Postgres with pgx and sqlc in Go |
| R15 | async/await و Tokio در Rust | async/await and Tokio in Rust |
| X7 | هشدار امنیتی ۳ | Security advisory 3 |
| R16 | Serde و JSON در Rust | Serde and JSON in Rust |
| A7 | تست سرویس‌های JetStream با nats-server توکار | Testing JetStream services with an embedded nats-server |
| GA5 | تراکنش و الگوی Repository در Go | Transactions and the repository pattern in Go |
| R17 | ساخت API با Axum در Rust | Building an API with Axum in Rust |
| R18 | دیتابیس با SQLx در Rust | Databases with SQLx in Rust |
| GA6 | الگوهای concurrency: worker pool و errgroup | Concurrency patterns: worker pool and errgroup |
| R19 | خطا در اپلیکیشن واقعی: thiserror و anyhow | Errors in real apps: thiserror and anyhow |
| A8 | KV و Object Store در NATS | KV and Object Store in NATS |
| GA7 | Outbox Pattern با Postgres و NATS در Go | The outbox pattern with Postgres and NATS in Go |
| R20 | کلاینت async NATS JetStream در Rust | An async NATS JetStream client in Rust |
| GA12 | سرویس gRPC با Go | A gRPC service in Go |
| X2 | ارتباط Go و Rust با gRPC | Go and Rust talking over gRPC |
| R21 | Trait Object و dyn در Rust | Trait objects and dyn in Rust |
| X8 | هشدار امنیتی ۴ | Security advisory 4 |
| GA8 | Rate limit و cache در Go | Rate limiting and caching in Go |
| R22 | ماکروها در Rust | Macros in Rust |
| A9 | JetStream در پروداکشن: cluster، retention و امنیت | JetStream in production: clustering, retention and security |
| R23 | Unsafe و FFI در Rust | Unsafe and FFI in Rust |
| GA9 | پروفایلینگ با pprof در Go | Profiling Go with pprof |
| R24 | پرفورمنس و benchmark با Criterion در Rust | Performance and benchmarking with Criterion in Rust |
| X3 | صدا زدن Rust از Go با FFI | Calling Rust from Go over FFI |
| R25 | Future، Pin و درون async در Rust | Futures, Pin and async internals in Rust |
| GA10 | Docker، CI و دیپلوی سرویس Go | Docker, CI and deploying a Go service |
| GA11 | زمان‌بند runtime و GC در Go | The Go scheduler and garbage collector |
| R26 | Observability در Rust با tracing | Observability in Rust with tracing |
| R27 | الگوی Type-State و طراحی API در Rust | The type-state pattern and API design in Rust |
| X4 | پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS | Capstone: an event pipeline with Go, Rust and NATS |
| X9 | هشدار امنیتی ۵ | Security advisory 5 |
| R28 | Docker، CI و release سرویس Rust | Docker, CI and releasing a Rust service |
| R29 | Rust و WebAssembly | Rust and WebAssembly |
| X10 | مرور سری Go در سال ۱۴۰۵ | Go series recap for 1405 |
| R30 | پروژه‌ی پایانی Rust: یک سرویس کامل | Rust capstone: a complete service |
| X11 | مرور سری Rust و جمع‌بندی سال ۱۴۰۵ | Rust series recap and a look back at 1405 |

## نقاط مهم ترتیب

- A3 اولین پست است چون در پایان A2 وعده‌اش را داده‌ایم.
- Go Fundamentals و Rust مقدماتی جلوتر از موضوع‌های پیشرفته‌ی همان زبان می‌آیند.
- GA7 (Outbox) بعد از A4 و GA5 می‌آید.
- پست‌های ترکیبی Go + Rust (X2 تا X4) بعد از پست‌های مرتبط هر دو زبان (GA12، R20 و R23) آمده‌اند.
- پست جمع‌بندی Rust آخرین پست سال است.

## سئو و تصویر کاور

هر پست باید این‌ها را داشته باشد (برای ۷۴ پست فعلی رعایت شده):

- `title` کوتاه (برچسب `<title>` با پسوند ` | Roham` یا ` | روهام` باید ≤ ۶۰ نویسه باشد). اگر بلندتر شد، کلید `seoTitle` را بگذارید (≤ ۵۲ نویسه انگلیسی، ≤ ۵۰ فارسی).
- `description` بین ۱۱۰ و ۱۵۵ نویسه، با کلیدواژه‌ی اصلی در ابتدا، فقط ادعاهایی که پست پوشش می‌دهد.
- `cover` با تصویر ۱۲۰۰×۶۳۰ برای هر زبان؛ همان خط پیش‌فرض (نمایش در لیست پست‌ها، اشتراک‌گذاری و JSON-LD؛ در صفحه‌ی خود پست مخفی است):
  ```toml
  cover = { image = "/images/covers/<slug>.png", alt = "<title>", hiddenInSingle = true }
  ```
- یک H1 (همان `title`)؛ داخل متن از `##` شروع کنید.

ساخت کاور و افزودن خط `cover` برای پست جدید:

```bash
python3 scripts/generate-covers.py --front-matter   # خط cover را به پست‌های بدون آن اضافه می‌کند
python3 scripts/generate-covers.py                  # کاورهای گم‌شده را می‌سازد (نیاز به Google Chrome)
python3 scripts/generate-covers.py --default        # کاور پیش‌فرض سایت (og-default)
```

سری جدید را به `SER` در `scripts/generate-covers.py` اضافه کنید. صفحه‌هایی که کاور ندارند (خانه، فهرست‌ها) از `og-default[.fa].png` استفاده می‌کنند.

## قالب هر پست

- دو نسخه: `content/posts/<slug>.fa.md` و `<slug>.en.md` با slug یکسان.
- front matter:
  ```toml
  +++
  date = '2026-10-25T10:00:00+03:30'
  draft = false
  title = '...'
  description = '...'
  categories = ["Go"]
  series = ["NATS JetStream"]
  tags = ["go", "nats"]
  +++
  ```
- ساختار: مقدمه‌ی بدون عنوان، «چرا؟»، ساختار و کد، اجرا و نتیجه‌ی واقعی، «چند نکته‌ی مهم»، «قدم بعدی».
- طول: 500 تا 750 کلمه. در آموزش‌های مقدماتی، نمونه‌های کوتاه و تمرین پایان پست.
- پست‌های دنباله‌دار با لینک `/fa/posts/<slug>/` (و `/posts/<slug>/` در انگلیسی) به پست قبلی لینک می‌دهند.
- «قدم بعدی» هر پست باید با ردیف بعدی همین تقویم هم‌خوان باشد.

## چک‌لیست هر پست

- [ ] کد در ریپوی دمو commit شده و واقعاً اجرا شده است (`go run` / `cargo run` / `go test`).
- [ ] نتیجه‌ی اجرا در متن آمده است، نه خروجی حدسی.
- [ ] نسخه‌ی فارسی و انگلیسی هم‌معنا هستند و اصطلاحات فنی بولد شده‌اند.
- [ ] `date` با جدول تقویم یکی است.
- [ ] `hugo --buildFuture` بدون خطا build می‌شود.
- [ ] وضعیت در جدول به ✍️ تغییر کرده است.
- [ ] قبل از push: `ssh-add ~/.ssh/id_rsa_second`.
