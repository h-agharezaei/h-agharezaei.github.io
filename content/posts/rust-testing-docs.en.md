+++
date = '2027-01-05T10:00:00+03:30'
draft = false
title = 'Testing and documentation in Rust'
description = 'Rust testing and docs: unit, integration and doc tests, assert macros and failure output, should_panic, ignore, test filters and cargo doc.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "testing", "documentation", "intermediate"]
cover = { image = "/images/covers/rust-testing-docs.png", alt = "Testing and documentation in Rust", hiddenInSingle = true }
+++

You change one line in a function that formats money, and a week later a customer sees `1,23.45` instead of `123.45`. A test is how you catch that on the same day: a small function that calls your code with a known input and checks that the answer is what you expect. In Rust you do not need to install a framework for this. The test runner is part of `cargo`, and the examples you write in your documentation are run as tests too, so a documentation example that no longer matches the code fails the build like any other test.

This post follows [smart pointers](/posts/rust-smart-pointers/) and covers tests and documentation, which Rust has built in. If you read the [Go testing post](/posts/go-testing-basics/), you will recognize the workflow, and I point out the differences near the end.

We test a small library crate called `textkit` with three functions: `slugify` (turns a title into a URL slug, `"Hello, World!"` becomes `hello-world`), `format_cents` (`123456` becomes `1,234.56`) and `parse_cents` (`"12.34"` becomes `1234`, and returns a `Result` because the input can be bad).

> I ran everything with Rust 1.90 (edition 2024), the same version as the original run. Outputs are copied from real runs of the demo. I replaced the temporary directory in one panic message with `<tmp>` and removed the "For more information..." lines. In the failure examples I show the messages I care about and cut the rest.

## The layout

A library crate with a `tests/` directory next to `src/`:

```text
textkit/
├── Cargo.toml
├── src/
│   └── lib.rs
└── tests/
    └── public_api.rs
```

`src/lib.rs` holds the three functions, their documentation and the unit tests. `tests/public_api.rs` holds tests that use the library from the outside. Both kinds run with one command, `cargo test`.

## Unit tests: next to the code

A test is an ordinary function with the attribute `#[test]` above it. An **attribute** is a label that tells the compiler something about the item under it. `cargo test` finds every function with this label and runs it. A test passes if it finishes normally and fails if it **panics**. A panic is Rust's way of stopping with an error message, and the `assert` macros panic when their check fails.

{{< term "unit-test" "Unit tests" >}} live in the same file as the code, in a module marked `#[cfg(test)]`. The mark means: compile this module only when running `cargo test`, so it does not make your real program bigger. Since the module is a child of the file's main module, `use super::*` gives it access to everything above it, private functions included.

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

(The real demo has two more rows in `format_cents_table`; I cut them here.)

`assert!` checks that a condition is true. `assert_eq!(a, b)` checks that two values are equal and `assert_ne!(a, b)` that they differ; both need the values to support `==` and `Debug` printing. Each of them takes an optional message with format arguments after the values. The second test uses that, so if one row fails the message tells you which input broke. A plain loop over an array of `(input, expected)` pairs is the usual Rust version of a table-driven test.

Here is how the whole run looks, so you can read it once. This is the part of `cargo test` for the unit tests of the full demo (it has nine tests):

```text
running 9 tests
test tests::big_loop ... ignored, slow in real life
test tests::format_cents_table ... ok
test tests::parse_cents_errors ... ok
test tests::parse_cents_ok ... ok
test tests::slugify_collapses_separators ... ok
test tests::slugify_empty_is_empty ... ok
test tests::prints_something ... ok
test tests::slugify_basic ... ok
test tests::unwrap_bad_amount_panics - should panic ... ok

test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
```

Each line is one test: its path (`tests::` is the module, then the function name) and `ok`. The last line is the summary: 8 passed, 1 ignored (I explain `ignore` below). Tests run in parallel on several threads, and the lines appear in the order they finish, so the order can be different on every run (in the run shown, `prints_something` finished before `slugify_basic`).

