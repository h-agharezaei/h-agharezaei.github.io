+++
title = "Ownership"
summary = "قاعده‌ی Rust که هر مقدار دقیقاً یک مالک دارد و با خارج شدن مالک از scope آزاد می‌شود."
category = "Rust"
fa_title = "مالکیت"
related = ["borrowing", "lifetime"]
posts = ["rust-ownership"]
+++

انتساب یا پاس دادن مقداری که `Copy` نیست آن را *move* می‌کند و متغیر قبلی دیگر قابل استفاده نیست. به این ترتیب Rust بدون garbage collector حافظه را قطعی آزاد می‌کند و double free در زمان کامپایل رد می‌شود. برای استفاده بدون گرفتن مالکیت، از [borrowing](/fa/glossary/borrowing/) استفاده کنید.

```rust
let a = String::from("hi");
let b = a; // a is moved
// println!("{a}"); // compile error
```
