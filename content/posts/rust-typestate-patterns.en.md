+++
date = '2027-03-06T10:00:00+03:30'
draft = false
title = 'The type-state pattern and API design in Rust'
description = 'Rust type-state pattern: newtypes, a PhantomData builder, consuming transitions, sealed traits, non_exhaustive and must_use, with real compiler errors.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "typestate", "api-design", "advanced"]
cover = { image = "/images/covers/rust-typestate-patterns.png", alt = "The type-state pattern and API design in Rust", hiddenInSingle = true }
+++

The previous topic was tracing. This post is about something that happens before any log line: designing APIs so the bug cannot be written at all. The idea is called "make invalid states unrepresentable". We already have the tools: [structs and enums](/posts/rust-structs-enums-pattern-matching/), [generics and traits](/posts/rust-generics-traits/), and above all [ownership](/posts/rust-ownership/), because a `self`-consuming method is a move, and a move is what makes type-state work. Everything below was run with Rust 1.90 (edition 2024) in a small workspace: one `api` library crate, one `app` binary, and a `fails` crate with one tiny binary per compile error, so every error is reproducible.

## Newtypes and validated constructors

A `u64` user id and a `u64` order id are the same type to the compiler. A **newtype** is a one-field tuple struct that fixes that:

```rust
pub struct UserId(pub u64);
pub struct OrderId(pub u64);

pub struct Email(String); // field is private

impl Email {
    pub fn parse(s: &str) -> Result<Email, String> {
        match s.split_once('@') {
            Some((u, d)) if !u.is_empty() && d.contains('.') => Ok(Email(s.to_string())),
            _ => Err(format!("invalid email: {s}")),
        }
    }
}
```

Because the field is private, the only way to get an `Email` is `parse`, so every `Email` in the program is valid. `Email::parse("roham@example.com")` gave `Ok`, and `Email::parse("nope")` gave `Err("invalid email: nope")`. `size_of::<UserId>()` is 8, the same as `u64`. Passing an `OrderId` where a `UserId` is expected:

```text
error[E0308]: mismatched types
 --> fails/src/bin/newtype.rs:9:30
9 |     println!("{}", load_user(order));
  |                    --------- ^^^^^ expected `UserId`, found `OrderId`
```

## The builder and its weakness

The classic builder keeps fields in `Option` and checks in `build()`:

```rust
pub fn build(self) -> Result<Request, String> {
    let url = self.url.ok_or("url is required")?;
    Ok(Request { url, timeout_ms: self.timeout_ms.unwrap_or(1000) })
}
```

Running it without a url gives `Err("url is required")`. It works, but the mistake is found at runtime, maybe in production. The compiler knows which methods we called, so let it check.

## A type-state builder

Put the state in a type parameter. `PhantomData<S>` lets the struct "use" `S` without storing anything:

```rust
pub struct NoUrl;
pub struct HasUrl;

pub struct RequestBuilder<S> { url: Option<String>, timeout_ms: u64, _state: PhantomData<S> }

impl RequestBuilder<NoUrl> {
    pub fn new() -> Self { /* ... */ }
    pub fn url(self, u: impl Into<String>) -> RequestBuilder<HasUrl> { /* ... */ }
}
impl<S> RequestBuilder<S> {
    pub fn timeout_ms(mut self, t: u64) -> Self { self.timeout_ms = t; self }
}
impl RequestBuilder<HasUrl> {
    pub fn build(self) -> Request { /* ... */ }
}
```

`RequestBuilder::new().timeout_ms(50).url("http://x").build()` compiles and prints `Request { url: "http://x", timeout_ms: 50 }`. `build` has no `Result` anymore. Calling it too early:

```text
error[E0599]: no method named `build` found for struct `RequestBuilder<NoUrl>` in the current scope
  = note: the method was found for
          - `RequestBuilder<HasUrl>`
```

And since `build(self)` consumes the builder, reusing it fails, with ownership doing the work:

