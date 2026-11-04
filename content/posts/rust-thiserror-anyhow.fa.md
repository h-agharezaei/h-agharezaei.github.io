+++
date = '2027-01-27T10:00:00+03:30'
draft = false
title = 'خطا در اپلیکیشن واقعی: thiserror و anyhow'
description = 'خطا در Rust با thiserror و anyhow: کوتاه کردن enum خطا، زنجیره‌ی context، downcast و نگاشت خطای تایپ‌دار به کد وضعیت HTTP در یک نقطه.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "errors", "thiserror", "anyhow", "backend"]
cover = { image = "/images/covers/rust-thiserror-anyhow.fa.png", alt = "خطا در اپلیکیشن واقعی: thiserror و anyhow", hiddenInSingle = true }
+++

یک درخواست به سرویس شما شکست می‌خورد و log فقط این را می‌گوید: `invalid digit found in string`. کدام درخواست؟ کدام فایل داشت خوانده می‌شد؟ برنامه می‌خواست چه کار کند؟ خطا درست است و بی‌فایده. یک پیام خطای خوب می‌گوید «وقتی این خراب شد چه می‌گذشت» و علت اصلی را هم نگه می‌دارد تا کد هنوز بتواند به آن نگاه کند.

یک خطا دو خواننده دارد و آن‌ها چیزهای متفاوتی می‌خواهند. بعضی کدها می‌خواهند *تصمیم بگیرند*: اگر سفارش نیست `404` بده؛ اگر پایگاه داده پایین است دوباره تلاش کن. این کد به خطاهایی نیاز دارد که بشود از هم تشخیص داد، یعنی نوعی که بتوان `match` کرد. یک آدم یا یک خط log می‌خواهد *بفهمد*: زنجیره‌ای از پیام‌ها از بالا («start server») تا علت اصلی. در [دیتابیس با SQLx در Rust](/fa/posts/rust-database-sqlx/) خطاها از پایگاه داده می‌آمدند: قطع اتصال، ردیف گم‌شده، نقض محدودیت. در [مدیریت خطا با Result و Option در Rust](/fa/posts/rust-error-handling-result/) پیاده‌سازی‌های `Display` و `Error` و `From` نوع‌های خطایمان را با دست نوشتیم. برای یادگیری خوب است ولی کد تکراری زیادی دارد. دو crate هر دو خواننده را پوشش می‌دهند: **thiserror** کد تکراری نوع‌های خطایی را که خودتان تعریف می‌کنید حذف می‌کند و **anyhow** یک خطای همه‌کاره با context است برای کدی که فقط باید گزارش بدهد. Go جواب خودش را دارد، sentinel error و wrap با `%w`، که در [کانفیگ، لاگ ساختاریافته و خطا در Go](/fa/posts/go-config-logging-errors/) آمده.

> از Rust نسخه‌ی 1.90، thiserror نسخه‌ی 2.0.21 و anyhow نسخه‌ی 1.0.104 استفاده کرده‌ام. همه‌چیز برای این نسخه‌ی مقاله دوباره کامپایل و اجرا شد، به‌شکل یک مثال محلی با هشت برنامه‌ی کوچک، و خروجی‌ها از اجراها کپی شده‌اند. demo فایل‌های نمونه‌اش را در `/tmp` می‌نویسد، برای همین این مسیرها را در خروجی می‌بینید.

## thiserror: همان enum با کد کمتر

`DivideError` مقاله‌ی قبلی این است. نسبت به نسخه‌ی دست‌نویس، پیاده‌سازی `Display` و پیاده‌سازی `Error` و `source()` همه رفته‌اند و derive آن‌ها را از روی attribute‌ها می‌نویسد:

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

`#[error("...")]` پیاده‌سازی `Display` را می‌سازد و پیام می‌تواند از فیلدهای variant استفاده کند. `#[source]` فیلدی را که `source()` برمی‌گرداند علامت می‌زند، و همین باعث می‌شود خطای اصلی در دسترس بماند. (فیلدی که اسمش `source` باشد خودکار شناخته می‌شود؛ من attribute را برای صریح‌بودن نوشتم.) demo چهار جفت رشته را تقسیم می‌کند: `84/2` و `1/0` و `abc/2` و ` x1/3`، و خطا و source آن و اینکه `DivideByZero` هست یا نه را چاپ می‌کند. رفتار با نسخه‌ی دست‌نویس یکی است:

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

حالت اول نتیجه‌ی عادی است. در بقیه، پیام خود خطا روی خط `error:` است، `source()` همان `ParseIntError` زیرین را می‌دهد (خط `caused by:`)، و برنامه هنوز می‌تواند با pattern match بپرسد «آیا از نوع تقسیم بر صفر است؟». همین بخش آخر دلیل ارزش یک خطای دارای نوع است.

دو attribute دیگر بقیه‌ی کد تکراری را می‌گیرند. `#[from]` پیاده‌سازی `From` را می‌سازد، پس `?` خطا را برایتان تبدیل می‌کند. `#[error(transparent)]` می‌گوید «این variant چیزی از خودش اضافه نمی‌کند»: هم پیام و هم `source()` از خطای داخلی می‌آید.

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

