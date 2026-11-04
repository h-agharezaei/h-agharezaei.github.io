+++
date = '2026-12-02T10:00:00+03:30'
draft = false
title = 'مدیریت خطا با Result و Option در Rust'
description = 'مدیریت خطا در Rust در عمل: Result و Option، تفاوت unwrap و expect، عملگر ?، map و and_then، نوع خطای سفارشی با From و برگرداندن Result از main.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "errors", "result", "option"]
cover = { image = "/images/covers/rust-error-handling-result.fa.png", alt = "مدیریت خطا با Result و Option در Rust", hiddenInSingle = true }
+++

فرض کنید تابعی دارید که یک رشته مثل `"8080"` را می‌گیرد و شماره‌ی پورت برمی‌گرداند. ورودی `"abc"` باشد چه؟ زبان‌ها جواب‌های مختلفی داده‌اند. بعضی استثنا (exception) پرتاب می‌کنند و باید یادتان باشد جایی آن را بگیرید. بعضی `null` یا عدد جادویی مثل `-1` برمی‌گردانند و باید یادتان باشد بررسی‌اش کنید. Go خطا را به‌صورت یک مقدار برگشتیِ دوم می‌دهد که می‌شود با `_` نادیده‌اش گرفت. Rust راه دیگری رفته است: امکان شکست را در **نوعِ** مقدار برگشتی می‌گذارد. اگر تابع ممکن است شکست بخورد، نوع برگشتی‌اش به‌جای «یک عدد» می‌شود «یک عدد، یا یک خطا»، و تا آن را باز نکنید به عدد دست نمی‌رسید.

در [مقاله‌ی قبل](/fa/posts/rust-collections-strings/) چند بار به این رسیدیم: `v.get(9)` و `ages.get("nobody")` هر دو یک `Option` برمی‌گرداندند، و parse کردن یک رشته به عدد `Result` برمی‌گرداند. این مقاله درباره‌ی همین دو نوع و ابزارهایی است که کار با آن‌ها را راحت می‌کنند. اگر از Go می‌آیید، همه‌چیز را با [توابع، defer و مدیریت خطا در Go](/fa/posts/go-functions-defer-errors/) مقایسه می‌کنیم.

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. از پیام خطای عملگر `?` چند خط راهنمای جانبی و خط «For more information…» را حذف کرده‌ام. یک برنامه‌ی کوچک هم نوشتم و اجرا کردم که فقط برای نشان‌دادن کار `?` با دست است.

## Option و Result

هر دو نوع در کتاب‌خانه‌ی استاندارد تعریف شده‌اند و enum‌های معمولی‌اند، همان enumهایی که در مقاله‌ی struct و enum دیدیم:

```rust
enum Option<T> { Some(T), None }
enum Result<T, E> { Ok(T), Err(E) }
```

`Option<T>` یعنی «یا یک مقدار از نوع `T`، یا هیچ». مثلاً `v.first()` روی یک `Vec` خالی `None` برمی‌گرداند. `Result<T, E>` یعنی «یا یک مقدار از نوع `T`، یا خطایی از نوع `E` که می‌گوید چه شد». مثلاً `"abc".parse::<i32>()` یک `Err` می‌دهد. این‌ها جای `null` و استثنا را در Rust می‌گیرند و چون نوع‌اند، کامپایلر مطمئن می‌شود هر دو حالت را در نظر گرفته‌اید.

ساده‌ترین راه کار با آن‌ها همان `match` است:

```rust
let empty: Vec<i32> = Vec::new();
match empty.first() {
    Some(n) => println!("first = {n}"),
    None => println!("empty list"),
}
```

(این را در یک برنامه‌ی کوچک جدا اجرا کردم و برای فهرست خالی `empty list` چاپ شد.) وقتی فقط به یک حالت علاقه دارید، `if let Some(n) = ...` کوتاه‌تر است؛ برای `[5, 6]` این شکل `first = 5` چاپ کرد. اگر یک `Result` را بدون استفاده رها کنید، کامپایلر هشدار می‌دهد، پس نادیده‌گرفتن خطا بی‌سروصدا اتفاق نمی‌افتد.

## unwrap و expect: وقتی شکست یعنی باگ

گاهی می‌دانید که مقدار حتماً هست، یا شکست در آن نقطه واقعاً یعنی برنامه اشتباه نوشته شده. آن‌وقت لازم نیست `match` بنویسید. `unwrap()` مقدار داخل `Ok` یا `Some` را بیرون می‌دهد و اگر `Err` یا `None` بود برنامه را با **panic** متوقف می‌کند. `expect("...")` همین کار را با پیامی که خودتان می‌نویسید انجام می‌دهد:

```rust
let ok: i32 = "42".parse().unwrap();
println!("ok = {ok}");
let n: i32 = "abc".parse().expect("port must be a number");
println!("n = {n}");
```

```text
ok = 42

thread 'main' panicked at src/bin/unwrap_panic.rs:4:32:
port must be a number: ParseIntError { kind: InvalidDigit }
```

خط اول همان `"42"` است که درست parse شد. بعد `"abc"` شکست می‌خورد، برنامه با پیام ما و خطای اصلی متوقف می‌شود، و کد خروج 101 است (اجرا و بررسی کردم). برای `Option` هم همین است: `unwrap()` روی `None` با پیام ``called `Option::unwrap()` on a `None` value`` panic می‌کند. من `expect` را به `unwrap` خالی ترجیح می‌دهم، چون وقتی بعداً panic را در لاگ می‌بینید، پیام می‌گوید چه انتظاری داشتیم. هر دو را در تست، آزمایش سریع و جاهایی که شکست واقعاً باگ است به کار ببرید. برای ورودی‌ای که از بیرون برنامه می‌آید، خطا را مدیریت کنید.

## عملگر ?

مدیریت خطا با `match` در هر قدم، کد را شلوغ می‌کند. فرض کنید تابعی دارید که یک رشته را به عدد تبدیل و دو برابر می‌کند. اگر تبدیل شکست خورد، می‌خواهیم خود همان خطا را به فراخواننده برگردانیم. با دست این‌طور نوشته می‌شود:

```rust
fn by_hand(s: &str) -> Result<i32, ParseIntError> {
    let n = match s.trim().parse::<i32>() {
        Ok(n) => n,
        Err(e) => return Err(e),
    };
    Ok(n * 2)
}
```

یعنی: اگر `Ok` بود مقدارش را بردار و ادامه بده، اگر `Err` بود همان‌جا از تابع برگرد و خطا را با خودت ببر. این الگو آن‌قدر تکراری است که Rust برایش علامت دارد: **عملگر `?`**. این یکی دقیقاً همان کار را می‌کند:

```rust
fn with_question(s: &str) -> Result<i32, ParseIntError> {
    let n = s.trim().parse::<i32>()?;
    Ok(n * 2)
}
```

هر دو تابع را با `"21"` و `"x"` صدا زدم تا مطمئن شوم یک‌جور رفتار می‌کنند:

```text
Ok(42) Ok(42)
Err(ParseIntError { kind: InvalidDigit }) Err(ParseIntError { kind: InvalidDigit })
```

خط اول نتیجه‌ی `with_question` و `by_hand` برای `"21"` است و خط دوم برای `"x"`، و در هر دو حالت یکی‌اند. (در عمل `?` یک کار کوچک دیگر هم می‌کند: خطا را با `From` به نوع خطای تابع تبدیل می‌کند، که چند بخش بعد می‌بینیم.) `?` همان کاری است که در Go با `if err != nil { return err }` می‌کنید، فقط یک علامت.

از آنجا که `?` یعنی «از تابع برگرد»، فقط در تابعی کار می‌کند که نوع برگشتی‌اش بتواند آن خطا را بپذیرد: `Result`، یا `Option` برای مقدارهای `Option`. اگر در `fn main()` ساده که چیزی برنمی‌گرداند استفاده‌اش کنید:

```text
error[E0277]: the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`)
 --> examples/question_in_unit_main.rs:2:30
  |
