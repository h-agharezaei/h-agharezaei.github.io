+++
date = '2026-12-08T10:00:00+03:30'
draft = false
title = 'Modules, crates and Cargo in Rust'
description = 'Rust modules, crates and Cargo: packages, pub and privacy errors, use and re-exports, lib plus bin, Cargo features, dev-dependencies and workspaces.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "cargo", "modules", "crates"]
cover = { image = "/images/covers/rust-modules-crates-cargo.png", alt = "Modules, crates and Cargo in Rust", hiddenInSingle = true }
+++

After [error handling with Result and Option](/posts/rust-error-handling-result/), every example still fits in one file. This post is about splitting code up and about Cargo, which builds and manages the project. Three words are easy to mix up, so first the definitions: a **crate** is one compilation unit (a library or an executable), a **package** is what `Cargo.toml` describes and holds one or more crates, and a **module** is a namespace inside a crate.

> I ran everything below with Rust 1.90 (cargo 1.90.0). Outputs and compiler messages are copied from those runs.

## Modules in one file, and privacy

`mod` declares a module, and everything inside it is **private by default**. Add `pub` to expose an item:

```rust
mod bank {
    pub struct Account {
        pub owner: String,
        balance: i64,
    }
    impl Account {
        pub fn new(owner: &str) -> Account { /* sets balance to 0 */ }
        pub fn balance(&self) -> i64 { self.balance }
    }
    fn audit(b: i64) { /* private helper */ }
}
```

Privacy applies to functions and to individual struct fields. Calling `bank::audit(5)` from outside gives:

```text
error[E0603]: function `audit` is private
  --> examples/priv_fn.rs:12:11
   |
12 |     bank::audit(5);
   |           ^^^^^ private function
```

and reading `a.balance` from outside gives:

```text
error[E0616]: field `balance` of struct `Account` is private
  --> examples/priv_field.rs:15:34
   |
15 |     println!("{} {}", a.owner, a.balance);
   |                                  ^^^^^^^ private field
```

The rule: an item is visible inside the module that defines it and that module's descendants, and outside only if it is `pub`. `pub(crate)` means "visible anywhere in this crate", and `pub(super)` means "visible in the parent module".

## Modules in separate files

`mod store;` (with a semicolon) tells the compiler to load the module from a file: `store.rs`, or `store/mod.rs`. Both work; I prefer `store.rs` plus a `store/` folder for its children. Here is the package I built, called `inventory`:

```text
inventory/
├── Cargo.toml
├── Cargo.lock
├── src/
│   ├── lib.rs          # library crate root: pub mod item; mod store; ...
│   ├── main.rs         # binary crate root
│   ├── item.rs         # mod item
│   ├── store.rs        # mod store
│   ├── store/
│   │   └── audit.rs    # mod store::audit
│   └── bin/
│       └── report.rs   # a second binary
├── tests/store.rs
└── examples/
```

`lib.rs` is the root of the library crate and `main.rs` the root of the binary crate. The two crates live in one package and share its name. Every file in `src/bin/` becomes an additional binary.

## Paths and use

Inside a crate you can name an item with a path: `crate::` starts at the crate root, `self::` at the current module, and `super::` at the parent. Inline modules in `lib.rs` show all three:

```rust
pub mod price {
    pub fn format(cents: u64) -> String { format!("{}.{:02}", cents / 100, cents % 100) }

    pub mod tax {
        pub fn with_vat(cents: u64) -> String { crate::price::format(cents * 120 / 100) }
        pub fn plain(cents: u64) -> String { super::format(cents) }
    }
}
```

`use` brings a name into scope so you don't repeat the path. **`pub use`** also re-exports it: `lib.rs` has `pub use store::Store;`, so users write `inventory::Store` even though `store` itself is a private module. That is how you keep the internal layout free to change.

## Library and binary in one package

`src/main.rs` uses its own package as an ordinary dependency, by the package name:

```rust
use inventory::item::Item;
use inventory::price::tax;
use inventory::Store;
```

