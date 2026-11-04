+++
date = '2027-02-08T10:00:00+03:30'
draft = false
title = 'Trait Object و dyn در Rust'
description = 'Trait object و dyn در Rust: Box<dyn Trait>، dispatch ایستا و پویا، fat pointer، خطای E0038، downcast با Any و انتخاب بین enum، generics و dyn.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "traits", "dyn", "intermediate"]
cover = { image = "/images/covers/rust-trait-objects-dyn.fa.png", alt = "Trait Object و dyn در Rust", hiddenInSingle = true }
+++

فرض کنید برنامه‌ای برای رسم شکل‌ها می‌نویسید. یک `Square` دارید و یک `Circle`، و می‌خواهید همه‌ی شکل‌ها را در یک فهرست نگه دارید تا یک حلقه مساحت هرکدام را چاپ کند. در Go این کار پیش‌پاافتاده است: یک interface به اسم `Shape` تعریف می‌کنید و یک slice از آن می‌سازید. در Rust اولین تلاش این است:

```rust
struct Square(f64);
struct Circle(f64);

fn main() {
    let shapes = vec![Square(2.0), Circle(1.0)];
    println!("{}", shapes.len());
}
```

```text
error[E0308]: mismatched types
 --> src/bin/x1.rs:5:36
  |
5 |     let shapes = vec![Square(2.0), Circle(1.0)];
  |                                    ^^^^^^^^^^^ expected `Square`, found `Circle`
```

خطا سرراست است: `Vec<T>` دقیقاً یک نوع `T` دارد. کامپایلر از اولین عنصر نتیجه گرفته که `T` همان `Square` است و `Circle` در آن جا نمی‌شود. این فقط لجبازی کامپایلر نیست؛ `Vec` عنصرها را پشت‌سرهم و هر کدام با اندازه‌ی یکسان می‌چیند، و `Square` و `Circle` ممکن است اندازه‌هایشان فرق کند. در [جنریک‌ها و trait‌ها](/fa/posts/rust-generics-traits/) هم دیدیم که جنریک «یک نوع، انتخاب‌شده در زمان کامپایل» است. حالا چیزی لازم داریم که بگوید «هر نوعی، به شرط اینکه `Shape` را پیاده کرده باشد، و انتخابش تا زمان اجرا باز بماند».

جواب Rust یک {{< term "trait-object" "trait object" >}} است که به شکل `dyn Trait` نوشته می‌شود. این مقاله بعد از [کلاینت async NATS JetStream](/fa/posts/rust-nats-async-client/) می‌آید و نیمه‌ی دیگر همان داستان جنریک‌هاست. طرف Go ماجرا، یعنی interface، در [struct، متد و interface](/fa/posts/go-structs-methods-interfaces/) آمده است.

> همه‌ی کدها را با Rust 1.90 (`rustc 1.90.0`) دوباره اجرا کرده‌ام و خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. برنامه‌ها فقط به کتابخانه‌ی استاندارد نیاز دارند و هیچ crate بیرونی ندارند. از پیام‌های خطا خط «For more information…» را حذف کرده‌ام. چند مثال کوچک (خطای `Vec` ناهمگن، نوشتن نام trait بدون `dyn`، و نسخه‌ی enum) را فقط برای نمایش در برنامه‌های جدا نوشتم و اجرا کردم. درباره‌ی کارایی ادعایی نمی‌کنم؛ فقط اندازه‌ها و خروجی کامپایلر را نشان می‌دهم.

## ایده‌ی اصلی: مقداری که نوعش را فراموش کرده‌ایم

یک trait object مقداری است که از نوع واقعی‌اش فقط یک چیز را می‌دانیم: «هر چه هست، `Shape` را پیاده کرده». نمی‌دانیم `Square` است یا `Circle`، ولی می‌دانیم می‌شود رویش `area()` را صدا زد. مثل پریز برق: برایمان مهم نیست پشت دیوار چه سیم‌کشی‌ای است، فقط می‌دانیم دوشاخه‌مان در آن جا می‌شود.

چون اندازه‌ی چنین مقداری معلوم نیست، آن را مستقیم نگه نمی‌داریم. پشت یک اشاره‌گر می‌گذاریمش: `Box<dyn Shape>` یعنی «یک Box روی heap، که چیزی داخلش است و آن چیز `Shape` است»، و `&dyn Shape` یعنی «یک reference به چیزی که `Shape` است». اشاره‌گر همیشه اندازه‌ی ثابتی دارد، پس `Vec` از آن‌ها ساخته می‌شود.

این کد همان فهرست را می‌سازد:

