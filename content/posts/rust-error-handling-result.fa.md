+++
date = '2026-12-02T10:00:00+03:30'
draft = false
title = 'مدیریت خطا با Result و Option در Rust'
description = 'مدیریت خطا در Rust در عمل: Result و Option، تفاوت unwrap و expect، عملگر ?، map و and_then، نوع خطای سفارشی با From و برگرداندن Result از main.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "errors", "result", "option"]
cover = { image = "/images/covers/rust-error-handling-result.fa.png", alt = "مدیریت خطا با Result و Option در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-collections-strings/) با `Vec`، `HashMap` و رشته‌ها کار کردیم. چند متد آن‌ها `Option` برمی‌گرداند و parse کردن یک رشته `Result` برمی‌گرداند. این مقاله درباره‌ی همین دو نوع است و اینکه کد Rust چطور با شکست کنار می‌آید. مثل Go، در Rust هم استثنا (exception) نداریم، اما خطا یک مقدار برگشتیِ دوم هم نیست: بخشی از نوعِ مقدار برگشتی است و نمی‌شود فراموشش کرد.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## Option و Result

```rust
enum Option<T> { Some(T), None }
enum Result<T, E> { Ok(T), Err(E) }
```

`Option<T>` یعنی «یک مقدار یا هیچ»، مثلاً `v.first()` روی یک `Vec` خالی. `Result<T, E>` یعنی «یک مقدار یا خطایی که توضیح می‌دهد چه شد»، مثلاً `"abc".parse::<i32>()`. هر دو enum معمولی هستند و با `match`، `if let` یا متدهای کمکیِ پایین کارشان می‌کنید. اگر یک `Result` را بدون استفاده رها کنید، کامپایلر هشدار می‌دهد.

## unwrap و expect

سریع‌ترین راه این است که مقدار را بگیرید و اگر نبود **panic** کنید:

```rust
let ok: i32 = "42".parse().unwrap();
let n: i32 = "abc".parse().expect("port must be a number");
```

```text
ok = 42

thread 'main' panicked at src/bin/unwrap_panic.rs:4:32:
port must be a number: ParseIntError { kind: InvalidDigit }
```

برنامه با کد خروج 101 تمام می‌شود. برای `Option`، فراخوانیِ `unwrap()` روی `None` با پیام ``called `Option::unwrap()` on a `None` value`` panic می‌کند. `expect` همین کار را با پیام خودتان می‌کند و برای همین آن را به `unwrap` خالی ترجیح می‌دهم. هر دو را در تست، آزمایش سریع، و جاهایی که شکست واقعاً یعنی باگ استفاده کنید. برای ورودیِ بیرون از برنامه، خطا را مدیریت کنید.

## عملگر ?

نوشتن `match` در هر قدم شلوغ است. **عملگر `?`** مقدار `Ok` را باز می‌کند و ادامه می‌دهد، یا همان `Err` را فوراً از تابع فعلی برمی‌گرداند. معادل Rust برای `if err != nil { return err }` است:

```rust
fn parse_and_double(s: &str) -> Result<i32, std::num::ParseIntError> {
    let n = s.trim().parse::<i32>()?;
    Ok(n * 2)
}
```

`?` فقط در تابعی کار می‌کند که نوع برگشتی‌اش جای آن خطا را داشته باشد (`Result`، یا `Option` برای مقدارهای `Option`). استفاده از آن در یک `fn main()` ساده کامپایل نمی‌شود:

```text
error[E0277]: the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`)
 --> examples/question_in_unit_main.rs:2:30
  |
