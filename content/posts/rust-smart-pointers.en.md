+++
date = '2026-12-30T10:00:00+03:30'
draft = false
title = 'Smart pointers: Box, Rc and RefCell in Rust'
description = 'Rust smart pointers: Box for heap data and recursive types, Deref and Drop, Rc shared ownership, RefCell interior mutability and Weak to break cycles.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "smart-pointers", "box", "rc", "refcell", "intermediate"]
cover = { image = "/images/covers/rust-smart-pointers.png", alt = "Smart pointers: Box, Rc and RefCell in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-closures-iterators/) I returned a `Box<dyn Fn>` and promised to explain it. A **smart pointer** is a struct that acts like a pointer but also owns the data and runs code when it goes away. You already know one: `String` and `Vec` own heap memory. This post covers the three you will meet most: `Box`, `Rc` and `RefCell`. It builds on [ownership](/posts/rust-ownership/): each of these exists for a case where plain ownership and borrowing are not enough.

> Everything below was compiled and run with Rust 1.90. Output and compiler messages are copied from those runs.

## Box: one owner, data on the heap

`Box<T>` puts a value on the heap and keeps a pointer on the stack. The classic use is a recursive type. Without `Box`, a cons list cannot compile:

```rust
enum List {
    Cons(i32, List),
    Nil,
}
```

```text
error[E0072]: recursive type `List` has infinite size
2 |     Cons(i32, List),
  |               ---- recursive without indirection
help: insert some indirection (e.g., a `Box`, `Rc`, or `&`) to break the cycle
```

The compiler must know the size of `List`, and a `List` containing a `List` has no end. A `Box` has a fixed size (one pointer), so this works:

```rust
enum List {
    Cons(i32, Box<List>),
    Nil,
}
// list = Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))))
// a recursive sum over it prints: sum = 6
```

The other common use is `Box<dyn Trait>`: values of different types behind one trait, as in the closure example last time. With a `Shape` trait implemented by `Square` and `Circle`, `Vec<Box<dyn Shape>>` can hold both, and calling `area()` on each printed `4` and `3.14`. Method calls go through a vtable at runtime, much like a Go interface.

## Deref and Drop

`Box<T>` implements the **Deref** trait, so `*b` gives the inner value. The compiler also applies **deref coercion**: it follows `Deref` automatically to make types line up. A `&Box<String>` becomes `&String` and then `&str`:

```rust
fn shout(s: &str) { println!("{}!", s.to_uppercase()); }

let b = Box::new(String::from("hello"));
shout(&b); // &Box<String> -> &String -> &str
```

It works for your own types too: implement `Deref` with `type Target = String` and `shout(&w)` and `w.len()` both compile. **Drop** is the other half: its `drop` runs at the end of scope, in reverse order of declaration. I created `wrapped`, then `a`, then `b`, each printing in `drop`:

```text
end of main
drop b
drop a
drop wrapped
```

## Rc: shared ownership

Sometimes a value really has several owners, such as a node shared by two lists. `Rc<T>` (reference counted) allows that; the value is freed when the last owner goes away. `Rc::clone` only increments a counter, it does not copy the data:

```rust
let a = Rc::new(String::from("shared"));
println!("after new: {}", Rc::strong_count(&a));
let b = Rc::clone(&a);
println!("after clone b: {}", Rc::strong_count(&a));
{
    let c = Rc::clone(&a);
    println!("in scope: {}", Rc::strong_count(&a));
}
println!("after scope: {}", Rc::strong_count(&a));
drop(b);
println!("after drop(b): {}", Rc::strong_count(&a));
```

```text
after new: 1
after clone b: 2
in scope: 3
after scope: 2
after drop(b): 1
```

An `Rc` gives you only shared (`&`) access. And it is not thread safe, because its counter is not atomic. The compiler enforces that:

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
  = help: within `{closure@src/bin/rc_thread.rs:6:27: 6:34}`, the trait `Send` is not implemented for `Rc<i32>`
note: required by a bound in `spawn`
```

For threads, the standard library has `Arc`, the atomic version. We will not use it here.

## RefCell: interior mutability

Borrowing rules are normally checked at compile time. **RefCell** moves the check to runtime, so you can mutate through a shared reference. This is called **interior mutability**. `borrow()` and `borrow_mut()` follow the same rules (many readers or one writer), but a violation is a panic instead of a compile error:

```rust
let c = RefCell::new(vec![1]);
let _first = c.borrow_mut();
match c.try_borrow_mut() {
    Ok(_) => println!("got it"),
    Err(e) => println!("try_borrow_mut failed: {e}"),
}
let _second = c.borrow_mut();
```

```text
try_borrow_mut failed: RefCell already borrowed

thread 'main' panicked at src/bin/refcell_panic.rs:10:21:
RefCell already borrowed
```

(Older tutorials show `already borrowed: BorrowMutError`; in 1.90 the text is the one above.) `try_borrow_mut` returns a `Result`, so you can handle the conflict instead of crashing.

## Rc and RefCell together

`Rc` gives many owners but read-only access; `RefCell` gives mutation. Combined, `Rc<RefCell<T>>` is shared mutable state in single-threaded code:

```rust
let counter = Rc::new(RefCell::new(Counter { hits: 0 }));
let a = Rc::clone(&counter);
let b = Rc::clone(&counter);
let inc_a = move || a.borrow_mut().hits += 1;
let inc_b = move || b.borrow_mut().hits += 10;
inc_a(); inc_b(); inc_a();
println!("hits = {}, owners = {}", counter.borrow().hits, Rc::strong_count(&counter));
```

```text
hits = 12, owners = 3
```

## Reference cycles and Weak

If two `Rc`s point at each other, neither count reaches zero. In my `cycle` demo, `a` and `b` each held the other, both counts were `2` at the end of `main`, and no `drop` line was ever printed. That is a memory leak, and Rust considers it safe code.

The fix is **Weak**: a pointer that does not own. `Rc::downgrade` makes one, and `upgrade()` returns `Option<Rc<T>>`, which is `None` once the value is gone. In a tree, parents own children with `Rc` and children point back with `Weak`:

```rust
struct Node {
    name: &'static str,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

```text
leaf parent = None
root: strong=1 weak=1
leaf: strong=2 weak=0
leaf parent = Some("root")
drop root
leaf parent = None
leaf: strong=1 weak=0
drop leaf
```

When `root` leaves its scope it is dropped even though `leaf` still points to it, because only a `Weak` does. Afterwards `upgrade()` gives `None`.

## A few things to watch

- Prefer plain ownership and borrowing first. These types are for cases the borrow checker cannot prove, not a way around it.
- `RefCell` moves errors from compile time to runtime. Keep `borrow_mut` guards short-lived, or use `try_borrow_mut`.
- `Rc::clone(&a)` is cheap and makes the ownership obvious; I prefer it to `a.clone()`.
- `Rc` and `RefCell` are single-threaded. For threads, use `Arc` and `Mutex`.
- In Go, the garbage collector makes shared pointers implicit, so you never count owners. Rust makes you choose, and pays no GC cost.

## Exercise

1. Add a `Cons` variant holding `Rc<List>` so two lists share the same tail, and print `Rc::strong_count` of the tail.
2. Make a `Rc<RefCell<Vec<String>>>` log shared by two closures and print it at the end.
3. Trigger the `RefCell` panic on purpose, then replace it with `try_borrow_mut`.

## What's next

Next we cover testing and documentation in Rust.
