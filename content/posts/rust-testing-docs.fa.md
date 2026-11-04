+++
date = '2027-01-05T10:00:00+03:30'
draft = false
title = 'تست و مستندسازی در Rust'
description = 'تست واحد، تست یکپارچگی و doc test در Rust: ماکروهای assert و خروجی شکستشان، should_panic، ignore، فیلتر تست‌ها و cargo doc روی یک crate کوچک.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "testing", "documentation", "intermediate"]
cover = { image = "/images/covers/rust-testing-docs.fa.png", alt = "تست و مستندسازی در Rust", hiddenInSingle = true }
+++

یک خط از تابعی را که پول فرمت می‌کند عوض می‌کنید و یک هفته بعد مشتری به‌جای `123.45` عبارت `1,23.45` را می‌بیند. تست راهی است که همان روز جلوی این را بگیرید: یک تابع کوچک که کد شما را با ورودی معلوم صدا می‌زند و بررسی می‌کند جواب همان باشد که انتظار دارید. در Rust برای این کار لازم نیست چیزی نصب کنید. اجراکننده‌ی تست جزو `cargo` است، و مثال‌هایی که در مستندات می‌نویسید هم به‌عنوان تست اجرا می‌شوند، پس مثال مستنداتی که دیگر با کد جور نیست مثل هر تست دیگر بیلد را شکست می‌دهد.

این مقاله بعد از [Smart Pointerها](/fa/posts/rust-smart-pointers/) می‌آید و درباره‌ی تست و مستندسازی است، که Rust هر دو را داخل خودش دارد. اگر [تست در Go](/fa/posts/go-testing-basics/) را خوانده باشید، روال را می‌شناسید و تفاوت‌ها را نزدیک آخر گفته‌ام.

یک crate کتابخانه‌ای کوچک به اسم `textkit` را تست می‌کنیم که سه تابع دارد: `slugify` (عنوان را به slug برای URL تبدیل می‌کند، `"Hello, World!"` می‌شود `hello-world`)، `format_cents` (`123456` می‌شود `1,234.56`) و `parse_cents` (`"12.34"` را به `1234` تبدیل می‌کند و چون ورودی ممکن است بد باشد `Result` برمی‌گرداند).

> همه‌چیز را با Rust نسخه‌ی 1.90 (edition 2024) اجرا کرده‌ام، همان نسخه‌ی اجرای اول. خروجی‌ها از اجرای واقعی demo برداشته شده‌اند. مسیر موقت را در یک پیام panic با `<tmp>` عوض کرده‌ام و خط‌های «For more information…» را حذف کرده‌ام. در مثال‌های شکست، پیام‌هایی را نشان می‌دهم که برایم مهم است و بقیه را بریده‌ام.

## ساختار پروژه

یک crate کتابخانه‌ای با پوشه‌ی `tests/` کنار `src/`:

```text
textkit/
├── Cargo.toml
├── src/
│   └── lib.rs
└── tests/
    └── public_api.rs
```

`src/lib.rs` سه تابع، مستندات آن‌ها و تست‌های واحد را دارد. `tests/public_api.rs` تست‌هایی دارد که کتابخانه را از بیرون به کار می‌برند. هر دو نوع با یک دستور اجرا می‌شوند: `cargo test`.

## تست واحد: کنار کد

تست یک تابع معمولی است که بالایش `#[test]` نوشته شده. **attribute** برچسبی است که به کامپایلر چیزی درباره‌ی آنچه زیرش آمده می‌گوید. `cargo test` هر تابعی را که این برچسب را دارد پیدا و اجرا می‌کند. تست وقتی موفق است که عادی تمام شود و وقتی شکست می‌خورد که **panic** کند. panic روش Rust برای متوقف‌شدن با پیام خطاست، و ماکروهای `assert` وقتی بررسی‌شان رد شود panic می‌کنند.

{{< term "unit-test" "تست‌های واحد" >}} در همان فایل کد هستند، داخل ماژولی با علامت `#[cfg(test)]`. این علامت یعنی: این ماژول را فقط وقتی `cargo test` اجرا می‌شود کامپایل کن، تا برنامه‌ی اصلی بزرگ‌تر نشود. چون ماژول فرزند ماژول اصلی فایل است، `use super::*` به همه‌ی چیزهای بالاتر دسترسی می‌دهد، حتی تابع‌های خصوصی.

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

(demo واقعی دو ردیف بیشتر در `format_cents_table` دارد؛ اینجا حذفشان کرده‌ام.)

