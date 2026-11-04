+++
date = '2027-03-06T10:00:00+03:30'
draft = false
title = 'الگوی Type-State و طراحی API در Rust'
description = 'طراحی API در Rust برای ناممکن کردن حالت نامعتبر: newtype، builder از نوع type-state، sealed trait، non_exhaustive و must_use با خطاهای واقعی کامپایلر.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "typestate", "api-design", "advanced"]
cover = { image = "/images/covers/rust-typestate-patterns.fa.png", alt = "الگوی Type-State و طراحی API در Rust", hiddenInSingle = true }
+++

یک سفارش باید پیش از ارسال پرداخت شده باشد. همه‌ی اعضای تیم این را می‌دانند و باز هم روزی کسی روی سفارشی که هنوز پیش‌نویس است `ship` را صدا می‌زند. دفاع معمول یک `if status != Paid { return Err(...) }` ابتدای `ship` است. کار می‌کند، ولی اشتباه وقتی پیدا می‌شود که کد اجرا شود؛ شاید در production، شاید نیمه‌شب.

یک نسخه‌ی کوچک‌تر از همین مسئله: برای کامپایلر، user id و order id که هر دو `u64` هستند یک type‌اند. پس `load_user(order_id)` بی‌هیچ شکایتی کامپایل می‌شود و چیز اشتباهی را بار می‌کند.

در هر دو مورد، اطلاعاتی که کامپایلر لازم دارد («این مقدار یک order id است»، «این سفارش هنوز پیش‌نویس است») پیش ما هست ولی جایی نوشته نشده که کامپایلر ببیند. این مقاله درباره‌ی نوشتن آن در type‌هاست، تا اصلاً نشود باگ را تایپ کرد. اسم این ایده «حالت نامعتبر را غیرقابل بیان کن» است (make invalid states unrepresentable). این کار پیش از [هر خط log](/fa/posts/rust-tracing-observability/) می‌آید: بهترین باگی که باید عیب‌یابی کنید باگی است که کامپایل نشد.

ابزارهایش را داریم: [struct و enum](/fa/posts/rust-structs-enums-pattern-matching/)، [جنریک‌ها و trait‌ها](/fa/posts/rust-generics-traits/) و مهم‌تر از همه [ownership](/fa/posts/rust-ownership/). متدی که `self` را by value می‌گیرد مقدار را *move* می‌کند، و همین move است که الگوی پایین، type-state، را ممکن می‌کند.

> همه‌چیز را با Rust نسخه‌ی 1.90 (`rustc 1.90.0`، edition 2024) در یک workspace کوچک بدون وابستگی اجرا کرده‌ام: یک crate کتاب‌خانه‌ای به نام `api` با همه‌ی type‌ها، یک برنامه‌ی `app` که از آن‌ها استفاده می‌کند و یک crate به نام `fails` که برای هر خطای کامپایل یک برنامه‌ی کوچک دارد، تا هر خطا جداگانه قابل تکرار باشد. برای این نسخه‌ی مقاله همه را دوباره اجرا کردم. خطاهای کامپایلر به خط‌های مهم کوتاه شده‌اند و خط‌های `note:` را که فقط به مسیر یک فایل روی ماشین من اشاره می‌کردند حذف کرده‌ام.

## Newtype و constructor اعتبارسنج

از مسئله‌ی کوچک‌تر شروع می‌کنیم. {{< term "newtype" "newtype" >}} یک struct با یک فیلد است. همان داده‌ی type داخلش را نگه می‌دارد، ولی کامپایلر آن را type دیگری می‌بیند:

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

حالا `UserId` و `OrderId` دو type جدایند. `Email` یک قدم جلوتر می‌رود. فیلدش خصوصی است، پس کد بیرون از ماژول نمی‌تواند `Email("whatever".to_string())` بنویسد. تنها راه گرفتن `Email` همان `parse` است و `parse` رشته را بررسی می‌کند. پس هر `Email` در هر جای برنامه از قبل معتبر است و تابعی که یکی را می‌گیرد لازم نیست دوباره بررسی‌اش کند. (بررسی اینجا عمداً ساده است، فقط یک اسباب‌بازی: مقداری متن، یک `@` و یک نقطه در دامنه.)

demo این را چاپ می‌کند:

```text
UserId(7), size 8
Ok("roham@example.com")
Err("invalid email: nope")
```

`parse` آدرس اول را پذیرفت و `nope` را رد کرد. و `size_of::<UserId>()` برابر ۸ است، مثل `u64`: پوشش در زمان اجرا هزینه‌ای ندارد و فقط برای کامپایلر هست. حالا باگ اول، دادن `OrderId` به تابعی که `UserId` می‌خواهد:

```text
error[E0308]: mismatched types
 --> fails/src/bin/newtype.rs:9:30
9 |     println!("{}", load_user(order));
  |                    --------- ^^^^^ expected `UserId`, found `OrderId`
```

## builder و ضعفش

newtype از مقدارها محافظت می‌کند. مسئله‌ی بعدی درباره‌ی *ترتیب فراخوانی* است. یک راه رایج برای ساختن شیئی با تنظیمات اختیاری زیاد **builder** است: متدها را یکی‌یکی صدا می‌زنید و با `build()` تمام می‌کنید. نسخه‌ی کلاسیک هر فیلد را در یک `Option` نگه می‌دارد و در `build()` بررسی می‌کند فیلدهای لازم پر شده باشند:

```rust
pub fn build(self) -> Result<Request, String> {
    let url = self.url.ok_or("url is required")?;
    Ok(Request { url, timeout_ms: self.timeout_ms.unwrap_or(1000) })
}
```

دو بار اجرایش کردم. بدون url، `build()` مقدار `Err("url is required")` برمی‌گرداند. با url ولی بدون timeout، `Ok(Request { url: "http://x", timeout_ms: 1000 })` برمی‌گرداند، یعنی timeout پیش‌فرض. کار می‌کند. ولی فراموش کردن url موقع اجرا پیدا می‌شود. کامپایلر دقیقاً می‌داند کدام متدها را صدا زده‌ایم، پس باید بگذاریم خودش بررسی کند.

## builder از نوع type-state

الگوی {{< term "type-state" "type-state" >}} حالت شیء را در type آن می‌گذارد. برای builder دو حالت داریم: «هنوز url نیست» و «url تنظیم شد». آن‌ها را دو type نشانه‌ی خالی می‌کنیم و به builder یک پارامتر type می‌دهیم که می‌گوید در کدام حالت است. این پارامتر جایی ذخیره نمی‌شود، پس به {{< term "phantom-data" "PhantomData" >}} نیاز داریم؛ فیلدی که برای کامپایلر از پارامتر «استفاده» می‌کند و جایی اشغال نمی‌کند:

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

سه بلوک `impl` را مثل سه قاعده بخوانید:

- `new` و `url` فقط روی `RequestBuilder<NoUrl>` هستند. و `url` یک *type دیگر* برمی‌گرداند، یعنی `RequestBuilder<HasUrl>`. تنظیم url یک قدم از یک حالت به حالت بعد است.
- `timeout_ms` برای هر `S` تعریف شده، پس در هر دو حالت می‌شود صدایش زد.
- `build` فقط روی `RequestBuilder<HasUrl>` هست.

پس کامپایلر حالا «بدون url، `build` نیست» را اجرا می‌کند. فراخوانی `RequestBuilder::new().timeout_ms(50).url("http://x").build()` کامپایل می‌شود و `Request { url: "http://x", timeout_ms: 50 }` چاپ می‌کند. دقت کنید `build` دیگر `Result` برنمی‌گرداند، چون چیزی نمانده که خراب شود. صدا زدن `build` زودتر از موعد:

```text
error[E0599]: no method named `build` found for struct `RequestBuilder<NoUrl>` in the current scope
  = note: the method was found for
          - `RequestBuilder<HasUrl>`
```

کامپایلر حتی می‌گوید متد در کدام حالت وجود دارد.

هر متدی که حالت را عوض می‌کند `self` می‌گیرد، نه `&self`. این همان ownership است که کار می‌کند: `build(self)` builder را مصرف می‌کند، پس استفاده‌ی دوباره از آن خطا می‌دهد:

```text
error[E0382]: use of moved value: `b`
5 |     let first = b.build();
  |                   ------- `b` moved due to this method call
6 |     let second = b.build();
  |                  ^ value used here after move
```

## ماشین حالت

