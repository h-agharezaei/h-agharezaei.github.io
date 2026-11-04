+++
date = '2026-12-24T10:00:00+03:30'
draft = false
title = 'Closure و Iterator در Rust'
description = 'Closure و iterator در Rust در عمل: حالت‌های capture و move، تفاوت Fn و FnMut و FnOnce، برگرداندن closure، adapterها و consumerها، تنبلی و Iterator سفارشی.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "closures", "iterators", "intermediate"]
cover = { image = "/images/covers/rust-closures-iterators.fa.png", alt = "Closure و Iterator در Rust", hiddenInSingle = true }
+++

فرض کنید یک فهرست عدد دارید و فقط عددهایی را می‌خواهید که از یک حد بزرگ‌ترند، حدی که از کاربر می‌گیرید. فیلتر کردن کار سختی نیست. قسمت جالب خود شرط است: یک تکه‌ی کوچک رفتار («آیا این عدد از `limit` بزرگ‌تر است؟») که می‌خواهید به تابع دیگری بدهید، و آن تکه باید متغیر `limit` را ببیند که در کد شما زندگی می‌کند. یک تابع معمولی نمی‌تواند این کار را بکند. **closure** می‌تواند، و این مقاله درباره‌ی closure است و ابزاری که بیشتر از همه با آن کار می‌کند: iterator.

[مقاله‌ی قبل](/fa/posts/rust-lifetimes/) درباره‌ی این بود که یک reference هرگز نباید بیشتر از مقدارش زنده بماند. همان بررسی اینجا برمی‌گردد، چون closure‌ای که از متغیرهای محلی شما استفاده می‌کند یا به آن‌ها reference دارد یا صاحبشان شده، و کامپایلر همان قاعده‌ها را اعمال می‌کند. اگر Go می‌دانید، closure همان چیزی است که در Go «function literal» می‌نامند؛ مقایسه‌ی این دو را در بخش گرفتن متغیرها گفته‌ام (طرف Go در [تابع در Go](/fa/posts/go-functions-defer-errors/) آمده است).

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 کامپایل و اجرا کرده‌ام (همان نسخه‌ی اجرای اول). خروجی‌ها و پیام‌های کامپایلر از همان اجراها برداشته شده‌اند. چند برنامه‌ی کوچک (مثال `limit`، یک `fn` که می‌خواهد از متغیر محلی استفاده کند، یک closure که به‌جای `Fn` پاس داده شده، و یک adapter که هیچ‌وقت مصرف نمی‌شود) در demo اصلی نبودند؛ آن‌ها را برای همین مقاله نوشتم و جداگانه اجرا کردم. از پیام‌ها خط «For more information…» را حذف کرده‌ام، و از بعضی هم پیشنهادهای `help:` و یک هشدار بی‌ربط «unused variable».

## closure: تابعی که اطرافش را به یاد دارد

{{< term "rust-closure" "closure" >}} یک تابع بی‌نام است که به شکل `|پارامترها| بدنه` نوشته می‌شود. تفاوتش با تابع معمولی این است که می‌تواند از متغیرهای جایی که ساخته شده استفاده کند. مثال `limit`:

```rust
let limit = 3;
let is_big = |n: i32| n > limit;
println!("{} {}", is_big(2), is_big(5));
```

```text
false true
```

`is_big` پارامتر `n` را می‌گیرد و از `limit` هم استفاده می‌کند، که به‌عنوان پارامتر نگرفته است. آن را از کد اطرافش برداشته است. یک `fn` معمولی چنین کاری نمی‌کند. اگر همین را به شکل یک تابع داخل `main` بنویسیم:

```rust
let limit = 3;
fn is_big(n: i32) -> bool {
    n > limit
}
```

```text
error[E0434]: can't capture dynamic environment in a fn item
 --> src/bin/x_fnitem.rs:4:13
  |
4 |         n > limit
  |             ^^^^^
  |
  = help: use the `|| { ... }` closure form instead
```

پیام مستقیم می‌گوید: تابع (fn item) نمی‌تواند محیط اطرافش را بگیرد، از شکل closure استفاده کن. به استفاده از یک متغیر بیرونی می‌گویند **capture** (گرفتن) آن متغیر، و تمام فایده‌ی closure همین است.

