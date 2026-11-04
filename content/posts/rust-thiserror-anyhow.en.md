+++
date = '2027-01-27T10:00:00+03:30'
draft = false
title = 'Errors in real apps: thiserror and anyhow'
description = 'Rust thiserror and anyhow: cut error boilerplate, report errors with context chains, downcast them and map typed errors to HTTP status codes.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "errors", "thiserror", "anyhow", "backend"]
cover = { image = "/images/covers/rust-thiserror-anyhow.png", alt = "Errors in real apps: thiserror and anyhow", hiddenInSingle = true }
+++

A request to your service fails, and the log says only this: `invalid digit found in string`. Which request? Which file was being read? What was the program trying to do? The error is correct, and it is useless. A good error message answers "what was happening when this went wrong", and it has to keep the original cause too, so that code can still look at it.

There are two readers for an error, and they want different things. Some code wants to *decide*: if the order is missing, answer `404`; if the database is down, retry. That code needs errors it can tell apart, so it needs a type it can `match` on. A human, or a log line, wants to *understand*: a chain of messages from the top ("start server") down to the root cause. In [Databases with SQLx in Rust](/posts/rust-database-sqlx/) the errors came from the database: connection failures, missing rows, constraint violations. Back in [error handling with Result](/posts/rust-error-handling-result/) we wrote the `Display`, `Error` and `From` implementations for our error types by hand. That is fine for learning, but it is a lot of boilerplate. Two crates cover the two readers: **thiserror** removes the boilerplate for error types you define, and **anyhow** is a catch-all error with context for code that only needs to report. Go has its own answer, sentinel errors and `%w` wrapping, covered in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).

> I used Rust 1.90, thiserror 2.0.21 and anyhow 1.0.104. Everything below was compiled and run again for this version of the post as a local example with eight small programs, and the outputs are copied from the runs. The demo writes its sample files in `/tmp`, so you will see those paths in the output.

## thiserror: the same enum, less code

Here is the `DivideError` from the earlier post. Compared with the manual version, the `Display` implementation, the `Error` implementation and `source()` are all gone, and the derive writes them from the attributes:

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

`#[error("...")]` generates `Display`, and the message can use the fields of the variant. `#[source]` marks the field that `source()` returns, which is how the original error stays reachable. (A field named `source` is picked up automatically; I wrote the attribute to be explicit.) The demo divides four pairs of strings: `84/2`, `1/0`, `abc/2` and ` x1/3`, and prints the error, its source and whether it is `DivideByZero`. The behavior is identical to the hand-written version:

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

The first case is a normal result. In the others, the error's own message is on the `error:` line, `source()` gives the underlying `ParseIntError` (the `caused by:` line), and the program can still ask "is this the divide-by-zero kind?" with a pattern match. That last part is why a typed error is worth having.

Two more attributes cover the rest of the boilerplate. `#[from]` generates the `From` implementation, so `?` converts the error for you. `#[error(transparent)]` says "this variant adds nothing of its own": both the message and `source()` come from the inner error.

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

`read_port` reads a file and parses its content as a port number. The demo calls it on three files: one containing `8080`, one containing `80x`, and one that does not exist:

```text
port = 8080
error: config: invalid digit found in string
error: No such file or directory (os error 2)
```

The first file works. The second fails in `parse()`, which `?` converted into `BadNumber`, so the message starts with our `config:` prefix. The third fails in `read_to_string`, converted into `Io`; because that variant is `transparent`, the message is the operating system's own text, without any prefix.

## Libraries and applications

Here is the rule I follow. A **library** exposes typed errors, because its callers may want to `match` on them, as we just did with `DivideByZero`. An **application** (the program at the top, with `main`) mostly *reports* errors: it logs them, prints them or turns them into a `500`. For that, `anyhow::Result<T>` is enough. It is a single error type that can hold any error type that implements `std::error::Error` (and is safe to send between threads, which ordinary error types are), and `?` converts into it automatically. In short: `thiserror` for the types you design, `anyhow` for the glue where you only pass errors along.

## Context chains

The problem from the opening was a message that says *what* failed but not *what we were doing*. `anyhow::Context` fixes that: it adds a message to an error as the error travels up. `.context("...")` takes a ready-made message, and `.with_context(|| ...)` takes a closure that builds the message, so the string is only created when there really is an error:

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

