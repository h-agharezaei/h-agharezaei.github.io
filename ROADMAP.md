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

<!-- NEW-SERIES-START -->
## سری‌های جدید: برنامه‌ی روزانه (۱۵۶ پست)

از ۶ آبان ۱۴۰۵ هر روز یک پست منتشر می‌شود: پست‌های سری‌های Go و Rust و NATS روی روزهای فرد می‌مانند و سری‌های زیر روزهای خالی را پر می‌کنند. از ۱ فروردین ۱۴۰۶ همه‌ی روزها مال این سری‌هاست و برنامه تا **۲۲ خرداد ۱۴۰۶** (۱۲ ژوئن ۲۰۲۷) ادامه دارد.

- ساعت انتشار ۱۰:۰۰ تهران (`+03:30`)، مثل قبل. پنج روز رزروشده‌ی هشدار امنیتی (۲۵ آبان، ۲۹ آذر، ۲۳ دی، ۲۱ بهمن، ۱۹ اسفند) برای پست‌های واقعی همان هفته خالی می‌مانند.
- هر پست طبق راهنمای [WRITING-GUIDE.md](WRITING-GUIDE.md) نوشته می‌شود: اجرای واقعی، کاور، glossary (فارسی و انگلیسی) و بدون خط `Co-Authored-By`.
- ترتیب سری‌ها طوری است که وابستگی‌ها رعایت شود (Git اول، توزیع‌شده آخر). سری Linux به‌خاطر نبود Linux واقعی روی این ماشین (macOS) دیرتر شروع می‌شود؛ تصمیم Docker یا VM هنوز باز است.

| سری (`series`) | دسته (`categories`) | پست | رنگ کاور |
|---|---|---|---|
| Git | Git | 10 | `#F05033` |
| Node.js | Node.js | 16 | `#6CC24A` |
| Databases | Databases | 16 | `#7C9CFF` |
| Algorithms | Algorithms | 18 | `#F59E0B` |
| Networking | Networking | 14 | `#22D3EE` |
| Python | Python | 16 | `#5B9BD5` |
| Software Security | Security | 16 | `#EF4444` |
| Software Engineering | Engineering | 16 | `#14B8A6` |
| Linux | Linux | 14 | `#FACC15` |
| Distributed Systems | Distributed Systems | 20 | `#D946EF` |

### تقویم

