+++
date = '2026-11-20T10:00:00+03:30'
draft = false
title = 'Struct، Enum و Pattern Matching در Rust'
description = 'آموزش struct، بلوک impl، enum همراه با داده، Option، match کامل، if let و let else در Rust با کد قابل اجرا و خطای واقعی کامپایلر.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "enums", "pattern-matching", "structs"]
cover = { image = "/images/covers/rust-structs-enums-pattern-matching.fa.png", alt = "Struct، Enum و Pattern Matching در Rust", hiddenInSingle = true }
+++

فرض کنید سفارش‌های یک فروشگاه سه وضعیت دارند: در انتظار پرداخت، پرداخت‌شده و لغوشده. شش ماه بعد وضعیت چهارمی هم اضافه می‌شود: «مرجوع‌شده». در بیشتر زبان‌ها باید خودتان یادتان بماند کدام قسمت‌های برنامه وضعیت‌ها را بررسی می‌کردند و آن‌ها را به‌روز کنید. در Rust اگر یکی از حالت‌ها را در `match` جا بیندازید، برنامه اصلاً کامپایل نمی‌شود: `error[E0004]: non-exhaustive patterns`. همین بررسی است که مدل‌کردن داده در Rust را متفاوت می‌کند.

حالا که در [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) دیدیم چطور مقدار را قرض بدهیم، وقت آن است که نوع‌های خودمان را بسازیم. اگر از Go می‌آیید، struct برایتان آشناست ولی enum نه: در Rust هر variant یک enum می‌تواند داده داشته باشد و `match` شما را مجبور می‌کند همه‌ی حالت‌ها را رسیدگی کنید. این ترکیب چیزی است که وقتی به زبان‌های دیگر برمی‌گردم بیشتر از همه دلم برایش تنگ می‌شود.

> همه‌ی کدهای زیر را با Rust 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها از همان اجراها هستند. چند برنامه‌ی کوچک اضافه (برای وضعیت سفارش، `Option` و استفاده بعد از move) هم نوشتم و اجرا کردم.

## Struct و بلوک impl

اول ساده‌ترین چیز: گروه‌کردن چند مقدار که با هم معنی دارند. **struct** این کار را می‌کند. هر مقدار یک اسم دارد و به آن «فیلد» می‌گویند. رفتارهای مربوط به نوع (به‌اصطلاح method) در یک بلوک جدا به اسم `impl` نوشته می‌شوند:

```rust
#[derive(Debug, Clone, PartialEq)]
struct User {
    name: String,
    age: u32,
    active: bool,
}

impl User {
    // associated function (no self), used as User::new(...)
    fn new(name: &str, age: u32) -> Self {
        User { name: name.to_string(), age, active: true }
    }
    fn greet(&self) -> String {
        format!("hi, I am {}", self.name)
    }
    fn birthday(&mut self) {
        self.age += 1;
    }
    fn into_name(self) -> String {
        self.name
    }
}
```

کلمه‌ی کلیدی خاصی برای constructor وجود ندارد. `new` فقط یک قرارداد است: یک **associated function**، یعنی تابعی در `impl` که `self` ندارد و با `User::new(...)` صدا زده می‌شود. (`Self` هم یعنی «همین نوعی که `impl` برایش نوشته شده».)

سه تابع بعدی methodها هستند و پارامتر اولشان `self` است. شکل `self` به دو مقاله‌ی قبل برمی‌گردد:

- `&self`: فقط قرض می‌گیرد، برای خواندن. `greet` همین است.
- `&mut self`: قرضِ تغییرپذیر، برای عوض‌کردن. `birthday` سن را زیاد می‌کند.
- `self`: مالکیت را می‌گیرد. `into_name` کل `User` را مصرف می‌کند و فقط اسم را برمی‌گرداند.

ببینید بعد از `into_name` چه می‌شود اگر باز هم از user استفاده کنیم:

```rust
fn main() {
    let u = User { name: "roham".to_string(), age: 30 };
    let name = u.into_name();
    println!("{name}");
    println!("{}", u.age);
}
```

