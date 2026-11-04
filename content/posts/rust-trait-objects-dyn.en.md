+++
date = '2027-02-08T10:00:00+03:30'
draft = false
title = 'Trait objects and dyn in Rust'
description = 'Rust trait objects and dyn: Box<dyn Trait>, static vs dynamic dispatch, fat pointers, dyn compatibility (E0038), downcasting with Any and enum vs generics.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "traits", "dyn", "intermediate"]
cover = { image = "/images/covers/rust-trait-objects-dyn.png", alt = "Trait objects and dyn in Rust", hiddenInSingle = true }
+++

Imagine you are writing a program that draws shapes. You have a `Square` and a `Circle`, and you want to keep all the shapes in one list so that a single loop can print the area of each. In Go this is trivial: define an interface called `Shape` and make a slice of it. In Rust the first attempt looks like this:

```rust
struct Square(f64);
struct Circle(f64);

fn main() {
    let shapes = vec![Square(2.0), Circle(1.0)];
    println!("{}", shapes.len());
}
```

```text
error[E0308]: mismatched types
 --> src/bin/x1.rs:5:36
  |
5 |     let shapes = vec![Square(2.0), Circle(1.0)];
  |                                    ^^^^^^^^^^^ expected `Square`, found `Circle`
```

The error is straightforward: a `Vec<T>` has exactly one type `T`. The compiler decided from the first element that `T` is `Square`, and a `Circle` does not fit. This is not stubbornness. A `Vec` lays its elements out one after another, each with the same size, and a `Square` and a `Circle` may have different sizes. In [Generics and traits](/posts/rust-generics-traits/) we saw that a generic means "one type, chosen at compile time". Now we need something that says "any type, as long as it implements `Shape`, and the choice stays open until the program runs".

Rust's answer is a {{< term "trait-object" "trait object" >}}, written `dyn Trait`. This post follows [the async NATS JetStream client](/posts/rust-nats-async-client/) and is the other half of the generics story. The Go side of the comparison, interfaces, is in [structs, methods and interfaces](/posts/go-structs-methods-interfaces/).

> I re-ran all the code below with Rust 1.90 (`rustc 1.90.0`), and the outputs and compiler messages come from those runs. The programs need only the standard library, no external crates. I removed the "For more information…" line from the error messages. A few small examples (the heterogeneous `Vec` error, writing a trait name without `dyn`, and the enum version) I wrote and ran as separate programs, only to show them here. I make no performance claims; I only show sizes and compiler output.

## The core idea: a value whose type we have forgotten

A trait object is a value about which we know only one thing of its real type: "whatever it is, it implements `Shape`". We do not know whether it is a `Square` or a `Circle`, but we know we can call `area()` on it. Think of a wall socket: you do not care what wiring is behind the wall, you only know your plug fits.

Because the size of such a value is unknown, we do not hold it directly. We put it behind a pointer. `Box<dyn Shape>` means "a box on the heap with something inside, and that something is a `Shape`". `&dyn Shape` means "a reference to something that is a `Shape`". A pointer always has a fixed size, so a `Vec` of them is possible.

This code builds the list we wanted:

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

Each output line comes from one element of the list. `Square` implements `name` itself and returns `"square"`. `Circle` does not, so it gets the trait's default implementation, `"shape"`. The loop never knows which type it is dealing with, and still the right method runs each time.

In the trait definition you saw `: Debug`. It is called a **supertrait**: every type that implements `Shape` must implement `Debug` too. That is why `{:?}` works on the trait object itself: the compiler knows that every `Shape` is also a `Debug`.

Other pointers work with `dyn` as well. `&dyn Shape` borrows, and `Rc<dyn Shape>` shares ownership. In the demo I made an `Rc<dyn Shape>`, cloned it, and `Rc::strong_count` printed `2` (the line `rc: area=9 count=2`).

## How is the right method found? Static and dynamic dispatch

Here is a question: when we call `s.area()` and we do not know the type of `s`, how does the program find the right code? Choosing which function runs is called **dispatch**. Rust has two ways, and you can see both on one small function:

```rust
fn print_static<S: Shape>(s: &S) { /* ... */ }   // generic
fn print_dyn(s: &dyn Shape) { /* ... */ }        // trait object
```

For the generic function the compiler does **monomorphization**: for every concrete type it is called with, it builds a separate copy of `print_static`. A call with a `Square` goes to the `Square` copy, a call with a `Circle` goes to the `Circle` copy. The decision is made before the program runs. This is **static dispatch**.

With `&dyn Shape` there is only one copy of `print_dyn`. That copy must work with any type, so it finds the method at run time. It does this through a small table called a {{< term "vtable" "vtable" >}}: for each concrete type that is used as `dyn Shape`, the compiler builds a table holding the addresses of that type's methods (`area`, `name` and so on). This is **dynamic dispatch**. A picture of it:

```text
&dyn Shape                      the vtable for Square
+-------------------+           +----------------------+
| pointer to data   | --+       | address of drop      |
| pointer to vtable | --|--->   | size and alignment   |
+-------------------+   |       | address of area      |
                        |       | address of name      |
                        v       +----------------------+
                     Square(2.0)
```

