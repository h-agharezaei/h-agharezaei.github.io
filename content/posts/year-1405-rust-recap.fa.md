+++
date = '2027-03-20T10:00:00+03:30'
draft = false
title = 'مرور سری Rust و جمع‌بندی سال ۱۴۰۵'
description = 'نقشه‌ی هر ۳۰ پست سری Rust، درس‌هایی که مدام تکرار شدند، مقایسه‌ی صادقانه‌ی Go و Rust، شمارش واقعی پست‌ها و کارهای نیمه‌تمام در پایان سال ۱۴۰۵.'
contentType = 'analysis'
categories = ["Meta"]
tags = ["rust", "go", "recap", "1405"]
cover = { image = "/images/covers/year-1405-rust-recap.fa.png", alt = "مرور سری Rust و جمع‌بندی سال ۱۴۰۵", hiddenInSingle = true }
+++

امروز آخرین روز سال ۱۴۰۵ است. بعد از [مرور سری Go در سال ۱۴۰۵](/fa/posts/year-1405-go-recap/)، این یکی برای Rust است. فرض کنید به Rust کنجکاوید اما هیچ‌کدام از مقاله‌های من را نخوانده‌اید: این صفحه می‌گوید سری Rust چه چیزهایی را پوشش می‌دهد، به چه ترتیبی، هر مقاله درباره‌ی کدام ایده است و اگر جای شما بودم اول چه می‌خواندم.

این سری ۳۰ مقاله دارد. اینجا به همان ترتیبی آمده‌اند که منتشر کردم، که ترتیب منطقی خواندن هم هست: هر مقاله روی قبلی‌ها سوار است. نکته‌ی زیر هر لینک از خود همان مقاله آمده است.

## سری Rust به ترتیب خواندن

### قدم‌های اول

- [شروع کار با Rust: نصب، Cargo و اولین برنامه](/fa/posts/rust-getting-started/): تقریباً هیچ‌وقت کامپایلر را مستقیم صدا نمی‌زنید. `rustup` ابزارها را نصب می‌کند و Cargo کدتان را می‌سازد و اجرا می‌کند، چیزی شبیه فرمان `go`. هنگام ویرایش، `cargo check` سریع‌ترین بازخورد را می‌دهد.
- [نوع‌ها، متغیرها و کنترل جریان در Rust](/fa/posts/rust-types-control-flow/): واژگان پایه، و چند پیش‌فرض که با Go فرق دارند. اگر به یک `u8` که ۲۵۵ دارد یکی اضافه کنید، در build دیباگ برنامه panic می‌کند و در build ریلیز بی‌صدا به ۰ برمی‌گردد.

### Ownership و نوع‌های اصلی

این بخشی از Rust است که برای بیشتر آدم‌ها تازه است. هر مقدار یک مالک دارد و کامپایلر قاعده‌ها را پیش از اجرای برنامه بررسی می‌کند.

- [Ownership در Rust](/fa/posts/rust-ownership/): `let b = a;` یک `String` را کپی نمی‌کند، جابه‌جا می‌کند، برای همین استفاده از `a` بعد از آن کامپایل نمی‌شود. Rust به این شکل بدون garbage collector حافظه را مدیریت می‌کند.
- [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/): به‌جای اینکه مقدار را بدهید، با یک reference قرضش می‌دهید. خطاهای کامپایلری که اینجا می‌بینید راه اصلی یادگرفتن قاعده‌هاست.
- [Struct، Enum و Pattern Matching در Rust](/fa/posts/rust-structs-enums-pattern-matching/): هر variant یک enum می‌تواند داده داشته باشد و `match` باید همه‌ی حالت‌ها را پوشش دهد، پس اگر بعداً یک variant اضافه کنید، کامپایلر همه‌ی جاهایی را که باید به‌روز شوند نشانتان می‌دهد.
- [Collectionها و String در Rust](/fa/posts/rust-collections-strings/): `Vec`، `HashMap` و دو نوع رشته، جایی که ownership به کار روزمره می‌رسد. تابعی که فقط متن را می‌خواند باید `&str` بگیرد.
- [مدیریت خطا با Result و Option در Rust](/fa/posts/rust-error-handling-result/): امکان شکست جزو نوع مقدار بازگشتی است، پس نمی‌شود فراموشش کرد.

