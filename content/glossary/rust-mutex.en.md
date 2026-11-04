+++
title = "Mutex (Rust)"
summary = "A lock that owns the data it protects; lock() returns a guard that unlocks when it goes out of scope."
category = "Rust"
related = ["arc", "data-race", "interior-mutability"]
posts = ["rust-concurrency-threads"]
+++

In Rust the data lives inside the mutex (`Mutex<T>`), so you cannot reach it without locking. `lock()` returns a guard; the lock is released when the guard is dropped. If a thread panics while holding the lock the mutex becomes poisoned and `lock()` returns an `Err`.