```text
error[E0382]: borrow of moved value: `u`
  --> src/bin/after_into.rs:17:20
   |
14 |     let u = User { name: "roham".to_string(), age: 30 };
   |         - move occurs because `u` has type `User`, which does not implement the `Copy` trait
15 |     let name = u.into_name();
   |                  ----------- `u` moved due to this method call
16 |     println!("{name}");
17 |     println!("{}", u.age);
   |                    ^^^^^ value borrowed here after move
   |
note: `User::into_name` takes ownership of the receiver `self`, which moves `u`
  --> src/bin/after_into.rs:8:18
   |
 8 |     fn into_name(self) -> String {
   |                  ^^^^
   = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
```

همان خطای E0382 مقاله‌ی ownership است، فقط این بار علتش یک method است: کامپایلر می‌گوید `into_name` مالک `self` می‌شود و پس `u` را move کرده است. (این یک برنامه‌ی کوچک جداگانه است که `User` در آن فقط دو فیلد `name` و `age` دارد؛ شماره‌ی خط‌ها هم مال همان فایل است.)

دو نوع سبک‌تر از struct هم هست. **tuple struct** فیلدهایش اسم ندارند: `struct Point(i32, i32)` و با `p.0` و `p.1` به آن‌ها می‌رسید. **unit struct** مثل `struct Marker;` اصلاً فیلد ندارد و فقط یک نوع است.

## derive: Debug، Clone و PartialEq

بالای `User` یک خط `#[derive(...)]` دیدید. با آن از کامپایلر می‌خواهید کد چند ویژگی (trait) را خودش برایتان بنویسد. `Debug` چاپ با `{:?}` و نسخه‌ی چندخطی و خوانای `{:#?}` را می‌دهد، `Clone` متد `.clone()` را و `PartialEq` عملگر `==` را. بدون derive باید هرکدام را دستی می‌نوشتید. برنامه‌ی `structs` از این‌ها استفاده می‌کند. (این برنامه اول `greet` را هم صدا می‌زند، و آخرش یک `Point` و یک `Marker` می‌سازد و بعد `into_name` را صدا می‌زند؛ خروجی کامل زیر است.)

```rust
let mut u = User::new("roham", 30);
println!("{}", u.greet());
u.birthday();
let snapshot = u.clone();
println!("{:?}", u);
println!("{:#?}", u);
println!("equal to snapshot: {}", u == snapshot);
u.birthday();
println!("equal after birthday: {}", u == snapshot);
```

```text
hi, I am roham
User { name: "roham", age: 31, active: true }
User {
    name: "roham",
    age: 31,
    active: true,
}
equal to snapshot: true
equal after birthday: false
point = (3, 4)
moved out name: roham
```

خط اول از `greet` است. بعد `birthday` سن را از ۳۰ به ۳۱ برد و `{:?}` همه‌ی فیلدها را در یک خط و `{:#?}` در چند خط چاپ کرد. `snapshot` یک کپی مستقل (با `.clone()`) از همان لحظه است، برای همین مقایسه با `==` اول `true` می‌دهد. بعد از `birthday` دوم `u` ۳۲ ساله شد ولی `snapshot` همان ۳۱ مانده، پس `false`. دو خط آخر از `Point` و `into_name` هستند: `point = (3, 4)` و `moved out name: roham`.

## Enum و حالت‌های ممکن

حالا به سؤال اول مقاله برگردیم: چطور چند حالت ممکن را مدل کنیم؟ در Go معمولاً یک نوع عددی با چند ثابت `iota` می‌سازید. این فقط یک عدد است. هیچ چیز جلوی تبدیل `42` به آن نوع را نمی‌گیرد، و کامپایلر Go هم بررسی نمی‌کند که `switch` همه‌ی ثابت‌ها را پوشش داده باشد. **Enum** در Rust یک نوع واقعی است که مقدارش همیشه دقیقاً یکی از حالت‌های تعریف‌شده‌اش است. به هر حالت یک **variant** می‌گویند.

