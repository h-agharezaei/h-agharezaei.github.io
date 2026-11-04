+++
date = '2027-03-14T10:00:00+03:30'
draft = false
title = 'Rust and WebAssembly'
description = 'Rust and WebAssembly: compile to wasm32-unknown-unknown and wasm32-wasip1, pass strings across the boundary and use wasm-bindgen.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "wasm", "webassembly", "wasi", "wasm-bindgen", "intermediate"]
cover = { image = "/images/covers/rust-wasm.png", alt = "Rust and WebAssembly", hiddenInSingle = true }
+++

You have a small piece of logic in Rust, say a validator or a parser, and you want to run exactly the same code somewhere that does not run native binaries: inside a JavaScript program, or inside a host that wants to run plugins it does not trust. Rewriting it in JavaScript means two copies that can disagree. Shipping a native library does not help, because the target is not a normal machine.

{{< term "webassembly" "WebAssembly" >}} (wasm for short) is the usual answer. It is a portable binary instruction format that runs on a sandboxed virtual machine. A wasm module cannot touch the DOM, files or the network by itself. It only has its own **linear memory**, which is one flat array of bytes, and whatever functions the host (a browser, Node, a runtime) chooses to give it.

This post builds Rust for wasm and looks at the one thing that surprises people first: only numbers can cross the boundary. A string has to be copied into the module's memory and passed as a pointer and a length. It comes after [release engineering](/posts/rust-docker-ci-release/): the artifact this time is a `.wasm` file instead of a Docker image. In [the unsafe and FFI post](/posts/rust-unsafe-ffi/) we already crossed a boundary with the C ABI, and Go did the same in [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/). WebAssembly is another way to cross a boundary, with a sandbox in the middle.