## What a failure looks like

A passing test teaches you nothing about the messages, so I broke things on purpose in a separate crate, `broken/`, in the demo directory. Its `slugify` is a naive version that only lowercases and replaces spaces, so it does not strip punctuation. Here is the message for the test that compares the slug of `"Hello, World!"`:

```text
---- tests::eq_fails stdout ----

thread 'tests::eq_fails' panicked at src/lib.rs:20:9:
assertion `left == right` failed: slug of a title with punctuation
  left: "hello,-world!"
 right: "hello-world"
```

The header says which test failed and where the panic happened (file, line, column). Then comes the assertion: `left` is the first argument, `right` is the second, and your own message follows the colon. We got `hello,-world!` where we wanted `hello-world`, which is exactly the bug.

The other assertions fail in the same style. `assert_ne!(double(2), 4)` fails with ``assertion `left != right` failed`` and prints `4` on both sides. And a plain `assert!` has no left and right, so I gave it my own message built from the real value:

```text
thread 'tests::plain_fails' panicked at src/lib.rs:30:9:
slug was "a-b"
```

The general rule is: a test fails when it panics, so any panic counts, whether it came from an `assert` or from an `unwrap` on an `Err`.

## should_panic, Result and ignore

Sometimes the correct behaviour is to panic. To test that, add `#[should_panic]`. The test then passes only if the code panics. With `expected` it passes only if the panic message contains that text:

```rust
#[test]
#[should_panic(expected = "invalid amount")]
fn unwrap_bad_amount_panics() {
    parse_cents("x").map_err(|e| e.to_string()).expect("invalid amount");
}
```

What if the code panics with a different message? In the `broken` crate a test expects the text `overflow` but the code panics with `something else`:

```text
thread 'tests::wrong_panic_message' panicked at src/lib.rs:36:9:
something else
note: panic did not contain expected string
      panic message: "something else"
 expected substring: "overflow"
```

The test fails, and the note shows both the real message and what you expected.

A test can also return `Result<(), E>`, which lets you use `?` inside it instead of unwrapping everything:

```rust
#[test]
fn parse_cents_ok() -> Result<(), ParseError> {
    assert_eq!(parse_cents("12.34")?, 1234);
    assert_eq!(parse_cents("7")?, 700);
    assert_eq!(parse_cents("7.5")?, 750);
    Ok(())
}
```

If one of the `?` returns an `Err`, the test fails and the error is printed with `Debug`. In the `broken` crate a test parses `"x"` as an integer with `?`, and the output is:

```text
---- tests::result_fails stdout ----
Error: ParseIntError { kind: InvalidDigit }
```

Finally, `#[ignore = "reason"]` skips a test by default, which is useful for a slow one. It appears as `ignored, slow in real life` (see the list above), and `cargo test -- --ignored` runs only the ignored tests. I ran that for `big_loop` and it passed.

## Running a subset and seeing output

Everything after a bare `--` goes to the test program itself, not to cargo. A word before it filters tests by name, keeping those whose name contains it:

```text
$ cargo test slugify
running 3 tests
test tests::slugify_basic ... ok
test tests::slugify_collapses_separators ... ok
test tests::slugify_empty_is_empty ... ok
test result: ok. 3 passed; 0 failed; 0 ignored; 0 measured; 6 filtered out
```

Only the three tests with `slugify` in their name ran, and the summary says six were filtered out. (The filter applies to the integration tests too: in the real run their group printed `0 passed ... 2 filtered out`. In my run no doc-test group was printed at all for this command; to run the one matching doc example you use `cargo test --doc slugify`. I show only the first group here.)

The output of passing tests is captured and hidden. `cargo test --lib prints -- --nocapture` shows it; the test `prints_something` then prints `slug = print-me`. And since tests run in parallel, `-- --test-threads=1` runs them one at a time, in order. That helps when tests share a file or some global state.

