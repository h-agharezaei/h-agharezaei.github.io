+++
title = "WASI"
summary = "The WebAssembly System Interface: a standard set of calls (files, arguments, stdin, clock) that a wasm host grants to a module explicitly."
category = "Rust"
related = ["webassembly"]
posts = ["rust-wasm"]
+++

A plain wasm module has no way to read a file or print a line. WASI defines those calls in a standard way, and the host decides what to hand over: a directory is visible to the module only if the host maps it in (a "preopen"). A normal Rust command-line program can be built for `wasm32-wasip1` with no code change and run under a runtime that supports WASI, such as `node:wasi` in Node.
