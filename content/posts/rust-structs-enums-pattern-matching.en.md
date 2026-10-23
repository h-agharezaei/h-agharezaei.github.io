+++
date = '2026-11-20T10:00:00+03:30'
draft = false
title = 'Structs, enums and pattern matching in Rust'
description = 'Rust structs, impl blocks, enums with data, Option, exhaustive match, if let and let else, with runnable code and the real compiler error.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "enums", "pattern-matching", "structs"]
cover = { image = "/images/covers/rust-structs-enums-pattern-matching.png", alt = "Structs, enums and pattern matching in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-borrowing-references/) we learned how to lend values with references. Now we can model data. If you come from Go, structs will look familiar. Enums will not: in Rust a variant can carry data, and `match` forces you to handle every case. This combination is the feature I miss most when I go back to other languages.

> Everything below was compiled and run with Rust 1.90, and the outputs are copied from those runs.

## Structs and impl blocks

A **struct** with named fields is the usual case. Behavior lives in a separate `impl` block:

```rust
#[derive(Debug, Clone, PartialEq)]
struct User {
    name: String,
    age: u32,
    active: bool,
}

impl User {
    // associated function: no self, called as User::new(...)
    fn new(name: &str, age: u32) -> Self {
        User { name: name.to_string(), age, active: true }
    }
    fn greet(&self) -> String { format!("hi, I am {}", self.name) }
    fn birthday(&mut self) { self.age += 1; }
    fn into_name(self) -> String { self.name }
}
```

There is no constructor keyword. `new` is just a convention: an **associated function** (no `self`) called with `User::new`. The three method forms map directly to the last two posts: `&self` borrows, `&mut self` borrows mutably, and `self` takes ownership, so after `into_name` the user is gone.

There are two lighter kinds of struct: a **tuple struct** like `struct Point(i32, i32)` (fields accessed as `p.0`) and a **unit struct** like `struct Marker;` with no fields at all.

## derive: Debug, Clone, PartialEq

`#[derive(...)]` asks the compiler to generate trait implementations. `Debug` gives you `{:?}` and the pretty `{:#?}`, `Clone` gives `.clone()`, and `PartialEq` gives `==`:

```rust
let mut u = User::new("roham", 30);
u.birthday();
let snapshot = u.clone();
println!("{:?}", u);
println!("{:#?}", u);
println!("equal to snapshot: {}", u == snapshot);
u.birthday();
println!("equal after birthday: {}", u == snapshot);
```

```text
User { name: "roham", age: 31, active: true }
User {
    name: "roham",
    age: 31,
    active: true,
}
equal to snapshot: true
equal after birthday: false
```

## Enums that carry data

A Go "enum" is usually a named integer type with `iota` constants. That is only a number: nothing stops you from converting `42` to the type, and the compiler does not check that a `switch` covers every constant. A Rust **enum** is a real sum type, and each variant can hold different data:

```rust
#[derive(Debug, Clone, PartialEq)]
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Triangle(f64, f64, f64),
    Empty,
}
```

You read the data back with `match`:

```rust
impl Shape {
    fn area(&self) -> f64 {
        match self {
            Shape::Circle { radius } => PI * radius * radius,
            Shape::Rect { w, h } => w * h,
            Shape::Triangle(a, b, c) => {
                let s = (a + b + c) / 2.0;
                (s * (s - a) * (s - b) * (s - c)).sqrt()
            }
            Shape::Empty => 0.0,
        }
    }
}
```

## Exhaustiveness: the compiler as a checklist

Now remove the `Empty` arm from a `match` over a similar enum. This is `src/bin/missing_variant.rs` in my demo:

```text
error[E0004]: non-exhaustive patterns: `&Shape::Empty` not covered
 --> src/bin/missing_variant.rs:8:11
  |
8 |     match s {
  |           ^ pattern `&Shape::Empty` not covered
  |
note: `Shape` defined here
 --> src/bin/missing_variant.rs:1:6
  |
1 | enum Shape {
  |      ^^^^^
...
4 |     Empty,
  |     ----- not covered
  = note: the matched value is of type `&Shape`
help: ensure that all possible cases are being handled by adding a match arm with a wildcard pattern or an explicit pattern as shown
  |
10~         Shape::Rect { w, h } => w * h,
11~ &Shape::Empty => todo!(),
  |
```

This is the payoff. When you add a variant six months later, every `match` that forgot it stops compiling. A `_ =>` wildcard silences this check, so use it deliberately, not by reflex.

## Option: no null

Rust has no null. A value that may be absent is an `Option<T>`, which is just an enum from the standard library: `Some(T)` or `None`. Because `Option<i32>` and `i32` are different types, you cannot forget the check:

```rust
fn first_even(v: &[i32]) -> Option<i32> {
    v.iter().copied().find(|n| n % 2 == 0)
}

println!("{:?} {:?}", first_even(&[1, 3, 4]), first_even(&[1, 3]));
// Some(4) None
```

## if let, let else, guards and @

`match` is verbose when you care about one case. **`if let`** handles it, and **`let else`** handles it and exits early otherwise:

```rust
if let Some(n) = first_even(&[7, 8]) {
    println!("found {n}");
}

fn parse_age(s: &str) -> u32 {
    let Ok(n) = s.parse::<u32>() else { return 0; };
    n
}
```

A **match guard** adds an `if` to an arm, and `@` binds a name to a value while testing it against a pattern:

```rust
fn describe(s: &Shape) -> String {
    match s {
        Shape::Rect { w, h } if w == h => format!("square with side {w}"),
        Shape::Circle { radius: r @ 0.0..=1.0 } => format!("small circle, r = {r}"),
        Shape::Circle { radius } => format!("circle, r = {radius}"),
        other => format!("{other:?}"),
    }
}
```

Running it over a list of shapes with `println!("{:<40} area = {:.2}", describe(s), s.area())`:

```text
small circle, r = 0.5                    area = 0.79
circle, r = 2                            area = 12.57
square with side 3                       area = 9.00
Rect { w: 2.0, h: 5.0 }                  area = 10.00
Triangle(3.0, 4.0, 5.0)                  area = 6.00
Empty                                    area = 0.00
```

`first_even(&[7, 8])` printed `found 8`, and `parse_age("42")` and `parse_age("abc")` gave `42` and `0`.

## A few things to watch

- Order matters in `match`: arms are tried top to bottom, so the guarded `Rect` arm must come before any general one.
- `{:?}` only works on types that derive or implement `Debug`; forgetting the derive is a common first error.
- `match` on a reference (`&Shape`) binds fields as references too, which is why `radius` above is used without any dereferencing.
- `unwrap()` on a `None` panics. Prefer `match`, `if let`, or `unwrap_or` unless you are sure.
- Compared with Go: iota constants are lighter to write, but they carry no data and no exhaustiveness check. Rust enums cost more thinking up front and give you both.

## Exercise

1. Add a `Square(f64)` variant to `Shape` without touching `area`, read the E0004 error, then fix it.
2. Write `fn largest(shapes: &[Shape]) -> Option<&Shape>` that returns `None` for an empty slice.
3. Model an order status enum (`Pending`, `Paid { tx_id: String }`, `Cancelled(String)`) and write a method that returns a human-readable label.

## What's next

We now have our own types. In the next post, collections and strings in Rust, we will store many of them with `Vec` and `HashMap` and look at `String` more closely.
