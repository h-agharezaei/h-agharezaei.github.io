+++
date = '2026-11-08T10:00:00+03:30'
draft = false
title = 'Ownership در Rust'
description = 'مفهوم ownership در Rust با کد قابل اجرا: سه قانون، stack و heap، move، نوع‌های Copy، clone، تابع‌ها و Drop، همراه با خطای واقعی کامپایلر.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "ownership", "memory"]
cover = { image = "/images/covers/rust-ownership.fa.png", alt = "Ownership در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-types-control-flow/) با نوع‌ها، متغیرها و ساختارهای کنترلی Rust آشنا شدیم؛ چیزهایی که برای کسی که از Go یا Node.js می‌آید آشناست. **Ownership** این‌طور نیست. این همان ایده‌ای است که Rust با آن حافظه را بدون garbage collector مدیریت می‌کند، و در هفته‌های اول بیشترین خطای کامپایلر مربوط به همین است.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها از همان اجراها کپی شده‌اند.

## سه قانون

1. هر مقدار (value) دقیقاً یک **owner** دارد.
2. در هر لحظه فقط یک owner وجود دارد.
3. وقتی owner از scope خارج شود، مقدار **drop** می‌شود (حافظه‌اش آزاد می‌شود).

کل مدل همین است. بقیه‌ی مقاله این است که این سه قانون در عمل چه معنایی دارند.

## Stack و heap، خیلی کوتاه

**Stack** جای مقدارهایی است که اندازه‌شان در زمان کامپایل معلوم است (عدد صحیح، boolean، آرایه‌ی با اندازه‌ی ثابت). گذاشتن و برداشتن از آن ارزان است. **Heap** جای داده‌ای است که اندازه‌اش تغییر می‌کند یا از قبل معلوم نیست، مثل متن داخل یک رشته. از allocator فضا می‌گیرید، یک pointer پس می‌گیرید و کسی باید بعداً آن را آزاد کند. Ownership جواب این سؤال است که «چه کسی و کِی آزادش می‌کند؟».

## String و &str

یک literal مثل `"hello"` از نوع `&str` است: نمایی فقط‌خواندنی از متنی که داخل خود برنامه قرار دارد. اما `String` صاحب یک بافر قابل رشد روی heap است. تبدیل با `to_string()` یا `String::from` انجام می‌شود:

```rust
let lit: &str = "hello";
let owned: String = lit.to_string();
println!("{lit} {owned}");
// hello hello
```

فعلاً همین‌قدر بدانید که `String` نوعِ دارای مالکیت است. علامت `&` در `&str` یک borrow است که موضوع مقاله‌ی بعد است.

## Move

```rust
fn main() {
    let a = String::from("salam");
    let b = a;
    println!("{a}");
    println!("{b}");
}
```

این کد کامپایل نمی‌شود:

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
help: consider cloning the value if the performance cost is acceptable
  |
3 |     let b = a.clone();
  |              ++++++++
```

`let b = a` رشته را کپی نمی‌کند؛ مالکیت را به `b` **منتقل (move)** می‌کند و `a` دیگر قابل استفاده نیست. دلیلش جلوگیری از double free است: فقط یک متغیر بافر را آزاد می‌کند. در Go اگر یک slice را به متغیر دیگر بدهید، هر دو به همان آرایه‌ی پشتی اشاره می‌کنند و هر دو معتبر می‌مانند؛ Rust این را در زمان کامپایل نمی‌پذیرد.

## نوع‌های Copy و clone

مقدارهای ساده‌ی روی stack ویژگی `Copy` را دارند؛ پس انتساب آن‌ها را کپی می‌کند و هر دو متغیر معتبر می‌مانند:

```rust
let x = 5;
let y = x;
println!("x = {x}, y = {y}");
// x = 5, y = 5
```

عددهای صحیح و اعشاری، `bool` و `char` از نوع `Copy` هستند، اما `String` نه. اگر واقعاً دو رشته‌ی مستقل می‌خواهید، آن را صریحاً با `.clone()` بگویید؛ یک کپی عمیق که حافظه‌ی جدید روی heap می‌گیرد:

```rust
let c = b.clone();
println!("b = {b}, c = {c}");
// b = salam, c = salam
```

صریح بودن همین‌جا مهم است: کپی گران در کد دیده می‌شود.

## Ownership و تابع‌ها

دادن یک مقدار به تابع هم مثل انتساب، آن را move می‌کند. برگرداندن مقدار، مالکیت را پس می‌دهد:

```rust
fn take(s: String) -> usize { s.len() }

fn take_and_give_back(s: String) -> (String, usize) {
    let n = s.len();
    (s, n)
}
```

بعد از `take(s)` دیگر نمی‌توانید از `s` استفاده کنید. با `take_and_give_back` رشته را پس می‌گیرید، اما فقط برای اینکه از داده‌ی خودمان دوباره استفاده کنیم tuple برگرداندن خیلی زود خسته‌کننده می‌شود. Borrowing که موضوع مقاله‌ی بعد است، این رفت‌وبرگشت را حذف می‌کند.

## Drop: دیدن لحظه‌ی آزاد شدن

یک نوع می‌تواند با پیاده‌سازی `Drop` وقتی owner‌اش از بین می‌رود کدی اجرا کند:

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

خروجی:

```text
end of inner block
drop inner
inside consume(third)
drop third
end of main
drop second
drop first
```

`inner` در آکولاد بستنِ بلوکش drop می‌شود. `third` وقتی `consume` تمام می‌شود drop می‌شود، چون تابع مالک آن بود. در پایان `main`، متغیرهای محلی به ترتیب عکسِ تعریف drop می‌شوند: اول `second` و بعد `first`.

## چند نکته

- Move فقط مخصوص `let` نیست. دادن به تابع، گذاشتن در `Vec` و برگرداندن از یک بلوک هم move هستند.
- هر بار که کامپایلر خطا داد سراغ `.clone()` نروید. کار می‌کند، اما یک کپی را پنهان می‌کند و معمولاً یعنی طراحی کد borrow می‌خواهد.
- Move روی نوع‌های heap فقط بخش کوچک pointer/length/capacity را روی stack کپی می‌کند؛ بافر heap کپی نمی‌شود.
- مقایسه با Go: garbage collector در زمان اجرا حافظه را برایتان آزاد می‌کند، به قیمت کمی سربار و زمان‌بندی کمتر قابل پیش‌بینی، و در ابتدا چیزی برای یاد گرفتن ندارد. Rust این تصمیم را در زمان کامپایل می‌گیرد، که هزینه‌اش یادگیری و گاهی تغییر ساختار کد است، ولی collector نمی‌خواهد. هیچ‌کدام مطلقاً بهتر نیست؛ مصالحه‌های متفاوتی هستند.
- `Drop` سرِ پایان scope اجرا می‌شود، نه «یک وقت بعداً»؛ برای همین برای بستن فایل و آزاد کردن lock هم استفاده می‌شود.

## تمرین

1. برنامه‌ی `let b = a;` را با `a` از نوع `String` بنویسید، خطای E0382 را ببینید و بعد با `.clone()` درستش کنید.
2. نوع `a` را `i32` کنید و ببینید چرا بدون هیچ تغییر دیگری کامپایل می‌شود.
3. یک `Noisy` چهارم کنار `_inner` در بلوک داخلی اضافه کنید و ترتیب drop را قبل از اجرا حدس بزنید.

## قدم بعدی

جابه‌جا کردن مقدار برای ورود و خروج از تابع‌ها دست‌وپاگیر است. در مقاله‌ی بعد، یعنی borrowing و reference در Rust، می‌بینیم چطور یک تابع بدون گرفتن مالکیت از مقدار استفاده کند.
