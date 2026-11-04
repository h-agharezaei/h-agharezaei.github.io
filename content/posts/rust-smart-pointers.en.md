+++
date = '2026-12-30T10:00:00+03:30'
draft = false
title = 'Smart pointers: Box, Rc and RefCell in Rust'
description = 'Rust smart pointers: Box for heap data and recursive types, Deref and Drop, Rc shared ownership, RefCell interior mutability and Weak to break cycles.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "smart-pointers", "box", "rc", "refcell", "intermediate"]
cover = { image = "/images/covers/rust-smart-pointers.png", alt = "Smart pointers: Box, Rc and RefCell in Rust", hiddenInSingle = true }
+++

Rust's ownership rule is simple: every value has one owner, and when the owner goes out of scope the value is dropped. Most of the time that is exactly what you want. But a few situations do not fit it. A type that contains itself, like a linked list, has no fixed size. A value that two parts of the program both need to own has no single owner. And a value that you need to change while several parts of the code hold a shared reference to it breaks the borrowing rules. For these cases the standard library has three small tools: `Box`, `Rc` and `RefCell`. Each one is a {{< term "smart-pointer" "smart pointer" >}}, and this post explains what that means, what problem each tool solves and what it costs.

It builds on [Ownership in Rust](/posts/rust-ownership/) and [Borrowing and references in Rust](/posts/rust-borrowing-references/), and it explains the `Box<dyn Fn>` that I used without explanation in the [previous post](/posts/rust-closures-iterators/) on closures.

> Everything below was compiled and run with Rust 1.90 (the same version as the original run). Output and compiler messages come from those runs. A few small programs (an `Rc` that is modified, a mutation through a shared reference, and a `RefCell` used through a shared reference) were not in the original demo; I wrote them for this post and ran them separately. I removed the "For more information..." line and some `note:` lines from the messages.

## What a smart pointer is

A plain reference (`&T`) only points at a value that somebody else owns. A **smart pointer** is a struct that points at a value and also owns it. It behaves like a reference (you can write `*x` to reach the value) but it also runs some code when it is dropped. You have already used two without the name: `String` owns text on the heap and frees it when it goes away, and `Vec<T>` does the same for its items.

Two words that I use below. The **stack** is where function variables of a known, fixed size live, and it is cleaned automatically when the function returns. The **heap** is a larger area where a value can have any size and live as long as someone owns it. A pointer to a heap value is a small, fixed-size thing that can sit on the stack.

## Box: put a value on the heap

`Box<T>` is the simplest smart pointer. It puts a value on the heap and keeps a pointer to it on the stack. It has exactly one owner, so the ownership rules stay the same: when the `Box` is dropped, the heap value is freed.

Why would you want that? The classic reason is a type that contains itself. Take a linked list in the style of "cons lists": a list is either a value followed by another list, or the end:

```rust
enum List {
    Cons(i32, List),
    Nil,
}
```

```text
error[E0072]: recursive type `List` has infinite size
 --> src/bin/cons_bad.rs:1:1
  |
1 | enum List {
  | ^^^^^^^^^
2 |     Cons(i32, List),
  |               ---- recursive without indirection
  |
help: insert some indirection (e.g., a `Box`, `Rc`, or `&`) to break the cycle
  |
2 |     Cons(i32, Box<List>),
  |               ++++    +
```

Rust needs to know the size of every type at compile time. How big is a `List`? It holds an `i32` and another `List`, which holds an `i32` and another `List`, and so on without end. The message says "infinite size" and "recursive without indirection". "Indirection" means: do not store the inner list here, store a pointer to it. A `Box` is exactly that, and a pointer has a fixed size no matter what it points to:

```rust
enum List {
    Cons(i32, Box<List>),
    Nil,
}
```

Now `Cons(1, Box::new(Cons(2, Box::new(Cons(3, Box::new(Nil))))))` compiles. In the demo I added a recursive `sum` method that adds the numbers up, and it prints:

```text
sum = 6
```

The second common use is `Box<dyn Trait>`. Sometimes you want one collection of values of different types that share a behaviour. A `Vec` needs all its items to have the same size, and `Square` and `Circle` are different types. Boxing them and calling them by their trait solves that. In the demo, a `Shape` trait has an `area` method, and `Square` and `Circle` implement it:

```rust
let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Square(2.0)), Box::new(Circle(1.0))];
for s in &shapes {
    println!("area = {}", s.area());
}
```

```text
area = 4
area = 3.14
```

`dyn Shape` means "some type that implements `Shape`, decided at run time". Each box remembers which type it holds, and the call to `area()` is routed to the right method when the program runs. That is the same idea as an interface value in Go. This is also what `Box<dyn Fn(i32) -> i32>` was in the closures post: a box holding "some closure with this signature".

## Deref and Drop: what makes it "smart"

Two traits make a type behave like a smart pointer, and you can implement both yourself.