## closure چطور می‌گیرد: قرض، قرض تغییرپذیر، move

گرفتن متغیر بدون قاعده نیست، چون متغیر گرفته‌شده هنوز یک مقدار معمولی Rust است و صاحب دارد. closure باید تصمیم بگیرد: فقط نگاهش کند؟ تغییرش بدهد؟ یا صاحبش شود؟ Rust به بدنه‌ی closure نگاه می‌کند و سبک‌ترین حالتی را که کار می‌کند انتخاب می‌کند:

```rust
let name = String::from("Roham");
let greet = || println!("hello {name}"); // فقط name را می‌خواند
greet();
println!("name still usable: {name}");

let mut count = 0;
let mut inc = || count += 1; // count را تغییر می‌دهد
inc();
inc();
println!("count = {count}");

let owned = String::from("moved in");
let consume = move || println!("{owned}");
consume();
```

```text
hello Roham
name still usable: Roham
count = 2
moved in
```

خط‌به‌خط:

- `greet` فقط `name` را می‌خواند، پس یک reference مشترک می‌گیرد. بعد از فراخوانی هنوز خودمان هم می‌توانیم `name` را به کار ببریم. این جفت خط اول خروجی است.
- `inc` مقدار `count` را عوض می‌کند، پس reference تغییرپذیر می‌گیرد. دقت کنید که مجبور شدیم بنویسیم `let mut inc`: صدا زدن آن وضعیت گرفته‌شده را تغییر می‌دهد، پس خود متغیر closure هم باید تغییرپذیر باشد. دو فراخوانی `count = 2` می‌دهد.
- `consume` با کلمه‌ی `move` جلویش نوشته شده است. `move` closure را مجبور می‌کند مالکیت همه‌ی چیزهایی را که استفاده می‌کند بگیرد، حتی وقتی reference هم کافی بود. بعد از این خط، `owned` مال closure است.

چرا کسی `move` بخواهد وقتی reference کافی است؟ به‌خاطر حالتی که closure از تابعی که در آن ساخته شده بیرون می‌رود. این تابع را ببینید که یک closure برمی‌گرداند:

```rust
fn make() -> impl Fn() {
    let s = String::from("local");
    || println!("{s}")
}
```

```text
error[E0373]: closure may outlive the current function, but it borrows `s`, which is owned by the current function
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^            - `s` is borrowed here
  |     |
  |     may outlive borrowed value `s`
  |
note: closure is returned here
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^^^^^^^^^^^^^^^^^
help: to force the closure to take ownership of `s` (and any other referenced variables), use the `move` keyword
  |
3 |     move || println!("{s}")
  |     ++++
```

این همان داستان reference معلق در مقاله‌ی lifetime است. closure فقط `s` را می‌خواند، پس آن را قرض گرفته. ولی `s` متغیر محلی `make` است و وقتی `make` تمام شود از بین می‌رود، در حالی که closure به بیرون، پیش صدازننده، فرستاده شده. closure به چیزی reference می‌داشت که دیگر وجود ندارد. کامپایلر همین را می‌گوید («may outlive borrowed value `s`») و راه‌حل را هم پیشنهاد می‌کند: `move` بنویس تا closure صاحب `s` شود و آن را با خودش ببرد.

روی دیگر `move` این است که اسم اصلی دیگر کار نمی‌کند:

```rust
let s = String::from("hi");
let f = move || println!("{s}");
f();
println!("{s}");
```

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/use_after_move.rs:5:16
  |
2 |     let s = String::from("hi");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
3 |     let f = move || println!("{s}");
  |             -------            - variable moved due to use in closure
  |             |
  |             value moved into closure here
4 |     f();
5 |     println!("{s}");
  |                ^ value borrowed here after move
