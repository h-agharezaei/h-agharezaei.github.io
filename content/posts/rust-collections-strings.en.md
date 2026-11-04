+++
date = '2026-11-28T10:00:00+03:30'
draft = false
title = 'Collections and strings in Rust'
description = 'Rust collections and strings: Vec, HashMap, HashSet, BTreeMap, String and &str, bounds panics, borrow errors, UTF-8 byte vs char counts and a word counter.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "collections", "vec", "hashmap", "string"]
cover = { image = "/images/covers/rust-collections-strings.png", alt = "Collections and strings in Rust", hiddenInSingle = true }
+++

Here is code that looks perfectly normal in Go or Node.js. We have a `Vec` (a list that can grow), we point at its first element, we add a new value to the end, and then we use the pointer again. In Rust this program does not compile. Why? Because adding a value can move the whole list to a different place in memory and leave our pointer aimed at empty space.

This example shows why the types that hold several values matter so much in Rust: this is where {{< term "ownership" "ownership" >}} and {{< term "borrowing" "borrowing" >}} leave the theory and meet everyday work. In this post we go through the most common ones: `Vec` for lists, `HashMap`, `HashSet` and `BTreeMap` for lookup by key, and the two string types, `String` and `&str`. They all hold the structs and enums we built in the [previous post](/posts/rust-structs-enums-pattern-matching/). For each one we run the code and read the real messages. If you come from Go, it helps to compare with [Slices, maps and strings in Go](/posts/go-slices-maps-strings/).

> I compiled and ran all the code below with Rust 1.90 as a local example, and the outputs come from those runs. From the `str_index` error I removed a few side lines of help text, and from the other errors the "For more information…" line.

## Vec: a list that grows

`Vec<T>` is an array that can grow, and its elements are stored on the {{< term "heap-memory" "heap" >}}. `T` is the type of the elements, so `Vec<i32>` is a list of integers. It is the closest thing to the slice in Go that you use every day.

The program below creates a `Vec`, adds an element at the end, reads an element in two ways, and then walks over the list once read-only and once changing the elements:

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

The first line shows the list and its length. The second line shows the difference between the two ways of reading: `v.get(1)` returns an `Option`. The second element exists, so we get `Some(20)`; index 9 does not exist, so we get `None` and nothing breaks. The third line is the walk with `&v`, which borrows the list for reading only. In the next loop `&mut v` borrows the list for changing: each `x` is a mutable reference to one element, `*x` reaches the element itself, and we add one to it. The last line shows the result. If you write the loop with `v` itself (`for x in v`), the list is moved into the loop and is no longer available afterwards.

The second way to read is `v[i]`. It assumes the index is valid, and if it is not, the program panics. I added one line to this program that reads `v[v.len() + 6]` (the list has four elements):

```text
thread 'main' panicked at src/bin/vecs.rs:15:21:
index out of bounds: the len is 4 but the index is 10
```

The message is precise: the length is 4 and the index is 10. In practice: use `get` for an index that comes from outside and handle the `None` yourself, and keep `v[i]` for places where you are sure the index is valid.

## When the borrow checker meets Vec

Now back to the example at the start. We take a reference to the first element, `push`, and then use the reference:

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

The three labels tell the whole story. Line 3: with `&v[0]` a shared (read-only) borrow of `v` started. Line 4: `push` needs a mutable borrow. Line 5: but `first` is still used, so the first borrow is still alive. The rule from [Borrowing and references in Rust](/posts/rust-borrowing-references/) (many readers or one writer) does not allow both at once.

The reason is the one I gave at the start. When a `Vec` runs out of room, it takes a bigger buffer, copies the elements into it and frees the old buffer. At that moment `first` would point into freed memory. Go has a similar problem (a stale slice that still points to the old array after an `append`) and it compiles; Rust rejects it right away. The fix is usually simple: finish with `first` before the `push`, or take a copy of the value instead of a reference (`let first = v[0];`, which works for numbers because they are `Copy`).

## HashMap, HashSet and BTreeMap

When you find data by a key and not by a position, you reach for a map. `HashMap<K, V>` connects each key to a value, and looking up a key is fast in the usual case. This program stores the ages of a few people:

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

