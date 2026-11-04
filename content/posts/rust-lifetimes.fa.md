+++
date = '2026-12-22T10:00:00+03:30'
draft = false
title = 'Lifetime در Rust'
description = 'مفهوم lifetime در Rust با کد قابل اجرا: تابع longest، خطاهای واقعی E0106 و E0597، قواعد elision، struct‌های دارای reference و معنای واقعی T: static.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "lifetimes", "intermediate", "borrowing"]
cover = { image = "/images/covers/rust-lifetimes.fa.png", alt = "Lifetime در Rust", hiddenInSingle = true }
+++

کوچک‌ترین برنامه‌ای که می‌شود نوشت تا Rust از آن ایراد بگیرد این است: یک متغیر `r` تعریف می‌کنیم، داخل یک آکولاد متغیر دیگری می‌سازیم و `r` را به آن اشاره می‌دهیم، و بعد از آکولاد `r` را چاپ می‌کنیم. در C این کد کامپایل می‌شود و رفتارش تعریف‌نشده است. در Go هم بی‌صدا کار می‌کند، چون کامپایلر Go متغیر را خودش به heap می‌برد. در Rust کامپایل نمی‌شود. ایده‌ای که پشت این ایراد است اسمش {{< term "lifetime" "lifetime" >}} (طول عمر) است، و ایده‌ی خودش از اسمش ساده‌تر است. در این مقاله از همان برنامه‌ی کوچک شروع می‌کنیم و قدم‌به‌قدم می‌رسیم به علامت `'a` که در امضای تابع‌ها می‌بینید.

اگر [Borrowing و Reference در Rust](/fa/posts/rust-borrowing-references/) را خوانده باشید، قاعده را می‌دانید: یک reference نباید بیشتر از مقداری که به آن اشاره می‌کند زنده بماند. این مقاله همان قاعده را عمیق‌تر می‌کند. بعد از [Generics و Trait در Rust](/fa/posts/rust-generics-traits/) می‌آید، چون جایی که lifetime لازم می‌شود، درست مثل trait bound، یک پارامتر در `<>` است و کامپایلر با آن چیزی را بررسی می‌کند.

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 کامپایل و اجرا کرده‌ام و خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. چند برنامه‌ی کوچک (برای مثال reference معلق، دو lifetime، و `'a` روی تابعی که reference محلی برمی‌گرداند) را برای نمایش پیام‌ها خودم نوشتم و اجرا کردم و هر جا چنین است، در متن گفته‌ام. از پیام‌ها خط «For more information…» را حذف کرده‌ام، و از یک پیام هم یک هشدار «unused variable» بی‌ربط.

## کوچک‌ترین مثال: reference معلق

برنامه این است:

```rust
fn main() {
    let r;
    {
        let x = 5;
        r = &x;
    }
    println!("r: {r}");
}
```

```text
error[E0597]: `x` does not live long enough
 --> src/bin/dangling.rs:5:13
  |
4 |         let x = 5;
  |             - binding `x` declared here
5 |         r = &x;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `x` dropped here while still borrowed
7 |     println!("r: {r}");
  |                   - borrow later used here
```

خطا را با هم از پایین به بالا بخوانیم، چون سه برچسب یک داستان کامل می‌گویند:

- خط ۴: متغیر `x` اینجا ساخته شد.
- خط ۵: `r` یک reference به `x` گرفت، یعنی آدرسش را نگه داشت.
- خط ۶: آکولاد بسته شد و `x` از بین رفت («dropped here»)، در حالی که هنوز کسی به آن اشاره می‌کند («while still borrowed»).
- خط ۷: و بعدش `r` استفاده شد («later used here»). یعنی از آدرسی می‌خوانیم که دیگر معتبر نیست.

به reference‌ای که به مقداری اشاره می‌کند که دیگر وجود ندارد **dangling** یا «معلق» می‌گویند (مثل سیمی که به جایی وصل نیست). Rust ساختن آن را از همان زمان کامپایل غیرممکن می‌کند. چطور؟ کامپایلر برای هر reference در ذهنش یک سؤال دارد: «این reference در چه بخشی از برنامه معتبر است؟». و برای هر مقدار یک سؤال دیگر: «این مقدار تا کجا زنده است؟». اگر بخش اول از بخش دوم بیرون بزند، خطا می‌دهد. در مثال ما `x` تا خط ۶ زنده است ولی `r` تا خط ۷ استفاده می‌شود.

