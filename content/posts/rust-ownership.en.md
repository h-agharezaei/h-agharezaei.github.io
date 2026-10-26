+++
date = '2026-11-08T10:00:00+03:30'
draft = false
title = 'Ownership in Rust'
description = 'Rust ownership explained with runnable code: the three rules, stack vs heap, moves, Copy, clone, functions and Drop, with a real compiler error.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "ownership", "memory"]
cover = { image = "/images/covers/rust-ownership.png", alt = "Ownership in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-types-control-flow/) we covered types, variables and control flow, which felt familiar if you come from Go or Node.js. {{< term "ownership" "Ownership" >}} is the part that does not. It is the idea Rust uses to manage memory without a garbage collector, and it is what the compiler complains about most in your first weeks.

> Everything below was compiled and run with Rust 1.90, and the outputs are copied from those runs.

## The three rules

1. Every value has exactly one **owner**.
2. There can only be one owner at a time.
3. When the owner goes out of scope, the value is dropped (its memory is freed).

That is the whole model. The rest of the post is what these rules mean in practice.

## Stack and heap, briefly

The **stack** holds values whose size is known at compile time (integers, booleans, fixed-size arrays). Pushing and popping is cheap. The **heap** holds data whose size can change or is unknown up front, such as the text in a string. You ask the allocator for space and get a pointer back, and someone must free it later. Ownership answers the question "who frees it, and when?".

## String vs &str

A string literal like `"hello"` has type `&str`: a read-only view of text baked into the program. A `String` owns a growable buffer on the heap. Convert with `to_string()` or `String::from`:

```rust
let lit: &str = "hello";
let owned: String = lit.to_string();
println!("{lit} {owned}");
// hello hello
```

For now, remember that `String` is the owning type. The `&` in `&str` is a borrow, which is the next post.

## Move semantics

```rust
fn main() {
    let a = String::from("salam");
    let b = a;
    println!("{a}");
    println!("{b}");
}
```

This does not compile:

```text
error[E0382]: borrow of moved value: `a`
 --> src/bin/moved.rs:4:16
  |
2 |     let a = String::from("salam");
  |         - move occurs because `a` has type `String`, which does not implement the `Copy` trait
3 |     let b = a;
  |             - value moved here
4 |     println!("{a}");
  |                ^ value borrowed here after move
  |
help: consider cloning the value if the performance cost is acceptable
  |
3 |     let b = a.clone();
  |              ++++++++
```

`let b = a` does not copy the string. It **moves** ownership to `b`, and `a` is no longer usable. This is what prevents a double free: only one variable ever frees the buffer. In Go, assigning a slice header shares the backing array and both names stay valid. Rust refuses that at compile time.

## Copy types and clone

Simple stack values implement the `Copy` trait, so assignment copies them and both variables stay valid:

```rust
let x = 5;
let y = x;
println!("x = {x}, y = {y}");
// x = 5, y = 5
```

Integers, floats, `bool` and `char` are `Copy`. `String` is not. If you really want two independent strings, say so explicitly with `.clone()`, a deep copy that allocates new heap memory:

```rust
let c = b.clone();
println!("b = {b}, c = {c}");
// b = salam, c = salam
```

The explicitness is the point: an expensive copy is visible in the code.

## Ownership and functions

Passing a value to a function moves it, exactly like assignment. Returning a value gives ownership back:

```rust
fn take(s: String) -> usize { s.len() }

fn take_and_give_back(s: String) -> (String, usize) {
    let n = s.len();
    (s, n)
}
```

After `take(s)` you cannot use `s` again. With `take_and_give_back` you get the string back, but returning tuples just to keep using your own data gets tedious fast. Borrowing, the subject of the next post, removes that dance.

## Drop: seeing it happen

Types can run code when their owner goes away by implementing `Drop`:

```rust
struct Noisy(&'static str);

impl Drop for Noisy {
    fn drop(&mut self) {
        println!("drop {}", self.0);
    }
}

fn consume(n: Noisy) {
    println!("inside consume({})", n.0);
}

fn main() {
    let _first = Noisy("first");
    let _second = Noisy("second");
    {
        let _inner = Noisy("inner");
        println!("end of inner block");
    }
    let third = Noisy("third");
    consume(third);
    println!("end of main");
}
```

Output:

```text
end of inner block
drop inner
inside consume(third)
drop third
end of main
drop second
drop first
```

`inner` is dropped at the closing brace of its block. `third` is dropped when `consume` returns, because the function owned it. At the end of `main`, locals are dropped in reverse order of declaration: `second` before `first`.

## A few things to watch

- A move is not just for `let`. Passing to a function, pushing into a `Vec` or returning from a block all move.
- Do not reach for `.clone()` every time the compiler complains. It works, but it hides a copy and often means the design wants a borrow.
- Moves of heap types copy only the small pointer/length/capacity part on the stack. The heap buffer is not copied.
- Compared with Go: a garbage collector frees memory for you at runtime at the cost of some runtime overhead and less predictable timing, with nothing to learn up front. Rust decides at compile time instead, which costs you learning and sometimes restructuring code, but needs no collector. Neither is strictly better; they are different trade-offs.
- `Drop` runs at scope end, not "eventually", so it is also used for closing files and releasing locks.

## Exercise

1. Write the `let b = a;` program with `a` as a `String`, reproduce the E0382 error, then fix it once with `.clone()`.
2. Change `a` to an `i32` and see why it compiles without any change.
3. Add a fourth `Noisy` in the inner block next to `_inner` and predict the drop order before running.

## What's next

Moving values in and out of functions is clumsy. In the next post, borrowing and references in Rust, we will see how to let a function use a value without taking ownership.