ساده‌ترین شکل، enum بدون داده است. این برنامه سه وضعیت سفارش را تعریف می‌کند و با `match` برای هرکدام یک متن برمی‌گرداند:

```rust
#[derive(Debug)]
enum Status {
    Pending,
    Paid,
    Cancelled,
}

fn label(s: &Status) -> &'static str {
    match s {
        Status::Pending => "waiting for payment",
        Status::Paid => "paid",
        Status::Cancelled => "cancelled",
    }
}

fn main() {
    let orders = [Status::Pending, Status::Paid, Status::Cancelled];
    for o in &orders {
        println!("{:?}: {}", o, label(o));
    }
}
```

```text
Pending: waiting for payment
Paid: paid
Cancelled: cancelled
```

`match` مقدار را با هر الگو (pattern) مقایسه می‌کند و کد شاخه‌ی اولین الگوی منطبق را اجرا می‌کند. اینجا الگوها فقط اسم variantها هستند.

قدرت واقعی Rust وقتی پیدا می‌شود که هر variant بتواند داده‌ی خودش را داشته باشد. مثلاً شکل‌های هندسی: دایره یک شعاع دارد، مستطیل طول و عرض، و مثلث سه ضلع. به این نوع می‌گویند sum type، یعنی مقدار «یا این است، یا آن»، همراه با داده‌ی مخصوص هر حالت:

```rust
#[derive(Debug, Clone, PartialEq)]
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Triangle(f64, f64, f64),
    Empty,
}
```

`Circle` و `Rect` فیلد نام‌دار دارند، `Triangle` فیلد بی‌نام (مثل tuple struct) و `Empty` اصلاً داده ندارد. داده را با `match` بیرون می‌کشیم. الگو هم شکل variant را مطابقت می‌دهد و هم همان‌جا اسم‌هایی به فیلدها می‌دهد:

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

مثلاً در شاخه‌ی اول `radius` به شعاع همان دایره وصل می‌شود. (فرمول مثلث، فرمول هرون است: با نصف محیط `s` مساحت را از سه ضلع حساب می‌کند. `PI` را در بالای فایل از `std::f64::consts::PI` آورده‌ایم.) چون `self` در اینجا یک `&Shape` است، `radius` و بقیه‌ی فیلدها خودشان reference به مقدارها هستند، و برای همین بدون `*` هم در حساب‌ها کار می‌کنند.

## کامل‌بودن match: کامپایلر به‌عنوان چک‌لیست

حالا همان مشکل اول مقاله. این برنامه یک `Shape` با سه حالت (`Circle`، `Rect`، `Empty`) دارد، ولی `match` در `area` فقط دو حالت اول را رسیدگی می‌کند:

```rust
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Empty,
}

fn area(s: &Shape) -> f64 {
    match s {
        Shape::Circle { radius } => 3.14 * radius * radius,
        Shape::Rect { w, h } => w * h,
    }
}
```

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
11~         &Shape::Empty => todo!(),
  |
