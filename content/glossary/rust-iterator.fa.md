+++
title = "Iterator (Rust)"
fa_title = "iterator در Rust"
summary = "مقداری با متد next که عنصرها را یکی‌یکی تحویل می‌دهد تا وقتی None برگرداند."
category = "Rust"
related = ["rust-closure", "trait"]
posts = ["rust-closures-iterators"]
+++

هر چیزی که trait به اسم `Iterator` را پیاده‌سازی کرده باشد: تنها متد لازمش `next` است که تا تمام‌شدن عنصرها `Some(item)` و بعد `None` برمی‌گرداند. adapterهایی مثل `map` و `filter` یک iterator را در iterator دیگری می‌پیچند و تا وقتی یک consumer مثل `collect` یا `sum` عنصرها را نکشد، کاری نمی‌کنند.
