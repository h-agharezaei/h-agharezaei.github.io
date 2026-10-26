+++
date = '2026-11-14T10:00:00+03:30'
draft = false
title = 'Borrowing and references in Rust'
description = 'Rust borrowing and references with runnable code: &T and &mut T, the readers-or-one-writer rule, NLL, dangling references, slices and real compiler errors.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "borrowing", "references"]
cover = { image = "/images/covers/rust-borrowing-references.png", alt = "Borrowing and references in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-ownership/) we ended with a clumsy pattern: pass a `String` into a function and return it back just to keep using it. {{< term "borrowing" "Borrowing" >}} is the fix. You hand a function a reference, it uses the value, and ownership never moves. This post covers the two kinds of references, the one rule that governs them, and the compiler errors you will meet while learning it.

> Everything below was compiled and run with Rust 1.90, and the outputs and errors are copied from those runs.

## Shared and mutable references

`&T` is a **shared reference**: you can read through it. `&mut T` is a **mutable reference**: you can read and change the value. Creating one is called **borrowing**.

```rust
fn length(s: &String) -> usize {
    s.len()
}

fn add_exclaim(s: &mut String) {
    s.push('!');
}

fn main() {
    let mut s = String::from("salam");
    let n = length(&s);
    println!("{s} has {n} bytes");

    add_exclaim(&mut s);
    println!("{s}");

    // many readers at once is fine
    let r1 = &s;
    let r2 = &s;
    println!("{r1} {r2}");
}
```

Output:

```text
salam has 5 bytes
salam!
salam! salam!
```

Compare with the last post: `length` no longer takes ownership, so `s` is still ours afterwards and there is no tuple to return. Note that the variable must be declared `mut` for `&mut s` to be allowed.

## The rule: many readers or one writer

At any moment you can have either any number of `&T` references, or exactly one `&mut T`, but not both. This is the whole borrowing rule. It is what lets the compiler guarantee that nobody changes data while someone else is reading it.

Two writers first:

```rust
fn main() {
    let mut s = String::from("salam");
    let a = &mut s;
    let b = &mut s;
    a.push('1');
    b.push('2');
    println!("{s}");
}
```

```text
error[E0499]: cannot borrow `s` as mutable more than once at a time
 --> src/bin/two_mut.rs:4:13
  |
3 |     let a = &mut s;
  |             ------ first mutable borrow occurs here
4 |     let b = &mut s;
  |             ^^^^^^ second mutable borrow occurs here
5 |     a.push('1');
  |     - first borrow later used here
```

Now a reader that is still alive while we mutate:

```rust
fn main() {
    let mut v = vec![1, 2, 3];
    let first = &v[0];
    v.push(4);
    println!("first = {first}");
}
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/bin/mutate_while_shared.rs:4:5
  |
3 |     let first = &v[0];
  |                  - immutable borrow occurs here
4 |     v.push(4);
  |     ^^^^^^^^^ mutable borrow occurs here
5 |     println!("first = {first}");
  |                        ----- immutable borrow later used here
```

The second one is the interesting case. `push` may need to reallocate the vector's buffer, which would leave `first` pointing at freed memory. Rust rejects the program before that can happen.

## A borrow ends at its last use

A borrow does not last until the closing brace. It lasts until the reference is last used. This is called **non-lexical lifetimes** (NLL). This program mixes a shared and a mutable borrow of the same variable, and it compiles:

```rust
fn main() {
    let mut s = String::from("salam");
    let r = &s;
    println!("reader sees {r}");
    // r is not used after this point, so the borrow has ended
    let w = &mut s;
    w.push_str(" donya");
    println!("{s}");
}
```

```text
reader sees salam
salam donya
```

If you added a `println!("{r}")` after the `push_str`, you would get the E0502 error from before. When the compiler complains, look for the "later used here" label: it points at the use that keeps the borrow alive.

## References cannot dangle

A reference must never outlive the value it points to. Here is a function that tries to return a reference to its own local:

```rust
fn dangle() -> &String {
    let s = String::from("salam");
    &s
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/dangle.rs:1:16
  |
1 | fn dangle() -> &String {
  |                ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but there is no value for it to be borrowed from
help: consider using the `'static` lifetime, but this is uncommon unless you're returning a borrowed value from a `const` or a `static`
  |
1 | fn dangle() -> &'static String {
  |                 +++++++
help: instead, you are more likely to want to return an owned value
  |
1 - fn dangle() -> &String {
1 + fn dangle() -> String {
  |
```

The compiler's second suggestion is the right one: return the `String` itself and let ownership move out. If you add a lifetime name to silence E0106 (`fn dangle<'a>() -> &'a String`), you get the deeper error:

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/dangle2.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function

```

`s` is dropped when the function ends, so the reference would point at nothing. Lifetimes get a proper treatment later in the series.

## Slices: borrowed views

A `&str` is a borrowed view into some string data, and `&[T]` is a borrowed view into a run of elements. They are references too, so the same rules apply, and functions that take them accept more inputs:

```rust
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

fn sum(xs: &[i32]) -> i32 {
    xs.iter().sum()
}

fn main() {
    let text = String::from("salam donya");
    println!("{}", first_word(&text));
    println!("{}", first_word("hello rust"));

    let v = vec![1, 2, 3, 4, 5];
    println!("{}", sum(&v));
    println!("{}", sum(&v[1..4]));
}
```

```text
salam
hello
15
9
```

`first_word` works for a `String` (via `&text`) and for a literal. `sum` works for a whole `Vec` and for a sub-range. Prefer `&str` and `&[T]` over `&String` and `&Vec<T>` in parameters.

## A few things to watch

- References are not pointers you manage by hand. You do not free them, and they are never null.
- Many readers or one writer applies per value, at the same time. Sequential borrows are fine, thanks to NLL.
- Read the error labels ("first borrow occurs here", "later used here") instead of just the headline; they tell you which two lines conflict.
- If a borrow error is hard to untangle, a shorter scope or an owned return value is often the fix. `.clone()` is a last resort.
- Compared with Go: Go lets you hold many pointers to the same value and mutate through any of them, and the compiler does not stop you. If goroutines do that without synchronisation, it is a data race and your problem to find (the race detector helps). Rust moves that check to compile time, at the cost of arguing with the compiler first.

## Exercise

1. Write `fn append_twice(s: &mut String, word: &str)` that pushes `word` onto `s` two times, and call it from `main`.
2. Reproduce the E0502 error with a `Vec`, then fix it by moving the `push` before you take the reference.
3. Write `fn largest(xs: &[i32]) -> i32` and call it with a full `Vec` and with a sub-slice.

## What's next

So far our data has been single values and collections. In the next post, structs, enums and pattern matching in Rust, we will model our own types and branch on them.
