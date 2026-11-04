+++
date = '2026-12-08T10:00:00+03:30'
draft = false
title = 'Module، Crate و Cargo در Rust'
description = 'Module، crate و Cargo در Rust: package و crate، privacy و pub، use و re-export، lib و bin در یک package، feature، dev-dependencies و workspace.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "cargo", "modules", "crates"]
cover = { image = "/images/covers/rust-modules-crates-cargo.fa.png", alt = "Module، Crate و Cargo در Rust", hiddenInSingle = true }
+++

تا اینجای این سری، هر مثال در یک فایل جا می‌شد. اما برنامه‌ی واقعی چند هزار خط می‌شود و اگر همه‌چیز در یک فایل و در یک فضای نام باشد، هم پیدا کردن چیزها سخت می‌شود و هم هر تابع کمکی داخلی ناخواسته در دسترس همه قرار می‌گیرد. Rust برای هر دو مشکل جواب دارد: کد را به **module** و فایل تقسیم می‌کنید و برای هر چیز تعیین می‌کنید از بیرون دیده شود یا نه. جالب اینجاست که پیش‌فرض «دیده نشود» است. اگر تابعی را داخل یک `mod` بنویسید و از بیرون صدایش بزنید، کامپایلر قبول نمی‌کند. بعد از [مدیریت خطا با Result و Option در Rust](/fa/posts/rust-error-handling-result/) که کدمان بزرگ‌تر شد، وقتش است ببینیم این تقسیم‌بندی چطور کار می‌کند.

اول سه واژه‌ای که راحت با هم قاطی می‌شوند. یک مثال کمک می‌کند: فکر کنید یک بسته‌ی پستی دارید.

- {{< term "crate" "crate" >}} یک واحد کامپایل است، یعنی چیزی که کامپایلر یک‌جا می‌سازد: یک کتاب‌خانه (که دیگران استفاده می‌کنند) یا یک برنامه‌ی اجرایی.
- **package** خود بسته است: چیزی که فایل `Cargo.toml` آن را توصیف می‌کند و یک یا چند crate در خود دارد.
- **module** یک فضای نام (namespace) داخل یک crate است، مثل پوشه‌ای که چیزهای مرتبط را کنار هم نگه می‌دارد و تعیین می‌کند کدام‌ها از بیرون دیده شوند.

و ابزاری که همه‌ی این‌ها را می‌سازد و مدیریت می‌کند {{< term "cargo" "Cargo" >}} است، همان که در [اولین مقاله‌ی این سری](/fa/posts/rust-getting-started/) با آن آشنا شدید.

> همه‌ی کدهای زیر را با Rust نسخه‌ی 1.90 (و cargo 1.90.0) اجرا کرده‌ام. خروجی‌ها و پیام‌های کامپایلر از همان اجراها هستند. در جاهایی که مسیر پوشه‌ی پروژه در خروجی بود، آن را با `...` کوتاه کرده‌ام.

## Module در یک فایل و privacy

`mod` یک module تعریف می‌کند و هر چیزی داخلش **به‌طور پیش‌فرض private** است، یعنی فقط از داخل همان module دیده می‌شود. برای نمایان‌کردن یک آیتم باید `pub` (از public) جلوی آن بنویسید. برنامه‌ی زیر یک module به اسم `bank` دارد: یک struct حساب با یک فیلد public و یک فیلد private، و یک تابع کمکی private به اسم `audit`:

```rust
mod bank {
    pub struct Account {
        pub owner: String,
        balance: i64,
    }

    impl Account {
        pub fn new(owner: &str) -> Account {
            Account { owner: owner.to_string(), balance: 0 }
        }
        pub fn deposit(&mut self, n: i64) {
            self.balance += n;
            audit(self.balance);
        }
        pub fn balance(&self) -> i64 {
            self.balance
        }
    }

    fn audit(b: i64) {
        println!("audit: balance is now {b}");
    }
}

use bank::Account;

fn main() {
    let mut a = Account::new("roham");
    a.deposit(50);
    println!("{} has {}", a.owner, a.balance());
}
```

```text
audit: balance is now 50
roham has 50
```

همه‌چیز کار می‌کند. `deposit` داخل module است و می‌تواند `audit` و فیلد `balance` را ببیند. بیرون module فقط به `Account`، `owner`، `new`، `deposit` و `balance()` دسترسی داریم، و اگر بخواهیم موجودی را بخوانیم باید از متد `balance()` بگذریم. به این ترتیب module کنترل می‌کند حساب چطور تغییر کند.

حالا ببینیم اگر از بیرون به چیز private دست بزنیم چه می‌شود. اول یک module کوچک که `audit` در آن private است و `main` آن را مستقیم صدا می‌زند:

