+++
date = '2026-12-22T10:00:00+03:30'
draft = false
title = 'Lifetime در Rust'
description = 'مفهوم lifetime در Rust با کد قابل اجرا: تابع longest، خطاهای واقعی E0106 و E0597، قواعد elision، struct‌های دارای reference و معنای واقعی T: static.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "lifetimes", "intermediate", "borrowing"]
cover = { image = "/images/covers/rust-lifetimes.fa.png", alt = "Lifetime در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-generics-traits/) کدی نوشتیم که روی نوع‌های مختلف کار می‌کند. حالا به reference‌ها برمی‌گردیم؛ موضوعی که در [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) دیدیم و بهتر است اول آن را بخوانید. آنجا دیدیم که reference نباید بیشتر از مقدارش عمر کند و گاهی کامپایلر یک «lifetime specifier» می‌خواهد. این مقاله توضیح می‌دهد آن یعنی چه و کِی باید خودتان بنویسیدش.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و خطاها از همان اجراها کپی شده‌اند.

## Lifetime چیست

**Lifetime** اسمی است برای بخشی از کد که در آن یک reference معتبر است. فقط در زمان کامپایل وجود دارد: چیزی در باینری نیست و در runtime اتفاقی نمی‌افتد. نوشتن `'a` عمر هیچ مقداری را تغییر نمی‌دهد؛ فقط به کامپایلر می‌گوید lifetime چند reference چه نسبتی با هم دارند تا بتواند بررسی کند هیچ‌کدام بیشتر از داده‌شان زنده نمانند.

## تابع longest

تابعی که یکی از دو reference ورودی را برمی‌گرداند:

```rust
fn longest(x: &str, y: &str) -> &str {
    if x.len() >= y.len() { x } else { y }
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/missing_annotation.rs:1:33
  |
1 | fn longest(x: &str, y: &str) -> &str {
  |               ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `x` or `y`
help: consider introducing a named lifetime parameter
  |
1 | fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
  |           ++++     ++          ++          ++
```

کامپایلر نمی‌داند نتیجه از `x` می‌آید یا `y`، در حالی که صدازننده باید بداند تا کِی می‌تواند از نتیجه استفاده کند. پیشنهاد کامپایلر را اعمال می‌کنیم:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let a = String::from("salam donya");
    let b = String::from("hi");
    let result = longest(&a, &b);
    println!("longest: {result}");
}
```

```text
longest: salam donya
```

امضا را این‌طور بخوانید: «`x`، `y` و نتیجه یک lifetime مشترک به نام `'a` دارند»، که در عمل یعنی کوتاه‌ترینِ دو ورودی. معمول‌ترین راه شکستن آن این است که یکی از ورودی‌ها scope کوتاه‌تری داشته باشد:

```rust
fn main() {
    let a = String::from("salam donya");
    let result;
    {
        let b = String::from("hi");
        result = longest(&a, &b);
    }
    println!("longest: {result}");
}
```

```text
error[E0597]: `b` does not live long enough
  --> src/bin/short_lived.rs:10:30
   |
 9 |         let b = String::from("hi");
   |             - binding `b` declared here
10 |         result = longest(&a, &b);
   |                              ^^ borrowed value does not live long enough
11 |     }
   |     - `b` dropped here while still borrowed
12 |     println!("longest: {result}");
   |                         ------ borrow later used here
```

نتیجه ممکن است همان `b` باشد و `b` در آکولاد بسته drop می‌شود، در حالی که `result` بعدش هنوز استفاده می‌شود. مثل قبل به برچسب «later used here» نگاه کنید.

## Lifetime elision

لازم نیست همه‌جا lifetime بنویسید، چون کامپایلر روی امضای تابع‌ها سه قاعده‌ی **elision** اعمال می‌کند:

1. هر lifetime حذف‌شده در پارامترها، یک lifetime مستقل می‌شود.
2. اگر دقیقاً یک lifetime ورودی وجود داشته باشد، به همه‌ی lifetime‌های حذف‌شده‌ی خروجی داده می‌شود.
3. اگر چند lifetime ورودی داریم ولی یکی از آن‌ها `&self` یا `&mut self` است، lifetime مربوط به `self` به همه‌ی lifetime‌های حذف‌شده‌ی خروجی داده می‌شود.

اگر بعد از این قواعد هنوز lifetime خروجی مشخص نباشد، E0106 می‌گیرید؛ دقیقاً مثل `longest` (دو ورودی و بدون `self`). تابعی که به هیچ نوشتنی نیاز ندارد، و معادل کامل‌نوشته‌اش:

```rust
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

fn first_word_explicit<'a>(s: &'a str) -> &'a str {
    s.split(' ').next().unwrap_or("")
}
```

