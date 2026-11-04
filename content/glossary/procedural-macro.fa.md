+++
title = "Procedural macro"
fa_title = "ماکروی procedural"
summary = "ماکرویی که به شکل یک تابع Rust نوشته می‌شود، توکن می‌گیرد و توکن برمی‌گرداند و در crate جدایی با `proc-macro = true` قرار دارد."
category = "Rust"
related = ["macro-rules"]
posts = ["rust-macros"]
+++

سه نوع دارد: derive (`#[derive(Describe)]`)، attribute-like (`#[route(...)]`) و function-like (`sql!(...)`). کد معمولاً با crate به نام `syn` ورودی را می‌خواند و با crate به نام `quote` خروجی را می‌نویسد. می‌تواند فیلدهای یک struct را بررسی کند، که `macro_rules!` نمی‌تواند.