به این «بخش معتبر بودن» می‌گویند **lifetime**. یک نکته که باید از همین اول بدانید: lifetime فقط در زمان کامپایل وجود دارد. چیزی از آن در برنامه‌ی نهایی نیست و در زمان اجرا هیچ کاری نمی‌کند. فقط یک بررسی است. و در بیشتر کدی که می‌نویسید، کامپایلر خودش lifetime‌ها را حدس می‌زند و شما هیچ‌چیز نمی‌نویسید، مثل همین مثال بالا که هیچ `'` در آن نبود. سؤال این است که کِی کامپایلر نمی‌تواند حدس بزند.

## وقتی کامپایلر از تابع عبور نمی‌کند

فرض کنید تابعی می‌نویسیم که دو رشته می‌گیرد و آن را که بلندتر است برمی‌گرداند. نه رشته جدید می‌سازد، فقط یکی از همان دو reference را پس می‌دهد:

```rust
fn longest(x: &str, y: &str) -> &str {
    if x.len() >= y.len() { x } else { y }
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/missing_annotation.rs:1:33
  |
1 | fn longest(x: &str, y: &str) -> &str {
  |               ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `x` or `y`
help: consider introducing a named lifetime parameter
  |
1 | fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
  |           ++++     ++          ++          ++
```

چرا کامپایلر اینجا گیر می‌کند؟ فکر کنید کسی `longest` را این‌طور صدا بزند: `a` یک متغیر بلندعمر باشد و `b` یکی که در یک آکولاد داخلی ساخته شده و زود می‌میرد. اگر نتیجه `a` باشد، می‌شود بعد از آکولاد هم استفاده‌اش کرد. اگر `b` باشد، نمی‌شود، و همان مشکل `x` و `r` پیش می‌آید. اما اینکه کدام برگردانده شود را `x.len() >= y.len()` در **زمان اجرا** تعیین می‌کند و کامپایلر هیچ‌وقت نمی‌داند. کامپایلر هر تابع را جدا بررسی می‌کند و برای بررسی جاهایی که صدایش می‌زنید فقط به **امضا** نگاه می‌کند. پس امضا باید بگوید نتیجه به کدام ورودی‌ها وابسته است. پیام خطا هم دقیقاً همین را می‌گوید: «امضا نمی‌گوید از `x` قرض گرفته شده یا از `y`».

## `'a` چه می‌گوید؟

پیشنهاد کامپایلر را اعمال می‌کنیم:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}
```

اول بخوانیمش. `<'a>` یک **اسم** برای یک lifetime اعلام می‌کند، مثل `<T>` که اسمی برای یک نوع اعلام می‌کرد. `&'a str` یعنی «یک reference به `str` که lifetimeاش `'a` است». پس امضا می‌گوید: «`x` و `y` و نتیجه همگی lifetime مشترکی به اسم `'a` دارند». به زبان ساده‌تر: **«نتیجه فقط تا وقتی معتبر است که هر دو ورودی معتبر باشند.»** (طبق Rust Book، در عمل `'a` برابر کوتاه‌تر از دو lifetime ورودی می‌شود.)

نکته‌ی اصلی همین‌جاست و باید حتماً رویش بایستیم: **`'a` عمر هیچ‌چیز را زیاد نمی‌کند.** این علامت چیزی را زنده نگه نمی‌دارد. فقط یک **رابطه** را توصیف می‌کند، رابطه‌ی بین reference‌هایی که از تابع می‌گذرند، تا کامپایلر بتواند در هر جایی که تابع صدا زده می‌شود بررسی‌شان کند. کد را با دو رشته‌ی معمولی اجرا می‌کنیم:

```rust
fn main() {
    let a = String::from("salam donya");
    let b = String::from("hi");
    let result = longest(&a, &b);
    println!("longest: {result}");
}
```

```text
longest: salam donya
```

هر دو رشته تا آخر `main` زنده‌اند و `result` هم داخل همان بازه است، پس مشکلی نیست. حالا همان کار را بکنیم ولی `b` را در یک آکولاد داخلی بسازیم و `result` را بعد از آن چاپ کنیم:

```rust
fn main() {
    let a = String::from("salam donya");
    let result;
    {
        let b = String::from("hi");
        result = longest(&a, &b);
    }
    println!("longest: {result}");
}
```

