+++
title = "Data race"
summary = "Two threads touching the same memory at the same time, at least one of them writing, without synchronization."
category = "Rust"
related = ["send-and-sync", "rust-mutex", "os-thread"]
posts = ["rust-concurrency-threads"]
+++

Example: two threads each do `counter += 1`. Each reads the old value, adds one and writes it back; if both read the same old value, one increment is lost. Safe Rust rules data races out at compile time through ownership and the `Send` and `Sync` traits.