```

«non-exhaustive» یعنی الگوها همه‌ی حالت‌های ممکن را نمی‌پوشانند. کامپایلر دقیقاً می‌گوید کدام حالت جا افتاده (`&Shape::Empty`)، به تعریف enum اشاره می‌کند و حتی شاخه‌ی لازم را پیشنهاد می‌دهد (`todo!()` یعنی «بعداً پر می‌کنم»). علامت `&` جلوی `Shape::Empty` به این دلیل است که روی `&Shape` match می‌کنیم.

ارزش اصلی همین است. شش ماه بعد که یک variant اضافه می‌کنید، هر `match` ای که آن را فراموش کرده باشد کامپایل نمی‌شود. کامپایلر مثل یک چک‌لیست همه‌ی جاهایی را که باید به‌روز کنید نشان می‌دهد. شاخه‌ی wildcard، یعنی `_ =>`، این بررسی را ساکت می‌کند و «هر حالت دیگر» را می‌گیرد. پس آن را آگاهانه به کار ببرید، نه از سر عادت، وگرنه همین حفاظت را از دست می‌دهید.

## Option: بدون null

یکی از مهم‌ترین کاربردهای enum در خود Rust است. Rust مقدار null ندارد. مقداری که ممکن است وجود نداشته باشد از نوع `Option<T>` است، که خودش یک enum در کتاب‌خانه‌ی استاندارد است با دو حالت: `Some(T)` یعنی مقدار هست و `None` یعنی نیست. (`<T>` یعنی هر نوعی، مثلاً `Option<i32>`؛ درباره‌ی این علامت در مقاله‌ی generics بیشتر می‌گوییم.)

چون `Option<i32>` و `i32` دو نوع جدا هستند، نمی‌توانید بررسی «شاید نباشد» را فراموش کنید. ببینید:

```rust
fn main() {
    let a: Option<i32> = Some(41);
    let b = a + 1;
    println!("{b}");
}
```

```text
error[E0369]: cannot add `{integer}` to `Option<i32>`
   --> src/bin/option_add.rs:3:15
    |
  3 |     let b = a + 1;
    |             - ^ - {integer}
    |             |
    |             Option<i32>
```

(پیام واقعی در ادامه یک `note` هم دارد که به سورس کتاب‌خانه‌ی استاندارد روی دستگاه من اشاره می‌کند؛ چون مسیر شخصی داشت حذفش کردم.) کامپایلر می‌گوید نمی‌شود عدد را با `Option<i32>` جمع کرد. باید اول `Option` را باز کنید و حالت `None` را هم تکلیف‌دار کنید، معمولاً با `match`:

```rust
fn first_even(v: &[i32]) -> Option<i32> {
    v.iter().copied().find(|n| n % 2 == 0)
}

fn main() {
    for list in [&[1, 3, 4][..], &[1, 3][..]] {
        match first_even(list) {
            Some(n) => println!("first even is {n}"),
            None => println!("no even number"),
        }
    }
}
```

```text
first even is 4
no even number
```

`first_even` اولین عدد زوج یک فهرست را برمی‌گرداند، اگر باشد. (`find` با یک تابع کوچک می‌گردد؛ چیزی که اینجا مهم است نوع برگشتی است.) برای `[1, 3, 4]` جواب `Some(4)` است و برای `[1, 3]` که زوجی ندارد `None`. `match` مجبورتان می‌کند هر دو حالت را بنویسید.

## if let، let else، guard و @

وقتی فقط یک حالت برایتان مهم است، `match` کامل طولانی می‌شود. **`if let`** فقط همان یک حالت را رسیدگی می‌کند و بقیه را نادیده می‌گیرد. **`let else`** برعکس است: اگر الگو نخورد، بلوک `else` اجرا می‌شود که باید از تابع خارج شود، و اگر خورد، متغیر برایتان در ادامه آماده است:

```rust
if let Some(n) = first_even(&[7, 8]) {
    println!("found {n}");
}

