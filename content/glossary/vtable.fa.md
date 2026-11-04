+++
title = "vtable"
fa_title = "vtable در Rust"
summary = "جدول کوچکی از آدرس متدها که اشاره‌گر `dyn Trait` با آن در زمان اجرا تابع درست را پیدا می‌کند."
category = "Rust"
related = ["trait-object", "trait"]
posts = ["rust-trait-objects-dyn"]
+++

برای هر نوع مشخصی که به شکل `dyn Trait` به کار می‌رود، کامپایلر جدولی از آدرس متدهای آن نوع می‌سازد. `&dyn Trait` یک fat pointer دو کلمه‌ای است: یکی به داده اشاره می‌کند و دیگری به این جدول، پس صدا زدن متد یعنی پیدا کردن آدرسش در جدول.