همین ترفند برای یک چرخه‌ی کامل هم کار می‌کند. سفارش از `Draft` و `Paid` و `Shipped` می‌گذرد. برای هرکدام یک type می‌سازیم، یعنی `Order<Draft>` و `Order<Paid>` و `Order<Shipped>`، و هر گذار `self` را می‌گیرد و حالت بعد را برمی‌گرداند. حالت قبلی از بین می‌رود، چون move شده است:

```rust
impl Order<Draft> { pub fn pay(self) -> Order<Paid> { /* ... */ } }
impl Order<Paid>  { pub fn ship(self) -> Order<Shipped> { /* ... */ } }
```

(`Order<Draft>` متدهای `new` و `add` را هم دارد و `Order<Shipped>` متد `tracking` را؛ اینجا نیاوردم.) demo یک سفارش می‌سازد و از هر سه حالت عبورش می‌دهد: `Order::new(OrderId(42)).add("book").add("pen").pay().ship().tracking()` مقدار `TRK-42` چاپ کرد. تلاش برای ارسال یک پیش‌نویس:

```text
error[E0599]: no method named `ship` found for struct `Order<api::Draft>` in the current scope
  = note: the method was found for
          - `Order<api::Paid>`
```

این جواب سؤالی است که با آن شروع کردیم: `ship` روی پیش‌نویس اصلاً وجود ندارد. در زمان اجرا هم هزینه‌ای ندارد. demo اندازه‌ی سه حالت را چاپ می‌کند:

```text
sizes: draft=32 paid=32 shipped=32 PhantomData<Draft>=0
```

نشانه اندازه‌ی صفر دارد، پس سه type دقیقاً یک چیدمان دارند (یک id از نوع `u64` و یک `Vec`، یعنی ۸ + ۲۴ بایت) و «حالت» فقط در بررسی‌کننده‌ی type‌ها وجود دارد.

## وقتی حالت در زمان اجرا معلوم می‌شود

یک مشکل بدیهی هست. وضعیتی که از پایگاه داده می‌خوانید موقع کامپایل معلوم نیست. نمی‌توانید `Order<???>` بنویسید. جواب معمول یک enum است که حالت‌های typeدار را می‌پیچد، و یک `match` تنها در مرزی که مقدار زمان اجرا وارد می‌شود:

```rust
pub enum AnyOrder { Draft(Order<Draft>), Paid(Order<Paid>), Shipped(Order<Shipped>) }
```

demo تابع `AnyOrder::from_db(id, status)` را دارد که از روی یک رشته variant درست را می‌سازد، و `advance()` که هر سفارشی را به حالت بعدش می‌برد. برای وضعیت‌های `draft` و `paid` و `shipped` و یک `oops` ناشناخته چاپ کرد:

```text
draft -> draft -> paid
paid -> paid -> shipped
shipped -> shipped -> shipped
oops -> unknown status
```

هر خط وضعیت است، برچسب سفارشی که از آن ساختیم و برچسب بعد از `advance()`. سفارش ارسال‌شده ارسال‌شده می‌ماند و `oops` همان مرز رد می‌شود. داخل هر شاخه‌ی `match` دوباره در کد کاملاً typeدار هستید.

اما هزینه را صادقانه بگویم. هر محور اضافه‌ی حالت type‌ها را ضرب می‌کند (دو پرچم مستقل همین حالا چهار ترکیب می‌دهند). پیام‌های خطا از type‌های جنریک حرف می‌زنند و خواندنشان سخت‌تر است. و برای تعداد کمی حالت، یک فیلد enum ساده اغلب راحت‌تر است. وقتی type-state بگیرید که ترتیب فراخوانی‌ها قاعده‌ی واقعی دامنه باشد.

## ابزارهای دیگر طراحی API

همین طرز فکر، «بگذار کامپایلر رد کند»، چند ابزار دیگر هم دارد.

**sealed trait** جلوی پیاده‌سازی trait شما توسط کد بیرون از crate را می‌گیرد. trait عمومی را وادار می‌کنید یک supertrait از یک ماژول خصوصی داشته باشد، که کسی بیرون نمی‌تواند اسمش را ببرد:

```rust
mod private { pub trait Sealed {} }
pub trait Currency: private::Sealed { fn code(&self) -> &'static str; }
```