```rust
trait Shape: Debug {
    fn area(&self) -> f64;
    fn name(&self) -> String { "shape".to_string() }
}

let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Square(2.0)), Box::new(Circle(1.0))];
for s in &shapes {
    println!("{} area={:.2} {:?}", s.name(), s.area(), s);
}
```

```text
square area=4.00 Square(2.0)
shape area=3.14 Circle(1.0)
```

هر خط خروجی از یک عنصر فهرست آمده است. `Square` متد `name` را خودش پیاده کرده و `"square"` برمی‌گرداند؛ `Circle` پیاده نکرده و همان پیاده‌سازی پیش‌فرض trait، یعنی `"shape"`، را گرفته. حلقه هیچ‌جا نمی‌داند با کدام نوع کار می‌کند، و با این حال هر بار متد درست اجرا می‌شود.

در تعریف trait عبارت `: Debug` را دیدید. به آن **supertrait** می‌گویند: هر نوعی که `Shape` را پیاده می‌کند باید `Debug` را هم پیاده کرده باشد. به همین دلیل `{:?}` روی خود trait object کار می‌کند، چون کامپایلر می‌داند هر `Shape` یک `Debug` هم هست.

اشاره‌گرهای دیگر هم با `dyn` کار می‌کنند. `&dyn Shape` قرض می‌گیرد و `Rc<dyn Shape>` مالکیت را مشترک می‌کند. در demo یک `Rc<dyn Shape>` ساختم، یک clone ازش گرفتم و `Rc::strong_count` عدد `2` چاپ کرد (خط `rc: area=9 count=2`).

## چطور متد درست پیدا می‌شود؟ dispatch ایستا و پویا

حالا یک سؤال: وقتی `s.area()` را صدا می‌زنیم و نوع `s` را نمی‌دانیم، چطور سراغ کد درست می‌رود؟ به انتخاب اینکه کدام تابع اجرا شود می‌گویند **dispatch**. Rust دو روش دارد و هر دو را می‌شود روی یک تابع ساده دید:

```rust
fn print_static<S: Shape>(s: &S) { /* ... */ }   // جنریک
fn print_dyn(s: &dyn Shape) { /* ... */ }        // trait object
```

در تابع جنریک کامپایلر **monomorphization** انجام می‌دهد: برای هر نوع مشخصی که با آن صدا زده شده یک نسخه‌ی جدا از `print_static` می‌سازد. فراخوانی `Square` به نسخه‌ی `Square` می‌رود و فراخوانی `Circle` به نسخه‌ی `Circle`. تصمیم قبل از اجرا گرفته شده و به آن **dispatch ایستا** می‌گویند.

با `&dyn Shape` فقط یک نسخه از `print_dyn` وجود دارد. این نسخه باید با هر نوعی کار کند، پس متد را موقع اجرا پیدا می‌کند. راهش یک جدول کوچک است به اسم {{< term "vtable" "vtable" >}}: برای هر نوع مشخصی که به شکل `dyn Shape` درآمده، کامپایلر یک جدول می‌سازد که آدرس متدهای آن نوع (`area`، `name` و ...) در آن است. به این **dispatch پویا** می‌گویند. تصویرش چیزی شبیه این است:

```text
&dyn Shape                      vtable مخصوص Square
+-------------------+           +----------------------+
| اشاره‌گر به داده   | --+       | آدرس drop            |
| اشاره‌گر به vtable | --|--->   | اندازه و alignment   |
+-------------------+   |       | آدرس area            |
                        |       | آدرس name            |
                        v       +----------------------+
                     Square(2.0)
```

(جزئیات چیدمان vtable در خود زبان تضمین‌شده نیست؛ این تصویر فقط ایده را نشان می‌دهد.) صدا زدن `s.area()` یعنی «برو سراغ vtable، آدرس `area` را بردار و آن تابع را با اشاره‌گر داده صدا بزن». در Go هم مقدار interface همین‌طور کار می‌کند: جفتی از اشاره‌گر به اطلاعات نوع و اشاره‌گر به داده.

پس معامله این است: با dispatch پویا یک نسخه از کد داریم و نوع‌ها را می‌شود قاطی کرد، ولی هر فراخوانی از یک جدول رد می‌شود و کامپایلر معمولاً نمی‌داند کدام تابع اجرا می‌شود، پس مثلاً نمی‌تواند آن را inline کند. با dispatch ایستا کد برای هر نوع تکثیر می‌شود و نوع‌ها باید در زمان کامپایل معلوم باشند. من درباره‌ی اندازه‌ی این تفاوت عددی نمی‌دهم؛ در بیشتر برنامه‌ها این تفاوت مهم‌ترین مسئله نیست و انتخاب را شکل مسئله تعیین می‌کند (در بخش انتخاب‌کردن برمی‌گردیم).

