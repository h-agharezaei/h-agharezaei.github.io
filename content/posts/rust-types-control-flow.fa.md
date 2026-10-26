+++
date = '2026-11-02T10:00:00+03:30'
draft = false
title = 'نوع‌ها، متغیرها و کنترل جریان در Rust'
description = 'متغیرهای پیش‌فرض immutable، shadowing، نوع‌های اسکالر، tuple و array، سرریز عدد صحیح و if و loop و while و for و match در Rust، با مقایسه با Go.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/rust-types-control-flow.fa.png", alt = "نوع‌ها، متغیرها و کنترل جریان در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-getting-started/) Rust را نصب کردیم، با Cargo آشنا شدیم و اولین برنامه را اجرا کردیم. حالا به واژگان پایه نیاز داریم: متغیر چطور تعریف می‌شود، چه نوع‌هایی داریم و چطور شرط و حلقه بنویسیم. اگر از Go آمده باشی بیشترش آشناست، ولی چند پیش‌فرض دقیقاً برعکس چیزی است که انتظار داری.

> همه‌ی کدهای زیر را با Rust 1.90 (`rustc 1.90.0`) کامپایل و اجرا کرده‌ام و خروجی‌ها واقعی‌اند.

## متغیرها به‌طور پیش‌فرض immutable هستند

در Rust دستور `let` یک binding تغییرناپذیر می‌سازد. دوباره مقدار دادن به آن خطای کامپایل است:

```rust
fn main() {
    let x = 5;
    x = 6;
    println!("{x}");
}
```

```text
error[E0384]: cannot assign twice to immutable variable `x`
 --> src/bin/immut.rs:3:5
  |
2 |     let x = 5;
  |         - first assignment to `x`
3 |     x = 6;
  |     ^^^^^ cannot assign twice to immutable variable
  |
help: consider making this binding mutable
  |
2 |     let mut x = 5;
  |         +++
```

اگر واقعاً می‌خواهی تغییر کند، باید با `mut` صریحاً بگویی. در Go هر متغیری قابل تغییر است؛ در Rust باید خودت این اجازه را بدهی و خواننده یک‌نگاه می‌فهمد چه چیزی ممکن است عوض شود.

## Shadowing با تغییر مقدار فرق دارد

می‌توانی با `let` دوباره متغیری هم‌نام تعریف کنی. به این کار **shadowing** می‌گویند و یک متغیر کاملاً جدید می‌سازد، پس حتی می‌تواند نوع دیگری داشته باشد:

```rust
let spaces = "   ";
let spaces = spaces.len(); // a new variable, now a usize
let mut count = 0;
count += 1;                // the same variable, mutated
```

تغییر مقدار (mutation) نوع را ثابت نگه می‌دارد. این کد کامپایل نمی‌شود:

```rust
let mut s = "abc";
s = 5;
```

```text
error[E0308]: mismatched types
11 |     s = 5;
   |         ^ expected `&str`, found integer
```

## نوع‌های اسکالر، tuple و array

نوع‌های اسکالری که بیشتر استفاده می‌کنی: عدد صحیح علامت‌دار از `i8` تا `i128` و `isize`، بدون علامت از `u8` تا `u128` و `usize`، اعشاری `f32` و `f64`، `bool` و `char`. نوع `char` یک Unicode scalar value است، پس ۴ بایت جا می‌گیرد و می‌تواند `'ز'` را نگه دارد.

```rust
const MAX_POINTS: u32 = 100_000;

fn main() {
    let a = 42;           // inferred as i32
    let b: u64 = 10_000_000_000;
    let c = 2.5;          // inferred as f64
    let ch = 'ز';
    let t: (i32, f64, char) = (1, 2.5, 'x');
    let (x, y, z) = t;    // destructuring
    let arr = [10, 20, 30];
    let zeros = [0u8; 4]; // four zeros
    println!("{} {} {:?} {:?}", t.0, arr.len(), arr, zeros);
    let n: i32 = "42".parse().unwrap(); // annotation needed here
    println!("{}", n + a);
}
```

خروجی (کوتاه‌شده):

```text
1 3 [10, 20, 30] [0, 0, 0, 0]
84
```

نکته‌ها:

- Rust نوع را حدس می‌زند؛ عدد صحیح به‌طور پیش‌فرض `i32` و اعشاری `f64` است. وقتی حدس ممکن نیست، مثل `parse()` بالا، نوع را صریح می‌نویسیم.
- **Tuple** طول ثابت و نوع‌های مختلط دارد؛ **array** طول ثابت و فقط یک نوع. برای فهرست قابل رشد بعداً سراغ `Vec` می‌رویم.
- `const` همیشه نوع صریح می‌خواهد، مقدارش باید در زمان کامپایل مشخص باشد و `mut` نمی‌شود.
- تبدیل ضمنی بین نوع‌های عددی وجود ندارد. جمع `i32` با `i64` خطای `cannot add i64 to i32` می‌دهد؛ با `as` یا `i64::from(a)` تبدیل کن. Go هم در این مورد همین‌طور است.

## سرریز عدد صحیح

همین برنامه را با یک `u8` برابر ۲۵۵ و جمع با ۱ اجرا کردم:

```rust
let n: u8 = std::env::args().nth(1).unwrap().parse().unwrap();
let m = n + 1;
```

