+++
date = '2027-01-27T10:00:00+03:30'
draft = false
title = 'خطا در اپلیکیشن واقعی: thiserror و anyhow'
description = 'خطا در Rust با thiserror و anyhow: کوتاه کردن enum خطا، زنجیره‌ی context، downcast و نگاشت خطای تایپ‌دار به کد وضعیت HTTP در یک نقطه.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "errors", "thiserror", "anyhow", "backend"]
cover = { image = "/images/covers/rust-thiserror-anyhow.fa.png", alt = "خطا در اپلیکیشن واقعی: thiserror و anyhow", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-database-sqlx/) منبع معمول خطا دیتابیس بود: قطع اتصال، ردیف پیدا‌نشده، نقض constraint. در [مدیریت خطا با Result](/fa/posts/rust-error-handling-result/) پیاده‌سازی‌های `Display`، `Error` و `From` را دستی نوشتیم. برای یادگیری خوب است، اما کد تکراری زیادی دارد. دو crate این تکرار را حذف می‌کنند: **thiserror** برای نوع‌های خطایی که خودتان تعریف می‌کنید و **anyhow** برای کدی که فقط باید خطا را گزارش کند. Go هم جواب خودش را دارد، یعنی sentinel error و wrap کردن با `%w`، که در [پیکربندی، لاگ و خطا در Go](/fa/posts/go-config-logging-errors/) دیدیم.

> Rust 1.90، thiserror 2.0.21 و anyhow 1.0.104. همه‌ی کدهای زیر به‌صورت یک نمونه‌ی محلی کامپایل و اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## thiserror: همان enum با کد کمتر

این همان `DivideError` مقاله‌ی قبلی است. نسبت به نسخه‌ی دستی، پیاده‌سازی `Display`، پیاده‌سازی `Error` و `source()` حذف شده‌اند:

```rust
use std::num::ParseIntError;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum DivideError {
    #[error("parse {input:?}: {source}")]
    Parse {
        input: String,
        #[source]
        source: ParseIntError,
    },
    #[error("divide by zero")]
    DivideByZero,
}
```

`#[error("...")]` پیاده‌سازی `Display` را می‌سازد و می‌تواند از فیلدها استفاده کند. `#[source]` فیلدی را که `source()` برمی‌گرداند مشخص می‌کند (فیلدی به نام `source` خودکار شناخته می‌شود، من صریح نوشتم). با همان چهار ورودی قبلی دقیقاً همان رفتار را می‌بینیم:

```text
result: 42
error: divide by zero
  is DivideByZero: true
error: parse "abc": invalid digit found in string
  caused by: invalid digit found in string
  is DivideByZero: false
error: parse " x1": invalid digit found in string
  caused by: invalid digit found in string
  is DivideByZero: false
```

`#[from]` پیاده‌سازی `From` را می‌سازد و `?` خودش تبدیل می‌کند. `#[error(transparent)]` هم `Display` و هم `source()` را به خطای داخلی می‌سپارد:

```rust
#[derive(Debug, Error)]
pub enum AppError {
    #[error("config: {0}")]
    BadNumber(#[from] ParseIntError),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error("not found")]
    NotFound,
}

pub fn read_port(path: &str) -> Result<u16, AppError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> AppError::Io
    let n: u16 = text.trim().parse()?;         // ParseIntError -> AppError::BadNumber
    Ok(n)
}
```

```text
port = 8080
error: config: invalid digit found in string
error: No such file or directory (os error 2)
```

## کتاب‌خانه در برابر اپلیکیشن

قاعده‌ی من این است: **کتاب‌خانه** (library) خطای تایپ‌دار نشان می‌دهد، چون فراخواننده شاید بخواهد روی آن `match` کند. **اپلیکیشن** بیشتر گزارش می‌دهد: لاگ می‌کند، چاپ می‌کند، 500 برمی‌گرداند. برای این کار `anyhow::Result<T>` کافی است. یک نوع خطاست که هر چیزی با `std::error::Error` را نگه می‌دارد و `?` خودکار به آن تبدیل می‌کند.

## زنجیره‌ی context

`anyhow::Context` در مسیر بالا آمدن خطا پیام اضافه می‌کند. `.with_context(|| ...)` پیام را تنبل (lazy) و فقط هنگام شکست می‌سازد:

```rust
fn load(path: &str) -> Result<u16> {
    let port = read_port(path).with_context(|| format!("load config {path}"))?;
    Ok(port)
}

fn run() -> Result<()> {
    load("/tmp/port_bad.txt").context("start server")?;
    Ok(())
}
```

همان خطا با سه شکل چاپ:

```text
--- {}
start server
--- {:#}
start server: load config /tmp/port_bad.txt: config: invalid digit found in string: invalid digit found in string
--- {:?}
start server

Caused by:
    0: load config /tmp/port_bad.txt
    1: config: invalid digit found in string
    2: invalid digit found in string
```

