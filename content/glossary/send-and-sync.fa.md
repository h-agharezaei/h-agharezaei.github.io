+++
title = "Send and Sync"
fa_title = "Send و Sync"
summary = "trait‌های نشانه: Send یعنی نوع را می‌شود به thread دیگر منتقل کرد، Sync یعنی می‌شود با reference بین thread‌ها به اشتراک گذاشت."
category = "Rust"
related = ["data-race", "arc", "rust-mutex"]
posts = ["rust-concurrency-threads"]
+++

`thread::spawn` از closure خود می‌خواهد `Send` باشد. کامپایلر `Send` و `Sync` را خودکار از روی فیلدهای نوع نتیجه می‌گیرد؛ `Rc` هیچ‌کدام نیست چون شمارنده‌اش atomic نیست، و برای همین استفاده‌اش بین thread‌ها خطای کامپایل است. `Arc<Mutex<T>>` هر دو را دارد.
