+++
date = '2026-10-29T10:00:00+03:30'
draft = false
title = 'Getting started with Rust: install, Cargo and a first program'
seoTitle = 'Getting Started with Rust: Install and Cargo'
description = 'Getting started with Rust for Go and Node.js developers: install with rustup, learn basic Cargo commands, add a dependency and run a first program.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "cargo", "beginner", "tooling"]
cover = { image = "/images/covers/rust-getting-started.png", alt = "Getting started with Rust: install, Cargo and a first program", hiddenInSingle = true }
+++

Say you have decided to learn Rust, and your first questions are: what do I install, and what do I type? The short answer is that you almost never call the Rust compiler, `rustc`, directly. Two tools stand in front of it. {{< term "rustup" "rustup" >}} installs and updates the compiler and the tools around it. {{< term "cargo" "Cargo" >}} creates projects, builds and runs your code, adds libraries and tidies the code up. Cargo plays roughly the role of the `go` command in Go.

This post also opens a Rust series, from beginner to advanced. I have spent most of my career writing backend services in Go and Node.js, and I am learning Rust in public. I have also written a few posts about Go (they start with [Getting started with Go](/posts/go-getting-started/)), so where a comparison helps, I will compare Rust with Go.

Why Rust at all? Not because it is trendy. Rust gives you memory safety without a {{< term "garbage-collector" "garbage collector" >}}: your program does not need a separate part of the runtime that cleans up unused memory, and still the compiler catches mistakes such as using memory after it has been freed. Its speed is in the same range as C and C++. And it has a strong type system that moves many bugs from runtime to compile time. The price is a steeper learning curve and a compiler that argues with you a lot at the beginning. This post does not get into those arguments yet. It is only about tooling: install, create a project and run a program.

> Everything below was run with Rust 1.90.0 on macOS. Build times and random numbers differ from run to run.

## Installing with rustup

The official way to install Rust is a tool called **rustup**. It is a "toolchain manager". A toolchain is the set of tools you need to work with the language: the compiler, Cargo and a few more. rustup installs them, and later it can move you to a newer version. You get the install command from https://rustup.rs:

```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
```

Afterwards you can update with `rustup update`. To make sure everything is in place, ask for the versions of the compiler and Cargo:

```bash
$ rustc --version
rustc 1.90.0 (1159e78c4 2025-09-14)
$ cargo --version
cargo 1.90.0 (840b83a10 2025-07-30)
```

Both tools answer, and both are version 1.90.0. Your version number is probably higher, and that is fine.

## The first project with Cargo

Now we create a new project. The command `cargo new` makes a folder with a ready-made layout:

```bash
$ cargo new rust-getting-started
    Creating binary (application) `rust-getting-started` package
$ cd rust-getting-started
```

`binary (application)` means a project that builds a runnable program. (The other kind is a library, which provides code for other projects.) Two things matter inside the folder. `src/main.rs` is where the program starts. `Cargo.toml` is the project's identity card: its name, its version and the libraries it needs. If you know Go, it is similar to `go.mod`. This is the `Cargo.toml` that `cargo new` generated:

```toml
[package]
name = "rust-getting-started"
version = "0.1.0"
edition = "2024"

[dependencies]
```

The `edition` line needs one explanation. To move forward, a language sometimes has to break something. Rust solves this with "editions": each project says which edition of the language it was written in, and the compiler follows that one. So the language can evolve without old code breaking. The `[dependencies]` section is empty for now.

`cargo new` also put a hello world program in `src/main.rs`. The command `cargo run` compiles it first and then runs it:

```bash
$ cargo run
   Compiling rust-getting-started v0.1.0 (...)
    Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.67s
     Running `target/debug/rust-getting-started`
Hello, world!
```

The first three lines are printed by Cargo, not by our program. `Compiling` means compilation started. `Finished` says it is done and which "profile" was used; I explain profiles in the next section. `Running` tells you which executable it started. The last line, `Hello, world!`, is the output of the program itself.

## Debug and release

You saw Cargo print `dev` profile. Cargo has two main ways to build. `cargo build` produces a **debug** build: it compiles quickly because it does not optimize the code, and it carries extra information that debuggers use. The output goes to `target/debug/`. `cargo build --release` turns optimization on. Compiling is slower, but the final program runs faster, and the output goes to `target/release/`:

```bash
$ cargo build --release
    Finished `release` profile [optimized] target(s) in 0.15s
$ ls target
CACHEDIR.TAG  debug  release
$ ls -l target/debug/rust-getting-started target/release/rust-getting-started
-rwxr-xr-x@ 1 <user>  staff  444520 ... target/debug/rust-getting-started
-rwxr-xr-x@ 1 <user>  staff  406192 ... target/release/rust-getting-started
```