```

این همان قاعده‌ی معمولی ownership است: `s` در خط ۳ به closure منتقل شد، پس در خط ۵ دیگر مال ما نیست. (خط‌های `= note` و `help:` درباره‌ی clone را برای فهمیدن خطا لازم نبود و حذفشان کرده‌ام.)

یک مقایسه با Go: closure در Go متغیرها را با reference می‌گیرد و garbage collector تا وقتی closure لازم دارد آن‌ها را زنده نگه می‌دارد، پس هیچ‌وقت به این موضوع فکر نمی‌کنید. در Rust خودتان انتخاب می‌کنید و کامپایلر انتخاب را بررسی می‌کند.

## Fn و FnMut و FnOnce: closure با چیزهایی که گرفته چه می‌کند

حالا پرسشی که بی‌ربط به نظر می‌رسد ولی همان ایده است. فرض کنید تابعی می‌نویسیم که یک closure را دو بار صدا می‌زند:

```rust
fn call_twice(f: impl Fn()) { f(); f(); }

let mut count = 0;
call_twice(|| count += 1);
```

```text
error[E0594]: cannot assign to `count`, as it is a captured variable in a `Fn` closure
 --> src/bin/x_fnmut.rs:5:19
  |
1 | fn call_twice(f: impl Fn()) { f(); f(); }
  |                  --------- change this to accept `FnMut` instead of `Fn`
...
5 |     call_twice(|| count += 1);
  |     ---------- -- ^^^^^^^^^^ cannot assign
  |     |          |
  |     |          in this closure
  |     expects `Fn` instead of `FnMut`
```

`impl Fn()` در پارامتر یعنی «هر closure‌ای که trait به اسم `Fn` را داشته باشد». closure ما `count` را تغییر می‌دهد، پس از آن نوع نیست. Rust برای closure‌ها سه {{< term "trait" "trait" >}} دارد، و اینکه یک closure کدام‌ها را بگیرد بستگی دارد به اینکه بدنه‌اش با مقدارهای گرفته‌شده چه می‌کند:

- **`Fn`**: فقط آنچه را گرفته می‌خواند. هر تعداد بار می‌شود صدایش زد.
- **`FnMut`**: آنچه را گرفته تغییر می‌دهد. چندبار می‌شود صدایش زد، ولی هر بار فقط یک صدازننده.
- **`FnOnce`**: چیزی را که گرفته از خودش بیرون می‌برد (مثلاً برمی‌گرداند). بعد از آن آن چیز دیگر نیست، پس فقط یک بار می‌شود صدایش زد.

هر closure از نوع `Fn` هم `FnMut` است و هم `FnOnce`، و هر `FnMut` هم `FnOnce` است. این سه مثل یک نردبان‌اند، و تابعی که فقط `FnOnce` بخواهد closure‌های بیشتری را قبول می‌کند. یک demo با یک تابع برای هر کدام:

```rust
fn call_fn(f: impl Fn() -> usize) -> usize { f() + f() }
fn call_mut(mut f: impl FnMut()) { f(); f(); }
fn call_once(f: impl FnOnce() -> String) -> String { f() }

let word = String::from("rust");
println!("Fn: {}", call_fn(|| word.len()));

let mut log = Vec::new();
call_mut(|| log.push(log.len()));
println!("FnMut: {log:?}");

let s = String::from("bye");
println!("FnOnce: {}", call_once(move || s));
```

```text
Fn: 8
FnMut: [0, 1]
FnOnce: bye
```

- `call_fn` closure را دو بار صدا می‌زند و هر بار `word.len()` برابر ۴ است، پس جمع `8` می‌شود.
- `call_mut` دو بار صدا می‌زند و هر بار طول فعلی `log` را داخلش push می‌کند، پس `[0, 1]` به دست می‌آید. پارامتر `mut f` تعریف شده چون صدا زدن یک `FnMut` آن را تغییر می‌دهد.
- `call_once` فقط یک بار صدا می‌زند. closure خود `s` را برمی‌گرداند، یعنی `String` را از closure بیرون می‌برد. به همین دلیل فقط `FnOnce` است.

پس تابعی که closure را فقط یک بار صدا می‌زند باید `FnOnce` بخواهد، چون همه‌ی closure‌ها را قبول می‌کند. و اگر دو بار صدا می‌زند، همان‌طور که خطای بالا نشان داد، دست‌کم `FnMut` لازم است.

اگر یک closure از نوع `FnOnce` را دو بار صدا بزنیم چه می‌شود؟

```rust
let s = String::from("hello");
let f = move || s; // s را برمی‌گرداند، پس فقط یک بار اجرا می‌شود
let a = f();
let b = f();
```

```text
error[E0382]: use of moved value: `f`
 --> src/bin/once_twice.rs:5:13
  |