(The exact layout of a vtable is not guaranteed by the language; the picture shows only the idea.) Calling `s.area()` means "go to the vtable, take the address of `area`, and call that function with the data pointer". A Go interface value works in a similar way: a pair of a pointer to type information and a pointer to the data.

So the trade is this. With dynamic dispatch there is one copy of the code and types can be mixed, but each call goes through a table, and the compiler usually cannot know which function will run, so it cannot, for example, inline it. With static dispatch the code is duplicated per type and the types must be known at compile time. I give no numbers for how big the difference is; in most programs it is not the main concern, and the shape of the problem decides the choice (we come back to this below).

## Fat pointers: a pointer of two words

The picture above shows that `&dyn Shape` has to point both to the data and to the vtable. That is two addresses, not one. Such a pointer is called a **fat pointer**. The demo prints the sizes:

```text
&i32               = 8
&dyn Shape         = 16
Box<dyn Shape>     = 16
Box<Square>        = 8
Square / Circle    = 8 / 8
```

These are sizes in bytes on my 64-bit machine. `&i32` is one address: 8 bytes. `&dyn Shape` is two addresses: 16 bytes. `Box<dyn Shape>` is 16 as well, but `Box<Square>` is only 8, because when the type is known no vtable is needed and the compiler itself knows which function to call. So the cost of `dyn` is one extra word per pointer, plus a heap allocation if you use `Box`.

## Not every trait can be dyn: the E0038 error

Now the main trap. Once we have forgotten the type, the compiler must be able to say, from `dyn Trait` alone, what signature each method has and where it sits in the vtable. For some methods this is impossible. Take this trait with two problematic methods, and then try to build a `Box<dyn Cloner>`:

```rust
trait Cloner {
    fn dup(&self) -> Self;
    fn convert<T: Into<f64>>(&self, x: T) -> f64;
}
```

```text
error[E0038]: the trait `Cloner` is not dyn compatible
  --> src/bin/e0038.rs:11:24
   |
11 |     let v: Vec<Box<dyn Cloner>> = vec![Box::new(A)];
   |                        ^^^^^^ `Cloner` is not dyn compatible
   |
note: for a trait to be dyn compatible it needs to allow building a vtable
      for more information, visit <https://doc.rust-lang.org/reference/items/traits.html#dyn-compatibility>
  --> src/bin/e0038.rs:2:22
   |
 1 | trait Cloner {
   |       ------ this trait is not dyn compatible...
 2 |     fn dup(&self) -> Self;
   |                      ^^^^ ...because method `dup` references the `Self` type in its return type
 3 |     fn convert<T: Into<f64>>(&self, x: T) -> f64;
   |        ^^^^^^^ ...because method `convert` has generic type parameters
   = help: consider moving `dup` to another trait
   = help: consider moving `convert` to another trait
   = help: only type `A` implements `Cloner`; consider using it directly instead.
```

(`A` is an empty struct in my program that implements the trait.) Line by line:

- **The first line and the `^^^^^^` marker**: the trait `Cloner` is not "dyn compatible", and the place that complains is the `dyn Cloner` in the `Vec` type. (Older versions called this property "object safety"; the newer name in the Rust Reference is "dyn compatibility".)
- **`dup` returns `Self`**: `Self` means "the concrete type that implements this trait". If all you have is a `dyn Cloner`, you do not know what `Self` is, so you do not know how many bytes the result of `dup` takes or where it goes.
- **`convert` has a type parameter `T`**: a generic method needs a separate copy for every `T`, that is, an unlimited number of copies. A vtable is a table with a fixed number of slots and has no room for "every version anyone might need later".
- **The three `help` lines**: the compiler's suggestions. The first two say to move that method to another trait. The third says that since only one type (`A`) implements the trait, maybe you do not want `dyn` at all and should use `A` directly.

If you want the trait to work with `dyn` but still keep such a method for concrete types, put `where Self: Sized` on that method. It means "this method exists only when the type is concrete", and it stays out of the vtable. I did this in `Shape`: `fn scaled<T: Into<f64>>(&self, k: T) -> f64 where Self: Sized`. It compiles, and `Square(2.0).scaled(3)` printed `12` (area 4 times 3). But you cannot call `scaled` through a `dyn Shape`, because that method is not in the vtable. The same way out works for `fn new() -> Self`: a small program with `fn new() -> Self where Self: Sized` in the trait and a `Box<dyn T>` compiled (exercise 3 asks you to try this).

## A plugin-style registry

A more realistic example: a system that sends a message through several channels, and we pick the channel by name. Here the types are not known at compile time, and more channels may be added later. This is where `dyn` is natural:

```rust
trait Notifier: Send + Sync {
    fn send(&self, to: &str, msg: &str) -> String;
}

let mut reg: HashMap<&str, Box<dyn Notifier>> = HashMap::new();
reg.insert("email", Box::new(Email));
reg.insert("sms", Box::new(Sms { gateway: "gw1".into() }));
reg.insert("log", Box::new(LogOnly));
```

