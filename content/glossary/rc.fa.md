+++
title = "Rc"
fa_title = "Rc"
summary = "smart pointer شمارنده‌دار که چند مالک را در یک مقدار شریک می‌کند؛ مقدار وقتی آخرین مالک برود آزاد می‌شود."
category = "Rust"
related = ["smart-pointer", "refcell", "ownership"]
posts = ["rust-smart-pointers"]
+++

`Rc<T>` یک شمارنده نگه می‌دارد که می‌گوید مقدار چند مالک دارد. `Rc::clone` فقط یکی به شمارنده اضافه می‌کند و داده را کپی نمی‌کند. فقط دسترسی خواندنی می‌دهد و فرستادنش به thread دیگر مجاز نیست (آنجا `Arc` را به کار ببرید).
