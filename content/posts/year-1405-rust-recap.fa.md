+++
date = '2027-03-20T10:00:00+03:30'
draft = false
title = 'مرور سری Rust و جمع‌بندی سال ۱۴۰۵'
description = 'نقشه‌ی هر ۳۰ پست سری Rust، درس‌هایی که مدام تکرار شدند، مقایسه‌ی صادقانه‌ی Go و Rust، شمارش واقعی پست‌ها و کارهای نیمه‌تمام در پایان سال ۱۴۰۵.'
categories = ["Meta"]
tags = ["rust", "go", "recap", "1405"]
cover = { image = "/images/covers/year-1405-rust-recap.fa.png", alt = "مرور سری Rust و جمع‌بندی سال ۱۴۰۵", hiddenInSingle = true }
+++

امروز آخرین روز سال ۱۴۰۵ است. بعد از [مرور سری Go در سال ۱۴۰۵](/fa/posts/year-1405-go-recap/)، این پست مرور Rust است: نقشه‌ی هر ۳۰ پست، چیزهایی که مدام برمی‌گشتند و چیزهایی که کم دارم. هر نکته از همان پستی آمده که لینکش را زده‌ام.

## سری Rust به ترتیب خواندن

**قدم‌های اول**

- [شروع کار با Rust: نصب، Cargo و اولین برنامه](/fa/posts/rust-getting-started/): در زمان ویرایش `cargo check`
- [نوع‌ها، متغیرها و کنترل جریان در Rust](/fa/posts/rust-types-control-flow/): یک سمی‌کالن اضافه دردسر می‌شود

**Ownership و نوع‌های پایه**

- [Ownership در Rust](/fa/posts/rust-ownership/): بی‌فکر `.clone()` نزن
- [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/): برچسب‌های خطا را بخوان
- [Struct، Enum و Pattern Matching در Rust](/fa/posts/rust-structs-enums-pattern-matching/): `match` همه‌ی حالت‌ها را می‌پوشاند
- [Collectionها و String در Rust](/fa/posts/rust-collections-strings/): `&str` بگیر، `String` برگردان
- [مدیریت خطا با Result و Option در Rust](/fa/posts/rust-error-handling-result/): خطا در نوع برگشتی است

**انتزاع‌ها**

- [Module، Crate و Cargo در Rust](/fa/posts/rust-modules-crates-cargo/): بدون `mod` فایل نادیده می‌ماند
- [Generics و Trait در Rust](/fa/posts/rust-generics-traits/): bound را هرجا کامپایلر خواست اضافه کن
- [Lifetime در Rust](/fa/posts/rust-lifetimes/): annotation توصیف می‌کند، عمر را بیشتر نمی‌کند
- [Closure و Iterator در Rust](/fa/posts/rust-closures-iterators/): iteratorها lazy هستند
- [Smart Pointerها: Box، Rc و RefCell در Rust](/fa/posts/rust-smart-pointers/): اول borrow
- [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/): مثال‌های مستند به‌شکل تست اجرا می‌شوند
- [Trait Object و dyn در Rust](/fa/posts/rust-trait-objects-dyn/): polymorphism زمان اجرا
- [ماکروها در Rust](/fa/posts/rust-macros/): تابع را ترجیح بده

**Concurrency و async**

- [Concurrency با Thread در Rust](/fa/posts/rust-concurrency-threads/): data race نه، deadlock هنوز
- [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/): future تا `.await` منتظر می‌ماند
- [Future، Pin و درون async در Rust](/fa/posts/rust-pin-future-internals/): بدون wake-up پیشرفتی نیست

**ساخت سرویس**