The program sorts the keys and calls `send("ali", "hello")` on each:

```text
email to ali: hello
log: ali <- hello
sms via gw1 to ali: hello
```

Each channel builds its own text, and `Sms` even has a `gateway` field that the others do not: every type has its own data, and they share only one behaviour. If a new channel is needed tomorrow, it takes one `impl Notifier for ...` and one `insert` line, and the code that sends is untouched.

`Send + Sync` in the trait definition are two supertrait bounds, meaning every implementation must be movable and shareable between threads (we covered {{< term "send-and-sync" "Send and Sync" >}} in [Concurrency with threads in Rust](/posts/rust-concurrency-threads/)). That is why I could put the registry in an `Arc` and call `send` from a separate thread, and it worked (the line `thread: sms via gw1 to sara: hi`). You can also write the bounds on the object itself, like `Box<dyn Job + Send>`. When I deliberately put an `Rc<i32>` inside a type used as `dyn Job + Send`, the compiler rejected it:

```text
error[E0277]: `Rc<i32>` cannot be sent between threads safely
 --> src/bin/no_send.rs:6:34
  |
6 |     let b: Box<dyn Job + Send> = Box::new(J(Rc::new(1)));
  |                                  ^^^^^^^^^^^^^^^^^^^^^^^ `Rc<i32>` cannot be sent between threads safely
  |
  = help: within `J`, the trait `Send` is not implemented for `Rc<i32>`
note: required because it appears within the type `J`
 --> src/bin/no_send.rs:3:8
  |
3 | struct J(Rc<i32>);
  |        ^
```

The meaning: by writing `+ Send` you promised that `J` is safe to send, but `J` contains an `Rc`, and `Rc` is not `Send` because its counter is not atomic. The compiler does not accept the promise and points at the root of the problem (`struct J(Rc<i32>)`).

## When you want the concrete type back: downcasting with Any

Sometimes, after forgetting the type, you need to ask "was this really a `Circle`?". The tool is the standard `Any` trait. The usual pattern is for the trait to have a method `as_any(&self) -> &dyn Any`, and then you call `downcast_ref`:

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

For each element of the list, `downcast_ref::<Circle>()` returns either `Some` with a reference to a `Circle` or `None`. The `Square` produces the first line and the `Circle` the second. This works, but if you need it often, you are taking back a type you deliberately forgot. A design with an enum is probably a better fit.

## enum, generics or dyn?

Now that we have seen all three tools, how do we choose? Let us ask three questions.

**Is the set of types closed, and do you know all of them?** For example, the shapes in your program are only `Square` and `Circle`. Write an `enum`:

```rust
enum Shape {
    Square(Square),
    Circle(Circle),
}

impl Shape {
    fn area(&self) -> f64 {
        match self {
            Shape::Square(s) => s.0 * s.0,
            Shape::Circle(c) => 3.14 * c.0 * c.0,
        }
    }
}
```

I ran this in a separate program: with `vec![Shape::Square(Square(2.0)), Shape::Circle(Circle(1.0))]` the total area printed `total area = 7.14`. The advantages: the compiler checks that the `match` is exhaustive (if you add a `Triangle` tomorrow and forget a place, you get an error), and no heap allocation is needed. The drawback: anyone who wants a new shape has to change the enum itself.

**Does each caller pick one type at compile time?** For example a function that takes one shape and only works with that. A generic (`fn f<S: Shape>(s: &S)`) is best: it is simple and gives static dispatch.

**Is the set open?** That is, plugins, handlers given by users of your library, or a list whose elements are of different types and where someone will add new types later. This is what `dyn` is for, and its price is a fat pointer and a vtable.

In Go an interface value is always a pair: a type and a pointer to the data. `dyn` is similar in idea, but Rust wants you to write `dyn` explicitly and it checks dyn compatibility at compile time.

## Common traps with dyn

- **Writing the trait name without `dyn`.** In edition 2021, `Box<Shape>` gives `E0782: expected a type, found a trait` and suggests adding `dyn`: `Box<dyn Shape>`. I tried this in a separate program too.
- **Confusing `Box<dyn Trait>` and `&dyn Trait`.** The first owns the value on the heap, the second only borrows it. Use whichever matches the ownership you need.
- **Forgetting `Send` and `Sync`.** To move or share an object between threads it must be `dyn Trait + Send + Sync`, or the compiler rejects it.
- **Generic methods or methods returning `Self`.** If you do not want to lose `dyn` for the whole trait, put `where Self: Sized` on that method.
- **Expecting downcasting to work for any type.** `Any` works only for `'static` types, that is, types that do not hold short-lived references.

## Exercise

1. Add a `Triangle` to the `Vec<Box<dyn Shape>>` and print the sum of all the areas.
2. Add a notifier named `"webhook"` to the registry without touching the code that calls `send`.
3. Make the trait incompatible on purpose with a method `fn new() -> Self`, and see which `where` fixes it.

## What's next

"Macros in Rust": code that writes code, including the `derive` and `println!` we have been using all along.
