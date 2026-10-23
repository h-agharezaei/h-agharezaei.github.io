+++
date = '2026-11-02T10:00:00+03:30'
draft = false
title = 'Types, variables and control flow in Rust'
description = 'Rust types and control flow: immutable-by-default variables, shadowing, scalar types, tuples, arrays, integer overflow, if, loop, for and match.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/rust-types-control-flow.png", alt = "Types, variables and control flow in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-getting-started/) we installed Rust, met Cargo and ran a first program. Now we need the basic vocabulary: how to declare variables, which types exist, and how to branch and loop. Coming from Go, most of it will look familiar, but a few defaults are the opposite of what you expect.

> All code below was compiled and run with Rust 1.90 (`rustc 1.90.0`). The outputs are real.

## Variables are immutable by default

In Rust `let` creates an immutable binding. Assigning to it twice is a compile error:

```rust
fn main() {
    let x = 5;
    x = 6;
    println!("{x}");
}
```

```text
error[E0384]: cannot assign twice to immutable variable `x`
 --> src/bin/immut.rs:3:5
  |
2 |     let x = 5;
  |         - first assignment to `x`
3 |     x = 6;
  |     ^^^^^ cannot assign twice to immutable variable
  |
help: consider making this binding mutable
  |
2 |     let mut x = 5;
  |         +++
```

If you really want to change it, say so with `mut`. In Go every variable is mutable; in Rust you opt in, and a reader can see at a glance what may change.

## Shadowing is not mutation

You can declare a new variable with the same name using `let` again. That is **shadowing**, and it creates a brand new variable, so it can even have a different type:

```rust
let spaces = "   ";
let spaces = spaces.len(); // a new variable, now a usize
let mut count = 0;
count += 1;                // the same variable, mutated
```

Mutation keeps the type fixed. This fails:

```rust
let mut s = "abc";
s = 5;
```

```text
error[E0308]: mismatched types
11 |     s = 5;
   |         ^ expected `&str`, found integer
```

## Scalar types, tuples and arrays

The scalar types you will use most: signed integers `i8` to `i128` and `isize`, unsigned `u8` to `u128` and `usize`, floats `f32` and `f64`, `bool`, and `char`. A `char` is a Unicode scalar value, so it is 4 bytes and can hold `'ز'`.

```rust
const MAX_POINTS: u32 = 100_000;

fn main() {
    let a = 42;           // inferred as i32
    let b: u64 = 10_000_000_000;
    let c = 2.5;          // inferred as f64
    let ch = 'ز';
    let t: (i32, f64, char) = (1, 2.5, 'x');
    let (x, y, z) = t;    // destructuring
    let arr = [10, 20, 30];
    let zeros = [0u8; 4]; // four zeros
    println!("{} {} {:?} {:?}", t.0, arr.len(), arr, zeros);
    let n: i32 = "42".parse().unwrap(); // annotation needed here
    println!("{}", n + a);
}
```

Output (trimmed):

```text
1 3 [10, 20, 30] [0, 0, 0, 0]
84
```

Notes:

- Rust infers types, and integers default to `i32`, floats to `f64`. You annotate when inference cannot decide, like `parse()` above.
- A **tuple** has a fixed length and mixed types; an **array** has a fixed length and one type. For a growable list you will use `Vec`, later.
- `const` always needs a type annotation and a value known at compile time, and it cannot be `mut`.
- There are no implicit numeric conversions. Adding an `i32` to an `i64` fails with `cannot add i64 to i32`; convert with `as` or `i64::from(a)`. Go behaves the same here.

## Integer overflow

I ran the same program with a `u8` equal to 255 and added 1:

```rust
let n: u8 = std::env::args().nth(1).unwrap().parse().unwrap();
let m = n + 1;
```

```text
$ cargo run -q --bin overflow 255
thread 'main' panicked at src/bin/overflow.rs:3:13:
attempt to add with overflow

$ cargo run -q --release --bin overflow 255
0
```

A debug build panics, a `--release` build silently wraps to 0. Because that difference is easy to trip over, say what you mean explicitly: `checked_add` returns an `Option`, `wrapping_add` wraps, `saturating_add` clamps at 255. In Go, overflow always wraps silently.

## Statements and expressions

Almost everything in Rust is an expression. A block's last expression, without a trailing semicolon, is its value:

```rust
fn square(x: i32) -> i32 {
    x * x
}
```

Add a semicolon and it becomes a statement that returns `()`:

```text
error[E0308]: mismatched types
1 | fn square(x: i32) -> i32 {
  |    ------            ^^^ expected `i32`, found `()`
2 |     x * x;
  |          - help: remove this semicolon to return this value
```

## Control flow

`if` is an expression, so it replaces Go's missing ternary. The condition must be a real `bool` (`if n {}` with an integer does not compile), and both branches must have the same type:

```rust
let kind = if n % 2 == 0 { "even" } else { "odd" };
```

`loop` runs forever until `break`, and `break` can carry a value:

```rust
let found = loop {
    tries += 1;
    if tries * tries > 50 { break tries; }
};
```

`while` is the usual condition loop. `for` iterates over anything iterable, and there is no C-style three-part `for`:

```rust
for i in 1..4 {}            // 1 2 3
for i in 1..=4 {}           // 1 2 3 4
for i in (1..4).rev() {}    // 3 2 1
for (i, name) in names.iter().enumerate() {}
```

`match` compares a value against patterns. Here is just a taste; patterns get their own post later:

```rust
let msg = match code {
    200 => "ok",
    404 => "not found",
    500..=599 => "server error",
    _ => "other",
};
```

The compiler requires `match` to be exhaustive, which is why the `_` arm is there.

## Putting it together

A small program with a temperature table and FizzBuzz:

```rust
fn main() {
    println!("   C      F");
    for c in (-10..=40).step_by(10) {
        let f = c as f64 * 9.0 / 5.0 + 32.0;
        let note = match c {
            i32::MIN..=-1 => "freezing",
            0..=24 => "mild",
            _ => "hot",
        };
        println!("{c:>4} {f:>6.1}  {note}");
    }
    for i in 1..=15 {
        let s = if i % 15 == 0 { "FizzBuzz".to_string() }
            else if i % 3 == 0 { "Fizz".to_string() }
            else if i % 5 == 0 { "Buzz".to_string() }
            else { i.to_string() };
        print!("{s} ");
    }
    println!();
}
```

```text
   C      F
 -10   14.0  freezing
   0   32.0  mild
  10   50.0  mild
  20   68.0  mild
  30   86.0  hot
  40  104.0  hot
1 2 Fizz 4 Buzz Fizz 7 8 Fizz Buzz 11 Fizz 13 14 FizzBuzz
```

## A few things to watch

- A semicolon on the last line of a function is the classic beginner error; the compiler message points straight at it.
- Debug and release builds can behave differently on overflow. Use `checked_*` where it matters.
- Array indexing is bounds-checked at runtime: `arr[5]` on a 3-element array panics with `index out of bounds: the len is 3 but the index is 5`.
- Shadowing is handy for conversions (`let x = x.trim();`), but overusing it makes code harder to follow.
- `1..4` excludes the end, `1..=4` includes it.

## Exercise

1. Write a function `fn is_leap(year: u32) -> bool` as a single expression with no `return`, and print the leap years between 1990 and 2030.
2. Use `loop` with `break value` to find the first power of 2 greater than 1000.
3. Make the overflow program print the result of `checked_add` for 250 and for 255, and compare with `wrapping_add`.

## What's next

In the next post, Ownership in Rust, we get to the idea that makes Rust different from Go: who owns a value, what a move is, and how borrowing works.
