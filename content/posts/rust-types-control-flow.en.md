+++
date = '2026-11-02T10:00:00+03:30'
draft = false
title = 'Types, variables and control flow in Rust'
description = 'Rust types and control flow: immutable-by-default variables, shadowing, scalar types, tuples, arrays, integer overflow, if, loop, for and match.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/rust-types-control-flow.png", alt = "Types, variables and control flow in Rust", hiddenInSingle = true }
+++

Take a `u8`, an integer that can only hold values from 0 to 255. Its value is 255 and you add 1. What do you get? Not 256, because it does not fit in this type. In Rust the answer depends on how you build: in debug mode the program stops with a panic, and with `--release` it silently goes back to 0. In Go, this kind of {{< term "integer-overflow" "overflow" >}} always wraps around silently.

The basic vocabulary of Rust, meaning variables, types, conditions and loops, is full of cases like this. If you come from Go, most of it looks familiar, but a few defaults are exactly the opposite of what you expect. This post walks through them one by one, and wherever the compiler objects, we read its message to learn what Rust is telling us. If you have not set up Rust and Cargo yet, start with [Getting started with Rust](/posts/rust-getting-started/).

> I compiled and ran all the code below with Rust 1.90 (`rustc 1.90.0`) and the outputs are real. I shortened some error messages only slightly, and I say so in the text where it happens.

## Variables are immutable by default

In Rust, `let` creates a variable that cannot be changed after its first value is set. Such a variable is called **immutable**. Let us see what happens if we try to change it:

```rust
fn main() {
    let x = 5;
    x = 6;
    println!("{x}");
}
```

This program does not compile. Here is the compiler's message:

```text
warning: value assigned to `x` is never read
 --> src/bin/immut.rs:2:9
  |
2 |     let x = 5;
  |         ^
  |
  = help: maybe it is overwritten before being read?
  = note: `#[warn(unused_assignments)]` on by default

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

For more information about this error, try `rustc --explain E0384`.
error: could not compile `rust-types-control-flow` (bin "immut") due to 1 previous error; 1 warning emitted
```

This is the first compiler error in this series, so let us read its structure once. The other messages have the same shape:

- At the top there is a `warning`. A warning does not stop compilation; it only says the value 5 is never read, because it is overwritten before anyone uses it. It is a side issue.
- `error[E0384]` is the main error. The code is in brackets, and the title says what is wrong: "you cannot assign twice to an immutable variable".
- The `-->` line gives the location: file, line number and column.
- Below it the compiler shows the source lines with their numbers, and marks the important parts with `-` and `^`. Here `-` marks the first assignment and `^^^^^` marks the second one, which is the problem.
- `help` suggests the fix: `let mut x`. The `+++` marks show what needs to be added.
- The last line says you can get a longer explanation of this error with `rustc --explain E0384`.

So if you really want a variable to change, you have to say so with `mut`. In Go every variable is changeable. In Rust you grant that permission yourself, and a reader can see at a glance what might change.

## Shadowing is not mutation

You may wonder how to compute a value once and then use it in a different form. One way is to declare a new variable with the same name using `let` again. This is called {{< term "shadowing" "shadowing" >}}. The old variable is not changed; a completely new variable with the same name is created, and from that point on it "covers" the name. That is why the new variable can even have a different type. The program below shows both things, shadowing and real mutation with `mut`:

```rust
fn main() {
    let spaces = "   ";
    let spaces = spaces.len(); // shadowing: new variable, new type
    println!("{spaces}");

    let mut count = 0;
    count += 1; // mutation: same variable, same type
    println!("{count}");

    let mut s = "abc";
    s = 5; // type change not allowed
}
```

The second line, `let spaces = spaces.len()`, creates a new variable that is a number, not a string. `count += 1` changes the same old variable. The difference is that mutation keeps the type fixed. The last two lines show that: `s` is a string, and you cannot put the number 5 in it:

```text
error[E0308]: mismatched types
  --> src/bin/shadow.rs:11:9
   |
10 |     let mut s = "abc";
   |                 ----- expected due to this value
11 |     s = 5; // type change not allowed
   |         ^ expected `&str`, found integer
