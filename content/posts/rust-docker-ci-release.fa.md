+++
date = '2027-03-12T10:00:00+03:30'
draft = false
title = 'Docker، CI و release سرویس Rust'
description = 'آماده‌سازی سرویس axum برای انتشار: release profile و اندازه‌ی باینری، باینری استاتیک musl، Dockerfile چندمرحله‌ای و GitHub Actions با actionlint.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "docker", "ci", "github-actions", "release", "backend"]
cover = { image = "/images/covers/rust-docker-ci-release.fa.png", alt = "Docker، CI و release سرویس Rust", hiddenInSingle = true }
+++

سرویس روی لپ‌تاپ من کار می‌کند. بیشتر داستان‌های استقرار (deploy) از همین جمله شروع می‌شوند. برای اینکه جای دیگری اجرا شود، کسی باید به سه سؤال جواب بدهد. چطور آن را بسته‌بندی کنیم که روی هر ماشین یکسان اجرا شود و بسته هم کوچک بماند؟ از کجا بدانیم هر تغییری پیش از رسیدن به آنجا هنوز build می‌شود و بررسی‌هایش را رد می‌کند؟ و لحظه‌ای که پلتفرم می‌خواهد نسخه‌ی قدیمی را متوقف کند و نسخه‌ی تازه را راه بیندازد چه اتفاقی می‌افتد؟

این مقاله برای یک سرویس کوچک `orders` به سبک [مقاله‌ی Axum](/fa/posts/rust-http-axum-api/) جواب می‌دهد که سه مسیر دارد: `/orders` و `/healthz` و `/readyz`. هم‌ارز Rust مقاله‌ی [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/) است. باینری release را کوچک می‌کنیم، آن را به‌صورت یک فایل ایستا می‌سازیم، در یک image از نوع {{< term "container" "container" >}} با Dockerfile {{< term "multi-stage-build" "چندمرحله‌ای" >}} می‌گذاریم و می‌گذاریم {{< term "ci" "CI" >}} (یکپارچه‌سازی پیوسته: سروری که روی هر push بررسی‌ها را اجرا می‌کند) آن را بررسی و منتشر کند. بعد از [مقاله‌ی type-state](/fa/posts/rust-typestate-patterns/) می‌آید: سرویس خوب طراحی شده و حالا باید از لپ‌تاپ من بیرون برود.

> **توضیح صادقانه.** Docker daemon روی این ماشین خاموش است و روشنش نکردم، پس `docker build` را هرگز اجرا نکردم. Dockerfile زیر با هدف درست بودن نوشته شده، ولی image ساخته نشده و اینجا نه اندازه‌ی image هست و نه خروجی لایه‌ها. چیزی که برای این نسخه‌ی مقاله واقعاً اجرا کردم، با `rustc 1.90.0` روی macOS arm64 و نسخه‌های قفل‌شده در `Cargo.lock` ‏demo: build‌های release و اندازه‌شان، cross build برای linux/arm64 با musl، endpoint‌ها، SIGTERM، `rustfmt`، `clippy` و `cargo test`. `actionlint` را این بار دوباره اجرا نکردم (به دانلودی از Go نیاز دارد که اینجا ممکن نبود)، پس نتیجه‌هایش پایین از اجرای اصلی همین مقاله است.

## کوچک کردن باینری release

build در حالت release از قبل برای سرعت بهینه شده، ولی کوچک نیست. اندازه مهم است چون فایل در هر deploy push و pull می‌شود و باینری کوچک در یک image کوچک هم جا می‌گیرد.

سرویس را برای `aarch64-unknown-linux-musl` ساختم (یک target ایستای Linux که بخش بعد توضیحش می‌دهم) و هر بار فقط یک تنظیم profile را عوض کردم. این تنظیم‌ها در بخش `[profile.release]` فایل `Cargo.toml` می‌روند؛ اینجا به‌جای آن از متغیرهای محیطی `CARGO_PROFILE_RELEASE_*` استفاده کردم، هر بار با پوشه‌ی target تمیز و `--locked`. هر عدد یک build است. برای این نسخه‌ی مقاله کل جدول را دوباره اجرا کردم و همه‌ی عددها دقیقاً همان شدند، پس این اندازه‌ها پایدارند. زمان build را نمی‌گویم، چون ماشین زیر بار بود.

