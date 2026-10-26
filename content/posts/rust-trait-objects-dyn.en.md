+++
date = '2027-02-08T10:00:00+03:30'
draft = false
title = 'Trait objects and dyn in Rust'
description = 'Rust trait objects and dyn: Box<dyn Trait>, static vs dynamic dispatch, fat pointers, dyn compatibility (E0038), downcasting with Any and enum vs generics.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "traits", "dyn", "intermediate"]
cover = { image = "/images/covers/rust-trait-objects-dyn.png", alt = "Trait objects and dyn in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-nats-async-client/) the Rust worker consumed messages from a Go program. Earlier, the gRPC posts ended on a question: how does Rust get the runtime polymorphism that Go gives us for free with interfaces? In [Generics and traits](/posts/rust-generics-traits/) we saw static dispatch, where every concrete type gets its own copy of the code. This post covers the other half: **trait objects**, written `dyn Trait`. They let one `Vec` or one `HashMap` hold different types. The Go side of the comparison is in [structs, methods and interfaces](/posts/go-structs-methods-interfaces/).

> Everything here ran on Rust 1.90. I make no performance claims; I only show sizes and compiler output.

## The problem and the solution

A generic `Vec<T>` has exactly one `T`. You cannot put a `Square` and a `Circle` in it. With `Box<dyn Shape>` you can, because the element type is now "some box that implements `Shape`":

```rust
trait Shape: Debug {
    fn area(&self) -> f64;
    fn name(&self) -> String { "shape".to_string() }
}

let shapes: Vec<Box<dyn Shape>> = vec![Box::new(Square(2.0)), Box::new(Circle(1.0))];
for s in &shapes {
    println!("{} area={:.2} {:?}", s.name(), s.area(), s);
}
```

```text
square area=4.00 Square(2.0)
shape area=3.14 Circle(1.0)
```

`trait Shape: Debug` is a **supertrait**: every `Shape` must also be `Debug`, which is why `{:?}` works on the trait object. The same idea works behind other pointers: `&dyn Shape` borrows, and `Rc<dyn Shape>` shares ownership (I cloned one and `Rc::strong_count` printed `2`).

## Static vs dynamic dispatch

```rust
fn print_static<S: Shape>(s: &S) { /* ... */ }   // generic
fn print_dyn(s: &dyn Shape) { /* ... */ }        // trait object
```

With the generic function, the compiler uses **monomorphization**: it generates one copy of `print_static` per concrete type and the call is resolved at compile time. With `&dyn Shape` there is one copy of `print_dyn`; the method is looked up at runtime in a **vtable**, a small table of function pointers for that concrete type. The second gives you one copy of the code and the ability to mix types; the cost is an indirect call through the table.

## Fat pointers

A reference to a trait object must carry both the data address and the vtable address:

```text
&i32               = 8
&dyn Shape         = 16
Box<dyn Shape>     = 16
Box<Square>        = 8
```

These are bytes on my 64-bit machine. A `&dyn Trait` is a **fat pointer**: two words instead of one.

## Dyn compatibility (E0038)

Not every trait can become a trait object. A vtable needs one fixed signature per method, so a method that returns `Self` or has its own type parameter cannot go in it. I tried both:

```text
error[E0038]: the trait `Cloner` is not dyn compatible
 1 | trait Cloner {
   |       ------ this trait is not dyn compatible...
 2 |     fn dup(&self) -> Self;
   |                      ^^^^ ...because method `dup` references the `Self` type in its return type
 3 |     fn convert<T: Into<f64>>(&self, x: T) -> f64;
   |        ^^^^^^^ ...because method `convert` has generic type parameters
```

The fix, when you want the trait to stay usable as `dyn` but keep such a method for concrete types, is `where Self: Sized` on that method. In my `Shape` I added `fn scaled<T: Into<f64>>(&self, k: T) -> f64 where Self: Sized`. It compiles, and `Square(2.0).scaled(3)` printed `12`, but you cannot call it through `dyn Shape`.

## A plugin-style registry

```rust
trait Notifier: Send + Sync {
    fn send(&self, to: &str, msg: &str) -> String;
}

let mut reg: HashMap<&str, Box<dyn Notifier>> = HashMap::new();
reg.insert("email", Box::new(Email));
reg.insert("sms", Box::new(Sms { gateway: "gw1".into() }));
reg.insert("log", Box::new(LogOnly));
```

```text
email to ali: hello
log: ali <- hello
sms via gw1 to ali: hello
```

Here `Send + Sync` is a supertrait bound on the trait. You can also write it on the object, as in `Box<dyn Job + Send>`. I wrapped the registry in an `Arc` and called `send` from a spawned thread, and it worked. When I put an `Rc<i32>` inside a `dyn Job + Send` implementer, the compiler refused: `Rc<i32>` cannot be sent between threads safely.

## Downcasting with Any

Sometimes you must get the concrete type back. The usual pattern is an `as_any(&self) -> &dyn Any` method, then `downcast_ref`:

```rust
match s.as_any().downcast_ref::<Circle>() {
    Some(c) => println!("it is a Circle, radius {}", c.0),
    None => println!("{} is not a Circle", s.name()),
}
```

```text
square is not a Circle
it is a Circle, radius 1
```

If you need this often, the design is probably asking for an enum.

## Enum, generics or dyn?

- **Enum**: the set of variants is closed and known to you. You get `match` exhaustiveness and no heap allocation.
- **Generics**: one caller picks one type at compile time (a function parameter, a struct field).
- **dyn**: the set is open (plugins, user-supplied handlers) or you need a heterogeneous collection, and you accept a pointer and a vtable.

In Go, an interface value holds a pair: a type and a pointer to the data. A `dyn` reference is similar in spirit, but Rust requires you to say `dyn` explicitly and checks dyn compatibility at compile time.

## A few things to watch

- In the 2021 edition a bare trait name in type position is an error; write `dyn Trait`.
- A `Box<dyn Trait>` owns its value on the heap; `&dyn Trait` borrows. Use whichever ownership you need.
- `dyn Trait + Send + Sync` is needed to move or share objects across threads.
- Methods with generics or `Self` returns need `where Self: Sized` to coexist with `dyn`.
- `Any` downcasting works only for `'static` types.

## Exercise

1. Add a `Triangle` to the `Vec<Box<dyn Shape>>` and print the sum of all areas.
2. Add a `"webhook"` notifier to the registry without touching the code that calls `send`.
3. Make the trait non-compatible on purpose with a `fn new() -> Self` method and see which `where` clause fixes it.

## What's next

Next: macros in Rust, the code that writes code, including the `derive` and `println!` we have been using all along.