```

`mismatched types` means the types do not agree. The compiler shows why it expected a `&str` (the type of a string literal): because of the value we gave on line 10. But on line 11 it found an `integer`. (This is the only error in this program; the first lines are fine.)

## Scalar types, tuples and arrays

Every value in Rust has a type that is known at compile time. The simplest types are called scalars, because each holds just one single value:

- Signed integers (can be negative): `i8` up to `i128`, and `isize`.
- Unsigned integers (zero and positive only): `u8` up to `u128`, and `usize`. The number after the letter is the number of bits. `usize` is as large as a pointer on that machine (8 bytes on mine), and it is used for indexes and sizes of collections.
- Floating-point numbers: `f32` and `f64`.
- `bool`: true or false.
- `char`: one character. It is a Unicode scalar value, so it takes 4 bytes and can hold `'ز'` as well.

Besides scalars there are two simple compound types. A **tuple** keeps several values, which may have different types, together, and its length is fixed. An **array** is several values of the same type, also with a fixed length. (For a list that can grow, we will get to `Vec` later.) The program below shows all of them at once:

```rust
const MAX_POINTS: u32 = 100_000;

fn main() {
    let a = 42; // inferred i32
    let b: u64 = 10_000_000_000;
    let c = 2.5; // f64
    let d: f32 = 1.5;
    let ok = true;
    let ch = 'ز';
    let t: (i32, f64, char) = (1, 2.5, 'x');
    let (x, y, z) = t;
    let arr = [10, 20, 30];
    let zeros = [0u8; 4];
    println!("{a} {b} {c} {d} {ok} {ch}");
    println!("{} {} {} {}", t.0, x, y, z);
    println!("{} {} {:?} {:?}", arr[0], arr.len(), arr, zeros);
    println!("{MAX_POINTS}");
    println!("char size = {} bytes, i32 = {}, usize = {}", std::mem::size_of::<char>(), std::mem::size_of::<i32>(), std::mem::size_of::<usize>());
    let n: i32 = "42".parse().unwrap();
    println!("{}", n + a);
}
```

Output:

```text
42 10000000000 2.5 1.5 true ز
1 1 2.5 x
10 3 [10, 20, 30] [0, 0, 0, 0]
100000
char size = 4 bytes, i32 = 4, usize = 8
84
```

Line by line:

1. Prints `a` through `ch`. We did not write a type for `a` and `c`; the compiler guessed it (`i32` and `f64`).
2. `t.0` is the first member of the tuple. `let (x, y, z) = t` unpacks the tuple into three separate variables (this is called destructuring), so `x`, `y` and `z` are the members of `t`.
3. `arr[0]` is the first element of the array and `arr.len()` its length. `{:?}` prints in the form meant for debugging, which arrays need. `[0u8; 4]` means an array with four elements, all of them `0` of type `u8`.
4. The constant `MAX_POINTS`.
5. Sizes in bytes: `char` is 4, `i32` is also 4, and `usize` is 8 on this machine.
6. `"42".parse()` converts the string to a number. `unwrap()` says "if the conversion failed, stop the program"; we will learn something better in the post about errors.

A few notes about the code above:

- Rust infers types. An integer defaults to `i32` and a floating-point number to `f64`. Only when inference is impossible, like with `parse()` which does not know what number to produce, do we write the type explicitly.
- `const` always needs an explicit type, its value must be known at compile time, and it cannot be `mut`. The underscore in the number (`100_000`) is only for readability.
- There is no automatic conversion between numeric types. You convert yourself, for example with `as`. Go is the same here. Let us see what happens when we add an `i32` and an `i64`:

```rust
fn main() {
    let a: i32 = 5;
    let b: i64 = 10;
    println!("{}", a + b);
}
```

```text
error[E0308]: mismatched types
 --> src/bin/mismatch.rs:4:24
  |
4 |     println!("{}", a + b);
  |                        ^ expected `i32`, found `i64`

error[E0277]: cannot add `i64` to `i32`
 --> src/bin/mismatch.rs:4:22
  |
4 |     println!("{}", a + b);
  |                      ^ no implementation for `i32 + i64`
  |
  = help: the trait `Add<i64>` is not implemented for `i32`
  = help: the following other types implement trait `Add<Rhs>`:
            `&i32` implements `Add<i32>`
            `&i32` implements `Add`
            `i32` implements `Add<&i32>`
            `i32` implements `Add`