| profile | بایت |
|---|---|
| release پیش‌فرض | 2091720 |
| `lto = "thin"` | 2012584 |
| `lto = "fat"` | 1504536 |
| `codegen-units = 1` | 1647288 |
| `strip = true` | 1331864 |
| `opt-level = "z"` | 2431520 |
| `panic = "abort"` | 1522992 |
| fat + cgu 1 + strip + abort | 895872 |
| همین‌ها + `opt-level = "z"` | 787192 |

معنی تنظیم‌ها:

- {{< term "lto" "lto" >}} (بهینه‌سازی در زمان link) به کامپایلر اجازه می‌دهد در پایان build همه‌ی crateها را با هم بهینه کند. `thin` نسخه‌ی ارزان‌تر است و `fat` نسخه‌ی کامل.
- `codegen-units = 1` کامپایلر را از تکه‌تکه کردن crate برای کار موازی بازمی‌دارد. یک تکه دیرتر build می‌شود، ولی بهتر بهینه می‌شود.
- `strip = true` نمادها و اطلاعات debug را از فایل بیرون می‌کشد. هزینه‌اش این است که stack trace یک باینری از کار افتاده چیز کمتری نشان می‌دهد.
- `opt-level = "z"` از کامپایلر می‌خواهد به‌جای سرعت برای اندازه بهینه کند.
- `panic = "abort"` سازوکار باز کردن stack هنگام panic را برمی‌دارد. آن‌وقت panic فوراً پروسه را می‌کشد.

هر تنظیم به‌تنهایی کمی کمک می‌کند (`strip` و `lto = "fat"` بیشتر از بقیه)، ولی با هم ۲٫۰۹ مگابایت را به ۰٫۹۰ مگابایت می‌رسانند. یک نتیجه مرا غافلگیر کرد: `opt-level = "z"` به‌تنهایی باینری را بزرگ‌تر کرد، ۲۴۳۱۵۲۰ بایت در برابر ۲۰۹۱۷۲۰. روی چهار تنظیم دیگر کوچک‌ترش کرد (۷۸۷۱۹۲). دلیلش را بررسی نکردم. درباره‌ی `panic = "abort"`: این فقط تغییر اندازه نیست، تغییر رفتار است. زیر orchestrator‌ای که پروسه‌ی از کار افتاده را دوباره راه می‌اندازد قبولش دارم، ولی اگر کدی به `catch_unwind` وابسته است نباید از آن استفاده کنید. من fat + cgu 1 + strip + abort را انتخاب کردم و `opt-level` را پیش‌فرض گذاشتم، چون سرعت برایم از ۱۰۰ کیلوبایت آخر مهم‌تر است:

```toml
[profile.release]
lto = "fat"
codegen-units = 1
strip = true
panic = "abort"
```

## باینری ایستا از macOS

چرا اصلاً `musl`؟ باینری معمولی Linux که با Rust ساخته شود هنگام اجرا از کتابخانه‌ی C سیستم (glibc) استفاده می‌کند، پس فقط جایی کار می‌کند که آن کتابخانه هست. اگر برای target از نوع {{< term "musl" "musl" >}} بسازید، کتابخانه‌ی C داخل باینری link می‌شود. نتیجه یک فایل ایستاست که از سیستم چیزی نمی‌خواهد، و همین اجازه می‌دهد image نهایی تقریباً خالی باشد.

مشکل اینجاست که من روی Mac هستم و container روی Linux اجرا می‌شود. پس باید cross-compile کنم. بعد از `rustup target add aarch64-unknown-linux-musl`، دستور ساده‌ی `cargo build --release --target aarch64-unknown-linux-musl` در مرحله‌ی link خطا داد (خروجی کوتاه شده):

```
WARN rustc_codegen_ssa::back::link Linker does not support -no-pie command line option. Retrying without.
error: linking with `cc` failed: exit status: 1
  = note: ld: unknown options: --as-needed -Bstatic -Bdynamic --eh-frame-hdr -z --gc-sections -z -z --strip-all
          clang: error: linker command failed with exit code 1
```