`{}` فقط بیرونی‌ترین پیام را نشان می‌دهد، `{:#}` کل زنجیره را در یک خط می‌آورد (برای لاگ مناسب است) و `{:?}` فهرست چندخطی `Caused by:` را می‌دهد (برای ترمینال خوب است). `err.chain()` لایه‌ها را پیمایش می‌کند. به تکرار «invalid digit found in string» دقت کنید: واریانت `BadNumber` من هم source را در پیام خودش چاپ می‌کند و هم به‌عنوان source در دسترس می‌گذارد. یکی را انتخاب کنید.

## anyhow! و bail! و ensure!

```rust
fn check(port: i64, host: &str) -> Result<()> {
    ensure!(port > 0, "port must be positive, got {port}");
    if host.is_empty() {
        bail!("host is empty");
    }
    if host == "forbidden" {
        return Err(anyhow!("host {host} is not allowed"));
    }
    Ok(())
}
```

```text
ok
error: port must be positive, got -1
error: host is empty
error: host forbidden is not allowed
```

`anyhow!` یک خطا می‌سازد، `bail!` معادل `return Err(anyhow!(...))` است و `ensure!` یک شرط به‌علاوه‌ی `bail!` است.

## Downcast کردن

`anyhow::Error` نوع واقعی را پنهان می‌کند، اما می‌تواند آن را پس بدهد، حتی با context اضافه‌شده:

```rust
let err = work().unwrap_err(); // divide("1","0").context("compute ratio")
match err.downcast_ref::<DivideError>() {
    Some(DivideError::DivideByZero) => println!("downcast_ref: DivideByZero"),
    Some(other) => println!("downcast_ref: other {other}"),
    None => println!("downcast_ref: None"),
}
println!("is::<std::io::Error>: {}", err.is::<std::io::Error>());
```

```text
display: compute ratio: divide by zero
downcast_ref: DivideByZero
is::<std::io::Error>: false
```

معادل `errors.As` در Go است. `downcast` (با مالکیت) و `is` هم وجود دارند.

## main و backtrace

```rust
fn main() -> Result<()> {
    println!("starting");
    let n: i32 = "abc".parse().context("read PORT")?;
    println!("n = {n}");
    Ok(())
}
```

```text
starting
Error: read PORT

Caused by:
    invalid digit found in string
```

کد خروج 1 است (با `echo $?` چک کردم). برخلاف `Box<dyn Error>`، فهرست `Caused by:` را مجانی می‌گیرید. درباره‌ی backtrace: بدون متغیر محیطی چیز اضافه‌ای چاپ نشد. با `RUST_BACKTRACE=1` بخش `Stack backtrace:` اضافه شد؛ فقط `RUST_LIB_BACKTRACE=1` هم همین را داد؛ و `RUST_LIB_BACKTRACE=0 RUST_BACKTRACE=1` هیچ backtrace‌ای چاپ نکرد.

## نگاشت خطا به کد وضعیت در یک نقطه

معادل Rust تابع `statusOf` مقاله‌ی Go یک `match` روی خطای تایپ‌دار است. به کلاینت متن ثابت می‌دهیم و زنجیره‌ی کامل به لاگ می‌رود. `Other(#[from] anyhow::Error)` هر چیز غیرمنتظره را می‌گیرد:

```rust
#[derive(Debug, Error)]
enum ServiceError {
    #[error("order {0} not found")]
    NotFound(String),
    #[error("invalid {field}: {reason}")]
    Validation { field: &'static str, reason: String },
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

fn status_of(err: &ServiceError) -> (u16, String) {
    match err {
        ServiceError::Validation { .. } => (422, err.to_string()),
        ServiceError::NotFound(_) => (404, "not found".to_string()),
        ServiceError::Other(_) => (500, "internal error".to_string()),
    }
}
```

```text
404 not found   (log: order 42 not found)
422 invalid qty: must be > 0   (log: invalid qty: must be > 0)
500 internal error   (log: dial tcp 10.0.0.5:5432: connection refused)
```

## چند نکته

- `anyhow::Error` را در API عمومی کتاب‌خانه نگذارید. فراخواننده نمی‌تواند `match` کند، فقط downcast.
- `{}` علت‌ها را پنهان می‌کند. با `{:#}` یا `{:?}` لاگ کنید وگرنه دلیل را از دست می‌دهید.
- `err.to_string()` یک خطای ناشناس را هرگز به کلاینت نفرستید، مثل نگاشت بالا.
- پیامی که source خودش را در متن دارد و هم‌زمان `source()` هم می‌دهد، در `{:#}` دو بار چاپ می‌شود.
- `with_context` با closure از ساختن رشته در مسیر موفق جلوگیری می‌کند.

## تمرین

1. واریانت `Forbidden` را به `ServiceError` اضافه کنید و آن را به 403 نگاشت کنید.
2. در برنامه‌ی `chain` یک لایه‌ی سوم `.context(...)` اضافه کنید و `{:#}` را با `{:?}` مقایسه کنید.
3. تابعی بنویسید که یک `anyhow::Error` بگیرد و اگر `AppError::NotFound` در آن بود 404 برگرداند، با `downcast_ref`.

## قدم بعدی

در مقاله‌ی بعد سراغ کلاینت async برای NATS JetStream در Rust می‌رویم.