**`Deref`** lets you write `*b` to get the value inside. It also enables something the compiler does for you, **deref coercion**: when a function wants a `&str` and you pass a `&Box<String>`, the compiler follows `Deref` step by step (`&Box<String>` to `&String` to `&str`) until the types match. Here is a small function that takes `&str`, and a `Wrapper` type I wrote that implements `Deref` with `type Target = String`:

```rust
fn shout(s: &str) { println!("{}!", s.to_uppercase()); }

let b = Box::new(String::from("hello"));
shout(&b); // &Box<String> -> &String -> &str

let w = Wrapper(String::from("wrapped"));
shout(&w);
println!("len = {}", w.len());
```

```text
HELLO!
WRAPPED!
len = 7
```

Both calls to `shout` compile even though neither argument is a `&str`. And `w.len()` works because the compiler looks through `Wrapper` to the `String` inside.

**`Drop`** is the other half. Its `drop` method runs automatically when the value goes out of scope. That is how a `Box` frees its heap memory, and how a file closes itself. Here `Wrapper` implements `Drop` and prints a line, so we can see when it happens. The demo creates `w` (the one called "wrapped"), then `_a`, then `_b`, and finishes `main`:

```text
end of main
drop b
drop a
drop wrapped
```

First "end of main" is printed, and then the values are dropped in the reverse order of their creation: `b`, then `a`, then `wrapped`. This reverse order is the rule: the last created is the first dropped, so a value can safely depend on the ones created before it.

## Rc: several owners

`Box` has one owner. Sometimes a value really has several: think of a node that two different lists both point to. Whoever drops last should free it, and nobody may free it earlier. `Rc<T>` ("reference counted") does this. It keeps a counter of owners, and the value is freed when the counter goes to zero. `Rc::clone` does not copy the data; it only adds one to the counter and gives you another pointer to the same data:

```rust
let a = Rc::new(String::from("shared"));
println!("after new: {}", Rc::strong_count(&a));
let b = Rc::clone(&a);
println!("after clone b: {}", Rc::strong_count(&a));
{
    let c = Rc::clone(&a);
    println!("in scope, c = {c}: {}", Rc::strong_count(&a));
}
println!("after scope: {}", Rc::strong_count(&a));
drop(b);
println!("after drop(b): {}", Rc::strong_count(&a));
```

```text
after new: 1
after clone b: 2
in scope, c = shared: 3
after scope: 2
after drop(b): 1
```

The count goes 1 (just `a`), 2 (after `b`), 3 (inside the braces, with `c`), back to 2 when `c` leaves its scope, and to 1 when we drop `b` by hand. When the last owner disappears the string is freed.

An `Rc` has two limits. First, it gives you only shared access, not the ability to change the value:

```rust
let a = Rc::new(5);
*a += 1;
```

```text
error[E0594]: cannot assign to data in an `Rc`
 --> src/bin/x_rcmut.rs:5:5
  |
5 |     *a += 1;
  |     ^^^^^^^ cannot assign
  |
  = help: trait `DerefMut` is required to modify through a dereference, but it is not implemented for `Rc<i32>`
```

That makes sense: if three owners could each change the value whenever they liked, we would be back to the problem the borrowing rules exist to prevent. Second, an `Rc` is not safe to share between threads, because its counter is updated without any protection against two threads doing it at once. The compiler enforces this. Trying to move an `Rc` into a thread:

```rust
let a = Rc::new(5);
let h = thread::spawn(move || println!("{a}"));
```

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
   --> src/bin/rc_thread.rs:6:27
    |
  6 |     let h = thread::spawn(move || println!("{a}"));
    |             ------------- -------^^^^^^^^^^^^^^^^
    |             |             |
    |             |             `Rc<i32>` cannot be sent between threads safely
    |             |             within this `{closure@src/bin/rc_thread.rs:6:27: 6:34}`
    |             required by a bound introduced by this call
    |
    = help: within `{closure@src/bin/rc_thread.rs:6:27: 6:34}`, the trait `Send` is not implemented for `Rc<i32>`
```

The key sentence is "the trait `Send` is not implemented for `Rc<i32>`". `Send` is a marker that says "this type may be moved to another thread", and `Rc` does not have it. I explain `Send` and the thread-safe version of `Rc`, which is called `Arc`, in the post on [threads](/posts/rust-concurrency-threads/). (I removed the `note:` lines that point into the standard library.)

## RefCell: changing a value through a shared reference

Now the other half of the story: mutation. The borrowing rules say that through a shared reference (`&`) you can only read:

```rust
let v = vec![1];
let r = &v;
r.push(2);
```

```text
error[E0596]: cannot borrow `*r` as mutable, as it is behind a `&` reference
 --> src/bin/x_shared_mut.rs:4:5
  |
4 |     r.push(2);
  |     ^ `r` is a `&` reference, so the data it refers to cannot be borrowed as mutable
