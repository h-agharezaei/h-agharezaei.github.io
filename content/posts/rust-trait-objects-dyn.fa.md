+++
date = '2027-02-08T10:00:00+03:30'
draft = false
title = 'Trait Object و dyn در Rust'
description = 'Trait object و dyn در Rust: Box<dyn Trait>، dispatch ایستا و پویا، fat pointer، خطای E0038، downcast با Any و انتخاب بین enum، generics و dyn.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "traits", "dyn", "intermediate"]
cover = { image = "/images/covers/rust-trait-objects-dyn.fa.png", alt = "Trait Object و dyn در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-nats-async-client/) Worker ِRust پیام‌های یک برنامه‌ی Go را مصرف کرد. پیش‌تر مقاله‌های gRPC با یک سؤال تمام شدند: Rust چطور چندریختی زمان اجرا را بسازد، همان چیزی که در Go با interface مجانی داریم؟ در [جنریک‌ها و trait‌ها](/fa/posts/rust-generics-traits/) dispatch ایستا را دیدیم، جایی که هر نوع مشخص نسخه‌ی خودش از کد را می‌گیرد. این مقاله نیمه‌ی دیگر است: **trait object** که به شکل `dyn Trait` نوشته می‌شود و اجازه می‌دهد یک `Vec` یا یک `HashMap` نوع‌های مختلف را نگه دارد. طرف Go ماجرا در [struct، متد و interface](/fa/posts/go-structs-methods-interfaces/) آمده است.

> همه‌ی کدها با Rust 1.90 اجرا شدند. ادعایی درباره‌ی کارایی نمی‌کنم؛ فقط اندازه‌ها و خروجی کامپایلر را نشان می‌دهم.

## مسئله و راه‌حل

`Vec<T>` جنریک دقیقاً یک `T` دارد و نمی‌توانید `Square` و `Circle` را با هم در آن بگذارید. با `Box<dyn Shape>` می‌شود، چون نوع عنصر حالا «هر Boxی که `Shape` را پیاده کرده» است:

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

`trait Shape: Debug` یک **supertrait** است: هر `Shape` باید `Debug` هم باشد و برای همین `{:?}` روی trait object کار می‌کند. همین ایده پشت pointer‌های دیگر هم کار می‌کند: `&dyn Shape` قرض می‌گیرد و `Rc<dyn Shape>` مالکیت را مشترک می‌کند (یکی را clone کردم و `Rc::strong_count` عدد `2` چاپ کرد).

## Dispatch ایستا در برابر پویا

```rust
fn print_static<S: Shape>(s: &S) { /* ... */ }   // جنریک
fn print_dyn(s: &dyn Shape) { /* ... */ }        // trait object
```

در تابع جنریک کامپایلر **monomorphization** انجام می‌دهد: برای هر نوع مشخص یک نسخه از `print_static` می‌سازد و فراخوانی در زمان کامپایل تعیین می‌شود. با `&dyn Shape` فقط یک نسخه از `print_dyn` وجود دارد و متد در زمان اجرا از **vtable** پیدا می‌شود، جدول کوچکی از function pointerها برای همان نوع مشخص. حاصل: یک نسخه از کد و امکان قاطی کردن نوع‌ها، به قیمت یک فراخوانی غیرمستقیم از طریق جدول.

## Fat pointer

ارجاع به trait object باید هم آدرس داده را داشته باشد و هم آدرس vtable:

```text
&i32               = 8
&dyn Shape         = 16
Box<dyn Shape>     = 16
Box<Square>        = 8
```

این‌ها بایت‌های ماشین ۶۴ بیتی من هستند. `&dyn Trait` یک **fat pointer** است: دو کلمه به‌جای یکی.

## سازگاری با dyn (E0038)

هر trait‌ای trait object نمی‌شود. vtable برای هر متد یک امضای ثابت لازم دارد، پس متدی که `Self` برمی‌گرداند یا پارامتر نوع خودش را دارد در آن جا نمی‌شود. هر دو را امتحان کردم:

```text
error[E0038]: the trait `Cloner` is not dyn compatible
 1 | trait Cloner {
   |       ------ this trait is not dyn compatible...
 2 |     fn dup(&self) -> Self;
   |                      ^^^^ ...because method `dup` references the `Self` type in its return type
 3 |     fn convert<T: Into<f64>>(&self, x: T) -> f64;
   |        ^^^^^^^ ...because method `convert` has generic type parameters
```

اگر می‌خواهید trait با `dyn` قابل استفاده بماند ولی چنین متدی برای نوع‌های مشخص باقی بماند، راهش `where Self: Sized` روی همان متد است. در `Shape` این را اضافه کردم: `fn scaled<T: Into<f64>>(&self, k: T) -> f64 where Self: Sized`. کامپایل می‌شود و `Square(2.0).scaled(3)` عدد `12` چاپ کرد، ولی از طریق `dyn Shape` نمی‌شود صدایش زد.

## رجیستری به سبک plugin

```rust
trait Notifier: Send + Sync {
    fn send(&self, to: &str, msg: &str) -> String;
}

let mut reg: HashMap<&str, Box<dyn Notifier>> = HashMap::new();
reg.insert("email", Box::new(Email));
reg.insert("sms", Box::new(Sms { gateway: "gw1".into() }));
reg.insert("log", Box::new(LogOnly));
```

```text
email to ali: hello
log: ali <- hello
sms via gw1 to ali: hello
```

اینجا `Send + Sync` قید supertrait روی خود trait است. می‌توانید روی object هم بنویسید، مثل `Box<dyn Job + Send>`. رجیستری را در `Arc` گذاشتم و از یک thread جدا `send` را صدا زدم و کار کرد. وقتی یک `Rc<i32>` داخل پیاده‌سازی‌ای از `dyn Job + Send` گذاشتم، کامپایلر رد کرد: `Rc<i32>` cannot be sent between threads safely.

## Downcast با Any

گاهی باید نوع مشخص را پس بگیرید. الگوی معمول متد `as_any(&self) -> &dyn Any` و بعد `downcast_ref` است:

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

اگر زیاد به این نیاز دارید، احتمالاً طراحی یک enum می‌خواهد.

## enum، جنریک یا dyn؟

- **enum**: مجموعه‌ی حالت‌ها بسته است و خودتان می‌شناسیدش. exhaustiveness در `match` و بدون تخصیص heap.
- **جنریک**: هر فراخواننده در زمان کامپایل یک نوع را انتخاب می‌کند (پارامتر تابع، فیلد struct).
- **dyn**: مجموعه باز است (plugin، handler‌هایی که کاربر می‌دهد) یا کلکسیون ناهمگن لازم دارید و یک pointer و vtable را می‌پذیرید.

در Go مقدار interface یک جفت است: نوع و pointer به داده. ارجاع `dyn` از نظر ایده شبیه است، ولی Rust می‌خواهد `dyn` را صریح بنویسید و سازگاری با dyn را در زمان کامپایل چک می‌کند.

## چند نکته

- در edition 2021 نام trait به‌تنهایی در جای نوع خطا است؛ `dyn Trait` بنویسید.
- `Box<dyn Trait>` مالک مقدار روی heap است و `&dyn Trait` قرض می‌گیرد؛ هر کدام که مالکیت لازم دارید.
- برای جابه‌جایی یا اشتراک object بین thread‌ها `dyn Trait + Send + Sync` لازم است.
- متدهای جنریک یا برگرداننده‌ی `Self` برای هم‌زیستی با `dyn` به `where Self: Sized` نیاز دارند.
- downcast با `Any` فقط برای نوع‌های `'static` کار می‌کند.

## تمرین

1. یک `Triangle` به `Vec<Box<dyn Shape>>` اضافه کنید و جمع همه‌ی مساحت‌ها را چاپ کنید.
2. یک notifier به نام `"webhook"` به رجیستری اضافه کنید، بدون دست زدن به کدی که `send` را صدا می‌زند.
3. با متد `fn new() -> Self` عمداً trait را ناسازگار کنید و ببینید کدام `where` درستش می‌کند.

## قدم بعدی

مقاله‌ی بعد: macroها در Rust، کدی که کد می‌نویسد، از جمله `derive` و `println!` که تا حالا استفاده می‌کردیم.
