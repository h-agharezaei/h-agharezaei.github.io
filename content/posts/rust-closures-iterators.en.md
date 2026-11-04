+++
date = '2026-12-24T10:00:00+03:30'
draft = false
title = 'Closures and iterators in Rust'
description = 'Rust closures and iterators: capture modes, move, Fn, FnMut and FnOnce, returning closures, adapters and consumers, laziness and a custom Iterator.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "closures", "iterators", "intermediate"]
cover = { image = "/images/covers/rust-closures-iterators.png", alt = "Closures and iterators in Rust", hiddenInSingle = true }
+++

Say you have a list of numbers and you want only the ones bigger than a limit that you read from the user. Filtering is easy. The interesting part is the condition: it is a tiny piece of behaviour ("is this number bigger than `limit`?") that you want to hand to another function, and it needs to see the variable `limit` that lives in your code. A plain function cannot do that. A **closure** can, and this post is about closures and about the tool they are used with most often: iterators.

The [previous post](/posts/rust-lifetimes/) was about checking that a reference never outlives its value. That check comes back here, because a closure that uses your local variables is holding references to them (or owning them), and the compiler applies the same rules. If you know Go, a closure is what Go calls a function literal; I compare the two in the section on capturing ([Go functions](/posts/go-functions-defer-errors/) has the Go side).

> I compiled and ran everything below with Rust 1.90 (the same version as the original run). Outputs and compiler messages are copied from those runs. A few small programs (the `limit` example, a `fn` that tries to use a local variable, a closure passed where `Fn` is required, and an adapter that is never used) were not in the original demo; I wrote them for this post and ran them separately. I removed the "For more information..." line from the messages, and from some of them the extra `help:` suggestions and an unrelated unused-variable warning.

## Closures: a function that remembers its surroundings

A {{< term "rust-closure" "closure" >}} is an anonymous function, written `|parameters| body`. The difference from a normal function is that it can use variables from the place where it was created. Here is the limit example:

```rust
let limit = 3;
let is_big = |n: i32| n > limit;
println!("{} {}", is_big(2), is_big(5));
```

```text
false true
```

`is_big` takes `n` as a parameter and also uses `limit`, which it did not receive as a parameter. It picked it up from the surrounding code. A normal `fn` cannot do this. If we write the same thing as a function inside `main`:

```rust
let limit = 3;
fn is_big(n: i32) -> bool {
    n > limit
}
```

```text
error[E0434]: can't capture dynamic environment in a fn item
 --> src/bin/x_fnitem.rs:4:13
  |
4 |         n > limit
  |             ^^^^^
  |
  = help: use the `|| { ... }` closure form instead
```

The message says it directly: a function item cannot capture its environment, use the closure form. Using a surrounding variable is called **capturing** it, and it is the whole point of closures.

## How a closure captures: borrow, mutable borrow, move

Capturing is not free of rules, because a captured variable is still a normal Rust value with an owner. The closure has to decide: does it only look at the variable, does it change it, or does it take it over? Rust looks at what the closure body does and picks the lightest option that works:

```rust
let name = String::from("Roham");
let greet = || println!("hello {name}"); // only reads name
greet();
println!("name still usable: {name}");

let mut count = 0;
let mut inc = || count += 1; // changes count
inc();
inc();
println!("count = {count}");

let owned = String::from("moved in");
let consume = move || println!("{owned}");
consume();
```

```text
hello Roham
name still usable: Roham
count = 2
moved in
```

Line by line:

- `greet` only reads `name`, so it takes a shared reference. After the call we can still use `name` ourselves. That is the first output pair.
- `inc` changes `count`, so it takes a mutable reference. Notice that we had to write `let mut inc`: calling it changes the captured state, so the closure variable itself must be mutable. Two calls give `count = 2`.
- `consume` is written with the word `move` in front. `move` forces the closure to take ownership of everything it uses, even when a reference would have been enough. After this line `owned` belongs to the closure.

Why would you ever want `move` when a reference is enough? Because of the case where the closure leaves the function it was created in. Look at this function that returns a closure:

```rust
fn make() -> impl Fn() {
    let s = String::from("local");
    || println!("{s}")
}
```

```text
error[E0373]: closure may outlive the current function, but it borrows `s`, which is owned by the current function
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^            - `s` is borrowed here
  |     |
  |     may outlive borrowed value `s`
  |
note: closure is returned here
 --> src/bin/dropped.rs:3:5
  |
3 |     || println!("{s}")
  |     ^^^^^^^^^^^^^^^^^^
help: to force the closure to take ownership of `s` (and any other referenced variables), use the `move` keyword
  |
3 |     move || println!("{s}")
  |     ++++
```