4 |     let a = f();
  |             --- `f` moved due to this call
5 |     let b = f();
  |             ^ value used here after move
  |
note: closure cannot be invoked more than once because it moves the variable `s` out of its environment
note: this value implements `FnOnce`, which causes it to be moved when called
```

فراخوانی اول `s` را به صدازننده می‌دهد، پس برای بار دوم چیزی در closure نمانده. صدا زدن یک closure از نوع `FnOnce` خود closure را مصرف می‌کند، و معنی «`f` moved due to this call» همین است.

### برگرداندن closure

یک تابع می‌تواند closure هم برگرداند. اگر یک closure مشخص برمی‌گرداند، `impl Fn(...)` را به‌عنوان نوع برگشتی بنویسید. اگر شاخه‌های مختلف closure‌های مختلف برمی‌گردانند، هر closure نوع پنهان خودش را دارد و نمی‌شود همه را زیر یک `impl` آورد. در این حالت آن‌ها را در یک `Box<dyn Fn(...)>` بگذارید، یعنی جعبه‌ای که «یک closure با این امضا» را نگه می‌دارد:

```rust
fn make_adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + n
}

fn make_op(kind: &str) -> Box<dyn Fn(i32) -> i32> {
    match kind {
        "double" => Box::new(|x| x * 2),
        _ => Box::new(|x| x + 100),
    }
}
```

```text
15
14 107
```

`make_adder(5)` closure‌ای می‌دهد که ۵ را اضافه می‌کند و صدا زدنش با ۱۰ برابر `15` است. `make_op("double")(7)` برابر `14` است و `make_op("other")(7)` برابر `107`. `move` در `make_adder` به همان دلیلی لازم است که بالا دیدیم: `n` یک متغیر محلی است. `Box` واقعاً چیست را در مقاله‌ی بعد می‌گویم؛ فعلاً آن را «راهی برای نگه‌داشتن مقداری که اندازه‌اش را کامپایلر نمی‌داند» بخوانید.

## iterator: یکی‌یکی

closure‌ها وقتی با iterator‌ها بیایند بیشترین فایده را دارند. **iterator** مقداری است که عنصرهای یک دنباله را یکی‌یکی تحویل می‌دهد. trait به اسم {{< term "rust-iterator" "Iterator" >}} فقط یک متد می‌خواهد: `next`. هر فراخوانی `Some(item)` برمی‌گرداند و وقتی عنصرها تمام شود `None`.

کمتر پیش می‌آید که خودتان `next` را صدا بزنید. حلقه‌ی `for` این کار را برایتان می‌کند. یک `Vec` از سه راه iterator می‌دهد و تفاوتشان در این است که عنصرها چه هستند:

```rust
let mut v = vec![String::from("a"), String::from("b")];
for s in v.iter() { println!("iter: {s}"); }           // عنصرها &String
for s in v.iter_mut() { s.push('!'); }                 // عنصرها &mut String
println!("after iter_mut: {v:?}");
for s in v.into_iter() { println!("into_iter: {s}"); } // عنصرها String، v منتقل می‌شود
```

```text
iter: a
iter: b
after iter_mut: ["a!", "b!"]
into_iter: a!
into_iter: b!
```

`iter()` هر عنصر را قرض می‌دهد (فقط خواندنی)، `iter_mut()` هر عنصر را برای تغییر دادن قرض می‌دهد (به هر دو رشته `!` اضافه کردیم)، و `into_iter()` خود عنصرها را می‌دهد و وکتور را مصرف می‌کند. بعد از حلقه‌ی آخر `v` دیگر وجود ندارد، دقیقاً مثل هر move دیگر.

## adapter و consumer

قدرت واقعی در زنجیر کردن است. روی یک iterator دو نوع متد هست:

- **adapter**‌ها یک iterator را به iterator دیگری تبدیل می‌کنند: `map` هر عنصر را عوض می‌کند، `filter` بعضی را نگه می‌دارد، `take` و `skip` دنباله را می‌برند و غیره. نتیجه‌شان یک iterator جدید است، نه جواب.
- **consumer**‌ها iterator را تا آخر اجرا می‌کنند و جواب می‌دهند: `sum`، `collect`، `any`، `find` و غیره.

اول adapter‌ها، روی `nums = [1, 2, 3, 4, 5, 6]`. هر خط زیر کد است و نتیجه‌ای که demo چاپ کرد:

```rust
nums.iter().map(|n| n * n)                     // [1, 4, 9, 16, 25, 36]
nums.iter().filter(|n| **n % 2 == 0)           // [2, 4, 6]
nums.iter().enumerate().take(2)                // (0, 1) و (1, 2)
names.iter().copied().zip(nums.iter())         // [("a", 1), ("b", 2), ("c", 3)]
nums.iter().skip(4)                            // [5, 6]
nums.iter().take(2).chain(nums.iter().skip(5)) // [1, 2, 6]
words.iter().flat_map(|s| s.split(' '))        // ["hi", "there", "go", "rust"]
```

به زبان ساده: `map` هر عدد را به توان دو می‌رساند؛ `filter` زوج‌ها را نگه می‌دارد؛ `enumerate` هر عنصر را با جایگاهش جفت می‌کند و `take(2)` بعد از دو تا می‌ایستد؛ `zip` دو دنباله را عنصر به عنصر جفت می‌کند (اینجا `names` برابر `["a", "b", "c"]` است)؛ `skip(4)` چهار تای اول را کنار می‌گذارد؛ `chain` دو iterator را پشت سر هم می‌چسباند (دو عنصر اول، و بعد هرچه بعد از رد کردن پنج‌تا می‌ماند)؛ `flat_map` برای هر ورودی تابعی را اجرا می‌کند که چند عنصر برمی‌گرداند و نتیجه‌ها را در یک دنباله‌ی صاف می‌ریزد (`words` برابر `["hi there", "go rust"]` است و هر جمله سر فاصله بریده می‌شود).

یک جزئیات که اول کار همه را گیج می‌کند `**n` در `filter` است. `nums.iter()` عنصرهایی از نوع `&i32` می‌دهد. و `filter` به closure خودش یک reference به عنصر می‌دهد، پس closure یک `&&i32` دریافت می‌کند. دو ستاره شما را به خود عدد می‌رساند. می‌توانید با `.copied()` اول عددها را کپی کنید، یا الگوی `|&&n|` را در پارامتر closure بنویسید. هر سه شکل (`**n` و `.copied()` و `|&&n|`) را در یک برنامه‌ی کوچک اجرا کردم و هر کدام نتیجه‌ی مورد انتظار را داد.

حالا consumer‌ها، روی همان فهرست:

```rust
nums.iter().sum::<i32>()                                      // 21
nums.iter().fold(String::new(), |acc, n| format!("{acc}{n}")) // "123456"
nums.iter().any(|&n| n > 5)                                   // true
nums.iter().all(|&n| n > 0)                                   // true
nums.iter().find(|&&n| n > 3)                                 // Some(4)
nums.iter().find(|&&n| n > 9)                                 // None
```

`sum` همه را جمع می‌کند. `fold` با یک مقدار اولیه (رشته‌ی خالی) شروع می‌کند و آن را به‌ترتیب با هر عنصر ترکیب می‌کند، و به همین ترتیب `123456` ساخته می‌شود. `any` می‌پرسد «دست‌کم یکی هست که شرط را داشته باشد؟» و `all` می‌پرسد «همه شرط را دارند؟». `find` اولین عنصر مطابق را داخل `Option` برمی‌گرداند، برای همین یک بار `Some(4)` گرفتیم و یک بار `None` (هیچ عددی از ۹ بزرگ‌تر نیست). و `collect` که بالاتر استفاده کردیم از عنصرها یک مجموعه می‌سازد: `Vec`، `HashMap`، `String` و غیره. نوعی که می‌خواهید تعیین می‌کند چه چیزی بگیرید.

## iterator‌ها تنبل‌اند

حالا بخشی که همه را غافلگیر می‌کند. ساختن یک زنجیر از adapter‌ها هیچ چیزی را اجرا نمی‌کند. adapter فقط کار را توصیف می‌کند؛ کار وقتی انجام می‌شود که یک consumer عنصرها را یکی‌یکی از زنجیر بکشد. با یک `println!` داخل `map` نشانش می‌دهم:

```rust
let nums = vec![1, 2, 3];
let it = nums.iter().map(|n| {
    println!("  map sees {n}");
    n * 10
});
println!("adapter built, nothing printed yet");
let out: Vec<i32> = it.collect();
println!("collected {out:?}");
```

```text
adapter built, nothing printed yet
  map sees 1
  map sees 2
  map sees 3
