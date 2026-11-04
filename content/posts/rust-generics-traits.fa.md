+++
date = '2026-12-12T10:00:00+03:30'
draft = false
title = 'Generics و Trait در Rust'
description = 'تابع و struct جنریک، trait با متد پیش‌فرض، trait bound و where، impl Trait، derive یا پیاده‌سازی دستی، سربارگذاری عملگر، monomorphization و قانون orphan.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "generics", "traits"]
cover = { image = "/images/covers/rust-generics-traits.fa.png", alt = "Generics و Trait در Rust", hiddenInSingle = true }
+++

فرض کنید تابعی می‌خواهید که بزرگ‌ترین عنصر یک فهرست را پیدا کند. برای فهرست عددهای صحیح می‌نویسیدش. فردا برای اعشاری‌ها لازم می‌شود، و بعدش برای رشته‌ها. منطق هر سه دقیقاً یکی است و فقط نوع عوض می‌شود. اگر سه نسخه‌ی جدا از روی هم بنویسید، هر اصلاحی را باید سه بار انجام دهید. در Go برای این کار از [Generics در Go](/fa/posts/go-generics/) استفاده می‌کنید. Rust هم همین را دارد، با تفاوتی که در این مقاله می‌بینیم: کامپایلر قبل از هر چیز می‌پرسد «این نوع چه کارهایی بلد است؟»

دو ایده در مرکز این مقاله است:

- **generics**: به‌جای یک نوع مشخص (`i32`)، یک «نوع به‌عنوان پارامتر» (`T`) می‌نویسید و تابع یا struct را یک بار تعریف می‌کنید.
- **trait**: یک مجموعه‌ی نام‌دار از رفتارها (متدها) که یک نوع می‌تواند داشته باشد. تقریباً همان نقش interface در Go. اگر به {{< term "trait" "trait" >}} در مقاله‌ی مدیریت خطا برخوردید (`Display`، `Error`، `From`)، همین بود.

این دو را قبلاً هم بی‌آنکه اسمشان را ببرم دیده‌اید: `Option<T>` جنریک است و `Debug` و `Display` که در `println!` استفاده کردیم trait هستند. اینجا همه را روی هم می‌گذاریم. این مقاله بعد از [Module، Crate و Cargo در Rust](/fa/posts/rust-modules-crates-cargo/) می‌آید، چون حالا که کد را مرتب کرده‌ایم، می‌خواهیم نوع‌های مختلف را با یک کد پوشش دهیم.

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. از پیام‌های خطا خط «For more information…» را حذف کرده‌ام. یک مثال را (برگرداندن دو نوع از `impl Describe`) فقط برای نمایش خطا در یک برنامه‌ی کوچک جدا نوشتم و اجرا کردم.

## تابع جنریک و bound

بیایید همان `largest` را بنویسیم. نوع را با `T` نشان می‌دهیم و فهرست را به‌صورت slice (`&[T]`) می‌گیریم، و یک reference به بزرگ‌ترین عنصر برمی‌گردانیم:

```rust
fn largest<T>(items: &[T]) -> &T {
    let mut max = &items[0];
    for item in items {
        if item > max {
            max = item;
        }
    }
    max
}
```

این کد کامپایل نمی‌شود:

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
  |
