+++
title = "FFI (Rust)"
summary = "Calling code written in another language (usually C) from Rust, or exposing Rust functions to it, through the C ABI."
category = "Rust"
related = ["raw-pointer", "undefined-behavior"]
posts = ["rust-unsafe-ffi"]
+++

Foreign functions are declared in an `unsafe extern "C"` block and calling them needs `unsafe`. To expose Rust code you use `extern "C"`, `#[unsafe(no_mangle)]` and `#[repr(C)]` types, and you must keep ownership rules in mind: memory is freed by the allocator that created it.
