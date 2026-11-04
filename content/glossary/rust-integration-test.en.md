+++
title = "Integration test (Rust)"
summary = "A test in the tests/ directory that uses your library only through its public API, like an outside user."
category = "Rust"
related = ["unit-test", "crate", "doc-test"]
posts = ["rust-testing-docs"]
+++

Each file in `tests/` is compiled as a separate crate that depends on your library, so it can call only public items. It works only for a library crate (one with a `lib.rs`), and each file becomes its own test program.
