+++
date = '2026-12-24T10:00:00+03:30'
draft = false
title = 'Closure و Iterator در Rust'
description = 'Closure و iterator در Rust در عمل: حالت‌های capture و move، تفاوت Fn و FnMut و FnOnce، برگرداندن closure، adapterها و consumerها، تنبلی و Iterator سفارشی.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "closures", "iterators", "intermediate"]
cover = { image = "/images/covers/rust-closures-iterators.fa.png", alt = "Closure و Iterator در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-lifetimes/) دیدیم کامپایلر چطور طول عمر referenceها را دنبال می‌کند. Closure و iterator جایی است که این دانش به کار می‌آید: closure یک تابع کوچک است که متغیرهای اطرافش را capture می‌کند، پس باید از همان قانون‌های borrowing پیروی کند. Iteratorها نیمه‌ی دیگرند و با هم جای بیشترِ حلقه‌های اندیس‌دار را می‌گیرند.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 کامپایل و اجرا شده‌اند و خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## Closure و capture

**Closure** یک تابع بی‌نام است که به شکل `|args| body` نوشته می‌شود. نوع پارامترها و مقدار برگشتی استنباط می‌شود و closure می‌تواند از متغیرهای scope بیرونی استفاده کند. Rust برای هر متغیر سبک‌ترین روش capture را انتخاب می‌کند:

```rust
let name = String::from("Roham");
let greet = || println!("hello {name}"); // borrows name
greet();
println!("name still usable: {name}");

let mut count = 0;
let mut inc = || count += 1; // mutable borrow
inc();
inc();
println!("count = {count}");
```

```text
hello Roham
name still usable: Roham
count = 2
```

کلیدواژه‌ی `move` closure را مجبور می‌کند مالکیت چیزهایی را که استفاده می‌کند بگیرد. وقتی closure از تابع فعلی بیشتر عمر می‌کند، مثلاً برگردانده می‌شود، به آن نیاز دارید. بدون آن کامپایلر قبول نمی‌کند:

```text
error[E0373]: closure may outlive the current function, but it borrows `s`, which is owned by the current function
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^            - `s` is borrowed here
  |     |
  |     may outlive borrowed value `s`
help: to force the closure to take ownership of `s` (and any other referenced variables), use the `move` keyword
```

روی دیگر سکه: بعد از `move` متغیر اصلی دیگر در دسترس نیست.

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/use_after_move.rs:5:16
3 |     let f = move || println!("{s}");
  |             -------            - variable moved due to use in closure
  |             |
  |             value moved into closure here
4 |     f();
5 |     println!("{s}");
  |                ^ value borrowed here after move
```

## Fn و FnMut و FnOnce

هر closure بسته به کاری که بدنه‌اش با مقدارهای capture شده می‌کند، یکی یا بیشتر از این سه trait را پیاده می‌کند:

- `Fn`: فقط می‌خواند و چند بار قابل فراخوانی است.
- `FnMut`: مقدارها را تغییر می‌دهد و چند بار قابل فراخوانی است.
- `FnOnce`: یک مقدار capture شده را بیرون می‌برد (move)، پس فقط یک بار قابل فراخوانی است.

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

هر closure از نوع `Fn` همزمان `FnMut` و `FnOnce` هم هست؛ پس تابعی که آرگومانش را فقط یک بار صدا می‌زند بهتر است `FnOnce` بخواهد تا بیشترین حالت‌ها را بپذیرد. صدا زدن دو بارِ closureای که `String` capture شده‌اش را برمی‌گرداند خطا می‌دهد:

```text
error[E0382]: use of moved value: `f`
note: closure cannot be invoked more than once because it moves the variable `s` out of its environment
note: this value implements `FnOnce`, which causes it to be moved when called
```

برای برگرداندن closure، اگر یک closure مشخص دارید از `impl Fn` و اگر شاخه‌های مختلف closureهای متفاوت برمی‌گردانند از `Box<dyn Fn>` استفاده کنید:

```rust
fn make_adder(n: i32) -> impl Fn(i32) -> i32 { move |x| x + n }

fn make_op(kind: &str) -> Box<dyn Fn(i32) -> i32> {
    match kind {
        "double" => Box::new(|x| x * 2),
        _ => Box::new(|x| x + 100),
    }
}
```

`make_adder(5)(10)` برابر `15` و `make_op("double")(7)` برابر `14` می‌شود. `Box` را در مقاله‌ی بعد درست بررسی می‌کنیم. در Go، closure متغیرها را با reference می‌گیرد و garbage collector زنده‌شان نگه می‌دارد (مقاله‌ی [تابع‌ها در Go](/fa/posts/go-functions-defer-errors/)). در Rust شما انتخاب می‌کنید و کامپایلر بررسی می‌کند.

## Iterator

trait به نام **Iterator** یک متد الزامی دارد: `next`، که تا وقتی `None` برنگردانده `Some(item)` می‌دهد. از یک `Vec` سه راه برای گرفتن iterator دارید:

```rust
let mut v = vec![String::from("a"), String::from("b")];
for s in v.iter() { println!("iter: {s}"); }          // &String
for s in v.iter_mut() { s.push('!'); }                // &mut String
println!("after iter_mut: {v:?}");
for s in v.into_iter() { println!("into_iter: {s}"); } // String, v is moved
```

```text
iter: a
iter: b
after iter_mut: ["a!", "b!"]
into_iter: a!
into_iter: b!
```

**Adapterها** یک iterator را به iterator دیگری تبدیل می‌کنند و **consumerها** آن را اجرا می‌کنند و نتیجه می‌دهند. خروجی‌ها از یک اجرا:

```rust
nums.iter().map(|n| n * n)                    // [1, 4, 9, 16, 25, 36]
nums.iter().filter(|n| **n % 2 == 0)          // [2, 4, 6]
nums.iter().enumerate().take(2)               // (0, 1) (1, 2)
names.iter().copied().zip(nums.iter())        // [("a", 1), ("b", 2), ("c", 3)]
nums.iter().skip(4)                           // [5, 6]
nums.iter().take(2).chain(nums.iter().skip(5)) // [1, 2, 6]
words.iter().flat_map(|s| s.split(' '))       // ["hi", "there", "go", "rust"]
```

consumerها روی `[1, 2, 3, 4, 5, 6]`: `sum` برابر `21`، `fold` که رشته می‌سازد `123456`، `any(|&n| n > 5)` برابر `true`، `all(|&n| n > 0)` برابر `true`، و `find` برای `> 3` مقدار `Some(4)` و برای `> 9` مقدار `None`. `collect` از روی نوعی که مشخص می‌کنید یک `Vec` (یا `HashMap`، `String` و غیره) می‌سازد.

## Iteratorها تنبل‌اند

تا وقتی consumer آیتم‌ها را نکشد، adapterها هیچ کاری نمی‌کنند:

```rust
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

اگر adapter بسازید و هرگز استفاده‌اش نکنید، کامپایلر هشدار هم می‌دهد.

## Iterator خودتان

فقط `next` را پیاده کنید تا همه‌ی adapterها و consumerها را مفت داشته باشید:

```rust
struct Countdown(u32);

impl Iterator for Countdown {
    type Item = u32;
    fn next(&mut self) -> Option<u32> {
        if self.0 == 0 { None } else { self.0 -= 1; Some(self.0 + 1) }
    }
}
```

`Countdown(5).collect::<Vec<_>>()` برابر `[5, 4, 3, 2, 1]` است و `Countdown(5).filter(|n| n % 2 == 1).map(|n| n * n).sum()` برابر `35` (یعنی 25 + 9 + 1).

## حلقه یا iterator

شمردن کلمه‌های بلندتر از دو حرف، یک بار با `for` و یک بار با زنجیره‌ی iterator (هر دو در دموی من، مرتب‌شده بر اساس تعداد و بعد کلمه):

```rust
let counts = text
    .split_whitespace()
    .map(|w| w.to_lowercase())
    .filter(|w| w.len() > 2)
    .fold(HashMap::new(), |mut m, w| {
        *m.entry(w).or_insert(0usize) += 1;
        m
    });
```

روی متن `"the cat and The dog and a bird saw the cat"` هر دو نسخه نتیجه‌ی یکسان می‌دهند که با `[("the", 3), ("and", 2), ("cat", 2)]` شروع می‌شود. وقتی واژگان را بلد باشید، زنجیره برای من خواناتر است، ولی حلقه هم کاملاً درست است و هیچ‌کدام را benchmark نکردم.

## چند نکته که باید حواستان باشد

- `iter()` reference می‌دهد، برای همین در `filter` اغلب `&&i32` می‌بینید و الگوهایی مثل `|&&n|` پیدا می‌شوند.
- `into_iter()` روی `Vec` آن را مصرف می‌کند. اگر بعداً داده را لازم دارید از `iter()` استفاده کنید.
- closureای که `FnOnce` است جایی که `Fn` لازم است قبول نمی‌شود.
- به‌جای ساختن یک `Vec` فقط برای حلقه زدن، مستقیم به نوع مورد نیاز `collect` کنید.
- تنبل بودن یعنی side effectهای داخل `map` ممکن است هرگز اجرا نشوند؛ برای side effect از `for` یا `for_each` استفاده کنید.

## تمرین

1. تابعی بنویسید که `&[i32]` بگیرد و مجموع مربع عددهای فرد را با یک زنجیره‌ی iterator برگرداند.
2. تابع `fn make_counter() -> impl FnMut() -> u32` را بنویسید که در فراخوانی‌های پشت‌سرهم 1، 2، 3 را برگرداند.
3. برای یک struct به نام `Fib` تیپ `Iterator` را پیاده کنید و ده مقدار اولش را با `take(10)` چاپ کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ smart pointerها در Rust می‌رویم: `Box`، `Rc` و `RefCell` و اینکه کی به آن‌ها نیاز پیدا می‌کنیم.
