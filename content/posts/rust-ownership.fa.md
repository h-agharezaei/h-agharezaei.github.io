+++
date = '2026-11-08T10:00:00+03:30'
draft = false
title = 'Ownership در Rust'
description = 'مفهوم ownership در Rust با کد قابل اجرا: سه قانون، stack و heap، move، نوع‌های Copy، clone، تابع‌ها و Drop، همراه با خطای واقعی کامپایلر.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "ownership", "memory"]
cover = { image = "/images/covers/rust-ownership.fa.png", alt = "Ownership در Rust", hiddenInSingle = true }
+++

با دو خط کد شروع کنیم. در خط اول مقداری را در متغیر `a` می‌گذاریم و در خط دوم همان را به `b` می‌دهیم: `let b = a;`. بعد دوباره `a` را چاپ می‌کنیم. اگر `a` یک عدد `i32` باشد، همه‌چیز خوب است. اگر `a` یک `String` باشد، برنامه اصلاً کامپایل نمی‌شود و کامپایلر خطای E0382 می‌دهد. یک خط کد یکسان، دو نتیجه‌ی متفاوت. چرا؟

جواب، ایده‌ای است که اسمش {{< term "ownership" "ownership" >}} یا «مالکیت» است. در Go و Node.js چیزی شبیه آن نداریم. این همان ایده‌ای است که Rust با آن حافظه را بدون {{< term "garbage-collector" "garbage collector" >}} مدیریت می‌کند، و در هفته‌های اول یادگیری Rust بیشترین خطاهای کامپایلر مربوط به همین است. اگر هنوز با نوع‌ها و متغیرهای Rust آشنا نیستید، اول [نوع‌ها، متغیرها و کنترل جریان در Rust](/fa/posts/rust-types-control-flow/) را بخوانید. یادآوری آن مقاله که اینجا لازم می‌شود: متغیرها به‌طور پیش‌فرض تغییرناپذیرند و نوع هر مقدار در زمان کامپایل معلوم است.

> همه‌ی کدهای زیر را با Rust 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها از همان اجراها هستند. چند برنامه‌ی کوچک اضافه هم نوشتم که فقط برای نشان‌دادن یک خطا یا یک اندازه بودند؛ آن‌ها هم اجرا شده‌اند.

## مسئله: چه کسی حافظه را آزاد می‌کند؟

هر برنامه‌ای حافظه می‌گیرد و باید آن را پس بدهد. اگر پس ندهد، حافظه کم‌کم تمام می‌شود. اگر دو بار پس بدهد، یا بعد از پس‌دادن هنوز از آن استفاده کند، برنامه خراب می‌شود و حتی ممکن است ناامن شود. زبان‌ها سه جواب متفاوت داده‌اند:

- **دستی (مثل C):** خودتان `free` می‌زنید. سریع است، ولی فراموش‌کردن یا دوبار زدنش باگ‌های جدی می‌سازد.
- **با garbage collector (مثل Go و Node.js):** بخشی از runtime هر چند وقت یک‌بار می‌گردد و حافظه‌ای را که دیگر کسی به آن دسترسی ندارد آزاد می‌کند. راحت است، ولی هزینه‌ی کار را در زمان اجرا می‌پردازید.
- **Ownership (Rust):** قاعده‌هایی هست که کامپایلر بررسی می‌کند. کامپایلر از روی قاعده‌ها دقیقاً می‌داند حافظه کجا باید آزاد شود و خودش آن کد را اضافه می‌کند. هیچ garbage collector‌ای در کار نیست و هیچ `free` دستی هم نمی‌نویسید.

پس ownership جواب این سؤال است: «چه کسی و کِی حافظه را آزاد می‌کند؟». برای فهمیدنش اول باید ببینیم مقدارها کجا زندگی می‌کنند.

## Stack و heap، خیلی کوتاه

برنامه دو جای اصلی برای نگه‌داشتن مقدارها دارد. {{< term "stack-memory" "Stack" >}} یک جای مرتب و سریع است که هر فراخوانی تابع تکه‌ای از آن را می‌گیرد و با برگشتن تابع پس می‌دهد. فقط مقدارهایی روی آن می‌روند که اندازه‌شان در زمان کامپایل معلوم است، مثل عدد صحیح، `bool` یا آرایه‌ای با اندازه‌ی ثابت. {{< term "heap-memory" "Heap" >}} برای داده‌ای است که اندازه‌اش عوض می‌شود یا از قبل معلوم نیست، مثل متنی که کاربر تایپ می‌کند. از سیستم فضا می‌خواهید، آدرس آن فضا را می‌گیرید و هر وقت کارتان تمام شد باید پسش بدهید. (در [اشاره‌گر و حافظه در Go](/fa/posts/go-pointers-memory/) همین دو جا را از دید Go دیده‌ایم.)