`read_port` یک فایل را می‌خواند و محتوایش را به‌عنوان شماره‌ی پورت parse می‌کند. demo آن را روی سه فایل صدا می‌زند: یکی با محتوای `8080`، یکی با `80x` و یکی که وجود ندارد:

```text
port = 8080
error: config: invalid digit found in string
error: No such file or directory (os error 2)
```

فایل اول درست کار می‌کند. دومی در `parse()` شکست می‌خورد که `?` آن را به `BadNumber` تبدیل کرد، پس پیام با پیشوند `config:` ما شروع می‌شود. سومی در `read_to_string` شکست می‌خورد و به `Io` تبدیل شد؛ چون آن variant از نوع `transparent` است، پیام همان متن خود سیستم‌عامل است، بدون هیچ پیشوندی.

## کتابخانه و اپلیکیشن

قاعده‌ای که خودم دنبال می‌کنم این است. یک **کتابخانه** خطای دارای نوع نشان می‌دهد، چون فراخواننده‌هایش ممکن است بخواهند `match` کنند، همان‌طور که همین الان با `DivideByZero` کردیم. یک **اپلیکیشن** (برنامه‌ی بالای همه، همان که `main` دارد) بیشتر خطا را *گزارش می‌کند*: log می‌کند، چاپ می‌کند یا به `500` تبدیلش می‌کند. برای این کار `anyhow::Result<T>` کافی است. یک نوع خطاست که هر نوع خطایی را که `std::error::Error` را پیاده کرده باشد نگه می‌دارد (و بشود آن را بین thread‌ها فرستاد، که نوع‌های خطای معمولی می‌شود)، و `?` خودکار به آن تبدیل می‌کند. خلاصه: `thiserror` برای نوع‌هایی که طراحی می‌کنید، `anyhow` برای چسبی که فقط خطا را رد می‌کند.

## زنجیره‌ی context

مشکل ابتدای مقاله پیامی بود که می‌گوید *چه چیز* شکست خورد ولی نمی‌گوید *چه می‌کردیم*. `anyhow::Context` این را حل می‌کند: وقتی خطا بالا می‌رود یک پیام به آن اضافه می‌کند. `.context("...")` یک پیام آماده می‌گیرد و `.with_context(|| ...)` یک closure که پیام را می‌سازد، پس رشته فقط وقتی ساخته می‌شود که واقعاً خطایی هست:

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

