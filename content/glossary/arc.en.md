+++
title = "Arc"
summary = "The thread-safe version of Rc: a reference-counted pointer whose counter is updated atomically."
category = "Rust"
related = ["rc", "rust-mutex", "send-and-sync"]
posts = ["rust-concurrency-threads"]
+++

`Arc<T>` lets several threads own one value; `Arc::clone` adds one to an atomic counter. It gives only shared access, so for changes you put a `Mutex` inside: `Arc<Mutex<T>>`.