## Integration tests: using the library from outside

Files in the `tests/` directory are different. Each one is compiled as a separate crate that uses your library the way an outside user would, so a {{< term "rust-integration-test" "integration test" >}} can call only the public API:

```rust
use textkit::{format_cents, parse_cents};

#[test]
fn round_trip() {
    let cents = parse_cents("1234.50").unwrap();
    assert_eq!(format_cents(cents), "1,234.50");
}
```

This one parses a string to cents and formats it back, which is a natural check that the two functions agree. Each file in `tests/` becomes its own test program with its own result line. This works only for a library crate, which is why `textkit` has a `lib.rs`: a binary crate with only `main.rs` cannot be imported by another crate.

## Doc comments and doc tests

Rust has two comment forms for documentation. `///` documents the item right below it, and `//!` documents the item that contains it, usually the whole crate at the top of `lib.rs`. The text is Markdown, and here is the part I like: every code block in it is compiled and run as a test, called a {{< term "doc-test" "doc test" >}}.

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

The example in the documentation is real code that readers can copy, and the compiler checks that it still works. Here is the complete `cargo test` summary: three groups (unit, integration, doc), each with its own result line:

```text
Running unittests src/lib.rs
test result: ok. 8 passed; 0 failed; 1 ignored; 0 measured; 0 filtered out
Running tests/public_api.rs
test result: ok. 2 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
Doc-tests textkit
test result: ok. 4 passed; 0 failed; 0 ignored; 0 measured; 0 filtered out
```

The four doc tests are the examples on `slugify`, `format_cents` and `parse_cents`, and the one at the top of the crate.

What happens when an example goes stale? In `broken/` I wrote a wrong example in a doc comment: `assert_eq!(textkit_broken::double(2), 5)`. Running `cargo test --doc` gives:

```text
test src/lib.rs - double (line 3) ... FAILED
thread 'main' panicked at <tmp>/doctest_bundle_2024.rs:6:1:
assertion `left == right` failed
  left: 4
 right: 5
```

It reads like any failed test, and it names the example by its file and line in the doc comment (`double (line 3)`). So documentation that lies is caught the next time you run the tests.

`cargo doc --no-deps` builds HTML documentation from these comments. I ran it and it generated `target/doc/textkit/index.html`, plus one page per item such as `fn.slugify.html`. `cargo doc --open` also opens it in the browser.

## Compared to Go

In both languages tests are part of the toolchain. In Go they live in `_test.go` files next to the code; in Rust, unit tests sit in the same file under `#[cfg(test)]`, and integration tests go in `tests/`. Go has `Example` functions whose output is checked; Rust runs the code blocks of doc comments instead.

## Things that trip people up

- **Integration tests cannot see private functions.** They use your crate as an outsider, so test private code in the unit test module.
- **Passing tests print nothing.** Output of passing tests is hidden unless you pass `-- --nocapture`.
- **A failing unit test stops `cargo test` before the later groups run.** In `broken/`, the unit tests failed and the output ended with `error: test failed, to rerun pass `--lib``, with no doc tests run at all. Use `cargo test --no-fail-fast` to run every group anyway (I checked that this runs the doc test too), or `cargo test --doc` to run the doc tests alone.
- **Tests run in parallel.** Shared files, ports or environment variables can make them {{< term "flaky-test" "flaky" >}}. Give each test its own data, or run with `--test-threads=1`.
- **`should_panic` without `expected` passes on any panic,** even an unrelated one. Add `expected`.

## Exercise

1. Add a test that `slugify("Ünï")` returns what you expect, and decide whether that is the behaviour you want (the function keeps ASCII only).
2. Add a doc test for `ParseError` that shows its `Display` output.
3. Add an integration test that parsing `"1.234"` returns an `Err`.

## What's next

So far everything has run on one thread. The next post, "Concurrency with threads in Rust", shows how the same ownership rules also prevent data races.
