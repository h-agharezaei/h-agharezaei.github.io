+++
title = "Pin (Rust)"
fa_title = "Pin در Rust"
summary = "پوششی مثل `Pin<&mut T>` که قول می‌دهد مقدار تا وقتی drop نشده در حافظه جابه‌جا نمی‌شود؛ futureهای self-referential به آن نیاز دارند."
category = "Rust"
related = ["rust-future", "rust-waker"]
posts = ["rust-pin-future-internals"]
+++

بلوک `async` ممکن است reference به یکی از متغیرهای محلی خودش داشته باشد، پس جابه‌جایش اشاره‌گر معلق به جا می‌گذارد. به همین دلیل `poll` یک `Pin<&mut Self>` می‌گیرد. بیشتر نوع‌ها `Unpin` هستند (پین کردن برایشان تغییری نمی‌دهد)؛ بلوک‌های async نیستند و آن‌ها را با `Box::pin` یا `std::pin::pin!` پین می‌کنید.