```text
$ cargo run -q --bin overflow 255
thread 'main' panicked at src/bin/overflow.rs:3:13:
attempt to add with overflow

$ cargo run -q --release --bin overflow 255
0
```

build حالت debug با panic متوقف می‌شود، ولی build حالت `--release` بی‌صدا به ۰ برمی‌گردد (wrap). چون این تفاوت راحت دردسر می‌سازد، منظورت را صریح بنویس: `checked_add` یک `Option` برمی‌گرداند، `wrapping_add` دور می‌زند و `saturating_add` روی ۲۵۵ می‌ایستد. در Go سرریز همیشه بی‌صدا wrap می‌شود.

## Statement و expression

تقریباً همه‌چیز در Rust یک expression است. آخرین expressionِ یک بلاک، بدون سمی‌کالن، مقدار آن بلاک است:

```rust
fn square(x: i32) -> i32 {
    x * x
}
```

اگر سمی‌کالن بگذاری statement می‌شود که `()` برمی‌گرداند:

```text
error[E0308]: mismatched types
1 | fn square(x: i32) -> i32 {
  |    ------            ^^^ expected `i32`, found `()`
2 |     x * x;
  |          - help: remove this semicolon to return this value
```

## کنترل جریان

`if` یک expression است و جای عملگر سه‌تایی را که در Go نیست پر می‌کند. شرط باید واقعاً `bool` باشد (`if n {}` با عدد صحیح کامپایل نمی‌شود) و هر دو شاخه باید نوع یکسان داشته باشند:

```rust
let kind = if n % 2 == 0 { "even" } else { "odd" };
```

`loop` تا `break` بی‌نهایت اجرا می‌شود و `break` می‌تواند مقدار برگرداند:

```rust
let found = loop {
    tries += 1;
    if tries * tries > 50 { break tries; }
};
```

`while` همان حلقه‌ی شرطی معمولی است. `for` روی هر چیز قابل پیمایش کار می‌کند و `for` سه‌قسمتیِ سبک C وجود ندارد:

```rust
for i in 1..4 {}            // 1 2 3
for i in 1..=4 {}           // 1 2 3 4
for i in (1..4).rev() {}    // 3 2 1
for (i, name) in names.iter().enumerate() {}
```

`match` یک مقدار را با الگوها مقایسه می‌کند. اینجا فقط یک نمونه می‌بینی؛ pattern matching بعداً مقاله‌ی جدا دارد:

```rust
let msg = match code {
    200 => "ok",
    404 => "not found",
    500..=599 => "server error",
    _ => "other",
};
```

کامپایلر `match` را موظف می‌کند همه‌ی حالت‌ها را پوشش دهد، برای همین شاخه‌ی `_` هست.

## کنار هم گذاشتن

یک برنامه‌ی کوچک با جدول دما و FizzBuzz:

```rust
fn main() {
    println!("   C      F");
    for c in (-10..=40).step_by(10) {
        let f = c as f64 * 9.0 / 5.0 + 32.0;
        let note = match c {
            i32::MIN..=-1 => "freezing",
            0..=24 => "mild",
            _ => "hot",
        };
        println!("{c:>4} {f:>6.1}  {note}");
    }
    for i in 1..=15 {
        let s = if i % 15 == 0 { "FizzBuzz".to_string() }
            else if i % 3 == 0 { "Fizz".to_string() }
            else if i % 5 == 0 { "Buzz".to_string() }
            else { i.to_string() };
        print!("{s} ");
    }
    println!();
}
```

```text
   C      F
 -10   14.0  freezing
   0   32.0  mild
  10   50.0  mild
  20   68.0  mild
  30   86.0  hot
  40  104.0  hot
1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz
```

## چند نکته‌ی مهم

- سمی‌کالنِ آخر تابع خطای کلاسیک مبتدی‌هاست؛ پیام کامپایلر مستقیم به همان اشاره می‌کند.
- build حالت debug و release در سرریز رفتار متفاوت دارند. جایی که مهم است از `checked_*` استفاده کن.
- اندیس array در زمان اجرا بررسی می‌شود: `arr[5]` روی آرایه‌ی ۳ عضوی panic می‌دهد با پیام `index out of bounds: the len is 3 but the index is 5`.
- Shadowing برای تبدیل‌ها مفید است (`let x = x.trim();`)، ولی زیاده‌روی در آن خواندن کد را سخت می‌کند.
- `1..4` انتها را شامل نمی‌شود و `1..=4` می‌شود.

## تمرین

۱. تابع `fn is_leap(year: u32) -> bool` را فقط با یک expression و بدون `return` بنویس و سال‌های کبیسه‌ی بین ۱۹۹۰ تا ۲۰۳۰ را چاپ کن.
۲. با `loop` و `break value` اولین توان ۲ بزرگ‌تر از ۱۰۰۰ را پیدا کن.
۳. برنامه‌ی سرریز را طوری تغییر بده که نتیجه‌ی `checked_add` را برای ۲۵۰ و ۲۵۵ چاپ کند و با `wrapping_add` مقایسه کن.

## قدم بعدی

در مقاله‌ی بعد، Ownership در Rust، به ایده‌ای می‌رسیم که Rust را از Go جدا می‌کند: چه کسی مالک یک مقدار است، move یعنی چه و borrowing چطور کار می‌کند.
