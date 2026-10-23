+++
date = '2026-12-08T10:00:00+03:30'
draft = false
title = 'Module، Crate و Cargo در Rust'
description = 'Module، crate و Cargo در Rust: package و crate، privacy و pub، use و re-export، lib و bin در یک package، feature، dev-dependencies و workspace.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "cargo", "modules", "crates"]
cover = { image = "/images/covers/rust-modules-crates-cargo.fa.png", alt = "Module، Crate و Cargo در Rust", hiddenInSingle = true, hiddenInList = true }
+++

بعد از [مدیریت خطا با Result و Option](/fa/posts/rust-error-handling-result/)، هنوز همه‌ی مثال‌هایمان در یک فایل جا می‌شوند. این مقاله درباره‌ی تقسیم کد بین فایل‌ها و درباره‌ی Cargo است، ابزاری که پروژه را می‌سازد و مدیریت می‌کند. سه واژه راحت با هم قاطی می‌شوند، پس اول تعریف‌ها: **crate** یک واحد کامپایل است (کتاب‌خانه یا برنامه‌ی اجرایی)، **package** چیزی است که `Cargo.toml` توصیف می‌کند و یک یا چند crate در خود دارد، و **module** یک فضای نام داخل یک crate است.

> همه‌ی کدهای زیر با Rust نسخه‌ی 1.90 (و cargo 1.90.0) اجرا شده‌اند. خروجی‌ها و پیام‌های کامپایلر از همان اجراها کپی شده‌اند.

## Module در یک فایل و privacy

`mod` یک module تعریف می‌کند و هر چیزی داخلش **به‌طور پیش‌فرض private** است. برای نمایان کردن یک آیتم `pub` اضافه کنید:

```rust
mod bank {
    pub struct Account {
        pub owner: String,
        balance: i64,
    }
    impl Account {
        pub fn new(owner: &str) -> Account { /* sets balance to 0 */ }
        pub fn balance(&self) -> i64 { self.balance }
    }
    fn audit(b: i64) { /* private helper */ }
}
```

privacy هم برای تابع‌ها صدق می‌کند و هم برای تک‌تک فیلدهای struct. صدا زدن `bank::audit(5)` از بیرون این خطا را می‌دهد:

```text
error[E0603]: function `audit` is private
  --> examples/priv_fn.rs:12:11
   |
12 |     bank::audit(5);
   |           ^^^^^ private function
```

و خواندن `a.balance` از بیرون این را:

```text
error[E0616]: field `balance` of struct `Account` is private
  --> examples/priv_field.rs:15:34
   |
15 |     println!("{} {}", a.owner, a.balance);
   |                                  ^^^^^^^ private field
```

قاعده این است: یک آیتم داخل module تعریف‌کننده‌اش و زیرمجموعه‌های آن دیده می‌شود، و بیرون از آن فقط اگر `pub` باشد. `pub(crate)` یعنی «در کل این crate دیده شود» و `pub(super)` یعنی «در module والد دیده شود».

## Module در فایل‌های جدا

عبارت `mod store;` (با سمیکالن) به کامپایلر می‌گوید module را از یک فایل بخواند: `store.rs` یا `store/mod.rs`. هر دو کار می‌کنند؛ من `store.rs` به‌علاوه‌ی پوشه‌ی `store/` برای فرزندانش را ترجیح می‌دهم. package‌ای که ساختم `inventory` نام دارد:

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

`lib.rs` ریشه‌ی crate کتاب‌خانه‌ای و `main.rs` ریشه‌ی crate اجرایی است. این دو در یک package‌اند و هر دو هم‌نام آن. هر فایل داخل `src/bin/` یک برنامه‌ی اجرایی اضافه می‌شود.

## مسیرها و use

داخل یک crate می‌شود آیتم را با مسیر صدا زد: `crate::` از ریشه‌ی crate شروع می‌کند، `self::` از module فعلی و `super::` از والد. module‌های inline در `lib.rs` هر سه را نشان می‌دهند:

```rust
pub mod price {
    pub fn format(cents: u64) -> String { format!("{}.{:02}", cents / 100, cents % 100) }

    pub mod tax {
        pub fn with_vat(cents: u64) -> String { crate::price::format(cents * 120 / 100) }
        pub fn plain(cents: u64) -> String { super::format(cents) }
    }
}
```

`use` یک نام را وارد scope می‌کند تا مسیر را تکرار نکنید. **`pub use`** آن را re-export هم می‌کند: در `lib.rs` عبارت `pub use store::Store;` هست، پس کاربرها `inventory::Store` می‌نویسند، با اینکه خودِ `store` یک module خصوصی است. با این روش ساختار داخلی را می‌توانید آزادانه عوض کنید.

## کتاب‌خانه و برنامه‌ی اجرایی در یک package

`src/main.rs` همان package خودش را مثل یک وابستگی معمولی و با نام package استفاده می‌کند:

```rust
use inventory::item::Item;
use inventory::price::tax;
use inventory::Store;
```

وقتی بیش از یک برنامه‌ی اجرایی دارید، `cargo run` خالی خطا می‌دهد (`could not determine which binary to run`)، پس نامش را بدهید:

```text
$ cargo run --bin inventory
3 item kinds in stock
order: ["bolt", "nut", "washer"]
total: 30.50 / with VAT: 36.60
$ cargo run --bin report
report: 1 item kinds in stock
```

## Cargo.toml: وابستگی و feature

```toml
[dependencies]
fastrand = { version = "2.5.0", optional = true }

[dev-dependencies]
pretty_assertions = "1.4.1"

[features]
shuffle = ["dep:fastrand"]
```

`[dev-dependencies]` فقط برای تست، example و benchmark استفاده می‌شود؛ `tests/store.rs` از `pretty_assertions` استفاده می‌کند و این وابستگی هیچ‌وقت وارد build معمولی نمی‌شود. **feature** یک کلید با نام است که در زمان کامپایل روشن یا خاموش می‌شود. اینجا `shuffle` وابستگی اختیاریِ `fastrand` را فعال می‌کند و کد با `#[cfg(feature = "shuffle")]` محافظت شده است:

```rust
#[cfg(feature = "shuffle")]
pub fn shuffle(&mut self) { fastrand::shuffle(&mut self.items); }
```

`main.rs` هم با همان `cfg` آن را صدا می‌زند. بدون این فلگ تابع اصلاً وجود ندارد و `fastrand` حتی در گراف وابستگی‌ها نیست:

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
    ...
$ cargo run --bin inventory --features shuffle
order: ["washer", "nut", "bolt"]
```

ترتیب تصادفی است و در اجرای شما فرق می‌کند. فایل **`Cargo.lock`** نسخه‌ی دقیق و checksum هر وابستگی را ثبت می‌کند. برای برنامه‌ها آن را commit کنید تا همه دقیقاً یک چیز بسازند؛ `Cargo.toml` می‌گوید «2.5.0 یا سازگار با آن» و فایل lock می‌گوید کدام نسخه انتخاب شد.

## Workspace

وقتی یک مخزن چند package مرتبط دارد، **workspace** یک `Cargo.lock` و یک پوشه‌ی `target/` را بینشان مشترک می‌کند. workspace آزمایشی من:

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

```text
$ cargo run -p cli
hello, workspace
$ cargo tree
cli v0.1.0 (.../workspace/cli)
└── greeter v0.1.0 (.../workspace/greeter)
```

`-p` یک package عضو را انتخاب می‌کند و با `cargo test -p greeter` هم کار می‌کند.

## مقایسه با Go

[مقاله‌ی Go](/fa/posts/go-packages-modules/) همین تقسیم‌بندی را با واژه‌های دیگر گفت: پکیج در Go یک دایرکتوری است و module در Go واحدی است که `go.mod` توصیف می‌کند. crate در Rust از نظر واحد کامپایل به پکیج Go نزدیک‌تر است، اما module‌ها با `mod` در کد تعریف می‌شوند و فقط به دایرکتوری وابسته نیستند. Go دیده شدن را با حرف بزرگ مشخص می‌کند و Rust با `pub`، و هر دو نسخه‌ی وابستگی‌ها را در فایلی جدا قفل می‌کنند (`go.sum` و `Cargo.lock`).

## چند نکته‌ی احتیاط

- اگر `mod foo;` را در والد ننویسید، فایل جدید به‌سادگی نادیده گرفته می‌شود؛ خودکار پیدا نمی‌شود.
- `pub` روی struct فیلدهایش را public نمی‌کند. هر فیلد `pub` جدا می‌خواهد.
- `cargo build` همه‌ی targetهای `src/` را کامپایل می‌کند، پس فایلی در `src/bin/` که خطای کامپایل دارد کل build را می‌شکند. برای همین دموهای خطادارم را در `examples/` گذاشتم.
- feature باید افزایشی باشد. feature‌ای که رفتار را حذف یا عوض کند، کسانی را که به شما وابسته‌اند غافلگیر می‌کند.

## تمرین

1. یک `pub(crate) fn` به `store.rs` اضافه کنید، از `item.rs` صدایش بزنید و بعد سعی کنید از `main.rs` صدایش بزنید. خطا را بخوانید.
2. module `price` را از `lib.rs` به `src/price.rs` و `src/price/tax.rs` منتقل کنید.
3. یک عضو سوم به workspace اضافه کنید که به `greeter` وابسته باشد و با `cargo run -p` اجرایش کنید.

## قدم بعدی

در مقاله‌ی بعد سراغ generic و trait در Rust می‌رویم: نوشتن کدی که برای نوع‌های مختلف کار کند و اینکه Rust رفتار مشترک را چطور توصیف می‌کند.
