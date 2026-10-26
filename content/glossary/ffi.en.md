+++
title = "FFI"
summary = "Foreign Function Interface: calling code written in another language, usually through the C ABI."
category = "Go"
related = ["grpc"]
posts = ["go-calls-rust-ffi", "rust-unsafe-ffi"]
+++

Go reaches Rust through cgo and a C-compatible boundary; Rust exposes `extern "C"` functions with `#[no_mangle]`. Crossing the boundary costs time and requires care with memory: whoever allocates a buffer must be the one to free it.
