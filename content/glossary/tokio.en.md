+++
title = "Tokio"
summary = "The most widely used async runtime crate for Rust: it runs futures, and provides timers, channels, locks and I/O."
category = "Rust"
related = ["rust-future", "rust-async-await", "crate"]
posts = ["rust-async-tokio"]
+++

Tokio supplies the executor that polls futures, plus `tokio::spawn`, `join!`, `select!`, `time::sleep`, `sync::mpsc` and an async `Mutex`. `#[tokio::main]` sets a runtime up around `main`. It is a normal crate from crates.io, not part of the standard library.
