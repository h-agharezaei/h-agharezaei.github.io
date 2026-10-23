+++
date = '2027-03-06T10:00:00+03:30'
draft = false
title = 'الگوی Type-State و طراحی API در Rust'
description = 'طراحی API در Rust برای ناممکن کردن حالت نامعتبر: newtype، builder از نوع type-state، sealed trait، non_exhaustive و must_use با خطاهای واقعی کامپایلر.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "typestate", "api-design", "advanced"]
cover = { image = "/images/covers/rust-typestate-patterns.fa.png", alt = "الگوی Type-State و طراحی API در Rust", hiddenInSingle = true, hiddenInList = true }
+++

موضوع قبلی tracing بود. این مقاله درباره‌ی چیزی است که پیش از هر خط log اتفاق می‌افتد: طراحی API طوری که اصلاً نشود باگ را نوشت. اسم این ایده «حالت نامعتبر را غیرقابل بیان کن» است (**make invalid states unrepresentable**). ابزارهایش را داریم: [struct و enum](/fa/posts/rust-structs-enums-pattern-matching/)، [جنریک‌ها و trait‌ها](/fa/posts/rust-generics-traits/) و مهم‌تر از همه [ownership](/fa/posts/rust-ownership/)، چون متدی که `self` را مصرف می‌کند یک move است و همین move است که type-state را ممکن می‌کند. همه‌چیز با Rust 1.90 (edition 2024) در یک workspace کوچک اجرا شد: یک کتاب‌خانه‌ی `api`، یک برنامه‌ی `app` و یک crate به اسم `fails` که برای هر خطای کامپایل یک برنامه‌ی کوچک دارد تا همه‌ی خطاها قابل تکرار باشند.

## Newtype و constructor اعتبارسنج

برای کامپایلر، شناسه‌ی کاربر و شناسه‌ی سفارش هر دو `u64` هستند. **newtype** یک tuple struct تک‌فیلدی است که این را درست می‌کند:

```rust
pub struct UserId(pub u64);
pub struct OrderId(pub u64);

pub struct Email(String); // فیلد خصوصی است

impl Email {
    pub fn parse(s: &str) -> Result<Email, String> {
        match s.split_once('@') {
            Some((u, d)) if !u.is_empty() && d.contains('.') => Ok(Email(s.to_string())),
            _ => Err(format!("invalid email: {s}")),
        }
    }
}
```

چون فیلد خصوصی است، تنها راه ساخت `Email` همان `parse` است؛ پس هر `Email` در برنامه معتبر است. `Email::parse("roham@example.com")` مقدار `Ok` داد و `Email::parse("nope")` مقدار `Err("invalid email: nope")`. مقدار `size_of::<UserId>()` برابر ۸ است، مثل `u64`. و اگر `OrderId` را جای `UserId` بدهیم:

```text
error[E0308]: mismatched types
 --> fails/src/bin/newtype.rs:9:30
9 |     println!("{}", load_user(order));
  |                    --------- ^^^^^ expected `UserId`, found `OrderId`
```

## Builder و ضعفش

builder کلاسیک فیلدها را در `Option` نگه می‌دارد و در `build()` بررسی می‌کند:

```rust
pub fn build(self) -> Result<Request, String> {
    let url = self.url.ok_or("url is required")?;
    Ok(Request { url, timeout_ms: self.timeout_ms.unwrap_or(1000) })
}
```

بدون url خروجی `Err("url is required")` بود. کار می‌کند، اما اشتباه در زمان اجرا پیدا می‌شود، شاید در production. کامپایلر می‌داند چه متدهایی صدا زده‌ایم؛ بگذاریم خودش بررسی کند.

## Builder از نوع type-state

حالت را در یک پارامتر نوع بگذارید. `PhantomData<S>` به struct اجازه می‌دهد از `S` «استفاده کند» بدون اینکه چیزی ذخیره کند:

```rust
pub struct NoUrl;
pub struct HasUrl;

pub struct RequestBuilder<S> { url: Option<String>, timeout_ms: u64, _state: PhantomData<S> }

impl RequestBuilder<NoUrl> {
    pub fn new() -> Self { /* ... */ }
    pub fn url(self, u: impl Into<String>) -> RequestBuilder<HasUrl> { /* ... */ }
}
impl<S> RequestBuilder<S> {
    pub fn timeout_ms(mut self, t: u64) -> Self { self.timeout_ms = t; self }
}
impl RequestBuilder<HasUrl> {
    pub fn build(self) -> Request { /* ... */ }
}
```

عبارت `RequestBuilder::new().timeout_ms(50).url("http://x").build()` کامپایل شد و `Request { url: "http://x", timeout_ms: 50 }` چاپ کرد. دیگر `Result` نداریم. صدا زدن زودهنگام `build`:

```text
error[E0599]: no method named `build` found for struct `RequestBuilder<NoUrl>` in the current scope
  = note: the method was found for
          - `RequestBuilder<HasUrl>`
```

و چون `build(self)` builder را مصرف می‌کند، استفاده‌ی دوباره هم رد می‌شود؛ اینجا ownership کار را انجام می‌دهد:

```text
error[E0382]: use of moved value: `b`
5 |     let first = b.build();
  |                   ------- `b` moved due to this method call
6 |     let second = b.build();
  |                  ^ value used here after move
```

## ماشین حالت

