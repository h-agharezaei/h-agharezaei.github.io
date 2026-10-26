+++
title = "Ownership"
summary = "Rust's rule that every value has exactly one owner, and is dropped when the owner goes out of scope."
category = "Rust"
related = ["borrowing", "lifetime"]
posts = ["rust-ownership"]
+++

Assigning or passing a non-`Copy` value *moves* it; the old binding can no longer be used. This lets Rust free memory deterministically with no garbage collector and rule out double frees at compile time. To use a value without taking it, use [borrowing](/glossary/borrowing/).

```rust
let a = String::from("hi");
let b = a; // a is moved
// println!("{a}"); // compile error
```