هر دو برای `"salam donya"` مقدار `salam` را چاپ می‌کنند. قاعده‌ی دوم اعمال می‌شود و نتیجه از ورودی قرض گرفته شده؛ برای همین برگرداندن بخشی از آن امن است.

## Struct‌هایی که reference نگه می‌دارند

struct‌ای که reference دارد به یک پارامتر lifetime نیاز دارد تا کامپایلر بداند struct نمی‌تواند بیشتر از چیزی که به آن اشاره می‌کند عمر کند:

```rust
struct Excerpt<'a> {
    part: &'a str,
}

impl<'a> Excerpt<'a> {
    // rule 3: the output gets the lifetime of &self
    fn part(&self) -> &str {
        self.part
    }
}

fn main() {
    let novel = String::from("Call me Ishmael. Some years ago...");
    let first_sentence = novel.split('.').next().unwrap();
    let e = Excerpt { part: first_sentence };
    println!("{}", e.part());
}
```

```text
Call me Ishmael
```

`impl<'a>` و `Excerpt<'a>` را می‌نویسیم چون `'a` مثل یک پارامتر generic بخشی از نوع است. اگر `Excerpt` بیشتر از `novel` عمر کند، همان E0597 قبلی را می‌گیرید (`novel` does not live long enough و هنوز borrow شده drop می‌شود).

## 'static

`'static` طولانی‌ترین lifetime است. string literal‌ها آن را دارند، چون متنشان داخل خود برنامه ذخیره شده:

```rust
let greeting: &'static str = "salam";
```

درباره‌ی قید `T: 'static` یک سوءتفاهم رایج هست. معنایش «مقدار تا ابد زنده است» نیست؛ معنایش این است که نوع، هیچ reference کوتاه‌عمرتر از `'static` ندارد. یک `String` صاحب‌دار یا یک `i32` این شرط را دارند و مثل هر مقدار دیگری drop می‌شوند:

```rust
fn takes_static<T: Debug + 'static>(value: T) { println!("got {value:?}"); }

takes_static(owned);   // String: ok
takes_static(42);      // ok
takes_static(&owned);  // a borrow of a local: error
```

```text
got "owned"
got 42
got "salam"
```

آخرین فراخوانی، در یک برنامه‌ی جدا، کامپایل نمی‌شود:

```text
error[E0597]: `owned` does not live long enough
 9 |     takes_static(&owned);
   |     -------------^^^^^^-
   |     |            |
   |     |            borrowed value does not live long enough
   |     argument requires that `owned` is borrowed for `'static`
```

برای رفع خطای lifetime سراغ `'static` نروید، مگر اینکه داده واقعاً literal یا ثابت باشد.

## وقتی با borrow checker کلنجار می‌روید

در دوره‌ی یادگیری همه‌جا lifetime را به زور جا نیندازید. اگر `Excerpt` اذیتتان کرد، یک `String` نگه دارید و یک بار `.to_string()` (یا `.clone()`) بزنید:

```rust
struct Excerpt {
    part: String, // owned: no lifetime needed
}
```

این نسخه را با همان ترفند scope داخلی که نسخه‌ی borrow‌دار را می‌شکست اجرا کردم و `Call me Ishmael` چاپ می‌کند. هزینه‌اش یک allocation است. استفاده از reference با lifetime نوعی بهینه‌سازی است؛ وقتی دلیل دارید سراغش بروید.

## چند نکته

- annotation‌های lifetime رابطه را توصیف می‌کنند و هرگز عمر مقدار را بیشتر نمی‌کنند.
- جایی که elision جواب می‌دهد چیزی ننویسید. فقط وقتی کامپایلر خواست `'a` اضافه کنید.
- تابع نمی‌تواند reference به متغیر محلی خودش را برگرداند؛ مقدار صاحب‌دار برگردانید.
- `'a` روی struct یعنی «این struct بیشتر از داده‌ی قرض‌گرفته‌شده عمر نمی‌کند».
- برچسب‌های E0597 را بخوانید: «declared here»، «dropped here» و «later used here».

## تمرین

1. تابع `fn longer_or_default<'a>(x: &'a str, default: &'static str) -> &'a str` را بنویسید که هرکدام طولانی‌تر است برگرداند. کامپایل می‌شود، چون reference با `'static` هرجا که reference کوتاه‌تر لازم باشد قابل استفاده است؛ سعی کنید دلیلش را توضیح دهید.
2. متد `fn first_word(&self) -> &str` را به `Excerpt` اضافه کنید و صدایش بزنید.
3. `Excerpt` را طوری عوض کنید که `String` داشته باشد و همه‌ی `'a`‌ها را حذف کنید.

## قدم بعدی

مقاله‌ی بعد درباره‌ی closure و iterator در Rust است: تابع‌هایی که محیط اطرافشان را capture می‌کنند و زنجیره‌های iterator که جای بیشتر حلقه‌ها را می‌گیرند.