ببینید `String` در Rust چطور ساخته شده. خود `String` یک تکه‌ی کوچک و ثابت روی stack است که سه چیز را نگه می‌دارد: آدرس بافری روی heap که حروف در آن است، طول متن، و ظرفیتِ آن بافر. برای اینکه این را ببینیم، اندازه‌اش را چاپ کردم:

```rust
fn main() {
    println!("i32: {} bytes", std::mem::size_of::<i32>());
    println!("String: {} bytes", std::mem::size_of::<String>());
    let s = String::from("salam");
    println!("len = {}, capacity >= len: {}", s.len(), s.capacity() >= s.len());
}
```

```text
i32: 4 bytes
String: 24 bytes
len = 5, capacity >= len: true
```

`String` همیشه ۲۴ بایت است، چه متنش یک حرف باشد چه یک میلیون حرف، چون این ۲۴ بایت فقط همان سه چیز (دو عدد و یک آدرس، هرکدام ۸ بایت روی این دستگاه ۶۴ بیتی) است. خود حروف جای دیگری، روی heap، هستند. پس `String` در حقیقت «دسته‌کلید» یک تکه حافظه‌ی heap است. این نکته برای ادامه مهم است.

## سه قانون

Rust ownership را با سه قانون ساده تعریف می‌کند:

1. هر مقدار (value) یک **owner** (مالک) دارد، یعنی یک متغیر که صاحب آن است.
2. در هر لحظه فقط و فقط یک owner وجود دارد.
3. وقتی owner از scope خارج شود، مقدار **drop** می‌شود، یعنی حافظه‌اش آزاد می‌شود.

scope همان محدوده‌ی آکولادهایی است که متغیر در آن تعریف شده. قانون سوم یعنی هیچ‌وقت `free` نمی‌زنید: به آکولاد بسته که برسیم، کامپایلر خودش کد آزادکردن را آنجا گذاشته است. قانون دوم دلیل وجود قانون‌هاست. اگر دو متغیر هر دو خودشان را صاحب همان بافر heap بدانند، هر دو هنگام خروج از scope آن را آزاد می‌کنند و یک حافظه دو بار آزاد می‌شود (به این باگ **double free** می‌گویند). با «فقط یک owner» این اتفاق محال می‌شود.

کل مدل همین است. بقیه‌ی مقاله این است که این سه قانون در عمل چه می‌کنند.

## String و &str

برای مثال‌های بعدی باید دو نوع رشته را از هم جدا کنیم. یک literal مثل `"hello"` از نوع `&str` است: فقط‌خواندنی و متنش داخل خود برنامه نوشته شده است. اما `String` همان نوعی است که بالا دیدیم: صاحب یک بافر قابل رشد روی heap. با `to_string()` یا `String::from` می‌شود از اولی دومی ساخت:

```rust
let lit: &str = "hello";
let owned: String = lit.to_string();
println!("{lit} {owned}");
// hello hello
```

فعلاً همین‌قدر کافی است: `String` صاحب داده‌اش است. علامت `&` در `&str` یعنی «قرض‌گرفتن» (borrow) که موضوع مقاله‌ی بعد است.

## Move: انتقال مالکیت

حالا به سؤال اول برگردیم. برنامه‌ی زیر همان دو خط را با `String` نوشته:

```rust
fn main() {
    let a = String::from("salam");
    let b = a;
    println!("{a}");
    println!("{b}");
}
```

ابتدا فکر کنید `let b = a` چه می‌کند. فقط همان ۲۴ بایت (آدرس، طول، ظرفیت) را در `b` می‌گذارد. حروف روی heap کپی نمی‌شوند. حالا اگر `a` و `b` هر دو معتبر می‌ماندند، هر دو به یک بافر اشاره می‌کردند و هر دو در پایان آن را آزاد می‌کردند: همان double free. Rust برای جلوگیری از آن می‌گوید مالکیت از `a` به `b` **منتقل (move)** شد و `a` دیگر معتبر نیست. به همین دلیل این کد کامپایل نمی‌شود:

```text
error[E0382]: borrow of moved value: `a`
 --> src/bin/moved.rs:4:16
  |
2 |     let a = String::from("salam");
  |         - move occurs because `a` has type `String`, which does not implement the `Copy` trait
3 |     let b = a;
  |             - value moved here
4 |     println!("{a}");
  |                ^ value borrowed here after move
  |
  = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
help: consider cloning the value if the performance cost is acceptable
  |
3 |     let b = a.clone();
  |              ++++++++

For more information about this error, try `rustc --explain E0382`.
error: could not compile `rust-ownership` (bin "moved") due to 1 previous error
```

این پیام داستان را به ترتیب زمان تعریف می‌کند. بخوانیم:

- عنوان: `borrow of moved value: a`، یعنی «از مقداری که move شده، استفاده شد». (کلمه‌ی borrow به این دلیل است که `println!` برای چاپ، مقدار را فقط قرض می‌گیرد.)
- خط ۲: `a` از نوع `String` است و چون `String` ویژگی `Copy` ندارد (کمی پایین‌تر توضیح می‌دهم)، انتساب آن move می‌شود.
- خط ۳: «value moved here»، یعنی همین‌جا مالکیت به `b` رفت.
- خط ۴: `println!("{a}")` به `a` دست می‌زند، بعد از اینکه move شده بود.
- خط `= note` درباره‌ی ماکروی `println` است و مربوط به ریشه‌ی خطا نیست؛ فقط می‌گوید خطا از داخل آن ماکرو دیده شده.
- `help`: اگر واقعاً دو رشته‌ی مستقل می‌خواهید، `a.clone()` بنویسید.

در Go اگر slice را به متغیر دیگری بدهید، هر دو به همان آرایه‌ی پشتی اشاره می‌کنند و هر دو معتبر می‌مانند. Rust این وضعیت را در زمان کامپایل نمی‌پذیرد، چون معلوم نیست حافظه را چه کسی آزاد کند.

## نوع‌های Copy و clone

پس چرا همین کد با `i32` کامپایل می‌شود؟ چون مقدارهای ساده‌ای مثل عدد، کلاً روی stack‌اند و کپی‌کردنشان ارزان و بی‌خطر است: هیچ بافر heap‌ای نیست که دوبار آزاد شود. این نوع‌ها ویژگی (trait) به اسم `Copy` دارند؛ برای آن‌ها انتساب یک کپی کامل می‌سازد و هر دو متغیر معتبر می‌مانند:

```rust
let x = 5;
let y = x;
println!("x = {x}, y = {y}");
// x = 5, y = 5
```

عددهای صحیح و اعشاری، `bool` و `char` از نوع `Copy` هستند، اما `String` نه. اگر از یک `String` واقعاً دو نسخه‌ی مستقل می‌خواهید، باید صریحاً `.clone()` بنویسید. clone یک کپی کامل می‌سازد: بافر جدیدی روی heap می‌گیرد و حروف را در آن کپی می‌کند.

```rust
let c = b.clone();
println!("b = {b}, c = {c}");
// b = salam, c = salam
```

اینکه Rust این کار را صریح کرده عمدی است: کپی گران باید در کد دیده شود، نه اینکه پشت یک `=` ساده پنهان باشد.

## Ownership و تابع‌ها

دادن یک مقدار به تابع هم مثل انتساب است. پارامتر تابع مالک جدید می‌شود. تابع‌های زیر را ببینید:

```rust
fn take(s: String) -> usize {
    s.len()
}

fn take_and_give_back(s: String) -> (String, usize) {
    let n = s.len();
    (s, n)
}
```

`take` رشته را می‌گیرد، طولش را برمی‌گرداند و در پایان تابع، `s` از scope خارج می‌شود و حافظه‌اش آزاد می‌شود. پس بعد از `take(s)` نمی‌توانید از `s` استفاده کنید:

```rust
fn main() {
    let s = String::from("rust");
    let n = take(s);
    println!("{n}");
    println!("{s}");
}
```

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/fnmove.rs:9:16
  |
6 |     let s = String::from("rust");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
7 |     let n = take(s);
  |                  - value moved here
8 |     println!("{n}");
9 |     println!("{s}");
  |                ^ value borrowed here after move
  |
note: consider changing this parameter type in function `take` to borrow instead if owning the value isn't necessary
 --> src/bin/fnmove.rs:1:12
  |
