+++
date = '2026-12-02T10:00:00+03:30'
draft = false
title = 'Error handling with Result and Option in Rust'
description = 'Rust error handling with Result and Option: unwrap vs expect, the ? operator, map and and_then, custom error types with From and main returning Result.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "errors", "result", "option"]
cover = { image = "/images/covers/rust-error-handling-result.png", alt = "Error handling with Result and Option in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-collections-strings/) we worked with `Vec`, `HashMap` and strings. Several of their methods returned an `Option`, and parsing a string returns a `Result`. This post is about those two types and how Rust code deals with failure. Like Go, Rust has no exceptions, but errors are not a second return value either: they are part of the type of the return value, so you cannot forget they exist.

> I compiled and ran everything below with Rust 1.90. Outputs and compiler messages are copied from those runs.

## Option and Result

```rust
enum Option<T> { Some(T), None }
enum Result<T, E> { Ok(T), Err(E) }
```

`Option<T>` means "a value or nothing", for example `v.first()` on an empty `Vec`. `Result<T, E>` means "a value or an error describing what went wrong", for example `"abc".parse::<i32>()`. Both are ordinary enums, and you handle them with `match`, `if let` or the helper methods below. If you ignore a `Result` without using it, the compiler warns you.

## unwrap and expect

The quickest way out is to take the value and **panic** if it is missing:

```rust
let ok: i32 = "42".parse().unwrap();
let n: i32 = "abc".parse().expect("port must be a number");
```

```text
ok = 42

thread 'main' panicked at src/bin/unwrap_panic.rs:4:32:
port must be a number: ParseIntError { kind: InvalidDigit }
```

The process exits with code 101. For an `Option`, `unwrap()` on `None` panics with ``called `Option::unwrap()` on a `None` value``. `expect` is the same but with your message, which is why I prefer it over bare `unwrap`. Use both in tests, quick experiments, and where a failure really means a bug. For input from outside the program, handle the error.

## The ? operator

Writing `match` at every step is noisy. The **`?` operator** unwraps an `Ok` and continues, or returns the `Err` from the current function immediately. It is the Rust counterpart of `if err != nil { return err }`:

```rust
fn parse_and_double(s: &str) -> Result<i32, std::num::ParseIntError> {
    let n = s.trim().parse::<i32>()?;
    Ok(n * 2)
}
```

`?` works only in a function whose return type can hold the error (`Result`, or `Option` for `Option` values). Using it in a plain `fn main()` fails to compile:

```text
error[E0277]: the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`)
 --> examples/question_in_unit_main.rs:2:30
  |
1 | fn main() {
  | --------- this function should return `Result` or `Option` to accept `?`
2 |     let n: i32 = "42".parse()?;
  |                              ^ cannot use the `?` operator in a function that returns `()`
```

## Combinators

Often you want to transform a value without unpacking it. I ran this:

```rust
let doubled = "21".parse::<i32>().map(|n| n * 2);
let r = "x".parse::<i32>().map_err(|e| format!("bad number: {e}"));
let first = empty.first().ok_or("empty list");        // Option -> Result
let r = "10".parse::<i32>().ok().and_then(|n| n.checked_div(0));
let a = "oops".parse::<i32>().unwrap_or(0);
let b = "oops".parse::<i32>().unwrap_or_else(|e| { println!("fallback because: {e}"); -1 });
```

```text
Ok(42)
Err("bad number: invalid digit found in string")
Err("empty list")
None
fallback because: invalid digit found in string
0 -1
```

`map` changes the `Ok` value, `map_err` changes the error, `ok_or` turns an `Option` into a `Result`, and `and_then` chains a step that can itself fail. `unwrap_or` gives a default value, and `unwrap_or_else` computes it only when needed.

## Your own error type and From

A real program mixes errors from different sources. Define an enum, implement `Display` and `std::error::Error`, and add a `From` impl. That last part is what lets `?` convert errors for you:

```rust
#[derive(Debug)]
enum AppError {
    Parse(ParseIntError),
    DivideByZero,
}

impl fmt::Display for AppError { /* match self and write! a message */ }
impl std::error::Error for AppError {}

impl From<ParseIntError> for AppError {
    fn from(e: ParseIntError) -> Self { AppError::Parse(e) }
}

fn divide(a: &str, b: &str) -> Result<i32, AppError> {
    let x: i32 = a.trim().parse()?; // ParseIntError becomes AppError via From
    let y: i32 = b.trim().parse()?;
    if y == 0 { return Err(AppError::DivideByZero); }
    Ok(x / y)
}
```

## main can return a Result

`main` may return `Result<(), E>` as long as `E` implements `Debug`. With `Box<dyn Error>` any error type fits:

```rust
fn main() -> Result<(), Box<dyn Error>> {
    println!("starting");
    let n: i32 = "abc".parse()?;
    println!("n = {n}");
    Ok(())
}
```

```text
starting
Error: ParseIntError { kind: InvalidDigit }
```

The error is printed to stderr with `Debug` formatting, and the exit code is 1 (I checked with `echo $?`). That is fine for a script, but not what a user should see in a real tool.

## The same task as in the Go post

In the [Go post](/posts/go-functions-defer-errors/) we parsed two numbers and divided them. Here is the Rust version, with an error that keeps the offending input and exposes the original error through `source()`:

```rust
enum DivideError {
    Parse { input: String, source: ParseIntError },
    DivideByZero,
}

fn parse(s: &str) -> Result<i32, DivideError> {
    s.trim().parse::<i32>().map_err(|e| DivideError::Parse {
        input: s.to_string(),
        source: e,
    })
}
```

`divide` calls `parse(a)?` and `parse(b)?`, then checks for zero. Running it on four inputs:

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

Checking "which error is it" is a `match` or `matches!` on the enum, instead of `errors.Is`/`errors.As`.

## Compared to Go

Both languages treat errors as values and make you deal with them near the call. In Go the error is a separate return value that you can drop with `_`, and the compiler does not complain. In Rust the `Result` is the return value, so you must unpack it (or `?` it) to get at the data, and the `Err` side is a concrete type you can `match` exhaustively. `?` replaces the repeated `if err != nil { return err }` lines. The cost is that you write the error type and `From` impls yourself, which is more upfront code.

## A few things to watch

- `unwrap` in library or server code turns bad input into a crash. Reserve it for cases that are truly impossible.
- `?` converts errors with `From`. If there is no `From` impl for that pair of types, you get a compile error, not a runtime surprise.
- `Box<dyn Error>` is convenient but erases the concrete type. For a library, a dedicated enum is friendlier to callers.
- Returning an error from `main` prints it with `Debug`, not `Display`. Handle errors in `main` yourself if you want nicer messages.
- Use `map_err` when you need to add context, like the input string in `DivideError::Parse`.

## Exercise

1. Add a `Negative` variant to `DivideError` and return it when either operand is negative.
2. Write `fn average(nums: &[f64]) -> Option<f64>` that returns `None` for an empty slice, and use `ok_or` to turn it into a `Result<f64, String>`.
3. Change `main` in the `Box<dyn Error>` example to handle the error with `match` and print it with `{}` instead of `{:?}`.

## What's next

In the next post we look at modules, crates and Cargo in Rust: how to split code across files, use external crates, and manage a project.
