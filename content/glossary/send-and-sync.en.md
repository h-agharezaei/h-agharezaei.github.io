+++
title = "Send and Sync"
summary = "Marker traits: Send means a type may be moved to another thread, Sync means it may be shared between threads by reference."
category = "Rust"
related = ["data-race", "arc", "rust-mutex"]
posts = ["rust-concurrency-threads"]
+++

`thread::spawn` requires its closure to be `Send`. The compiler works out `Send` and `Sync` automatically from a type's fields; `Rc` is neither because its counter is not atomic, which is why using it across threads is a compile error. `Arc<Mutex<T>>` is both.
