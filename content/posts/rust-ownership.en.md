+++
date = '2026-11-08T10:00:00+03:30'
draft = false
title = 'Ownership in Rust'
description = 'Rust ownership explained with runnable code: the three rules, stack vs heap, moves, Copy, clone, functions and Drop, with a real compiler error.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "ownership", "memory"]
cover = { image = "/images/covers/rust-ownership.png", alt = "Ownership in Rust", hiddenInSingle = true }
+++

Let us start with two lines of code. In the first we put a value in a variable `a`, and in the second we hand it over to `b`: `let b = a;`. Then we print `a` again. If `a` is an `i32`, all is well. If `a` is a `String`, the program does not compile at all, and the compiler gives error E0382. One identical line of code, two different results. Why?

The answer is an idea called {{< term "ownership" "ownership" >}}. Go and Node.js have nothing quite like it. It is the idea Rust uses to manage memory without a {{< term "garbage-collector" "garbage collector" >}}, and in the first weeks of learning Rust most compiler errors come from it. If you are not yet familiar with Rust's types and variables, read [Types, variables and control flow in Rust](/posts/rust-types-control-flow/) first. What we need from it here: variables are immutable by default, and the type of every value is known at compile time.

> I compiled and ran all the code below with Rust 1.90, and the outputs come from those runs. I also wrote a few small extra programs that exist only to show one error or one size; those were run too.

## The problem: who frees the memory?

Every program takes memory and must give it back. If it does not, memory slowly runs out. If it gives it back twice, or keeps using it after giving it back, the program breaks and can even become unsafe. Languages have given three different answers:

- **By hand (like C):** you call `free` yourself. It is fast, but forgetting it, or calling it twice, creates serious bugs.
- **With a garbage collector (like Go and Node.js):** a part of the runtime periodically looks around and frees memory that nobody can reach any more. It is convenient, but you pay for the work at run time.
- **Ownership (Rust):** there are rules that the compiler checks. From the rules the compiler knows exactly where memory must be freed, and it inserts that code itself. There is no garbage collector, and you never write a `free` by hand.

So ownership answers this question: "who frees the memory, and when?" To understand it, we first need to see where values live.

## Stack and heap, very briefly