اینجا `run` تابع `load` را صدا می‌زند که `read_port` را روی فایلی با محتوای `80x` صدا می‌زند. هر لایه یک جمله اضافه می‌کند. demo همین خطا را به سه شکل چاپ می‌کند و بعد زنجیره را قدم می‌زند:

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
--- chain()
0: start server
1: load config /tmp/port_bad.txt
2: config: invalid digit found in string
3: invalid digit found in string
```

- `{}` فقط بیرونی‌ترین پیام را نشان می‌دهد. اگر خط log شما از این استفاده کند، دلیل را از دست می‌دهید.
- `{:#}` کل زنجیره را در یک خط و با دونقطه جدا می‌کند. برای log انتخاب خوبی است.
- `{:?}` پیام اول را چاپ می‌کند و بعد فهرست شماره‌دار `Caused by:`. برای ترمینال از همه بهتر است.
- `err.chain()` لایه‌ها را به‌شکل iterator می‌دهد، اگر بخواهید خودتان قالب‌بندی‌شان کنید.

به تکرار «invalid digit found in string» در انتهای خط `{:#}` و در لایه‌های ۱ و ۲ فهرست `{:?}` نگاه کنید. از variant ‏`BadNumber` خودم می‌آید: source را هم داخل پیام خودش چاپ می‌کند (`config: {0}`) *و* هم همان خطا را به‌عنوان `source()` نشان می‌دهد. پس متن دو بار می‌آید. یکی از این دو را انتخاب کنید: یا source در پیام، یا `source()`.

## anyhow! و bail! و ensure!

گاهی خطای زیرینی وجود ندارد و فقط می‌خواهید یکی بسازید. سه ماکرو این کار را می‌کنند:

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

demo آن را با `(80, "example.com")` و `(-1, "a")` و `(80, "")` و `(80, "forbidden")` صدا می‌زند:

```text
ok
error: port must be positive, got -1
error: host is empty
error: host forbidden is not allowed
```

`anyhow!` از یک پیام خطا می‌سازد، `bail!` میان‌بر `return Err(anyhow!(...))` است و `ensure!` بررسی یک شرط است به‌علاوه‌ی `bail!`. هر یک از سه حالت شکست بالا یکی از این سه را به کار برده است.

## downcast: برگرداندن نوع

یک `anyhow::Error` نوع خطای واقعی را پنهان می‌کند. ولی اگر جایی واقعاً لازم باشد بدانید «این تقسیم بر صفر بود؟»، می‌توانید بپرسید و جواب حتی از میان context‌های اضافه‌شده هم درست در می‌آید:

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

`downcast_ref::<T>()` وقتی خطا، جایی در زنجیره، از نوع `T` باشد `Some` برمی‌گرداند. هم‌ارز `errors.As` در Go است. متد `is::<T>()` جواب بله‌یا‌خیر می‌دهد و یک `downcast` مالک‌شونده هم هست (demo چاپ می‌کند `downcast (owned): DivideByZero`). کم از آن استفاده کنید: اگر زیاد downcast می‌کنید، یک enum با نوع بهتر به کارتان می‌آید.

## وقتی main یک Result برمی‌گرداند

`main` می‌تواند `anyhow::Result` برگرداند، که راه تنبل و خوب برای تمام‌کردن یک اپلیکیشن است:

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

برنامه خطا را با `{:?}` چاپ می‌کند، پس فهرست `Caused by:` را مفت می‌گیرید (برگرداندن `Box<dyn Error>` ساده از `main` چنین زنجیره‌ای چاپ نمی‌کند) و کد خروج ۱ است، که بررسی کردم. backtrace با متغیرهای محیطی کنترل می‌شود. وقتی هیچ‌کدام تنظیم نیست چیز اضافه‌ای چاپ نمی‌شود. با `RUST_BACKTRACE=1` خروجی بخش `Stack backtrace:` می‌گیرد؛ `RUST_LIB_BACKTRACE=1` تنها هم همین را می‌کند؛ و `RUST_LIB_BACKTRACE=0 RUST_BACKTRACE=1` هیچ‌چیز چاپ نکرد، چون متغیر مخصوص کتابخانه اولویت دارد. (خود backtrace را نچسباندم: بلند است و فریم‌هایش بین build‌ها فرق می‌کند.)

## یک جا برای نگاشت خطا به کد وضعیت

این نسخه‌ی Rust از تابع `statusOf` در مقاله‌ی Go است. خطای دارای نوع در یک جا `match` می‌شود: کلاینت متن ثابت می‌گیرد و زنجیره‌ی کامل به log می‌رود.

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

این هر دو crate را کنار هم می‌گذارد: `ServiceError` یک enum دارای نوع برای حالت‌هایی است که درباره‌شان تصمیم می‌گیریم و `Other(#[from] anyhow::Error)` برای هر چیز غیرمنتظره است. demo از هر نوع یک خطا می‌سازد و status و پیام کلاینت و آنچه به log می‌رود را چاپ می‌کند:

```text
404 not found   (log: order 42 not found)
422 invalid qty: must be > 0   (log: invalid qty: must be > 0)
500 internal error   (log: dial tcp 10.0.0.5:5432: connection refused)
```

کلاینتِ `500` هیچ‌وقت نشانی پایگاه داده را نمی‌فهمد؛ فقط log آن را دارد. `422` تنها حالتی است که پیام کلاینت و log یکی است، چون پیامش برای کلاینت نوشته شده.

## اشتباه‌های رایج در گزارش خطا

- **`anyhow::Error` را در API عمومی یک کتابخانه نگذارید.** فراخواننده‌ها نمی‌توانند رویش `match` کنند و فقط می‌توانند downcast کنند.
- **`{}` علت‌ها را پنهان می‌کند.** با `{:#}` یا `{:?}` log کنید، وگرنه دلیل را گم می‌کنید.
- **`err.to_string()` یک خطای ناشناخته را هرگز برای کلاینت نفرستید،** همان‌طور که نگاشت status بالا از آن پرهیز می‌کند. ممکن است نشانی، query یا مسیر فایل داخلش باشد.
- **پیامی که source را هم در خودش دارد و هم به‌عنوان `source()` نشان می‌دهد آن را دو بار چاپ می‌کند** در `{:#}`، همان‌طور که دیدیم.
- **`with_context` با closure را ترجیح بدهید** وقتی ساختن پیام هزینه دارد، تا رشته در مسیر موفق ساخته نشود.

## تمرین

۱. یک variant ‏`Forbidden` به `ServiceError` اضافه کنید و آن را به ۴۰۳ نگاشت کنید.
۲. در `chain` یک لایه‌ی سوم `.context(...)` اضافه کنید و `{:#}` را با `{:?}` مقایسه کنید.
۳. تابعی بنویسید که یک `anyhow::Error` می‌گیرد و اگر `AppError::NotFound` داخلش باشد ۴۰۴ برمی‌گرداند، با `downcast_ref`.

## قدم بعدی

خطا جایی بیشترین اهمیت را دارد که پیام‌ها می‌توانند شکست بخورند و دوباره تحویل شوند. مقاله‌ی بعد، «کلاینت async NATS JetStream در Rust»، این خطاها را به کار می‌گیرد: worker آن با یک enum کوچک `thiserror` تصمیم می‌گیرد پیامِ شکست‌خورده دوباره تحویل شود یا کنار گذاشته شود.
