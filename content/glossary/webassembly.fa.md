+++
title = "WebAssembly"
fa_title = "WebAssembly"
summary = "قالب دودویی قابل‌حمل برای دستورها که در یک ماشین مجازی ایزوله اجرا می‌شود، در مرورگر و در runtimeهای مستقل؛ Rust با targetهای wasm32 به آن کامپایل می‌شود."
category = "Rust"
related = ["wasi", "wasm-bindgen", "rust-ffi"]
posts = ["rust-wasm"]
+++

ماژول WebAssembly (به‌اختصار wasm) فایل کامپایل‌شده‌ای است که یک برنامه‌ی میزبان بارگذاری و اجرایش می‌کند. خودش به دنیای بیرون دسترسی ندارد: فقط linear memory خودش را دارد و تابع‌هایی که میزبان انتخاب کند داخلش import کند. برای ساختن Rust برای آن، targetای مثل `wasm32-unknown-unknown` (بدون رابط سیستم) یا `wasm32-wasip1` (با WASI) اضافه می‌کنید و `cargo build --target ...` را اجرا می‌کنید.