```text
error[E0597]: `b` does not live long enough
  --> src/bin/short_lived.rs:10:30
   |
 9 |         let b = String::from("hi");
   |             - binding `b` declared here
10 |         result = longest(&a, &b);
   |                              ^^ borrowed value does not live long enough
11 |     }
   |     - `b` dropped here while still borrowed
12 |     println!("longest: {result}");
   |                         ------ borrow later used here
```

همان داستان قبلی: `b` در خط ۱۱ از بین می‌رود، و `result` در خط ۱۲ استفاده می‌شود. توجه کنید کامپایلر با اینکه در این اجرا `a` از `b` بلندتر است و نتیجه عملاً `a` می‌شد، باز هم خطا می‌دهد. چون امضا گفته نتیجه به هر دو وابسته است و کامپایلر فقط به امضا اعتماد می‌کند، نه به مقدارها. اگر `result` را داخل همان آکولاد چاپ کنیم (من این را هم اجرا کردم)، همان `longest: salam donya` بدون خطا چاپ می‌شود، چون در آن لحظه هر دو هنوز زنده‌اند.

حالا ببینیم رابطه را می‌شود تغییر داد. اگر تابع فقط `x` را برگرداند، چرا باید نتیجه به `y` گره بخورد؟ دو lifetime جدا اعلام می‌کنیم:

```rust
fn first_of<'a, 'b>(x: &'a str, _y: &'b str) -> &'a str {
    x
}
```

(این هم یک برنامه‌ی کوچک جدا است.) حالا نتیجه فقط به `x` وابسته است. اگر همان آزمایش آکولاد داخلی را با آن تکرار کنیم، یعنی `b` را در آکولاد بسازیم و به‌عنوان آرگومان دوم بدهیم و `result` را بیرون چاپ کنیم، کامپایل می‌شود و `first: salam donya` چاپ می‌کند. چون `b` دیگر ربطی به نتیجه ندارد.

و کامپایلر مراقب است که بدنه‌ی تابع با امضا بخواند. اگر بنویسیم که نتیجه از `'a` است ولی از `y` که `'b` دارد برگردانیم:

```rust
fn first_of<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
    y
}
```

```text
error: lifetime may not live long enough
 --> src/bin/wrong_relation.rs:2:5
  |
1 | fn first_of<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
  |             --  -- lifetime `'b` defined here
  |             |
  |             lifetime `'a` defined here
2 |     y
  |     ^ function was supposed to return data with lifetime `'a` but it is returning data with lifetime `'b`
  |
  = help: consider adding the following bound: `'b: 'a`
```

پیام می‌گوید: «تابع قرار بود داده‌ای با lifetime `'a` برگرداند ولی داده‌ای با lifetime `'b` برمی‌گرداند». یعنی وعده‌ای که در امضا داده‌ایم نگه داشته نشده. این همان چیزی است که می‌خواستم نشان بدهم: امضا یک قرارداد است و کامپایلر هم بدنه را در برابر آن می‌سنجد، هم فراخواننده را.

و آخرین مثال برای اینکه ثابت شود `'a` چیزی را زنده نمی‌کند. تابعی که یک reference به متغیر محلی خودش را برمی‌گرداند، حتی با نوشتن `'a`، درست نمی‌شود:

```rust
fn make<'a>() -> &'a String {
    let s = String::from("salam");
    &s
}
```

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/extend.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function
```

`s` وقتی `make` تمام شود drop می‌شود، و هیچ برچسبی نمی‌تواند آن را نگه دارد. راه درست برگرداندن خود `String` است (مثل مقاله‌ی borrowing).

## Lifetime elision: چرا همیشه `'a` نمی‌نویسید

شاید پرسیده باشید پس چرا در `fn length(s: &String) -> usize` یا `fn first_word(s: &str) -> &str` چیزی ننوشتیم؟ چون کامپایلر روی امضا سه قاعده‌ی ثابت اعمال می‌کند و در بیشتر موارد خودش جای خالی را پر می‌کند. به این کار **elision** («حذف‌کردنِ مجاز») می‌گویند:

1. هر reference در پارامترها یک lifetime مستقل می‌گیرد.
2. اگر دقیقاً یک lifetime در ورودی‌ها باشد، به همه‌ی reference‌های خروجی هم داده می‌شود.
3. اگر یکی از ورودی‌ها `&self` یا `&mut self` باشد (در یک متد)، lifetime مربوط به `self` به همه‌ی reference‌های خروجی داده می‌شود.

