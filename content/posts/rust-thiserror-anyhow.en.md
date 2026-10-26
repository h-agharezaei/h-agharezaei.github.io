+++
date = '2027-01-27T10:00:00+03:30'
draft = false
title = 'Errors in real apps: thiserror and anyhow'
description = 'Rust thiserror and anyhow: cut error boilerplate, report errors with context chains, downcast them and map typed errors to HTTP status codes.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "errors", "thiserror", "anyhow", "backend"]
cover = { image = "/images/covers/rust-thiserror-anyhow.png", alt = "Errors in real apps: thiserror and anyhow", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-database-sqlx/) the typical source of errors was the database: connection failures, missing rows, constraint violations. Back in [error handling with Result](/posts/rust-error-handling-result/) we wrote the `Display`, `Error` and `From` impls by hand. That is fine for learning, but it is a lot of boilerplate. Two crates remove it: **thiserror** for error types you define, and **anyhow** for code that only needs to report errors. Go has its own answer, sentinel errors and `%w` wrapping, covered in [config, logging and errors in Go](/posts/go-config-logging-errors/).

> Rust 1.90, thiserror 2.0.21, anyhow 1.0.104. Everything below was compiled and run as a local example; outputs are copied from the runs.

## thiserror: the same enum, less code

Here is the `DivideError` from the earlier post. Compared with the manual version, the `Display` impl, the `Error` impl and `source()` are all gone:

```rust
use std::num::ParseIntError;
use thiserror::Error;

#[derive(Debug, Error)]
pub enum DivideError {
    #[error("parse {input:?}: {source}")]
    Parse {
        input: String,
        #[source]
        source: ParseIntError,
    },
    #[error("divide by zero")]
    DivideByZero,
}
```

`#[error("...")]` generates `Display` and can use the fields. `#[source]` marks the field returned by `source()` (a field named `source` is picked up automatically, I wrote the attribute to be explicit). Running the same four inputs as before gives identical behavior:

```text
result: 42
error: divide by zero
  is DivideByZero: true
error: parse "abc": invalid digit found in string
  caused by: invalid digit found in string
  is DivideByZero: false
error: parse " x1": invalid digit found in string
  caused by: invalid digit found in string
  is DivideByZero: false
```

`#[from]` generates the `From` impl, so `?` converts for you. `#[error(transparent)]` forwards both `Display` and `source()` to the inner error:

```rust
#[derive(Debug, Error)]
pub enum AppError {
    #[error("config: {0}")]
    BadNumber(#[from] ParseIntError),
    #[error(transparent)]
    Io(#[from] std::io::Error),
    #[error("not found")]
    NotFound,
}

pub fn read_port(path: &str) -> Result<u16, AppError> {
    let text = std::fs::read_to_string(path)?; // io::Error -> AppError::Io
    let n: u16 = text.trim().parse()?;         // ParseIntError -> AppError::BadNumber
    Ok(n)
}
```

```text
port = 8080
error: config: invalid digit found in string
error: No such file or directory (os error 2)
```

## Libraries vs applications

My rule: a **library** exposes typed errors, because callers may want to `match` on them. An **application** mostly reports: log it, print it, return 500. For that, `anyhow::Result<T>` is enough. It is one error type that holds anything implementing `std::error::Error`, and `?` converts into it automatically.

## Context chains

`anyhow::Context` adds a message as the error travels up. `.with_context(|| ...)` builds the message lazily, only on failure:

```rust
fn load(path: &str) -> Result<u16> {
    let port = read_port(path).with_context(|| format!("load config {path}"))?;
    Ok(port)
}

fn run() -> Result<()> {
    load("/tmp/port_bad.txt").context("start server")?;
    Ok(())
}
```

The same error printed three ways:

```text
--- {}
start server
--- {:#}
start server: load config /tmp/port_bad.txt: config: invalid digit found in string: invalid digit found in string
--- {:?}
start server

Caused by:
    0: load config /tmp/port_bad.txt
    1: config: invalid digit found in string
    2: invalid digit found in string
```