First line: like `Vec`, `get` returns an `Option`. We find "sara", and for "nobody" we get `None`. So "the key does not exist" and "its value is zero" are two different things and never get mixed up. Then `insert` with a key that already exists replaces the old value (sara's age goes from 25 to 26).

The next two lines show `entry`, which is made for "if it is missing, create it, then update it". `entry("reza")` means "look at the place for this key". `or_insert(0)` puts 0 there if the key was missing, and in both cases returns a mutable reference to the value. With `*` we reach the value itself and add to it. The first time reza did not exist, started from 0 and got 41; the second time one was added and it became 42. The last line says we have three keys.

One important thing about `HashMap`: the iteration order is not defined. To see it, I inserted the keys 0 to 7 and printed `keys()` in three separate runs:

```text
[3, 5, 6, 2, 4, 0, 1, 7]
[2, 6, 1, 7, 5, 4, 0, 3]
[0, 7, 3, 6, 2, 4, 1, 5]
```

The order is different every time. It is random, and if you run it yourself you will probably see yet another order, so do not rely on any particular order. If you want output in a fixed order, either sort the keys or use `BTreeMap`, which comes next.

`HashSet<T>` is basically a map with only keys, and it is good for the question "have I seen this value before?". `insert` returns `false` when the value was already there. `BTreeMap` is like `HashMap` but always keeps its keys sorted. In general its lookups are slower than a hash lookup, and that is the price of being ordered. The program below shows both:

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

In the first loop, when the second "a" and the second "b" arrive, `insert` returns `false` and we print "duplicate". At the end three unique values are left. In the second part we inserted the keys in the order zed, amir, mina, but `BTreeMap` prints them alphabetically.

## String and &str

There are two string types, and at first they are confusing. If you remember the ownership post, `String` owns a growable buffer on the heap. `&str` is a borrowed view of text that is stored somewhere else: a literal inside the program (like `"hello"`) or a part of a `String`. For this reason a function that only reads text should take `&str`, because it accepts both a `String` and a literal. Both are always valid {{< term "utf-8" "UTF-8" >}}. UTF-8 means each character takes one to four bytes: English letters one byte and most Persian letters two. As a result `len()` counts bytes, not characters.

The program below counts three words (English, Persian, an emoji) in two ways, and then prints the letters of "سلام" with their positions:

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

The first three lines: `len()` is the number of bytes and `chars().count()` is the number of characters. For "hello" both are 5. "سلام" has four characters but eight bytes. The rocket emoji is one character but four bytes. These are the same numbers as in Go (8 bytes and 4 characters). The `char_indices` line shows at which byte each letter starts, and since each letter is two bytes, the numbers go up by two: 0, 2, 4, 6. The next line shows the first four bytes: `216, 179` are the bytes of "س" and `217, 132` are the bytes of "ل". The last line shows the slice `[0..2]`, that is bytes 0 to 2, which is exactly the letter "س".

This is why writing `s[0]` on a string is not allowed. You may mean "the first letter", but the first byte is something else:

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

The compiler makes you say what you want: a byte (`.bytes().nth(0)`) or a character (`.chars().nth(0)`). Slicing with a range, like `&s[0..2]`, is allowed, but the range must fall on character boundaries. If you cut in the middle of a character, according to the documentation the program panics. In the example above, bytes 0 to 2 were exactly "س", which is why we got an answer.

To build and split text, here are a few common operations together:

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

`push_str` adds a piece of text and `push` adds one character to the end of the `String` (so `s` must be `mut`). `format!` creates a new `String` and does not consume `s`, which is why we can still print `s`. `split_whitespace` splits the text on any space, tab or newline and drops the extra whitespace.

## A small program: word frequency

Let us now use several of these together. It is the same word-count program as in the Go post, with the same input: we lowercase the text, split it into words with `split_whitespace`, count with `entry`, and since a map has no defined order, we put the result in a `Vec` and sort it: first by count (descending), and alphabetically when counts are equal.

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

"the" appears three times and "fox" twice; the rest once, in alphabetical order. The difference from Go is that there `counts[w]++` was enough, because a missing key reads as zero. In Rust this "if it is missing" is explicit, and `entry(...).or_insert(0)` writes it down. It is a little more code, but nothing is hidden.

## Surprises you should know

- `v[i]` panics when out of range. For an index you do not control, use `get`.
- While you hold a reference into a `Vec` and still use it, you cannot `push`. `push` may move all the elements, and the compiler checks this for you.
- Do not rely on `HashMap` order, because it differs from run to run. For a stable output use `BTreeMap` or sort.
- `len()` on a string counts bytes. For the number of characters use `chars().count()`. Even a "character" is not always what a reader sees as one letter, because some letters are built from several characters (for example a letter plus a combining mark).
- Take `&str` in function parameters, and return `String` when you create new text.
- In Go a slice header can be aliased and silently share memory, but a `Vec` has one owner. The sharing bugs from the Go post become compile errors here. The price is that sometimes you have to reorganise code to make the borrow checker happy.

## Exercise

1. Write the word counter with `BTreeMap` and see which order you get for free. To order by count you still need a sort.
2. Read a Persian sentence, split it with `split_whitespace`, and print `chars().count()` for each word.
3. Make the `vec_borrow` example compile by copying the first element (`let first = v[0];`) instead of borrowing it.

## What's next

Many of the operations above returned an `Option`, and real programs fail in other ways too. That is why the next step is "Error handling with Result and Option in Rust".
