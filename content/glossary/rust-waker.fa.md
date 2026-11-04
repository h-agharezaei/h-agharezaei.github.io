+++
title = "Waker (Rust)"
fa_title = "Waker در Rust"
summary = "دسته‌ای داخل `Context` در poll که future با آن به executor خبر می‌دهد حالا می‌تواند پیشرفت کند، تا executor دوباره poll‌اش کند."
category = "Rust"
related = ["rust-future", "rust-executor"]
posts = ["rust-pin-future-internals"]
+++

وقتی future `Pending` برمی‌گرداند باید ترتیبی بدهد که وقتی پیشرفت ممکن شد (مثلاً تایمر تمام شد) `cx.waker().wake()` یا `wake_by_ref()` صدا زده شود. تا آن موقع executor می‌تواند بخوابد. futureای که `Pending` بدهد و بیدارسازی را ترتیب ندهد دیگر هرگز poll نمی‌شود.