| # | تاریخ میلادی | تاریخ شمسی | شناسه | slug | سری | وضعیت |
|---|---|---|---|---|---|---|
| 1 | 2026-10-28 | 1405/08/06 | GT1 | `git-how-git-thinks` | Git | ✍️ |
| 2 | 2026-10-30 | 1405/08/08 | GT2 | `git-index-staging` | Git | ✍️ |
| 3 | 2026-11-01 | 1405/08/10 | GT3 | `git-branches-head-refs` | Git | ✍️ |
| 4 | 2026-11-03 | 1405/08/12 | GT4 | `git-merge-vs-rebase` | Git | ✍️ |
| 5 | 2026-11-05 | 1405/08/14 | GT5 | `git-resolve-conflicts` | Git | ✍️ |
| 6 | 2026-11-07 | 1405/08/16 | GT6 | `git-undo-reflog-revert` | Git | ✍️ |
| 7 | 2026-11-09 | 1405/08/18 | GT7 | `git-bisect` | Git | ✍️ |
| 8 | 2026-11-11 | 1405/08/20 | ND1 | `node-event-loop` | Node.js | ✍️ |
| 9 | 2026-11-13 | 1405/08/22 | GT8 | `git-hooks-commit-hygiene` | Git | ✍️ |
| 10 | 2026-11-15 | 1405/08/24 | GT9 | `git-submodule-subtree-worktree` | Git | ✍️ |
| 11 | 2026-11-17 | 1405/08/26 | GT10 | `git-workflows-packfiles` | Git | ✍️ |
| 12 | 2026-11-19 | 1405/08/28 | DB1 | `db-relational-sql-essentials` | Databases | ✍️ |
| 13 | 2026-11-21 | 1405/08/30 | ND2 | `node-modules-esm-cjs` | Node.js | ✍️ |
| 14 | 2026-11-23 | 1405/09/02 | DB2 | `db-schema-design-normalization` | Databases | ✍️ |
| 15 | 2026-11-25 | 1405/09/04 | AL1 | `algo-big-o-measured` | Algorithms | ✍️ |
| 16 | 2026-11-27 | 1405/09/06 | ND3 | `node-npm-package-json` | Node.js | ✍️ |
| 17 | 2026-11-29 | 1405/09/08 | DB3 | `db-indexes-btree-explain` | Databases | ✍️ |
| 18 | 2026-12-01 | 1405/09/10 | AL2 | `algo-dynamic-arrays` | Algorithms | ✍️ |
| 19 | 2026-12-03 | 1405/09/12 | ND4 | `node-promises-async-await` | Node.js | ✍️ |
| 20 | 2026-12-05 | 1405/09/14 | DB4 | `db-composite-partial-covering-indexes` | Databases | ✍️ |
| 21 | 2026-12-07 | 1405/09/16 | AL3 | `algo-linked-lists` | Algorithms | ✍️ |
| 22 | 2026-12-09 | 1405/09/18 | DB5 | `db-planner-statistics` | Databases | ✍️ |
| 23 | 2026-12-11 | 1405/09/20 | ND5 | `node-errors-unhandled-rejections` | Node.js | ✍️ |
| 24 | 2026-12-13 | 1405/09/22 | DB6 | `db-transactions-acid` | Databases | ✍️ |
| 25 | 2026-12-15 | 1405/09/24 | AL4 | `algo-hash-tables` | Algorithms | ✍️ |
| 26 | 2026-12-17 | 1405/09/26 | ND6 | `node-streams-backpressure` | Node.js | ✍️ |
| 27 | 2026-12-19 | 1405/09/28 | NW1 | `net-tcp-ip-model` | Networking | ✍️ |
| 28 | 2026-12-21 | 1405/09/30 | DB7 | `db-isolation-levels-anomalies` | Databases | ✍️ |
| 29 | 2026-12-23 | 1405/10/02 | AL5 | `algo-stacks-queues-deques` | Algorithms | ✍️ |
| 30 | 2026-12-25 | 1405/10/04 | NW2 | `net-addressing-subnets` | Networking | ✍️ |
| 31 | 2026-12-27 | 1405/10/06 | ND7 | `node-http-server` | Node.js | ✍️ |
| 32 | 2026-12-29 | 1405/10/08 | DB8 | `db-mvcc-vacuum` | Databases | ✍️ |
| 33 | 2026-12-31 | 1405/10/10 | AL6 | `algo-heaps-priority-queues` | Algorithms | ✍️ |
| 34 | 2027-01-02 | 1405/10/12 | NW3 | `net-dns-in-practice` | Networking | ✍️ |
| 35 | 2027-01-04 | 1405/10/14 | DB9 | `db-locks-deadlocks` | Databases | ✍️ |
| 36 | 2027-01-06 | 1405/10/16 | ND8 | `node-fastify-api` | Node.js | ✍️ |
| 37 | 2027-01-08 | 1405/10/18 | PY1 | `py-environment-uv-venv` | Python | ✍️ |
| 38 | 2027-01-10 | 1405/10/20 | AL7 | `algo-binary-search-invariants` | Algorithms | ✍️ |
| 39 | 2027-01-12 | 1405/10/22 | NW4 | `net-tcp-handshake-states` | Networking | ✍️ |
| 40 | 2027-01-14 | 1405/10/24 | DB10 | `db-jsonb-fulltext-search` | Databases | ✍️ |
| 41 | 2027-01-16 | 1405/10/26 | ND9 | `node-testing-builtin` | Node.js | ✍️ |
| 42 | 2027-01-18 | 1405/10/28 | PY2 | `py-types-control-flow` | Python | ✍️ |
| 43 | 2027-01-20 | 1405/10/30 | AL8 | `algo-sorting` | Algorithms | ✍️ |
| 44 | 2027-01-22 | 1405/11/02 | NW5 | `net-sockets-tcp-from-scratch` | Networking | ✍️ |
| 45 | 2027-01-24 | 1405/11/04 | DB11 | `db-zero-downtime-migrations` | Databases | ✍️ |
| 46 | 2027-01-26 | 1405/11/06 | ND10 | `node-project-structure-config` | Node.js | ✍️ |
| 47 | 2027-01-28 | 1405/11/08 | PY3 | `py-functions-generators` | Python | ✍️ |
| 48 | 2027-01-30 | 1405/11/10 | DB12 | `db-partitioning` | Databases | ✍️ |
| 49 | 2027-02-01 | 1405/11/12 | AL9 | `algo-trees-bst-btree` | Algorithms | ✍️ |
| 50 | 2027-02-03 | 1405/11/14 | NW6 | `net-udp-sockets` | Networking | ✍️ |
| 51 | 2027-02-05 | 1405/11/16 | EN1 | `eng-testing-pyramid-tdd` | Software Engineering | ✍️ |
| 52 | 2027-02-07 | 1405/11/18 | PY4 | `py-classes-dataclasses` | Python | ✍️ |
| 53 | 2027-02-09 | 1405/11/20 | SC1 | `sec-threat-modeling-stride` | Software Security | ✍️ |
| 54 | 2027-02-11 | 1405/11/22 | ND11 | `node-postgres-pg` | Node.js | ✍️ |
| 55 | 2027-02-13 | 1405/11/24 | DB13 | `db-replication-streaming` | Databases | ✍️ |
| 56 | 2027-02-15 | 1405/11/26 | NW7 | `net-http1-by-hand` | Networking | ✍️ |
| 57 | 2027-02-17 | 1405/11/28 | AL10 | `algo-tries-union-find` | Algorithms | ✍️ |
| 58 | 2027-02-19 | 1405/11/30 | EN2 | `eng-property-based-testing` | Software Engineering | ✍️ |
| 59 | 2027-02-21 | 1405/12/02 | SC2 | `sec-owasp-top10-in-code` | Software Security | ✍️ |
| 60 | 2027-02-23 | 1405/12/04 | PY5 | `py-errors-context-managers` | Python | ✍️ |
| 61 | 2027-02-25 | 1405/12/06 | DB14 | `db-backup-restore-pitr` | Databases | ✍️ |
| 62 | 2027-02-27 | 1405/12/08 | ND12 | `node-nats-jetstream` | Node.js | ✍️ |
| 63 | 2027-03-01 | 1405/12/10 | NW8 | `net-tls-openssl` | Networking | ✍️ |
| 64 | 2027-03-03 | 1405/12/12 | EN3 | `eng-refactoring-safely` | Software Engineering | ✍️ |
| 65 | 2027-03-05 | 1405/12/14 | AL11 | `algo-graphs-bfs-dfs` | Algorithms | ✍️ |
| 66 | 2027-03-07 | 1405/12/16 | SC3 | `sec-injection-xss` | Software Security | ✍️ |
| 67 | 2027-03-09 | 1405/12/18 | DB15 | `db-connection-pooling` | Databases | ✍️ |
| 68 | 2027-03-11 | 1405/12/20 | PY6 | `py-type-hints-mypy` | Python | ✍️ |
| 69 | 2027-03-13 | 1405/12/22 | NW9 | `net-http2` | Networking | ✍️ |
| 70 | 2027-03-15 | 1405/12/24 | ND13 | `node-validation-zod` | Node.js | ✍️ |
| 71 | 2027-03-17 | 1405/12/26 | EN4 | `eng-code-review` | Software Engineering | ✍️ |
| 72 | 2027-03-19 | 1405/12/28 | LX1 | `linux-shell-practical` | Linux | ✍️ |
| 73 | 2027-03-21 | 1406/01/01 | AL12 | `algo-shortest-paths-dijkstra` | Algorithms | ✍️ |
| 74 | 2027-03-22 | 1406/01/02 | SC4 | `sec-password-hashing` | Software Security | ✍️ |
| 75 | 2027-03-23 | 1406/01/03 | DB16 | `db-slow-query-case-study` | Databases | ✍️ |
| 76 | 2027-03-24 | 1406/01/04 | PY7 | `py-testing-pytest` | Python | ✍️ |
| 77 | 2027-03-25 | 1406/01/05 | NW10 | `net-websocket` | Networking | ✍️ |
| 78 | 2027-03-26 | 1406/01/06 | EN5 | `eng-api-design-versioning-pagination` | Software Engineering | ✍️ |
| 79 | 2027-03-27 | 1406/01/07 | LX2 | `linux-filesystem-permissions` | Linux | ✍️ |
| 80 | 2027-03-28 | 1406/01/08 | ND14 | `node-worker-threads-cluster` | Node.js | ✍️ |
| 81 | 2027-03-29 | 1406/01/09 | SC5 | `sec-sessions-vs-jwt` | Software Security | ✍️ |
| 82 | 2027-03-30 | 1406/01/10 | AL13 | `algo-topological-sort` | Algorithms | ✍️ |
| 83 | 2027-03-31 | 1406/01/11 | PY8 | `py-gil-threading` | Python | ✍️ |
| 84 | 2027-04-01 | 1406/01/12 | NW11 | `net-grpc-over-http2` | Networking | ✍️ |
| 85 | 2027-04-02 | 1406/01/13 | SC6 | `sec-oauth2-oidc` | Software Security | ✍️ |
| 86 | 2027-04-03 | 1406/01/14 | LX3 | `linux-processes-signals` | Linux | ✍️ |
| 87 | 2027-04-04 | 1406/01/15 | EN6 | `eng-openapi-contracts` | Software Engineering | ✍️ |
| 88 | 2027-04-05 | 1406/01/16 | ND15 | `node-profiling-memory-shutdown` | Node.js | ✍️ |
| 89 | 2027-04-06 | 1406/01/17 | AL14 | `algo-dynamic-programming-1` | Algorithms | 📝 |
| 90 | 2027-04-07 | 1406/01/18 | PY9 | `py-multiprocessing` | Python | 📝 |
| 91 | 2027-04-08 | 1406/01/19 | NW12 | `net-load-balancer-l4-l7` | Networking | 📝 |
| 92 | 2027-04-09 | 1406/01/20 | SC7 | `sec-authorization-rbac-idor` | Software Security | 📝 |
| 93 | 2027-04-10 | 1406/01/21 | LX4 | `linux-proc-observability` | Linux | 📝 |
| 94 | 2027-04-11 | 1406/01/22 | EN7 | `eng-technical-debt` | Software Engineering | 📝 |
| 95 | 2027-04-12 | 1406/01/23 | AL15 | `algo-dynamic-programming-2` | Algorithms | 📝 |
| 96 | 2027-04-13 | 1406/01/24 | ND16 | `node-vs-go-when-to-use` | Node.js | 📝 |
| 97 | 2027-04-14 | 1406/01/25 | PY10 | `py-asyncio` | Python | 📝 |
| 98 | 2027-04-15 | 1406/01/26 | DS1 | `ds-why-distributed-is-hard` | Distributed Systems | 📝 |
| 99 | 2027-04-16 | 1406/01/27 | NW13 | `net-troubleshooting-curl-traceroute` | Networking | 📝 |
| 100 | 2027-04-17 | 1406/01/28 | SC8 | `sec-csrf-cors-headers` | Software Security | 📝 |
| 101 | 2027-04-18 | 1406/01/29 | LX5 | `linux-systemd-units-timers` | Linux | 📝 |
| 102 | 2027-04-19 | 1406/01/30 | EN8 | `eng-adr-documentation` | Software Engineering | 📝 |
| 103 | 2027-04-20 | 1406/01/31 | DS2 | `ds-cap-pacelc` | Distributed Systems | 📝 |
| 104 | 2027-04-21 | 1406/02/01 | AL16 | `algo-greedy-backtracking` | Algorithms | 📝 |
| 105 | 2027-04-22 | 1406/02/02 | PY11 | `py-fastapi-pydantic` | Python | 📝 |
| 106 | 2027-04-23 | 1406/02/03 | NW14 | `net-slow-request-case-study` | Networking | 📝 |
| 107 | 2027-04-24 | 1406/02/04 | SC9 | `sec-tls-x509-certificates` | Software Security | 📝 |
| 108 | 2027-04-25 | 1406/02/05 | DS3 | `ds-consistency-models` | Distributed Systems | 📝 |
| 109 | 2027-04-26 | 1406/02/06 | LX6 | `linux-cgroups-namespaces` | Linux | 📝 |
| 110 | 2027-04-27 | 1406/02/07 | EN9 | `eng-feature-flags-trunk-based` | Software Engineering | 📝 |
| 111 | 2027-04-28 | 1406/02/08 | AL17 | `algo-string-algorithms` | Algorithms | 📝 |
| 112 | 2027-04-29 | 1406/02/09 | DS4 | `ds-logical-clocks` | Distributed Systems | 📝 |
| 113 | 2027-04-30 | 1406/02/10 | SC10 | `sec-secrets-management` | Software Security | 📝 |
| 114 | 2027-05-01 | 1406/02/11 | PY12 | `py-sqlalchemy-postgres` | Python | 📝 |
| 115 | 2027-05-02 | 1406/02/12 | LX7 | `linux-memory-page-cache-oom` | Linux | 📝 |
| 116 | 2027-05-03 | 1406/02/13 | EN10 | `eng-ci-cd-pipeline-design` | Software Engineering | 📝 |
| 117 | 2027-05-04 | 1406/02/14 | DS5 | `ds-timeouts-retries-backoff` | Distributed Systems | 📝 |
| 118 | 2027-05-05 | 1406/02/15 | SC11 | `sec-supply-chain-vulns` | Software Security | 📝 |
| 119 | 2027-05-06 | 1406/02/16 | AL18 | `algo-bloom-filter-consistent-hashing` | Algorithms | 📝 |
| 120 | 2027-05-07 | 1406/02/17 | PY13 | `py-packaging-publishing` | Python | 📝 |
| 121 | 2027-05-08 | 1406/02/18 | DS6 | `ds-circuit-breaker-bulkhead` | Distributed Systems | 📝 |
| 122 | 2027-05-09 | 1406/02/19 | LX8 | `linux-io-epoll` | Linux | 📝 |
| 123 | 2027-05-10 | 1406/02/20 | EN11 | `eng-sli-slo-error-budgets` | Software Engineering | 📝 |
| 124 | 2027-05-11 | 1406/02/21 | DS7 | `ds-replication-quorum` | Distributed Systems | 📝 |
| 125 | 2027-05-12 | 1406/02/22 | SC12 | `sec-ssrf-deserialization` | Software Security | 📝 |
| 126 | 2027-05-13 | 1406/02/23 | PY14 | `py-cli-scripts` | Python | 📝 |
| 127 | 2027-05-14 | 1406/02/24 | LX9 | `linux-networking-ip-ss-nftables` | Linux | 📝 |
| 128 | 2027-05-15 | 1406/02/25 | DS8 | `ds-sharding-consistent-hashing` | Distributed Systems | 📝 |
| 129 | 2027-05-16 | 1406/02/26 | EN12 | `eng-postmortems-blameless` | Software Engineering | 📝 |
| 130 | 2027-05-17 | 1406/02/27 | SC13 | `sec-crypto-mistakes` | Software Security | 📝 |
| 131 | 2027-05-18 | 1406/02/28 | DS9 | `ds-consensus-raft` | Distributed Systems | 📝 |
| 132 | 2027-05-19 | 1406/02/29 | PY15 | `py-data-csv-sqlite` | Python | 📝 |
| 133 | 2027-05-20 | 1406/02/30 | LX10 | `linux-ssh-keys` | Linux | 📝 |
| 134 | 2027-05-21 | 1406/02/31 | EN13 | `eng-legacy-code` | Software Engineering | 📝 |
| 135 | 2027-05-22 | 1406/03/01 | SC14 | `sec-memory-safety-c-vs-rust` | Software Security | 📝 |
| 136 | 2027-05-23 | 1406/03/02 | DS10 | `ds-saga-vs-2pc` | Distributed Systems | 📝 |
| 137 | 2027-05-24 | 1406/03/03 | PY16 | `py-ffi-pyo3-ctypes` | Python | 📝 |
| 138 | 2027-05-25 | 1406/03/04 | LX11 | `linux-users-sudo-capabilities` | Linux | 📝 |
| 139 | 2027-05-26 | 1406/03/05 | DS11 | `ds-cqrs-event-sourcing` | Distributed Systems | 📝 |
| 140 | 2027-05-27 | 1406/03/06 | SC15 | `sec-fuzzing` | Software Security | 📝 |
| 141 | 2027-05-28 | 1406/03/07 | EN14 | `eng-ddd-basics` | Software Engineering | 📝 |
| 142 | 2027-05-29 | 1406/03/08 | DS12 | `ds-messaging-event-driven` | Distributed Systems | 📝 |
| 143 | 2027-05-30 | 1406/03/09 | LX12 | `linux-logs-journalctl` | Linux | 📝 |
| 144 | 2027-05-31 | 1406/03/10 | SC16 | `sec-logging-audit-incident-response` | Software Security | 📝 |
| 145 | 2027-06-01 | 1406/03/11 | DS13 | `ds-service-discovery-load-balancing` | Distributed Systems | 📝 |
| 146 | 2027-06-02 | 1406/03/12 | EN15 | `eng-monorepo-vs-polyrepo` | Software Engineering | 📝 |
| 147 | 2027-06-03 | 1406/03/13 | DS14 | `ds-distributed-rate-limiting` | Distributed Systems | 📝 |
| 148 | 2027-06-04 | 1406/03/14 | LX13 | `linux-strace-perf` | Linux | 📝 |
| 149 | 2027-06-05 | 1406/03/15 | EN16 | `eng-estimation-planning` | Software Engineering | 📝 |
| 150 | 2027-06-06 | 1406/03/16 | DS15 | `ds-fault-injection-testing` | Distributed Systems | 📝 |
| 151 | 2027-06-07 | 1406/03/17 | LX14 | `linux-scripting-cron-safely` | Linux | 📝 |
| 152 | 2027-06-08 | 1406/03/18 | DS16 | `ds-modular-monolith-vs-microservices` | Distributed Systems | 📝 |
| 153 | 2027-06-09 | 1406/03/19 | DS17 | `ds-deployment-strategies` | Distributed Systems | 📝 |
| 154 | 2027-06-10 | 1406/03/20 | DS18 | `ds-capacity-estimation` | Distributed Systems | 📝 |
| 155 | 2027-06-11 | 1406/03/21 | DS19 | `ds-case-studies` | Distributed Systems | 📝 |
| 156 | 2027-06-12 | 1406/03/22 | DS20 | `ds-capstone` | Distributed Systems | 📝 |

