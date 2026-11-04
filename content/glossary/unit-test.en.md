+++
title = "Unit test (Rust)"
summary = "A small test that lives in the same file as the code it checks, in a module marked #[cfg(test)]."
category = "Rust"
related = ["doc-test", "rust-integration-test", "cargo"]
posts = ["rust-testing-docs"]
+++

In Rust, unit tests sit next to the code in a child module marked `#[cfg(test)]`, which is compiled only for `cargo test`. Because the module is a child, `use super::*` gives it access to private items. A test is a function marked `#[test]` that fails when it panics.
