+++
date = '2027-01-05T10:00:00+03:30'
draft = false
title = 'Testing and documentation in Rust'
description = 'Rust testing and docs: unit, integration and doc tests, assert macros and failure output, should_panic, ignore, test filters and cargo doc.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "testing", "documentation", "intermediate"]
cover = { image = "/images/covers/rust-testing-docs.png", alt = "Testing and documentation in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-smart-pointers/) we looked at smart pointers. Now a topic every real project needs: tests and docs. Rust has both built in, and they are closer than in most languages, because the examples in your documentation are compiled and run as tests. If you read the [Go testing post](/posts/go-testing-basics/), you will recognize the workflow, with some differences I point out at the end.

We test a small library crate called `textkit` with three functions: `slugify` (title to URL slug), `format_cents` (`123456` to `1,234.56`) and `parse_cents` (`"12.34"` to `1234`, returning a `Result`).

> I ran everything with Rust 1.90 (edition 2024). Outputs are copied from real runs.

## Layout

The crate is a library plus a `tests/` directory:

```text
textkit/
├── Cargo.toml
├── src/
│   └── lib.rs
└── tests/
    └── public_api.rs
```

## Unit tests

Unit tests live in the same file as the code, in a module marked `#[cfg(test)]`. That module is compiled only for `cargo test`. Because it is a child module, `use super::*` gives it access to everything in the parent, private items included.

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slugify_basic() {
        assert_eq!(slugify("Hello, World!"), "hello-world");
    }

    #[test]
    fn format_cents_table() {
        let cases = [(0, "0.00"), (5, "0.05"), (123456, "1,234.56"), (-250000, "-2,500.00")];
        for (input, want) in cases {
            assert_eq!(format_cents(input), want, "input = {input}");
        }
    }
}
```

`assert!` checks a boolean, `assert_eq!` and `assert_ne!` compare two values (they need `Debug` and `PartialEq`). Each takes an optional format string, which the second test uses, so a failing row tells you which input broke. A plain loop over an array of cases is the usual Rust version of a table-driven test.

## What a failure looks like

I broke things on purpose in a separate crate, `broken/`, in the demo directory. A naive `slugify` that does not strip punctuation:

```text
---- tests::eq_fails stdout ----

thread 'tests::eq_fails' panicked at src/lib.rs:20:9:
assertion `left == right` failed: slug of a title with punctuation
  left: "hello,-world!"
 right: "hello-world"
```

`left` is the first argument, `right` the second, and your message follows the colon. `assert_ne!(double(2), 4)` fails with ``assertion `left != right` failed`` and both sides printed as `4`. A test fails when it panics, so any panic counts.

## should_panic, Result and ignore

To test that code panics, add `#[should_panic]`. With `expected` the test passes only if the panic message contains that substring:

```rust
#[test]
#[should_panic(expected = "invalid amount")]
fn unwrap_bad_amount_panics() {
    parse_cents("x").map_err(|e| e.to_string()).expect("invalid amount");
}
```

If the message differs, you get `panic did not contain expected string`, with the real and expected messages. A test can also return `Result<(), E>`, so you can use `?` inside it. An `Err` fails the test and prints the error with `Debug`, e.g. `Error: ParseIntError { kind: InvalidDigit }`:

```rust
#[test]
fn parse_cents_ok() -> Result<(), ParseError> {
    assert_eq!(parse_cents("12.34")?, 1234);
    Ok(())
}
```

`#[ignore = "reason"]` skips a slow test by default. It shows as `ignored, slow in real life`, and `cargo test -- --ignored` runs only ignored tests.

## Running subsets and seeing output

Everything after a bare `--` goes to the test binary. A word before it filters test names by substring:

```text
$ cargo test slugify
running 3 tests
test tests::slugify_empty_is_empty ... ok
test tests::slugify_basic ... ok
test tests::slugify_collapses_separators ... ok
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 6 filtered out
```

Output of passing tests is captured and hidden. `cargo test --lib prints -- --nocapture` shows it (`slug = print-me`). Tests run on several threads; `-- --test-threads=1` runs them in order, which helps when they share a file or global state.

## Integration tests

Files in `tests/` are separate crates that link your library as an outside user would, so they can use only the public API:

```rust
use textkit::{format_cents, parse_cents};

#[test]
fn round_trip() {
    let cents = parse_cents("1234.50").unwrap();
    assert_eq!(format_cents(cents), "1,234.50");
}
```

Each file there becomes its own test binary. This only works for a library crate, which is why `textkit` has a `lib.rs`.

## Doc comments and doc tests

`///` documents the item below it; `//!` documents the enclosing item, usually the crate at the top of `lib.rs`. Markdown works, and every code block is compiled and run as a test:

```rust
/// Parses `"12.34"` into `1234` cents.
///
/// ```
/// use textkit::{parse_cents, ParseError};
///
/// assert_eq!(parse_cents("12.34"), Ok(1234));
/// assert_eq!(parse_cents(""), Err(ParseError::Empty));
/// ```
pub fn parse_cents(s: &str) -> Result<i64, ParseError> { /* ... */ }
```

Here is the full `cargo test` summary: three groups (unit, integration, doc), each with its own result line.

```text
Running unittests src/lib.rs
test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
Running tests/public_api.rs
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
Doc-tests textkit
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

A stale example fails the build. In `broken/` I wrote `assert_eq!(textkit_broken::double(2), 5)` in a doc comment:

```text
test src/lib.rs - double (line 3) ... FAILED
thread 'main' panicked at .../doctest_bundle_2024.rs:6:1:
assertion `left == right` failed
  left: 4
 right: 5
```

`cargo doc --no-deps` builds HTML documentation. I confirmed it generated `target/doc/textkit/index.html`, plus a page per item such as `fn.slugify.html`. `cargo doc --open` also opens it.

## Compared to Go

In both languages tests are part of the toolchain. In Go they live in `_test.go` files next to the code; in Rust unit tests sit in the same file under `#[cfg(test)]`, and integration tests go in `tests/`. Go has `Example` functions checked against their output; Rust runs the code blocks of doc comments.

## A few things to watch

- Integration tests cannot see private functions. Test those in the unit module.
- Output of passing tests is hidden unless you pass `--nocapture`.
- A failing unit test stops `cargo test` before doc tests run. Use `cargo test --doc` to run them alone.
- Tests run in parallel, so shared files or environment variables can make them flaky.
- `should_panic` without `expected` passes on any panic, even an unrelated one.

## Exercise

1. Add a test that `slugify("Ünï")` returns what you expect and decide if that is the behavior you want (the function keeps ASCII only).
2. Add a doc test for `ParseError` that shows its `Display` output.
3. Add an integration test that parsing `"1.234"` returns an `Err`.

## What's next

In the next post we get to concurrency with threads in Rust: spawning threads, moving data into them, and sharing state safely.
