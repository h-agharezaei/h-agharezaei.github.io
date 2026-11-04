+++
date = '2026-12-12T10:00:00+03:30'
draft = false
title = 'Generics and traits in Rust'
description = 'Rust generics and traits: generic functions and structs, default methods, trait bounds, impl Trait, operator overloading, monomorphization, orphan rule.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "generics", "traits"]
cover = { image = "/images/covers/rust-generics-traits.png", alt = "Generics and traits in Rust", hiddenInSingle = true }
+++

Suppose you want a function that finds the largest element of a list. You write it for a list of integers. Tomorrow you need it for floats, and then for strings. The logic of all three is exactly the same and only the type changes. If you write three copy-pasted versions, every fix has to be made three times. In Go you would use generics for this, as in [Generics in Go](/posts/go-generics/). Rust has the same thing, with a difference that we will see in this post: before anything else, the compiler asks "what can this type do?"

Two ideas are at the centre of this post:

- **generics**: instead of one concrete type (`i32`), you write a "type as a parameter" (`T`) and define the function or struct once.
- **traits**: a named set of behaviours (methods) that a type can have. Roughly the role of interfaces in Go. If you met the word {{< term "trait" "trait" >}} in the error handling post (`Display`, `Error`, `From`), this was it.

You have already seen both without my naming them: `Option<T>` is generic, and `Debug` and `Display`, which we used in `println!`, are traits. Here we put it all together. This post comes after [Modules, crates and Cargo in Rust](/posts/rust-modules-crates-cargo/), because now that the code is tidy, we want one piece of code to cover many types.

> I compiled and ran all the code below with Rust 1.90, and the outputs and compiler messages come from those runs. From the error messages I removed the "For more information…" line. One example (returning two types from `impl Describe`) I wrote and ran in a separate small program, only to show the error.

## A generic function and its bound

Let us write that `largest`. We use `T` for the type and take the list as a slice (`&[T]`), and we return a reference to the largest element:

```rust
fn largest<T>(items: &[T]) -> &T {
    let mut max = &items[0];
    for item in items {
        if item > max {
            max = item;
        }
    }
    max
}
```

This does not compile:

```text
error[E0369]: binary operation `>` cannot be applied to type `&T`
 --> examples/err_no_bound.rs:4:17
  |
4 |         if item > max {
  |            ---- ^ --- &T
  |            |
  |            &T
  |
help: consider restricting type parameter `T` with trait `PartialOrd`
  |
1 | fn largest<T: std::cmp::PartialOrd>(items: &[T]) -> &T {
  |             ++++++++++++++++++++++
```

Notice that the error is about the line with `>`, even though the only call in the program (`largest(&[3, 9, 4])`) uses numbers, and `>` makes sense for numbers. The reason is that the compiler checks the body of a generic function only once, based on what it knows about `T`. And it knows nothing about `T`: it might be a number, or a struct that cannot be compared at all. So `>` is not allowed. The fix is the compiler's own suggestion. We must give `T` a **trait bound**, that is, say "`T` can be any type, as long as it has `PartialOrd` (the ability to compare with `>` and `<`)":

```rust
fn largest<T: PartialOrd>(items: &[T]) -> &T {
    let mut max = &items[0];
    for item in items {
        if item > max {
            max = item;
        }
    }
    max
}
```

Now the complete program, which makes three calls:

```rust
println!("{}", largest(&[3, 9, 4]));
println!("{}", largest(&[1.5, 0.2]));
println!("{}", largest(&["pear", "apple"]));
```

```text
9
1.5
pear
```

One function, three types (`i32`, `f64` and `&str`), and all three answers are right. "pear" is larger than "apple" because strings compare alphabetically. Now the bound makes sense: the function can only be called with types that promised to be comparable.

## Generic structs and enums

Your own types can be generic too. `Pair<T>` holds two values of the same type and `MyOption<T>` is the familiar shape of `Option<T>`:

```rust
struct Pair<T> {
    a: T,
    b: T,
}

impl<T: PartialOrd + Display> Pair<T> {
    fn show_largest(&self) {
        if self.a >= self.b {
            println!("largest = {}", self.a);
        } else {
            println!("largest = {}", self.b);
        }
    }
}

enum MyOption<T> {
    Nothing,
    Just(T),
}
```

One note on `impl<T: PartialOrd + Display> Pair<T>`: the method `show_largest` exists only for pairs whose `T` is both comparable and printable, because it uses both `>=` and `{}`. For a pair of a type that cannot be printed, `Pair` exists but this method does not. Running it:

