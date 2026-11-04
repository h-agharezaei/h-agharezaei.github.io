+++
title = "Procedural macro"
summary = "A macro written as a Rust function that takes tokens and returns tokens; it lives in its own crate with `proc-macro = true`."
category = "Rust"
related = ["macro-rules"]
posts = ["rust-macros"]
+++

There are three kinds: derive macros (`#[derive(Describe)]`), attribute-like macros (`#[route(...)]`) and function-like macros (`sql!(...)`). The code usually uses the `syn` crate to read the input and the `quote` crate to write the output. It can inspect the fields of a struct, which `macro_rules!` cannot.
