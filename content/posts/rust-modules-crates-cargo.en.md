+++
date = '2026-12-08T10:00:00+03:30'
draft = false
title = 'Modules, crates and Cargo in Rust'
description = 'Rust modules, crates and Cargo: packages, pub and privacy errors, use and re-exports, lib plus bin, Cargo features, dev-dependencies and workspaces.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "cargo", "modules", "crates"]
cover = { image = "/images/covers/rust-modules-crates-cargo.png", alt = "Modules, crates and Cargo in Rust", hiddenInSingle = true }
+++

Up to this point in the series, every example fit in one file. A real program grows to thousands of lines, and if everything lives in one file and one namespace, finding things gets hard and every internal helper is accidentally available to everyone. Rust has an answer for both problems: you split the code into **modules** and files, and for each item you decide whether it is visible from outside. The interesting part is that the default is "not visible". If you write a function inside a `mod` and call it from outside, the compiler refuses. Now that our code has grown past [Error handling with Result and Option in Rust](/posts/rust-error-handling-result/), it is time to see how this splitting works.

First, three words that are easy to mix up. An analogy helps: think of a parcel.

- A {{< term "crate" "crate" >}} is one unit of compilation, the thing the compiler builds in one go: either a library (that others use) or an executable program.
- A **package** is the parcel itself: what the `Cargo.toml` file describes, holding one or more crates.
- A **module** is a namespace inside a crate, like a folder that keeps related things together and decides which of them are visible from outside.

The tool that builds and manages all of this is {{< term "cargo" "Cargo" >}}, which you met in the [first post of this series](/posts/rust-getting-started/).

> I ran everything below with Rust 1.90 (cargo 1.90.0). Outputs and compiler messages are copied from those runs. Where the output contained the path of the project folder, I shortened it to `...`.

## Modules in one file, and privacy

`mod` declares a module, and everything inside it is **private by default**, meaning it is visible only from inside that module. To expose an item you write `pub` (for public) in front of it. The program below has a module called `bank`: an account struct with one public and one private field, and a private helper function called `audit`:

```rust
mod bank {
    pub struct Account {
        pub owner: String,
        balance: i64,
    }

    impl Account {
        pub fn new(owner: &str) -> Account {
            Account { owner: owner.to_string(), balance: 0 }
        }
        pub fn deposit(&mut self, n: i64) {
            self.balance += n;
            audit(self.balance);
        }
        pub fn balance(&self) -> i64 {
            self.balance
        }
    }

    fn audit(b: i64) {
        println!("audit: balance is now {b}");
    }
}

use bank::Account;

fn main() {
    let mut a = Account::new("roham");
    a.deposit(50);
    println!("{} has {}", a.owner, a.balance());
}
```

```text
audit: balance is now 50
roham has 50
```

Everything works. `deposit` is inside the module, so it can see `audit` and the `balance` field. Outside the module we only have `Account`, `owner`, `new`, `deposit` and `balance()`, and to read the balance we must go through the `balance()` method. That way the module controls how an account can change.

Now let us see what happens when we touch something private from outside. First a tiny module where `audit` is private and `main` calls it directly:

```rust
mod bank {
    fn audit(b: i64) {
        println!("audit: {b}");
    }
    pub fn deposit(n: i64) {
        audit(n);
    }
}

fn main() {
    bank::deposit(5);
    bank::audit(5);
}
```

```text
error[E0603]: function `audit` is private
  --> examples/priv_fn.rs:12:11
   |
12 |     bank::audit(5);
   |           ^^^^^ private function
   |
note: the function `audit` is defined here
  --> examples/priv_fn.rs:2:5
   |
 2 |     fn audit(b: i64) {
   |     ^^^^^^^^^^^^^^^^
```

The line `bank::deposit(5)` is fine because it is `pub`. The error is only for `bank::audit(5)`, and the compiler also shows where the function is defined and why it is private. Privacy is not only for functions; it covers each field of a struct too. If we read `a.balance` from outside:

