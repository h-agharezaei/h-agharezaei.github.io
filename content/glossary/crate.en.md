+++
title = "Crate"
summary = "Rust's unit of compilation: one library or one executable, built from a root file."
category = "Rust"
related = ["cargo"]
posts = ["rust-modules-crates-cargo"]
+++

A crate is what the Rust compiler builds in one go. A library crate has `lib.rs` as its root and an executable crate has `main.rs`. One Cargo package can hold a library crate and several executable crates, and modules (`mod`) organise the code inside a crate.