`{}` shows only the outermost message, `{:#}` joins the whole chain on one line (good for logs), and `{:?}` gives the multi-line `Caused by:` list (good for a terminal). `err.chain()` iterates the layers. Notice the repeated "invalid digit found in string": my `BadNumber` variant prints its source in its own message and also exposes it as the source. Pick one.

## anyhow!, bail! and ensure!

```rust
fn check(port: i64, host: &str) -> Result<()> {
    ensure!(port > 0, "port must be positive, got {port}");
    if host.is_empty() {
        bail!("host is empty");
    }
    if host == "forbidden" {
        return Err(anyhow!("host {host} is not allowed"));
    }
    Ok(())
}
```

```text
ok
error: port must be positive, got -1
error: host is empty
error: host forbidden is not allowed
```

`anyhow!` builds an error, `bail!` is `return Err(anyhow!(...))`, and `ensure!` is a check plus `bail!`.

## Downcasting

An `anyhow::Error` hides the concrete type, but it can give it back, even through added context:

```rust
let err = work().unwrap_err(); // divide("1","0").context("compute ratio")
match err.downcast_ref::<DivideError>() {
    Some(DivideError::DivideByZero) => println!("downcast_ref: DivideByZero"),
    Some(other) => println!("downcast_ref: other {other}"),
    None => println!("downcast_ref: None"),
}
println!("is::<std::io::Error>: {}", err.is::<std::io::Error>());
```

```text
display: compute ratio: divide by zero
downcast_ref: DivideByZero
is::<std::io::Error>: false
```

It is the Rust counterpart of `errors.As`. `downcast` (owned) and `is` exist too.

## main and backtraces

```rust
fn main() -> Result<()> {
    println!("starting");
    let n: i32 = "abc".parse().context("read PORT")?;
    println!("n = {n}");
    Ok(())
}
```

```text
starting
Error: read PORT

Caused by:
    invalid digit found in string
```

The exit code is 1 (checked with `echo $?`). Unlike `Box<dyn Error>`, you get the `Caused by:` list for free. Backtraces: without env vars nothing extra is printed. With `RUST_BACKTRACE=1` the output gained a `Stack backtrace:` section; `RUST_LIB_BACKTRACE=1` alone did the same; `RUST_LIB_BACKTRACE=0 RUST_BACKTRACE=1` printed none.

## One place to map errors to status codes

The Rust analogue of `statusOf` in the Go post is a `match` over the typed error. Clients get fixed text, the full chain goes to the log:

```rust
#[derive(Debug, Error)]
enum ServiceError {
    #[error("order {0} not found")]
    NotFound(String),
    #[error("invalid {field}: {reason}")]
    Validation { field: &'static str, reason: String },
    #[error(transparent)]
    Other(#[from] anyhow::Error),
}

fn status_of(err: &ServiceError) -> (u16, String) {
    match err {
        ServiceError::Validation { .. } => (422, err.to_string()),
        ServiceError::NotFound(_) => (404, "not found".to_string()),
        ServiceError::Other(_) => (500, "internal error".to_string()),
    }
}
```

`Other(#[from] anyhow::Error)` catches everything unexpected.

```text
404 not found   (log: order 42 not found)
422 invalid qty: must be > 0   (log: invalid qty: must be > 0)
500 internal error   (log: dial tcp 10.0.0.5:5432: connection refused)
```

## A few things to watch

- Do not put `anyhow::Error` in the public API of a library. Callers cannot `match` on it, only downcast.
- `{}` hides the causes. Log with `{:#}` or `{:?}`, or you will lose the reason.
- Never send `err.to_string()` of an unknown error to the client, as in the status mapping above.
- A message that includes its source and also exposes it as `source()` prints twice in `{:#}`.
- `with_context` with a closure avoids building the string on the success path.

## Exercise

1. Add a `Forbidden` variant to `ServiceError` and map it to 403.
2. In `chain`, add a third `.context(...)` layer and compare `{:#}` with `{:?}`.
3. Write a function that takes an `anyhow::Error` and returns 404 if it contains `AppError::NotFound`, using `downcast_ref`.

## What's next

Next we move to the async NATS JetStream client in Rust.
