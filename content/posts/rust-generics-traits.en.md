+++
date = '2026-12-12T10:00:00+03:30'
draft = false
title = 'Generics and traits in Rust'
description = 'Rust generics and traits: generic functions and structs, default methods, trait bounds, impl Trait, operator overloading, monomorphization, orphan rule.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "generics", "traits"]
cover = { image = "/images/covers/rust-generics-traits.png", alt = "Generics and traits in Rust", hiddenInSingle = true }
+++

In the [previous post](/posts/rust-modules-crates-cargo/) we split code into modules and crates. Now we write code that works for many types at once. In Rust that takes two ideas: **generics** (code parameterized over a type) and **traits** (a named set of behavior a type can have). You have already used both without naming them: `Option<T>` is generic, and `Display` and `Debug` are traits.

> Everything below was compiled and run with Rust 1.90. Outputs and compiler messages are copied from those runs.

## Generic functions and bounds

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

`T: PartialOrd` is a **trait bound**: `T` can be any type that supports `>`. `largest(&[3, 9, 4])` gives `9`, `largest(&[1.5, 0.2])` gives `1.5`, and `largest(&["pear", "apple"])` gives `pear`. Remove the bound and the compiler refuses, even though we never call the function with a bad type:

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
```

The function body is checked once, against what the bounds promise. A generic type works the same way: `struct Pair<T> { a: T, b: T }` and `enum MyOption<T> { Nothing, Just(T) }` are the same shape as the `Option<T>` you know. Methods can add bounds: `impl<T: PartialOrd + Display> Pair<T>` gives `show_largest` only to pairs whose `T` can be compared and printed.

## Traits

A **trait** declares methods; a type opts in with `impl Trait for Type`. A trait can provide a **default method** that implementors may keep or override:

```rust
trait Describe {
    fn name(&self) -> String;
    fn describe(&self) -> String {
        format!("I am {}", self.name())
    }
}

impl Describe for Dog {
    fn name(&self) -> String { "a dog".to_string() }
}
impl Describe for Cat {
    fn name(&self) -> String { format!("a cat with {} lives", self.lives) }
    fn describe(&self) -> String { format!("Meow, {}", self.name()) }
}
```

Here `Dog` and `Cat` are two small structs (`Cat` has a `lives: u8` field). Calling `describe()` on each prints `I am a dog` and `Meow, a cat with 9 lives`.

## Bounds, where and impl Trait

Three spellings of one idea:

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

`where` just moves long bounds out of the angle brackets. `impl Describe` in argument position is shorthand for a generic parameter. In return position it means "some single concrete type that implements `Describe`", and the caller only sees the trait. A function returning `impl Describe` cannot return a `Dog` in one branch and a `Cat` in another. Output: `announce_where(&Dog, &Cat { lives: 7 })` printed `I am a dog / Meow, a cat with 7 lives`.

## Derive or implement

`#[derive(...)]` generates a standard implementation for you. `Default` can be derived, so `Config::default()` gives `Config { port: 0, name: "", verbose: false }`, and struct update syntax fills the rest: `Config { port: 8080, ..Default::default() }`. `Display` cannot be derived, because there is no obvious format for users, so you write it:

```rust
impl Display for Money {
    fn fmt(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        write!(f, "${}.{:02}", self.cents / 100, self.cents % 100)
    }
}
```

`Money { cents: 12345 }` prints `$123.45`. Operators are traits too. Implementing `std::ops::Add` for a `Point { x, y }` struct (deriving `Debug`, `Clone`, `Copy`) makes `+` work:

```rust
impl Add for Point {
    type Output = Point;
    fn add(self, o: Point) -> Point {
        Point { x: self.x + o.x, y: self.y + o.y }
    }
}
```

`Point { x: 1, y: 2 } + Point { x: 10, y: 20 }` prints `Point { x: 11, y: 22 }`.

## Monomorphization

The compiler generates a separate copy of a generic function for every concrete type it is used with; this is called **monomorphization**. A tiny experiment makes the copies visible:

```rust
fn identity<T>(x: T) -> T {
    println!("identity::<{}>", type_name::<T>());
    x
}
```

```text
identity::<i32>
identity::<&str>
identity::<f64>
```

Three calls, three types, three instantiations. I make no speed claim here; the point is that generics are resolved at compile time.

## The orphan rule

You can implement a trait for a type only if the trait or the type is defined in your crate. Implementing the standard `Display` for the standard `Vec<i32>` is rejected:

```text
error[E0117]: only traits defined in the current crate can be implemented for types defined outside of the crate
 --> examples/err_orphan.rs:3:1
  |
3 | impl fmt::Display for Vec<i32> {
  | ^^^^^^^^^^^^^^^^^^^^^^--------
  |                       |
  |                       `Vec` is not defined in the current crate
  |
  = note: define and implement a trait or new type instead
```

The compiler's hint is the usual fix: wrap the type in your own struct (the newtype pattern), or define your own trait.

## Compared with Go

In Go, an interface is satisfied structurally: any type with the right methods fits, with no declaration (see [Generics in Go](/posts/go-generics/) for constraints). In Rust the link is explicit: you write `impl Trait for Type`, and the orphan rule says where that line may live. Both use interface-like sets of behavior as generic constraints.

## A few things to watch

- Without a bound, you can do almost nothing with a `T`; add bounds as the compiler asks.
- `impl Trait` in return position means one concrete type, not "any type".
- Derive when a standard implementation fits; implement by hand when the meaning is yours (`Display`).
- The orphan rule is about who owns the trait and the type, not about visibility.

## Exercise

1. Write `fn smallest<T: PartialOrd>(items: &[T]) -> &T` and test it with integers and strings.
2. Define a trait `Area` with `fn area(&self) -> f64` and a default method `describe` that prints the area; implement it for `Circle` and `Rect`.
3. Implement `Mul<f64>` for `Point` with `f64` fields, so `p * 2.0` works.

## What's next

In the next post we meet lifetimes in Rust, which explain what those `&T` references are allowed to point to and for how long.
