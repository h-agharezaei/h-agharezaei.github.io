+++
date = '2026-11-14T10:00:00+03:30'
draft = false
title = 'Borrowing و Reference در Rust'
description = 'مفهوم borrowing و reference در Rust با کد قابل اجرا: &T و &mut T، قانون چند خواننده یا یک نویسنده، NLL، dangling reference، slice و خطاهای واقعی.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "borrowing", "references"]
cover = { image = "/images/covers/rust-borrowing-references.fa.png", alt = "Borrowing و Reference در Rust", hiddenInSingle = true }
+++

فرض کنید کتابی دارید و دوستتان می‌خواهد یک صفحه‌اش را بخواند. دو راه هست: کتاب را به او ببخشید، که دیگر مال شما نیست، یا فقط قرضش بدهید و پس بگیرید. در [Ownership در Rust](/fa/posts/rust-ownership/) فقط راه اول را دیدیم: وقتی یک `String` را به تابع می‌دادیم، مالکیتش هم همراهش می‌رفت و تابع باید آن را پس می‌داد تا دوباره از آن استفاده کنیم. آخر آن مقاله گفتم این رفت‌وبرگشت دست‌وپاگیر است. راه دوم، یعنی قرض‌دادن، همان چیزی است که {{< term "borrowing" "borrowing" >}} (قرض‌گیری) نام دارد.

ایده‌ی اصلی ساده است: به‌جای خود مقدار، یک **reference** به تابع می‌دهید. reference یعنی آدرسی که به مقدار اشاره می‌کند. تابع از طریق آن مقدار را می‌بیند (و در یک حالت خاص، تغییر می‌دهد)، ولی مالکیت همان‌جا که بود می‌ماند و کسی که مالک است همچنان مسئول آزادکردن حافظه است. در این مقاله دو نوع reference، تنها قانون حاکم بر آن‌ها و خطاهای کامپایلری را می‌بینیم که حین یادگیری با آن‌ها روبه‌رو می‌شوید. هر قانون را اول با خطایی که کامپایلر می‌دهد نشان می‌دهم تا دلیلش روشن باشد.

> همه‌ی کدهای زیر را با Rust 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها و خطاها از همان اجراها هستند. چند خط فرعی از پیام‌های خطا (مثل «For more information...») را برای کوتاه‌شدن حذف کرده‌ام. دو برنامه‌ی کوچک هم نوشتم که فقط برای نشان‌دادن `*` و یک اصلاح بودند.

## Reference اشتراکی و تغییرپذیر

دو نوع reference داریم. `&T` یک **shared reference** است: از طریق آن می‌توانید مقدار را بخوانید، ولی تغییرش نمی‌دهید. `&mut T` یک **mutable reference** است: می‌توانید هم بخوانید و هم مقدار را عوض کنید. ساختن هرکدام را «borrow کردن» می‌گویند. با `&s` یک reference اشتراکی به `s` می‌سازید و با `&mut s` یک reference تغییرپذیر.

برنامه‌ی زیر دو تابع دارد: `length` فقط طول رشته را می‌خواند، و `add_exclaim` یک `!` به آخر آن اضافه می‌کند. در `main` هر دو را صدا می‌زنیم و آخر کار دو reference اشتراکی همزمان می‌سازیم:

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

```text
salam has 5 bytes
salam!
salam! salam!
```

خط اول: `length(&s)` فقط قرض گرفت و طول را برگرداند. بعدش `s` هنوز مال ماست و می‌توانیم چاپش کنیم، بدون اینکه تابع چیزی را پس بدهد و بدون tuple. خط دوم: `add_exclaim(&mut s)` رشته را عوض کرد (`!` اضافه شد) و `s` در `main` همان تغییر را می‌بیند، چون تابع روی خود رشته کار کرده، نه روی یک کپی. خط سوم: دو reference اشتراکی همزمان مشکلی ندارند.

دو نکته درباره‌ی کد:

- برای نوشتن `&mut s` باید خود متغیر هم `mut` تعریف شده باشد (`let mut s`). نمی‌شود از چیزی که تغییرناپذیر است reference تغییرپذیر گرفت.
- reference را با `*` «باز می‌کنند» تا به خود مقدار برسند. وقتی متد صدا می‌زنید (`s.len()`) Rust خودش این کار را می‌کند، ولی در انتساب باید صریح بنویسید. برنامه‌ی کوچک زیر هر دو را نشان می‌دهد:

```rust
fn main() {
    let mut x = 10;
    let r = &mut x;
    *r += 5;
    println!("{x}");

    let s = String::from("salam");
    let rs = &s;
    println!("{} {}", rs.len(), (*rs).len());
}
```