دلیل: `cc` در macOS همان linker اپل است و فلگ‌های فایل‌های Linux (ELF) را نمی‌شناسد. معمولاً به یک cross linker مثل `zig` (با `cargo-zigbuild`) یا یک musl gcc نیاز دارید؛ هیچ‌کدام اینجا نصب نیست. ولی rustup داخل toolchain یک linker به نام `rust-lld` دارد و همان کافی بود. با یک متغیر محیطی Cargo را به آن اشاره دادم و دوباره build کردم:

```
$ CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=<sysroot>/lib/rustlib/aarch64-apple-darwin/bin/rust-lld \
    cargo build --release --locked --target aarch64-unknown-linux-musl
$ file .../release/orders-svc
ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, stripped
$ stat -f %z .../release/orders-svc
895872
```

`file` همان را می‌گوید که می‌خواستیم: یک فایل اجرایی ELF لینوکسی برای ARM64، به‌صورت ایستا link شده و strip شده (profile نهایی حالا در `Cargo.toml` است). اندازه‌ی ۸۹۵۸۷۲ بایت با ردیف profile نهایی در جدول یکی است. اینجا نمی‌توانم ELF لینوکسی را اجرا کنم، پس این فقط ثابت می‌کند build و link کار می‌کنند، نه اینکه برنامه اجرا می‌شود. اجراهای پایین با build معمولی برای ماشین خودم است.

## سلامت، آمادگی و SIGTERM

وقتی پلتفرم سرویس شما را اجرا می‌کند، دو سؤال جدا از آن می‌پرسد و قاطی کردنشان یک اشتباه کلاسیک است:

- **زنده بودن** (liveness، `/healthz`): «پروسه زنده است؟» اگر شکست بخورد پلتفرم پروسه را دوباره راه می‌اندازد.
- **آمادگی** (readiness، `/readyz`): «الان ترافیک برایت بفرستم؟» اگر شکست بخورد پلتفرم پروسه را نگه می‌دارد ولی دیگر درخواست برایش نمی‌فرستد.

چیز سوم خود توقف است. پلتفرم container را با فرستادن {{< term "sigterm" "SIGTERM" >}} به پروسه متوقف می‌کند و بعد مدتی صبر می‌کند تا آن را بکشد. می‌خواهیم سرویس درخواست‌هایی را که در دست دارد تمام کند و تمیز خارج شود: این همان {{< term "graceful-shutdown" "خاموش شدن تمیز" >}} است. آمادگی یک `AtomicBool` است که بعد از `bind` روشن و با رسیدن سیگنال خاموش می‌شود؛ بعد `with_graceful_shutdown` اجازه می‌دهد درخواست‌های در جریان تمام شوند. اول خاموش کردن آمادگی یعنی پلتفرم دیگر درخواست تازه نمی‌فرستد در حالی که قدیمی‌ها تمام می‌شوند.

یک چیز دیگر هم هست. image از نوع distroless (پایین بیشتر می‌گویم) شل و `curl` ندارد، پس یک دستور معمولی {{< term "health-check" "health check" >}} چیزی برای اجرا ندارد. برای همین باینری فلگ `--healthcheck` خودش را دارد که با یک `TcpStream` ساده `/healthz` همان سرویس را صدا می‌زند و با کد ۰ یا ۱ خارج می‌شود. بخشی که خاموش شدن را اداره می‌کند:

```rust
axum::serve(listener, app)
    .with_graceful_shutdown(async move {
        let mut term = signal(SignalKind::terminate()).unwrap();
        tokio::select! { _ = term.recv() => {} _ = tokio::signal::ctrl_c() => {} }
        ready.store(false, Ordering::SeqCst); // fail readiness first
        println!("shutting down");
    })
    .await
    .unwrap();
```

`select!` منتظر SIGTERM یا Ctrl-C می‌ماند. هر کدام برسد، کد آمادگی را خاموش می‌کند، `shutting down` چاپ می‌کند و future تمام می‌شود، که به `axum::serve` می‌گوید پذیرش اتصال تازه را متوقف کند و منتظر اتصال‌های فعلی بماند.