```rust
mod bank {
    fn audit(b: i64) {
        println!("audit: {b}");
    }
    pub fn deposit(n: i64) {
        audit(n);
    }
}

fn main() {
    bank::deposit(5);
    bank::audit(5);
}
```

```text
error[E0603]: function `audit` is private
  --> examples/priv_fn.rs:12:11
   |
12 |     bank::audit(5);
   |           ^^^^^ private function
   |
note: the function `audit` is defined here
  --> examples/priv_fn.rs:2:5
   |
 2 |     fn audit(b: i64) {
   |     ^^^^^^^^^^^^^^^^
```

خط `bank::deposit(5)` مشکلی ندارد چون `pub` است. خطا فقط برای `bank::audit(5)` است و کامپایلر هم نشان می‌دهد تابع کجا تعریف شده و چرا private است. privacy فقط مال تابع‌ها نیست و تک‌تک فیلدهای struct را هم شامل می‌شود. اگر از بیرون `a.balance` را بخوانیم:

```text
error[E0616]: field `balance` of struct `Account` is private
  --> examples/priv_field.rs:15:34
   |
15 |     println!("{} {}", a.owner, a.balance);
   |                                  ^^^^^^^ private field
```

(در این برنامه `main` همان `a.owner` و `a.balance` را چاپ می‌کند، `a.owner` درست است چون `pub` است و فقط `a.balance` خطا می‌دهد.) قاعده‌ی کلی این است: یک آیتم داخل module تعریف‌کننده‌اش و module‌های درونِ آن دیده می‌شود، و بیرون از آن فقط اگر `pub` باشد. دو شکل محدودتر هم هست: `pub(crate)` یعنی «در کل این crate دیده شود، نه بیرون از آن» و `pub(super)` یعنی «در module والد دیده شود».

## Module در فایل‌های جدا

نوشتن همه‌ی module‌ها در یک فایل فقط برای مثال خوب است. در پروژه‌ی واقعی هر module در فایل خودش می‌رود. برای این، در فایل والد فقط `mod store;` (با سمیکالن و بدون آکولاد) می‌نویسید و کامپایلر module را از یک فایل می‌خواند: `store.rs` یا `store/mod.rs`. هر دو کار می‌کنند؛ من `store.rs` به‌علاوه‌ی پوشه‌ی `store/` برای module‌های فرزندش را ترجیح می‌دهم. برای نمایش، یک package به اسم `inventory` (یک انبار کوچک) ساختم با این ساختار:

```text
inventory/
├── Cargo.toml
├── Cargo.lock
├── src/
│   ├── lib.rs          # library crate root: pub mod item; mod store; ...
│   ├── main.rs         # binary crate root
│   ├── item.rs         # mod item
│   ├── store.rs        # mod store
│   ├── store/
│   │   └── audit.rs    # mod store::audit
│   └── bin/
│       └── report.rs   # a second binary
├── tests/store.rs
└── examples/
```

`lib.rs` ریشه‌ی crate کتاب‌خانه‌ای و `main.rs` ریشه‌ی crate اجرایی است. این دو در یک package‌اند و هر دو هم‌نام آن. هر فایل داخل `src/bin/` یک برنامه‌ی اجرایی اضافه است. دو نکته در این کد مهم است. اول `item.rs`: فیلدها سه سطح دسترسی مختلف دارند.

```rust
pub struct Item {
    pub name: String,
    qty: u32,
    pub(crate) cents: u64,
}
```

`name` را همه می‌بینند، `qty` فقط داخل module `item` است (و برای بیرون یک متد `qty()` گذاشتم) و `cents` را فقط کدهای داخل همین crate می‌بینند. دوم `store/audit.rs`:

```rust
use super::Store;

pub(super) fn describe(store: &Store) -> String {
    // A child module may touch the private field of its ancestor.
    format!("{} item kinds in stock", store.items.len())
}
```

فیلد `items` در `Store` private است، ولی `audit` یک module فرزند `store` است و فرزند اجازه دارد چیزهای private والد را ببیند، برای همین `store.items` کامپایل می‌شود. خود تابع `describe` هم `pub(super)` است، یعنی فقط `store` آن را می‌بیند و صدا می‌زند.

## مسیرها و use

برای رسیدن به یک آیتم، مسیرش را می‌نویسید. `crate::` از ریشه‌ی crate شروع می‌کند، `self::` از module فعلی و `super::` از module والد. module‌های inline در `lib.rs` هر دو شکل را نشان می‌دهند:

```rust
pub mod price {
    pub fn format(cents: u64) -> String {
        format!("{}.{:02}", cents / 100, cents % 100)
    }

    pub mod tax {
        // Absolute path from the crate root.
        pub fn with_vat(cents: u64) -> String {
            crate::price::format(cents * 120 / 100)
        }

        // Relative path: go up one level, then down.
        pub fn plain(cents: u64) -> String {
            super::format(cents)
        }
    }
}
```