اگر بعد از اعمال این قاعده‌ها هنوز lifetime خروجی معلوم نباشد، همان E0106 را می‌گیرید. `longest` دقیقاً همین حالت است: دو ورودی (قاعده‌ی ۲ کار نمی‌کند) و بدون `self` (قاعده‌ی ۳ هم کار نمی‌کند). حالا یک تابع را با هر دو شکل ببینیم، آنچه می‌نویسید و آنچه کامپایلر استنباط می‌کند:

```rust
// one input reference: elision gives the output the same lifetime
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

// written out in full, this is what the compiler infers
fn first_word_explicit<'a>(s: &'a str) -> &'a str {
    s.split(' ').next().unwrap_or("")
}
```

```text
salam
salam
```

برنامه هر دو تابع را روی `"salam donya"` صدا می‌زند و هر دو `salam` برمی‌گردانند. قاعده‌ی ۲ اعمال می‌شود، پس نتیجه از ورودی قرض گرفته شده و برگرداندن بخشی از آن امن است.

## struct‌هایی که reference نگه می‌دارند

تا اینجا reference‌ها در پارامتر تابع بودند. اگر یک struct بخواهد reference نگه دارد، همین مشکل را دارد: struct نباید بیشتر از چیزی که به آن اشاره می‌کند زنده بماند. پس نوع struct هم یک پارامتر lifetime می‌گیرد، درست مثل یک پارامتر generic:

```rust
struct Excerpt<'a> {
    part: &'a str,
}

impl<'a> Excerpt<'a> {
    // elision rule 3: the output gets the lifetime of &self
    fn part(&self) -> &str {
        self.part
    }
}

fn main() {
    let novel = String::from("Call me Ishmael. Some years ago...");
    let first_sentence = novel.split('.').next().unwrap();
    let e = Excerpt { part: first_sentence };
    println!("{}", e.part());
}
```

```text
Call me Ishmael
```

`Excerpt<'a>` یعنی «یک `Excerpt` که تا وقتی داده‌ای که `part` به آن اشاره می‌کند زنده است، معتبر است». برای همین باید `impl<'a>` هم بنویسیم، چون `'a` بخشی از نوع است. متد `part` چیزی ننوشته چون قاعده‌ی ۳ کار را می‌کند. در `main`، `novel` صاحب متن است، `first_sentence` یک تکه از آن را قرض می‌گیرد و `e` همان تکه را نگه می‌دارد. همه‌چیز در یک scope است، پس `Call me Ishmael` چاپ می‌شود. اگر `Excerpt` بیشتر از `novel` زنده بماند چه؟

```rust
let e;
{
    let novel = String::from("Call me Ishmael. Some years ago...");
    e = Excerpt { part: novel.split('.').next().unwrap() };
}
println!("{}", e.part);
```

```text
error[E0597]: `novel` does not live long enough
  --> src/bin/excerpt_dies.rs:9:29
   |
 8 |         let novel = String::from("Call me Ishmael. Some years ago...");
   |             ----- binding `novel` declared here
 9 |         e = Excerpt { part: novel.split('.').next().unwrap() };
   |                             ^^^^^ borrowed value does not live long enough
10 |     }
   |     - `novel` dropped here while still borrowed
11 |     println!("{}", e.part);
   |                    ------ borrow later used here
```

همان خطای E0597 دوباره، با همان سه برچسب: `novel` ساخته شد، در آکولاد بسته drop شد، و `e.part` بعدش استفاده شد.

## `'static`

یک lifetime ویژه هم هست: `'static`، یعنی «تا آخر عمر برنامه». رشته‌های literal این را دارند، چون متنشان داخل خود برنامه ذخیره شده و هیچ‌وقت آزاد نمی‌شود:

```rust
let greeting: &'static str = "salam";
```

در مورد قید `T: 'static` یک سوءتفاهم رایج هست. معنایش «مقدار تا ابد زنده است» نیست. معنایش این است که **نوع `T` هیچ reference کوتاه‌عمری در خودش ندارد**. یک `String` صاحب‌دار یا یک `i32` این شرط را دارند (چون اصلاً reference نیستند) و مثل هر مقدار دیگری معمولی drop می‌شوند. برنامه‌ی زیر سه مقدار را به تابعی می‌دهد که `T: Debug + 'static` می‌خواهد:

```rust
fn takes_static<T: Debug + 'static>(value: T) {
    println!("got {value:?}");
}

let greeting: &'static str = "salam";
println!("{greeting}");

let owned = String::from("owned");
takes_static(owned);
takes_static(42);
takes_static(greeting);
```

```text
salam
got "owned"
got 42
got "salam"
```

هر سه می‌پذیرد. اما اگر یک reference به یک متغیر محلی بدهیم، یعنی `takes_static(&owned)`:

```text
error[E0597]: `owned` does not live long enough
  --> src/bin/static_fail.rs:9:18
   |
 8 |     let owned = String::from("owned");
   |         ----- binding `owned` declared here
 9 |     takes_static(&owned);
   |     -------------^^^^^^-
   |     |            |
   |     |            borrowed value does not live long enough
   |     argument requires that `owned` is borrowed for `'static`
10 | }
   | - `owned` dropped here while still borrowed
```

پیام می‌گوید آرگومان لازم دارد `owned` تا `'static` قرض داده شده باشد، که ممکن نیست چون `owned` در آخر `main` drop می‌شود. برای رفع یک خطای lifetime سراغ `'static` نروید، مگر اینکه داده واقعاً literal یا ثابت باشد. `'static` را اضافه‌کردن معمولاً فقط خطا را به جای دیگری می‌برد.

## وقتی با borrow checker کلنجار می‌روید

در دوره‌ی یادگیری لازم نیست همه‌جا lifetime به کد بچسبانید. اگر `Excerpt` اذیتتان کرد، می‌توانید به‌جای قرض‌گرفتن یک `String` نگه دارید و یک بار `.to_string()` (یا `.clone()`) بزنید:

```rust
struct Excerpt {
    part: String, // owned: no lifetime parameter needed
}
```

این نسخه را با همان ترفند scope داخلی که نسخه‌ی borrow‌دار را می‌شکست اجرا کردم (`e` در یک آکولاد ساخته می‌شود و بیرون استفاده می‌شود)، و بدون خطا `Call me Ishmael` چاپ می‌کند. چرا؟ چون `Excerpt` حالا صاحب متن خودش است و به چیزی در جای دیگر وابسته نیست. هزینه‌اش یک allocation و کپی‌کردن متن است. استفاده از reference با lifetime در واقع نوعی بهینه‌سازی است: وقتی دلیل دارید سراغش بروید.

## خطاهای رایج با lifetime

- annotation‌های lifetime رابطه را توصیف می‌کنند و هرگز عمر مقدار را بیشتر نمی‌کنند. اگر مقداری زود می‌میرد، `'a` نجاتش نمی‌دهد.
- جایی که elision جواب می‌دهد چیزی ننویسید. فقط وقتی کامپایلر E0106 داد `'a` اضافه کنید.
- تابع نمی‌تواند reference به متغیر محلی خودش را برگرداند؛ مقدار صاحب‌دار (مثلاً خود `String`) برگردانید.
- `'a` روی struct یعنی «این struct بیشتر از داده‌ی قرض‌گرفته‌شده زنده نمی‌ماند».
- برچسب‌های E0597 را بخوانید: «declared here»، «dropped here» و «later used here». هر سه را که پیدا کنید، معمولاً معلوم می‌شود چه چیزی را باید جابه‌جا کنید.

## تمرین

1. تابع `fn longer_or_default<'a>(x: &'a str, default: &'static str) -> &'a str` را بنویسید که هرکدام طولانی‌تر است برگرداند. (من آن را با `"ab"` و `"xyz"` اجرا کردم و `xyz` چاپ می‌کند.) کامپایل می‌شود، چون reference با `'static` هرجا که reference کوتاه‌تر لازم باشد قابل استفاده است. سعی کنید دلیلش را توضیح دهید.
2. متد `fn first_word(&self) -> &str` را به `Excerpt` اضافه کنید و صدایش بزنید.
3. `Excerpt` را طوری عوض کنید که `String` داشته باشد و همه‌ی `'a`‌ها را حذف کنید.

## قدم بعدی

حالا می‌دانید چرا کامپایلر گاهی `'a` می‌خواهد و چه چیزی را بررسی می‌کند. جای بعدی که این قاعده‌ها دوباره پیدا می‌شوند، closure‌ها هستند: متغیرهای اطرافشان را capture می‌کنند و باید از همین قانون‌ها پیروی کنند. برای همین قدم بعدی «Closure و Iterator در Rust» است.
