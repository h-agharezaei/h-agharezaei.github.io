+++
date = '2027-02-14T10:00:00+03:30'
draft = false
title = 'ماکروها در Rust'
description = 'نوشتن ماکروی declarative با macro_rules! و ماکروی derive با syn و quote در Rust، همراه با خروجی واقعی، hygiene، باز کردن دستی ماکرو و خطاهای کامپایلر.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "macros", "proc-macro", "intermediate"]
cover = { image = "/images/covers/rust-macros.fa.png", alt = "ماکروها در Rust", hiddenInSingle = true }
+++

در [مقاله‌ی قبل](/fa/posts/rust-trait-objects-dyn/) موضوع traitها بود. حالا سراغ ابزار دیگرِ انتزاع می‌رویم: **ماکرو** (macro). هر روز از آن‌ها استفاده می‌کنید: `println!`، `vec!` و همان `#[derive(Serialize)]` که در [Serde و JSON در Rust](/fa/posts/rust-serde-json/) دیدیم. در این مقاله هر دو نوع را خودمان می‌نویسیم: ماکروی declarative با `macro_rules!` و ماکروی derive در یک crate جدا.

> همه‌چیز را با Rust نسخه‌ی 1.90، `syn` نسخه‌ی 2.0.119، `quote` نسخه‌ی 1.0.47 و `proc-macro2` نسخه‌ی 1.0.107 اجرا کرده‌ام. خروجی‌ها از اجرای واقعی یک workspace محلی کپی شده‌اند.

## ماکرو یعنی کدی که کد می‌نویسد

تابع در زمان اجرا کار می‌کند و مقدار می‌گیرد. ماکرو در زمان کامپایل اجرا می‌شود، *توکن‌ها* را می‌گیرد و کد جدیدی برمی‌گرداند که کامپایلر آن را کامپایل می‌کند. برای همین `println!` می‌تواند تعداد دلخواهی آرگومان بگیرد، کاری که تابع معمولی نمی‌تواند. علامت `!` یعنی این یک فراخوانی ماکرو است.

## ماکروهای declarative

ماکروی `macro_rules!` فهرستی از الگو و قالب است. عبارت `$x:expr` یک expression را می‌گیرد و بخش بعد از `:` همان **fragment specifier** است. بقیه: `ident` (یک نام)، `ty` (یک نوع) و `tt` (یک token tree، منعطف‌ترین حالت).

```rust
macro_rules! square {
    ($x:expr) => { $x * $x };
}

macro_rules! max {
    ($x:expr) => ($x);
    ($x:expr, $($rest:expr),+) => {{
        let a = $x;
        let b = $crate::max!($($rest),+);
        if a > b { a } else { b }
    }};
}
```

عبارت `$(...),+` تکرار است: یک یا چند مورد جداشده با کاما. `max!` با باقی‌مانده‌ی فهرست خودش را صدا می‌زند، پس برای هر تعداد و هر نوعِ `PartialOrd` کار می‌کند:

```text
square!(3 + 1) = 16
max!(3, 9, 4) = 9
max!(2.5, 1.5) = 2.5
```

دقت کنید `square!(3 + 1)` برابر 16 است، نه `3 + 1 * 3 + 1 = 7`. یک fragment از نوع `expr` همچنان یک گره‌ی کامل expression می‌ماند، پس دام جایگزینی متنی در C اینجا وجود ندارد.

یک literal برای `HashMap` با `$(...),*` و کامای انتهایی اختیاری:

```rust
macro_rules! hashmap {
    ($($k:expr => $v:expr),* $(,)?) => {{
        let mut m = ::std::collections::HashMap::new();
        $( m.insert($k, $v); )*
        m
    }};
}
```

عبارت `hashmap!{ "a" => 1, "b" => 2, }` خروجی `[("a", 1), ("b", 2)]` داد (قبل از چاپ مرتب شد). ماکرو می‌تواند item هم تولید کند. این یکی یک `ident` و فهرستی از variantها می‌گیرد:

```rust
macro_rules! make_enum {
    ($name:ident { $($variant:ident),+ $(,)? }) => {
        #[derive(Debug, Clone, Copy, PartialEq)]
        pub enum $name { $($variant),+ }
        impl $name {
            pub const ALL: &'static [$name] = &[$($name::$variant),+];
            pub fn name(&self) -> &'static str {
                match self { $($name::$variant => stringify!($variant)),+ }
            }
        }
    };
}
make_enum!(Color { Red, Green, Blue });
```

پیمایش `Color::ALL` و چاپ `c.name()` مقادیر `Red`، `Green` و `Blue` را داد. یک `make_struct!(Point { x: i32, y: i32 })` هم با fragmentهای `ty` نوشتم که `Point::field_names()` را به شکل `["x", "y"]` چاپ کرد. شمارنده‌ی مبتنی بر `tt` یعنی `count_tts!(a b c d)` عدد 4 را برگرداند.

### باز کردن دستی و hygiene

`cargo expand` به nightly نیاز دارد، پس ماکرو را دستی باز می‌کنیم. `square!(3 + 1)` به `(3 + 1) * (3 + 1)` تبدیل می‌شود و آرگومان یک واحد می‌ماند. یک تست این را ثابت می‌کند:

```rust
assert_eq!(square!(3 + 1), (3 + 1) * (3 + 1));
```