`with_vat` مسیر مطلق می‌نویسد (از ریشه‌ی crate)، و `plain` یک سطح بالا می‌رود (`super`) و `format` را از `price` برمی‌دارد. هر دو یک تابع را صدا می‌زنند.

نوشتن مسیر کامل هر بار خسته‌کننده است، پس `use` یک نام را وارد scope می‌کند. شکل ویژه‌ی آن **`pub use`** است که علاوه بر آن، نام را برای دیگران هم باز می‌کند (re-export). در `lib.rs` عبارت `pub use store::Store;` هست. خودِ `store` یک module خصوصی است، ولی کاربرها می‌توانند `inventory::Store` بنویسند. فایده‌اش این است که ساختار داخلی را بعداً آزادانه می‌توانید عوض کنید و نام عمومی ثابت می‌ماند.

## کتاب‌خانه و برنامه‌ی اجرایی در یک package

`src/main.rs` همان package را مثل یک وابستگی معمولی و با نام package استفاده می‌کند. یعنی برنامه‌ی اجرایی فقط مشتری کتاب‌خانه‌ی خودتان است و فقط چیزهای `pub` را می‌بیند:

```rust
use inventory::item::Item;
use inventory::price::tax;
use inventory::Store;
```

وقتی بیش از یک برنامه‌ی اجرایی در package هست، `cargo run` به‌تنهایی نمی‌داند کدام را اجرا کند. این پیام را می‌دهد: `could not determine which binary to run`، و فهرست `available binaries: inventory, report` را نشان می‌دهد. پس با `--bin` نام را بدهید:

```text
$ cargo run --bin inventory
3 item kinds in stock
order: ["bolt", "nut", "washer"]
total: 30.50 / with VAT: 36.60
$ cargo run --bin report
report: 1 item kinds in stock
```

خروجی اول از `main.rs` است: سه نوع کالا اضافه شده، به همان ترتیبی که اضافه کردیم چاپ شده‌اند، و جمع سه قلم ۲۵۰۰ و ۵۰۰ و ۵۰ سنت یعنی 30.50 است؛ با ۲۰ درصد مالیات 36.60 می‌شود (`with_vat` مبلغ را ۱۲۰/۱۰۰ ضرب می‌کند). خروجی دوم از `src/bin/report.rs` است که برنامه‌ی دوم ماست و فقط یک کالا دارد.

## Cargo.toml: وابستگی و feature

وابستگی‌ها در `Cargo.toml` نوشته می‌شوند. package ما یکی از هر نوع دارد:

```toml
[dependencies]
fastrand = { version = "2.5.0", optional = true }

[dev-dependencies]
pretty_assertions = "1.4.1"

[features]
shuffle = ["dep:fastrand"]
```

`[dev-dependencies]` وابستگی‌هایی است که فقط برای تست، example و benchmark لازم‌اند. `tests/store.rs` از `pretty_assertions` استفاده می‌کند و این وابستگی هیچ‌وقت وارد build معمولی نمی‌شود. (نوشتن `"1.4.1"` یعنی «1.4.1 یا نسخه‌ی سازگار با آن»، طبق قاعده‌ی نسخه‌گذاری Cargo.)

**feature** یک کلید با نام است که در زمان کامپایل روشن یا خاموش می‌شود. اینجا `shuffle` وابستگیِ اختیاریِ `fastrand` را فعال می‌کند. معمولاً برای ویژگی‌ای که همه لازمش ندارند به کار می‌رود، تا کسی که نمی‌خواهدش وابستگی اضافه نیاورد. کد هم با `#[cfg(feature = "shuffle")]` محافظت شده است:

```rust
#[cfg(feature = "shuffle")]
pub fn shuffle(&mut self) { fastrand::shuffle(&mut self.items); }
```

`main.rs` هم با همان `cfg` آن را صدا می‌زند. بدون این فلگ، تابع اصلاً وجود ندارد و `fastrand` حتی در گراف وابستگی‌ها نیست. `cargo tree` همین را نشان می‌دهد:

```text
$ cargo tree
inventory v0.1.0 (.../rust-modules-crates-cargo)
[dev-dependencies]
└── pretty_assertions v1.4.1
    ├── diff v0.1.13
    └── yansi v1.0.1

$ cargo tree --features shuffle
inventory v0.1.0 (.../rust-modules-crates-cargo)
└── fastrand v2.5.0
[dev-dependencies]
└── pretty_assertions v1.4.1
    ├── diff v0.1.13
    └── yansi v1.0.1
$ cargo run --bin inventory --features shuffle
order: ["washer", "nut", "bolt"]
```