### عنوان‌ها

| شناسه | عنوان فارسی | عنوان انگلیسی |
|---|---|---|
| GT1 | گیت چطور فکر می‌کند: object و hash | How Git thinks: objects and hashes |
| GT2 | index و staging: سه ناحیه‌ی گیت | The index and staging: Git's three areas |
| GT3 | branch، HEAD و ref: فقط اشاره‌گر | Branches, HEAD and refs: just pointers |
| GT4 | merge یا rebase؟ دو تاریخچه‌ی واقعی | Merge or rebase? Two real histories |
| GT5 | حل conflict و rerere | Resolving conflicts and rerere |
| GT6 | برگرداندن کار: reflog، revert و cherry-pick | Undoing work: reflog, revert and cherry-pick |
| GT7 | پیدا کردن باگ با git bisect | Finding a bug with git bisect |
| ND1 | event loop در Node.js | The Node.js event loop |
| GT8 | hookها و commit message تمیز | Hooks and clean commit messages |
| GT9 | submodule، subtree و worktree | Submodules, subtrees and worktrees |
| GT10 | workflowهای تیمی و درون packfile | Team workflows and packfiles inside |
| DB1 | مدل رابطه‌ای و SQL ضروری | The relational model and essential SQL |
| ND2 | ماژول‌ها: ESM و CommonJS | Modules: ESM and CommonJS |
| DB2 | طراحی schema و نرمال‌سازی | Schema design and normalization |
| AL1 | تحلیل Big-O با اندازه‌گیری واقعی | Big-O analysis with real measurements |
| ND3 | npm، package.json و قفل وابستگی | npm, package.json and lockfiles |
| DB3 | ایندکس B-tree و EXPLAIN ANALYZE | B-tree indexes and EXPLAIN ANALYZE |
| AL2 | آرایه‌ی پویا و slice از درون | Dynamic arrays and slices from the inside |
| ND4 | Promise و async/await در Node.js | Promises and async/await in Node.js |
| DB4 | ایندکس ترکیبی، جزئی و پوششی | Composite, partial and covering indexes |
| AL3 | لیست پیوندی و چرا کم‌کاربرد است | Linked lists and why they are rarely the answer |
| DB5 | planner و آمار: چرا ایندکس استفاده نمی‌شود | The planner and statistics: why an index is not used |
| ND5 | خطا و unhandled rejection در Node.js | Errors and unhandled rejections in Node.js |
| DB6 | تراکنش و ACID | Transactions and ACID |
| AL4 | hash table از صفر | A hash table from scratch |
| ND6 | stream و backpressure در Node.js | Streams and backpressure in Node.js |
| NW1 | مدل TCP/IP و مسیر یک بسته | The TCP/IP model and the path of a packet |
| DB7 | سطح‌های ایزولاسیون و ناهنجاری‌ها | Isolation levels and anomalies |
| AL5 | stack، queue و deque | Stacks, queues and deques |
| NW2 | آدرس‌دهی IP و subnet | IP addressing and subnets |
| ND7 | سرور HTTP با node:http | An HTTP server with node:http |
| DB8 | MVCC و VACUUM | MVCC and VACUUM |
| AL6 | heap و priority queue | Heaps and priority queues |
| NW3 | DNS در عمل | DNS in practice |
| DB9 | قفل و deadlock در دیتابیس | Locks and deadlocks in the database |
| ND8 | ساخت API با Fastify | Building an API with Fastify |
| PY1 | محیط Python: venv و uv | The Python environment: venv and uv |
| AL7 | جست‌وجوی دودویی و invariant | Binary search and invariants |
| NW4 | TCP: دست‌دادن و حالت‌های اتصال | TCP: the handshake and connection states |
| DB10 | JSONB و جست‌وجوی متنی | JSONB and full-text search |
| ND9 | تست در Node.js با node:test | Testing in Node.js with node:test |
| PY2 | نوع‌ها و کنترل جریان در Python | Types and control flow in Python |
| AL8 | مرتب‌سازی: quick، merge و heap | Sorting: quick, merge and heap |
| NW5 | سرور و کلاینت TCP از صفر | A TCP server and client from scratch |
| DB11 | migration بدون downtime | Zero-downtime migrations |
| ND10 | ساختار پروژه و کانفیگ در Node.js | Project structure and config in Node.js |
| PY3 | توابع، closure و generator در Python | Functions, closures and generators in Python |
| DB12 | partitioning جدول‌ها | Table partitioning |
| AL9 | درخت جست‌وجو و B-tree | Search trees and the B-tree |
| NW6 | UDP و تفاوتش با TCP | UDP and how it differs from TCP |
| EN1 | هرم تست و TDD | The test pyramid and TDD |
| PY4 | کلاس و dataclass در Python | Classes and dataclasses in Python |
| SC1 | مدل‌سازی تهدید با STRIDE | Threat modeling with STRIDE |
| ND11 | Postgres از Node.js با pg | Postgres from Node.js with pg |
| DB13 | replication با دو instance واقعی | Replication with two real instances |
| NW7 | HTTP/1.1 با دست | HTTP/1.1 by hand |
| AL10 | trie و union-find | Tries and union-find |
| EN2 | تست خاصیت‌محور | Property-based testing |
| SC2 | OWASP Top 10 در کد واقعی | The OWASP Top 10 in real code |
| PY5 | خطا و context manager در Python | Errors and context managers in Python |
| DB14 | backup، restore و PITR | Backup, restore and PITR |
| ND12 | NATS JetStream از Node.js | NATS JetStream from Node.js |
| NW8 | TLS و گواهی با openssl | TLS and certificates with openssl |
| EN3 | refactor امن | Refactoring safely |
| AL11 | گراف: BFS و DFS | Graphs: BFS and DFS |
| SC3 | تزریق و XSS | Injection and XSS |
| DB15 | connection pool و حالت‌های خرابی | Connection pooling and its failure modes |
| PY6 | type hint و mypy | Type hints and mypy |
| NW9 | HTTP/2 و فرق‌هایش | HTTP/2 and what changes |
| ND13 | اعتبارسنجی ورودی با Zod | Input validation with Zod |
| EN4 | code review مؤثر | Effective code review |
| LX1 | پوسته‌ی کاربردی: pipe، redirect و xargs | The practical shell: pipes, redirects and xargs |
| AL12 | کوتاه‌ترین مسیر و Dijkstra | Shortest paths and Dijkstra |
| SC4 | ذخیره‌ی امن پسورد: argon2 و bcrypt | Storing passwords safely: argon2 and bcrypt |
| DB16 | case study: پیدا کردن و رفع یک query کند | Case study: finding and fixing a slow query |
| PY7 | تست در Python با pytest | Testing in Python with pytest |
| NW10 | WebSocket | WebSocket |
| EN5 | طراحی API: نسخه‌بندی و pagination | API design: versioning and pagination |
| LX2 | سیستم فایل و مجوزها | The filesystem and permissions |
| ND14 | worker thread و cluster در Node.js | Worker threads and cluster in Node.js |
| SC5 | session یا JWT؟ | Sessions or JWT? |
| AL13 | topological sort و وابستگی‌ها | Topological sort and dependencies |
| PY8 | GIL و threading | The GIL and threading |
| NW11 | gRPC روی HTTP/2 | gRPC over HTTP/2 |
| SC6 | OAuth2 و OIDC | OAuth2 and OIDC |
| LX3 | پروسه و سیگنال | Processes and signals |
| EN6 | OpenAPI و قرارداد API | OpenAPI and API contracts |
| ND15 | پروفایل، حافظه و خاموشی تمیز در Node.js | Profiling, memory and graceful shutdown in Node.js |
| AL14 | برنامه‌ریزی پویا ۱: ایده و memoization | Dynamic programming 1: the idea and memoization |
| PY9 | multiprocessing در Python | Multiprocessing in Python |
| NW12 | load balancer لایه‌ی ۴ و ۷ | Layer 4 and layer 7 load balancers |
| SC7 | مجوزدهی: RBAC و IDOR | Authorization: RBAC and IDOR |
| LX4 | /proc و مشاهده‌ی سیستم | /proc and observing the system |
| EN7 | بدهی فنی | Technical debt |
| AL15 | برنامه‌ریزی پویا ۲: مسئله‌های کلاسیک | Dynamic programming 2: classic problems |
| ND16 | Node.js یا Go؟ هرکدام برای چه کاری | Node.js or Go? When to use which |
| PY10 | asyncio در Python | asyncio in Python |
| DS1 | چرا سیستم توزیع‌شده سخت است | Why distributed systems are hard |
| NW13 | عیب‌یابی شبکه با curl، dig و traceroute | Network troubleshooting with curl, dig and traceroute |
| SC8 | CSRF، CORS و هدرهای امنیتی | CSRF, CORS and security headers |
| LX5 | systemd: واحدها و timerها | systemd: units and timers |
| EN8 | ADR و مستندسازی تصمیم‌ها | ADRs and documenting decisions |
| DS2 | CAP و PACELC درست | CAP and PACELC, correctly |
| AL16 | greedy و backtracking | Greedy algorithms and backtracking |
| PY11 | ساخت API با FastAPI و Pydantic | Building an API with FastAPI and Pydantic |
| NW14 | case study: چرا این درخواست کند است | Case study: why is this request slow |
| SC9 | TLS و گواهی x509 در عمل | TLS and x509 certificates in practice |
| DS3 | مدل‌های consistency | Consistency models |
| LX6 | cgroup و namespace: پایه‌ی کانتینر | cgroups and namespaces: the base of containers |
| EN9 | feature flag و trunk-based development | Feature flags and trunk-based development |
| AL17 | الگوریتم‌های رشته: KMP و Rabin–Karp | String algorithms: KMP and Rabin–Karp |
| DS4 | ساعت منطقی: Lamport و vector clock | Logical clocks: Lamport and vector clocks |
| SC10 | مدیریت راز و کلید | Managing secrets and keys |
| PY12 | SQLAlchemy و Postgres | SQLAlchemy and Postgres |
| LX7 | حافظه، page cache و OOM killer | Memory, the page cache and the OOM killer |
| EN10 | طراحی pipeline برای CI/CD | Designing a CI/CD pipeline |
| DS5 | timeout، retry و backoff با jitter | Timeouts, retries and backoff with jitter |
| SC11 | زنجیره‌ی تأمین و آسیب‌پذیری وابستگی‌ها | The supply chain and vulnerable dependencies |
| AL18 | Bloom filter و consistent hashing | Bloom filters and consistent hashing |
| PY13 | بسته‌بندی و انتشار پروژه‌ی Python | Packaging and publishing a Python project |
| DS6 | circuit breaker و bulkhead | Circuit breakers and bulkheads |
| LX8 | I/O و epoll | I/O and epoll |
| EN11 | SLI، SLO و error budget | SLIs, SLOs and error budgets |
| DS7 | replication و quorum | Replication and quorums |
| SC12 | SSRF و deserialization ناامن | SSRF and unsafe deserialization |
| PY14 | ابزار خط فرمان و اسکریپت‌نویسی با Python | Command-line tools and scripts with Python |
| LX9 | شبکه در Linux: ip، ss و nftables | Linux networking: ip, ss and nftables |
| DS8 | sharding و consistent hashing | Sharding and consistent hashing |
| EN12 | postmortem بدون سرزنش | Blameless postmortems |
| SC13 | اشتباه‌های رایج رمزنگاری | Common cryptography mistakes |
| DS9 | consensus و Raft | Consensus and Raft |
| PY15 | پردازش داده‌ی کوچک با csv و sqlite3 | Small data processing with csv and sqlite3 |
| LX10 | SSH و کلیدها | SSH and keys |
| EN13 | کار با کد legacy | Working with legacy code |
| SC14 | امنیت حافظه: C در برابر Rust | Memory safety: C versus Rust |
| DS10 | saga یا 2PC؟ | Sagas or two-phase commit? |
| PY16 | صدا زدن Rust از Python با ctypes و PyO3 | Calling Rust from Python with ctypes and PyO3 |
| LX11 | کاربر، sudo و capability | Users, sudo and capabilities |
| DS11 | CQRS و event sourcing | CQRS and event sourcing |
| SC15 | fuzzing برای پیدا کردن باگ امنیتی | Fuzzing to find security bugs |
| EN14 | مبانی DDD | Domain-driven design basics |
| DS12 | پیام‌رسانی و معماری رویدادمحور | Messaging and event-driven architecture |
| LX12 | لاگ‌ها و journalctl | Logs and journalctl |
| SC16 | لاگ، audit و واکنش به حادثه | Logging, auditing and incident response |
| DS13 | service discovery و load balancing | Service discovery and load balancing |
| EN15 | monorepo یا polyrepo؟ | Monorepo or polyrepo? |
| DS14 | rate limit توزیع‌شده | Distributed rate limiting |
| LX13 | strace و perf برای عیب‌یابی | strace and perf for troubleshooting |
| EN16 | برآورد و برنامه‌ریزی | Estimation and planning |
| DS15 | تست خرابی با تزریق خطا | Failure testing with fault injection |
| LX14 | اسکریپت‌نویسی ایمن و cron | Safe scripting and cron |
| DS16 | modular monolith یا microservice؟ | Modular monolith or microservices? |
| DS17 | روش‌های استقرار: blue-green و canary | Deployment strategies: blue-green and canary |
| DS18 | برآورد ظرفیت | Capacity estimation |
| DS19 | case study: rate limiter و سامانه‌ی اعلان | Case studies: a rate limiter and a notification system |
| DS20 | پروژه‌ی پایانی توزیع‌شده | Distributed systems capstone |
<!-- NEW-SERIES-END -->
