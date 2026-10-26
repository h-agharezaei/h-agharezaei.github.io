+++
date = '2027-01-05T10:00:00+03:30'
draft = false
title = 'تست و مستندسازی در Rust'
description = 'تست واحد، تست یکپارچگی و doc test در Rust: ماکروهای assert و خروجی شکستشان، should_panic، ignore، فیلتر تست‌ها و cargo doc روی یک crate کوچک.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "testing", "documentation", "intermediate"]
cover = { image = "/images/covers/rust-testing-docs.fa.png", alt = "تست و مستندسازی در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-smart-pointers/) با smart pointerها آشنا شدیم. حالا سراغ چیزی می‌رویم که هر پروژه‌ی واقعی لازمش دارد: تست و مستندات. Rust هر دو را در خودش دارد و این دو به هم نزدیک‌تر از بیشتر زبان‌ها هستند، چون مثال‌های داخل مستندات کامپایل می‌شوند و مثل تست اجرا می‌شوند. اگر [مقاله‌ی تست در Go](/fa/posts/go-testing-basics/) را خوانده باشید، روند کار برایتان آشناست؛ تفاوت‌ها را آخر مقاله می‌گویم.

یک crate کتاب‌خانه‌ای کوچک به اسم `textkit` را تست می‌کنیم با سه تابع: `slugify` (عنوان به slug برای URL)، `format_cents` (عدد `123456` به `1,234.56`) و `parse_cents` (رشته‌ی `"12.34"` به `1234` که `Result` برمی‌گرداند).

> همه‌چیز با Rust نسخه‌ی 1.90 (edition 2024) اجرا شده و خروجی‌ها از اجراهای واقعی کپی شده‌اند.

## ساختار پروژه

crate یک کتاب‌خانه است به‌علاوه‌ی پوشه‌ی `tests/`:

```text
textkit/
├── Cargo.toml
├── src/
│   └── lib.rs
└── tests/
    └── public_api.rs
```

## تست واحد

تست‌های واحد (**unit test**) در همان فایلِ کد و داخل ماژولی با `#[cfg(test)]` قرار می‌گیرند. این ماژول فقط برای `cargo test` کامپایل می‌شود. چون ماژول فرزند است، `use super::*` به همه‌ی چیزهای والد، حتی بخش‌های private، دسترسی می‌دهد.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slugify_basic() {
        assert_eq!(slugify("Hello, World!"), "hello-world");
    }

    #[test]
    fn format_cents_table() {
        let cases = [(0, "0.00"), (5, "0.05"), (123456, "1,234.56"), (-250000, "-2,500.00")];
        for (input, want) in cases {
            assert_eq!(format_cents(input), want, "input = {input}");
        }
    }
}
```

`assert!` یک مقدار بولی را چک می‌کند و `assert_eq!` و `assert_ne!` دو مقدار را مقایسه می‌کنند (نوع‌ها باید `Debug` و `PartialEq` داشته باشند). هر سه یک پیام اختیاری با قالب رشته می‌گیرند، مثل تست دوم، تا ردیفِ خراب را بشناسید. حلقه روی آرایه‌ای از حالت‌ها، معادل معمول Rust برای تست table-driven است.

## شکست چه شکلی است

عمداً در crate جداگانه‌ای به اسم `broken/` در پوشه‌ی دمو چیزها را خراب کردم. یک `slugify` ساده که نشانه‌گذاری را حذف نمی‌کند:

```text
---- tests::eq_fails stdout ----

thread 'tests::eq_fails' panicked at src/lib.rs:20:9:
assertion `left == right` failed: slug of a title with punctuation
  left: "hello,-world!"
 right: "hello-world"
```

`left` آرگومان اول است، `right` آرگومان دوم و پیام شما بعد از دونقطه می‌آید. `assert_ne!(double(2), 4)` با ``assertion `left != right` failed`` شکست می‌خورد و هر دو طرف `4` چاپ می‌شود. تست وقتی شکست می‌خورد که panic کند، پس هر panicی حساب می‌شود.

## should_panic، Result و ignore

برای تست اینکه کدی panic می‌کند، `#[should_panic]` بگذارید. با `expected` تست فقط وقتی پاس می‌شود که پیام panic شامل آن زیررشته باشد:

```rust
#[test]
#[should_panic(expected = "invalid amount")]
fn unwrap_bad_amount_panics() {
    parse_cents("x").map_err(|e| e.to_string()).expect("invalid amount");
}
```

اگر پیام فرق داشته باشد، `panic did not contain expected string` را همراه پیام واقعی و مورد انتظار می‌بینید. تست می‌تواند `Result<(), E>` هم برگرداند تا داخلش از `?` استفاده کنید. `Err` تست را رد می‌کند و خطا را با `Debug` چاپ می‌کند، مثلاً `Error: ParseIntError { kind: InvalidDigit }`:

```rust
#[test]
fn parse_cents_ok() -> Result<(), ParseError> {
    assert_eq!(parse_cents("12.34")?, 1234);
    Ok(())
}
```