```text
error[E0616]: field `balance` of struct `Account` is private
  --> examples/priv_field.rs:15:34
   |
15 |     println!("{} {}", a.owner, a.balance);
   |                                  ^^^^^^^ private field
```

(In this program `main` prints `a.owner` and `a.balance`; `a.owner` is fine because it is `pub`, and only `a.balance` fails.) The general rule: an item is visible inside the module that defines it and the modules nested inside it, and outside only if it is `pub`. There are two narrower forms: `pub(crate)` means "visible in this whole crate, not outside it", and `pub(super)` means "visible in the parent module".

## Modules in separate files

Writing all the modules in one file is good only for examples. In a real project each module goes into its own file. For that, in the parent file you write just `mod store;` (with a semicolon and no braces), and the compiler reads the module from a file: `store.rs` or `store/mod.rs`. Both work; I prefer `store.rs` plus a `store/` folder for its child modules. To show this I built a package called `inventory` (a tiny warehouse) with this layout:

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

`lib.rs` is the root of the library crate and `main.rs` is the root of the executable crate. They are in one package and both carry its name. Each file inside `src/bin/` adds one more executable. Two things in this code matter. First `item.rs`: the fields have three different levels of access.

```rust
pub struct Item {
    pub name: String,
    qty: u32,
    pub(crate) cents: u64,
}
```

Everyone can see `name`, `qty` is visible only inside the `item` module (for outside I added a `qty()` method), and `cents` is visible only to code inside this crate. Second `store/audit.rs`:

```rust
use super::Store;

pub(super) fn describe(store: &Store) -> String {
    // A child module may touch the private field of its ancestor.
    format!("{} item kinds in stock", store.items.len())
}
```

The `items` field of `Store` is private, but `audit` is a child module of `store`, and a child is allowed to see the private things of its parent, which is why `store.items` compiles. The function `describe` itself is `pub(super)`, so only `store` can see and call it.

## Paths and use

To reach an item you write its path. `crate::` starts from the root of the crate, `self::` from the current module and `super::` from the parent. The inline modules in `lib.rs` show two of these forms:

```rust
pub mod price {
    pub fn format(cents: u64) -> String {
        format!("{}.{:02}", cents / 100, cents % 100)
    }

    pub mod tax {
        // Absolute path from the crate root.
        pub fn with_vat(cents: u64) -> String {
            crate::price::format(cents * 120 / 100)
        }

        // Relative path: go up one level, then down.
        pub fn plain(cents: u64) -> String {
            super::format(cents)
        }
    }
}
```

`with_vat` writes an absolute path (from the crate root), and `plain` goes one level up (`super`) and takes `format` from `price`. Both call the same function.

Writing the full path every time is tiring, so `use` brings a name into scope. Its special form is **`pub use`**, which in addition opens the name to others (a re-export). In `lib.rs` there is `pub use store::Store;`. The `store` module itself is private, but users can write `inventory::Store`. The benefit is that you can freely change the internal structure later while the public name stays the same.

## A library and an executable in one package

`src/main.rs` uses its own package like an ordinary dependency, by the package name. In other words, the executable is just a customer of your own library and sees only the `pub` items:

```rust
use inventory::item::Item;
use inventory::price::tax;
use inventory::Store;
```

When there is more than one executable in the package, a bare `cargo run` does not know which one to run. It says `could not determine which binary to run` and lists `available binaries: inventory, report`. So give the name with `--bin`:

```text
$ cargo run --bin inventory
3 item kinds in stock
order: ["bolt", "nut", "washer"]
total: 30.50 / with VAT: 36.60
$ cargo run --bin report
report: 1 item kinds in stock
```

The first output is from `main.rs`: three kinds of item were added and printed in the order we added them, and the total of the three lines, 2500, 500 and 50 cents, is 30.50; with 20 percent VAT it is 36.60 (`with_vat` multiplies the amount by 120/100). The second output is from `src/bin/report.rs`, our second program, which has just one item.

## Cargo.toml: dependencies and features

Dependencies are written in `Cargo.toml`. Our package has one of each kind:

