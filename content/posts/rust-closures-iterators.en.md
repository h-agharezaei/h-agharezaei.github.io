+++
date = '2026-12-24T10:00:00+03:30'
draft = false
title = 'Closures and iterators in Rust'
description = 'Rust closures and iterators: capture modes, move, Fn, FnMut and FnOnce, returning closures, adapters and consumers, laziness and a custom Iterator.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "closures", "iterators", "intermediate"]
cover = { image = "/images/covers/rust-closures-iterators.png", alt = "Closures and iterators in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-lifetimes/) we learned how the compiler tracks how long references live. Closures and iterators are where that knowledge pays off: a closure is a small function that captures variables from its surroundings, so it has to follow the same borrowing rules. Iterators are the other half, and together they replace most of the index-based loops you would write in other languages.

> I compiled and ran everything below with Rust 1.90. Outputs and compiler messages are copied from those runs.

## Closures and capturing

A **closure** is an anonymous function written `|args| body`. Parameter and return types are inferred, and the closure can use variables from the enclosing scope. Rust picks the lightest way to capture each variable:

```rust
let name = String::from("Roham");
let greet = || println!("hello {name}"); // borrows name
greet();
println!("name still usable: {name}");

let mut count = 0;
let mut inc = || count += 1; // mutable borrow
inc();
inc();
println!("count = {count}");
```

```text
hello Roham
name still usable: Roham
count = 2
```

The `move` keyword forces the closure to take ownership of what it uses. You need it when the closure outlives the current function, for example when it is returned. Without it, the compiler refuses:

```text
error[E0373]: closure may outlive the current function, but it borrows `s`, which is owned by the current function
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^            - `s` is borrowed here
  |     |
  |     may outlive borrowed value `s`
help: to force the closure to take ownership of `s` (and any other referenced variables), use the `move` keyword
```

The flip side: after `move`, the original variable is gone.

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/use_after_move.rs:5:16
3 |     let f = move || println!("{s}");
  |             -------            - variable moved due to use in closure
  |             |
  |             value moved into closure here
4 |     f();
5 |     println!("{s}");
  |                ^ value borrowed here after move
```

## Fn, FnMut and FnOnce

Every closure implements one or more of three traits, depending on what its body does with captured values:

- `Fn`: only reads captures, can be called many times.
- `FnMut`: mutates captures, can be called many times.
- `FnOnce`: moves a capture out, so it can be called once.

```rust
fn call_fn(f: impl Fn() -> usize) -> usize { f() + f() }
fn call_mut(mut f: impl FnMut()) { f(); f(); }
fn call_once(f: impl FnOnce() -> String) -> String { f() }

let word = String::from("rust");
println!("Fn: {}", call_fn(|| word.len()));
let mut log = Vec::new();
call_mut(|| log.push(log.len()));
println!("FnMut: {log:?}");
let s = String::from("bye");
println!("FnOnce: {}", call_once(move || s));
```

```text
Fn: 8
FnMut: [0, 1]
FnOnce: bye
```

Every `Fn` closure is also `FnMut` and `FnOnce`, so a function that only calls its argument once should ask for `FnOnce` and accept the most. Calling a closure that returns its captured `String` twice fails:

```text
error[E0382]: use of moved value: `f`
note: closure cannot be invoked more than once because it moves the variable `s` out of its environment
note: this value implements `FnOnce`, which causes it to be moved when called
```

To return a closure, use `impl Fn` when there is one concrete closure, or `Box<dyn Fn>` when different branches return different closures:

```rust
fn make_adder(n: i32) -> impl Fn(i32) -> i32 { move |x| x + n }

fn make_op(kind: &str) -> Box<dyn Fn(i32) -> i32> {
    match kind {
        "double" => Box::new(|x| x * 2),
        _ => Box::new(|x| x + 100),
    }
}
```

`make_adder(5)(10)` gives `15`, and `make_op("double")(7)` gives `14`. We will look at `Box` properly in the next post. Go closures capture variables by reference and the garbage collector keeps them alive (see [the Go functions post](/posts/go-functions-defer-errors/)); in Rust you choose and the compiler checks it.

## Iterators

The **Iterator** trait has one required method: `next`, which returns `Some(item)` until it returns `None`. There are three ways to get an iterator from a `Vec`:

```rust
let mut v = vec![String::from("a"), String::from("b")];
for s in v.iter() { println!("iter: {s}"); }          // &String
for s in v.iter_mut() { s.push('!'); }                // &mut String
println!("after iter_mut: {v:?}");
for s in v.into_iter() { println!("into_iter: {s}"); } // String, v is moved
```

```text
iter: a
iter: b
after iter_mut: ["a!", "b!"]
into_iter: a!
into_iter: b!
```

**Adapters** turn one iterator into another; **consumers** run it and produce a result. Output from one run:

```rust
nums.iter().map(|n| n * n)                    // [1, 4, 9, 16, 25, 36]
nums.iter().filter(|n| **n % 2 == 0)          // [2, 4, 6]
nums.iter().enumerate().take(2)               // (0, 1) (1, 2)
names.iter().copied().zip(nums.iter())        // [("a", 1), ("b", 2), ("c", 3)]
nums.iter().skip(4)                           // [5, 6]
nums.iter().take(2).chain(nums.iter().skip(5)) // [1, 2, 6]
words.iter().flat_map(|s| s.split(' '))       // ["hi", "there", "go", "rust"]
```

Consumers on `[1, 2, 3, 4, 5, 6]`: `sum` gave `21`, `fold` building a string gave `123456`, `any(|&n| n > 5)` gave `true`, `all(|&n| n > 0)` gave `true`, `find` for `> 3` gave `Some(4)` and for `> 9` gave `None`. `collect` builds a `Vec` (or `HashMap`, `String`, and so on) from the target type you ask for.

## Iterators are lazy

Adapters do nothing until a consumer pulls items through them:

```rust
let it = nums.iter().map(|n| {
    println!("  map sees {n}");
    n * 10
});
println!("adapter built, nothing printed yet");
let out: Vec<i32> = it.collect();
println!("collected {out:?}");
```

```text
adapter built, nothing printed yet
  map sees 1
  map sees 2
  map sees 3
collected [10, 20, 30]
```

The compiler also warns if you build an adapter and never use it.

## Your own Iterator

Implement `next` and you get every adapter and consumer for free:

```rust
struct Countdown(u32);

impl Iterator for Countdown {
    type Item = u32;
    fn next(&mut self) -> Option<u32> {
        if self.0 == 0 { None } else { self.0 -= 1; Some(self.0 + 1) }
    }
}
```

`Countdown(5).collect::<Vec<_>>()` gives `[5, 4, 3, 2, 1]`, and `Countdown(5).filter(|n| n % 2 == 1).map(|n| n * n).sum()` gives `35` (25 + 9 + 1).

## Loop versus iterators

Counting words longer than two letters, with a `for` loop and then with an iterator chain (both in my demo, sorted by count then word):

```rust
let counts = text
    .split_whitespace()
    .map(|w| w.to_lowercase())
    .filter(|w| w.len() > 2)
    .fold(HashMap::new(), |mut m, w| {
        *m.entry(w).or_insert(0usize) += 1;
        m
    });
```

On `"the cat and The dog and a bird saw the cat"` both versions return the same result, starting `[("the", 3), ("and", 2), ("cat", 2)]`. I find the chain easier to read once you know the vocabulary, but the loop is just as valid, and I did not benchmark either.

## A few things to watch

- `iter()` yields references, so closures often see `&&i32` in `filter`; that is why patterns like `|&&n|` appear.
- `into_iter()` on a `Vec` consumes it. Use `iter()` if you need the data afterwards.
- A closure that is `FnOnce` cannot be passed where `Fn` is required.
- Prefer `collect` into the type you need rather than building a `Vec` just to loop over it.
- Lazy means side effects inside `map` may never run; use `for` or `for_each` for side effects.

## Exercise

1. Write a function that takes `&[i32]` and returns the sum of squares of the odd numbers, using one iterator chain.
2. Write `fn make_counter() -> impl FnMut() -> u32` that returns 1, 2, 3 on successive calls.
3. Implement `Iterator` for a `Fib` struct and print its first ten values with `take(10)`.

## What's next

Next we look at smart pointers in Rust: `Box`, `Rc` and `RefCell`, and when you need them.