## Fat pointer: اشاره‌گر به اندازه‌ی دو کلمه

در تصویر بالا دیدید که `&dyn Shape` باید هم به داده اشاره کند هم به vtable. یعنی دو آدرس، نه یکی. به چنین اشاره‌گری **fat pointer** می‌گویند. demo اندازه‌ها را چاپ می‌کند:

```text
&i32               = 8
&dyn Shape         = 16
Box<dyn Shape>     = 16
Box<Square>        = 8
Square / Circle    = 8 / 8
```

این اندازه‌ها بر حسب بایت روی ماشین ۶۴ بیتی من‌اند. `&i32` یک آدرس است: ۸ بایت. `&dyn Shape` دو آدرس است: ۱۶ بایت. `Box<dyn Shape>` هم همین‌طور ۱۶ است، ولی `Box<Square>` فقط ۸ بایت است، چون وقتی نوع مشخص است نیازی به vtable نیست و کامپایلر خودش می‌داند کدام تابع را صدا بزند. پس هزینه‌ی `dyn` یک کلمه‌ی اضافه در هر اشاره‌گر است، به‌علاوه‌ی یک heap allocation اگر از `Box` استفاده کنید.

## همه‌ی trait‌ها dyn نمی‌شوند: خطای E0038

حالا تله‌ی اصلی این مقاله. وقتی نوع را فراموش کرده‌ایم، کامپایلر باید بتواند فقط با نگاه به `dyn Trait` بگوید هر متد چه امضایی دارد و کجای vtable است. برای بعضی متدها این ممکن نیست. این trait را در نظر بگیرید که دو متد مشکل‌دار دارد، و بعد سعی می‌کنیم یک `Box<dyn Cloner>` بسازیم:

```rust
trait Cloner {
    fn dup(&self) -> Self;
    fn convert<T: Into<f64>>(&self, x: T) -> f64;
}
```

```text
error[E0038]: the trait `Cloner` is not dyn compatible
  --> src/bin/e0038.rs:11:24
   |
11 |     let v: Vec<Box<dyn Cloner>> = vec![Box::new(A)];
   |                        ^^^^^^ `Cloner` is not dyn compatible
   |
note: for a trait to be dyn compatible it needs to allow building a vtable
      for more information, visit <https://doc.rust-lang.org/reference/items/traits.html#dyn-compatibility>
  --> src/bin/e0038.rs:2:22
   |
 1 | trait Cloner {
   |       ------ this trait is not dyn compatible...
 2 |     fn dup(&self) -> Self;
   |                      ^^^^ ...because method `dup` references the `Self` type in its return type
 3 |     fn convert<T: Into<f64>>(&self, x: T) -> f64;
   |        ^^^^^^^ ...because method `convert` has generic type parameters
   = help: consider moving `dup` to another trait
   = help: consider moving `convert` to another trait
   = help: only type `A` implements `Cloner`; consider using it directly instead.
```

(`A` یک struct خالی در برنامه‌ی من است که این trait را پیاده کرده.) خط‌به‌خط:

- **خط اول و سطر `^^^^^^`**: trait `Cloner` «dyn compatible» نیست و جای شکایت همان `dyn Cloner` در نوع `Vec` است. (در نسخه‌های قدیمی‌تر به این ویژگی «object safety» می‌گفتند؛ اسم جدیدتر در Rust Reference «dyn compatibility» است.)
- **`dup` برمی‌گرداند `Self`**: `Self` یعنی «همان نوع مشخصی که این trait را پیاده کرده». اگر فقط یک `dyn Cloner` دارید، نمی‌دانید `Self` چیست، پس نمی‌دانید نتیجه‌ی `dup` چند بایت است و کجا قرار می‌گیرد.
- **`convert` یک پارامتر نوع `T` دارد**: متد جنریک به‌ازای هر `T` یک نسخه‌ی جدا می‌خواهد، یعنی تعداد نامحدودی نسخه. vtable جدولی با تعداد ثابتی خانه است و جایی برای «هر نسخه‌ای که کسی بعداً لازم داشته باشد» ندارد.
- **سه خط `help`**: پیشنهادهای کامپایلر. اولی و دومی می‌گویند آن متد را به trait دیگری ببرید. سومی می‌گوید چون فقط یک نوع (`A`) این trait را پیاده کرده، شاید اصلاً `dyn` نخواهید و مستقیم `A` را به کار ببرید.

