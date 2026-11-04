+++
title = "Executor (Rust)"
summary = "The part of a runtime that polls futures, and sleeps until a waker says one of them can make progress."
category = "Rust"
related = ["rust-waker", "rust-future", "tokio"]
posts = ["rust-pin-future-internals"]
+++

The standard library defines `Future` and `Waker` but has no executor, so a crate such as Tokio provides one. The simplest executor is a loop: poll the future, and if it returned `Pending`, park the thread until the waker unparks it.