This is the same story as the dangling reference in the lifetimes post. The closure only reads `s`, so it borrowed it. But `s` is a local variable of `make` and dies when `make` returns, while the closure is being sent out to the caller. The closure would hold a reference to something that no longer exists. The compiler says so ("may outlive borrowed value `s`") and suggests the fix: write `move`, so the closure owns `s` and takes it along.

The other side of `move` is that the original name stops working:

```rust
let s = String::from("hi");
let f = move || println!("{s}");
f();
println!("{s}");
```

```text
error[E0382]: borrow of moved value: `s`
 --> src/bin/use_after_move.rs:5:16
  |
2 |     let s = String::from("hi");
  |         - move occurs because `s` has type `String`, which does not implement the `Copy` trait
3 |     let f = move || println!("{s}");
  |             -------            - variable moved due to use in closure
  |             |
  |             value moved into closure here
4 |     f();
5 |     println!("{s}");
  |                ^ value borrowed here after move
```

It is the ordinary ownership rule again: `s` was moved into the closure on line 3, so on line 5 it is not ours to use. (I removed the `= note` and `help:` lines about cloning; they were not needed to understand the error.)

A comparison with Go: a Go closure captures variables by reference and the garbage collector keeps them alive for as long as the closure needs them, so you never think about this. In Rust you can choose, and the compiler checks the choice.

## Fn, FnMut and FnOnce: what the closure does with what it captured

Now a question that looks unrelated but is the same idea. Suppose we write a function that calls a closure twice:

```rust
fn call_twice(f: impl Fn()) { f(); f(); }

let mut count = 0;
call_twice(|| count += 1);
```

```text
error[E0594]: cannot assign to `count`, as it is a captured variable in a `Fn` closure
 --> src/bin/x_fnmut.rs:5:19
  |
1 | fn call_twice(f: impl Fn()) { f(); f(); }
  |                  --------- change this to accept `FnMut` instead of `Fn`
...
5 |     call_twice(|| count += 1);
  |     ---------- -- ^^^^^^^^^^ cannot assign
  |     |          |
  |     |          in this closure
  |     expects `Fn` instead of `FnMut`
```

`impl Fn()` in the parameter means "any closure that implements the trait `Fn`". Our closure changes `count`, so it is not that kind of closure. Rust has three {{< term "trait" "traits" >}} for closures, and which ones a closure gets depends on what its body does with the captured values:

- **`Fn`**: it only reads what it captured. It can be called any number of times.
- **`FnMut`**: it changes what it captured. It can be called many times, but only by one caller at a time.
- **`FnOnce`**: it moves something it captured out of itself (for example it returns it). After that the thing is gone, so it can be called only once.

Every closure that is `Fn` is also `FnMut` and `FnOnce`, and every `FnMut` is also `FnOnce`. The three form a ladder, and a function that asks only for `FnOnce` accepts the most closures. Here is a demo with one function for each:

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

- `call_fn` calls the closure twice, and `word.len()` is 4 each time, so the sum is `8`.
- `call_mut` calls the closure twice and each call pushes the current length of `log`, so we get `[0, 1]`. The parameter is declared `mut f` because calling an `FnMut` changes it.
- `call_once` calls it once. The closure returns `s` itself, which moves the `String` out of the closure. That is why it is only `FnOnce`.

So a function that calls its closure only once should ask for `FnOnce`, because that accepts every closure. And if you call it twice, as the error above shows, you need at least `FnMut`.

What happens if you try to call an `FnOnce` closure twice?

```rust
let s = String::from("hello");
let f = move || s; // returns s, so it can only run once
let a = f();
let b = f();
```

```text
error[E0382]: use of moved value: `f`
 --> src/bin/once_twice.rs:5:13
  |
4 |     let a = f();
  |             --- `f` moved due to this call
5 |     let b = f();
  |             ^ value used here after move
  |
note: closure cannot be invoked more than once because it moves the variable `s` out of its environment
note: this value implements `FnOnce`, which causes it to be moved when called
```

The first call hands `s` to the caller, so the closure has nothing left to give the second time. Calling an `FnOnce` closure consumes the closure itself, and that is what "`f` moved due to this call" means.

### Returning a closure

A function can also return a closure. If it returns one specific closure, write `impl Fn(...)` as the return type. If different branches return different closures, each closure has its own hidden type, so they cannot share an `impl`. In that case put them in a `Box<dyn Fn(...)>`, which is a box that holds "some closure with this signature":

```rust
fn make_adder(n: i32) -> impl Fn(i32) -> i32 {
    move |x| x + n
}

fn make_op(kind: &str) -> Box<dyn Fn(i32) -> i32> {
    match kind {
        "double" => Box::new(|x| x * 2),
        _ => Box::new(|x| x + 100),
    }
}
```

```text
15
14 107
```

