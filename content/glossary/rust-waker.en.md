+++
title = "Waker (Rust)"
summary = "A handle inside the poll `Context` that a future uses to tell the executor it can make progress now, so the executor polls it again."
category = "Rust"
related = ["rust-future", "rust-executor"]
posts = ["rust-pin-future-internals"]
+++

When a future returns `Pending`, it must arrange for `cx.waker().wake()` (or `wake_by_ref()`) to be called when progress is possible, for example when a timer fires. Until then the executor is free to sleep. A future that returns `Pending` without arranging a wake-up is never polled again.