### سازمان‌دادن کد و انتزاع‌ها

- [Module، Crate و Cargo در Rust](/fa/posts/rust-modules-crates-cargo/): همه‌چیز به‌طور پیش‌فرض خصوصی است و فایلی که `mod` برایش نوشته نشده باشد، ساده نادیده گرفته می‌شود.
- [Generics و Trait در Rust](/fa/posts/rust-generics-traits/): یک تابع برای چند نوع، و کامپایلر اول می‌پرسد آن نوع چه کاری از دستش برمی‌آید که با trait bound جواب می‌دهید.
- [Lifetime در Rust](/fa/posts/rust-lifetimes/): annotation مربوط به lifetime رابطه‌ی reference‌ها با هم را توصیف می‌کند؛ هیچ‌وقت عمر یک مقدار را بیشتر نمی‌کند.
- [Closure و Iterator در Rust](/fa/posts/rust-closures-iterators/): closure می‌تواند از متغیرهای کد اطرافش استفاده کند و iteratorها lazy هستند: تا وقتی کسی عنصر نخواهد، چیزی اجرا نمی‌شود.
- [Smart Pointerها: Box، Rc و RefCell در Rust](/fa/posts/rust-smart-pointers/): سه ابزار استاندارد برای جاهایی که قاعده‌ی یک‌مالکی جواب نمی‌دهد، مثل مالکیت مشترک.
- [تست و مستندسازی در Rust](/fa/posts/rust-testing-docs/): اجراکننده‌ی تست جزو Cargo است و مثال‌هایی که در مستندات می‌نویسید هم به‌صورت تست اجرا می‌شوند.

### Concurrency و async

- [Concurrency با Thread در Rust](/fa/posts/rust-concurrency-threads/): کامپایلر کدی را که data race دارد قبول نمی‌کند. جلوی deadlock را نمی‌گیرد.
- [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/): تابع async تا await نشود کاری نمی‌کند، تسک‌های زیاد چند thread را شریکی استفاده می‌کنند و بلاک‌کردن thread درون یک تسک همان اشتباه بزرگ است.

### ساخت سرویس

- [Serde و JSON در Rust](/fa/posts/rust-serde-json/): JSON همان دم در بررسی می‌شود: یا یک مقدار درست‌وحسابی می‌گیرید یا یک خطای روشن.
- [ساخت API با Axum در Rust](/fa/posts/rust-http-axum-api/): همان API سفارش‌ها در سری Go، با status codeهای دقیق. extractorی که بدنه را می‌خواند باید آخر بیاید.
- [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/): queryهای ساده هنگام اجرا بررسی می‌شوند و ماکروهای `query!` آن‌ها را هنگام کامپایل بررسی می‌کنند.
- [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/): یک نوع خطا برای کدی است که باید تصمیم بگیرد و یک نوع برای آدمی که باید بفهمد چه شد، و علت اصلی نباید گم شود.
- [کلاینت async NATS JetStream در Rust](/fa/posts/rust-nats-async-client/): یک publisher که می‌داند پیامش ذخیره شده و یک worker که پیام ناموفق را فقط چند بار محدود دوباره امتحان می‌کند.

### رفتن به عمق

- [Trait Object و dyn در Rust](/fa/posts/rust-trait-objects-dyn/): وقتی یک فهرست با نوع‌های مختلف می‌خواهید، `Box<dyn Trait>` متد را هنگام اجرا پیدا می‌کند.
- [ماکروها در Rust](/fa/posts/rust-macros/): کدی که هنگام کامپایل کد می‌نویسد. اگر یک تابع یا generics کار را راه می‌اندازد، سراغ تابع بروید.
- [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/): `unsafe` یعنی کامپایلر چیزی را نمی‌تواند ثابت کند و شما قول می‌دهید، پس آن بلوک‌ها را کوچک نگه دارید و پشت یک تابع safe بگذارید. همین مقاله یک کتابخانه می‌سازد که C بتواند صدایش بزند.
- [پرفورمنس و benchmark با Criterion در Rust](/fa/posts/rust-performance-criterion/): کار را تکرار کنید، آمار بگیرید و مطمئن شوید کامپایلر کاری را که می‌خواستید اندازه بگیرید حذف نکرده است.
- [Future، Pin و درون async در Rust](/fa/posts/rust-pin-future-internals/): یک future و یک executor کوچک را با دست می‌سازیم تا ببینیم `.await` واقعاً چه می‌کند و `Pin` چرا هست.