```text
15
5 5
```

`*r += 5` می‌گوید «به آنچه `r` به آن اشاره می‌کند ۵ تا اضافه کن»، و `x` شد ۱۵. در خط آخر `rs.len()` و `(*rs).len()` یک کار را می‌کنند و هر دو ۵ می‌دهند.

## چند خواننده یا یک نویسنده

حالا بپرسیم: اگر دو reference تغییرپذیر به یک مقدار بگیریم چه می‌شود؟ در Go چنین چیزی مشکلی ندارد، ولی ببینید Rust چه می‌گوید:

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

پیام را بخوانیم. عنوان می‌گوید نمی‌شود `s` را بیش از یک بار هم‌زمان به‌صورت تغییرپذیر قرض گرفت. سه برچسب داستان را تعریف می‌کنند: اولین borrow در خط ۳، دومین borrow در خط ۴ (که مشکل‌ساز است)، و «first borrow later used here» در خط ۵. این برچسب آخر مهم‌ترین است. نشان می‌دهد چرا اولی هنوز زنده است: `a` بعد از دومین borrow دوباره استفاده می‌شود. اگر `a` دیگر استفاده نمی‌شد، مشکلی نبود (این را در بخش بعد می‌بینیم).

حالا حالت دوم: یک خواننده که هنوز زنده است، در حالی که مقدار را تغییر می‌دهیم. (`vec![1, 2, 3]` یک `Vec` می‌سازد، یعنی فهرست قابل رشد؛ بعداً درباره‌اش بیشتر می‌گوییم.)

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

این بار یک reference اشتراکی (`first`، به اولین عنصر) و یک reference تغییرپذیر (`v.push` برای تغییر `v` در پشت صحنه `&mut v` می‌گیرد) با هم تداخل دارند. این مورد جالب‌تر است. چرا خطرناک است؟ `push` ممکن است جا کم بیاورد و کل بافر vector را به جای بزرگ‌تری منتقل کند. آن‌وقت `first` به همان جای قدیمی اشاره می‌کرد که دیگر آزاد شده است. این همان «استفاده از حافظه‌ی آزادشده» است که در C باگ و حفره‌ی امنیتی می‌شود. Rust برنامه را قبل از رسیدن به آن لحظه رد می‌کند.

از این دو خطا قانون borrowing را می‌توان گفت: **در هر لحظه یا هر تعداد `&T` دارید، یا دقیقاً یک `&mut T`؛ هر دو با هم نه.** به زبان ساده: چند خواننده یا یک نویسنده. دلیلش این است که تا وقتی کسی در حال خواندن است، هیچ‌کس نباید داده را زیر پایش عوض کند. کامپایلر بخشی به اسم {{< term "borrow-checker" "borrow checker" >}} دارد که همین قانون را در زمان کامپایل بررسی می‌کند.

## Borrow با آخرین استفاده تمام می‌شود

شاید فکر کنید پس هر وقت یک reference اشتراکی گرفتم، تا آخر scope نمی‌توانم چیزی را عوض کنم. خوشبختانه این‌طور نیست. borrow تا آکولاد بسته دوام ندارد؛ تا آخرین باری که reference استفاده شده ادامه دارد. به این ویژگی **non-lexical lifetimes** (به اختصار NLL) می‌گویند. برنامه‌ی زیر یک borrow اشتراکی و بعد یک borrow تغییرپذیر از یک متغیر دارد، و کامپایل می‌شود:

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

`r` آخرین بار در `println!` اول استفاده شد. بعد از آن borrow تمام شده است، پس `&mut s` مجاز است. اگر بعد از `push_str` یک `println!("{r}")` اضافه کنید، `r` دوباره زنده می‌شود و همان خطای E0502 قبلی را می‌گیرید. نتیجه‌ی کاربردی: وقتی کامپایلر ایراد می‌گیرد، دنبال برچسب «later used here» بگردید. به استفاده‌ای اشاره می‌کند که borrow را زنده نگه داشته است. اغلب راه‌حل این است که تغییر را قبل از گرفتن reference انجام دهید. برای مثال، اگر در برنامه‌ی `Vec` بالا `v.push(4)` را به قبل از `let first = &v[0]` ببریم، برنامه کامپایل می‌شود و `first = 1` چاپ می‌کند.

## Reference نباید dangling شود

یک reference هرگز نباید بیشتر از مقداری که به آن اشاره می‌کند عمر کند، وگرنه به حافظه‌ای اشاره می‌کند که دیگر وجود ندارد. به چنین reference‌ای **dangling** می‌گویند. تابع زیر می‌خواهد reference به یک متغیر محلی خودش را برگرداند:

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