همین ترفند برای چرخه‌ی عمر: `Order<Draft>`، `Order<Paid>` و `Order<Shipped>`. هر انتقال `self` را می‌گیرد و حالت بعدی را برمی‌گرداند، پس حالت قبلی از بین می‌رود.

```rust
impl Order<Draft> { pub fn pay(self) -> Order<Paid> { /* ... */ } }
impl Order<Paid>  { pub fn ship(self) -> Order<Shipped> { /* ... */ } }
```

عبارت `Order::new(OrderId(42)).add("book").add("pen").pay().ship().tracking()` مقدار `TRK-42` چاپ کرد. ارسال یک پیش‌نویس:

```text
error[E0599]: no method named `ship` found for struct `Order<api::Draft>` in the current scope
  = note: the method was found for
          - `Order<api::Paid>`
```

هزینه‌ی زمان اجرا ندارد: اندازه‌ها `draft=32 paid=32 shipped=32 PhantomData<Draft>=0` چاپ شد. marker اندازه‌ی صفر دارد، پس سه حالت چیدمان یکسان دارند.

## وقتی حالت در زمان اجرا مشخص می‌شود

وضعیتی که از دیتابیس می‌خوانیم در زمان کامپایل معلوم نیست. راه معمول یک enum است که حالت‌های تایپ‌دار را در خود نگه می‌دارد، و یک `match` در مرز برنامه:

```rust
pub enum AnyOrder { Draft(Order<Draft>), Paid(Order<Paid>), Shipped(Order<Shipped>) }
```

`AnyOrder::from_db(1, "paid")` یک سفارش پرداخت‌شده ساخت و `advance()` آن را به shipped برد. داخل هر شاخه دوباره در کد تایپ‌دار هستید. محدودیت‌ها را بدانید: هر محور حالت اضافه، تعداد نوع‌ها را ضرب می‌کند (دو پرچم مستقل چهار ترکیب می‌شود)، پیام‌های خطا نوع‌های جنریک را نشان می‌دهند، و برای چند حالت ساده یک فیلد enum معمولی اغلب ساده‌تر است. type-state را وقتی بگیرید که ترتیب فراخوانی‌ها واقعاً یک invariant است.

## ابزارهای دیگر طراحی API

**Sealed trait** جلوی پیاده‌سازی trait شما توسط crate‌های بیرونی را می‌گیرد. trait عمومی یک supertrait در ماژول خصوصی می‌خواهد:

```rust
mod private { pub trait Sealed {} }
pub trait Currency: private::Sealed { fn code(&self) -> &'static str; }
```

در crate دیگر، `impl Currency for Btc` خطا می‌دهد:

```text
error[E0277]: the trait bound `Btc: api::private::Sealed` is not satisfied
  = note: `Currency` is a "sealed trait", because to implement it you also need to implement `api::private::Sealed`, which is not accessible
```

**`#[non_exhaustive]`** اجازه می‌دهد بعداً variant یا فیلد اضافه کنید بدون breaking change. از crate دیگر:

```text
error[E0004]: non-exhaustive patterns: `_` not covered
  = note: `Event` is marked as non-exhaustive, so a wildcard `_` is necessary to match exhaustively
error[E0639]: cannot create non-exhaustive struct using struct expression
```

**`#[must_use]`** نتیجه‌ی فراموش‌شده را به warning تبدیل می‌کند: `warning: unused return value of `with_tax` that must be used` به‌همراه پیامی که خودمان نوشتیم.

دو عادت کوچک‌تر. آرگومان را `impl Into<String>` یا `impl AsRef<str>` بگیرید تا `&str` و `String` هر دو برسند (`greet("a")` و `greet(String::from("b"))` هر دو کار کردند). و `Default` را پیاده کنید و از struct update syntax استفاده کنید: `Options { retries: 5, ..Default::default() }` مقدار `Options { timeout_ms: 1000, retries: 5, verbose: false }` چاپ کرد.

## چند نکته‌ی مهم

- type-state فقط از کسی محافظت می‌کند که از API تایپ‌دار استفاده می‌کند؛ فیلد `pub` یا constructor عمومی می‌تواند آن را دور بزند.
- فیلد marker را خصوصی و نوع‌های marker را unit struct نگه دارید.
- اگر انتقال می‌تواند شکست بخورد، `Result<Order<Paid>, Error>` برگردانید؛ وگرنه فراخواننده مقدار قبلی را از دست می‌دهد.
- افزودن `#[non_exhaustive]` به نوع موجود، خودش برای کد پایین‌دستی breaking change است.
- جایی که یک بررسی زمان اجرا با خطای روشن کافی است، type-state نگیرید.

## مقایسه با Go

Go در عمل type-state ندارد. ابزار معمول constructor‌های `NewX` است که مقدار اجباری را پارامتر می‌کنند، و الگوی functional options (`type Option func(*Server)`) برای مقدارهای اختیاری. مقدار اجباری با قرار گرفتن در امضای constructor تضمین می‌شود، اما صدا زدن متد به ترتیب اشتباه را چیزی نمی‌گیرد و خطا در زمان اجرا می‌آید.

## تمرین

۱. حالت `Cancelled` را اضافه کنید که فقط از `Draft` قابل رسیدن باشد و بررسی کنید `Order<Shipped>` متد `cancel` ندارد.
۲. برای `Email` پیاده‌سازی `AsRef<str>` بنویسید و آن را به `greet` بدهید.

## قدم بعدی

مقاله‌ی بعد: Docker، CI و release یک سرویس Rust.