collected [10, 20, 30]
```

خط «adapter built» اول آمد و پیش از آن هیچ خط «map sees» نیست. closure تا وقتی `collect` شروع به خواستن عنصر نکرد اجرا نشد. به این رفتار می‌گویند ارزیابی تنبل (lazy)، و دلیل اینکه زنجیرهای بلند آن‌قدر که می‌ترسید کند نیستند هم همین است: در هر قدم یک فهرست جدید ساخته نمی‌شود. هر عنصر یکی‌یکی از کل زنجیر می‌گذرد.

روی دیگرش یک تله است: اگر یک adapter بسازید و هیچ‌وقت مصرفش نکنید، هیچ اتفاقی نمی‌افتد. کامپایلر می‌داند این اشتباه رایج است و هشدار می‌دهد:

```rust
nums.iter().map(|n| println!("saw {n}"));
println!("done");
```

```text
warning: unused `Map` that must be used
 --> src/bin/x_unused.rs:3:5
  |
3 |     nums.iter().map(|n| println!("saw {n}"));
  |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  |
  = note: iterators are lazy and do nothing unless consumed
  = note: `#[warn(unused_must_use)]` on by default
```

برنامه کامپایل می‌شود و فقط `done` چاپ می‌کند؛ هیچ خط «saw»ای نیست. (کامپایلر یک هشدار دوم هم داد و `for_each` را پیشنهاد کرد، که ابزار درست برای وقتی است که می‌خواهید یک closure را فقط برای اثر جانبی‌اش اجرا کنید.)

## iterator خودتان

چون `Iterator` فقط `next` می‌خواهد، با نوشتن همین یک متد هر نوعی را می‌توانید iterator کنید. یک شمارش معکوس:

```rust
struct Countdown(u32);