```

That is usually what you want. But occasionally you know the code is correct and the compiler cannot prove it, especially when several `Rc` owners must each be able to change the value. `RefCell<T>` is the tool for that. It moves the same borrowing rules from compile time to run time: `borrow()` gives a shared view, `borrow_mut()` gives a mutable one, and the cell counts them while the program runs. Changing a value through a shared reference like this is called {{< term "interior-mutability" "interior mutability" >}}. The same snippet that failed above works when the vector is inside a `RefCell`:

```rust
let c = RefCell::new(vec![1]);
let r = &c;
r.borrow_mut().push(2);
println!("{:?}", c.borrow());
```

```text
[1, 2]
```

The rule is still "many readers or one writer", but if you break it you do not get a compile error, you get a panic. Here the demo takes a mutable borrow and keeps it, then tries to take a second one. It uses `try_borrow_mut` first, which returns a `Result` instead of panicking, and then `borrow_mut` to show the panic:

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

The first borrow `_first` is still alive, so `try_borrow_mut` returns an error and we print it, and the plain `borrow_mut` on the last line panics with the same message. (Older tutorials show `already borrowed: BorrowMutError`; with Rust 1.90 the text is the one above. I removed the `RUST_BACKTRACE` note line.) This is the price of `RefCell`: a mistake that the compiler would have caught is now a crash at run time.

## Rc and RefCell together

`Rc` gives many owners but read-only access. `RefCell` gives mutation. Put one inside the other and you get shared, changeable data in single-threaded code: `Rc<RefCell<T>>`. In the demo, two closures each own one handle to the same counter:

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

`inc_a` is called twice (+1 each) and `inc_b` once (+10), so `hits` is 12. The owners are three: `counter` itself and the two closures that each hold a clone.

## Reference cycles and Weak

Counting owners has a famous weakness. If `a` points to `b` and `b` points back to `a`, each is owned by the other, so neither count can ever reach zero. In the `cycle` demo, two nodes hold each other this way and the program prints:

```text
a=2 b=2
```

Both counts are 2 at the end of `main`. When `main` ends, the variables `a` and `b` are dropped, which lowers each count to 1, but not to 0. The nodes implement `Drop` and print a line when they are freed, and no "drop" line ever appears. The memory is never released. This is a memory leak, and Rust considers it safe code: it is not a crash and not undefined behaviour, only waste.

The cure is **`Weak`**: a pointer that does not own. `Rc::downgrade` makes one from an `Rc`, and it does not add to the owner count. To use it you call `upgrade()`, which returns `Option<Rc<T>>`: `Some` while the value is alive and `None` once it is gone. In a tree, parents own their children with `Rc`, and children point back to their parent with `Weak`:

```rust
struct Node {
    name: &'static str,
    parent: RefCell<Weak<Node>>,
    children: RefCell<Vec<Rc<Node>>>,
}
```

The demo creates a `leaf`, then inside a block creates a `root`, makes `leaf` a child of `root` and gives `leaf` a weak pointer to `root`. It prints the counts, leaves the block and prints again:

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

- `leaf parent = None`: at first `leaf` has no parent.
- `root: strong=1 weak=1`: `root` has one owner (the variable `root`) and one weak pointer (from `leaf`).
- `leaf: strong=2 weak=0`: `leaf` has two owners (the variable `leaf` and `root`'s `children` list).
- `leaf parent = Some("root")`: `upgrade()` succeeds, because `root` is still alive.
- `drop root`: the block ends. `root` has only one strong owner, so it is freed, even though `leaf` still points to it, because that pointer is `Weak`.
- `leaf parent = None`: now `upgrade()` returns `None`.
- `leaf: strong=1 weak=0`: `root`'s list is gone, so only the variable `leaf` owns `leaf`. At the end of `main`, `drop leaf` is printed.

## When not to reach for them

- **Plain ownership and borrowing first.** These types are for cases the borrow checker cannot prove, not a way around it. If a `&` or a move works, use it.
- **`RefCell` turns compile errors into crashes.** Keep the guards from `borrow_mut` short-lived, or use `try_borrow_mut` when a conflict is possible.
- **Write `Rc::clone(&a)` instead of `a.clone()`.** Both do the same, but the first makes it obvious that you are adding an owner, not copying data. That is my preference, not a rule.
- **`Rc` and `RefCell` are for one thread.** For threads you need their thread-safe relatives, `Arc` and `Mutex`.
- **Watch for cycles.** A cycle of `Rc`s silently leaks. If a child needs to point to its parent, use `Weak`.
- In Go the garbage collector makes sharing implicit, so you never count owners. Rust makes you choose, and in return there is no garbage collector running.

## Exercise

1. Add a `Cons` variant that holds `Rc<List>` so two lists can share the same tail, and print `Rc::strong_count` of the tail.
2. Make an `Rc<RefCell<Vec<String>>>` log that is shared by two closures, and print it at the end.
3. Trigger the `RefCell` panic on purpose, then replace the second borrow with `try_borrow_mut`.

## What's next

With the core of the language covered, the code needs a way to prove it works. The next post is "Testing and documentation in Rust".
