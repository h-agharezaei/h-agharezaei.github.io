+++
title = "Doc test"
summary = "A code example inside a documentation comment that Rust compiles and runs as a test."
category = "Rust"
related = ["unit-test", "cargo"]
posts = ["rust-testing-docs"]
+++

Every code block inside a `///` or `//!` comment is compiled and run by `cargo test`. If the code no longer compiles or an assertion in it fails, the test fails. This keeps the examples in your documentation from going stale.
