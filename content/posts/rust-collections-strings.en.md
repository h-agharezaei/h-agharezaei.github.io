+++
date = '2026-11-28T10:00:00+03:30'
draft = false
title = 'Collections and strings in Rust'
description = 'Rust collections and strings: Vec, HashMap, HashSet, BTreeMap, String and &str, bounds panics, borrow errors, UTF-8 byte vs char counts and a word counter.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "collections", "vec", "hashmap", "string"]
cover = { image = "/images/covers/rust-collections-strings.png", alt = "Collections and strings in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-structs-enums-pattern-matching/) we modeled our own types with structs and enums. Now the standard library types that hold many values: **Vec**, **HashMap** and friends, and the two string types. They are where ownership and borrowing stop being theory, because the compiler will refuse code that looks perfectly reasonable in Go or Node.js. We will run code and read the actual messages.

> Everything below was compiled and run with Rust 1.90 as a local example.

## Vec

`Vec<T>` is a growable array on the heap, the closest thing to a Go slice you will use daily.

```rust
let mut v = vec![10, 20, 30];
v.push(40);
println!("{:?} len={}", v, v.len());
println!("get(1) = {:?}, get(9) = {:?}", v.get(1), v.get(9));
for x in &v {
    print!("{x} ");
}
println!();
for x in &mut v {
    *x += 1;
}
println!("{:?}", v);
```

```text
[10, 20, 30, 40] len=4
get(1) = Some(20), get(9) = None
10 20 30 40 
[11, 21, 31, 41]
```

`v[i]` assumes the index is valid; `v.get(i)` returns an `Option` and lets you decide. Indexing out of bounds panics. With `v[v.len() + 6]` on that 4-element vector:

```text
thread 'main' panicked at src/bin/vecs.rs:15:21:
index out of bounds: the len is 4 but the index is 10
```

Iterating with `&v` borrows the vector read-only; `&mut v` borrows it mutably so you can change elements through `*x`. Iterating with plain `v` would move the vector into the loop.

## The borrow checker meets Vec

Here is the classic one. Take a reference to the first element, push, then use the reference:

```rust
let mut v = vec![1, 2, 3];
let first = &v[0];
v.push(4);
println!("{first}");
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> src/bin/vec_borrow.rs:4:5
  |
3 |     let first = &v[0];
  |                  - immutable borrow occurs here
4 |     v.push(4);
  |     ^^^^^^^^^ mutable borrow occurs here
5 |     println!("{first}");
  |                ----- immutable borrow later used here
```

`push` may reallocate the buffer, which would leave `first` pointing at freed memory. Go has the mirror-image problem (a stale slice after `append`) and lets it compile; Rust rejects it. Fix it by finishing with `first` before pushing, or by copying the value out.

## HashMap, HashSet and BTreeMap

```rust
let mut ages: HashMap<String, u32> = HashMap::new();
ages.insert("ali".to_string(), 30);
ages.insert("sara".to_string(), 25);
println!("{:?} {:?}", ages.get("sara"), ages.get("nobody"));
ages.insert("sara".to_string(), 26); // replaces the old value
*ages.entry("reza".to_string()).or_insert(0) += 41;
*ages.entry("reza".to_string()).or_insert(0) += 1;
println!("sara={} reza={} len={}", ages["sara"], ages["reza"], ages.len());
```

```text
Some(25) None
sara=26 reza=42 len=3
```

`get` returns an `Option`, so "missing" and "zero" are different values by construction. `entry(key).or_insert(default)` is the idiom for "create if absent, then update": it returns a mutable reference to the value, which we increment with `*`.

Iteration order is not specified. I inserted keys 0 to 7 and printed `keys()` in three separate runs:

```text
[3, 5, 6, 2, 4, 0, 1, 7]
[2, 6, 1, 7, 5, 4, 0, 3]
[0, 7, 3, 6, 2, 4, 1, 5]
```

A `HashSet<T>` is a map with only keys; `insert` returns `false` if the value was already there. A `BTreeMap` keeps keys sorted, at the price of slower lookups than hashing:

```rust
let mut seen = HashSet::new();
for w in ["a", "b", "a", "c", "b"] {
    if !seen.insert(w) {
        println!("duplicate {w}");
    }
}
println!("unique = {}", seen.len());

let mut sorted = BTreeMap::new();
for (k, v) in [("zed", 1), ("amir", 2), ("mina", 3)] {
    sorted.insert(k, v);
}
println!("{:?}", sorted);
```

```text
duplicate a
duplicate b
unique = 3
{"amir": 2, "mina": 3, "zed": 1}
```

## String and &str

`String` owns a growable UTF-8 buffer; `&str` is a borrowed view into UTF-8 text (a literal, or part of a `String`). Functions that only read text should take `&str`. Both are always valid UTF-8, and `len()` counts bytes:

```rust
for w in ["hello", "سلام", "🚀"] {
    println!("{w} bytes={} chars={}", w.len(), w.chars().count());
}
for (i, c) in "سلام".char_indices() {
    print!("{i}:{c} ");
}
println!();
println!("{:?}", "سلام".bytes().take(4).collect::<Vec<u8>>());
println!("{:?}", &"سلام"[0..2]);
```

```text
hello bytes=5 chars=5
سلام bytes=8 chars=4
🚀 bytes=4 chars=1
0:س 2:ل 4:ا 6:م 
[216, 179, 217, 132]
"س"
```

Same numbers as in Go: 8 bytes, 4 characters. Here `chars()` yields Unicode scalar values, and `bytes()` the raw bytes (216 is the first byte of `س`). That is why `s[0]` is not allowed:

```rust
let s = String::from("salam");
let c = s[0];
```

```text
error[E0277]: the type `str` cannot be indexed by `{integer}`
 --> src/bin/str_index.rs:3:15
  |
3 |     let c = s[0];
  |               ^ string indices are ranges of `usize`
  |
  = note: you can use `.chars().nth()` or `.bytes().nth()`
```

Rust makes you say whether you want a byte or a character. Range slicing like `&s[0..2]` is allowed, but the range must fall on character boundaries; here bytes 0 to 2 happen to be exactly `س`.

To build and split text:

```rust
let mut s = String::from("go");
s.push_str("lang");
s.push('!');
let t = format!("{s}-{}", 2026);
println!("{s} {t}");
println!("{:?}", "  go   is \t fun\n".split_whitespace().collect::<Vec<_>>());
```

```text
golang! golang!-2026
["go", "is", "fun"]
```

`format!` returns a new `String` and does not consume its arguments.

## Small program: word frequency

Same task as in the Go post, same input:

```rust
let text = "the quick brown fox jumps over the lazy dog the fox";
let mut counts: HashMap<String, u32> = HashMap::new();
for w in text.to_lowercase().split_whitespace() {
    *counts.entry(w.to_string()).or_insert(0) += 1;
}
let mut entries: Vec<(&String, &u32)> = counts.iter().collect();
entries.sort_by(|a, b| b.1.cmp(a.1).then(a.0.cmp(b.0)));
for (word, n) in entries {
    println!("{word:<6} {n}");
}
```

```text
the    3
fox    2
brown  1
dog    1
jumps  1
lazy   1
over   1
quick  1
```

As in Go, the map order is unspecified, so we collect the entries into a `Vec` and sort by count descending, then alphabetically. The `entry` API replaces Go's `counts[w]++`, which works there because a missing key reads as zero. In Rust a missing key is explicit.

## A few things to watch

- `v[i]` panics when out of bounds; use `get` for input you do not control.
- You cannot hold a reference into a `Vec` across a `push`; the compiler enforces this.
- Never rely on `HashMap` order. Use `BTreeMap` or sort when you need stable output.
- `len()` on a string is bytes; use `chars().count()` for characters. Even a "character" is not always what a reader sees as one letter, since combining marks exist.
- Take `&str` in function parameters; return `String` when you create new text.
- Compared with Go: a Go slice header can alias and silently share memory, while a `Vec` has a single owner, so the sharing bugs from the Go post become compile errors. The cost is that you sometimes restructure code to satisfy the borrow checker.

## Exercise

1. Change the word counter to use `BTreeMap` and notice what ordering you get for free. You still need a sort for count order.
2. Read a Persian sentence, split it with `split_whitespace`, and print the `chars().count()` of each word.
3. Make the `vec_borrow` example compile by copying the first element (`let first = v[0];`) instead of borrowing it.

## What's next

Many of the operations here returned `Option`, and real programs also fail in other ways. Next is error handling with `Result` and `Option` in Rust.
