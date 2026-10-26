+++
title = "Lifetime"
summary = "یک annotation زمان کامپایل که مشخص می‌کند یک reference تا کی معتبر است."
category = "Rust"
fa_title = "طول عمر"
related = ["ownership", "borrowing"]
posts = ["rust-lifetimes"]
+++

lifetimeهایی مثل `'a` هیچ‌وقت طول عمر داده را تغییر نمی‌دهند؛ فقط به کامپایلر اجازه می‌دهند بررسی کند reference از چیزی که به آن اشاره می‌کند بیشتر زنده نمی‌ماند. بیشترشان خودکار استنتاج می‌شوند (elision) و وقتی تابع referenceای برمی‌گرداند که به یکی از چند ورودی وابسته است، باید صریح بنویسید.

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```