داخل crate، `Usd` و `Eur` هر دو را پیاده می‌کنند. از یک crate دیگر، `impl Currency for Btc` خطا می‌دهد:

```text
error[E0277]: the trait bound `Btc: api::private::Sealed` is not satisfied
  = note: `Currency` is a "sealed trait", because to implement it you also need to implement `api::private::Sealed`, which is not accessible
```

وقتی می‌خواهید بعداً متد به trait اضافه کنید بی‌آنکه کسی را بشکنید، به کار می‌آید.

`#[non_exhaustive]` روی enum یا struct قول می‌دهد که ممکن است در آینده variant یا فیلد اضافه کنید. کد در crate‌های دیگر آن‌وقت باید موقع match یک شاخه‌ی wildcard بگذارد و نمی‌تواند struct را با struct expression بسازد. از یک crate دیگر:

```text
error[E0004]: non-exhaustive patterns: `_` not covered
  = note: `Event` is marked as non-exhaustive, so a wildcard `_` is necessary to match exhaustively
error[E0639]: cannot create non-exhaustive struct using struct expression
```

`#[must_use]` نتیجه‌ی فراموش‌شده را به هشدار تبدیل می‌کند. `with_tax` ما مجموع جدید را برمی‌گرداند و صدا زدنش با نادیده گرفتن نتیجه این هشدار را داد: ‎``warning: unused return value of `with_tax` that must be used``‎ و بعد پیامی که خودمان گذاشتیم: `the new total is returned, the original is unchanged`.

دو عادت کوچک‌تر هم کمک می‌کنند. پارامتر را `impl Into<String>` یا `impl AsRef<str>` بگیرید تا صدازننده بتواند `&str` یا `String` بدهد (`greet("a")` و `greet(String::from("b"))` هر دو کار کردند و `hi a hi b` چاپ شد). و برای struct گزینه‌ها `Default` پیاده کنید و از struct update syntax استفاده کنید: `Options { retries: 5, ..Default::default() }` مقدار `Options { timeout_ms: 1000, retries: 5, verbose: false }` چاپ کرد.

## محدودیت‌های type-state

- **فقط از صدازننده‌هایی محافظت می‌کند که از API دارای type استفاده می‌کنند.** یک فیلد `pub` یا constructor عمومی که از گذارها رد شود آن را دور می‌زند.
- **فیلد نشانه را خصوصی نگه دارید و type‌های نشانه را unit struct ساده.** آن‌وقت کسی نمی‌تواند از هیچ `Order<Paid>` بسازد.
- **گذاری که ممکن است شکست بخورد باید مقدار قبلی را برگرداند.** `pay(self)` پیش‌نویس را مصرف می‌کند. اگر پرداخت می‌تواند شکست بخورد و صدازننده هنوز پیش‌نویس را لازم دارد، `Result<Order<Paid>, Error>` برگردانید که خطا پیش‌نویس را پس بدهد؛ وگرنه گم می‌شود.
- **اضافه کردن `#[non_exhaustive]` به type‌ای که از قبل وجود دارد خودش تغییر شکننده است** برای کد پایین‌دستی که رویش match می‌کند.
- **جایی که یک بررسی زمان اجرا با خطای روشن کافی است، type-state نگیرید.** اگر بیشتر وقت‌ها حالت‌ها از پایگاه داده می‌آیند، شاید type‌های اضافه ارزششان را نداشته باشند.

## مقایسه با Go

Go در عمل type-state ندارد. ابزار معمول constructor‌های `NewX` است که مقدار اجباری را پارامتر می‌کنند، و الگوی functional options (`type Option func(*Server)`) برای مقدارهای اختیاری. مقدار اجباری با قرار گرفتن در امضای constructor تضمین می‌شود، اما صدا زدن متد به ترتیب اشتباه را چیزی نمی‌گیرد. این خطا در زمان اجرا می‌آید.

## تمرین

۱. حالت `Cancelled` را اضافه کنید که فقط از `Draft` قابل رسیدن باشد و بررسی کنید `Order<Shipped>` متد `cancel` ندارد.
۲. برای `Email` پیاده‌سازی `AsRef<str>` بنویسید و آن را به `greet` بدهید.

## قدم بعدی

«Docker، CI و release سرویس Rust»: سرویسی که خوب طراحی شده هنوز باید از لپ‌تاپ بیرون برود.