fn parse_age(s: &str) -> u32 {
    let Ok(n) = s.parse::<u32>() else {
        return 0;
    };
    n
}
```

اولی `found 8` چاپ می‌کند، چون ۷ فرد است و ۸ اولین زوج. `parse_age` رشته را به عدد تبدیل می‌کند و اگر نشد (`Err`)، ۰ برمی‌گرداند: `parse_age("42")` می‌شود `42` و `parse_age("abc")` می‌شود `0`. (`Ok` و `Err` همان دو حالتی هستند که تبدیل می‌تواند داشته باشد؛ در مقاله‌ی مدیریت خطا کامل می‌شود.)

دو امکان دیگر الگوها را دقیق‌تر می‌کنند. **Match guard** یک `if` به شاخه اضافه می‌کند: شاخه فقط وقتی انتخاب می‌شود که الگو بخورد و شرط هم درست باشد. علامت `@` مقداری را هم‌زمان که با الگو تطبیق می‌دهد به یک اسم وصل می‌کند. تابع `describe` از هر دو استفاده می‌کند:

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

بخوانیم: مستطیلی که عرضش با طولش برابر است «مربع» حساب می‌شود (guard). دایره‌ای که شعاعش بین ۰ و ۱ است «دایره‌ی کوچک» است و `r` شعاع را نگه می‌دارد (`@`). هر دایره‌ی دیگر یک متن عمومی می‌گیرد. و آخری، `other`، هر چیز باقی‌مانده را می‌گیرد و با `{:?}` چاپ می‌کند. اجرای آن روی فهرستی از شکل‌ها، با `println!("{:<40} area = {:.2}", describe(s), s.area())`. (`{:<40}` یعنی «چپ‌چین در عرض ۴۰» و `{:.2}` یعنی دو رقم اعشار.)

```text
small circle, r = 0.5                    area = 0.79
circle, r = 2                            area = 12.57
square with side 3                       area = 9.00
Rect { w: 2.0, h: 5.0 }                  area = 10.00
Triangle(3.0, 4.0, 5.0)                  area = 6.00
Empty                                    area = 0.00
```

سطر اول: دایره‌ی ۰٫۵ به شاخه‌ی `@` خورد. سطر دوم: شعاع ۲ از بازه بیرون است، پس به شاخه‌ی عمومی دایره رسید (`{radius}` عدد `2.0` را به شکل `2` چاپ می‌کند). سطر سوم: مستطیل ۳ در ۳ مربع است. سطر چهارم: مستطیل ۲ در ۵ شرط guard را ندارد و به `other` می‌رسد. دو سطر آخر هم `other` هستند. ترتیب هم مهم است: شاخه‌ها از بالا به پایین امتحان می‌شوند، برای همین شاخه‌ی دایره‌ی کوچک باید قبل از دایره‌ی عمومی باشد.

## جاهایی که match غافلگیرتان می‌کند

- **ترتیب در `match` مهم است.** شاخه‌ها از بالا به پایین امتحان می‌شوند و اولین مطابقت انتخاب می‌شود. شاخه‌ی خاص‌تر (مثل `Rect` با guard) باید قبل از شاخه‌ی عمومی‌تر بیاید.
- **`{:?}` فقط روی نوع‌هایی کار می‌کند که `Debug` را derive یا پیاده‌سازی کرده باشند.** فراموش‌کردن derive یکی از رایج‌ترین خطاهای اول کار است.
- **اگر روی یک reference (مثل `&Shape`) match کنید، فیلدها هم reference می‌شوند.** برای همین `radius` در مثال بالا بدون `*` کار می‌کرد.
- **`unwrap()` روی `None` باعث panic می‌شود.** مگر وقتی مطمئن هستید، از `match`، `if let` یا `unwrap_or` استفاده کنید. (در برنامه‌ی `shape` هم `None.unwrap_or(-1)` را اجرا کردم و `-1` برگشت.)
- **مقایسه با Go.** ثابت‌های `iota` سبک‌تر نوشته می‌شوند ولی داده نمی‌برند و بررسی کامل‌بودن ندارند. enum در Rust اول کار بیشتر فکر کردن می‌خواهد و در عوض هر دو را به شما می‌دهد.

## تمرین

۱. یک variant به اسم `Square(f64)` به `Shape` اضافه کنید، بدون اینکه به `area` دست بزنید. خطای E0004 را بخوانید و بعد درستش کنید.
۲. تابع `fn largest(shapes: &[Shape]) -> Option<&Shape>` را بنویسید که برای slice خالی `None` برگرداند.
۳. یک enum برای وضعیت سفارش (`Pending`، `Paid { tx_id: String }`، `Cancelled(String)`) بسازید و متدی بنویسید که یک برچسب خوانا برگرداند.

## قدم بعدی

«Collectionها و String در Rust». حالا نوع‌های خودمان را داریم و طبیعی است که بخواهیم تعداد زیادی از آن‌ها را نگه داریم: با `Vec` و `HashMap`، و با نگاهی دقیق‌تر به `String`.
