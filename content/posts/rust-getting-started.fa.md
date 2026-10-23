+++
date = '2026-10-29T10:00:00+03:30'
draft = false
title = 'شروع کار با Rust: نصب، Cargo و اولین برنامه'
description = 'اولین مقاله‌ی سری Rust برای برنامه‌نویس‌های Go و Node.js: نصب با rustup، دستورهای اصلی Cargo، افزودن dependency و اجرای اولین برنامه.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "cargo", "beginner", "tooling"]
cover = { image = "/images/covers/rust-getting-started.fa.png", alt = "شروع کار با Rust: نصب، Cargo و اولین برنامه", hiddenInSingle = true, hiddenInList = true }
+++

این اولین مقاله‌ی یک سری آموزشی Rust است، از مقدماتی تا پیشرفته. بیشتر سال‌های کاری‌ام را با Go و Node.js سرویس backend نوشته‌ام و حالا دارم Rust را علنی یاد می‌گیرم. هرجا مفید باشد Rust را با Go مقایسه می‌کنم، چون قبلاً چند مقاله درباره‌ی Go نوشته‌ام.

اصلاً چرا Rust؟ نه به‌خاطر مد بودنش. Rust امنیت حافظه را بدون **garbage collector** می‌دهد، سرعتی در حد C و C++ دارد و سیستم نوع (type system) قوی‌ای دارد که خیلی از باگ‌ها را از زمان اجرا به زمان کامپایل می‌آورد. هزینه‌اش منحنی یادگیری تندتر است و کامپایلری که اوایل زیاد با شما بحث می‌کند. این مقاله فقط درباره‌ی ابزارهاست: نصب، Cargo و یک برنامه‌ی اجراشدنی.

> همه‌ی مثال‌ها با Rust 1.90.0 روی macOS اجرا شده‌اند.

## نصب با rustup