1 | fn take(s: String) -> usize {
  |    ----    ^^^^^^ this parameter takes ownership of the value
  |    |
  |    in this function
  = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
help: consider cloning the value if the performance cost is acceptable
  |
7 |     let n = take(s.clone());
  |                   ++++++++

For more information about this error, try `rustc --explain E0382`.
error: could not compile `rust-ownership` (bin "fnmove") due to 1 previous error
```

همان داستان قبل است: مالکیت در خط ۷ به `take` رفت. این بار کامپایلر یک پیشنهاد هم دارد (`note`): اگر `take` لازم نیست مالک رشته باشد، پارامترش را طوری عوض کنید که قرض بگیرد. دقیقاً همین راه درست است و مقاله‌ی بعد آن را توضیح می‌دهد. (این خطا را با یک برنامه‌ی کوچک جداگانه گرفته‌ام که فقط `take` و همین `main` را دارد.)

راه دیگر این است که تابع مالکیت را پس بدهد، مثل `take_and_give_back` که رشته را به‌همراه جواب برمی‌گرداند:

```rust
let s2 = String::from("ownership");
let (s2, n2) = take_and_give_back(s2);
println!("{s2} has {n2} bytes");
```

این کار می‌کند، چون `s2` تازه دوباره مالک می‌شود (همان shadowing که در مقاله‌ی قبل دیدیم). ولی فقط برای اینکه از داده‌ی خودمان دوباره استفاده کنیم، رفت‌وبرگشت دادن و برگرداندن tuple خیلی زود خسته‌کننده می‌شود. Borrowing در مقاله‌ی بعد این رفت‌وبرگشت را حذف می‌کند.

## Drop: دیدن لحظه‌ی آزادشدن

قانون سوم می‌گوید مقدار وقتی owner‌اش از scope خارج شد drop می‌شود. این اتفاق معمولاً نامرئی است. ولی Rust اجازه می‌دهد یک نوع، کدی داشته باشد که دقیقاً در لحظه‌ی drop اجرا شود (با پیاده‌سازی trait به اسم `Drop`). از این امکان استفاده می‌کنیم تا لحظه‌ی آزادشدن را ببینیم. نوع `Noisy` هر وقت drop شود اسمش را چاپ می‌کند:

```rust
struct Noisy(&'static str);

impl Drop for Noisy {
    fn drop(&mut self) {
        println!("drop {}", self.0);
    }
}

fn consume(n: Noisy) {
    println!("inside consume({})", n.0);
}

fn main() {
    let _first = Noisy("first");
    let _second = Noisy("second");
    {
        let _inner = Noisy("inner");
        println!("end of inner block");
    }
    let third = Noisy("third");
    consume(third);
    println!("end of main");
}
```

(اسم متغیرهایی که با `_` شروع می‌شوند به کامپایلر می‌گوید عمداً استفاده‌شان نمی‌کنیم و هشدار نمی‌دهد؛ ولی متغیرها تا پایان scope زنده‌اند.) خروجی:

```text
end of inner block
drop inner
inside consume(third)
drop third
end of main
drop second
drop first
```

خط به خط:

- `end of inner block` و بعد `drop inner`: `_inner` با بسته‌شدن آکولاد بلوک داخلی drop شد، یعنی بعد از چاپ آن خط.
- `inside consume(third)`: `third` را به تابع دادیم و تابع مالک آن شد.
- `drop third`: تابع که تمام شد، `n` از scope بیرون رفت و مقدار drop شد. دقت کنید که این خط قبل از `end of main` است، یعنی `third` در `main` drop نشد، چون دیگر مال `main` نبود.
- `end of main`، و بعد در پایان `main` باقی متغیرها drop می‌شوند، به ترتیب عکسِ تعریف: اول `second` و بعد `first`.

## اشتباه‌های رایج با move

- **Move فقط مخصوص `let` نیست.** دادن به تابع، گذاشتن مقدار در یک `Vec` و برگرداندن از یک بلوک هم move هستند.
- **هر بار که کامپایلر خطا داد، سراغ `.clone()` نروید.** کار می‌کند، ولی یک کپی را پنهان می‌کند و معمولاً علامت این است که طراحی کد باید به‌جای مالکیت، borrow بخواهد.
- **Move روی نوع‌های heap ارزان است.** فقط همان سه فیلد (آدرس، طول، ظرفیت) جابه‌جا می‌شوند و بافر heap کپی نمی‌شود.
- **مقایسه با Go.** garbage collector در زمان اجرا حافظه را برایتان آزاد می‌کند، به قیمت کمی سربار و زمان‌بندی کمتر قابل پیش‌بینی، و در ابتدا چیزی برای یاد گرفتن ندارد. Rust این تصمیم را در زمان کامپایل می‌گیرد، که هزینه‌اش یادگیری و گاهی تغییر ساختار کد است، ولی collector نمی‌خواهد. هیچ‌کدام مطلقاً بهتر نیست؛ مصالحه‌های متفاوتی هستند.
- **`Drop` سر پایان scope اجرا می‌شود، نه «یک وقت بعداً».** برای همین برای بستن فایل و آزادکردن lock هم استفاده می‌شود.

## تمرین

۱. برنامه‌ی `let b = a;` را با `a` از نوع `String` بنویسید، خطای E0382 را ببینید و بعد با `.clone()` درستش کنید.
۲. نوع `a` را `i32` کنید و ببینید چرا بدون هیچ تغییر دیگری کامپایل می‌شود.
۳. یک `Noisy` چهارم کنار `_inner` در بلوک داخلی اضافه کنید و ترتیب drop را قبل از اجرا حدس بزنید.

## قدم بعدی

«Borrowing و Reference در Rust». جابه‌جاکردن مقدار برای ورود و خروج از تابع‌ها دست‌وپاگیر است. در مقاله‌ی بعد می‌بینیم چطور تابع بدون گرفتن مالکیت از مقدار استفاده کند.