`assert!` بررسی می‌کند یک شرط درست باشد. `assert_eq!(a, b)` بررسی می‌کند دو مقدار برابرند و `assert_ne!(a, b)` که با هم فرق دارند؛ هر دو لازم دارند مقدارها `==` و چاپ با `Debug` را پشتیبانی کنند. هر کدام بعد از مقدارها یک پیام اختیاری با آرگومان‌های فرمت می‌گیرند. تست دوم از همین استفاده می‌کند، تا اگر یک ردیف شکست خورد پیام بگوید کدام ورودی خراب بوده. یک حلقه‌ی ساده روی آرایه‌ای از جفت‌های `(ورودی، انتظار)` روش معمول Rust برای تست جدولی است.

حالا یک بار کل اجرا را ببینید تا بتوانید بخوانیدش. این بخشِ تست‌های واحد در خروجی `cargo test` برای demo کامل است (نُه تست دارد):

```text
running 9 tests
test tests::big_loop ... ignored, slow in real life
test tests::format_cents_table ... ok
test tests::parse_cents_errors ... ok
test tests::parse_cents_ok ... ok
test tests::slugify_collapses_separators ... ok
test tests::slugify_empty_is_empty ... ok
test tests::prints_something ... ok
test tests::slugify_basic ... ok
test tests::unwrap_bad_amount_panics - should panic ... ok

test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
```

هر خط یک تست است: مسیرش (`tests::` اسم ماژول است و بعد اسم تابع) و `ok`. آخرین خط خلاصه است: ۸ تست موفق، ۱ تست نادیده‌گرفته (`ignore` را پایین‌تر توضیح می‌دهم). تست‌ها موازی روی چند thread اجرا می‌شوند و خط‌ها به ترتیب تمام‌شدن می‌آیند، پس ترتیب در هر اجرا می‌تواند فرق کند (در اجرای نشان‌داده‌شده `prints_something` زودتر از `slugify_basic` تمام شد).

## شکست چه شکلی است

تستِ موفق چیزی درباره‌ی پیام‌ها یاد نمی‌دهد، پس عمداً در یک crate جدا به اسم `broken/` در پوشه‌ی demo همه‌چیز را خراب کردم. `slugify` آنجا یک نسخه‌ی ساده است که فقط حروف را کوچک می‌کند و فاصله‌ها را عوض می‌کند، پس نشانه‌گذاری را پاک نمی‌کند. پیام تستی که slug عبارت `"Hello, World!"` را مقایسه می‌کند:

```text
---- tests::eq_fails stdout ----

thread 'tests::eq_fails' panicked at src/lib.rs:20:9:
assertion `left == right` failed: slug of a title with punctuation
  left: "hello,-world!"
 right: "hello-world"
```

بالا نوشته کدام تست شکست خورد و panic کجا رخ داد (فایل، خط، ستون). بعد خود assertion می‌آید: `left` آرگومان اول است، `right` آرگومان دوم، و پیام خودتان بعد از دو نقطه می‌آید. به‌جای `hello-world` گرفتیم `hello,-world!`، که دقیقاً همان باگ است.

assertion‌های دیگر هم به همین شکل شکست می‌خورند. `assert_ne!(double(2), 4)` با ``assertion `left != right` failed`` شکست می‌خورد و در دو طرف `4` چاپ می‌شود. و `assert!` ساده چپ و راست ندارد، پس پیام خودم را با مقدار واقعی ساختم:

```text
thread 'tests::plain_fails' panicked at src/lib.rs:30:9:
slug was "a-b"
```

قاعده‌ی کلی: تست وقتی شکست می‌خورد که panic کند، پس هر panic‌ای حساب می‌شود، چه از `assert` بیاید چه از `unwrap` روی یک `Err`.

## should_panic و Result و ignore

گاهی رفتار درست همان panic کردن است. برای تستش `#[should_panic]` بگذارید. تست فقط وقتی موفق است که کد panic کند. با `expected` فقط وقتی موفق است که پیام panic آن متن را داشته باشد:

```rust
#[test]
#[should_panic(expected = "invalid amount")]
fn unwrap_bad_amount_panics() {
    parse_cents("x").map_err(|e| e.to_string()).expect("invalid amount");
}
```

اگر کد با پیام دیگری panic کند چه؟ در crate به اسم `broken` یک تست متن `overflow` را انتظار دارد ولی کد با `something else` panic می‌کند:

```text
thread 'tests::wrong_panic_message' panicked at src/lib.rs:36:9:
something else
note: panic did not contain expected string
      panic message: "something else"
 expected substring: "overflow"
```