عنوان از چیزی به اسم {{< term "lifetime" "lifetime" >}} حرف می‌زند، یعنی مدتی که یک reference معتبر است. فعلاً لازم نیست دقیق بدانید. توضیح `help` اول کل ماجرا را می‌گوید: تابع reference برمی‌گرداند، ولی هیچ مقداری نیست که این reference از آن قرض گرفته شود (چون `s` داخل خود تابع ساخته می‌شود). پیشنهاد دوم کامپایلر راه‌حل درست است: خود `String` را برگردانید و مالکیت بیرون برود.

اگر برای ساکت‌کردن E0106 یک اسم lifetime اضافه کنید (`fn dangle<'a>() -> &'a String`)، به خطای عمیق‌تری می‌رسید که علت واقعی را می‌گوید:

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/dangle2.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function
```

`s` وقتی تابع تمام می‌شود drop می‌شود (همان قانون سوم ownership)، پس reference به هیچ‌چیز اشاره می‌کرد. lifetimeها را بعداً در همین سری جدی‌تر بررسی می‌کنیم.

## Slice: نمای قرض‌گرفته‌شده

دو نوع reference خاص هم زیاد با آن‌ها سروکار دارید. `&str` یک نمای قرض‌گرفته‌شده از متن یک رشته است (کل آن یا بخشی از آن) و `&[T]` نمای قرض‌گرفته‌شده از یک ردیف عنصر. این‌ها هم reference هستند و همان قانون‌ها را دارند. فایده‌شان این است که تابعی که آن‌ها را بگیرد، ورودی‌های بیشتری را می‌پذیرد:

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

`first_word` اولین کلمه‌ی متن را برمی‌گرداند (متن را روی فاصله‌ها تکه می‌کند و تکه‌ی اول را برمی‌دارد). هم برای `String` کار می‌کند (با `&text`) و هم برای یک literal مثل `"hello rust"`. (طبق مستندات Rust، `&String` را خودکار به `&str` تبدیل می‌کنند؛ به این تبدیل deref coercion می‌گویند.) `sum` هم برای کل `Vec` کار می‌کند (۱+۲+۳+۴+۵ = ۱۵) و هم برای یک بازه‌ی آن: `&v[1..4]` یعنی عنصرهای شماره‌ی ۱ تا ۳، یعنی ۲+۳+۴ = ۹. به همین دلیل در پارامتر تابع‌ها `&str` و `&[T]` را به `&String` و `&Vec<T>` ترجیح دهید.

## خواندن خطاهای borrow

- **reference اشاره‌گری نیست که خودتان مدیریتش کنید.** آزادش نمی‌کنید و در Rust ایمن هرگز null نیست.
- **«چند خواننده یا یک نویسنده» برای هر مقدار و در یک زمان معنا دارد.** borrowهای پشت‌سرهم، وقتی اولی دیگر استفاده نمی‌شود، با NLL مشکلی ندارند.
- **به برچسب‌های خطا نگاه کنید، نه فقط عنوان.** «first borrow occurs here» و «later used here» نشان می‌دهند کدام دو خط با هم تداخل دارند.
- **اگر رفع خطای borrow سخت شد،** معمولاً کوتاه‌کردن عمر reference (قبل از تغییر، دیگر استفاده‌اش نکنید) یا برگرداندن مقدار صاحب‌دار کمک می‌کند. `.clone()` آخرین راه است.
- **مقایسه با Go.** در Go می‌توانید چند pointer به یک مقدار داشته باشید و از هرکدام تغییرش دهید و کامپایلر جلویتان را نمی‌گیرد. اگر goroutineها این کار را بدون هماهنگی بکنند، data race پیش می‌آید و پیداکردنش با خود شماست (race detector کمک می‌کند). Rust این بررسی را به زمان کامپایل می‌آورد، به قیمت اینکه اول با کامپایلر کلنجار بروید.

## تمرین

۱. تابع `fn append_twice(s: &mut String, word: &str)` را بنویسید که `word` را دو بار به `s` اضافه کند و از `main` صدایش بزنید.
۲. خطای E0502 را با یک `Vec` بازتولید کنید و با جابه‌جاکردن `push` به قبل از گرفتن reference درستش کنید.
۳. تابع `fn largest(xs: &[i32]) -> i32` را بنویسید و یک بار با کل `Vec` و یک بار با یک sub-slice صدایش بزنید.

## قدم بعدی

«Struct، Enum و Pattern Matching در Rust». تا اینجا داده‌هایمان مقدارهای تکی و مجموعه بوده‌اند. حالا که می‌دانیم چطور مقدار را قرض بدهیم، نوع‌های خودمان را می‌سازیم و روی آن‌ها شاخه می‌زنیم.
