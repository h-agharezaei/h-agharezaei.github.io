+++
title = "Thread (Rust)"
summary = "An operating-system thread started with std::thread::spawn; it runs a closure alongside the main thread and shares the program's memory."
category = "Rust"
related = ["data-race", "send-and-sync", "rust-closure"]
posts = ["rust-concurrency-threads"]
+++

`thread::spawn` starts a new OS thread and returns a `JoinHandle`. The thread may outlive the function that started it, so its closure must own what it uses (`move`). `join()` waits for it and returns `Ok(value)` or `Err` if the thread panicked.