- [Serde و JSON در Rust](/fa/posts/rust-serde-json/): نمایش enum را آگاهانه انتخاب کن
- [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/): extractor بدنه آخر می‌آید
- [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/): از `SELECT *` دوری کن
- [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/): `anyhow` در کتاب‌خانه نه
- [کلاینت async NATS JetStream در Rust](/fa/posts/rust-nats-async-client/): `ack_wait` بالاتر از زمان پردازش
- [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/): `spawn` span را گم می‌کند
- [Docker، CI و release سرویس Rust](/fa/posts/rust-docker-ci-release/): من `docker build` را اجرا نکردم
- [پروژه‌ی پایانی Rust: یک سرویس کامل](/fa/posts/rust-capstone-service/): علت را فقط لاگ کن

**رفتن به عمق**

- [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/): بلوک‌های `unsafe` را کوچک نگه دار
- [پرفورمنس و benchmark با Criterion در Rust](/fa/posts/rust-performance-criterion/): ۰٫۳ ns یعنی کار حذف شده
- [الگوی Type-State و طراحی API در Rust](/fa/posts/rust-typestate-patterns/): حالت نامعتبر ناممکن شود
- [Rust و WebAssembly](/fa/posts/rust-wasm/): فقط عدد از مرز رد می‌شود

## درس‌هایی که مدام تکرار شدند

1. **کامپایلر معلم است.** [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) می‌گوید برچسب‌های خطا را بخوان، نه فقط تیتر را.
2. **Owned یا borrowed یک تصمیم طراحی است.** [Ownership در Rust](/fa/posts/rust-ownership/) می‌گوید `.clone()` اغلب یعنی طراحی یک borrow می‌خواهد.
3. **خطا مقدار است و در نوع می‌آید.** [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/) هشدار می‌دهد که `{}` علت‌ها را پنهان می‌کند.
4. **Async به runtime نیاز دارد.** [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/): داخل یک task هرگز کد blocking اجرا نکن.
5. **وقتی سیستم آرام است اندازه بگیر.** [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) عددی نمی‌دهد چون load بالای ۳ بود.

## Go و Rust کنار هم

در [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/)، یک تست شمارش کلمه روی لپ‌تاپی که بیکار نبود برای Go میانه‌ی ۲۴۹ میلی‌ثانیه و برای Rust ۳۵۷ میلی‌ثانیه داد؛ Rust حافظه‌ی کمتری مصرف کرد. خود پست آن را «یک microbenchmark» می‌داند که چیزی درباره‌ی سرویس‌های شبکه‌ای نمی‌گوید. [ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) از یک proto در هر دو جهت کار کرد. [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/) می‌گوید: «سرعت یا throughput را اندازه نگرفتم». من هنوز برای بیشتر سرویس‌ها Go را انتخاب می‌کنم.

## سال در عدد

از فهرست پست‌ها: ۷۲ پست تا زمان نوشتن این متن، هرکدام یک جفت فارسی و انگلیسی؛ با دو پست مرور می‌شود ۷۴. Rust ۳۰، Go Fundamentals ۱۴، Go Backend ۱۲، NATS JetStream ۹، Go + Rust ۴ و بدون سری ۳. سری Rust از 2026-10-29 تا 2027-03-18 ادامه داشت.

## چه چیزی را بعداً اضافه می‌کنم

این‌ها ایده‌اند، نه قول؛ از خلأهای خود پست‌ها آمده‌اند:

- یک `docker build` واقعی و `cargo audit` برای [Docker، CI و release سرویس Rust](/fa/posts/rust-docker-ci-release/).
- [Rust و WebAssembly](/fa/posts/rust-wasm/) در یک مرورگر واقعی؛ فقط Node استفاده شد.
- Miri و sanitizerها برای [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/).
- خروجی گرفتن span با `tracing-opentelemetry`؛ اجرا نشد.

## از اینجا به کجا برویم

تازه‌وارد Rust:

1. [Ownership در Rust](/fa/posts/rust-ownership/)
2. [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/)
3. [پروژه‌ی پایانی Rust: یک سرویس کامل](/fa/posts/rust-capstone-service/)

آمده از Go:

1. [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/)
2. [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/)

## خداحافظ ۱۴۰۵

فردا نوروز است و ۱۴۰۶ شروع می‌شود. ممنون که همراه بودید. سال نو مبارک.
