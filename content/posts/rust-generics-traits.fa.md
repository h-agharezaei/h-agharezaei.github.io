+++
date = '2026-12-12T10:00:00+03:30'
draft = false
title = 'Generics و Trait در Rust'
description = 'تابع و struct جنریک، trait با متد پیش‌فرض، trait bound و where، impl Trait، derive یا پیاده‌سازی دستی، سربارگذاری عملگر، monomorphization و قانون orphan.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "generics", "traits"]
cover = { image = "/images/covers/rust-generics-traits.fa.png", alt = "Generics و Trait در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-modules-crates-cargo/) کد را به ماژول و crate تقسیم کردیم. حالا می‌خواهیم کدی بنویسیم که برای چند نوع هم‌زمان کار کند. در Rust این کار روی دو ایده بنا شده: **generics** (کدی که نوع، پارامتر آن است) و **trait** (مجموعه‌ای نام‌دار از رفتار که یک نوع می‌تواند داشته باشد). این دو را قبلاً بی‌آنکه اسم ببریم استفاده کرده‌اید: `Option<T>` جنریک است و `Display` و `Debug` trait هستند.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## تابع جنریک و bound

```rust
fn largest<T: PartialOrd>(items: &[T]) -> &T {
    let mut max = &items[0];
    for item in items {
        if item > max {
            max = item;
        }
    }
    max
}
```

`T: PartialOrd` یک **trait bound** است: `T` می‌تواند هر نوعی باشد که عملگر `>` را پشتیبانی کند. `largest(&[3, 9, 4])` مقدار `9`، `largest(&[1.5, 0.2])` مقدار `1.5` و `largest(&["pear", "apple"])` مقدار `pear` را می‌دهد. اگر bound را حذف کنید، کامپایلر قبول نمی‌کند، حتی اگر هیچ‌وقت تابع را با نوع نامناسب صدا نزده باشیم:

```text
error[E0369]: binary operation `>` cannot be applied to type `&T`
 --> examples/err_no_bound.rs:4:17
  |
4 |         if item > max {
  |            ---- ^ --- &T
  |            |
  |            &T
  |
help: consider restricting type parameter `T` with trait `PartialOrd`
```

بدنه‌ی تابع فقط یک بار و بر اساس چیزی که bound‌ها تضمین می‌کنند بررسی می‌شود. نوع جنریک هم همین‌طور است: `struct Pair<T> { a: T, b: T }` و `enum MyOption<T> { Nothing, Just(T) }` همان شکلِ `Option<T>` آشنا را دارند. متدها هم می‌توانند bound اضافه کنند: `impl<T: PartialOrd + Display> Pair<T>` متد `show_largest` را فقط به جفت‌هایی می‌دهد که `T` آن‌ها قابل مقایسه و چاپ باشد.

## Trait

یک **trait** متدها را اعلام می‌کند و نوع با `impl Trait for Type` به آن ملحق می‌شود. trait می‌تواند **متد پیش‌فرض** (default method) داشته باشد که پیاده‌ساز می‌تواند نگهش دارد یا override کند:

```rust
trait Describe {
    fn name(&self) -> String;
    fn describe(&self) -> String {
        format!("I am {}", self.name())
    }
}

impl Describe for Dog {
    fn name(&self) -> String { "a dog".to_string() }
}
impl Describe for Cat {
    fn name(&self) -> String { format!("a cat with {} lives", self.lives) }
    fn describe(&self) -> String { format!("Meow, {}", self.name()) }
}
```

`Dog` و `Cat` دو struct کوچک هستند (`Cat` فیلد `lives: u8` دارد). صدا زدن `describe()` روی آن‌ها به ترتیب `I am a dog` و `Meow, a cat with 9 lives` چاپ می‌کند.

## bound، where و impl Trait

سه نوشتار برای یک ایده:

```rust
fn announce_generic<T: Describe>(x: &T) { println!("{}", x.describe()); }

fn announce_where<T, U>(x: &T, y: &U) -> String
where
    T: Describe,
    U: Describe + ?Sized,
{
    format!("{} / {}", x.describe(), y.describe())
}

fn announce_impl(x: &impl Describe) { println!("{}", x.describe()); }
fn make_dog() -> impl Describe { Dog }
```

`where` فقط bound‌های طولانی را از داخل `<>` بیرون می‌آورد. `impl Describe` در جایگاه آرگومان میان‌بُرِ یک پارامتر جنریک است. در جایگاه مقدار برگشتی یعنی «یک نوع مشخص و واحد که `Describe` را پیاده کرده» و فراخواننده فقط trait را می‌بیند. تابعی که `impl Describe` برمی‌گرداند نمی‌تواند در یک شاخه `Dog` و در شاخه‌ی دیگر `Cat` برگرداند. خروجی `announce_where(&Dog, &Cat { lives: 7 })` این بود: `I am a dog / Meow, a cat with 7 lives`.

## derive یا پیاده‌سازی دستی

`#[derive(...)]` یک پیاده‌سازی استاندارد برایتان می‌سازد. `Default` را می‌شود derive کرد؛ پس `Config::default()` مقدار `Config { port: 0, name: "", verbose: false }` را می‌دهد و با struct update syntax بقیه پر می‌شود: `Config { port: 8080, ..Default::default() }`. اما `Display` را نمی‌شود derive کرد، چون قالب مناسب برای کاربر معلوم نیست، پس خودتان می‌نویسید:

```rust
impl Display for Money {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "${}.{:02}", self.cents / 100, self.cents % 100)
    }
}
```

`Money { cents: 12345 }` را به شکل `$123.45` چاپ می‌کند. عملگرها هم trait هستند. پیاده کردن `std::ops::Add` برای struct‌ای مثل `Point { x, y }` (با derive کردن `Debug`، `Clone` و `Copy`) عملگر `+` را فعال می‌کند:

```rust
impl Add for Point {
    type Output = Point;
    fn add(self, o: Point) -> Point {
        Point { x: self.x + o.x, y: self.y + o.y }
    }
}
```

`Point { x: 1, y: 2 } + Point { x: 10, y: 20 }` مقدار `Point { x: 11, y: 22 }` را چاپ می‌کند.

## Monomorphization

کامپایلر برای هر نوع مشخصی که یک تابع جنریک با آن استفاده می‌شود یک نسخه‌ی جدا تولید می‌کند؛ به این کار **monomorphization** می‌گویند. یک آزمایش کوچک این نسخه‌ها را نشان می‌دهد:

```rust
fn identity<T>(x: T) -> T {
    println!("identity::<{}>", type_name::<T>());
    x
}
```

```text
identity::<i32>
identity::<&str>
identity::<f64>
```

سه فراخوانی، سه نوع، سه نمونه‌سازی. ادعایی درباره‌ی سرعت ندارم؛ فقط جنریک در زمان کامپایل حل می‌شود.

## قانون orphan

فقط وقتی می‌توانید trait‌ای را برای نوعی پیاده کنید که یا trait یا نوع در crate خودتان تعریف شده باشد. پیاده کردن `Display` استاندارد برای `Vec<i32>` استاندارد رد می‌شود:

```text
error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate
 --> examples/err_orphan.rs:3:1
  |
3 | impl fmt::Display for Vec<i32> {
  | ^^^^^^^^^^^^^^^^^^^^^^--------
  |                       |
  |                       `Vec` is not defined in the current crate
  |
  = note: define and implement a trait or new type instead
```

راه‌حل معمول همان پیشنهاد کامپایلر است: نوع را داخل struct خودتان بپیچید (الگوی newtype) یا trait خودتان را تعریف کنید.

## مقایسه با Go

در Go یک interface به‌صورت ساختاری (structural) برآورده می‌شود: هر نوعی که متدهای درست را داشته باشد جا می‌شود و نیازی به اعلام نیست (درباره‌ی constraint‌ها به [Generics در Go](/fa/posts/go-generics/) نگاه کنید). در Rust این پیوند صریح است: خودتان `impl Trait for Type` می‌نویسید و قانون orphan می‌گوید این خط کجا می‌تواند باشد. در هر دو زبان مجموعه‌ای از رفتار شبیه interface به‌عنوان constraint جنریک به کار می‌رود.

## چند نکته

- بدون bound تقریباً کاری با `T` نمی‌شود کرد؛ bound‌ها را همان‌طور که کامپایلر می‌گوید اضافه کنید.
- `impl Trait` در مقدار برگشتی یعنی یک نوع مشخص، نه «هر نوعی».
- وقتی پیاده‌سازی استاندارد کافی است derive کنید؛ وقتی معنا مال شماست (مثل `Display`) دستی بنویسید.
- قانون orphan درباره‌ی مالکیت trait و نوع است، نه دیده شدن (visibility).

## تمرین

1. تابع `fn smallest<T: PartialOrd>(items: &[T]) -> &T` را بنویسید و با عدد و رشته تست کنید.
2. trait‌ای به نام `Area` با `fn area(&self) -> f64` و یک متد پیش‌فرض `describe` که مساحت را چاپ می‌کند تعریف کنید و برای `Circle` و `Rect` پیاده کنید.
3. `Mul<f64>` را برای `Point` با فیلدهای `f64` پیاده کنید تا `p * 2.0` کار کند.

## قدم بعدی

در مقاله‌ی بعد با lifetime‌ها در Rust آشنا می‌شویم؛ آن‌ها توضیح می‌دهند این `&T`‌ها مجازند به چه چیزی و تا کِی اشاره کنند.