1 | fn largest<T: std::cmp::PartialOrd>(items: &[T]) -> &T {
  |             ++++++++++++++++++++++
```

دقت کنید خطا درباره‌ی خطی است که `>` در آن هست، با اینکه تنها فراخوانی برنامه (`largest(&[3, 9, 4])`) با عدد است و برای عدد `>` معنی دارد. دلیلش این است که کامپایلر بدنه‌ی تابع جنریک را فقط یک بار، و بر اساس آنچه درباره‌ی `T` می‌داند، بررسی می‌کند. و درباره‌ی `T` هیچ نمی‌داند: شاید عدد باشد، شاید یک struct که اصلاً مقایسه نمی‌شود. پس `>` مجاز نیست. راه‌حل همان پیشنهاد کامپایلر است. باید به `T` یک **trait bound** بدهیم، یعنی بگوییم «`T` می‌تواند هر نوعی باشد، به شرط اینکه `PartialOrd` (قابلیت مقایسه با `>` و `<`) را داشته باشد»:

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

حالا برنامه‌ی کامل را اجرا می‌کنیم که سه فراخوانی دارد:

```rust
println!("{}", largest(&[3, 9, 4]));
println!("{}", largest(&[1.5, 0.2]));
println!("{}", largest(&["pear", "apple"]));
```

```text
9
1.5
pear
```

یک تابع، سه نوع (`i32`، `f64` و `&str`)، و جواب هر سه درست است. «pear» از «apple» بزرگ‌تر است چون ترتیب الفبایی دارند. حالا bound معنی دارد: تابع فقط با نوع‌هایی صدا زده می‌شود که قول داده‌اند مقایسه‌پذیر باشند.

## struct و enum جنریک

نوع‌های خودتان هم می‌توانند جنریک باشند. `Pair<T>` دو مقدار هم‌نوع را نگه می‌دارد و `MyOption<T>` همان شکل `Option<T>` آشناست:

```rust
struct Pair<T> {
    a: T,
    b: T,
}

impl<T: PartialOrd + Display> Pair<T> {
    fn show_largest(&self) {
        if self.a >= self.b {
            println!("largest = {}", self.a);
        } else {
            println!("largest = {}", self.b);
        }
    }
}

enum MyOption<T> {
    Nothing,
    Just(T),
}
```

یک نکته در `impl<T: PartialOrd + Display> Pair<T>`: متد `show_largest` فقط برای جفت‌هایی وجود دارد که `T` آن‌ها هم مقایسه‌پذیر باشد و هم قابل چاپ، چون هم `>=` استفاده می‌کند و هم `{}`. برای جفتی از نوعی که چاپ نمی‌شود، `Pair` وجود دارد ولی این متد وجود ندارد. اجرایش:

```rust
Pair { a: 2, b: 7 }.show_largest();

let m: MyOption<i32> = MyOption::Just(5);
if let MyOption::Just(v) = m {
    println!("just {v}");
}
```

```text
largest = 7
just 5
```

## Trait: رفتار مشترک

حالا سراغ خود trait برویم. یک trait متدها را **اعلام** می‌کند و هر نوع با `impl Trait for Type` به آن ملحق می‌شود. trait می‌تواند **متد پیش‌فرض** (default method) هم داشته باشد: پیاده‌ساز می‌تواند آن را همان‌طور نگه دارد یا بازنویسی (override) کند. مثال: یک trait به اسم `Describe` که هر نوع باید `name` را بدهد، و `describe` به‌طور پیش‌فرض از آن یک جمله می‌سازد:

```rust
trait Describe {
    fn name(&self) -> String;
    fn describe(&self) -> String {
        format!("I am {}", self.name())
    }
}

struct Dog;
struct Cat {
    lives: u8,
}

impl Describe for Dog {
    fn name(&self) -> String {
        "a dog".to_string()
    }
}

impl Describe for Cat {
    fn name(&self) -> String {
        format!("a cat with {} lives", self.lives)
    }
    fn describe(&self) -> String {
        format!("Meow, {}", self.name())
    }
}
```

`Dog` فقط `name` را نوشته و `describe` پیش‌فرض را می‌گیرد. `Cat` هر دو را نوشته و `describe` را عوض کرده است. تابع زیر هر نوعی را که `Describe` داشته باشد می‌پذیرد:

```rust
fn announce_generic<T: Describe>(x: &T) {
    println!("{}", x.describe());
}

announce_generic(&Dog);
announce_generic(&Cat { lives: 9 });
```

```text
I am a dog
Meow, a cat with 9 lives
```

سگ همان جمله‌ی پیش‌فرض را می‌گوید و گربه جمله‌ی خودش را. اگر نوعی که `Describe` ندارد به این تابع بدهیم چه می‌شود؟ (این از یک برنامه‌ی کوچک جداست که تابع `show` آن `T: Display` می‌خواهد و نوع `Plain` ندارد.)

```text
error[E0277]: `Plain` doesn't implement `std::fmt::Display`
 --> examples/err_not_impl.rs:8:10
  |
8 |     show(Plain);
  |     ---- ^^^^^ the trait `std::fmt::Display` is not implemented for `Plain`
  |     |
  |     required by a bound introduced by this call
  |
note: required by a bound in `show`
 --> examples/err_not_impl.rs:3:12
  |
3 | fn show<T: std::fmt::Display>(x: T) {
  |            ^^^^^^^^^^^^^^^^^ required by this bound in `show`
```

این بار خطا در نقطه‌ی **فراخوانی** است و پیام روشن است: `Plain` آن trait را پیاده نکرده و `show` آن را لازم دارد. پس bound هم از بدنه‌ی تابع محافظت می‌کند و هم از جایی که صدایش می‌زنند.

## سه نوشتار برای یک ایده: bound، where و impl Trait

همان bound را می‌شود به سه شکل نوشت:

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

- شکل اول (`<T: Describe>`) همان است که دیدیم.
- `where` فقط bound‌های طولانی را از داخل `<>` بیرون می‌آورد تا امضا خوانا بماند. معنایش فرقی ندارد. (`?Sized` یعنی «`U` لازم نیست اندازه‌اش در زمان کامپایل معلوم باشد». اینجا لازم نبود؛ می‌توانید فعلاً نادیده‌اش بگیرید.)
- `impl Describe` در جایگاه آرگومان میان‌بُر همان پارامتر جنریک است.
- `impl Describe` در جایگاه مقدار برگشتی یعنی «یک نوع مشخص و واحد که `Describe` را پیاده کرده»، و فراخواننده فقط trait را می‌بیند. `make_dog` در واقع `Dog` برمی‌گرداند.

اجرای دو تای آخر:

```rust
announce_impl(&make_dog());
println!("{}", announce_where(&Dog, &Cat { lives: 7 }));
```

```text
I am a dog
I am a dog / Meow, a cat with 7 lives
```

حواستان باشد «یک نوع مشخص» جدی است. تابعی که `impl Describe` برمی‌گرداند نمی‌تواند در یک شاخه `Dog` و در شاخه‌ی دیگر `Cat` برگرداند. (این را در یک برنامه‌ی کوچک جدا آزمودم:)

```rust
fn make(dog: bool) -> impl Describe {
    if dog { Dog } else { Cat }
}
```

```text
error[E0308]: `if` and `else` have incompatible types
  --> examples/err_two_types.rs:16:27
   |
16 |     if dog { Dog } else { Cat }
   |              ---          ^^^ expected `Dog`, found `Cat`
   |              |
   |              expected because of this
   |
help: you could change the return type to be a boxed trait object
   |
15 - fn make(dog: bool) -> impl Describe {
15 + fn make(dog: bool) -> Box<dyn Describe> {
   |
```

برای اینکه نوع‌های مختلف را در زمان اجرا برگردانید، پیشنهاد کامپایلر (`Box<dyn Describe>`) راه است. این موضوع trait objectها است و در مقاله‌ی دیگری از این سری به آن می‌رسیم.

## derive یا پیاده‌سازی دستی

بعضی trait‌ها را کامپایلر می‌تواند برایتان بنویسد. `#[derive(...)]` یک پیاده‌سازی استاندارد می‌سازد. `Default` یکی از آن‌هاست و برای هر فیلد مقدار صفر یا خالی می‌گذارد، و با نحو «به‌روزرسانی struct» (`..Default::default()`) فقط فیلدهایی را که می‌خواهید عوض می‌کنید:

```rust
#[derive(Debug, Default, Clone, PartialEq)]
struct Config {
    port: u16,
    name: String,
    verbose: bool,
}

let c = Config::default();
println!("{:?}", c);
let c2 = Config { port: 8080, ..Default::default() };
println!("{:?} equal={}", c2, c == c2);
```

```text
Config { port: 0, name: "", verbose: false }
Config { port: 8080, name: "", verbose: false } equal=false
```

اما `Display` را نمی‌شود derive کرد، چون کامپایلر نمی‌داند قالب مناسب برای کاربر چیست («۱۲۳٫۴۵ دلار» یا «123.45 USD»؟). پس خودتان می‌نویسید:

```rust
impl Display for Money {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "${}.{:02}", self.cents / 100, self.cents % 100)
    }
}

println!("{}", Money { cents: 12345 });
```

```text
$123.45
```

عملگرها هم trait هستند. `a + b` در پشت صحنه یعنی `Add::add(a, b)`. پس با پیاده‌کردن `std::ops::Add` برای یک struct، عملگر `+` برایش کار می‌کند:

```rust
impl Add for Point {
    type Output = Point;
    fn add(self, o: Point) -> Point {
        Point { x: self.x + o.x, y: self.y + o.y }
    }
}

println!("{:?}", Point { x: 1, y: 2 } + Point { x: 10, y: 20 });
```

```text
Point { x: 11, y: 22 }
```

(`type Output = Point` می‌گوید نتیجه‌ی جمع چه نوعی است. `Point` در برنامه با `#[derive(Debug, Clone, Copy, PartialEq)]` تعریف شده است.)

## Monomorphization: چرا جنریک در زمان اجرا هزینه ندارد

یک سؤال طبیعی: کامپایلر با یک تابع جنریک چه می‌کند؟ جواب این است که برای هر نوع مشخصی که تابع با آن استفاده شود، یک نسخه‌ی جدا و تخصصی از آن می‌سازد. اسمش **monomorphization** است. مثل اینکه خودتان `largest_i32` و `largest_f64` را نوشته باشید، ولی کامپایلر این کار را می‌کند. یک آزمایش کوچک این را نشان می‌دهد: تابعی که نام نوع `T` را چاپ می‌کند:

```rust
fn identity<T>(x: T) -> T {
    println!("identity::<{}>", type_name::<T>());
    x
}

identity(5i32);
identity("hi");
identity(2.5f64);
```

```text
identity::<i32>
identity::<&str>
identity::<f64>
```

سه فراخوانی، سه نوع مختلف، یعنی سه نمونه‌سازی جدا. خود برنامه این را مستقیم نشان نمی‌دهد (چاپ نام نوع فقط می‌گوید هر فراخوانی `T` متفاوتی دیده است)، ولی طبق Rust Book همین کار کامپایلر باعث می‌شود جنریک در زمان اجرا هزینه‌ی اضافه نداشته باشد: هر نسخه برای نوع خودش بهینه می‌شود. بهایش حجم بیشتر کد کامپایل‌شده است. من اینجا چیزی درباره‌ی سرعت اندازه نگرفته‌ام.

## قانون orphan

یک محدودیت مهم: فقط وقتی می‌توانید یک trait را برای یک نوع پیاده کنید که **یا خودِ trait یا خودِ نوع در crate شما تعریف شده باشد**. اگر هر دو بیرونی باشند، دو crate مختلف می‌توانستند دو پیاده‌سازی متناقض بنویسند و معلوم نبود کدام برنده است. برای همین، پیاده‌کردن `Display` استاندارد برای `Vec<i32>` استاندارد رد می‌شود:

```text
error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate
 --> examples/err_orphan.rs:3:1
  |
3 | impl fmt::Display for Vec<i32> {
  | ^^^^^^^^^^^^^^^^^^^^^^--------
  |                       |
  |                       `Vec` is not defined in the current crate
  |
  = note: impl doesn't have any local type before any uncovered type parameters
  = note: for more information see https://doc.rust-lang.org/reference/items/implementations.html#orphan-rules
  = note: define and implement a trait or new type instead
```

راه‌حل معمول همان پیشنهاد کامپایلر است: نوع را داخل یک struct خودتان بپیچید (به این الگو newtype می‌گویند) و برای آن trait را پیاده کنید، یا trait خودتان را تعریف کنید.

## مقایسه با Go

در Go یک interface به‌صورت ساختاری (structural) برآورده می‌شود: هر نوعی که متدهای درست را داشته باشد جا می‌شود و نیازی به اعلام نیست. در Rust این پیوند صریح است: خودتان `impl Trait for Type` می‌نویسید و قانون orphan می‌گوید این خط کجا می‌تواند باشد. در هر دو زبان، مجموعه‌ای از رفتار شبیه interface به‌عنوان constraint جنریک به کار می‌رود (درباره‌ی constraintها در Go به [Generics در Go](/fa/posts/go-generics/) نگاه کنید).

## دام‌های trait

- بدون bound تقریباً کاری با `T` نمی‌شود کرد. وقتی کامپایلر ایراد می‌گیرد، bound را همان‌طور که پیشنهاد می‌دهد اضافه کنید.
- `impl Trait` در مقدار برگشتی یعنی یک نوع مشخص، نه «هر نوعی».
- وقتی پیاده‌سازی استاندارد کافی است derive کنید، و وقتی معنا مال شماست (مثل `Display`) دستی بنویسید.
- قانون orphan درباره‌ی مالکیت trait و نوع است، نه دیده‌شدن (visibility).

## تمرین

1. تابع `fn smallest<T: PartialOrd>(items: &[T]) -> &T` را بنویسید و با عدد و رشته آزمایش کنید.
2. trait‌ای به نام `Area` با `fn area(&self) -> f64` و یک متد پیش‌فرض `describe` که مساحت را چاپ می‌کند تعریف کنید و برای `Circle` و `Rect` پیاده کنید.
3. `Mul<f64>` را برای `Point` با فیلدهای `f64` پیاده کنید تا `p * 2.0` کار کند.

## قدم بعدی

در `largest` بالا یک `&T` برگرداندیم و کامپایلر بی‌حرف قبول کرد، ولی هر بار چنین نیست. وقتی تابع دو reference می‌گیرد و یکی را برمی‌گرداند، کامپایلر می‌پرسد این reference تا کِی معتبر است. جواب این سؤال «Lifetime در Rust» است.