impl Iterator for Countdown {
    type Item = u32;
    fn next(&mut self) -> Option<u32> {
        if self.0 == 0 {
            None
        } else {
            self.0 -= 1;
            Some(self.0 + 1)
        }
    }
}
```

`type Item = u32` می‌گوید iterator چه چیزی تولید می‌کند. `next` وقتی شمارنده به صفر برسد `None` برمی‌گرداند؛ وگرنه شمارنده را کم می‌کند و مقدار قبل از کم‌شدن را برمی‌گرداند. حالا همه‌ی adapter‌ها و consumer‌ها بدون هیچ کد اضافه روی آن کار می‌کنند:

```rust
let v: Vec<u32> = Countdown(5).collect();
let s: u32 = Countdown(5).filter(|n| n % 2 == 1).map(|n| n * n).sum();
for n in Countdown(3) { println!("tick {n}"); }
```

```text
[5, 4, 3, 2, 1]
35
tick 3
tick 2
tick 1
```

عددهای فرد در ۵ و ۴ و ۳ و ۲ و ۱ برابر ۵ و ۳ و ۱ هستند؛ مربع‌هایشان ۲۵ و ۹ و ۱ است و جمع `35` می‌شود. و حلقه‌ی `for` هم روی آن کار می‌کند، چون `for` فقط تا رسیدن به `None` مدام `next` را صدا می‌زند.

## حلقه و زنجیر iterator کنار هم

یک کار کوچک واقعی: شمردن اینکه هر کلمه‌ی بلندتر از دو حرف چند بار در یک متن آمده، بدون توجه به بزرگی و کوچکی حروف. اول با حلقه‌ی `for`، بعد با زنجیر iterator:

```rust
fn loop_version(text: &str) -> Vec<(String, usize)> {
    let mut counts: HashMap<String, usize> = HashMap::new();
    for w in text.split_whitespace() {
        let w = w.to_lowercase();
        if w.len() > 2 {
            *counts.entry(w).or_insert(0) += 1;
        }
    }
    let mut out: Vec<(String, usize)> = counts.into_iter().collect();
    out.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}