With more than one binary, a bare `cargo run` fails (`could not determine which binary to run`), so name it:

```text
$ cargo run --bin inventory
3 item kinds in stock
order: ["bolt", "nut", "washer"]
total: 30.50 / with VAT: 36.60
$ cargo run --bin report
report: 1 item kinds in stock
```

## Cargo.toml: dependencies and features

```toml
[dependencies]
fastrand = { version = "2.5.0", optional = true }

[dev-dependencies]
pretty_assertions = "1.4.1"

[features]
shuffle = ["dep:fastrand"]
```

`[dev-dependencies]` are used only by tests, examples and benchmarks; `tests/store.rs` uses `pretty_assertions`, and it never ends up in your normal build. A **feature** is a named compile-time switch. Here `shuffle` turns on the optional `fastrand` dependency, and the code is gated with `#[cfg(feature = "shuffle")]`:

```rust
#[cfg(feature = "shuffle")]
pub fn shuffle(&mut self) { fastrand::shuffle(&mut self.items); }
```

`main.rs` calls it under the same `cfg`. Without the flag the function does not exist, and `fastrand` is not even in the dependency graph:

```text
$ cargo tree
inventory v0.1.0 (.../rust-modules-crates-cargo)
[dev-dependencies]
└── pretty_assertions v1.4.1
    ├── diff v0.1.13
    └── yansi v1.0.1

$ cargo tree --features shuffle
inventory v0.1.0 (.../rust-modules-crates-cargo)
└── fastrand v2.5.0
[dev-dependencies]
└── pretty_assertions v1.4.1
    ...
$ cargo run --bin inventory --features shuffle
order: ["washer", "nut", "bolt"]
```

The order is random, so yours will differ. **`Cargo.lock`** records the exact version and checksum of every dependency. Commit it for applications so everyone builds the same thing; `Cargo.toml` says "2.5.0 or compatible", the lock file says which one was chosen.

## Workspaces

When one repository holds several related packages, a **workspace** shares one `Cargo.lock` and one `target/` directory. My test workspace:

```text
workspace/
├── Cargo.toml      # [workspace] resolver = "3", members = ["greeter", "cli"]
├── Cargo.lock
├── greeter/        # library: pub fn hello(name) -> String
│   ├── Cargo.toml
│   └── src/lib.rs
└── cli/            # binary, depends on greeter = { path = "../greeter" }
    ├── Cargo.toml
    └── src/main.rs
```

```text
$ cargo run -p cli
hello, workspace
$ cargo tree
cli v0.1.0 (.../workspace/cli)
└── greeter v0.1.0 (.../workspace/greeter)
```

`-p` selects a member package; it also works with `cargo test -p greeter`.

## Compared with Go

The [Go post](/posts/go-packages-modules/) described the same split with different words: a Go package is a directory and a Go module is the unit described by `go.mod`. In Rust a crate is closer to a Go package as a unit of compilation, but modules are declared in code with `mod`, not by directory alone. Go marks visibility with capitalization and Rust with `pub`, and both pin dependency versions in a second file (`go.sum`, `Cargo.lock`).

## A few things to watch

- Forgetting `mod foo;` in the parent: a new file is simply ignored; it is not found automatically.
- `pub` on a struct does not make its fields public. Each field needs its own `pub`.
- `cargo build` compiles all targets in `src/`, so a file in `src/bin/` with a compile error breaks the whole build. I put my failing demos in `examples/` for that reason.
- Features should be additive. A feature that removes or changes behavior surprises anyone who depends on you.

## Exercise

1. Add a `pub(crate) fn` to `store.rs`, call it from `item.rs`, and then try calling it from `main.rs`. Read the error.
2. Move the `price` module out of `lib.rs` into `src/price.rs` and `src/price/tax.rs`.
3. Add a third member to the workspace that depends on `greeter`, and run it with `cargo run -p`.

## What's next

Next we look at generics and traits in Rust: writing code that works for many types and how Rust describes shared behavior.
