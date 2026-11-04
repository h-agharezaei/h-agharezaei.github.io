+++
date = '2027-03-06T10:00:00+03:30'
draft = false
title = 'The type-state pattern and API design in Rust'
description = 'Rust type-state pattern: newtypes, a PhantomData builder, consuming transitions, sealed traits, non_exhaustive and must_use, with real compiler errors.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "typestate", "api-design", "advanced"]
cover = { image = "/images/covers/rust-typestate-patterns.png", alt = "The type-state pattern and API design in Rust", hiddenInSingle = true }
+++

An order has to be paid before it ships. Everyone on the team knows this, and still somebody will one day call `ship` on an order that is only a draft. The usual defence is an `if status != Paid { return Err(...) }` at the top of `ship`. It works, but the mistake is found when the code runs, maybe in production, maybe at night.

Here is a second, smaller version of the same problem. To the compiler, a `u64` user id and a `u64` order id are the same type, so `load_user(order_id)` compiles without complaint and loads the wrong thing.

In both cases the information the compiler needs ("this value is an order id", "this order is still a draft") is known to us, but it is not written anywhere the compiler can see. This post is about writing it down in the types, so the bug cannot be typed in the first place. The idea has a name: make invalid states unrepresentable. It comes before [any log line](/posts/rust-tracing-observability/): the best bug to debug is the one that did not compile.

We already have the tools: [structs and enums](/posts/rust-structs-enums-pattern-matching/), [generics and traits](/posts/rust-generics-traits/), and above all [ownership](/posts/rust-ownership/). A method that takes `self` by value *moves* the value, and a move is what makes the pattern we meet below, type-state, work.

> Everything below was run with Rust 1.90 (`rustc 1.90.0`, edition 2024) in a small workspace with no dependencies: an `api` library crate with all the types, an `app` binary that uses them, and a `fails` crate with one tiny binary per compile error, so every error can be reproduced on its own. I re-ran all of it for this version of the post. The compiler errors are shortened to the important lines; I also removed the `note:` lines that only pointed to a file path on my machine.

## Newtypes and validated constructors

We start with the smaller problem. A {{< term "newtype" "newtype" >}} is a struct with one field. It holds the same data as the type inside it, but the compiler sees it as a different type:

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

`UserId` and `OrderId` are now different types. `Email` goes one step further. Its field is private, so code outside the module cannot write `Email("whatever".to_string())`. The only way to get an `Email` is `parse`, and `parse` checks the string. So every `Email` anywhere in the program is already valid, and no function that receives one needs to check it again. (The check here is deliberately simple, just a toy: some text, an `@`, and a dot in the domain.)

The demo prints this:

```text
UserId(7), size 8
Ok("roham@example.com")
Err("invalid email: nope")
```

`parse` accepted the first address and rejected `nope`. And `size_of::<UserId>()` is 8, the same as a `u64`: the wrapper costs nothing at runtime, it exists only for the compiler. Now the original bug, passing an `OrderId` to a function that wants a `UserId`:

```text
error[E0308]: mismatched types
 --> fails/src/bin/newtype.rs:9:30
9 |     println!("{}", load_user(order));
  |                    --------- ^^^^^ expected `UserId`, found `OrderId`
```

## The builder and its weakness

Newtypes protect values. The next problem is about *order of calls*. A common way to build an object with many optional settings is a **builder**: you call methods one by one and finish with `build()`. The classic one keeps every field in an `Option` and checks in `build()` that the required ones were set:

```rust
pub fn build(self) -> Result<Request, String> {
    let url = self.url.ok_or("url is required")?;
    Ok(Request { url, timeout_ms: self.timeout_ms.unwrap_or(1000) })
}
```

I ran it twice. Without a url, `build()` returns `Err("url is required")`. With a url but no timeout, it returns `Ok(Request { url: "http://x", timeout_ms: 1000 })`, using the default timeout. It works. But forgetting the url is found at runtime. The compiler knows exactly which methods we called, so we should let it check.

## A type-state builder

The {{< term "type-state" "type-state" >}} pattern puts the state of the object into its type. For the builder there are two states: "no url yet" and "url set". We make them two empty marker types and give the builder a type parameter that says which state it is in. The parameter is not stored anywhere, so we need {{< term "phantom-data" "PhantomData" >}}, a field that "uses" the parameter for the compiler and takes no space:

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

Read the three `impl` blocks as three rules:

- `new` and `url` exist only on `RequestBuilder<NoUrl>`. And `url` returns a *different type*, `RequestBuilder<HasUrl>`. Setting the url is a step from one state to the next.
- `timeout_ms` is defined for every `S`, so it can be called in either state.
- `build` exists only on `RequestBuilder<HasUrl>`.

So the compiler now enforces "no `build` without a url". The call `RequestBuilder::new().timeout_ms(50).url("http://x").build()` compiles and prints `Request { url: "http://x", timeout_ms: 50 }`. Notice that `build` no longer returns a `Result`, because there is nothing left to go wrong. Calling `build` too early:

```text
error[E0599]: no method named `build` found for struct `RequestBuilder<NoUrl>` in the current scope
  = note: the method was found for
          - `RequestBuilder<HasUrl>`
```

The compiler even tells us in which state the method does exist.

Every method that changes the state takes `self`, not `&self`. That is ownership at work: `build(self)` consumes the builder, so using it a second time fails:

```text
error[E0382]: use of moved value: `b`
5 |     let first = b.build();
  |                   ------- `b` moved due to this method call
6 |     let second = b.build();
  |                  ^ value used here after move
```

## A state machine

