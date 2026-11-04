+++
title = "Heap (memory)"
fa_title = "heap (حافظه)"
summary = "بخش حافظه برای داده‌ای که اندازه‌اش پویاست یا در زمان کامپایل معلوم نیست."
category = "Rust"
related = ["stack-memory", "ownership", "garbage-collector"]
posts = ["rust-ownership"]
+++

از سیستم فضا می‌گیرید، آدرس آن را پس می‌گیرید و بعداً باید آزادش کنید. در Rust مالک مقدار هنگام خروج از scope آن را آزاد می‌کند و در Go garbage collector این کار را می‌کند. با ساختمان داده‌ی heap برای صف اولویت اشتباه نشود.