`make_adder(5)` gives a closure that adds 5, and calling it with 10 gives `15`. `make_op("double")(7)` gives `14` and `make_op("other")(7)` gives `107`. `move` is needed in `make_adder` for the reason we saw above: `n` is a local variable. I explain what `Box` really is in the next post; for now read it as "a way to hold a value whose size the compiler does not know".

## Iterators: one item at a time

Closures become most useful together with iterators. An **iterator** is a value that hands out the items of a sequence one at a time. The {{< term "rust-iterator" "Iterator" >}} trait asks for just one method, `next`. Each call returns `Some(item)`, and when the items are finished it returns `None`.

You rarely call `next` yourself. A `for` loop calls it for you. A `Vec` gives you an iterator in three ways, and the difference is what the items are:

```rust
let mut v = vec![String::from("a"), String::from("b")];
for s in v.iter() { println!("iter: {s}"); }           // items are &String
for s in v.iter_mut() { s.push('!'); }                 // items are &mut String
println!("after iter_mut: {v:?}");
for s in v.into_iter() { println!("into_iter: {s}"); } // items are String, v is moved
```

```text
iter: a
iter: b
after iter_mut: ["a!", "b!"]
into_iter: a!
into_iter: b!
```

`iter()` lends each item (read only), `iter_mut()` lends each item for changing (we added `!` to both strings), and `into_iter()` gives the items themselves and consumes the vector. After the last loop `v` is gone, exactly like any other move.

## Adapters and consumers

The real power is in chaining. There are two kinds of methods on an iterator:

- **Adapters** turn one iterator into another one: `map` changes each item, `filter` keeps some of them, `take` and `skip` cut the sequence, and so on. They give you a new iterator back, not a result.
- **Consumers** run the iterator to the end and give you a result: `sum`, `collect`, `any`, `find`...

First the adapters, on `nums = [1, 2, 3, 4, 5, 6]`. Each line below is the code and the result printed by the demo:

```rust
nums.iter().map(|n| n * n)                     // [1, 4, 9, 16, 25, 36]
nums.iter().filter(|n| **n % 2 == 0)           // [2, 4, 6]
nums.iter().enumerate().take(2)                // (0, 1) and (1, 2)
names.iter().copied().zip(nums.iter())         // [("a", 1), ("b", 2), ("c", 3)]
nums.iter().skip(4)                            // [5, 6]
nums.iter().take(2).chain(nums.iter().skip(5)) // [1, 2, 6]
words.iter().flat_map(|s| s.split(' '))        // ["hi", "there", "go", "rust"]
```

In words: `map` squares each number; `filter` keeps the even ones; `enumerate` pairs each item with its position and `take(2)` stops after two; `zip` pairs two sequences item by item (here `names` is `["a", "b", "c"]`); `skip(4)` drops the first four; `chain` glues two iterators one after the other (the first two items, then everything after skipping five); `flat_map` runs a function that returns many items for each input and flattens the results into one sequence (`words` is `["hi there", "go rust"]`, and every sentence is split at the space).

One detail that confuses everyone at first is `**n` in `filter`. `nums.iter()` gives items of type `&i32`. And `filter` passes its closure a reference to the item, so the closure receives `&&i32`. Two stars get you down to the number. You can avoid that by copying the numbers first with `.copied()`, or by writing the pattern `|&&n|` in the closure parameter. I ran all three forms (`**n`, `.copied()` and `|&&n|`) in a small program, and each gives the expected result.

Now the consumers, on the same list:

```rust
nums.iter().sum::<i32>()                                      // 21
nums.iter().fold(String::new(), |acc, n| format!("{acc}{n}")) // "123456"
nums.iter().any(|&n| n > 5)                                   // true
nums.iter().all(|&n| n > 0)                                   // true
nums.iter().find(|&&n| n > 3)                                 // Some(4)
nums.iter().find(|&&n| n > 9)                                 // None
```

`sum` adds everything up. `fold` starts with a value (an empty string) and combines it with each item in turn, which is how it builds `123456`. `any` asks "is there at least one that matches?" and `all` asks "do all of them match?". `find` returns the first match wrapped in `Option`, so we get `Some(4)` in one case and `None` in the other (nothing is bigger than 9). And `collect`, which we used above, builds a collection from the items: a `Vec`, a `HashMap`, a `String`... The type you ask for decides what you get.

## Iterators are lazy

Here is the part that surprises people. Building a chain of adapters does not run anything. An adapter only describes the work; the work happens when a consumer pulls items through the chain, one by one. Let me prove it with a `println!` inside `map`:

```rust
let nums = vec![1, 2, 3];
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

The line "adapter built" comes first, and no "map sees" line appears before it. The closure only ran once `collect` started asking for items. This is called lazy evaluation, and it is also why long chains are not slow in the way you might fear: they do not build a new list at every step. Each item travels through the whole chain, one at a time.

The flip side is a trap: if you build an adapter and never consume it, nothing happens. The compiler knows this is a common mistake and warns you:

```rust
nums.iter().map(|n| println!("saw {n}"));
println!("done");
```

```text
warning: unused `Map` that must be used
 --> src/bin/x_unused.rs:3:5
  |
3 |     nums.iter().map(|n| println!("saw {n}"));
  |     ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  |
  = note: iterators are lazy and do nothing unless consumed
  = note: `#[warn(unused_must_use)]` on by default
```

The program compiles and prints only `done`; there is no "saw" line. (The compiler printed a second warning too, suggesting `for_each`, which is the right tool when you want to run a closure for its side effects.)

## Your own iterator

Because `Iterator` needs only `next`, you can make any type an iterator by writing that one method. Here is a countdown:

```rust
struct Countdown(u32);

impl Iterator for Countdown {
    type Item = u32;
    fn next(&mut self) -> Option<u32> {
        if self.0 == 0 {
            None
        } else {
            self.0 -= 1;
            Some(self.0 + 1)
        }
    }
}
```

`type Item = u32` says what the iterator produces. `next` returns `None` when the counter hits zero; otherwise it lowers the counter and returns the value from before the change. Now every adapter and consumer works on it without any extra code:

```rust
let v: Vec<u32> = Countdown(5).collect();
let s: u32 = Countdown(5).filter(|n| n % 2 == 1).map(|n| n * n).sum();
for n in Countdown(3) { println!("tick {n}"); }
```

```text
[5, 4, 3, 2, 1]
35
tick 3
tick 2
tick 1
```

The odd numbers among 5, 4, 3, 2, 1 are 5, 3 and 1; their squares are 25, 9 and 1, and the sum is `35`. And a `for` loop works on it as well, since a `for` loop just calls `next` until `None`.

## A loop and an iterator chain, side by side

Here is a small real task: count how often each word longer than two letters appears in a text, ignoring case. First with a `for` loop, then with an iterator chain:

```rust
fn loop_version(text: &str) -> Vec<(String, usize)> {
    let mut counts: HashMap<String, usize> = HashMap::new();
    for w in text.split_whitespace() {
        let w = w.to_lowercase();
        if w.len() > 2 {
            *counts.entry(w).or_insert(0) += 1;
        }
    }
    let mut out: Vec<(String, usize)> = counts.into_iter().collect();
    out.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}

fn iter_version(text: &str) -> Vec<(String, usize)> {
    let counts = text
        .split_whitespace()
        .map(|w| w.to_lowercase())
        .filter(|w| w.len() > 2)
        .fold(HashMap::new(), |mut m, w| {
            *m.entry(w).or_insert(0usize) += 1;
            m
        });
    let mut out: Vec<_> = counts.into_iter().collect();
    out.sort_by(|a, b| b.1.cmp(&a.1).then(a.0.cmp(&b.0)));
    out
}
```

Both sort the result by count (largest first) and then by word, so the output is stable. On `"the cat and The dog and a bird saw the cat"` the demo prints the first three entries and checks that the two versions agree:

```text
[("the", 3), ("and", 2), ("cat", 2)]
same result: true
```

"the" appears three times (once as "The"), "and" and "cat" twice each, and the one-letter "a" is filtered out. I find the chain easier to read once you know the vocabulary, but the loop is just as valid, and I did not benchmark either.

## Traps with closures and iterators

- **`iter()` gives references.** That is why closures in `filter` see `&&i32` and you meet patterns like `|&&n|`. If the stars bother you, use `.copied()` or `.cloned()` first.
- **`into_iter()` on a `Vec` consumes it.** The vector is moved and you cannot use it afterwards. Use `iter()` when you still need the data.
- **A closure that is only `FnOnce` cannot go where `Fn` or `FnMut` is required.** The error comes from the function you pass it to, not from the closure, as the `call_twice` example showed.
- **Do not build a `Vec` only to loop over it.** Chain the adapters and consume them directly; `collect` into a collection only when you need the collection.
- **Laziness means side effects may never run.** A `println!` inside `map` runs only if something consumes the iterator. For side effects use a `for` loop or `for_each`.

## Exercise

1. Write a function that takes `&[i32]` and returns the sum of the squares of the odd numbers, using one iterator chain.
2. Write `fn make_counter() -> impl FnMut() -> u32` that returns 1, 2, 3 on successive calls. Which keyword do you need, and why?
3. Implement `Iterator` for a `Fib` struct and print its first ten values with `take(10)`.

## What's next

In this post `Box<dyn Fn>` appeared without a real explanation. The next post, "Smart pointers: Box, Rc and RefCell in Rust", explains what a `Box` is and what the other smart pointers are for.