The same trick works for a whole life cycle. An order goes through `Draft`, `Paid` and `Shipped`. We make a type for each, `Order<Draft>`, `Order<Paid>` and `Order<Shipped>`, and every transition takes `self` and returns the next state. The old state is gone, because it was moved:

```rust
impl Order<Draft> { pub fn pay(self) -> Order<Paid> { /* ... */ } }
impl Order<Paid>  { pub fn ship(self) -> Order<Shipped> { /* ... */ } }
```

(`Order<Draft>` also has `new` and `add`, and `Order<Shipped>` has `tracking`; I left them out here.) The demo builds an order and walks it through all three states: `Order::new(OrderId(42)).add("book").add("pen").pay().ship().tracking()` printed `TRK-42`. Trying to ship a draft:

```text
error[E0599]: no method named `ship` found for struct `Order<api::Draft>` in the current scope
  = note: the method was found for
          - `Order<api::Paid>`
```

This is the answer to the question we started with: `ship` simply does not exist on a draft. It costs nothing at runtime, either. The demo prints the sizes of the three states:

```text
sizes: draft=32 paid=32 shipped=32 PhantomData<Draft>=0
```

The marker is zero-sized, so the three types have exactly the same layout (a `u64` id and a `Vec`, 8 + 24 bytes), and the "state" exists only in the type checker.

## When the state is decided at runtime

There is an obvious catch. A status that you read from a database is not known when you compile. You cannot write `Order<???>`. The usual answer is an enum that wraps the typed states, and a single `match` at the boundary where the runtime value comes in:

```rust
pub enum AnyOrder { Draft(Order<Draft>), Paid(Order<Paid>), Shipped(Order<Shipped>) }
```

The demo has `AnyOrder::from_db(id, status)`, which builds the right variant from a string, and `advance()`, which moves any order to its next state. For the statuses `draft`, `paid`, `shipped` and an unknown `oops`, it printed:

```text
draft -> draft -> paid
paid -> paid -> shipped
shipped -> shipped -> shipped
oops -> unknown status
```

Each line is the status, the label of the order we built from it, and the label after `advance()`. A shipped order stays shipped, and `oops` is rejected at the boundary. Inside each arm of the `match`, you are back in fully typed code.

Be honest about the cost, though. Every extra axis of state multiplies the types (two independent flags already give four combinations). Error messages mention generic types, which are harder to read. And for a handful of states, a plain enum field is often simpler. Use type-state when the order of calls is a real rule of the domain.

## Other API-design tools

The same mindset, "let the compiler refuse", has a few more tools.

A **sealed trait** stops code outside your crate from implementing your trait. You make the public trait require a supertrait that lives in a private module, which nobody outside can name:

```rust
mod private { pub trait Sealed {} }
pub trait Currency: private::Sealed { fn code(&self) -> &'static str; }
```

Inside the crate, `Usd` and `Eur` implement both. From another crate, `impl Currency for Btc` fails:

```text
error[E0277]: the trait bound `Btc: api::private::Sealed` is not satisfied
  = note: `Currency` is a "sealed trait", because to implement it you also need to implement `api::private::Sealed`, which is not accessible
```

That is useful when you want to add methods to the trait later without breaking anyone.

`#[non_exhaustive]` on an enum or struct promises that you may add variants or fields in the future. Code in other crates must then use a wildcard arm when matching, and cannot build the struct with a struct expression. From another crate:

```text
error[E0004]: non-exhaustive patterns: `_` not covered
  = note: `Event` is marked as non-exhaustive, so a wildcard `_` is necessary to match exhaustively
error[E0639]: cannot create non-exhaustive struct using struct expression
```

`#[must_use]` turns a forgotten result into a warning. Our `with_tax` returns the new total, and calling it and ignoring the result gives ``warning: unused return value of `with_tax` that must be used``, followed by the message we attached: `the new total is returned, the original is unchanged`.

Two smaller habits help too. Take `impl Into<String>` or `impl AsRef<str>` as a parameter, so callers can pass a `&str` or a `String` (`greet("a")` and `greet(String::from("b"))` both worked and printed `hi a hi b`). And implement `Default` for option structs and use struct update syntax: `Options { retries: 5, ..Default::default() }` printed `Options { timeout_ms: 1000, retries: 5, verbose: false }`.

## Limits of type-state

- **It only protects callers who use the typed API.** A `pub` field or a public constructor that skips the transitions bypasses it.
- **Keep the marker field private and the marker types simple unit structs.** Then nobody can build an `Order<Paid>` out of thin air.
- **A transition that can fail needs to return the old value.** `pay(self)` consumes the draft. If paying can fail and the caller still needs the draft, return `Result<Order<Paid>, Error>` where the error carries the draft back; otherwise it is lost.
- **Adding `#[non_exhaustive]` to a type that already exists is itself a breaking change** for downstream code that matches on it.
- **Do not use type-state when a runtime check with a clear error is enough.** If the states come from a database most of the time, the extra types may not pay for themselves.

## Compared with Go

Go has no type-state in practice. The usual tools are `NewX` constructors, where required values are parameters, and the functional options pattern (`type Option func(*Server)`) for the optional ones. A required value is guaranteed by being in the constructor's signature, but nothing stops you from calling a method in the wrong order. That becomes a runtime error.

## Exercise

1. Add a `Cancelled` state reachable only from `Draft`, and check that `Order<Shipped>` has no `cancel`.
2. Make `Email` implement `AsRef<str>` and pass it to `greet`.

## What's next

*Docker, CI and releasing a Rust service*: a well-designed service still has to leave the laptop.