1 | fn main() {
  | --------- this function should return `Result` or `Option` to accept `?`
2 |     let n: i32 = "42".parse()?;
  |                              ^ cannot use the `?` operator in a function that returns `()`
```

پیام دقیقاً همین را می‌گوید: تابع `()` برمی‌گرداند و جایی برای خطا ندارد. (کامپایلر یک پیشنهاد هم می‌دهد که نوع برگشتی `main` را عوض کنید؛ آن را در بخش `main` می‌بینیم.)

## Combinatorها: تبدیل بدون باز کردن

همیشه نمی‌خواهید مقدار را باز کنید. گاهی فقط می‌خواهید آن را تبدیل کنید و `Result` یا `Option` بودنش بماند. چند متد برای این کار هست. هر خط برنامه‌ی زیر یکی را نشان می‌دهد:

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

(`|n| n * 2` یک تابع کوچک بی‌نام است؛ به آن closure می‌گویند و در مقاله‌های بعد بیشتر درباره‌اش می‌گویم.) هر خط خروجی مال یک خط کد است:

- `map` مقدار داخل `Ok` را عوض می‌کند: `21` دو برابر می‌شود و `Ok(42)` می‌ماند.
- `map_err` فقط خطا را عوض می‌کند. اینجا خطای parse را به یک متن با پیام خودمان تبدیل کردیم.
- `ok_or` یک `Option` را به `Result` تبدیل می‌کند. فهرست خالی `None` می‌دهد و ما آن را به `Err("empty list")` تبدیل می‌کنیم.
- `and_then` قدمی را زنجیر می‌کند که خودش هم می‌تواند شکست بخورد. اینجا `"10"` درست parse می‌شود، ولی `checked_div(0)` (تقسیم با بررسی صفر) `None` می‌دهد و نتیجه `None` می‌شود.
- `unwrap_or(0)` اگر شکست خورد یک مقدار پیش‌فرض می‌دهد. `unwrap_or_else` همین است ولی مقدار پیش‌فرض را با یک تابع می‌سازد که فقط در صورت شکست اجرا می‌شود؛ اینجا شکست خورد، برای همین پیام `fallback because...` چاپ شد و `-1` برگشت. خط آخر `0 -1` است: مقدار `a` و `b`.

## نوع خطای خودتان و From

تا اینجا خطاها از کتاب‌خانه‌ی استاندارد بودند. یک برنامه‌ی واقعی خطاهای چند منبع را قاطی می‌کند: parse، فایل، شبکه. راه معمول این است که یک enum برای خطاهای برنامه‌ی خودتان تعریف کنید، که هر variant یک نوع شکست است. دو {{< term "trait" "trait" >}} هم باید برایش پیاده کنید. trait یعنی مجموعه‌ای از متدها که یک نوع قول می‌دهد داشته باشد؛ در مقاله‌ی generic و trait دقیق‌تر می‌بینیم. اینجا فقط لازم است بدانید `Display` می‌گوید خطا چطور به متن تبدیل شود و `Error` علامتی است که می‌گوید این نوع یک خطا است. نوع سوم، `From`، چیز جالب‌تری دارد: به Rust می‌گوید یک `ParseIntError` را چطور به `AppError` تبدیل کند، و `?` از همین استفاده می‌کند.

```rust
#[derive(Debug)]
enum AppError {
    Parse(ParseIntError),
    DivideByZero,
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            AppError::Parse(e) => write!(f, "parse error: {e}"),
            AppError::DivideByZero => write!(f, "divide by zero"),
        }
    }
}

impl std::error::Error for AppError {}

impl From<ParseIntError> for AppError {
    fn from(e: ParseIntError) -> Self {
        AppError::Parse(e)
    }
}