Each build kind got its own folder inside `target/`. The number in the fifth column is the file size in bytes. For a hello world the two numbers are close; the real difference of release shows when the program does heavy work. (I replaced my user name with `<user>`. The sizes also depend on the compiler version and the machine.) A simple rule: use debug while writing code, and use `--release` for anything you measure or ship.

## Check, format and lint

Three more small commands will serve you every day:

- `cargo check` only verifies that the code is valid (types and the rules of the language) and does not produce an executable, so it is much faster than a full build. I run it a lot while writing code.
- `cargo fmt` tidies the code with the `rustfmt` tool, like `gofmt` in Go. `cargo fmt --check` changes nothing and only tells you if a file is not tidy.
- `cargo clippy` is a **linter**: it reads your program and points out places that work but could be written better, or that are probably mistakes. I ran it on the program in the next section and it gave no warnings.

## A slightly bigger program, with a dependency

So far we have not written any code. Let us write a small program that uses an outside library. In Rust, a package of code is called a **crate**, and public crates are published on crates.io. To make a random number we need a crate named `rand`. Adding it is one command (it needs the internet the first time):

```bash
$ cargo add rand
      Adding rand v0.10.3 to dependencies
```

Cargo edited `Cargo.toml` for us and put a line like `rand = "0.10.3"` under `[dependencies]`. The exact version that was really used is also recorded in a file called `Cargo.lock`. Cargo creates that file itself, and you do not need to edit it by hand.

Now the program. It does something simple: it takes an optional command-line argument and prints a greeting with a random number between 1 and 100.

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

Line by line:

- `env::args()` gives the command-line arguments. Argument number 0 is the program's own name, so `.nth(1)` takes the first argument the user typed.
- The user may type no argument at all. That is why `nth(1)` returns its value inside an `Option`, which means "either there is something, or there is not". `unwrap_or_else` says: if there was nothing, use `"world"` instead. I will explain `Option` properly in later posts; this meaning is enough for now.
- `random_range(1..=100)` returns a number from 1 to 100, where 100 itself is possible.
- `println!` prints the text, and replaces anything inside `{}` with the value of that variable.

We run it twice, once without an argument and once with a name:

```bash
$ cargo run -q
Hello, world! Your lucky number is 82.
$ cargo run -q -- Roham
Hello, Roham! Your lucky number is 86.
```

The `-q` (quiet) option removes the `Compiling` and `Running` lines so that only the program's own output remains. The `--` separates Cargo's own arguments from your program's arguments; everything after it goes to the program. The first time we gave no argument, so the default name `world` was printed; the second time it was `Roham`. The random number differs on every run, so your numbers will be different.

## Go and Rust tools side by side

To see the everyday tasks next to each other:

| Task | Go | Rust |
| --- | --- | --- |
| New project | `go mod init` | `cargo new` |
| Build and run | `go run .` | `cargo run` |
| Build | `go build` | `cargo build` (with `--release` for optimized) |
| Add a dependency | `go get` | `cargo add` |
| Format code | `gofmt` / `go fmt` | `cargo fmt` |
| Dependency file | `go.mod` | `Cargo.toml` (plus `Cargo.lock`) |

## Common tooling traps

- **The `target/` folder grows large.** Cargo puts all build output there. Keep it out of git; `cargo new` creates a `.gitignore` that already excludes `target`.
- **The first build after adding a dependency is slow.** Cargo downloads and compiles the crate. Later builds reuse that work and are faster.
- **Crate versions change, and old tutorials mislead.** In version 0.10 of `rand`, you need `use rand::RngExt` to call `random_range`. If an older tutorial shows different code, check the version first.
- **Use the right command for the job.** While editing, `cargo check` gives the fastest feedback; when measuring speed you must use `--release`, because the speed of a debug build is not meaningful.
- **Clippy and rustfmt are "components".** If `cargo clippy` is not found on your machine, install it with `rustup component add clippy`.

## Exercise

1. Change the program so that it takes two arguments, a name and a maximum number, and picks the lucky number from `1..=max`. (Hint: arguments are strings, so you have to parse the second one.)
2. Run `cargo build --release` and compare the executable with the debug one using `ls -l`.

## What's next

"Types, variables and control flow in Rust". Now that we can build and run a program, it is time to learn the language itself: its basic vocabulary, where immutability, shadowing, `if` and `match` differ from Go right from the start.