1 | fn main() {
  | --------- this function should return `Result` or `Option` to accept `?`
2 |     let n: i32 = "42".parse()?;
  |                              ^ cannot use the `?` operator in a function that returns `()`
```

## Combinatorها

اغلب می‌خواهید مقدار را بدون باز کردنش تبدیل کنید. این را اجرا کردم:

```rust
let doubled = "21".parse::<i32>().map(|n| n * 2);
let r = "x".parse::<i32>().map_err(|e| format!("bad number: {e}"));
let first = empty.first().ok_or("empty list");        // Option -> Result
let r = "10".parse::<i32>().ok().and_then(|n| n.checked_div(0));
let a = "oops".parse::<i32>().unwrap_or(0);
let b = "oops".parse::<i32>().unwrap_or_else(|e| { println!("fallback because: {e}"); -1 });
```

```text
Ok(42)
Err("bad number: invalid digit found in string")
Err("empty list")
None
fallback because: invalid digit found in string
0 -1
```

`map` مقدار `Ok` را عوض می‌کند، `map_err` خطا را، `ok_or` یک `Option` را به `Result` تبدیل می‌کند و `and_then` قدمی را زنجیر می‌کند که خودش می‌تواند شکست بخورد. `unwrap_or` یک مقدار پیش‌فرض می‌دهد و `unwrap_or_else` آن را فقط در صورت نیاز حساب می‌کند.

## نوع خطای خودتان و From

یک برنامه‌ی واقعی خطاهای منابع مختلف را قاطی می‌کند. یک enum تعریف کنید، `Display` و `std::error::Error` را پیاده کنید و یک `From` اضافه کنید. همین آخری باعث می‌شود `?` خطاها را خودکار تبدیل کند:

```rust
#[derive(Debug)]
enum AppError {
    Parse(ParseIntError),
    DivideByZero,
}

impl fmt::Display for AppError { /* match self and write! a message */ }
impl std::error::Error for AppError {}

impl From<ParseIntError> for AppError {
    fn from(e: ParseIntError) -> Self { AppError::Parse(e) }
}

fn divide(a: &str, b: &str) -> Result<i32, AppError> {
    let x: i32 = a.trim().parse()?; // ParseIntError becomes AppError via From
    let y: i32 = b.trim().parse()?;
    if y == 0 { return Err(AppError::DivideByZero); }
    Ok(x / y)
}
```

## main هم می‌تواند Result برگرداند

`main` می‌تواند `Result<(), E>` برگرداند، به شرطی که `E` پیاده‌سازی `Debug` داشته باشد. با `Box<dyn Error>` هر نوع خطایی جا می‌شود:

```rust
fn main() -> Result<(), Box<dyn Error>> {
    println!("starting");
    let n: i32 = "abc".parse()?;
    println!("n = {n}");
    Ok(())
}
```

```text
starting
Error: ParseIntError { kind: InvalidDigit }
```

خطا با قالب `Debug` روی stderr چاپ می‌شود و کد خروج 1 است (با `echo $?` بررسی کردم). برای یک اسکریپت خوب است، ولی چیزی نیست که کاربر یک ابزار واقعی ببیند.

## همان مسئله‌ی مقاله‌ی Go

در [مقاله‌ی Go](/fa/posts/go-functions-defer-errors/) دو عدد را parse کردیم و تقسیم‌شان کردیم. نسخه‌ی Rust اینجاست، با خطایی که ورودی مشکل‌دار را نگه می‌دارد و خطای اصلی را از طریق `source()` در دسترس می‌گذارد:

```rust
enum DivideError {
    Parse { input: String, source: ParseIntError },
    DivideByZero,
}

fn parse(s: &str) -> Result<i32, DivideError> {
    s.trim().parse::<i32>().map_err(|e| DivideError::Parse {
        input: s.to_string(),
        source: e,
    })
}
```

تابع `divide` اول `parse(a)?` و `parse(b)?` را صدا می‌زند و بعد صفر را چک می‌کند. اجرا روی چهار ورودی:

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

برای اینکه بفهمیم کدام خطا رخ داده، به‌جای `errors.Is`/`errors.As` یک `match` یا `matches!` روی enum می‌زنیم.

## مقایسه با Go

هر دو زبان خطا را مقدار می‌دانند و شما را مجبور می‌کنند نزدیک محل فراخوانی با آن کار کنید. در Go خطا یک مقدار برگشتیِ جداست که با `_` می‌شود دورش ریخت و کامپایلر اعتراضی نمی‌کند. در Rust خودِ `Result` مقدار برگشتی است، پس برای رسیدن به داده باید آن را باز کنید (یا `?` بزنید)، و سمت `Err` یک نوع مشخص است که می‌شود روی آن `match` کامل نوشت. `?` جای خط‌های تکراریِ `if err != nil { return err }` را می‌گیرد. هزینه‌اش این است که نوع خطا و `From` را خودتان می‌نویسید، یعنی کد اولیه‌ی بیشتر.

## چند نکته

- `unwrap` در کتاب‌خانه یا سرور، ورودی بد را به crash تبدیل می‌کند. فقط برای حالت‌های واقعاً غیرممکن.
- `?` خطا را با `From` تبدیل می‌کند. اگر برای آن جفت نوع `From` نباشد، خطای کامپایل می‌گیرید، نه یک غافلگیری در زمان اجرا.
- `Box<dyn Error>` راحت است ولی نوع مشخص را پنهان می‌کند. برای کتاب‌خانه، یک enum اختصاصی برای فراخواننده‌ها بهتر است.
- خطایی که از `main` برمی‌گردد با `Debug` چاپ می‌شود، نه `Display`. اگر پیام تمیزتر می‌خواهید، خطا را خودتان در `main` مدیریت کنید.
- وقتی می‌خواهید context اضافه کنید از `map_err` استفاده کنید، مثل رشته‌ی ورودی در `DivideError::Parse`.

## تمرین

1. یک variant به نام `Negative` به `DivideError` اضافه کنید و وقتی یکی از عملوندها منفی بود آن را برگردانید.
2. تابع `fn average(nums: &[f64]) -> Option<f64>` را بنویسید که برای slice خالی `None` برگرداند، و با `ok_or` آن را به `Result<f64, String>` تبدیل کنید.
3. در مثال `Box<dyn Error>`، خطا را در خود `main` با `match` مدیریت کنید و به‌جای `{:?}` با `{}` چاپش کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ ماژول‌ها، crateها و Cargo در Rust می‌رویم: اینکه کد را بین فایل‌ها تقسیم کنیم، از crateهای بیرونی استفاده کنیم و پروژه را مدیریت کنیم.