### راه‌اندازی یک سرویس

- [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/): خط‌های لاگ ساده نمی‌گویند به کدام درخواست مربوط‌اند؛ eventهای ساختاریافته و spanها می‌گویند. اگر یک تسک را با `tokio::spawn` شروع کنید span گم می‌شود، مگر اینکه خودتان آن را بدهید.
- [الگوی Type-State و طراحی API در Rust](/fa/posts/rust-typestate-patterns/): واقعیت‌هایی مثل «این سفارش هنوز پیش‌نویس است» را در نوع‌ها بنویسید تا فراخوانی اشتباه کامپایل نشود.
- [Docker، CI و release سرویس Rust](/fa/posts/rust-docker-ci-release/): باینری ایستای کوچک‌تر، image چندمرحله‌ای و workflow برای CI. هیچ‌وقت `docker build` را اجرا نکردم و مقاله هم همین را می‌گوید.
- [Rust و WebAssembly](/fa/posts/rust-wasm/): همان کد Rust را داخل یک میزبان مثل Node اجرا کنید. فقط عددها از مرز رد می‌شوند، پس یک رشته به‌صورت pointer و طول فرستاده می‌شود.
- [پروژه‌ی پایانی Rust: یک سرویس کامل](/fa/posts/rust-capstone-service/): تکه‌های سری در یک سرویس `orders` به هم وصل می‌شوند تا باگ‌هایی را ببینیم که در درزها پنهان‌اند. یک نمونه: یک کاراکتر NUL در نام از اعتبارسنجی گذشت و بعد Postgres ردش کرد، پس کلاینت فقط یک 500 کلی دید و لاگ علت واقعی را داشت.

## درس‌هایی که تکرار شدند

1. **کامپایلر معلم است.** [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) می‌گوید به برچسب‌های خطا نگاه کنید، نه فقط عنوانش: «first borrow occurs here» و «later used here» نشان می‌دهند کدام دو خط با هم تعارض دارند.
2. **owned یا borrowed یک تصمیم طراحی است.** [Ownership در Rust](/fa/posts/rust-ownership/) می‌گوید هر بار کامپایلر اعتراض کرد سراغ `.clone()` نروید؛ کپی را پنهان می‌کند و معمولاً نشانه‌ی این است که طراحی باید قرض بگیرد، نه مالک شود.
3. **خطاها مقدارهایی در نوع‌اند و علتشان مهم است.** [خطا در اپلیکیشن واقعی: thiserror و anyhow](/fa/posts/rust-thiserror-anyhow/) هشدار می‌دهد `{}` فقط بیرونی‌ترین پیام را نشان می‌دهد، پس با `{:#}` یا `{:?}` لاگ کنید وگرنه دلیل را از دست می‌دهید.
4. **async به runtime نیاز دارد و بلاک‌کردنش ضرر دارد.** [async/await و Tokio در Rust](/fa/posts/rust-async-tokio/) بلاک‌کردن thread درون یک تسک را یک اشتباه بزرگ می‌داند.
5. **دقیق اندازه بگیرید، یا بگویید نگرفته‌اید.** [پرفورمنس و benchmark با Criterion در Rust](/fa/posts/rust-performance-criterion/) توضیح می‌دهد نتیجه‌ی حدود ۰٫۳ نانوثانیه یعنی کار حذف شده است. [صدا زدن Rust از Go با FFI](/fa/posts/go-calls-rust-ffi/) هیچ عددی نمی‌دهد، چون ماشین مشغول بود و load average حدود ۴ بود.

## Go و Rust کنار هم