راه رسمی، **rustup** است، مدیر toolchain (از https://rustup.rs):

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

این دستور کامپایلر (`rustc`) و ابزار build و مدیریت پکیج یعنی **Cargo** را نصب می‌کند و بعداً با `rustup update` می‌توانید به‌روزرسانی کنید. نصب را بررسی کنید:

```bash
$ rustc --version
rustc 1.90.0 (1159e78c4 2025-09-14)
$ cargo --version
cargo 1.90.0 (840b83a10 2025-07-30)
```

## اولین پروژه با Cargo

در عمل تقریباً هیچ‌وقت `rustc` را مستقیم صدا نمی‌زنیم؛ Cargo این کار را می‌کند:

```bash
$ cargo new rust-getting-started
    Creating binary (application) `rust-getting-started` package
$ cd rust-getting-started
```

ساختار پروژه کوچک است: فایل `Cargo.toml` (نام، نسخه و dependencyها؛ شبیه `go.mod` با کمی metadata بیشتر) و `src/main.rs` که نقطه‌ی شروع برنامه است. این `Cargo.toml` تولیدشده است:

```toml
[package]
name = "rust-getting-started"
version = "0.1.0"
edition = "2024"

[dependencies]
```

`edition` نسخه‌ی زبان است و باعث می‌شود Rust بدون شکستن کدهای قدیمی پیشرفت کند. فایل `main.rs` یک hello world است و `cargo run` آن را build و اجرا می‌کند:

```bash
$ cargo run
   Compiling rust-getting-started v0.1.0 (...)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.37s
     Running `target/debug/rust-getting-started`
Hello, world!
```

## Debug و release

`cargo build` یک build **debug** می‌سازد که سریع کامپایل می‌شود و در `target/debug/` قرار می‌گیرد. `cargo build --release` بهینه‌سازی را روشن می‌کند و خروجی در `target/release/` است:

```bash
$ cargo build --release
    Finished `release` profile [optimized] target(s) in 0.34s
$ ls target
CACHEDIR.TAG  debug  release
$ ls -la target/debug/rust-getting-started target/release/rust-getting-started
-rwxr-xr-x@ 1 hossein  staff  443816 ... target/debug/rust-getting-started
-rwxr-xr-x@ 1 hossein  staff  406208 ... target/release/rust-getting-started
```

برای hello world اندازه‌ها نزدیک هم‌اند؛ تفاوت اصلی در سرعت کدهای سنگین است. هنگام توسعه از debug استفاده کنید و برای هر چیزی که اندازه‌گیری یا منتشر می‌کنید از `--release`.

## Check، format و lint

- `cargo check` فقط نوع‌ها را بررسی می‌کند و فایل اجرایی نمی‌سازد، پس خیلی سریع‌تر از build کامل است. من مدام اجرایش می‌کنم.
- `cargo fmt` کد را با `rustfmt` فرمت می‌کند (مثل `gofmt`). `cargo fmt --check` فقط گزارش می‌دهد.
- `cargo clippy` همان linter است. روی دستگاه من با پروفایل پیش‌فرض rustup نصب بود و برای کد زیر هیچ warning‌ای نداد.

## برنامه‌ای کمی بزرگ‌تر، با dependency

یک crate را با `cargo add` اضافه کنید (بار اول به اینترنت نیاز دارد):

```bash
$ cargo add rand
      Adding rand v0.10.3 to dependencies
```

Cargo خودش `Cargo.toml` را ویرایش می‌کند (`rand = "0.10.3"`). حالا برنامه‌ای که یک آرگومان اختیاری از خط فرمان می‌گیرد و یک سلام همراه با عدد تصادفی چاپ می‌کند:

```rust
use std::env;

use rand::RngExt;

fn main() {
    // اولین آرگومان خط فرمان، یا "world" اگر چیزی داده نشود
    let name = env::args().nth(1).unwrap_or_else(|| "world".to_string());
    let lucky: u32 = rand::rng().random_range(1..=100);
    println!("Hello, {name}! Your lucky number is {lucky}.");
}
```

`env::args().nth(1)` یک `Option` برمی‌گرداند (شاید آرگومانی نباشد) و `unwrap_or_else` مقدار پیش‌فرض را می‌دهد. `Option` را بعداً درست توضیح می‌دهیم. خروجی (عدد در هر اجرا فرق می‌کند):

```bash
$ cargo run -q
Hello, world! Your lucky number is 78.
$ cargo run -q -- Roham
Hello, Roham! Your lucky number is 20.
```

`--` آرگومان‌های خود Cargo را از آرگومان‌های برنامه‌ی شما جدا می‌کند.

## مقایسه‌ی ابزارهای Go و Rust

| کار | Go | Rust |
| --- | --- | --- |
| پروژه‌ی جدید | `go mod init` | `cargo new` |
| Build و اجرا | `go run .` | `cargo run` |
| Build | `go build` | `cargo build` (با `--release` برای بهینه) |
| افزودن dependency | `go get` | `cargo add` |
| فرمت کد | `gofmt` / `go fmt` | `cargo fmt` |
| فایل dependency | `go.mod` | `Cargo.toml` (به‌همراه `Cargo.lock`) |

## چند نکته

- Cargo خروجی را در `target/` می‌سازد که می‌تواند بزرگ شود. آن را از git دور نگه دارید (`cargo new` برایش `.gitignore` می‌سازد).
- اولین build بعد از افزودن dependency، آن را دانلود و کامپایل می‌کند؛ buildهای بعدی از cache استفاده می‌کنند.
- نسخه‌ی crateها سریع عوض می‌شود. در `rand` نسخه‌ی 0.10 برای `random_range` باید `use rand::RngExt` بنویسید؛ آموزش‌های قدیمی API دیگری نشان می‌دهند، پس نسخه را چک کنید.
- هنگام ویرایش از `cargo check` و هنگام سنجش سرعت از `--release` استفاده کنید.
- Clippy و rustfmt «component» هستند؛ اگر `cargo clippy` نبود، `rustup component add clippy` را بزنید.

## تمرین

۱. برنامه را طوری تغییر دهید که دو آرگومان بگیرد، یک نام و یک حداکثر عدد، و عدد شانسی را از `1..=max` انتخاب کند. (راهنما: آرگومان‌ها رشته‌اند، پس باید دومی را parse کنید.)
۲. `cargo build --release` را بزنید و با `ls -la` فایل اجرایی را با نسخه‌ی debug مقایسه کنید.

## قدم بعدی

در مقاله‌ی بعد درباره‌ی نوع‌ها، متغیرها و کنترل جریان در Rust صحبت می‌کنیم: immutable بودن به‌صورت پیش‌فرض، shadowing، `if`، `match` و حلقه‌ها.
