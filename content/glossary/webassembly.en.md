+++
title = "WebAssembly"
summary = "A portable binary instruction format that runs in a sandboxed virtual machine, in browsers and in standalone runtimes; Rust compiles to it with a wasm32 target."
category = "Rust"
related = ["wasi", "wasm-bindgen", "rust-ffi"]
posts = ["rust-wasm"]
+++

A WebAssembly (wasm) module is a compiled file that a host program loads and runs. It cannot reach the outside world by itself: it has only its own linear memory and the functions the host chooses to import into it. You build Rust for it by adding a target such as `wasm32-unknown-unknown` (no system interface) or `wasm32-wasip1` (with WASI), then running `cargo build --target ...`.
