+++
title = "Borrow checker"
fa_title = "borrow checker"
summary = "بخشی از کامپایلر Rust که reference‌ها را با قانون‌های borrowing می‌سنجد."
category = "Rust"
related = ["borrowing", "ownership", "lifetime"]
posts = ["rust-borrowing-references"]
+++

در زمان کامپایل بررسی می‌کند که هیچ‌وقت یک reference تغییرپذیر هم‌زمان با reference دیگری به همان مقدار نداشته باشید و هیچ reference‌ای بیشتر از مقدارش عمر نکند. تخلف‌ها خطای کامپایل می‌شوند (مثل E0499، E0502 و E0515)، پس این باگ‌ها به زمان اجرا نمی‌رسند.