در [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/) کلمه‌های یک متن تولیدشده‌ی ده‌میلیون‌کلمه‌ای را شمردم. در اجرای اولیه‌ام، روی لپ‌تاپی که بیکار نبود، میانه‌ی زمان شمارش برای Go برابر ۲۴۹ میلی‌ثانیه و برای Rust برابر ۳۵۷ میلی‌ثانیه بود. Rust حافظه‌ی کمتری مصرف کرد (۸۱ مگابایت در برابر ۱۶۷ تا ۲۰۷) و باینری خیلی کوچک‌تری ساخت (۴۴۵٬۶۰۰ بایت در برابر ۲٬۵۴۴٬۶۱۰). بعد hasher پیش‌فرض Rust را با یک hasher ساده عوض کردم و میانه شد ۲۱۴ میلی‌ثانیه، سریع‌تر از هر دو. نتیجه‌ی خود مقاله این است که یک microbenchmark درباره‌ی بار کاری شما مدرک نیست و این آزمون چیزی درباره‌ی سرویس‌های شبکه‌ای نمی‌گوید.

[ارتباط Go و Rust با gRPC](/fa/posts/go-rust-grpc-interop/) هر دو زبان را از یک فایل `.proto` کار می‌دهد. [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/) می‌گوید دموی آن چیزی را درباره‌ی سرعت اندازه نمی‌گیرد. من هنوز برای بیشتر سرویس‌ها Go را انتخاب می‌کنم و Rust را یاد می‌گیرم تا بدانم کِی ابزار بهتری است.

## سال در عدد

با شمارش از روی تاریخ مقاله‌ها، تا امروز ۱۸۰ مقاله منتشر شده است، با احتساب دو مقاله‌ی مرور، و هر کدام یک نسخه‌ی فارسی و یک نسخه‌ی انگلیسی دارد. سری Rust ۳۰ مقاله دارد، از ۲۹ اکتبر ۲۰۲۶ تا ۱۸ مارس ۲۰۲۷. مقاله‌های مرتبط با Go هم روی هم ۳۹ تا هستند: Go Fundamentals ۱۴، Go Backend ۱۲، NATS JetStream ۹ و Go + Rust ۴.

## چه چیزهایی به گفته‌ی خود مقاله‌ها هنوز کم است

این‌ها کمبودهایی‌اند که خود مقاله‌ها به آن‌ها اعتراف کرده‌اند، نه قول.

- `docker build` واقعی و `cargo audit` برای [Docker، CI و release سرویس Rust](/fa/posts/rust-docker-ci-release/)؛ هیچ‌کدام اجرا نشد.
- [Rust و WebAssembly](/fa/posts/rust-wasm/) در یک مرورگر: مرورگری در دسترس نبود و فقط Node به کار رفت.
- Miri و sanitizerها برای [Unsafe و FFI در Rust](/fa/posts/rust-unsafe-ffi/): هیچ‌کدام نصب نبود، پس اجرا نشدند.
- خروجی‌گرفتن spanها با `tracing-opentelemetry` در [Observability در Rust با tracing](/fa/posts/rust-tracing-observability/): مقاله فقط اسمش را می‌آورد و اجرایش نکرده است.

## از کجا شروع کنم؟

اگر در Rust تازه‌کارید:

1. [Ownership در Rust](/fa/posts/rust-ownership/)
2. [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/)
3. [پروژه‌ی پایانی Rust: یک سرویس کامل](/fa/posts/rust-capstone-service/)

اگر از Go می‌آیید:

1. [Go یا Rust؟ هرکدام برای چه کاری](/fa/posts/go-vs-rust-when-to-use/)
2. [پروژه‌ی پایانی: Pipeline رویدادمحور با Go، Rust و NATS](/fa/posts/go-rust-event-pipeline-capstone/)

اگر هنوز Rust را نصب نکرده‌اید، از [شروع کار با Rust: نصب، Cargo و اولین برنامه](/fa/posts/rust-getting-started/) شروع کنید.

## خداحافظ ۱۴۰۵

فردا نوروز است و ۱۴۰۶ شروع می‌شود. ممنون که تا اینجا همراه بودید. سال نو مبارک.
