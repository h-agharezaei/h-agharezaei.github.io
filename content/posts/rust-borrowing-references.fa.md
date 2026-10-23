+++
date = '2026-11-14T10:00:00+03:30'
draft = false
title = 'Borrowing و Reference در Rust'
description = 'مفهوم borrowing و reference در Rust با کد قابل اجرا: &T و &mut T، قانون چند خواننده یا یک نویسنده، NLL، dangling reference، slice و خطاهای واقعی.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "borrowing", "references"]
cover = { image = "/images/covers/rust-borrowing-references.fa.png", alt = "Borrowing و Reference در Rust", hiddenInSingle = true, hiddenInList = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-ownership/) به یک الگوی دست‌وپاگیر رسیدیم: یک `String` را به تابع بدهیم و فقط برای اینکه بتوانیم دوباره از آن استفاده کنیم، پسش بگیریم. **Borrowing** راه‌حل است. به تابع یک reference می‌دهید، تابع از مقدار استفاده می‌کند و مالکیت جابه‌جا نمی‌شود. در این مقاله دو نوع reference، تنها قانون حاکم بر آن‌ها و خطاهای کامپایلری را می‌بینیم که حین یادگیری با آن‌ها روبه‌رو می‌شوید.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و خطاها از همان اجراها کپی شده‌اند.

## Reference اشتراکی و تغییرپذیر

`&T` یک **shared reference** است: می‌توانید از طریق آن بخوانید. `&mut T` یک **mutable reference** است: می‌توانید بخوانید و مقدار را عوض کنید. ساختن هرکدام را **borrow** کردن می‌گویند.

```rust
fn length(s: &String) -> usize {
    s.len()
}

fn add_exclaim(s: &mut String) {
    s.push('!');
}

fn main() {
    let mut s = String::from("salam");
    let n = length(&s);
    println!("{s} has {n} bytes");

    add_exclaim(&mut s);
    println!("{s}");

    // many readers at once is fine
    let r1 = &s;
    let r2 = &s;
    println!("{r1} {r2}");
}
```

خروجی:

```text
salam has 5 bytes
salam!
salam! salam!
```

با مقاله‌ی قبل مقایسه کنید: `length` مالکیت را نمی‌گیرد، پس `s` بعد از آن هنوز مال ماست و دیگر tuple‌ای برای برگرداندن لازم نیست. توجه کنید برای نوشتن `&mut s` باید خود متغیر `mut` تعریف شده باشد.

## قانون: چند خواننده یا یک نویسنده

در هر لحظه یا هر تعداد `&T` دارید، یا دقیقاً یک `&mut T`؛ هر دو با هم نه. کل قانون borrowing همین است و باعث می‌شود کامپایلر تضمین کند وقتی کسی در حال خواندن است، دیگری داده را تغییر نمی‌دهد.

اول دو نویسنده:

```rust
fn main() {
    let mut s = String::from("salam");
    let a = &mut s;
    let b = &mut s;
    a.push('1');
    b.push('2');
    println!("{s}");
}
```

```text
error[E0499]: cannot borrow `s` as mutable more than once at a time
 --> src/bin/two_mut.rs:4:13
  |
3 |     let a = &mut s;
  |             ------ first mutable borrow occurs here
4 |     let b = &mut s;
  |             ^^^^^^ second mutable borrow occurs here
5 |     a.push('1');
  |     - first borrow later used here
```

حالا خواننده‌ای که هنوز زنده است، در حالی که داده را تغییر می‌دهیم:

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    v.push(4);
    println!("first = {first}");
}
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/bin/mutate_while_shared.rs:4:5
  |
3 |     let first = &v[0];
  |                  - immutable borrow occurs here
4 |     v.push(4);
  |     ^^^^^^^^^ mutable borrow occurs here
5 |     println!("first = {first}");
  |                        ----- immutable borrow later used here