A program has two main places to keep values. The {{< term "stack-memory" "stack" >}} is a tidy, fast place: each function call takes a piece of it and gives it back when the function returns. Only values whose size is known at compile time go there, such as an integer, a `bool` or a fixed-size array. The {{< term "heap-memory" "heap" >}} is for data whose size changes or is not known in advance, like text a user types. You ask the system for space, get its address, and when you are done you must give it back. (In [Pointers and memory in Go](/posts/go-pointers-memory/) we looked at these same two places from Go's side.)

Let us see how `String` is built in Rust. A `String` itself is a small, fixed piece on the stack that holds three things: the address of a buffer on the heap where the characters are, the length of the text, and the capacity of that buffer. To see this, I printed its size:

```rust
fn main() {
    println!("i32: {} bytes", std::mem::size_of::<i32>());
    println!("String: {} bytes", std::mem::size_of::<String>());
    let s = String::from("salam");
    println!("len = {}, capacity >= len: {}", s.len(), s.capacity() >= s.len());
}
```

```text
i32: 4 bytes
String: 24 bytes
len = 5, capacity >= len: true
```

A `String` is always 24 bytes, whether its text is one letter or a million, because those 24 bytes are only those three things (two numbers and an address, 8 bytes each on this 64-bit machine). The characters themselves are somewhere else, on the heap. So a `String` is really the "key ring" of a piece of heap memory. This matters for what follows.

## The three rules

Rust defines ownership with three simple rules:

1. Every value has an **owner**, a variable that owns it.
2. There is only one owner at any time.
3. When the owner goes out of scope, the value is **dropped**, which means its memory is freed.

A scope is the area between the curly braces where the variable was declared. The third rule means you never call `free`: where the closing brace is, the compiler has put the freeing code for you. The second rule is the reason the rules exist. If two variables both believed they owned the same heap buffer, both would free it when leaving their scope, and the same memory would be freed twice (this bug is called a **double free**). With "only one owner" that cannot happen.

That is the whole model. The rest of this post is what these three rules do in practice.

## String and &str

For the next examples we need to tell two kinds of strings apart. A literal like `"hello"` has the type `&str`: it is read-only and its text is written inside the program itself. A `String` is the type we saw above: it owns a growable buffer on the heap. With `to_string()` or `String::from` you can make the second from the first:

```rust
let lit: &str = "hello";
let owned: String = lit.to_string();
println!("{lit} {owned}");
// hello hello
```

That is enough for now: a `String` owns its data. The `&` in `&str` means "borrowing", which is the subject of the next post.

## Move: transferring ownership

Back to the first question. The program below is the same two lines, with a `String`:

```rust
fn main() {
    let a = String::from("salam");
    let b = a;
    println!("{a}");
    println!("{b}");
}
```

First think about what `let b = a` does. It puts only those same 24 bytes (address, length, capacity) into `b`. The characters on the heap are not copied. Now if both `a` and `b` stayed valid, both would point to one buffer and both would free it at the end: the double free. To prevent it, Rust says ownership was **moved** from `a` to `b`, and `a` is no longer valid. That is why this code does not compile:

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
  = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
help: consider cloning the value if the performance cost is acceptable
  |
3 |     let b = a.clone();
  |              ++++++++

For more information about this error, try `rustc --explain E0382`.
error: could not compile `rust-ownership` (bin "moved") due to 1 previous error
```

This message tells the story in time order. Let us read it:

- The title: `borrow of moved value: a`, meaning "a value that was moved was used". (The word borrow is there because `println!` only borrows the value to print it.)
- Line 2: `a` has type `String`, and because `String` does not have the `Copy` property (I explain it just below), assigning it moves it.
- Line 3: "value moved here", the place where ownership went to `b`.
- Line 4: `println!("{a}")` touches `a` after it was moved.
- The `= note` line is about the `println` macro and is not the root of the error; it only says the error was detected inside that macro.
- `help`: if you really want two independent strings, write `a.clone()`.

In Go, if you assign a slice to another variable, both point to the same backing array and both stay valid. Rust does not accept that situation at compile time, because it would be unclear who frees the memory.

## Copy types and clone

So why does the same code compile with `i32`? Because simple values like numbers live entirely on the stack, and copying them is cheap and harmless: there is no heap buffer that could be freed twice. These types have a property (a trait) called `Copy`; for them, assignment makes a full copy and both variables stay valid:

```rust
let x = 5;
let y = x;
println!("x = {x}, y = {y}");
// x = 5, y = 5
```

Integers, floats, `bool` and `char` are `Copy`, but `String` is not. If you really want two independent copies of a `String`, you have to write `.clone()` explicitly. A clone makes a full copy: it takes a new buffer on the heap and copies the characters into it.

```rust
let c = b.clone();
println!("b = {b}, c = {c}");
// b = salam, c = salam
```

That Rust makes this explicit is on purpose: an expensive copy should be visible in the code, not hidden behind a plain `=`.

## Ownership and functions

Passing a value to a function works like assignment. The function's parameter becomes the new owner. Look at these functions:

```rust
fn take(s: String) -> usize {
    s.len()
}

fn take_and_give_back(s: String) -> (String, usize) {
    let n = s.len();
    (s, n)
}
```

`take` receives the string, returns its length, and at the end of the function `s` goes out of scope and its memory is freed. So after `take(s)` you cannot use `s`:

```rust
fn main() {
    let s = String::from("rust");
    let n = take(s);
    println!("{n}");
    println!("{s}");
}
```

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/fnmove.rs:9:16
  |
6 |     let s = String::from("rust");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
7 |     let n = take(s);
  |                  - value moved here
8 |     println!("{n}");
9 |     println!("{s}");
  |                ^ value borrowed here after move
  |
note: consider changing this parameter type in function `take` to borrow instead if owning the value isn't necessary
 --> src/bin/fnmove.rs:1:12
  |
1 | fn take(s: String) -> usize {
  |    ----    ^^^^^^ this parameter takes ownership of the value
  |    |
  |    in this function
  = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
help: consider cloning the value if the performance cost is acceptable
  |
7 |     let n = take(s.clone());
  |                   ++++++++

For more information about this error, try `rustc --explain E0382`.
error: could not compile `rust-ownership` (bin "fnmove") due to 1 previous error
```

It is the same story as before: ownership went to `take` on line 7. This time the compiler also has a suggestion (the `note`): if `take` does not need to own the string, change its parameter so that it borrows. That is exactly the right way, and the next post explains it. (I got this error from a separate small program that contains only `take` and this `main`.)

The other way is for the function to give ownership back, like `take_and_give_back`, which returns the string together with the answer:

```rust
let s2 = String::from("ownership");
let (s2, n2) = take_and_give_back(s2);
println!("{s2} has {n2} bytes");
```

This works, because `s2` becomes the owner again (the same shadowing we saw in the previous post). But passing things back and forth and returning tuples, just so we can use our own data again, gets tiring very quickly. Borrowing, in the next post, removes this back and forth.

## Drop: seeing the moment of freeing

The third rule says a value is dropped when its owner goes out of scope. This is normally invisible. But Rust lets a type have code that runs exactly at the moment of the drop (by implementing a trait called `Drop`). We use that to see when freeing happens. The type `Noisy` prints its name whenever it is dropped:

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

(A variable name starting with `_` tells the compiler we deliberately do not use it, so it gives no warning; the variables still live until the end of their scope.) Output:

```text
end of inner block
drop inner
inside consume(third)
drop third
end of main
drop second
drop first
```

Line by line:

- `end of inner block`, then `drop inner`: `_inner` was dropped when the inner block's brace closed, that is, after that line was printed.
- `inside consume(third)`: we passed `third` to the function and the function became its owner.
- `drop third`: when the function finished, `n` went out of scope and the value was dropped. Notice this line comes before `end of main`: `third` was not dropped in `main`, because it no longer belonged to `main`.
- `end of main`, and then at the end of `main` the remaining variables are dropped in the reverse order of their declaration: `second` first, then `first`.

## Common mistakes with move

- **Move is not only for `let`.** Passing to a function, putting a value in a `Vec` and returning from a block are moves too.
- **Do not reach for `.clone()` every time the compiler complains.** It works, but it hides a copy, and it is usually a sign that the design should borrow instead of own.
- **A move of a heap type is cheap.** Only those three fields (address, length, capacity) are moved; the heap buffer is not copied.
- **Comparison with Go.** The garbage collector frees memory for you at run time, at the cost of some overhead and less predictable timing, and it has nothing to learn at the start. Rust makes this decision at compile time, which costs learning and sometimes restructuring code, but needs no collector. Neither is absolutely better; they are different trade-offs.
- **`Drop` runs at the end of the scope, not "some time later".** That is why it is also used for closing files and releasing locks.

## Exercise

1. Write the `let b = a;` program with `a` as a `String`, see error E0382, then fix it with `.clone()`.
2. Change the type of `a` to `i32` and see why it compiles with no other change.
3. Add a fourth `Noisy` next to `_inner` in the inner block, and guess the drop order before running it.

## What's next

"Borrowing and references in Rust". Moving values in and out of functions is clumsy. In the next post we see how a function can use a value without taking ownership of it.
