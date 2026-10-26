+++
date = '2026-11-28T10:00:00+03:30'
draft = false
title = 'Collectionها و String در Rust'
description = 'مروری عملی بر Vec، HashMap، HashSet، BTreeMap، String و &str در Rust: panic خارج از محدوده، خطای borrow، تفاوت بایت و کاراکتر در UTF-8 و شمارش کلمه.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "collections", "vec", "hashmap", "string"]
cover = { image = "/images/covers/rust-collections-strings.fa.png", alt = "Collectionها و String در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-structs-enums-pattern-matching/) با struct و enum نوع‌های خودمان را ساختیم. حالا سراغ نوع‌های کتاب‌خانه‌ی استاندارد می‌رویم که چند مقدار را نگه می‌دارند: **Vec**، **HashMap** و همراهانشان، و دو نوع رشته. اینجا ownership و borrowing از تئوری بیرون می‌آیند، چون کامپایلر کدی را رد می‌کند که در Go یا Node.js کاملاً عادی به نظر می‌رسد. کد را اجرا می‌کنیم و پیام‌های واقعی را می‌خوانیم.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 و به‌صورت یک مثال محلی کامپایل و اجرا شده‌اند.

## Vec

`Vec<T>` یک آرایه‌ی قابل رشد روی heap است؛ نزدیک‌ترین چیز به slice در Go که هر روز استفاده می‌کنید.

```rust
let mut v = vec![10, 20, 30];
v.push(40);
println!("{:?} len={}", v, v.len());
println!("get(1) = {:?}, get(9) = {:?}", v.get(1), v.get(9));
for x in &v {
    print!("{x} ");
}
println!();
for x in &mut v {
    *x += 1;
}
println!("{:?}", v);
```

```text
[10, 20, 30, 40] len=4
get(1) = Some(20), get(9) = None
10 20 30 40 
[11, 21, 31, 41]
```

`v[i]` فرض می‌کند اندیس معتبر است؛ `v.get(i)` یک `Option` برمی‌گرداند و تصمیم با شماست. اندیس خارج از محدوده panic می‌دهد. با `v[v.len() + 6]` روی همان vector چهارتایی:

```text
thread 'main' panicked at src/bin/vecs.rs:15:21:
index out of bounds: the len is 4 but the index is 10
```

پیمایش با `&v` برداری را فقط‌خواندنی قرض می‌گیرد؛ `&mut v` آن را قابل تغییر قرض می‌گیرد تا با `*x` عنصرها را عوض کنید. پیمایش با خودِ `v` آن را داخل حلقه move می‌کند.

## Borrow checker و Vec

مثال کلاسیک: یک reference به عنصر اول بگیرید، `push` کنید، و بعد از reference استفاده کنید:

```rust
let mut v = vec![1, 2, 3];
let first = &v[0];
v.push(4);
println!("{first}");
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/bin/vec_borrow.rs:4:5
  |
3 |     let first = &v[0];
  |                  - immutable borrow occurs here
4 |     v.push(4);
  |     ^^^^^^^^^ mutable borrow occurs here
5 |     println!("{first}");
  |                ----- immutable borrow later used here
```

`push` ممکن است بافر را دوباره allocate کند و آن‌وقت `first` به حافظه‌ی آزادشده اشاره می‌کرد. در Go مشکل مشابهی هست (slice کهنه بعد از `append`) و کامپایل هم می‌شود؛ Rust آن را رد می‌کند. راه‌حل: کار با `first` را قبل از `push` تمام کنید یا مقدار را کپی کنید.

## HashMap، HashSet و BTreeMap

```rust
let mut ages: HashMap<String, u32> = HashMap::new();
ages.insert("ali".to_string(), 30);
ages.insert("sara".to_string(), 25);
println!("{:?} {:?}", ages.get("sara"), ages.get("nobody"));
ages.insert("sara".to_string(), 26); // مقدار قبلی را عوض می‌کند
*ages.entry("reza".to_string()).or_insert(0) += 41;
*ages.entry("reza".to_string()).or_insert(0) += 1;
println!("sara={} reza={} len={}", ages["sara"], ages["reza"], ages.len());
```

```text
Some(25) None
sara=26 reza=42 len=3
```

`get` یک `Option` می‌دهد، پس «وجود ندارد» و «صفر است» ذاتاً دو چیز متفاوت‌اند. `entry(key).or_insert(default)` اصطلاح رایج «اگر نبود بساز، بعد به‌روز کن» است: یک reference قابل تغییر به مقدار برمی‌گرداند که با `*` افزایشش می‌دهیم.

ترتیب پیمایش مشخص نیست. کلیدهای ۰ تا ۷ را گذاشتم و `keys()` را در سه اجرای جدا چاپ کردم:

```text
[3, 5, 6, 2, 4, 0, 1, 7]
[2, 6, 1, 7, 5, 4, 0, 3]
[0, 7, 3, 6, 2, 4, 1, 5]
```

`HashSet<T>` یک map فقط با کلید است؛ اگر مقدار از قبل وجود داشته باشد `insert` مقدار `false` برمی‌گرداند. `BTreeMap` کلیدها را مرتب نگه می‌دارد، به قیمت جست‌وجوی کندتر از hash:

```rust
let mut seen = HashSet::new();
for w in ["a", "b", "a", "c", "b"] {
    if !seen.insert(w) {
        println!("duplicate {w}");
    }
}
println!("unique = {}", seen.len());

let mut sorted = BTreeMap::new();
for (k, v) in [("zed", 1), ("amir", 2), ("mina", 3)] {
    sorted.insert(k, v);
}
println!("{:?}", sorted);
```

```text
duplicate a
duplicate b
unique = 3
{"amir": 2, "mina": 3, "zed": 1}
```

## String و &str

`String` صاحب یک بافر UTF-8 قابل رشد است؛ `&str` یک نمای قرضی روی متن UTF-8 است (یک literal یا بخشی از یک `String`). تابعی که فقط متن را می‌خواند باید `&str` بگیرد. هر دو همیشه UTF-8 معتبرند و `len()` بایت می‌شمارد:

```rust
for w in ["hello", "سلام", "🚀"] {
    println!("{w} bytes={} chars={}", w.len(), w.chars().count());
}
for (i, c) in "سلام".char_indices() {
    print!("{i}:{c} ");
}
println!();
println!("{:?}", "سلام".bytes().take(4).collect::<Vec<u8>>());
println!("{:?}", &"سلام"[0..2]);
```

```text
hello bytes=5 chars=5
سلام bytes=8 chars=4
🚀 bytes=4 chars=1
0:س 2:ل 4:ا 6:م 
[216, 179, 217, 132]
"س"
```

همان اعداد Go: ۸ بایت و ۴ کاراکتر. `chars()` مقدارهای اسکالر Unicode می‌دهد و `bytes()` بایت‌های خام را (216 اولین بایتِ `س` است). برای همین `s[0]` مجاز نیست:

```rust
let s = String::from("salam");
let c = s[0];
```

```text
error[E0277]: the type `str` cannot be indexed by `{integer}`
 --> src/bin/str_index.rs:3:15
  |
3 |     let c = s[0];
  |               ^ string indices are ranges of `usize`
  |
  = note: you can use `.chars().nth()` or `.bytes().nth()`
```

Rust شما را مجبور می‌کند بگویید بایت می‌خواهید یا کاراکتر. برش با بازه مثل `&s[0..2]` مجاز است، ولی بازه باید روی مرز کاراکترها بیفتد؛ اینجا بایت ۰ تا ۲ دقیقاً `س` است.

ساختن و شکستن متن:

```rust
let mut s = String::from("go");
s.push_str("lang");
s.push('!');
let t = format!("{s}-{}", 2026);
println!("{s} {t}");
println!("{:?}", "  go   is \t fun\n".split_whitespace().collect::<Vec<_>>());
```

```text
golang! golang!-2026
["go", "is", "fun"]
```

`format!` یک `String` جدید می‌سازد و آرگومان‌هایش را مصرف نمی‌کند.

## برنامه‌ی کوچک: شمارش تکرار کلمه

همان کار مقاله‌ی Go با همان ورودی:

```rust
let text = "the quick brown fox jumps over the lazy dog the fox";
let mut counts: HashMap<String, u32> = HashMap::new();
for w in text.to_lowercase().split_whitespace() {
    *counts.entry(w.to_string()).or_insert(0) += 1;
}
let mut entries: Vec<(&String, &u32)> = counts.iter().collect();
entries.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
for (word, n) in entries {
    println!("{word:<6} {n}");
}
```

```text
the    3
fox    2
brown  1
dog    1
jumps  1
lazy   1
over   1
quick  1
```

مثل Go ترتیب map مشخص نیست؛ پس ورودی‌ها را در یک `Vec` می‌ریزیم و اول بر اساس تعداد (نزولی) و بعد الفبایی مرتب می‌کنیم. API ی `entry` جای `counts[w]++` در Go را می‌گیرد، که آنجا کار می‌کند چون کلید ناموجود صفر خوانده می‌شود. در Rust کلید ناموجود صریح است.

## چند نکته که باید حواستان باشد

- `v[i]` خارج از محدوده panic می‌دهد؛ برای ورودی‌ای که کنترلش با شما نیست از `get` استفاده کنید.
- نمی‌شود در طول یک `push` یک reference به داخل `Vec` نگه داشت؛ کامپایلر این را اجرا می‌کند.
- به ترتیب `HashMap` تکیه نکنید. برای خروجی ثابت از `BTreeMap` یا مرتب‌سازی استفاده کنید.
- `len()` روی رشته بایت است؛ برای کاراکتر از `chars().count()` استفاده کنید. حتی «کاراکتر» هم همیشه همان چیزی نیست که خواننده یک حرف می‌بیند، چون علامت‌های ترکیبی وجود دارند.
- در پارامتر تابع‌ها `&str` بگیرید؛ وقتی متن تازه می‌سازید `String` برگردانید.
- مقایسه با Go: هدر slice در Go می‌تواند alias شود و بی‌سروصدا حافظه را share کند، اما `Vec` یک owner دارد؛ پس باگ‌های share شدن در مقاله‌ی Go اینجا خطای کامپایل می‌شوند. هزینه‌اش این است که گاهی کد را برای راضی کردن borrow checker بازچینی می‌کنید.

## تمرین

1. شمارنده‌ی کلمه را با `BTreeMap` بنویسید و ببینید چه ترتیبی رایگان می‌گیرید. برای ترتیب بر اساس تعداد هنوز مرتب‌سازی لازم است.
2. یک جمله‌ی فارسی بخوانید، با `split_whitespace` بشکنید و `chars().count()` هر کلمه را چاپ کنید.
3. مثال `vec_borrow` را با کپی کردن عنصر اول (`let first = v[0];`) به‌جای قرض گرفتن، قابل کامپایل کنید.

## قدم بعدی

خیلی از عملیات بالا `Option` برمی‌گرداندند و برنامه‌های واقعی به شکل‌های دیگری هم شکست می‌خورند. در مقاله‌ی بعد سراغ مدیریت خطا با `Result` و `Option` در Rust می‌رویم.
