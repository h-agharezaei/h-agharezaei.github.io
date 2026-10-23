+++
date = '2026-11-20T10:00:00+03:30'
draft = false
title = 'Struct، Enum و Pattern Matching در Rust'
description = 'آموزش struct، بلوک impl، enum همراه با داده، Option، match کامل، if let و let else در Rust با کد قابل اجرا و خطای واقعی کامپایلر.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "enums", "pattern-matching", "structs"]
cover = { image = "/images/covers/rust-structs-enums-pattern-matching.fa.png", alt = "Struct، Enum و Pattern Matching در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-borrowing-references/) یاد گرفتیم چطور مقدارها را با reference قرض بدهیم. حالا می‌توانیم داده را مدل کنیم. اگر از Go می‌آیید، struct برایتان آشناست ولی enum نه: در Rust هر variant می‌تواند داده داشته باشد و `match` شما را مجبور می‌کند همه‌ی حالت‌ها را رسیدگی کنید. این ترکیب چیزی است که وقتی به زبان‌های دیگر برمی‌گردم بیشتر از همه دلم برایش تنگ می‌شود.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## Struct و بلوک impl

رایج‌ترین حالت یک **struct** با فیلدهای نام‌دار است. رفتار (behavior) در یک بلوک جدا به اسم `impl` نوشته می‌شود:

```rust
#[derive(Debug, Clone, PartialEq)]
struct User {
    name: String,
    age: u32,
    active: bool,
}

impl User {
    // associated function: بدون self، با User::new(...) صدا زده می‌شود
    fn new(name: &str, age: u32) -> Self {
        User { name: name.to_string(), age, active: true }
    }
    fn greet(&self) -> String { format!("hi, I am {}", self.name) }
    fn birthday(&mut self) { self.age += 1; }
    fn into_name(self) -> String { self.name }
}
```

کلمه‌ی کلیدی خاصی برای constructor وجود ندارد. `new` فقط یک قرارداد است: یک **associated function** (بدون `self`) که با `User::new` صدا زده می‌شود. سه شکل method دقیقاً به دو مقاله‌ی قبل برمی‌گردد: `&self` قرض گرفتن، `&mut self` قرض گرفتن برای تغییر، و `self` گرفتن مالکیت است؛ بنابراین بعد از `into_name` دیگر user وجود ندارد.

دو نوع سبک‌تر از struct هم هست: **tuple struct** مثل `struct Point(i32, i32)` (دسترسی با `p.0`) و **unit struct** مثل `struct Marker;` که اصلاً فیلد ندارد.

## derive: ‏Debug، Clone و PartialEq

`#[derive(...)]` از کامپایلر می‌خواهد پیاده‌سازی trait ها را خودش بسازد. `Debug` همان `{:?}` و نسخه‌ی خوانای `{:#?}` را می‌دهد، `Clone` متد `.clone()` را و `PartialEq` عملگر `==` را:

```rust
let mut u = User::new("roham", 30);
u.birthday();
let snapshot = u.clone();
println!("{:?}", u);
println!("{:#?}", u);
println!("equal to snapshot: {}", u == snapshot);
u.birthday();
println!("equal after birthday: {}", u == snapshot);
```

```text
User { name: "roham", age: 31, active: true }
User {
    name: "roham",
    age: 31,
    active: true,
}
equal to snapshot: true
equal after birthday: false
```

## Enum هایی که داده دارند

«enum» در Go معمولاً یک نوع عددی با ثابت‌های `iota` است. این فقط یک عدد است: هیچ چیز جلوی تبدیل `42` به آن نوع را نمی‌گیرد و کامپایلر هم بررسی نمی‌کند که `switch` همه‌ی ثابت‌ها را پوشش داده باشد. **Enum** در Rust یک sum type واقعی است و هر variant می‌تواند داده‌ی متفاوتی نگه دارد:

```rust
#[derive(Debug, Clone, PartialEq)]
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Triangle(f64, f64, f64),
    Empty,
}
```

داده را با `match` بیرون می‌کشیم:

```rust
impl Shape {
    fn area(&self) -> f64 {
        match self {
            Shape::Circle { radius } => PI * radius * radius,
            Shape::Rect { w, h } => w * h,
            Shape::Triangle(a, b, c) => {
                let s = (a + b + c) / 2.0;
                (s * (s - a) * (s - b) * (s - c)).sqrt()
            }
            Shape::Empty => 0.0,
        }
    }
}
```

## کامل بودن match: کامپایلر به‌عنوان چک‌لیست

حالا شاخه‌ی `Empty` را از یک `match` روی enum مشابه حذف کنید. این فایل `src/bin/missing_variant.rs` در نمونه‌ی من است:

```text
error[E0004]: non-exhaustive patterns: `&Shape::Empty` not covered
 --> src/bin/missing_variant.rs:8:11
  |
8 |     match s {
  |           ^ pattern `&Shape::Empty` not covered
  |
note: `Shape` defined here
 --> src/bin/missing_variant.rs:1:6
  |
1 | enum Shape {
  |      ^^^^^
...
4 |     Empty,
  |     ----- not covered
  = note: the matched value is of type `&Shape`
help: ensure that all possible cases are being handled by adding a match arm with a wildcard pattern or an explicit pattern as shown
  |
10~         Shape::Rect { w, h } => w * h,
11~ &Shape::Empty => todo!(),
  |
```

ارزش اصلی همین است. شش ماه بعد که یک variant اضافه می‌کنید، هر `match` ای که آن را فراموش کرده باشد کامپایل نمی‌شود. wildcard یعنی `_ =>` این بررسی را ساکت می‌کند، پس آن را آگاهانه به کار ببرید، نه از سر عادت.

## Option: بدون null

Rust مقدار null ندارد. مقداری که ممکن است وجود نداشته باشد از نوع `Option<T>` است، که خودش یک enum در کتاب‌خانه‌ی استاندارد است: یا `Some(T)` یا `None`. چون `Option<i32>` و `i32` دو نوع جدا هستند، نمی‌توانید بررسی را فراموش کنید:

```rust
fn first_even(v: &[i32]) -> Option<i32> {
    v.iter().copied().find(|n| n % 2 == 0)
}

println!("{:?} {:?}", first_even(&[1, 3, 4]), first_even(&[1, 3]));
// Some(4) None
```

## ‏if let، let else، guard و @

وقتی فقط یک حالت برایتان مهم است `match` طولانی می‌شود. **`if let`** همان یک حالت را رسیدگی می‌کند و **`let else`** در غیر آن صورت زودتر از تابع خارج می‌شود:

```rust
if let Some(n) = first_even(&[7, 8]) {
    println!("found {n}");
}

fn parse_age(s: &str) -> u32 {
    let Ok(n) = s.parse::<u32>() else { return 0; };
    n
}
```

**Match guard** یک `if` به شاخه اضافه می‌کند و `@` یک مقدار را هم‌زمان که با الگو تطبیق می‌دهد به یک نام وصل می‌کند:

```rust
fn describe(s: &Shape) -> String {
    match s {
        Shape::Rect { w, h } if w == h => format!("square with side {w}"),
        Shape::Circle { radius: r @ 0.0..=1.0 } => format!("small circle, r = {r}"),
        Shape::Circle { radius } => format!("circle, r = {radius}"),
        other => format!("{other:?}"),
    }
}
```

اجرای آن روی فهرستی از شکل‌ها با `println!("{:<40} area = {:.2}", describe(s), s.area())`:

```text
small circle, r = 0.5                    area = 0.79
circle, r = 2                            area = 12.57
square with side 3                       area = 9.00
Rect { w: 2.0, h: 5.0 }                  area = 10.00
Triangle(3.0, 4.0, 5.0)                  area = 6.00
Empty                                    area = 0.00
```

خروجی `first_even(&[7, 8])` عبارت `found 8` بود و `parse_age("42")` و `parse_age("abc")` به‌ترتیب `42` و `0` برگرداندند.

## چند نکته که باید حواستان باشد

- ترتیب در `match` مهم است: شاخه‌ها از بالا به پایین امتحان می‌شوند، پس شاخه‌ی `Rect` همراه guard باید قبل از شاخه‌های عمومی‌تر بیاید.
- `{:?}` فقط روی نوع‌هایی کار می‌کند که `Debug` را derive یا پیاده‌سازی کرده باشند؛ فراموش کردن derive یکی از رایج‌ترین خطاهای اول است.
- اگر روی یک reference (مثل `&Shape`) match کنید، فیلدها هم reference می‌شوند؛ برای همین `radius` در مثال بالا بدون dereference استفاده شده است.
- `unwrap()` روی `None` باعث panic می‌شود. مگر وقتی مطمئن هستید، از `match`، `if let` یا `unwrap_or` استفاده کنید.
- مقایسه با Go: ثابت‌های iota سبک‌تر نوشته می‌شوند ولی داده نمی‌برند و بررسی کامل بودن ندارند. enum در Rust اول کار بیشتر فکر کردن می‌خواهد و در عوض هر دو را به شما می‌دهد.

## تمرین

1. یک variant به اسم `Square(f64)` به `Shape` اضافه کنید، بدون اینکه به `area` دست بزنید. خطای E0004 را بخوانید و بعد درستش کنید.
2. تابع `fn largest(shapes: &[Shape]) -> Option<&Shape>` را بنویسید که برای slice خالی `None` برگرداند.
3. یک enum برای وضعیت سفارش (`Pending`، `Paid { tx_id: String }`، `Cancelled(String)`) بسازید و متدی بنویسید که یک برچسب خوانا برگرداند.

## قدم بعدی

حالا نوع‌های خودمان را داریم. در مقاله‌ی بعد، collection ها و رشته‌ها در Rust، بسیاری از آن‌ها را با `Vec` و `HashMap` نگه می‌داریم و `String` را دقیق‌تر بررسی می‌کنیم.