fn iter_version(text: &str) -> Vec<(String, usize)> {
    let counts = text
        .split_whitespace()
        .map(|w| w.to_lowercase())
        .filter(|w| w.len() > 2)
        .fold(HashMap::new(), |mut m, w| {
            *m.entry(w).or_insert(0usize) += 1;
            m
        });
    let mut out: Vec<_> = counts.into_iter().collect();
    out.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}
```

هر دو نتیجه را اول بر اساس تعداد (بیشتر اول) و بعد بر اساس خود کلمه مرتب می‌کنند تا خروجی ثابت باشد. روی `"the cat and The dog and a bird saw the cat"` demo سه ورودی اول را چاپ می‌کند و بررسی می‌کند که دو نسخه یکسان باشند:

```text
[("the", 3), ("and", 2), ("cat", 2)]
same result: true
```

«the» سه بار آمده (یک بار به شکل «The»)، «and» و «cat» دو بار، و «a» که یک‌حرفی است فیلتر شده. به نظر من وقتی واژگان را بدانید زنجیر خواناتر است، ولی حلقه هم به همان اندازه درست است، و هیچ‌کدام را benchmark نکرده‌ام.

## تله‌ها در closure و iterator

- **`iter()` reference می‌دهد.** برای همین closure‌های `filter` یک `&&i32` می‌بینند و با الگوهایی مثل `|&&n|` روبه‌رو می‌شوید. اگر ستاره‌ها اذیتتان می‌کنند، اول از `.copied()` یا `.cloned()` استفاده کنید.
- **`into_iter()` روی `Vec` آن را مصرف می‌کند.** وکتور منتقل می‌شود و بعدش نمی‌توانید از آن استفاده کنید. اگر هنوز به داده نیاز دارید از `iter()` استفاده کنید.
- **closure‌ای که فقط `FnOnce` است جایی که `Fn` یا `FnMut` لازم است قبول نمی‌شود.** خطا از طرف تابعی می‌آید که closure را به آن می‌دهید، نه از خود closure، همان‌طور که مثال `call_twice` نشان داد.
- **یک `Vec` نسازید فقط برای اینکه رویش حلقه بزنید.** adapter‌ها را زنجیر کنید و مستقیم مصرفشان کنید؛ فقط وقتی خود مجموعه را لازم دارید `collect` کنید.
- **تنبلی یعنی اثر جانبی ممکن است هیچ‌وقت اجرا نشود.** یک `println!` داخل `map` فقط وقتی اجرا می‌شود که چیزی iterator را مصرف کند. برای اثر جانبی از حلقه‌ی `for` یا `for_each` استفاده کنید.

## تمرین

۱. تابعی بنویسید که `&[i32]` بگیرد و مجموع مربع‌های عددهای فرد را با یک زنجیر iterator برگرداند.
۲. `fn make_counter() -> impl FnMut() -> u32` را بنویسید که در فراخوانی‌های پشت سر هم ۱ و ۲ و ۳ برگرداند. به چه کلمه‌ای نیاز دارید و چرا؟
۳. `Iterator` را برای یک struct به اسم `Fib` پیاده کنید و ده مقدار اولش را با `take(10)` چاپ کنید.

## قدم بعدی

در این مقاله `Box<dyn Fn>` بدون توضیح درست آمد. مقاله‌ی بعد، «Smart Pointerها: Box، Rc و RefCell در Rust»، می‌گوید `Box` واقعاً چیست و smart pointer‌های دیگر به چه کاری می‌آیند.