```text
error[E0382]: use of moved value: `b`
5 |     let first = b.build();
  |                   ------- `b` moved due to this method call
6 |     let second = b.build();
  |                  ^ value used here after move
```

## A state machine

Same trick for a lifecycle: `Order<Draft>`, `Order<Paid>`, `Order<Shipped>`. Each transition takes `self` and returns the next state, so the old state is gone.

```rust
impl Order<Draft> { pub fn pay(self) -> Order<Paid> { /* ... */ } }
impl Order<Paid>  { pub fn ship(self) -> Order<Shipped> { /* ... */ } }
```

`Order::new(OrderId(42)).add("book").add("pen").pay().ship().tracking()` printed `TRK-42`. Shipping a draft:

```text
error[E0599]: no method named `ship` found for struct `Order<api::Draft>` in the current scope
  = note: the method was found for
          - `Order<api::Paid>`
```

It costs nothing at runtime: the sizes printed were `draft=32 paid=32 shipped=32 PhantomData<Draft>=0`. The marker is zero-sized, so the three states have identical layout.

## When the state is decided at runtime

A status read from a database is not known at compile time. The usual answer is an enum that wraps the typed states, and one `match` at the boundary:

```rust
pub enum AnyOrder { Draft(Order<Draft>), Paid(Order<Paid>), Shipped(Order<Shipped>) }
```

`AnyOrder::from_db(1, "paid")` built a paid order, and `advance()` moved it to shipped. Inside each arm you are back in typed code. Be aware of the limits: every extra axis of state multiplies the types (two independent flags give four combinations), error messages mention generic types, and for a handful of states a plain enum field is often simpler. Use type-state when the order of calls is a real invariant.

## Other API-design tools

**Sealed traits** stop outside crates from implementing your trait. A public trait requires a supertrait in a private module:

```rust
mod private { pub trait Sealed {} }
pub trait Currency: private::Sealed { fn code(&self) -> &'static str; }
```

From another crate, `impl Currency for Btc` fails:

```text
error[E0277]: the trait bound `Btc: api::private::Sealed` is not satisfied
  = note: `Currency` is a "sealed trait", because to implement it you also need to implement `api::private::Sealed`, which is not accessible
```

**`#[non_exhaustive]`** lets you add variants and fields later without a breaking change. From another crate:

```text
error[E0004]: non-exhaustive patterns: `_` not covered
  = note: `Event` is marked as non-exhaustive, so a wildcard `_` is necessary to match exhaustively
error[E0639]: cannot create non-exhaustive struct using struct expression
```

**`#[must_use]`** turns a forgotten result into a warning: `warning: unused return value of `with_tax` that must be used`, plus the message we attached.

Two smaller habits. Take `impl Into<String>` or `impl AsRef<str>` so callers pass `&str` and `String` alike (`greet("a")` and `greet(String::from("b"))` both worked). And derive or implement `Default`, then use struct update syntax: `Options { retries: 5, ..Default::default() }` printed `Options { timeout_ms: 1000, retries: 5, verbose: false }`.

## A few things to watch

- Type-state only protects callers who use the typed API; a `pub` field or a public constructor can bypass it.
- Keep the marker fields private and the marker types unit structs.
- If a transition can fail, return `Result<Order<Paid>, Error>`; otherwise the caller loses the old value.
- Adding `#[non_exhaustive]` to an existing type is itself a breaking change for downstream code.
- Do not use type-state when a runtime check with a clear error is enough.

## Compared with Go

Go has no type-state in practice. The usual tools are `NewX` constructors, where required values are parameters, and the functional options pattern (`type Option func(*Server)`) for optional ones. A missing required value is avoided by putting it in the constructor signature, but nothing stops you from calling a method in the wrong order; that becomes a runtime error.

## Exercise

1. Add a `Cancelled` state reachable only from `Draft`, and check that `Order<Shipped>` has no `cancel`.
2. Make `Email` implement `AsRef<str>` and pass it to `greet`.

## What's next

Next: Docker, CI and releasing a Rust service.