> I built and ran the `raw` and `wasi` demos and the Go sizes again for this version of the post, with `rustc 1.90.0` (edition 2024), Node 20.13.1 and Go 1.27.3 on macOS arm64. The `wasm-bindgen` command-line tool is not installed on this machine and I installed nothing, so the `wasm-bindgen` section below is from my original run, with `wasm-bindgen` 0.2.129 (the version locked in that demo's `Cargo.lock`). There was no browser available either: everything is loaded from Node, and I make no claims about browsers. The demos are local crates: `raw`, `bindgen`, `wasi` and `gohello`.

## The minimal path: numbers only

Set up the targets once with `rustup target add wasm32-unknown-unknown wasm32-wasip1`. We start with `wasm32-unknown-unknown`, the target with no system interface at all. The crate type is `cdylib`, which makes Cargo produce a stand-alone `.wasm` file, and the functions look exactly like the C ABI ones from the FFI post:

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

`#[unsafe(no_mangle)]` keeps the function name as it is, so the host can find `add` in the module's exports. I also added a profile called `small` (`opt-level = "z"`, `lto = true`, `strip = true`, `codegen-units = 1`; the meaning of these is in [the release post](/posts/rust-docker-ci-release/)) and built the crate twice, with `cargo build --release --target wasm32-unknown-unknown` and with `--profile small`. The size of `raw.wasm` in bytes was:

```text
24161   (release)
10334   (small)
```

These sizes include the string helpers from the next section, and they are the same numbers as in my original run.

## Strings need linear memory

A string is not a number, so the host has to put its bytes into the module's memory and then pass the address and the length. The module exports `alloc` and `dealloc` for that (they use a `Layout` with alignment 1, which is right for bytes), and a function that reads the bytes back. Here is the reading function:

```rust
#[unsafe(no_mangle)]
pub unsafe extern "C" fn count_chars(ptr: *const u8, len: usize) -> usize {
    let bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
    std::str::from_utf8(bytes).map(|s| s.chars().count()).unwrap_or(0)
}
```

It builds a slice from the pointer and length, checks that it is valid UTF-8, and counts the characters (not bytes). Now the JavaScript side, run with `node js/run.mjs <file>`. It loads the module, calls the numeric functions, and then does the three steps for a string: encode it as UTF-8, `alloc` space inside the module and copy the bytes there, call `count_chars`. (This is the core of the script; the real file also prints the export names and the memory size.)

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

The complete output of the script, for both builds (they printed the same):

```text
exports: memory, add, fib, alloc, dealloc, count_chars, __data_end, __heap_base
add(2, 40) = 42
fib(50) = 12586269025n
fib(90) = 2880067194370816120n
bytes=13 chars=9
memory pages: 18
```

Line by line:

- `exports` lists what the module offers. Besides our functions there are the `memory` itself and two markers (`__data_end` and `__heap_base`) that the toolchain adds.
- `add` and `fib` return the expected numbers. Note the `n` after the Fibonacci results: a Rust `u64` arrives in JavaScript as a `BigInt`, because a plain JavaScript number cannot hold every 64-bit integer.
- `bytes=13 chars=9`: the text `سلام wasm` is 9 characters, but in UTF-8 the four Persian letters take two bytes each, so it needs 13 bytes. The module counted the characters correctly from the bytes the host copied in.
- `memory pages: 18` is the size of the module's memory in 64 KiB pages. I did not investigate why it is 18.

This is the same discipline as in C FFI: you own the allocation, the pointer is just an integer, and nothing checks you. That is also why you have to call `dealloc`.

## wasm-bindgen: generated glue

Writing this by hand for every function does not scale. The {{< term "wasm-bindgen" "wasm-bindgen" >}} crate and its command-line tool generate the glue for you. You write a normal Rust function and mark it:

```rust
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn greet(name: &str) -> String {
    format!("Hello, {name}! Greetings from Rust.")
}
```

Here `name` is a real `&str` and the return value a real `String`, and the generated code does the copying we wrote by hand above. According to the wasm-bindgen docs, the command-line tool and the crate must be the same version; both were 0.2.129 in my original run. After building for `wasm32-unknown-unknown`, I ran `wasm-bindgen target/wasm32-unknown-unknown/release/greeter.wasm --target nodejs --out-dir pkg`. It produced a `.js` file, a `.d.ts` (the TypeScript types) and a `_bg.wasm`. Then a small Node script calls it like any JavaScript library (it also calls an `add` function, whose output line I leave out here):

```text
$ node run.cjs
Hello, Roham! Greetings from Rust.
Hello, سلام! Greetings from Rust.
```

For the sizes, in the original run: the file Cargo produced (with `opt-level = "z"`, `lto`, `strip`) was 27347 bytes, the processed `greeter_bg.wasm` was 12716 bytes, and the generated JavaScript added 3769 bytes. I did not compare this with a manual version with the same functions, so I make no claim about the cost of the glue.

## WASI: wasm outside the browser

The `raw` module above could do nothing except compute. {{< term "wasi" "WASI" >}} is a system interface (files, command-line arguments, stdin, the clock) that a host grants to a module explicitly. A plain Rust command-line program needs no code change for it, only a different target. The demo is a small word counter that prints its arguments, counts the lines and words of stdin, and then tries to read `/data/hello.txt`:

```rust
let args: Vec<String> = std::env::args().skip(1).collect();
let mut text = String::new();
std::io::stdin().read_to_string(&mut text).unwrap();
let words = text.split_whitespace().count();
println!("args={args:?} lines={} words={words}", text.lines().count());
if let Ok(path) = std::fs::read_to_string("/data/hello.txt") {
    println!("file says: {}", path.trim());
}
```

`cargo build --release --target wasm32-wasip1` gave a 71215-byte `wordcount.wasm` (with `opt-level = "z"`, `lto` and `strip` in the profile). Node's `node:wasi` module (experimental: it prints a warning, which I left out) can run it. The host script passes the arguments `a b`, connects stdin, and maps a local `data` directory to `/data` inside the module:

```text
$ printf 'one two\nthree\n' | node run.mjs target/wasm32-wasip1/release/wordcount.wasm
args=["a", "b"] lines=2 words=3
file says: hello from the host
```

The input has two lines and three words, and the program printed both its arguments and the content of the file. The program reads `/data/hello.txt`, and that path exists only because the host passed `preopens: { "/data": ... }`. With `preopens: {}` the same module printed just the first line: the file was invisible. That is the sandbox working: the module can only see what the host chose to give it.

## Go on the same ground

Go can target wasm too, with `GOOS=js GOARCH=wasm` and `GOOS=wasip1 GOARCH=wasm`. I built a hello world both ways and ran the wasip1 one under Node WASI: it printed `hello from Go`. The sizes with Go 1.27.3 were 2507699 bytes (js) and 2480862 bytes (wasip1; 2436331 with `-ldflags="-s -w"`). (My original run, with an earlier Go version, measured about 2.6 MB for the same builds, so these numbers move with the Go version.) The equivalent Rust hello world, built with `rustc --target wasm32-wasip1 -C opt-level=z -C lto -C strip=symbols`, was 42565 bytes and printed `hello from Rust`. The Go program carries its own runtime, which is the likely cause of the difference, but I did not measure which part dominates.

## When wasm makes sense

- Plugins and untrusted code: the host decides what the module may touch.
- Sharing one piece of logic with JavaScript code (validation, parsing, a codec).
- Edge or serverless runtimes that accept wasm modules.

And when it does not:

- A normal backend service: a native binary is simpler, and WASI support in libraries (sockets, threads) varies.
- Heavy DOM work: wasm still goes through JavaScript for it.
- Frequent small calls with strings: every call copies bytes across the boundary.

## Before you reach for wasm

- **Versions of `wasm-bindgen` must match.** The command-line tool and the crate in `Cargo.toml` have to be the same version, or the tool will complain.
- **Without glue, only numbers cross.** A `u64` becomes a `BigInt` in JavaScript, which surprises code that expects a normal number.
- **Free what you `alloc`.** The module does not clean up memory the host asked for, so forgetting `dealloc` leaks.
- **WASI in Node is experimental** and may change.
- **Size depends on the profile** (24161 against 10334 bytes above); measure your own build.

## Exercise

Add an exported `reverse(ptr, len)` function that reverses a string in place and call it from Node. Then compare how much code `wasm-bindgen` saves.

## What's next

*Rust capstone: a complete service* wires the earlier pieces together.
