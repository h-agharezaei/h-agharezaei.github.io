+++
title = "Use-after-free"
summary = "Using a pointer after the memory it points to has been freed."
category = "Security"
related = ["memory-safety", "buffer-overflow", "ownership"]
posts = ["sec-memory-safety-c-vs-rust"]
+++

After `free(p)` the pointer still holds the old address, and reading it may even appear to work. In Rust the [ownership](/glossary/ownership/) and borrow rules turn the same mistake into a compile error.