```toml
[dependencies]
fastrand = { version = "2.5.0", optional = true }

[dev-dependencies]
pretty_assertions = "1.4.1"

[features]
shuffle = ["dep:fastrand"]
```

`[dev-dependencies]` are dependencies needed only for tests, examples and benchmarks. `tests/store.rs` uses `pretty_assertions`, and that dependency never enters the normal build. (Writing `"1.4.1"` means "1.4.1 or a compatible version", following Cargo's versioning rule.)

A **feature** is a named switch that is turned on or off at compile time. Here `shuffle` enables the optional dependency `fastrand`. It is typically used for a capability that not everyone needs, so that people who do not want it do not pull in an extra dependency. The code is guarded with `#[cfg(feature = "shuffle")]`:

```rust
#[cfg(feature = "shuffle")]
pub fn shuffle(&mut self) { fastrand::shuffle(&mut self.items); }
```

`main.rs` calls it behind the same `cfg`. Without the flag, the function does not exist at all and `fastrand` is not even in the dependency graph. `cargo tree` shows this:

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
    ├── diff v0.1.13
    └── yansi v1.0.1
$ cargo run --bin inventory --features shuffle
order: ["washer", "nut", "bolt"]
```

The first tree has only `pretty_assertions` (and its two dependencies) and no `fastrand`. With `--features shuffle` the second tree also has `fastrand`, and the program shuffles the list. The order is random and differs in your run (when I ran it again, by chance the original order came out).

The **`Cargo.lock`** file records the exact version and checksum of every dependency. `Cargo.toml` says "`fastrand` version 2.5.0 or a compatible one", and the lock file says which version was actually chosen. For applications, commit it so that everyone builds exactly the same thing.

## Workspaces

When a repository has several related packages, a **workspace** lets them share one `Cargo.lock` and one `target/` folder. My experimental workspace has two members: a library called `greeter` and an executable called `cli` that depends on it:

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

(`resolver` is a setting about how versions and features are chosen; I put in the value that comes with edition 2024 and did not go further into it.)

```text
$ cargo run -p cli
hello, workspace
$ cargo tree
cli v0.1.0 (.../workspace/cli)
└── greeter v0.1.0 (.../workspace/greeter)
```

`-p` selects a member package, and it works with `cargo test -p greeter` too. The dependency tree also says `cli` depends on `greeter`.

## Comparison with Go

The [Go post](/posts/go-packages-modules/) described the same organisation with other words. In Go a package is a directory and a module is the unit that `go.mod` describes. A Rust crate is closer to a Go package as a unit of compilation, but modules are declared in code with `mod` and do not depend only on the directory structure. Go marks visibility with a capital first letter and Rust with `pub`, and both lock dependency versions in a separate file (`go.sum` and `Cargo.lock`).

## Structure and visibility traps

- If you do not write `mod foo;` in the parent, the file `foo.rs` is simply ignored. Files are not discovered automatically; you have to declare the module.
- `pub` on a struct does not make its fields public. Each field needs its own `pub`, like `Account`, which kept `owner` open and `balance` closed.
- `cargo build` compiles only the library and the executables and does not touch `examples/`, but a broken file in `src/bin/` breaks the whole build. That is why I put my demos with errors in `examples/`. Note that `cargo test` does compile all the examples: when I ran `cargo test`, it stopped with the same `priv_fn` and `priv_field` errors, and `cargo test --test store` ran the test alone and it passed.
- A feature should be additive, meaning that turning it on only adds something. A feature that removes or changes behaviour surprises the people who depend on you.

## Exercise

1. Add a `pub(crate) fn` to `store.rs`, call it from `item.rs`, and then try to call it from `main.rs`. Read the error.
2. Move the `price` module from `lib.rs` to `src/price.rs` and `src/price/tax.rs`.
3. Add a third member to the workspace that depends on `greeter`, and run it with `cargo run -p`.

## What's next

Now that the code is tidy and split, the next question is how to write code that works for many types without rewriting it for each one. That is why the next step is "Generics and traits in Rust".