`#[ignore = "reason"]` یک تست کند را به‌طور پیش‌فرض کنار می‌گذارد. در خروجی به شکل `ignored, slow in real life` می‌آید و `cargo test -- --ignored` فقط تست‌های ignore شده را اجرا می‌کند.

## اجرای زیرمجموعه و دیدن خروجی

هرچه بعد از یک `--` تنها بیاید به خود باینری تست می‌رسد. کلمه‌ای قبل از آن، نام تست‌ها را بر اساس زیررشته فیلتر می‌کند:

```text
$ cargo test slugify
running 3 tests
test tests::slugify_empty_is_empty ... ok
test tests::slugify_basic ... ok
test tests::slugify_collapses_separators ... ok
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 6 filtered out
```

خروجی تست‌های موفق گرفته و پنهان می‌شود. `cargo test --lib prints -- --nocapture` آن را نشان می‌دهد (`slug = print-me`). تست‌ها روی چند thread اجرا می‌شوند؛ `-- --test-threads=1` آن‌ها را پشت سر هم اجرا می‌کند، که وقتی به یک فایل یا state مشترک دست می‌زنند به کار می‌آید.

## تست یکپارچگی

فایل‌های `tests/` crateهای جداگانه‌ای هستند که کتاب‌خانه‌ی شما را مثل یک کاربر بیرونی لینک می‌کنند، پس فقط به API عمومی دسترسی دارند:

```rust
use textkit::{format_cents, parse_cents};

#[test]
fn round_trip() {
    let cents = parse_cents("1234.50").unwrap();
    assert_eq!(format_cents(cents), "1,234.50");
}
```

هر فایل آنجا یک باینری تستِ جداست. این فقط برای crate کتاب‌خانه‌ای جواب می‌دهد و برای همین `textkit` یک `lib.rs` دارد.

## کامنت مستندات و doc test

`///` آیتمِ بعدی‌اش را مستند می‌کند و `//!` آیتمِ دربرگیرنده را، که معمولاً خودِ crate در بالای `lib.rs` است. Markdown کار می‌کند و هر بلاک کد کامپایل می‌شود و مثل تست اجرا می‌شود:

```rust
/// Parses `"12.34"` into `1234` cents.
///
/// ```
/// use textkit::{parse_cents, ParseError};
///
/// assert_eq!(parse_cents("12.34"), Ok(1234));
/// assert_eq!(parse_cents(""), Err(ParseError::Empty));
/// ```
pub fn parse_cents(s: &str) -> Result<i64, ParseError> { /* ... */ }
```

این هم خلاصه‌ی کامل `cargo test`: سه گروه (unit، integration، doc) که هر کدام خط نتیجه‌ی خودش را دارد.

```text
Running unittests src/lib.rs
test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
Running tests/public_api.rs
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
Doc-tests textkit
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

مثالِ کهنه، تست را قرمز می‌کند. در `broken/` در یک کامنت مستندات نوشتم `assert_eq!(textkit_broken::double(2), 5)`:

```text
test src/lib.rs - double (line 3) ... FAILED
thread 'main' panicked at .../doctest_bundle_2024.rs:6:1:
assertion `left == right` failed
  left: 4
 right: 5
```

`cargo doc --no-deps` مستندات HTML می‌سازد. بررسی کردم که `target/doc/textkit/index.html` ساخته شد، به‌علاوه‌ی یک صفحه برای هر آیتم، مثل `fn.slugify.html`. با `cargo doc --open` هم باز می‌شود.

## مقایسه با Go

در هر دو زبان تست بخشی از toolchain است. در Go تست‌ها در فایل‌های `_test.go` کنار کد هستند؛ در Rust تست واحد در همان فایل زیر `#[cfg(test)]` است و تست یکپارچگی در `tests/`. Go تابع‌های `Example` دارد که با خروجی‌شان چک می‌شوند؛ Rust بلاک‌های کدِ کامنت مستندات را اجرا می‌کند.

## چند نکته

- تست یکپارچگی تابع private را نمی‌بیند. آن‌ها را در ماژول تست واحد بررسی کنید.
- خروجی تست‌های موفق بدون `--nocapture` پنهان است.
- شکست یک تست واحد باعث می‌شود `cargo test` پیش از doc testها متوقف شود. برای اجرای تنهایشان `cargo test --doc` بزنید.
- تست‌ها موازی اجرا می‌شوند؛ فایل یا متغیر محیطی مشترک می‌تواند آن‌ها را ناپایدار کند.
- `should_panic` بدون `expected` با هر panicی پاس می‌شود، حتی panic بی‌ربط.

## تمرین

1. تستی بنویسید که خروجی `slugify("Ünï")` را چک کند و تصمیم بگیرید رفتار دلخواه شماست یا نه (تابع فقط ASCII نگه می‌دارد).
2. برای `ParseError` یک doc test بنویسید که خروجی `Display` آن را نشان دهد.
3. یک تست یکپارچگی بنویسید که نشان دهد `"1.234"` به `Err` می‌رسد.

## قدم بعدی

در مقاله‌ی بعد سراغ concurrency با thread در Rust می‌رویم: ساخت thread، منتقل کردن داده به آن و اشتراک امن state.