```

مورد دوم جالب‌تر است. `push` ممکن است بافر vector را دوباره allocate کند و آن‌وقت `first` به حافظه‌ی آزادشده اشاره می‌کرد. Rust برنامه را قبل از رسیدن به آن لحظه رد می‌کند.

## Borrow با آخرین استفاده تمام می‌شود

Borrow تا آکولاد بسته دوام ندارد؛ تا آخرین باری که reference استفاده شده ادامه دارد. به این ویژگی **non-lexical lifetimes** (به اختصار NLL) می‌گویند. این برنامه یک borrow اشتراکی و یک borrow تغییرپذیر از یک متغیر دارد و کامپایل می‌شود:

```rust
fn main() {
    let mut s = String::from("salam");
    let r = &s;
    println!("reader sees {r}");
    // r is not used after this point, so the borrow has ended
    let w = &mut s;
    w.push_str(" donya");
    println!("{s}");
}
```

```text
reader sees salam
salam donya
```

اگر بعد از `push_str` یک `println!("{r}")` اضافه کنید، همان خطای E0502 قبلی را می‌گیرید. وقتی کامپایلر ایراد می‌گیرد، دنبال برچسب «later used here» بگردید: به استفاده‌ای اشاره می‌کند که borrow را زنده نگه داشته است.

## Reference نباید dangling شود

یک reference هرگز نباید بیشتر از مقداری که به آن اشاره می‌کند عمر کند. این تابع می‌خواهد reference به متغیر محلی خودش را برگرداند:

```rust
fn dangle() -> &String {
    let s = String::from("salam");
    &s
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/dangle.rs:1:16
  |
1 | fn dangle() -> &String {
  |                ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but there is no value for it to be borrowed from
help: consider using the `'static` lifetime, but this is uncommon unless you're returning a borrowed value from a `const` or a `static`
  |
1 | fn dangle() -> &'static String {
  |                 +++++++
help: instead, you are more likely to want to return an owned value
  |
1 - fn dangle() -> &String {
1 + fn dangle() -> String {
  |
```

پیشنهاد دوم کامپایلر درست است: خود `String` را برگردانید و مالکیت بیرون برود. اگر برای ساکت کردن E0106 یک اسم lifetime اضافه کنید (`fn dangle<'a>() -> &'a String`) به خطای عمیق‌تر می‌رسید:

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/dangle2.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function

```

`s` وقتی تابع تمام می‌شود drop می‌شود، پس reference به هیچ‌چیز اشاره می‌کرد. Lifetime‌ها را بعداً در همین سری جدی‌تر بررسی می‌کنیم.

## Slice: نمای قرض‌گرفته‌شده

`&str` یک نمای borrow شده از داده‌ی یک رشته است و `&[T]` نمای borrow شده از یک ردیف عنصر. این‌ها هم reference هستند و همان قوانین را دارند، و تابعی که آن‌ها را بگیرد ورودی‌های بیشتری را می‌پذیرد:

```rust
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

fn sum(xs: &[i32]) -> i32 {
    xs.iter().sum()
}

fn main() {
    let text = String::from("salam donya");
    println!("{}", first_word(&text));
    println!("{}", first_word("hello rust"));

    let v = vec![1, 2, 3, 4, 5];
    println!("{}", sum(&v));
    println!("{}", sum(&v[1..4]));
}
```

```text
salam
hello
15
9
```

`first_word` هم برای `String` (با `&text`) کار می‌کند و هم برای literal. `sum` هم برای کل `Vec` و هم برای یک بازه از آن. در پارامترها `&str` و `&[T]` را به `&String` و `&Vec<T>` ترجیح دهید.

## چند نکته

- Reference اشاره‌گری نیست که خودتان مدیریتش کنید. آزادش نمی‌کنید و هرگز null نیست.
- «چند خواننده یا یک نویسنده» برای هر مقدار و در یک زمان معنا دارد. Borrow‌های پشت‌سرهم با NLL مشکلی ندارند.
- به برچسب‌های خطا («first borrow occurs here» و «later used here») نگاه کنید، نه فقط تیتر؛ نشان می‌دهند کدام دو خط با هم تداخل دارند.
- اگر رفع خطای borrow سخت شد، معمولاً کوتاه‌تر کردن scope یا برگرداندن مقدار صاحب‌دار کمک می‌کند. `.clone()` آخرین راه است.
- مقایسه با Go: در Go می‌توانید چند pointer به یک مقدار داشته باشید و از هرکدام تغییرش دهید و کامپایلر جلویتان را نمی‌گیرد. اگر goroutine‌ها این کار را بدون هماهنگی بکنند، data race است و پیدا کردنش با خود شماست (race detector کمک می‌کند). Rust این بررسی را به زمان کامپایل می‌آورد، به قیمت اینکه اول با کامپایلر کلنجار بروید.

## تمرین

1. تابع `fn append_twice(s: &mut String, word: &str)` را بنویسید که `word` را دو بار به `s` اضافه کند و از `main` صدایش بزنید.
2. خطای E0502 را با یک `Vec` بازتولید کنید و با جابه‌جا کردن `push` به قبل از گرفتن reference درستش کنید.
3. تابع `fn largest(xs: &[i32]) -> i32` را بنویسید و یک بار با کل `Vec` و یک بار با یک sub-slice صدایش بزنید.

## قدم بعدی

تا اینجا داده‌هایمان مقدارهای تکی و مجموعه بوده‌اند. در مقاله‌ی بعد، یعنی struct، enum و pattern matching در Rust، نوع‌های خودمان را می‌سازیم و روی آن‌ها شاخه می‌زنیم.