تست شکست می‌خورد و note هم پیام واقعی را نشان می‌دهد و هم آنچه انتظار داشتید.

یک تست می‌تواند `Result<(), E>` هم برگرداند، که اجازه می‌دهد به‌جای unwrap کردن همه‌چیز از `?` در آن استفاده کنید:

```rust
#[test]
fn parse_cents_ok() -> Result<(), ParseError> {
    assert_eq!(parse_cents("12.34")?, 1234);
    assert_eq!(parse_cents("7")?, 700);
    assert_eq!(parse_cents("7.5")?, 750);
    Ok(())
}
```

اگر یکی از `?`‌ها `Err` برگرداند، تست شکست می‌خورد و خطا با `Debug` چاپ می‌شود. در crate به اسم `broken` یک تست `"x"` را با `?` به عدد صحیح تبدیل می‌کند و خروجی این است:

```text
---- tests::result_fails stdout ----
Error: ParseIntError { kind: InvalidDigit }
```

و در آخر، `#[ignore = "دلیل"]` یک تست را به‌طور پیش‌فرض رد می‌کند، که برای تست کند به کار می‌آید. به شکل `ignored, slow in real life` دیده می‌شود (فهرست بالا را ببینید) و `cargo test -- --ignored` فقط تست‌های ردشده را اجرا می‌کند. این را برای `big_loop` اجرا کردم و موفق شد.

## اجرای یک زیرمجموعه و دیدن خروجی

هر چیزی بعد از یک `--` تنها به خود برنامه‌ی تست می‌رسد، نه به cargo. یک کلمه قبل از آن تست‌ها را بر اساس نام فیلتر می‌کند و آن‌هایی را نگه می‌دارد که اسمشان آن را دارد:

```text
$ cargo test slugify
running 3 tests
test tests::slugify_basic ... ok
test tests::slugify_collapses_separators ... ok
test tests::slugify_empty_is_empty ... ok
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 6 filtered out
```

فقط سه تستی که `slugify` در اسمشان است اجرا شد و خلاصه می‌گوید شش‌تای دیگر فیلتر شدند. (فیلتر روی تست‌های integration هم اثر دارد: در اجرای واقعی گروه آن‌ها `0 passed ... 2 filtered out` چاپ کرد. در اجرای من برای این دستور هیچ گروه doc-test چاپ نشد؛ برای اجرای مثال مستنداتِ منطبق از `cargo test --doc slugify` استفاده می‌کنید. اینجا فقط گروه اول را نشان داده‌ام.)

خروجی تست‌های موفق گرفته و پنهان می‌شود. `cargo test --lib prints -- --nocapture` آن را نشان می‌دهد؛ تست `prints_something` آن‌وقت `slug = print-me` را چاپ می‌کند. و چون تست‌ها موازی اجرا می‌شوند، `-- --test-threads=1` آن‌ها را یکی‌یکی و به ترتیب اجرا می‌کند. وقتی تست‌ها یک فایل یا یک وضعیت سراسری را مشترکاً استفاده می‌کنند این کمک می‌کند.

## تست integration: استفاده از کتابخانه از بیرون

فایل‌های پوشه‌ی `tests/` فرق دارند. هر کدام به‌صورت یک crate جدا کامپایل می‌شود که کتابخانه‌ی شما را مثل یک کاربر بیرونی به کار می‌برد، پس یک {{< term "rust-integration-test" "تست integration" >}} فقط می‌تواند API عمومی را صدا بزند:

```rust
use textkit::{format_cents, parse_cents};

#[test]
fn round_trip() {
    let cents = parse_cents("1234.50").unwrap();
    assert_eq!(format_cents(cents), "1,234.50");
}
```

این تست یک رشته را به سنت تبدیل می‌کند و دوباره فرمتش می‌کند، که بررسی طبیعی توافق آن دو تابع است. هر فایل در `tests/` یک برنامه‌ی تست جدا با خط نتیجه‌ی خودش می‌شود. این فقط برای crate از نوع کتابخانه کار می‌کند، برای همین `textkit` یک `lib.rs` دارد: crate دودویی که فقط `main.rs` دارد را crate دیگر نمی‌تواند import کند.

## کامنت مستندات و doc test

Rust دو شکل کامنت برای مستندات دارد. `///` آیتمِ درست زیرش را مستند می‌کند و `//!` آیتمی را که آن را در بر دارد، معمولاً کل crate در بالای `lib.rs`. متن Markdown است و بخشی که دوستش دارم این است: هر بلاک کد در آن به‌عنوان تست کامپایل و اجرا می‌شود، به این تست می‌گویند {{< term "doc-test" "doc test" >}}.

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

