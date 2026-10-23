+++
date = '2027-03-14T10:00:00+03:30'
draft = false
title = 'Rust and WebAssembly'
description = 'Rust and WebAssembly: compile to wasm32-unknown-unknown and wasm32-wasip1, pass strings across the boundary and use wasm-bindgen.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "wasm", "webassembly", "wasi", "wasm-bindgen", "intermediate"]
cover = { image = "/images/covers/rust-wasm.png", alt = "Rust and WebAssembly", hiddenInSingle = true, hiddenInList = true }
+++

[Release engineering](/posts/rust-docker-ci-release/) was the previous topic. This post is about a different kind of artifact: a `.wasm` file. In [the unsafe and FFI post](/posts/rust-unsafe-ffi/) we crossed a boundary with the C ABI, and Go did the same in [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/). WebAssembly is another way to cross a boundary, with a sandbox in the middle.

**WebAssembly** (wasm) is a portable binary instruction format that runs on a sandboxed virtual machine. A wasm module cannot touch the DOM, files or the network by itself; it only has its own **linear memory** and whatever functions the host (a browser, Node, a runtime) chooses to give it. Only numbers cross the boundary.

> Everything here was built and run with Rust 1.90, edition 2024, Node 20.13 and `wasm-bindgen` 0.2.129 on macOS. There was no browser available, so everything was loaded from Node and I make no claims about browsers. The demos are local crates: `raw`, `bindgen`, `wasi`, `gohello`.

## The minimal path: numbers only

Set up the targets once: `rustup target add wasm32-unknown-unknown wasm32-wasip1`. The crate type is `cdylib`, and the functions look exactly like the C ABI ones from the FFI post:

```rust
#[unsafe(no_mangle)]
pub extern "C" fn add(a: i32, b: i32) -> i32 { a + b }

#[unsafe(no_mangle)]
pub extern "C" fn fib(n: u32) -> u64 {
    let (mut a, mut b) = (0u64, 1u64);
    for _ in 0..n { (a, b) = (b, a + b); }
    a
}
```

I also added a profile `small` (`opt-level = "z"`, `lto = true`, `strip = true`, `codegen-units = 1`) and built the crate twice with `cargo build --release --target wasm32-unknown-unknown` and `--profile small`:

```text
-rwxr-xr-x  1 hossein  staff  24161 raw.wasm   (release)
-rwxr-xr-x  1 hossein  staff  10334 raw.wasm   (small)
```

The size numbers include the string helpers shown below.

## Strings need linear memory

A string is not a number, so the host must put its bytes into the module's memory and pass a pointer and a length. The module exports `alloc` and `dealloc` for that (a `Layout` with alignment 1) and a function that reads the bytes back:

```rust
#[unsafe(no_mangle)]
pub unsafe extern "C" fn count_chars(ptr: *const u8, len: usize) -> usize {
    let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
    std::str::from_utf8(bytes).map(|s| s.chars().count()).unwrap_or(0)
}
```

Here is the JavaScript side, run with `node js/run.mjs <file>`:

```js
const { instance } = await WebAssembly.instantiate(bytes, {});
const { add, fib, alloc, dealloc, count_chars, memory } = instance.exports;
console.log("add(2, 40) =", add(2, 40));
console.log("fib(90) =", fib(90));

const enc = new TextEncoder().encode("سلام wasm");
const ptr = alloc(enc.length);
new Uint8Array(memory.buffer, ptr, enc.length).set(enc);
console.log(`bytes=${enc.length} chars=${count_chars(ptr, enc.length)}`);
dealloc(ptr, enc.length);
```

```text
add(2, 40) = 42
fib(90) = 2880067194370816120n
bytes=13 chars=9
```

Both builds printed the same. Note the `n`: a Rust `u64` arrives in JavaScript as a `BigInt`. This is the same discipline as C FFI: you own the allocation, the pointer is just an integer, and nothing checks you.

## wasm-bindgen: generated glue

Writing that by hand for every function does not scale. The **wasm-bindgen** crate and CLI generate the glue:

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}! Greetings from Rust.")
}
```

The CLI version must match the crate version exactly (both 0.2.129 here). After `wasm-bindgen target/wasm32-unknown-unknown/release/greeter.wasm --target nodejs --out-dir pkg` we get a `.js` file, a `.d.ts` and a `_bg.wasm`:

```text
$ node run.cjs
Hello, Roham! Greetings from Rust.
Hello, سلام! Greetings from Rust.
```

The size: the cargo output (with `opt-level = "z"`, `lto`, `strip`) was 27347 bytes, the processed `greeter_bg.wasm` is 12716 bytes, plus 3769 bytes of generated JavaScript. I did not compare against the manual version with the same functions, so I make no claim about the overhead of the glue.

## WASI: wasm outside the browser

**WASI** is a system interface (files, args, stdin, clock) that a host grants explicitly. A plain Rust CLI needs no code change, only a target: `cargo build --release --target wasm32-wasip1` gave a 71215-byte `wordcount.wasm`. Node's `node:wasi` (experimental, it prints a warning) ran it:

```text
$ printf 'one two\nthree\n' | node run.mjs target/wasm32-wasip1/release/wordcount.wasm
args=["a", "b"] lines=2 words=3
file says: hello from the host
```

The program reads `/data/hello.txt`. That path exists only because the host passed `preopens: { "/data": ... }`. With `preopens: {}` the same module printed just the first line: the file was invisible. That is the sandbox working.

## Go on the same ground

Go can target wasm too: `GOOS=js GOARCH=wasm` and `GOOS=wasip1 GOARCH=wasm`. A hello world printed `hello from Go` under Node WASI, and the sizes were 2635407 bytes (js) and 2607556 bytes (wasip1; 2557546 with `-ldflags="-s -w"`). The equivalent Rust hello world with `opt-level=z`, `lto`, `strip=symbols` was 42565 bytes. The Go program carries its runtime, which is the likely cause, but I did not measure which part dominates.

## When wasm makes sense

- Plugins and untrusted code: the host decides what the module may touch.
- Sharing one piece of logic with JavaScript code (validation, parsing, a codec).
- Edge or serverless runtimes that accept wasm modules.

And when it does not:

- A normal backend service: a native binary is simpler, and WASI support in libraries (sockets, threads) varies.
- Heavy DOM work: wasm still goes through JavaScript for it.
- Frequent small calls with strings: every call copies bytes across the boundary.

## A few things to watch

- The `wasm-bindgen` CLI and crate versions must match.
- Without glue, only numbers cross; `u64` becomes `BigInt` in JavaScript.
- Free what you `alloc`, or the module leaks.
- WASI in Node is experimental and may change.
- Size depends on the profile (24161 vs 10334 bytes above); measure your own build.

## Exercise

Add an exported `reverse(ptr, len)` function that reverses a string in place and call it from Node. Then compare how much code `wasm-bindgen` saves.

## What's next

Next is the Rust capstone project: a complete service.
