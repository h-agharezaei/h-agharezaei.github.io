+++
date = '2026-12-02T10:00:00+03:30'
draft = false
title = 'Error handling with Result and Option in Rust'
description = 'Rust error handling with Result and Option: unwrap vs expect, the ? operator, map and and_then, custom error types with From and main returning Result.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "errors", "result", "option"]
cover = { image = "/images/covers/rust-error-handling-result.png", alt = "Error handling with Result and Option in Rust", hiddenInSingle = true }
+++

Imagine a function that takes a string like `"8080"` and returns a port number. What should it do when the input is `"abc"`? Languages have answered this differently. Some throw an exception, and you have to remember to catch it somewhere. Some return `null` or a magic number like `-1`, and you have to remember to check it. Go returns the error as a second return value, which you can ignore with `_`. Rust took another road: it puts the possibility of failure into the **type** of the returned value. If a function can fail, its return type is no longer "a number" but "a number, or an error", and you cannot get to the number until you open it.

In the [previous post](/posts/rust-collections-strings/) we met this several times: `v.get(9)` and `ages.get("nobody")` both returned an `Option`, and parsing a string into a number returns a `Result`. This post is about those two types and the tools that make them pleasant to use. If you come from Go, we compare everything with [Functions, defer and error handling in Go](/posts/go-functions-defer-errors/).

> I compiled and ran all the code below with Rust 1.90, and the outputs and compiler messages come from those runs. From the error message about the `?` operator I removed a few side lines of help and the "For more information…" line. I also wrote and ran one small extra program that only shows what `?` does by hand.

## Option and Result

Both types are defined in the standard library, and they are ordinary enums, the same kind of enum we saw in the structs and enums post:

```rust
enum Option<T> { Some(T), None }
enum Result<T, E> { Ok(T), Err(E) }
```

`Option<T>` means "either a value of type `T`, or nothing". For example `v.first()` on an empty `Vec` returns `None`. `Result<T, E>` means "either a value of type `T`, or an error of type `E` that says what went wrong". For example `"abc".parse::<i32>()` gives an `Err`. These take the place of `null` and exceptions in Rust, and because they are types, the compiler makes sure you have thought about both cases.

The simplest way to work with them is `match`:

```rust
let empty: Vec<i32> = Vec::new();
match empty.first() {
    Some(n) => println!("first = {n}"),
    None => println!("empty list"),
}
```

(I ran this in a separate small program and it printed `empty list` for the empty list.) When you care about only one case, `if let Some(n) = ...` is shorter; for `[5, 6]` that form printed `first = 5`. If you leave a `Result` unused, the compiler warns you, so ignoring an error does not happen silently.

## unwrap and expect: when failure means a bug

Sometimes you know the value must be there, or a failure at that point really means the program was written wrong. Then you do not need a `match`. `unwrap()` hands you the value inside `Ok` or `Some`, and if it finds `Err` or `None` it stops the program with a **panic**. `expect("...")` does the same with a message you write yourself:

```rust
let ok: i32 = "42".parse().unwrap();
println!("ok = {ok}");
let n: i32 = "abc".parse().expect("port must be a number");
println!("n = {n}");
```

```text
ok = 42

thread 'main' panicked at src/bin/unwrap_panic.rs:4:32:
port must be a number: ParseIntError { kind: InvalidDigit }
```

The first line is the `"42"`, which parsed fine. Then `"abc"` fails, and the program stops with our message and the original error, with exit code 101 (I ran it and checked). It is the same for `Option`: `unwrap()` on `None` panics with ``called `Option::unwrap()` on a `None` value``. I prefer `expect` to a bare `unwrap`, because when you later see the panic in a log, the message tells you what we expected. Use both in tests, quick experiments, and places where failure is truly a bug. For input that comes from outside the program, handle the error.

## The ? operator

Handling errors with a `match` at every step clutters the code. Suppose you have a function that turns a string into a number and doubles it. If the conversion fails, we want to hand that same error back to the caller. By hand it looks like this:

```rust
fn by_hand(s: &str) -> Result<i32, ParseIntError> {
    let n = match s.trim().parse::<i32>() {
        Ok(n) => n,
        Err(e) => return Err(e),
    };
    Ok(n * 2)
}
```

That means: if it is `Ok`, take the value and carry on; if it is `Err`, return from the function right there and take the error with you. This pattern is so repetitive that Rust has a symbol for it: the **`?` operator**. This does exactly the same thing:

```rust
fn with_question(s: &str) -> Result<i32, ParseIntError> {
    let n = s.trim().parse::<i32>()?;
    Ok(n * 2)
}
```

I called both functions with `"21"` and `"x"` to be sure they behave the same:

```text
Ok(42) Ok(42)
Err(ParseIntError { kind: InvalidDigit }) Err(ParseIntError { kind: InvalidDigit })
```

The first line is the result of `with_question` and `by_hand` for `"21"`, the second for `"x"`, and in both cases they agree. (In practice `?` does one more small thing: it converts the error to the function's error type with `From`, which we see a few sections later.) `?` is what you do in Go with `if err != nil { return err }`, only as a single symbol.

Because `?` means "return from the function", it works only in a function whose return type can accept that error: `Result`, or `Option` for `Option` values. If you use it in a plain `fn main()` that returns nothing:

```text
error[E0277]: the `?` operator can only be used in a function that returns `Result` or `Option` (or another type that implements `FromResidual`)
 --> examples/question_in_unit_main.rs:2:30
  |
1 | fn main() {
  | --------- this function should return `Result` or `Option` to accept `?`
2 |     let n: i32 = "42".parse()?;
  |                              ^ cannot use the `?` operator in a function that returns `()`
```

The message says exactly that: the function returns `()` and has no place for an error. (The compiler also suggests changing the return type of `main`; we do that in the section about `main`.)

## Combinators: transforming without unwrapping

You do not always want to open the value. Sometimes you only want to transform it and keep it as a `Result` or `Option`. There are several methods for this. Each line of the program below shows one:

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

(`|n| n * 2` is a small function without a name, called a closure; I say more about them in a later post.) Each line of output belongs to one line of code:

- `map` changes the value inside `Ok`: `21` is doubled and it stays `Ok(42)`.
- `map_err` changes only the error. Here we turned the parse error into text with our own message.
- `ok_or` turns an `Option` into a `Result`. The empty list gives `None`, and we turn it into `Err("empty list")`.
- `and_then` chains a step that can itself fail. Here `"10"` parses fine, but `checked_div(0)` (division that checks for zero) gives `None`, so the result is `None`.
- `unwrap_or(0)` gives a default value if it failed. `unwrap_or_else` is the same, but builds the default with a function that runs only on failure; here it failed, so the `fallback because...` message was printed and `-1` came back. The last line, `0 -1`, shows the values of `a` and `b`.

## Your own error type, and From

So far the errors came from the standard library. A real program mixes errors from several sources: parsing, files, the network. The usual way is to define an enum for your own program's errors, where each variant is one kind of failure. You also implement two {{< term "trait" "traits" >}} for it. A trait is a set of methods that a type promises to have; the generics and traits post goes deeper. For now you only need to know that `Display` says how the error turns into text and `Error` is a marker that says "this type is an error". The third one, `From`, is the interesting one: it tells Rust how to convert a `ParseIntError` into an `AppError`, and `?` uses it.

```rust
#[derive(Debug)]
enum AppError {
    Parse(ParseIntError),
    DivideByZero,
}

impl fmt::Display for AppError {
    fn fmt(&self, f: &mut fmt::Formatter) -> fmt::Result {
        match self {
            AppError::Parse(e) => write!(f, "parse error: {e}"),
            AppError::DivideByZero => write!(f, "divide by zero"),
        }
    }
}

impl std::error::Error for AppError {}

impl From<ParseIntError> for AppError {
    fn from(e: ParseIntError) -> Self {
        AppError::Parse(e)
    }
}

fn divide(a: &str, b: &str) -> Result<i32, AppError> {
    let x: i32 = a.trim().parse()?; // ParseIntError -> AppError via From
    let y: i32 = b.trim().parse()?;
    if y == 0 {
        return Err(AppError::DivideByZero);
    }
    Ok(x / y)
}
```

Notice that `divide` returns `Result<i32, AppError>` but `parse()` produces a `ParseIntError`. Without `From` this would be a compile error. With `From`, the `?` symbol converts the error from `ParseIntError` to `AppError` automatically as it returns it. The complete program makes four calls, and the last one lets its error escape from `main` with `?`:

```text
Ok(42)
Err(DivideByZero)
Err("parse error: invalid digit found in string")
Error: Parse(ParseIntError { kind: InvalidDigit })
```

The first three lines come from `println!`: a good division (`84 / 2`), a division by zero, and a bad input whose error was turned into text with `to_string()` (that is, our `Display`). The last line appears when the fourth call fails and `?` pushes the error out of `main`. That is the next section.

## main can return a Result too

`main` can return `Result<(), E>` as long as `E` implements `Debug`. If it returns `Err`, the program prints the error and exits with a non-zero code. With `Box<dyn Error>`, which means "any kind of error", every error fits:

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

After `starting` we fail, and `?` returns the error from `main`, so the `n = ...` line never runs. The error is printed on stderr in `Debug` format (which is why we see `Error: ParseIntError { kind: ... }` and not a readable sentence), and the exit code is 1 (I checked with `echo $?`). That is fine for a script, but it is not what you want to show to the user of a real tool.

## The same problem as the Go post

In the [Go post](/posts/go-functions-defer-errors/) we turned two strings into numbers and divided them. The Rust version is the same, with two differences. The error keeps the bad input inside it, and it exposes the original error through `source()` (the equivalent of the `%w` chain and `Unwrap` in Go):

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

`divide` first calls `parse(a)?` and `parse(b)?` and then checks for zero. (The `Display` and `Error` implementations are like the previous example, and the full code is in the same local example.) The run on four inputs:

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

The inputs were `("84","2")`, `("10","0")`, `("abc","2")` and `("7"," x1")`. The first gives 42. The second is `DivideByZero`, and since it has no cause, no `caused by` line is printed. The last two are parse errors: the message shows the bad input (in quotes, so the leading space of `" x1"` is visible) and the `caused by` line is the original error we got through `source()`. To find out which kind of error happened, instead of `errors.Is` and `errors.As` in Go we write a `match` or `matches!` on the enum; the last line of each block shows that.

## Comparison with Go

Both languages treat an error as a value and make you deal with it close to the call. In Go the error is a separate return value that you can throw away with `_` without the compiler objecting. In Rust the `Result` itself is the return value, so to get to the data you have to open it (or use `?`), and the `Err` side is a concrete type you can `match` on exhaustively. `?` replaces the repeated `if err != nil { return err }` lines. The cost is that you write the error type and `From` yourself, which means more initial code.

## Where error handling breaks down

- `unwrap` in a library or a server turns bad input into a crash. Keep it for cases that are truly impossible.
- `?` converts errors with `From`. If there is no `From` for that pair of types, you get a compile error, not a surprise at run time.
- `Box<dyn Error>` is convenient but hides the concrete error type, and the caller cannot `match` on it. For a library, a dedicated enum is better.
- An error returned from `main` is printed with `Debug`, not `Display`. If you want a cleaner message, handle the error yourself in `main`.
- When you want to add context, use `map_err`, like the input string we kept in `DivideError::Parse`.

## Exercise

1. Add a variant called `Negative` to `DivideError` and return it when one of the operands is negative.
2. Write `fn average(nums: &[f64]) -> Option<f64>` that returns `None` for an empty slice, and turn it into a `Result<f64, String>` with `ok_or`.
3. In the `Box<dyn Error>` example, handle the error inside `main` with a `match` and print it with `{}` instead of `{:?}`.

## What's next

As a program grows, `DivideError`, `parse` and `main` no longer fit in one file. That is why the next step is "Modules, crates and Cargo in Rust": splitting code across files and crates.