Here `run` calls `load`, which calls `read_port` on the file that contains `80x`. Each layer adds one sentence. The demo prints the same error in three ways and then walks the chain:

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
--- chain()
0: start server
1: load config /tmp/port_bad.txt
2: config: invalid digit found in string
3: invalid digit found in string
```

- `{}` shows only the outermost message. If your log line uses this, you lose the reason.
- `{:#}` joins the whole chain on one line, separated by colons. This is a good choice for logs.
- `{:?}` prints the first message, then a numbered `Caused by:` list. This is the nicest for a terminal.
- `err.chain()` gives you the layers as an iterator, in case you want to format them yourself.

Look at the repeated "invalid digit found in string" at the end of the `{:#}` line, and at layers 1 and 2 in the `{:?}` list. It comes from my own `BadNumber` variant: it prints its source inside its own message (`config: {0}`) *and* exposes the same error as its `source()`. So the text appears twice. Pick one of the two, either the source in the message or `source()`.

## anyhow!, bail! and ensure!

Sometimes there is no underlying error and you just want to create one. Three macros do it:

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

The demo calls it with `(80, "example.com")`, `(-1, "a")`, `(80, "")` and `(80, "forbidden")`:

```text
ok
error: port must be positive, got -1
error: host is empty
error: host forbidden is not allowed
```

`anyhow!` builds an error from a message, `bail!` is shorthand for `return Err(anyhow!(...))`, and `ensure!` is a condition check followed by `bail!`. Each of the three failing cases above uses one of the three.

## Downcasting: getting the type back

An `anyhow::Error` hides the concrete error type. But if some code really needs to know "was this a divide-by-zero?", it can ask, and the answer works even through added context:

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

`downcast_ref::<T>()` returns `Some` when the error, somewhere in the chain, is a `T`. It is the Rust counterpart of `errors.As` in Go. The `is::<T>()` method answers yes or no, and there is an owned `downcast` too (the demo prints `downcast (owned): DivideByZero`). Use this sparingly: if you downcast a lot, a typed enum would serve you better.

## main returning a Result

`main` can return `anyhow::Result`, which is the lazy and good way to end an application:

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

The program prints the error with `{:?}`, so you get the `Caused by:` list for free (returning a plain `Box<dyn Error>` from `main` does not print such a chain), and the exit code is 1, which I checked. Backtraces are controlled by environment variables. With none set, nothing extra is printed. With `RUST_BACKTRACE=1` the output gains a `Stack backtrace:` section; `RUST_LIB_BACKTRACE=1` alone does the same; and `RUST_LIB_BACKTRACE=0 RUST_BACKTRACE=1` printed none, because the library variable wins. (I did not paste the backtrace itself: it is long and its frames differ between builds.)

## One place to map errors to status codes

This is the Rust version of the `statusOf` function from the Go post. The typed error is matched in one place: the client gets fixed text, and the full chain goes to the log.

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

This combines both crates: `ServiceError` is a typed enum for the cases we decide on, and `Other(#[from] anyhow::Error)` is the catch-all for everything unexpected. The demo makes one error of each kind and prints the status, the message for the client, and what would go to the log:

```text
404 not found   (log: order 42 not found)
422 invalid qty: must be > 0   (log: invalid qty: must be > 0)
500 internal error   (log: dial tcp 10.0.0.5:5432: connection refused)
```

The client of the `500` never learns about the database address; only the log has it. The `422` is the one case where the message for the client and the log are the same, because it was written for the client.

## Common error-reporting mistakes

- **Do not put `anyhow::Error` in the public API of a library.** Callers cannot `match` on it; they can only downcast.
- **`{}` hides the causes.** Log with `{:#}` or `{:?}`, or you will lose the reason.
- **Never send `err.to_string()` of an unknown error to the client,** as the status mapping above avoids. It may contain addresses, queries or file paths.
- **A message that includes its source and also exposes it as `source()` prints it twice** in `{:#}`, as we saw.
- **Prefer `with_context` with a closure** when building the message costs something, so the string is not built on the success path.

## Exercise

1. Add a `Forbidden` variant to `ServiceError` and map it to 403.
2. In `chain`, add a third `.context(...)` layer and compare `{:#}` with `{:?}`.
3. Write a function that takes an `anyhow::Error` and returns 404 if it contains `AppError::NotFound`, using `downcast_ref`.

## What's next

Errors matter most where messages can fail and be redelivered. The next post, *An async NATS JetStream client in Rust*, puts these errors to work: its worker uses a small `thiserror` enum to decide whether a failed message is redelivered or dropped.
