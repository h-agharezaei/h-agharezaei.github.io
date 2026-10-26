+++
date = '2026-12-22T10:00:00+03:30'
draft = false
title = 'Lifetimes in Rust'
description = "Rust lifetimes with runnable code: the longest function, real E0106 and E0597 errors, elision rules, structs holding references and what T: 'static means."
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "lifetimes", "intermediate", "borrowing"]
cover = { image = "/images/covers/rust-lifetimes.png", alt = "Lifetimes in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-generics-traits/) we wrote code that works over many types. Now we come back to references, the topic of [Borrowing and References in Rust](/posts/rust-borrowing-references/), which you should read first. There we saw that a reference must never outlive its value, and that the compiler sometimes asks for a "lifetime specifier". This post explains what that means and when you have to write one.

> All code below was compiled and run with Rust 1.90, and the outputs and errors are copied from those runs.

## What a lifetime is

A **lifetime** is a name for the region of code in which a reference is valid. It exists only at compile time: there is nothing in the binary and nothing happens at runtime. Annotations like `'a` do not change how long anything lives. They only describe to the compiler how the lifetimes of several references relate to each other, so it can check that none of them outlives its data.

## The longest function

A function that returns one of its two input references:

```rust
fn longest(x: &str, y: &str) -> &str {
    if x.len() >= y.len() { x } else { y }
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/missing_annotation.rs:1:33
  |
1 | fn longest(x: &str, y: &str) -> &str {
  |               ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `x` or `y`
help: consider introducing a named lifetime parameter
  |
1 | fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
  |           ++++     ++          ++          ++
```

The compiler cannot know whether the result comes from `x` or `y`, and the caller needs to know how long it can use the result. We follow the suggestion:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}

fn main() {
    let a = String::from("salam donya");
    let b = String::from("hi");
    let result = longest(&a, &b);
    println!("longest: {result}");
}
```

```text
longest: salam donya
```

Read the signature as: "`x`, `y` and the result share a lifetime `'a`", which in practice means the shorter of the two inputs. The classic way to break it is to give one input a shorter scope:

```rust
fn main() {
    let a = String::from("salam donya");
    let result;
    {
        let b = String::from("hi");
        result = longest(&a, &b);
    }
    println!("longest: {result}");
}
```

```text
error[E0597]: `b` does not live long enough
  --> src/bin/short_lived.rs:10:30
   |
 9 |         let b = String::from("hi");
   |             - binding `b` declared here
10 |         result = longest(&a, &b);
   |                              ^^ borrowed value does not live long enough
11 |     }
   |     - `b` dropped here while still borrowed
12 |     println!("longest: {result}");
   |                         ------ borrow later used here
```

The result might be `b`, and `b` is dropped at the closing brace while `result` is still used afterwards. Same trick as before: look at the "later used here" label.

## Lifetime elision

You don't write lifetimes everywhere because the compiler applies three **elision** rules to function signatures:

1. Every elided lifetime in the parameters becomes its own separate lifetime parameter.
2. If there is exactly one input lifetime, it is assigned to all elided lifetimes in the output.
3. If there are several input lifetimes but one of them is `&self` or `&mut self`, the lifetime of `self` is assigned to all elided output lifetimes.

If the output lifetimes are still undetermined after these rules, you get E0106, exactly as with `longest` (two inputs, no `self`). A function that needs nothing, and its spelled-out equivalent:

```rust
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

fn first_word_explicit<'a>(s: &'a str) -> &'a str {
    s.split(' ').next().unwrap_or("")
}
```

Both print `salam` for `"salam donya"`. Rule 2 applies, and the result borrows from the input, which is why it is safe to return a part of it.

## Structs that hold references

A struct holding a reference needs a lifetime parameter, so the compiler knows the struct cannot outlive what it points to:

```rust
struct Excerpt<'a> {
    part: &'a str,
}

impl<'a> Excerpt<'a> {
    // rule 3: the output gets the lifetime of &self
    fn part(&self) -> &str {
        self.part
    }
}

fn main() {
    let novel = String::from("Call me Ishmael. Some years ago...");
    let first_sentence = novel.split('.').next().unwrap();
    let e = Excerpt { part: first_sentence };
    println!("{}", e.part());
}
```

```text
Call me Ishmael
```

You write `impl<'a>` and `Excerpt<'a>` because `'a` is part of the type, just like a generic parameter. If the `Excerpt` outlives `novel`, you get the same E0597 as before (`novel` does not live long enough, dropped while still borrowed).

## 'static

`'static` is the longest lifetime. String literals have it, because their text is stored in the program itself:

```rust
let greeting: &'static str = "salam";
```

There is a common misconception about the bound `T: 'static`. It does not mean "the value lives forever". It means the type contains no references shorter than `'static`. An owned `String` or an `i32` satisfies it and is dropped like any other value:

```rust
fn takes_static<T: Debug + 'static>(value: T) { println!("got {value:?}"); }

takes_static(owned);   // String: ok
takes_static(42);      // ok
takes_static(&owned);  // a borrow of a local: error
```

```text
got "owned"
got 42
got "salam"
```

The last call, in a separate program, fails:

```text
error[E0597]: `owned` does not live long enough
 9 |     takes_static(&owned);
   |     -------------^^^^^^-
   |     |            |
   |     |            borrowed value does not live long enough
   |     argument requires that `owned` is borrowed for `'static`
```

Don't "fix" a lifetime error by adding `'static` unless the data really is a literal or a constant.

## When you fight the borrow checker

While learning, don't force lifetimes everywhere. If `Excerpt` gives you trouble, store a `String` and call `.to_string()` (or `.clone()`) once:

```rust
struct Excerpt {
    part: String, // owned: no lifetime needed
}
```

I ran this version with the same inner-scope trick that broke the borrowing version, and it prints `Call me Ishmael`. The cost is one allocation. Reaching for references with lifetimes is an optimization; do it when you have a reason.

## A few things to watch

- Lifetime annotations describe relationships; they never extend how long a value lives.
- Don't annotate when elision works. Only add `'a` when the compiler asks.
- A function can't return a reference to a local variable. Return an owned value instead.
- `'a` on a struct means "this struct cannot outlive that borrowed data".
- Read the labels in E0597: "declared here", "dropped here", "later used here".

## Exercise

1. Write `fn longer_or_default<'a>(x: &'a str, default: &'static str) -> &'a str` returning whichever is longer. It compiles, because a `'static` reference can be used wherever a shorter one is expected; try to explain why.
2. Add a method `fn first_word(&self) -> &str` to `Excerpt` and call it.
3. Change `Excerpt` to own a `String` and delete every `'a`.

## What's next

The next post covers closures and iterators in Rust: functions that capture their environment and the iterator chains that replace most loops.
