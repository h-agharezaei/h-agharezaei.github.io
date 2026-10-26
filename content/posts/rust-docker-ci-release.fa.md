+++
date = '2027-03-12T10:00:00+03:30'
draft = false
title = 'Docker، CI و release سرویس Rust'
description = 'آماده‌سازی سرویس axum برای انتشار: release profile و اندازه‌ی باینری، باینری استاتیک musl، Dockerfile چندمرحله‌ای و GitHub Actions با actionlint.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "docker", "ci", "github-actions", "release", "backend"]
cover = { image = "/images/covers/rust-docker-ci-release.fa.png", alt = "Docker، CI و release سرویس Rust", hiddenInSingle = true }
+++

موضوع مقاله‌ی قبل طراحی API بود، در [الگوهای typestate](/fa/posts/rust-typestate-patterns/). حالا سرویس باید از لپ‌تاپ من بیرون برود. این نسخه‌ی Rust از [Docker، CI و دیپلوی سرویس Go](/fa/posts/go-docker-ci-deploy/) است و یک سرویس کوچک `orders` به سبک [مقاله‌ی Axum](/fa/posts/rust-http-axum-api/) دارد: `/orders`، `/healthz` و `/readyz`.

> **توضیح صادقانه.** Docker daemon روی این ماشین خاموش است و روشنش نکردم، پس `docker build` را هرگز اجرا نکردم. Dockerfile زیر با هدف درست بودن نوشته شده، ولی image ساخته نشده و اینجا نه اندازه‌ی image هست و نه خروجی لایه‌ها. چیزی که واقعاً اجرا کردم، روی Rust 1.90.0 (macOS arm64): build‌های release و اندازه‌شان، cross build برای linux/arm64 با musl، endpoint‌ها، SIGTERM، clippy، rustfmt و `actionlint`.

## کوچک کردن باینری release

سرویس را برای `aarch64-unknown-linux-musl` ساختم و هر بار فقط یک تنظیم profile را عوض کردم (با `CARGO_PROFILE_RELEASE_*`، هر بار با پوشه‌ی target تمیز و `--locked`). اندازه‌ها بایت هستند، از هر کدام یک build. زمان build را نمی‌گویم، چون ماشین زیر بار بود.

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
| همان + `opt-level = "z"` | 787192 |

هر تنظیم به‌تنهایی کمی کم می‌کند (`strip` و `lto = "fat"` بیشتر از بقیه)، ولی با هم ۲٫۰۹ مگابایت را به ۰٫۹۰ مگابایت می‌رسانند. `opt-level = "z"` به‌تنهایی باینری را بزرگ‌تر کرد؛ دلیلش را بررسی نکردم. `panic = "abort"` unwinding را حذف می‌کند؛ panic پروسه را می‌کشد. با orchestrator که ری‌استارتش می‌کند قابل قبول است، ولی تغییر رفتار است. من fat + cgu 1 + strip + abort را انتخاب کردم و `opt-level` را پیش‌فرض گذاشتم، چون سرعت برایم مهم‌تر از ۱۰۰ کیلوبایت آخر است:

```toml
[profile.release]
lto = "fat"
codegen-units = 1
strip = true
panic = "abort"
```

## باینری استاتیک از روی macOS

`cargo build --target aarch64-unknown-linux-musl` بعد از `rustup target add` در مرحله‌ی link شکست خورد:

```
WARN rustc_codegen_ssa::back::link Linker does not support -no-pie command line option. Retrying without.
error: linking with `cc` failed: exit status: 1
  = note: ld: unknown options: --as-needed -Bstatic -Bdynamic --eh-frame-hdr -z --gc-sections ...
          clang: error: linker command failed with exit code 1
```

دلیل: `cc` در macOS همان linker اپل است و فلگ‌های ELF را نمی‌شناسد. معمولاً به یک cross linker مثل `zig` (با `cargo-zigbuild`) یا یک musl gcc نیاز دارید؛ هیچ‌کدام اینجا نصب نیست. ولی rustup داخل toolchain یک `rust-lld` دارد و همان کافی بود:

```
$ CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=<sysroot>/lib/rustlib/aarch64-apple-darwin/bin/rust-lld \
    cargo build --release --locked --target aarch64-unknown-linux-musl
$ file .../release/orders-svc
ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, not stripped
```

اینجا نمی‌توانم ELF لینوکسی را اجرا کنم، پس این فقط build و link را ثابت می‌کند نه اجرا را؛ اجراهای پایین با build مخصوص میزبان است.

## سلامت، آمادگی و SIGTERM

آمادگی یک `AtomicBool` است که بعد از `bind` روشن و با رسیدن سیگنال خاموش می‌شود؛ بعد `with_graceful_shutdown` اجازه می‌دهد درخواست‌های در جریان تمام شوند. image از نوع distroless `curl` ندارد، پس باینری یک فلگ `--healthcheck` هم دارد که با یک `TcpStream` ساده `/healthz` خودش را صدا می‌زند:

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

اجرای واقعی build مخصوص release با profile نهایی:

```
$ curl -si localhost:18432/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:18432/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ curl -s localhost:18432/orders
[{"id":1,"item":"book"},{"id":2,"item":"pen"}]
$ orders-svc --healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo exit=$?
exit=0
```

لاگ `shutting down` و بعد `stopped` را نشان داد. وقتی سروری نیست، `--healthcheck` پیام `Connection refused (os error 61)` چاپ می‌کند و با کد ۱ خارج می‌شود.

## Dockerfile

Cargo مرحله‌ای برای «فقط دانلود وابستگی‌ها» ندارد، پس از ترفند `main.rs` ساختگی استفاده می‌کنم (ابزار `cargo-chef` همین ایده را خودکار می‌کند): اول فقط با manifest‌ها build می‌کنیم، بعد کد واقعی را کپی می‌کنیم.

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

`touch` تضمین می‌کند Cargo کد واقعی را جدیدتر ببیند. باینری استاتیک musl با `distroless/static` جور است؛ build با glibc به `distroless/cc` نیاز دارد. `.dockerignore` پوشه‌ی `target` و `.git` را کنار می‌گذارد. این فایل را build نکرده‌ام و link با musl داخل image‌ی `rust` هم آزمایش نشده است.

## workflow‌های CI و release

`ci.yml` این‌ها را اجرا می‌کند: `cargo fmt --check`، `cargo clippy --locked --all-targets -- -D warnings` و `cargo test --locked`. هر سه را محلی اجرا کردم و پاس شدند. `release.yml` با تگ‌های `v*` اجرا می‌شود، یک matrix سه‌تایی با `upload-artifact` می‌سازد و یک job جدا به نام `image` به GHCR push می‌کند؛ فقط همان job مجوز `packages: write` دارد. نسخه‌ی action‌ها روی آخرین تگ‌هایی pin شده که از API گیت‌هاب پرسیدم: `actions/checkout@v7.0.1`، `Swatinem/rust-cache@v2.9.3`، `docker/build-push-action@v7.4.0` و بقیه. هر دو فایل پاس می‌شوند:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ go run ... .github/workflows/release.yml
exit=0 (both)
```

عمداً matrix را هم خراب کردم (`matrix.targt`): actionlint گفت `property "targt" is not defined in object type {os: string; target: string}`. این ابزار سینتکس را می‌سنجد، نه اینکه push کار می‌کند.

## بهداشت زنجیره‌ی تأمین

- `Cargo.lock` را برای باینری‌ها commit کنید و همه‌جا `--locked` بگذارید، تا CI همان چیزی را بسازد که review شده.
- `cargo audit` یا `cargo deny` را در CI اجرا کنید (اینجا اجرایشان نکردم؛ فقط اشاره می‌کنم).
- toolchain را pin کنید (`1.90.0`).

## چند نکته که باید حواستان باشد

- قبل از اعتماد به Dockerfile، `docker build` را خودتان اجرا کنید.
- `panic = "abort"` رفتار panic را عوض می‌کند؛ ببینید چیزی به `catch_unwind` وابسته نباشد.

## قدم بعدی

مقاله‌ی بعد: Rust و WebAssembly، همین زبان برای یک مقصد کاملاً متفاوت.