fn divide(a: &str, b: &str) -> Result<i32, AppError> {
    let x: i32 = a.trim().parse()?; // ParseIntError -> AppError via From
    let y: i32 = b.trim().parse()?;
    if y == 0 {
        return Err(AppError::DivideByZero);
    }
    Ok(x / y)
}
```

دقت کنید `divide` نوع `Result<i32, AppError>` برمی‌گرداند ولی `parse()` یک `ParseIntError` تولید می‌کند. بدون `From` این یک خطای کامپایل بود. با `From`، علامت `?` هنگام برگشتن خطا آن را خودکار از `ParseIntError` به `AppError` تبدیل می‌کند. برنامه‌ی کامل چهار فراخوانی دارد، که آخری را با `?` از `main` خارج می‌کند:

```text
Ok(42)
Err(DivideByZero)
Err("parse error: invalid digit found in string")
Error: Parse(ParseIntError { kind: InvalidDigit })
```

سه خط اول از `println!` می‌آیند: تقسیم درست (`84 / 2`)، تقسیم بر صفر، و ورودی خراب که خطایش با `to_string()` (یعنی همان `Display` ما) به متن تبدیل شده. خط آخر وقتی چاپ می‌شود که فراخوانی چهارم شکست می‌خورد و `?` خطا را از `main` بیرون می‌دهد. این همان بخش بعدی است.

## main هم می‌تواند Result برگرداند

`main` می‌تواند `Result<(), E>` برگرداند، به شرط اینکه `E` پیاده‌سازی `Debug` داشته باشد. اگر `Err` برگردد، برنامه خطا را چاپ می‌کند و با کد خروج غیرصفر تمام می‌شود. با `Box<dyn Error>` که یعنی «هر نوع خطایی» هر خطایی در آن جا می‌شود:

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

بعد از `starting` شکست می‌خوریم و `?` خطا را از `main` برمی‌گرداند، پس خط `n = ...` هرگز اجرا نمی‌شود. خطا با قالب `Debug` روی stderr چاپ می‌شود (برای همین `Error: ParseIntError { kind: ... }` می‌بینیم و نه یک جمله‌ی خوانا) و کد خروج 1 است (با `echo $?` بررسی کردم). برای یک اسکریپت خوب است، ولی چیزی نیست که بخواهید به کاربر یک ابزار واقعی نشان بدهید.

## همان مسئله‌ی مقاله‌ی Go

در [مقاله‌ی Go](/fa/posts/go-functions-defer-errors/) دو رشته را به عدد تبدیل کردیم و تقسیم‌شان کردیم. نسخه‌ی Rust همان است، با دو تفاوت. خطا ورودی مشکل‌دار را در خودش نگه می‌دارد، و خطای اصلی را از طریق `source()` در دسترس می‌گذارد (معادل زنجیره‌ی `%w` و `Unwrap` در Go):

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

`divide` اول `parse(a)?` و `parse(b)?` را صدا می‌زند و بعد صفر را بررسی می‌کند. (پیاده‌سازی `Display` و `Error` مثل مثال قبل است و کد کامل در همان مثال محلی هست.) اجرا روی چهار ورودی:

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

ورودی‌ها `("84","2")`، `("10","0")`، `("abc","2")` و `("7"," x1")` بودند. اولی ۴۲ می‌دهد. دومی `DivideByZero` است و چون علتی ندارد، خط `caused by` چاپ نشده. دو ورودی آخر خطای parse هستند: پیام ورودی خراب را (با گیومه، پس فاصله‌ی ابتدای `" x1"` هم دیده می‌شود) نشان می‌دهد و خط `caused by` همان خطای اصلی است که با `source()` گرفتیم. برای اینکه بفهمیم کدام نوع خطا رخ داده، به‌جای `errors.Is` و `errors.As` در Go، یک `match` یا `matches!` روی enum می‌نویسیم؛ آخرین خط هر بلوک همین را نشان می‌دهد.

## مقایسه با Go

هر دو زبان خطا را مقدار می‌دانند و شما را مجبور می‌کنند نزدیک محل فراخوانی با آن کار کنید. در Go خطا یک مقدار برگشتیِ جداست که با `_` می‌شود دورش ریخت و کامپایلر اعتراضی نمی‌کند. در Rust خودِ `Result` مقدار برگشتی است، پس برای رسیدن به داده باید آن را باز کنید (یا `?` بزنید)، و سمت `Err` یک نوع مشخص است که می‌شود روی آن `match` کامل نوشت. `?` جای خط‌های تکراریِ `if err != nil { return err }` را می‌گیرد. هزینه‌اش این است که نوع خطا و `From` را خودتان می‌نویسید، یعنی کد اولیه‌ی بیشتر.

## جاهایی که مدیریت خطا خراب می‌شود

- `unwrap` در کتاب‌خانه یا سرور، ورودی بد را به crash تبدیل می‌کند. آن را فقط برای حالت‌هایی نگه دارید که واقعاً غیرممکن‌اند.
- `?` خطا را با `From` تبدیل می‌کند. اگر برای آن جفت نوع `From` نباشد، خطای کامپایل می‌گیرید، نه یک غافلگیری در زمان اجرا.
- `Box<dyn Error>` راحت است ولی نوع مشخص خطا را پنهان می‌کند و فراخواننده نمی‌تواند روی آن `match` کند. برای کتاب‌خانه، یک enum اختصاصی بهتر است.
- خطایی که از `main` برمی‌گردد با `Debug` چاپ می‌شود، نه `Display`. اگر پیام تمیزتر می‌خواهید، خطا را خودتان در `main` مدیریت کنید.
- وقتی می‌خواهید زمینه (context) اضافه کنید از `map_err` استفاده کنید، مثل رشته‌ی ورودی که در `DivideError::Parse` نگه داشتیم.

## تمرین

1. یک variant به نام `Negative` به `DivideError` اضافه کنید و وقتی یکی از عملوندها منفی بود آن را برگردانید.
2. تابع `fn average(nums: &[f64]) -> Option<f64>` را بنویسید که برای slice خالی `None` برگرداند، و با `ok_or` آن را به `Result<f64, String>` تبدیل کنید.
3. در مثال `Box<dyn Error>`، خطا را در خود `main` با `match` مدیریت کنید و به‌جای `{:?}` با `{}` چاپش کنید.

## قدم بعدی

وقتی برنامه بزرگ‌تر می‌شود، `DivideError` و `parse` و `main` دیگر در یک فایل نمی‌گنجند. برای همین قدم بعدی «Module، Crate و Cargo در Rust» است: تقسیم کد بین فایل‌ها و crateها.
