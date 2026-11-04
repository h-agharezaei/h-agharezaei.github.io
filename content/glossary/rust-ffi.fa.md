+++
title = "FFI (Rust)"
fa_title = "FFI در Rust"
summary = "صدا زدن کدی که به زبان دیگری (معمولاً C) نوشته شده از Rust، یا در دسترس گذاشتن تابع‌های Rust برای آن، از طریق C ABI."
category = "Rust"
related = ["raw-pointer", "undefined-behavior"]
posts = ["rust-unsafe-ffi"]
+++

تابع‌های خارجی در بلوک `unsafe extern "C"` تعریف می‌شوند و صدا زدنشان `unsafe` می‌خواهد. برای در دسترس گذاشتن کد Rust از `extern "C"`، `#[unsafe(no_mangle)]` و نوع‌های `#[repr(C)]` استفاده می‌کنید و باید قانون مالکیت را به خاطر داشته باشید: حافظه را همان allocator آزاد می‌کند که ساخته.
