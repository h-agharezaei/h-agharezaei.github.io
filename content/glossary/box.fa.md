+++
title = "Box"
fa_title = "Box"
summary = "smart pointer با یک مالک که مقدارش را در heap نگه می‌دارد و روی stack فقط یک اشاره‌گر دارد."
category = "Rust"
related = ["smart-pointer", "heap-memory", "stack-memory"]
posts = ["rust-smart-pointers"]
+++

`Box<T>` مقدار را به heap می‌برد و یک اشاره‌گر با اندازه‌ی ثابت به شما می‌دهد. برای نوع‌های بازگشتی (نوعی که خودش را در خود دارد) و برای `Box<dyn Trait>` لازم است، یعنی وقتی مقدارهایی از نوع‌های مختلف پشت یک trait نگه داشته می‌شوند. وقتی box از scope بیرون برود، مقدار داخل heap آزاد می‌شود.
