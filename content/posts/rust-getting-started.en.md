+++
date = '2026-10-29T10:00:00+03:30'
draft = false
title = 'Getting started with Rust: install, Cargo and a first program'
seoTitle = 'Getting Started with Rust: Install and Cargo'
description = 'Getting started with Rust for Go and Node.js developers: install with rustup, learn basic Cargo commands, add a dependency and run a first program.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "cargo", "beginner", "tooling"]
cover = { image = "/images/covers/rust-getting-started.png", alt = "Getting started with Rust: install, Cargo and a first program", hiddenInSingle = true, hiddenInList = true }
+++

This is the first post in a Rust series, from beginner to advanced. I have spent most of my career writing backend services in Go and Node.js, and I am learning Rust in public. Where it helps, I will compare Rust with Go, since I have already written a few posts about Go.

Why Rust at all? Honestly, not because it is trendy. Rust gives you memory safety without a garbage collector, performance in the same range as C and C++, and a strong type system that moves many bugs from runtime to compile time. The price is a steeper learning curve and a compiler that argues with you a lot at the beginning. This post is only about tooling: install, Cargo, and a program that runs.

> Everything below was run with Rust 1.90.0 on macOS.

## Installing with rustup

The official way is **rustup**, the toolchain manager (from https://rustup.rs):

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

It installs the compiler (`rustc`), the build tool and package manager (**Cargo**) and lets you update later with `rustup update`. Check the install:

```bash
$ rustc --version
rustc 1.90.0 (1159e78c4 2025-09-14)
$ cargo --version
cargo 1.90.0 (840b83a10 2025-07-30)
```

## Your first project with Cargo

In practice you almost never call `rustc` directly. Cargo does it:

```bash
$ cargo new rust-getting-started
    Creating binary (application) `rust-getting-started` package
$ cd rust-getting-started
```

The layout is small: `Cargo.toml` (name, version, dependencies; similar to `go.mod` plus metadata), and `src/main.rs`, the entry point. This is the generated `Cargo.toml`:

```toml
[package]
name = "rust-getting-started"
version = "0.1.0"
edition = "2024"

[dependencies]
```

`edition` is the language edition; it lets Rust evolve without breaking old code. The generated `main.rs` is a hello world, and `cargo run` builds and runs it:

```bash
$ cargo run
   Compiling rust-getting-started v0.1.0 (...)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 1.37s
     Running `target/debug/rust-getting-started`
Hello, world!
```

## Debug vs release

`cargo build` makes a fast-to-compile debug build in `target/debug/`. `cargo build --release` turns optimizations on and puts the result in `target/release/`:

```bash
$ cargo build --release
    Finished `release` profile [optimized] target(s) in 0.34s
$ ls target
CACHEDIR.TAG  debug  release
$ ls -la target/debug/rust-getting-started target/release/rust-getting-started
-rwxr-xr-x@ 1 hossein  staff  443816 ... target/debug/rust-getting-started
-rwxr-xr-x@ 1 hossein  staff  406208 ... target/release/rust-getting-started
```

For hello world the sizes are close; the real difference is in speed on heavy code. Use debug while developing and `--release` for anything you measure or ship.

## Check, format, lint

- `cargo check` type-checks without producing a binary, so it is much faster than a full build. I run it constantly.
- `cargo fmt` formats code with `rustfmt` (like `gofmt`). `cargo fmt --check` only reports.
- `cargo clippy` is the linter. It was installed on my machine with the default rustup profile and printed no warnings for the code below.

## A slightly bigger program, with a dependency

Add a crate with `cargo add` (this needs network the first time):

```bash
$ cargo add rand
      Adding rand v0.10.3 to dependencies
```

Cargo edits `Cargo.toml` for us (`rand = "0.10.3"`). Now a program that takes an optional CLI argument and prints a greeting with a random number:

```rust
use std::env;

use rand::RngExt;

fn main() {
    // First CLI argument, or "world" when none is given.
    let name = env::args().nth(1).unwrap_or_else(|| "world".to_string());
    let lucky: u32 = rand::rng().random_range(1..=100);
    println!("Hello, {name}! Your lucky number is {lucky}.");
}
```

`env::args().nth(1)` returns an `Option` (there may be no argument), and `unwrap_or_else` supplies the default. We will cover `Option` properly later. Output (the number differs on every run):

```bash
$ cargo run -q
Hello, world! Your lucky number is 78.
$ cargo run -q -- Roham
Hello, Roham! Your lucky number is 20.
```

The `--` separates Cargo's own flags from the arguments for your program.

## Go vs Rust tooling

| Task | Go | Rust |
| --- | --- | --- |
| New project | `go mod init` | `cargo new` |
| Build and run | `go run .` | `cargo run` |
| Build | `go build` | `cargo build` (`--release` for optimized) |
| Add a dependency | `go get` | `cargo add` |
| Format | `gofmt` / `go fmt` | `cargo fmt` |
| Dependency file | `go.mod` | `Cargo.toml` (plus `Cargo.lock`) |

## A few things to watch

- Cargo builds into `target/`, which can get large. Keep it out of git (`cargo new` adds a `.gitignore` for it).
- The first build with a new dependency downloads and compiles it; later builds reuse the cache.
- Crate versions move fast. `rand` 0.10 needs `use rand::RngExt` for `random_range`; older tutorials show different APIs, so check the version.
- Prefer `cargo check` while editing and `--release` when you measure performance.
- Clippy and rustfmt are components; if `cargo clippy` is missing, run `rustup component add clippy`.

## Exercise

1. Change the program to take two arguments, a name and a maximum number, and pick the lucky number from `1..=max`. (Hint: arguments are strings, so you will need to parse the second one.)
2. Run `cargo build --release` and compare the binary with the debug one using `ls -la`.

## What's next

Next we will look at types, variables and control flow in Rust: immutability by default, shadowing, `if`, `match` and loops.