این یک اجرای واقعی build مخصوص release با profile نهایی است. آن را روی یک پورت آزاد تصادفی راه انداختم (demo آدرس را از متغیر `ADDR` می‌خواند؛ شماره‌ی پورت `<port>` پایین هر بار فرق می‌کند)، endpoint‌ها را صدا زدم، health check را اجرا کردم و بعد SIGTERM فرستادم:

```
$ curl -si localhost:<port>/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:<port>/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ curl -s localhost:<port>/orders
[{"id":1,"item":"book"},{"id":2,"item":"pen"}]
$ orders-svc --healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo exit=$?
exit=0
```

`sed` فقط خط اول (وضعیت) و خط آخر (بدنه) را نگه می‌دارد. بررسی‌ها `200` با `ok` و `ready` برمی‌گردانند، سفارش‌ها به‌صورت JSON می‌آیند، `--healthcheck` کد ۰ می‌دهد و بعد از `SIGTERM` پروسه با وضعیت ۰ خارج می‌شود. لاگ خود سرویس این بود:

```
listening on 127.0.0.1:<port>
shutting down
stopped
```

`stopped` بعد از تمام شدن سرور چاپ می‌شود، پس فقط وقتی می‌آید که خاموش شدن تمیز بوده باشد. وقتی سروری بالا نیست، `--healthcheck` پیام `healthcheck: Connection refused (os error 61)` چاپ می‌کند و با کد ۱ خارج می‌شود.

## Dockerfile

حالا image. Cargo مرحله‌ای برای «فقط دانلود و build وابستگی‌ها» ندارد. Docker هر مرحله (لایه) را cache می‌کند و اگر ورودی‌هایش عوض نشده باشد دوباره استفاده‌اش می‌کند، پس می‌خواهیم build وابستگی‌ها لایه‌ی جدا خودش باشد. ترفندش یک `main.rs` ساختگی است: یک بار فقط با manifest‌ها و یک برنامه‌ی خالی build می‌کنیم، بعد کد واقعی را کپی می‌کنیم. ابزار `cargo-chef` همین ایده را خودکار می‌کند.

```dockerfile
FROM rust:1.90 AS build
ARG RUST_TARGET=aarch64-unknown-linux-musl
RUN rustup target add ${RUST_TARGET}
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs \
 && cargo build --release --locked --target ${RUST_TARGET} && rm -rf src
COPY src ./src
RUN touch src/main.rs \
 && cargo build --release --locked --target ${RUST_TARGET} \
 && cp target/${RUST_TARGET}/release/orders-svc /orders-svc

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /orders-svc /orders-svc
USER nonroot:nonroot
ENV ADDR=0.0.0.0:8080
ENTRYPOINT ["/orders-svc"]
```

آن را در دو نیمه بخوانید. مرحله‌ی اول، با نام `build`، از image رسمی `rust:1.90` شروع می‌شود که بزرگ است چون کل toolchain را دارد. target مربوط به musl را اضافه می‌کند، فقط `Cargo.toml` و `Cargo.lock` را کپی می‌کند، یک برنامه‌ی ساختگی build می‌کند (این کار همه‌ی وابستگی‌ها را دانلود و در یک لایه‌ی cache‌شده کامپایل می‌کند)، کد ساختگی را پاک می‌کند و تازه بعد `src` واقعی را کپی می‌کند. `touch` تضمین می‌کند Cargo کد واقعی را جدیدتر از build ساختگی ببیند. بعد دوباره build می‌کند که حالا فقط کد خودمان را کامپایل می‌کند.

مرحله‌ی دوم از `distroless/static` شروع می‌شود، imageای که تقریباً هیچ چیز در آن نیست: نه شل، نه package manager. فقط باینری تمام‌شده را از مرحله‌ی اول کپی می‌کند، به کاربر غیر root می‌رود و برنامه را راه می‌اندازد. کامپایلر و کد منبع هیچ‌وقت به image نهایی نمی‌رسند. باینری ایستای musl با `distroless/static` جور است؛ طبق توضیح پروژه‌ی distroless، build‌ای که از glibc استفاده کند به نوع `cc` نیاز دارد. `.dockerignore` پوشه‌ی `target` و `.git` و لاگ‌ها را از context بیرون نگه می‌دارد. این فایل را build نکرده‌ام و link با musl داخل imageی `rust` هم آزمایش نشده است.

