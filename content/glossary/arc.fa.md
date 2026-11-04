+++
title = "Arc"
fa_title = "Arc"
summary = "نسخه‌ی thread-safe از Rc: اشاره‌گر شمارنده‌دار که شمارنده‌اش به‌صورت atomic به‌روز می‌شود."
category = "Rust"
related = ["rc", "rust-mutex", "send-and-sync"]
posts = ["rust-concurrency-threads"]
+++

`Arc<T>` اجازه می‌دهد چند thread مالک یک مقدار باشند؛ `Arc::clone` یکی به یک شمارنده‌ی atomic اضافه می‌کند. فقط دسترسی مشترک می‌دهد، پس برای تغییر یک `Mutex` داخلش می‌گذارید: `Arc<Mutex<T>>`.