Some errors have detailed explanations: E0277, E0308.
For more information about an error, try `rustc --explain E0277`.
error: could not compile `rust-types-control-flow` (bin "mismatch") due to 2 previous errors
```

Two errors are reported for one mistake. The first is simple: the right side of the addition should have been `i32`, but it is `i64`. The second says the same thing from another angle: there is no implementation of `i32 + i64`. In Rust even addition works through a {{< term "trait" "trait" >}} called `Add`, and the `help` lines list the additions that really exist; none of them is `i32` with `i64`. The fix is to convert one side, for example `i64::from(a) + b`. Note that you only need `trait` here to read the message; I explain it properly in later posts.

## Integer overflow

Back to the question at the top. The program below reads a `u8` from the command line, adds one to it and prints it. Then it prints four explicit ways of adding side by side:

```rust
fn main() {
    let n: u8 = std::env::args().nth(1).unwrap().parse().unwrap();
    let m = n + 1;
    println!("{m}");
    println!("{:?} {:?} {} {}", n.checked_add(1), n.wrapping_add(1), n.saturating_add(1), n.overflowing_add(1).1);
}
```

We run it first with 250, which has room, and then with 255 in both build modes:

```text
$ cargo run -q --bin overflow 250
251
Some(251) 251 251 false

$ cargo run -q --bin overflow 255
thread 'main' panicked at src/bin/overflow.rs:3:13:
attempt to add with overflow
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

$ cargo run -q --release --bin overflow 255
0
None 0 255 true
```

With 250 everything is normal. With 255 in a debug build the program stops with a **panic**. A panic is Rust's way of stopping the program on an unrecoverable error: a message with the location (file, line, column) is printed and the program ends. But in a `--release` build the overflow wraps around silently: 255 + 1 becomes 0 and the program carries on (according to the Rust docs this is the default behaviour, and a project setting can change it).

Because this difference can easily cause trouble, it is better to write what you mean. The last line of the output shows four choices:

- `checked_add` returns an `Option`: `Some(251)` means the addition fit and this is the result, and `None` means it overflowed.
- `wrapping_add` wraps on purpose: 255 + 1 becomes 0.
- `saturating_add` stops at the maximum: 255.
- `overflowing_add` returns the wrapped result together with a `bool` telling whether it overflowed. We printed only that `bool` (`.1`).

As a reminder: in Go, integer overflow always wraps silently.

## Statements and expressions

Another important difference from Go: in Rust almost everything is an expression, meaning something that has a value. The last expression of a block, **without a semicolon**, is the value of the whole block. That is why the function below does not need `return`:

```rust
fn square(x: i32) -> i32 {
    x * x
}
```

If you put a semicolon at the end of an expression, it becomes a statement, whose value is `()` (meaning "nothing"). See what error this mistake gives in `square`:

```rust
fn square(x: i32) -> i32 {
    x * x;
}
fn main() { println!("{}", square(2)); }
```

```text
error[E0308]: mismatched types
 --> src/bin/semi.rs:1:22
  |