```rust
Pair { a: 2, b: 7 }.show_largest();

let m: MyOption<i32> = MyOption::Just(5);
if let MyOption::Just(v) = m {
    println!("just {v}");
}
```

```text
largest = 7
just 5
```

## Traits: shared behaviour

Now to the trait itself. A trait **declares** methods, and each type joins it with `impl Trait for Type`. A trait can also have a **default method**: the implementer can keep it as it is or override it. Example: a trait called `Describe`, where every type must give a `name`, and `describe` by default makes a sentence from it:

```rust
trait Describe {
    fn name(&self) -> String;
    fn describe(&self) -> String {
        format!("I am {}", self.name())
    }
}

struct Dog;
struct Cat {
    lives: u8,
}

impl Describe for Dog {
    fn name(&self) -> String {
        "a dog".to_string()
    }
}

impl Describe for Cat {
    fn name(&self) -> String {
        format!("a cat with {} lives", self.lives)
    }
    fn describe(&self) -> String {
        format!("Meow, {}", self.name())
    }
}
```

`Dog` writes only `name` and gets the default `describe`. `Cat` writes both and replaces `describe`. The function below accepts any type that has `Describe`:

```rust
fn announce_generic<T: Describe>(x: &T) {
    println!("{}", x.describe());
}

announce_generic(&Dog);
announce_generic(&Cat { lives: 9 });
```

```text
I am a dog
Meow, a cat with 9 lives
```

The dog says the default sentence and the cat says its own. What happens if we pass a type that does not have the trait? (This is from a separate small program whose `show` function requires `T: Display` and whose type `Plain` does not have it.)

```text
error[E0277]: `Plain` doesn't implement `std::fmt::Display`
 --> examples/err_not_impl.rs:8:10
  |
8 |     show(Plain);
  |     ---- ^^^^^ the trait `std::fmt::Display` is not implemented for `Plain`
  |     |
  |     required by a bound introduced by this call
  |
note: required by a bound in `show`
 --> examples/err_not_impl.rs:3:12
  |
3 | fn show<T: std::fmt::Display>(x: T) {
  |            ^^^^^^^^^^^^^^^^^ required by this bound in `show`
```

This time the error is at the **call**, and the message is clear: `Plain` has not implemented that trait and `show` requires it. So a bound protects both the body of the function and the place where it is called.

## Three ways to write one idea: bound, where and impl Trait

The same bound can be written in three ways:

```rust
fn announce_generic<T: Describe>(x: &T) { println!("{}", x.describe()); }

fn announce_where<T, U>(x: &T, y: &U) -> String
where
    T: Describe,
    U: Describe + ?Sized,
{
    format!("{} / {}", x.describe(), y.describe())
}

fn announce_impl(x: &impl Describe) { println!("{}", x.describe()); }
fn make_dog() -> impl Describe { Dog }
```

- The first form (`<T: Describe>`) is the one we saw.
- `where` only moves long bounds out of the `<>` so the signature stays readable. The meaning is the same. (`?Sized` means "`U` need not have a size known at compile time". It was not needed here; you can ignore it for now.)
- `impl Describe` in argument position is a shorthand for the same generic parameter.
- `impl Describe` in return position means "one single concrete type that implements `Describe`", and the caller sees only the trait. `make_dog` really returns a `Dog`.

Running the last two:

```rust
announce_impl(&make_dog());
println!("{}", announce_where(&Dog, &Cat { lives: 7 }));
```

```text
I am a dog
I am a dog / Meow, a cat with 7 lives
```

Take "one concrete type" seriously. A function returning `impl Describe` cannot return `Dog` in one branch and `Cat` in another. (I tried this in a separate small program:)

```rust
fn make(dog: bool) -> impl Describe {
    if dog { Dog } else { Cat }
}
```

```text
error[E0308]: `if` and `else` have incompatible types
  --> examples/err_two_types.rs:16:27
   |
16 |     if dog { Dog } else { Cat }
   |              ---          ^^^ expected `Dog`, found `Cat`
   |              |
   |              expected because of this
   |
help: you could change the return type to be a boxed trait object
   |
15 - fn make(dog: bool) -> impl Describe {
15 + fn make(dog: bool) -> Box<dyn Describe> {
   |
```

To return different types decided at run time, the compiler's suggestion (`Box<dyn Describe>`) is the way. That is the topic of trait objects, which a later post in this series covers.

## derive or a manual implementation

The compiler can write some traits for you. `#[derive(...)]` generates a standard implementation. `Default` is one of them: it puts a zero or empty value in each field, and with the struct update syntax (`..Default::default()`) you change only the fields you want:

```rust
#[derive(Debug, Default, Clone, PartialEq)]
struct Config {
    port: u16,
    name: String,
    verbose: bool,
}

let c = Config::default();
println!("{:?}", c);
let c2 = Config { port: 8080, ..Default::default() };
println!("{:?} equal={}", c2, c == c2);
```

```text
Config { port: 0, name: "", verbose: false }
Config { port: 8080, name: "", verbose: false } equal=false
```

But `Display` cannot be derived, because the compiler does not know what format is right for the user ("$123.45" or "123.45 USD"?). So you write it yourself:

```rust
impl Display for Money {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "${}.{:02}", self.cents / 100, self.cents % 100)
    }
}

println!("{}", Money { cents: 12345 });
```

```text
$123.45
```

Operators are traits too. Behind the scenes `a + b` means `Add::add(a, b)`. So by implementing `std::ops::Add` for a struct, the `+` operator works for it:

```rust
impl Add for Point {
    type Output = Point;
    fn add(self, o: Point) -> Point {
        Point { x: self.x + o.x, y: self.y + o.y }
    }
}

println!("{:?}", Point { x: 1, y: 2 } + Point { x: 10, y: 20 });
```

```text
Point { x: 11, y: 22 }
```

(`type Output = Point` says what type the sum has. `Point` in the program is defined with `#[derive(Debug, Clone, Copy, PartialEq)]`.)

## Monomorphization: why generics cost nothing at run time

A natural question: what does the compiler do with a generic function? The answer is that for each concrete type the function is used with, it builds a separate, specialised version. This is called **monomorphization**. It is as if you had written `largest_i32` and `largest_f64` yourself, but the compiler does it. A small experiment shows this: a function that prints the name of the type `T`:

```rust
fn identity<T>(x: T) -> T {
    println!("identity::<{}>", type_name::<T>());
    x
}

identity(5i32);
identity("hi");
identity(2.5f64);
```

```text
identity::<i32>
identity::<&str>
identity::<f64>
```

Three calls with three different types means three separate instantiations. The program does not show this directly (printing the type name only says each call saw a different `T`), but according to the Rust Book this very work of the compiler is why generics add no extra cost at run time: each version is optimised for its own type. The price is more compiled code. I did not measure anything about speed here.

## The orphan rule

An important restriction: you can implement a trait for a type only if **either the trait or the type is defined in your own crate**. If both were foreign, two different crates could write two conflicting implementations and it would be unclear which wins. That is why implementing the standard `Display` for the standard `Vec<i32>` is rejected:

```text
error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate
 --> examples/err_orphan.rs:3:1
  |
3 | impl fmt::Display for Vec<i32> {
  | ^^^^^^^^^^^^^^^^^^^^^^--------
  |                       |
  |                       `Vec` is not defined in the current crate
  |
  = note: impl doesn't have any local type before any uncovered type parameters
  = note: for more information see https://doc.rust-lang.org/reference/items/implementations.html#orphan-rules
  = note: define and implement a trait or new type instead
```

The usual fix is the compiler's suggestion: wrap the type in a struct of your own (this pattern is called a newtype) and implement the trait for that, or define your own trait.

## Comparison with Go

In Go, an interface is satisfied structurally: any type that has the right methods fits, with no declaration. In Rust the link is explicit: you write `impl Trait for Type` yourself, and the orphan rule says where that line may live. In both languages, a set of interface-like behaviour is used as a generic constraint (for constraints in Go see [Generics in Go](/posts/go-generics/)).

## Trait traps

- Without a bound you can hardly do anything with `T`. When the compiler complains, add the bound as it suggests.
- `impl Trait` in return position means one concrete type, not "any type".
- Derive when the standard implementation is enough, and write it by hand when the meaning is yours (like `Display`).
- The orphan rule is about who owns the trait and the type, not about visibility.

## Exercise

1. Write `fn smallest<T: PartialOrd>(items: &[T]) -> &T` and try it with numbers and strings.
2. Define a trait called `Area` with `fn area(&self) -> f64` and a default method `describe` that prints the area, and implement it for `Circle` and `Rect`.
3. Implement `Mul<f64>` for a `Point` with `f64` fields so that `p * 2.0` works.

## What's next

In `largest` above we returned a `&T` and the compiler accepted it without a word, but that is not always the case. When a function takes two references and returns one of them, the compiler asks how long that reference stays valid. The answer to that question is "Lifetimes in Rust".