## workflowهای CI و release

CI اینجا دو workflow در GitHub Actions است. `ci.yml` روی push به `main` و روی pull request اجرا می‌شود و سه بررسی دارد:

- `cargo fmt --check` اگر کد قالب‌بندی نشده باشد شکست می‌خورد.
- `cargo clippy --locked --all-targets -- -D warnings` لینتر را اجرا می‌کند و `-D warnings` هر هشدار را به خطا تبدیل می‌کند.
- `cargo test --locked` تست‌ها را اجرا می‌کند.

هر سه را محلی با `rustc 1.90.0` اجرا کردم و پاس شدند. یک نکته‌ی صادقانه: این demo کوچک تست ندارد، پس `cargo test` ۰ تست اجرا کرد و «پاس شدنش» بدیهی است.

`release.yml` وقتی تگی که با `v` شروع می‌شود push کنید اجرا می‌شود. یک matrix سه‌تایی می‌سازد (Linux با musl روی x86-64 و arm64، و macOS روی arm64) و هر باینری را با `upload-artifact` آپلود می‌کند، و یک job جدا به نام `image` وارد GHCR (رجیستری container گیت‌هاب) می‌شود و image را push می‌کند. فقط همان job مجوز `packages: write` دارد؛ بقیه فقط‌خواندنی‌اند. نسخه‌ی actionها روی تگ‌هایی pin شده که در اجرای اصلی از API گیت‌هاب پرسیدم: `actions/checkout@v7.0.1`، `Swatinem/rust-cache@v2.9.3`، `docker/build-push-action@v7.4.0` و بقیه. برای این نسخه دوباره بررسی‌شان نکرده‌ام. `actionlint` (لینتر فایل‌های workflow) را در اجرای اصلی روی هر دو فایل اجرا کردم و هر دو پاس شدند:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ go run ... .github/workflows/release.yml
exit=0 (both)
```

عمداً matrix را هم خراب کردم (`matrix.targt`) و actionlint گفت `property "targt" is not defined in object type {os: string; target: string}`. یادتان باشد چه چیزی را می‌سنجد: سینتکس و type‌ها در workflow، نه اینکه push به رجیستری کار می‌کند.

## بهداشت زنجیره‌ی تأمین

هر چیزی که سرویس شما از آن ساخته می‌شود، یعنی وابستگی‌ها و ابزارهای build، بخشی از {{< term "software-supply-chain" "زنجیره‌ی تأمین نرم‌افزار" >}} آن است. سه عادت کوچک کمک می‌کند:

- `Cargo.lock` را برای باینری‌ها commit کنید و همه‌جا `--locked` بگذارید، تا CI دقیقاً همان چیزی را بسازد که review شده.
- `cargo audit` یا `cargo deny` را در CI اجرا کنید. اینجا اجرایشان نکردم (نصب نیستند)؛ فقط اشاره می‌کنم.
- toolchain را pin کنید (`1.90.0`) تا انتشار یک کامپایلر جدید build شما را غافلگیرانه عوض نکند.

## پیش از اعتماد به این تنظیمات

- **Dockerfile آزمایش نشده است.** پیش از تکیه بر آن خودتان `docker build` را اجرا کنید. به‌ویژه link با musl داخل imageی `rust` اینجا امتحان نشد.
- **`panic = "abort"` کار panic را عوض می‌کند.** ببینید چیزی در کدتان به `catch_unwind` وابسته نباشد.
- **جدول اندازه‌ها برای همین سرویس است.** برنامه‌های دیگر عددهای دیگری می‌دهند؛ پیش از کپی کردن profile، مال خودتان را اندازه بگیرید.
- **بررسی workflow یک لینت است.** ثابت نمی‌کند job انتشار روی گیت‌هاب موفق می‌شود.

## قدم بعدی

«Rust و WebAssembly»: همین زبان برای مقصدی کاملاً متفاوت.