در درخت اول فقط `pretty_assertions` (و دو وابستگی خودش) هست و `fastrand` نیست. با `--features shuffle` درخت دوم `fastrand` را هم دارد و برنامه فهرست را به‌هم می‌ریزد. ترتیب تصادفی است و در اجرای شما فرق می‌کند (وقتی من دوباره اجرایش کردم، تصادفاً همان ترتیب اولیه درآمد).

فایل **`Cargo.lock`** نسخه‌ی دقیق و checksum هر وابستگی را ثبت می‌کند. `Cargo.toml` می‌گوید «`fastrand` نسخه‌ی 2.5.0 یا سازگار با آن»، و فایل lock می‌گوید کدام نسخه واقعاً انتخاب شد. برای برنامه‌ها آن را commit کنید تا همه دقیقاً یک چیز بسازند.

## Workspace

وقتی یک مخزن چند package مرتبط دارد، **workspace** یک `Cargo.lock` و یک پوشه‌ی `target/` را بینشان مشترک می‌کند. workspace آزمایشی من دو عضو دارد: یک کتاب‌خانه به اسم `greeter` و یک برنامه‌ی اجرایی به اسم `cli` که به آن وابسته است:

```text
workspace/
├── Cargo.toml      # [workspace] resolver = "3", members = ["greeter", "cli"]
├── Cargo.lock
├── greeter/        # library: pub fn hello(name) -> String
│   ├── Cargo.toml
│   └── src/lib.rs
└── cli/            # binary, depends on greeter = { path = "../greeter" }
    ├── Cargo.toml
    └── src/main.rs
```

(`resolver` تنظیمی است درباره‌ی نحوه‌ی انتخاب نسخه‌ها و featureها؛ من مقداری را که با edition 2024 می‌آید گذاشتم و بیشتر واردش نشدم.)

```text
$ cargo run -p cli
hello, workspace
$ cargo tree
cli v0.1.0 (.../workspace/cli)
└── greeter v0.1.0 (.../workspace/greeter)
```

`-p` یک package عضو را انتخاب می‌کند و با `cargo test -p greeter` هم کار می‌کند. درخت وابستگی هم می‌گوید `cli` به `greeter` وابسته است.

## مقایسه با Go

[مقاله‌ی Go](/fa/posts/go-packages-modules/) همین تقسیم‌بندی را با واژه‌های دیگر گفت. در Go، پکیج یک دایرکتوری است و module واحدی است که `go.mod` توصیف می‌کند. crate در Rust از نظر واحد کامپایل به پکیج Go نزدیک‌تر است، اما module‌ها با `mod` در کد تعریف می‌شوند و فقط به ساختار دایرکتوری وابسته نیستند. Go دیده‌شدن را با حرف بزرگ اول نام مشخص می‌کند و Rust با `pub`، و هر دو نسخه‌ی وابستگی‌ها را در فایلی جدا قفل می‌کنند (`go.sum` و `Cargo.lock`).

## دام‌های ساختار و visibility

- اگر `mod foo;` را در والد ننویسید، فایل `foo.rs` به‌سادگی نادیده گرفته می‌شود. فایل‌ها خودکار پیدا نمی‌شوند و باید module را اعلام کنید.
- `pub` روی struct فیلدهایش را public نمی‌کند. هر فیلد `pub` جدا می‌خواهد، مثل `Account` که `owner` را باز و `balance` را بسته نگه داشت.
- `cargo build` فقط کتاب‌خانه و برنامه‌های اجرایی را کامپایل می‌کند و سراغ `examples/` نمی‌رود، ولی یک فایل خطادار در `src/bin/` کل build را می‌شکند. برای همین دموهای خطادارم را در `examples/` گذاشتم. البته `cargo test` همه‌ی exampleها را هم کامپایل می‌کند: وقتی من `cargo test` زدم، با همان خطاهای `priv_fn` و `priv_field` متوقف شد، و `cargo test --test store` تست را جداگانه اجرا کرد و پاس شد.
- feature باید افزایشی باشد، یعنی روشن‌کردنش فقط چیزی اضافه کند. feature‌ای که رفتار را حذف یا عوض کند، کسانی را که به شما وابسته‌اند غافلگیر می‌کند.

## تمرین

1. یک `pub(crate) fn` به `store.rs` اضافه کنید، از `item.rs` صدایش بزنید و بعد سعی کنید از `main.rs` صدایش بزنید. خطا را بخوانید.
2. module `price` را از `lib.rs` به `src/price.rs` و `src/price/tax.rs` منتقل کنید.
3. یک عضو سوم به workspace اضافه کنید که به `greeter` وابسته باشد و با `cargo run -p` اجرایش کنید.

## قدم بعدی

حالا که کد مرتب و تقسیم شده، سؤال بعدی نوشتن کدی است که برای نوع‌های مختلف کار کند، بدون اینکه برای هر نوع از نو نوشته شود. برای همین قدم بعدی «Generics و Trait در Rust» است.