اگر می‌خواهید trait با `dyn` کار کند ولی همان متد برای نوع‌های مشخص باقی بماند، راهش گذاشتن `where Self: Sized` روی همان متد است. یعنی «این متد فقط وقتی نوع مشخص است وجود دارد» و از vtable بیرون می‌ماند. در `Shape` من همین کار را کردم: `fn scaled<T: Into<f64>>(&self, k: T) -> f64 where Self: Sized`. کامپایل می‌شود و `Square(2.0).scaled(3)` عدد `12` چاپ کرد (مساحت ۴ ضرب در ۳). ولی از طریق `dyn Shape` نمی‌شود `scaled` را صدا زد، چون آن متد در vtable نیست. همین راه برای `fn new() -> Self` هم جواب می‌دهد: یک برنامه‌ی کوچک با `fn new() -> Self where Self: Sized` در trait و یک `Box<dyn T>` کامپایل شد (تمرین ۳ همین را از شما می‌خواهد).

## رجیستری به سبک plugin

مثال واقعی‌تر: سیستمی که پیام را از چند کانال می‌فرستد و کانال‌ها را با اسمشان انتخاب می‌کنیم. اینجا نوع‌ها در زمان کامپایل مشخص نیستند و ممکن است بعداً کانال‌های بیشتری اضافه شود. این‌جا `dyn` طبیعی است:

```rust
trait Notifier: Send + Sync {
    fn send(&self, to: &str, msg: &str) -> String;
}

let mut reg: HashMap<&str, Box<dyn Notifier>> = HashMap::new();
reg.insert("email", Box::new(Email));
reg.insert("sms", Box::new(Sms { gateway: "gw1".into() }));
reg.insert("log", Box::new(LogOnly));
```

برنامه کلیدها را مرتب می‌کند و برای هرکدام `send("ali", "hello")` را صدا می‌زند:

```text
email to ali: hello
log: ali <- hello
sms via gw1 to ali: hello
```

هر کانال متن خودش را ساخته است، و `Sms` فیلد `gateway` را هم دارد که دیگران ندارند: هر نوع داده‌ی خودش را دارد و فقط یک رفتار مشترک دارند. اگر فردا کانال جدیدی لازم شود، فقط یک `impl Notifier for ...` و یک خط `insert` می‌خواهد و کد فرستنده دست نمی‌خورد.

`Send + Sync` در تعریف trait دو قید supertrait است و یعنی هر پیاده‌سازی باید بین thread‌ها قابل انتقال و اشتراک باشد (درباره‌ی {{< term "send-and-sync" "Send و Sync" >}} در [Concurrency با Thread در Rust](/fa/posts/rust-concurrency-threads/) صحبت کردیم). به همین دلیل رجیستری را در یک `Arc` گذاشتم و از یک thread جدا `send` را صدا زدم، و کار کرد (خط `thread: sms via gw1 to sara: hi`). قیدها را می‌شود روی خود object هم نوشت، مثل `Box<dyn Job + Send>`. وقتی عمداً یک `Rc<i32>` داخل نوعی گذاشتم که به‌عنوان `dyn Job + Send` به کار رفت، کامپایلر ردش کرد:

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
 --> src/bin/no_send.rs:6:34
  |
6 |     let b: Box<dyn Job + Send> = Box::new(J(Rc::new(1)));
  |                                  ^^^^^^^^^^^^^^^^^^^^^^^ `Rc<i32>` cannot be sent between threads safely
  |
  = help: within `J`, the trait `Send` is not implemented for `Rc<i32>`
note: required because it appears within the type `J`
 --> src/bin/no_send.rs:3:8
  |
3 | struct J(Rc<i32>);
  |        ^