1 | fn square(x: i32) -> i32 {
  |    ------            ^^^ expected `i32`, found `()`
  |    |
  |    implicitly returns `()` as its body has no tail or `return` expression
2 |     x * x;
  |          - help: remove this semicolon to return this value
```

The function promised to return an `i32` (`^^^`), but because the body ends with a semicolon it returns nothing but `()`. The compiler even states the cause: the body has no "tail", meaning a final expression without a semicolon. And it points at the fix on the semicolon itself: remove it.

## Control flow

Because `if` is an expression too, it can return a value and takes the place of the ternary operator (`? :`) that Go does not have and some languages do. It has two rules: the condition must be a real `bool` (an integer is not accepted), and both branches must have the same type. The program below breaks both rules:

```rust
fn main() {
    let n = 1;
    let v = if n > 0 { 1 } else { "no" };
    if n { println!("x"); }
}
```

```text
error[E0308]: `if` and `else` have incompatible types
 --> src/bin/ifmis.rs:3:35
  |
3 |     let v = if n > 0 { 1 } else { "no" };
  |                        -          ^^^^ expected integer, found `&str`
  |                        |
  |                        expected because of this

error[E0308]: mismatched types
 --> src/bin/ifmis.rs:4:8
  |
4 |     if n { println!("x"); }
  |        ^ expected `bool`, found integer
```

First error: the `if` branch returns an integer and the `else` branch a string. For the whole `if` to have one type, both must be the same. Second error: `n` is a number, not a `bool`. You have to write `if n != 0`. A correct version:

```rust
let kind = if n % 2 == 0 { "even" } else { "odd" };
```

**`loop`** runs forever until you `break`, and `break` can return a value too. **`while`** is the usual conditional loop. **`for`** works on anything that can be iterated; the three-part C-style `for` (`for i := 0; i < n; i++`) does not exist in Rust. Ranges come in two forms: `1..4` does not include the end, and `1..=4` does. **`match`** compares a value against several patterns and picks the first one that matches. Here you only see a sample; pattern matching gets its own post. This program shows all of these together:

```rust
fn main() {
    let n = 7;
    let kind = if n % 2 == 0 { "even" } else { "odd" };
    println!("{n} is {kind}");

    let mut tries = 0;
    let found = loop {
        tries += 1;
        if tries * tries > 50 {
            break tries;
        }
    };
    println!("first n with n*n > 50: {found}");

    let mut k = 3;
    while k > 0 {
        println!("k = {k}");
        k -= 1;
    }

    for i in 1..4 { print!("{i} "); }
    for i in 1..=4 { print!("{i} "); }
    for i in (1..4).rev() { print!("{i} "); }
    println!();
    let names = ["a", "b"];
    for (i, name) in names.iter().enumerate() { println!("{i}: {name}"); }

    let code = 404;
    let msg = match code {
        200 => "ok",
        404 => "not found",
        500..=599 => "server error",
        _ => "other",
    };
    println!("{msg}");
    println!("{}", square(4));
}

fn square(x: i32) -> i32 {
    x * x
}
```

```text
7 is odd
first n with n*n > 50: 8
k = 3
k = 2
k = 1
1 2 3 1 2 3 4 3 2 1 
0: a
1: b
not found
16
```

- First line: 7 is odd. Second line: `loop` finds the first `tries` whose square is greater than 50. 7 × 7 = 49 is still too small and 8 × 8 = 64 is enough, so `break tries` hands 8 to `found`.
- The three `k = ...` lines come from `while`. The counter goes down to zero.
- The line `1 2 3 1 2 3 4 3 2 1` is three `for` loops one after another on one line: `1..4` is 1 to 3, `1..=4` is 1 to 4, and `(1..4).rev()` is 3 down to 1.
- `enumerate()` adds each element's index, so we see `0: a` and `1: b`.
- `404` hits the second pattern of the `match`: `not found`.
- `square(4)` is the same `square` function without the semicolon, and gives 16.

The compiler requires a `match` to cover every possible case, which is why there is a `_` branch at the end: it means "anything else".

## Putting it together

One last small program to wrap up: a table converting Celsius to Fahrenheit (with a note on each row), and then FizzBuzz up to 15. In the formatting, `{c:>4}` means "right-aligned in a width of 4" and `{f:>6.1}` means "right-aligned in a width of 6 with one decimal digit".

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

`step_by(10)` moves the loop from -10 to 40 in steps of ten. `c as f64` converts the integer to a float (the explicit conversion we talked about above). `match` works on ranges: below zero is `freezing`, 0 to 24 is `mild`, anything more is `hot`. In FizzBuzz you saw `if` and `else if` sitting where an expression goes and producing the value of `s`. (All branches return a `String`, which is why `.to_string()` was needed.)

## Common traps for beginners

- **The last semicolon of a function.** This is the classic beginner mistake. You saw that the compiler's message points right at that semicolon, so if you see `expected i32, found ()`, look at the end of the function first.
- **Debug and release differ on overflow.** A test that panics in debug might silently give a wrong answer in release. Where it matters, use `checked_*` so the behaviour is the same in both modes.
- **Array indexes are checked at run time.** If you give the index at run time (say, read it from the command line and it is 5) and the array has 3 elements, the program panics, and unlike C it does not read memory outside the array. The real message is:

  ```text
  thread 'main' panicked at src/bin/idx.rs:4:20:
  index out of bounds: the len is 3 but the index is 5
  ```

- **Do not overdo shadowing.** It is good for conversions (`let x = x.trim();`), but if one name is covered ten times, the code becomes hard to read.
- **Ranges:** `1..4` does not include the end and `1..=4` does. Keep in mind which one you want.

## Exercise

1. Write `fn is_leap(year: u32) -> bool` as a single expression with no `return`, and print the leap years between 1990 and 2030.
2. Use `loop` and `break value` to find the first power of 2 greater than 1000.
3. Change the overflow program to print the result of `checked_add` for 250 and 255, and compare it with `wrapping_add`.

## What's next

"Ownership in Rust". Now that we know variables and types, we can reach the idea that sets Rust apart from Go: who owns a value, what a move is, and why the compiler rejects some code.
