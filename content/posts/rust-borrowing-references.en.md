+++
date = '2026-11-14T10:00:00+03:30'
draft = false
title = 'Borrowing and references in Rust'
description = 'Rust borrowing and references with runnable code: &T and &mut T, the readers-or-one-writer rule, NLL, dangling references, slices and real compiler errors.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "borrowing", "references"]
cover = { image = "/images/covers/rust-borrowing-references.png", alt = "Borrowing and references in Rust", hiddenInSingle = true }
+++

Imagine you own a book and a friend wants to read one page of it. There are two ways: give them the book, so it is no longer yours, or just lend it and get it back. In [Ownership in Rust](/posts/rust-ownership/) we saw only the first way: when we passed a `String` to a function, ownership went with it, and the function had to give it back so we could use it again. At the end of that post I said this back and forth is clumsy. The second way, lending, is what {{< term "borrowing" "borrowing" >}} is.

The core idea is simple: instead of the value itself, you give the function a **reference**. A reference is an address that points to the value. The function sees the value through it (and in one special case, changes it), but ownership stays where it was, and the owner is still the one responsible for freeing the memory. In this post we look at the two kinds of reference, the single rule that governs them, and the compiler errors you will meet while learning. I show each rule first through the error the compiler gives, so the reason is clear.

> I compiled and ran all the code below with Rust 1.90, and the outputs and errors come from those runs. I removed a few side lines of the error messages (like "For more information...") to keep them short. I also wrote two small programs that exist only to show `*` and one fix.

## Shared and mutable references

There are two kinds of reference. `&T` is a **shared reference**: through it you can read the value but not change it. `&mut T` is a **mutable reference**: you can read it and also change the value. Making either is called "borrowing". `&s` makes a shared reference to `s`, and `&mut s` makes a mutable one.

The program below has two functions: `length` only reads the length of the string, and `add_exclaim` appends a `!` to it. In `main` we call both, and at the end we make two shared references at the same time:

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

```text
salam has 5 bytes
salam!
salam! salam!
```

First line: `length(&s)` only borrowed and returned the length. Afterwards `s` is still ours and we can print it, without the function giving anything back and without a tuple. Second line: `add_exclaim(&mut s)` changed the string (a `!` was added), and `s` in `main` sees that change, because the function worked on the string itself, not on a copy. Third line: two shared references at the same time are no problem.

Two notes about the code:

- To write `&mut s`, the variable itself must be declared `mut` (`let mut s`). You cannot take a mutable reference to something immutable.
- You "unwrap" a reference with `*` to reach the value itself. When you call a method (`s.len()`) Rust does this for you, but in an assignment you must write it. The small program below shows both:

```rust
fn main() {
    let mut x = 10;
    let r = &mut x;
    *r += 5;
    println!("{x}");

    let s = String::from("salam");
    let rs = &s;
    println!("{} {}", rs.len(), (*rs).len());
}
```

```text
15
5 5
```

`*r += 5` says "add 5 to what `r` points to", and `x` became 15. On the last line `rs.len()` and `(*rs).len()` do the same thing and both give 5.

## Many readers or one writer

Now let us ask: what happens if we take two mutable references to one value? In Go that is no problem, but see what Rust says:

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

Let us read the message. The title says you cannot borrow `s` as mutable more than once at a time. Three labels tell the story: the first borrow on line 3, the second borrow on line 4 (the problematic one), and "first borrow later used here" on line 5. That last label is the most important. It shows why the first borrow is still alive: `a` is used again after the second borrow. If `a` were not used any more, there would be no problem (we see this in the next section).

Now the second case: a reader that is still alive while we change the value. (`vec![1, 2, 3]` makes a `Vec`, a growable list; we will say more about it later.)

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

This time a shared reference (`first`, to the first element) and a mutable reference (`v.push` takes `&mut v` behind the scenes to change `v`) conflict. This case is more interesting. Why is it dangerous? `push` may run out of room and move the whole vector buffer to a bigger place. Then `first` would point to the old place, which has been freed. That is "use of freed memory", which in C is a bug and a security hole. Rust rejects the program before it reaches that moment.

