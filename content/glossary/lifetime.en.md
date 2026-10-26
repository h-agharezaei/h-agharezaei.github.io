+++
title = "Lifetime"
summary = "A compile-time annotation describing how long a reference stays valid."
category = "Rust"
related = ["ownership", "borrowing"]
posts = ["rust-lifetimes"]
+++

Lifetimes such as `'a` never change how long data lives; they only let the compiler check that a reference does not outlive what it points to. Most are inferred (elision), and you write them explicitly when a function returns a reference tied to one of several inputs.

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() > y.len() { x } else { y }
}
```
