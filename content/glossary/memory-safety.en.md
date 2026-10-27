+++
title = "Memory safety"
summary = "A language or tool guarantee that a program cannot read or write memory it does not own."
category = "Security"
related = ["buffer-overflow", "use-after-free", "ownership"]
posts = ["sec-memory-safety-c-vs-rust", "sec-fuzzing"]
+++

Memory-safe code cannot index past an array, use freed memory or free it twice. Rust enforces this at compile time in safe code, Go and most managed languages with runtime checks and a garbage collector. C leaves it to the programmer. See [buffer overflow](/glossary/buffer-overflow/) and [use-after-free](/glossary/use-after-free/).