From these two errors we can state the borrowing rule: **at any time you can have any number of `&T`, or exactly one `&mut T`, but never both.** In plain words: many readers or one writer. The reason is that while someone is reading, nobody should change the data under their feet. The compiler has a part called the {{< term "borrow-checker" "borrow checker" >}} that verifies this rule at compile time.

## A borrow ends at its last use

You might think: so once I take a shared reference, I cannot change anything until the end of the scope. Fortunately that is not so. A borrow does not last until the closing brace; it lasts until the last time the reference is used. This feature is called **non-lexical lifetimes** (NLL for short). The program below takes a shared borrow and then a mutable borrow of the same variable, and it compiles:

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

`r` was used for the last time in the first `println!`. After that the borrow is over, so `&mut s` is allowed. If you add a `println!("{r}")` after `push_str`, `r` becomes alive again and you get the same E0502 error as before. The practical result: when the compiler objects, look for the label "later used here". It points at the use that keeps the borrow alive. Often the fix is to make the change before taking the reference. For example, if in the `Vec` program above we move `v.push(4)` before `let first = &v[0]`, the program compiles and prints `first = 1`.

## A reference must not dangle

A reference must never outlive the value it points to, otherwise it points to memory that no longer exists. Such a reference is called **dangling**. The function below tries to return a reference to one of its own local variables:

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

The title talks about something called a {{< term "lifetime" "lifetime" >}}, which is how long a reference stays valid. You do not need the details yet. The first `help` explains the whole thing: the function returns a reference, but there is no value for this reference to be borrowed from (because `s` is created inside the function itself). The compiler's second suggestion is the right fix: return the `String` itself and let ownership move out.

If you add a lifetime name just to silence E0106 (`fn dangle<'a>() -> &'a String`), you reach a deeper error that states the real cause:

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/dangle2.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function
```

`s` is dropped when the function ends (the third rule of ownership), so the reference would point to nothing. We will look at lifetimes more seriously later in this series.

## Slices: a borrowed view

There are two special references you will use a lot. `&str` is a borrowed view of the text of a string (all of it or a part of it), and `&[T]` is a borrowed view of a run of elements. These are references too, with the same rules. Their benefit is that a function taking them accepts more inputs:

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

`first_word` returns the first word of the text (it splits the text on spaces and takes the first piece). It works for a `String` (with `&text`) and for a literal like `"hello rust"`. (According to the Rust docs, a `&String` is converted to `&str` automatically; this conversion is called deref coercion.) `sum` works for a whole `Vec` (1+2+3+4+5 = 15) and for a range of it: `&v[1..4]` means the elements at index 1 to 3, so 2+3+4 = 9. For this reason, prefer `&str` and `&[T]` over `&String` and `&Vec<T>` in function parameters.

## Reading borrow errors

- **A reference is not a pointer you manage yourself.** You do not free it, and in safe Rust it is never null.
- **"Many readers or one writer" applies per value and per moment.** Back-to-back borrows are fine with NLL once the first one is no longer used.
- **Look at the labels of the error, not only the title.** "first borrow occurs here" and "later used here" show which two lines conflict.
- **If a borrow error is hard to fix,** shortening the life of the reference (stop using it before the change) or returning an owned value usually helps. `.clone()` is the last resort.
- **Comparison with Go.** In Go you can hold several pointers to one value and change it through any of them, and the compiler does not stop you. If goroutines do it without coordination, you get a data race, and finding it is up to you (the race detector helps). Rust moves this check to compile time, at the price of wrestling with the compiler at first.

## Exercise

1. Write `fn append_twice(s: &mut String, word: &str)` that appends `word` to `s` twice, and call it from `main`.
2. Reproduce the E0502 error with a `Vec` and fix it by moving the `push` before taking the reference.
3. Write `fn largest(xs: &[i32]) -> i32` and call it once with a whole `Vec` and once with a sub-slice.

## What's next

"Structs, enums and pattern matching in Rust". So far our data has been single values and collections. Now that we know how to lend a value, we build our own types and branch on them.