مثالِ داخل مستندات کد واقعی است که خواننده می‌تواند آن را بردارد و کامپایلر بررسی می‌کند هنوز کار می‌کند. خلاصه‌ی کامل `cargo test` این است: سه گروه (واحد، integration، doc) که هرکدام خط نتیجه‌ی خودشان را دارند:

```text
Running unittests src/lib.rs
test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
Running tests/public_api.rs
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
Doc-tests textkit
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

چهار doc test مثال‌های `slugify` و `format_cents` و `parse_cents` و مثال بالای crate هستند.

وقتی یک مثال کهنه شود چه می‌شود؟ در `broken/` یک مثال غلط در کامنت مستندات نوشتم: `assert_eq!(textkit_broken::double(2), 5)`. اجرای `cargo test --doc` این را می‌دهد:

```text
test src/lib.rs - double (line 3) ... FAILED
thread 'main' panicked at <tmp>/doctest_bundle_2024.rs:6:1:
assertion `left == right` failed
  left: 4
 right: 5
```

مثل هر تست شکست‌خورده‌ی دیگری خوانده می‌شود و مثال را با فایل و شماره‌ی خطش در کامنت مستندات (`double (line 3)`) نام می‌برد. پس مستنداتی که دروغ می‌گوید دفعه‌ی بعد که تست‌ها را اجرا کنید گرفته می‌شود.

`cargo doc --no-deps` از این کامنت‌ها مستندات HTML می‌سازد. اجرایش کردم و `target/doc/textkit/index.html` ساخته شد، به‌علاوه‌ی یک صفحه برای هر آیتم مثل `fn.slugify.html`. `cargo doc --open` آن را در مرورگر هم باز می‌کند.

## مقایسه با Go

در هر دو زبان تست جزو ابزارهای اصلی است. در Go تست‌ها در فایل‌های `_test.go` کنار کد هستند؛ در Rust تست‌های واحد در همان فایل و زیر `#[cfg(test)]` می‌نشینند و تست‌های integration در `tests/`. Go تابع‌های `Example` دارد که خروجی‌شان بررسی می‌شود؛ Rust به‌جایش بلاک‌های کد در کامنت مستندات را اجرا می‌کند.

## چیزهایی که پایتان را گیر می‌اندازد

- **تست‌های integration تابع‌های خصوصی را نمی‌بینند.** آن‌ها crate شما را از بیرون به کار می‌برند، پس کد خصوصی را در ماژول تست واحد تست کنید.
- **تست‌های موفق چیزی چاپ نمی‌کنند.** خروجی تست‌های موفق پنهان است، مگر `-- --nocapture` بدهید.
- **یک تست واحد شکست‌خورده `cargo test` را پیش از گروه‌های بعدی متوقف می‌کند.** در `broken/` تست‌های واحد شکست خوردند و خروجی با ``error: test failed, to rerun pass `--lib` `` تمام شد و هیچ doc testای اجرا نشد. با `cargo test --no-fail-fast` همه‌ی گروه‌ها را به‌هرحال اجرا کنید (بررسی کردم که doc test هم اجرا می‌شود)، یا با `cargo test --doc` فقط doc test‌ها را.
- **تست‌ها موازی اجرا می‌شوند.** فایل، port یا متغیر محیطی مشترک می‌تواند آن‌ها را {{< term "flaky-test" "ناپایدار (flaky)" >}} کند. به هر تست داده‌ی خودش را بدهید، یا با `--test-threads=1` اجرا کنید.
- **`should_panic` بدون `expected` با هر panicی موفق می‌شود،** حتی ربط‌نداشته. `expected` را اضافه کنید.

## تمرین

۱. تستی بنویسید که `slugify("Ünï")` همان را که انتظار دارید برگرداند، و تصمیم بگیرید آیا رفتار دلخواهتان است (تابع فقط ASCII را نگه می‌دارد).
۲. یک doc test برای `ParseError` اضافه کنید که خروجی `Display` آن را نشان دهد.
۳. یک تست integration اضافه کنید که نشان دهد parse کردن `"1.234"` یک `Err` برمی‌گرداند.

## قدم بعدی

تا اینجا همه‌چیز روی یک thread اجرا شده. مقاله‌ی بعد، «Concurrency با Thread در Rust»، نشان می‌دهد همین قاعده‌های ownership چطور جلوی data race را هم می‌گیرند.