```

معنی‌اش این است: شما قول داده‌اید که `J` به `Send` است (با نوشتن `+ Send`)، ولی `J` یک `Rc` در خود دارد و `Rc` به‌خاطر شمارنده‌ی غیراتمی‌اش `Send` نیست. کامپایلر قول را نمی‌پذیرد و ریشه‌ی مشکل (`struct J(Rc<i32>)`) را نشان می‌دهد.

## وقتی نوع مشخص را پس می‌خواهید: downcast با Any

گاهی بعد از فراموش کردن نوع، لازم می‌شود بپرسید «این واقعاً `Circle` بود؟». ابزارش trait استاندارد `Any` است. الگوی معمول این است که trait یک متد `as_any(&self) -> &dyn Any` داشته باشد و بعد `downcast_ref` را صدا بزنید:

```rust
match s.as_any().downcast_ref::<Circle>() {
    Some(c) => println!("it is a Circle, radius {}", c.0),
    None => println!("{} is not a Circle", s.name()),
}
```

```text
square is not a Circle
it is a Circle, radius 1
```

برای هر عنصر فهرست، `downcast_ref::<Circle>()` یا `Some` با reference به `Circle` برمی‌گرداند یا `None`. `Square` خط اول را می‌سازد و `Circle` خط دوم را. این کار می‌کند، ولی اگر مدام به آن نیاز دارید، یعنی دارید نوعی را که عمداً فراموش کرده بودید پس می‌گیرید. احتمالاً طراحی با یک enum مناسب‌تر است.

## enum، جنریک یا dyn؟

حالا که هر سه ابزار را دیدیم، چطور انتخاب کنیم؟ مثال را عوض می‌کنیم و سه سؤال می‌پرسیم.

**مجموعه‌ی نوع‌ها بسته است و خودتان می‌شناسیدش؟** مثلاً شکل‌های برنامه‌ی شما فقط `Square` و `Circle` است. یک `enum` بنویسید:

```rust
enum Shape {
    Square(Square),
    Circle(Circle),
}

impl Shape {
    fn area(&self) -> f64 {
        match self {
            Shape::Square(s) => s.0 * s.0,
            Shape::Circle(c) => 3.14 * c.0 * c.0,
        }
    }
}
```

این را در یک برنامه‌ی جدا اجرا کردم: با `vec![Shape::Square(Square(2.0)), Shape::Circle(Circle(1.0))]` جمع مساحت‌ها `total area = 7.14` چاپ شد. مزایایش: `match` را کامپایلر کامل‌بودن چک می‌کند (اگر فردا یک `Triangle` اضافه کنید و جایی را فراموش کنید، خطا می‌گیرید) و heap allocation لازم نیست. عیبش: هر کسی که شکل جدید می‌خواهد باید خود enum را عوض کند.

**هر فراخواننده در زمان کامپایل یک نوع را انتخاب می‌کند؟** مثلاً تابعی که یک شکل می‌گیرد و فقط با همان کار دارد. جنریک (`fn f<S: Shape>(s: &S)`) بهترین است: ساده است و dispatch ایستا می‌دهد.

**مجموعه باز است؟** یعنی plugin، handler‌هایی که کاربر کتابخانه می‌دهد، یا فهرستی که عنصرهایش از نوع‌های مختلف‌اند و کسی بعداً نوع جدید اضافه می‌کند. `dyn` برای همین است، و بهایش یک اشاره‌گر پهن و یک vtable است.

در Go مقدار interface همیشه یک جفت است: نوع و اشاره‌گر به داده. `dyn` از نظر ایده شبیه است، ولی Rust می‌خواهد `dyn` را صریح بنویسید و سازگاری با dyn را هم در زمان کامپایل چک می‌کند.

## خطاهای رایج با dyn

- **نوشتن نام trait بدون `dyn`.** در edition 2021 `Box<Shape>` خطای `E0782: expected a type, found a trait` می‌دهد و پیشنهاد می‌کند `dyn` را اضافه کنید: `Box<dyn Shape>`. این را هم در برنامه‌ی جدا امتحان کردم.
- **اشتباه گرفتن `Box<dyn Trait>` و `&dyn Trait`.** اولی مالک مقدار روی heap است و دومی فقط قرض می‌گیرد. هر کدام را که مالکیت لازم دارید بخواهید.
- **فراموش کردن `Send` و `Sync`.** برای جابه‌جایی یا اشتراک object بین thread‌ها باید `dyn Trait + Send + Sync` باشد، وگرنه کامپایلر رد می‌کند.
- **متدهای جنریک یا برگرداننده‌ی `Self`.** اگر نمی‌خواهید trait را از `dyn` بیندازید، `where Self: Sized` را روی همان متد بگذارید.
- **انتظار downcast برای هر نوعی.** `Any` فقط برای نوع‌های `'static` کار می‌کند، یعنی نوعی که reference کوتاه‌عمر در خودش ندارد.

## تمرین

1. یک `Triangle` به `Vec<Box<dyn Shape>>` اضافه کنید و جمع همه‌ی مساحت‌ها را چاپ کنید.
2. یک notifier به نام `"webhook"` به رجیستری اضافه کنید، بدون دست زدن به کدی که `send` را صدا می‌زند.
3. با متد `fn new() -> Self` عمداً trait را ناسازگار کنید و ببینید کدام `where` درستش می‌کند.

## قدم بعدی

«ماکروها در Rust»: کدی که کد می‌نویسد، از جمله همان `derive` و `println!` که تا حالا استفاده می‌کردیم.