```text
test tests::square_expansion_is_equivalent ... ok
```

**Hygiene** یعنی متغیرهایی که داخل ماکرو ساخته می‌شوند scope خودشان را دارند. `max!` داخل خودش متغیر `a` دارد و من آن را با `a` خودم صدا زدم:

```rust
let a = 100;
let r = max!(a, 7);  // a = 100, max!(a, 7) = 100
let x = 10;
double_with_temp!(x) // macro has `let x = 2; $e * x` -> 20
```

مورد دوم 20 چاپ می‌کند، نه 4: `x` ماکرو و `x` من دو متغیر متفاوت‌اند.

### خطا وقتی ماکرو را اشتباه صدا می‌زنید

`square!(3, 4)` با هیچ قاعده‌ای جور نمی‌شود:

```text
error: no rules expected `,`
 --> demo/src/bin/bad_square.rs:3:29
  |
3 |     println!("{}", square!(3, 4));
  |                             ^ no rules expected this token in macro call
  |
note: while trying to match meta-variable `$x:expr`
```

این‌طور بخوانید: «قاعده یک `expr` می‌خواست و به کاما رسید». چنین خطاهایی هم به محل فراخوانی اشاره می‌کنند و هم به تعریف ماکرو.

## ماکروی derive

ماکروهای procedural توابعی در Rust هستند که توکن را به توکن تبدیل می‌کنند و باید در یک crate با `proc-macro = true` باشند. پس از یک workspace استفاده می‌کنیم: `describe_derive` (خودِ ماکرو) و `demo` (کاربر آن). وابستگی‌ها: `syn = "2"` توکن‌ها را به درخت نحوی تبدیل می‌کند، `quote = "1"` از روی یک قالب توکن می‌سازد و `proc-macro2` نوع توکنِ مشترک است.

```rust
#[proc_macro_derive(Describe)]
pub fn derive_describe(input: TokenStream) -> TokenStream {
    let ast = parse_macro_input!(input as DeriveInput);
    let name = &ast.ident;
    let fields = match &ast.data {
        Data::Struct(s) => match &s.fields {
            Fields::Named(f) => &f.named,
            _ => return syn::Error::new_spanned(name,
                "Describe needs a struct with named fields").to_compile_error().into(),
        },
        _ => return syn::Error::new_spanned(name,
            "Describe can only be derived for structs").to_compile_error().into(),
    };
    let lines: Vec<String> = fields.iter().map(|f| {
        let ty = &f.ty;
        format!("{}: {}", f.ident.as_ref().unwrap(),
                quote!(#ty).to_string().replace(" ", ""))
    }).collect();
    let title = name.to_string();
    quote! {
        impl #name {
            pub fn describe() -> String {
                let mut out = String::from(#title);
                #( out.push_str("\n  "); out.push_str(#lines); )*
                out
            }
        }
    }.into()
}
```

استفاده: `#[derive(Describe)] struct User { name: String, age: u32, tags: Vec<String>, email: Option<String> }` و `println!("{}", User::describe())`:

```text
User
  name: String
  age: u32
  tags: Vec<String>
  email: Option<String>
```

روی یک `enum`، ماکرو یک `compile_error!` وابسته به span (یعنی نام `Shape`) برمی‌گرداند، پس پیام در جای درست نمایش داده می‌شود:

```text
error: Describe can only be derived for structs
 --> demo/src/bin/bad_derive.rs:4:6
  |
4 | enum Shape {
  |      ^^^^^
```

`serde` هم از نظر مفهومی همین کار را می‌کند: derive آن struct شما را با `syn` می‌خواند، سپس با `quote` کد `impl Serialize` تولید می‌کند و attributeهایی مثل `#[serde(rename)]` را اعمال می‌کند. دو نوع دیگر از ماکروی procedural هم هست: attribute-like (مثل `#[route(GET, "/")]` که آیتمِ متصل‌شده را جایگزین می‌کند) و function-like (مثل `sql!(...)` که مثل `macro_rules!` صدا زده می‌شود اما با کد Rust نوشته شده است).

## چند نکته که باید حواستان باشد

- تابع یا generics را ترجیح بدهید. فقط برای آرگومان متغیر، سینتکس جدید یا تولید itemهای تکراری سراغ ماکرو بروید.
- ماکرو هزینه‌ی زمان کامپایل (باید crate ماکرو و `syn` ساخته شوند) و خوانایی دارد و پیام خطا بدتر می‌شود.
- با تست‌های کوچک و ورودی کوچک اشکال‌زدایی کنید؛ باز کردن دستی مثل بالا عادت خوبی است.
- داخل ماکروهای export شده همیشه از `$crate::` و مسیر کامل مثل `::std::collections::HashMap` استفاده کنید.
- به‌جای panic، یک `syn::Error` با span مناسب برگردانید.

## تمرین

۱. ماکروی `min!` را شبیه `max!` بنویسید و `min!(5, 2, 8)` را تست کنید.
۲. `Describe` را طوری گسترش دهید که `field_count() -> usize` هم تولید کند.

## قدم بعدی

مقاله‌ی بعد درباره‌ی unsafe و FFI در Rust است: `unsafe` واقعاً چه اجازه‌ای می‌دهد و چطور کد C را صدا بزنیم.
