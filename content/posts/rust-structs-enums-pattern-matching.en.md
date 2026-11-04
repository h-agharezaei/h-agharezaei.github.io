+++
date = '2026-11-20T10:00:00+03:30'
draft = false
title = 'Structs, enums and pattern matching in Rust'
description = 'Rust structs, impl blocks, enums with data, Option, exhaustive match, if let and let else, with runnable code and the real compiler error.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "beginner", "enums", "pattern-matching", "structs"]
cover = { image = "/images/covers/rust-structs-enums-pattern-matching.png", alt = "Structs, enums and pattern matching in Rust", hiddenInSingle = true }
+++

Suppose orders in a shop have three statuses: waiting for payment, paid and cancelled. Six months later a fourth one is added: "returned". In most languages you have to remember which parts of the program checked the status, and update them yourself. In Rust, if you forget one of the cases in a `match`, the program simply does not compile: `error[E0004]: non-exhaustive patterns`. That check is what makes modelling data in Rust different.

Now that [Borrowing and references in Rust](/posts/rust-borrowing-references/) showed us how to lend a value, it is time to build our own types. If you come from Go, structs will look familiar but enums will not: in Rust each variant of an enum can carry data, and `match` forces you to handle every case. This combination is the thing I miss most when I go back to other languages.

> I compiled and ran all the code below with Rust 1.90, and the outputs come from those runs. I also wrote and ran a few small extra programs (for the order status, `Option` and use after a move).

## Structs and the impl block

First the simplest thing: grouping several values that belong together. A **struct** does this. Each value has a name and is called a "field". The behaviours of the type (methods, as they are called) are written in a separate block named `impl`:

```rust
#[derive(Debug, Clone, PartialEq)]
struct User {
    name: String,
    age: u32,
    active: bool,
}

impl User {
    // associated function (no self), used as User::new(...)
    fn new(name: &str, age: u32) -> Self {
        User { name: name.to_string(), age, active: true }
    }
    fn greet(&self) -> String {
        format!("hi, I am {}", self.name)
    }
    fn birthday(&mut self) {
        self.age += 1;
    }
    fn into_name(self) -> String {
        self.name
    }
}
```

There is no special keyword for a constructor. `new` is only a convention: an **associated function**, meaning a function in `impl` that has no `self` and is called as `User::new(...)`. (`Self` means "the type this `impl` is written for".)

The next three are methods, and their first parameter is `self`. The form of `self` goes back to the previous two posts:

- `&self`: only borrows, for reading. `greet` is like this.
- `&mut self`: a mutable borrow, for changing. `birthday` increases the age.
- `self`: takes ownership. `into_name` consumes the whole `User` and returns only the name.

See what happens if we use the user after `into_name`:

```rust
fn main() {
    let u = User { name: "roham".to_string(), age: 30 };
    let name = u.into_name();
    println!("{name}");
    println!("{}", u.age);
}
```

```text
error[E0382]: borrow of moved value: `u`
  --> src/bin/after_into.rs:17:20
   |
14 |     let u = User { name: "roham".to_string(), age: 30 };
   |         - move occurs because `u` has type `User`, which does not implement the `Copy` trait
15 |     let name = u.into_name();
   |                  ----------- `u` moved due to this method call
16 |     println!("{name}");
17 |     println!("{}", u.age);
   |                    ^^^^^ value borrowed here after move
   |
note: `User::into_name` takes ownership of the receiver `self`, which moves `u`
  --> src/bin/after_into.rs:8:18
   |
 8 |     fn into_name(self) -> String {
   |                  ^^^^
   = note: this error originates in the macro `$crate::format_args_nl` which comes from the expansion of the macro `println` (in Nightly builds, run with -Z macro-backtrace for more info)
```

It is the same E0382 error from the ownership post, only this time the cause is a method: the compiler says `into_name` takes ownership of `self`, so it moved `u`. (This is a separate small program where `User` has only the two fields `name` and `age`; the line numbers belong to that file.)

There are two lighter kinds of struct too. A **tuple struct** has fields without names: `struct Point(i32, i32)`, and you reach them with `p.0` and `p.1`. A **unit struct** like `struct Marker;` has no fields at all and is just a type.

## derive: Debug, Clone and PartialEq

You saw a `#[derive(...)]` line above `User`. With it you ask the compiler to write the code of some traits for you. `Debug` gives printing with `{:?}` and the multi-line readable form `{:#?}`, `Clone` gives the `.clone()` method, and `PartialEq` gives the `==` operator. Without derive you would write each by hand. The `structs` program uses them. (It also calls `greet` first, and at the end it builds a `Point` and a `Marker` and then calls `into_name`; the complete output is below.)

```rust
let mut u = User::new("roham", 30);
println!("{}", u.greet());
u.birthday();
let snapshot = u.clone();
println!("{:?}", u);
println!("{:#?}", u);
println!("equal to snapshot: {}", u == snapshot);
u.birthday();
println!("equal after birthday: {}", u == snapshot);
```

```text
hi, I am roham
User { name: "roham", age: 31, active: true }
User {
    name: "roham",
    age: 31,
    active: true,
}
equal to snapshot: true
equal after birthday: false
point = (3, 4)
moved out name: roham
```

The first line is from `greet`. Then `birthday` took the age from 30 to 31, and `{:?}` printed all fields on one line while `{:#?}` printed them on several. `snapshot` is an independent copy (made with `.clone()`) of that moment, so comparing with `==` gives `true` at first. After the second `birthday`, `u` is 32 but `snapshot` is still 31, so it gives `false`. The last two lines come from `Point` and `into_name`: `point = (3, 4)` and `moved out name: roham`.

## Enums and the possible cases

Now back to the question at the start: how do we model several possible cases? In Go you usually make an integer type with a few `iota` constants. It is just a number. Nothing stops you from converting `42` to that type, and the Go compiler does not check that a `switch` covers all the constants. A Rust **enum** is a real type whose value is always exactly one of the cases you defined. Each case is called a **variant**.

The simplest form is an enum without data. This program defines three order statuses and returns a text for each with `match`:

```rust
#[derive(Debug)]
enum Status {
    Pending,
    Paid,
    Cancelled,
}

fn label(s: &Status) -> &'static str {
    match s {
        Status::Pending => "waiting for payment",
        Status::Paid => "paid",
        Status::Cancelled => "cancelled",
    }
}

fn main() {
    let orders = [Status::Pending, Status::Paid, Status::Cancelled];
    for o in &orders {
        println!("{:?}: {}", o, label(o));
    }
}
```

```text
Pending: waiting for payment
Paid: paid
Cancelled: cancelled
```

`match` compares the value against each pattern and runs the code of the first pattern that fits. Here the patterns are just variant names.

The real power of Rust shows up when each variant can carry its own data. Take geometric shapes: a circle has a radius, a rectangle a width and a height, and a triangle three sides. This kind of type is called a sum type: the value is "either this or that", together with the data specific to each case:

```rust
#[derive(Debug, Clone, PartialEq)]
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Triangle(f64, f64, f64),
    Empty,
}
```

`Circle` and `Rect` have named fields, `Triangle` has unnamed fields (like a tuple struct) and `Empty` has no data at all. We pull the data out with `match`. The pattern both matches the shape of the variant and gives names to the fields right there:

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

For example, in the first arm `radius` is bound to the radius of that very circle. (The triangle formula is Heron's formula: with half the perimeter `s`, it computes the area from the three sides. `PI` is imported at the top of the file from `std::f64::consts::PI`.) Because `self` here is a `&Shape`, `radius` and the other fields are themselves references to the values, and that is why they work in the arithmetic without a `*`.

## Exhaustive match: the compiler as a checklist

Now the problem from the start of the post. This program has a `Shape` with three variants (`Circle`, `Rect`, `Empty`), but the `match` in `area` handles only the first two:

```rust
enum Shape {
    Circle { radius: f64 },
    Rect { w: f64, h: f64 },
    Empty,
}

fn area(s: &Shape) -> f64 {
    match s {
        Shape::Circle { radius } => 3.14 * radius * radius,
        Shape::Rect { w, h } => w * h,
    }
}
```

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
11~         &Shape::Empty => todo!(),
  |
```

"Non-exhaustive" means the patterns do not cover every possible case. The compiler says exactly which case is missing (`&Shape::Empty`), points at the enum definition, and even suggests the arm you need (`todo!()` means "I will fill this in later"). The `&` in front of `Shape::Empty` is there because we match on a `&Shape`.

This is the main value. Six months from now, when you add a variant, every `match` that forgot it will fail to compile. The compiler acts as a checklist of all the places you need to update. A wildcard arm, `_ =>`, silences this check and takes "every other case". So use it deliberately, not out of habit, or you lose exactly this protection.

## Option: no null

One of the most important uses of enums is in Rust itself. Rust has no null value. A value that might be missing has the type `Option<T>`, which is itself an enum in the standard library with two variants: `Some(T)` means the value is there and `None` means it is not. (`<T>` means "any type", for example `Option<i32>`; we will say more about this notation in the generics post.)

Because `Option<i32>` and `i32` are two different types, you cannot forget the "it might be missing" check. See:

```rust
fn main() {
    let a: Option<i32> = Some(41);
    let b = a + 1;
    println!("{b}");
}
```

```text
error[E0369]: cannot add `{integer}` to `Option<i32>`
   --> src/bin/option_add.rs:3:15
    |
  3 |     let b = a + 1;
    |             - ^ - {integer}
    |             |
    |             Option<i32>
```

(The real message continues with a `note` that points into the standard library source on my machine; I removed it because it contained a personal path.) The compiler says you cannot add a number to an `Option<i32>`. You have to open the `Option` first and also deal with the `None` case, usually with `match`:

```rust
fn first_even(v: &[i32]) -> Option<i32> {
    v.iter().copied().find(|n| n % 2 == 0)
}

fn main() {
    for list in [&[1, 3, 4][..], &[1, 3][..]] {
        match first_even(list) {
            Some(n) => println!("first even is {n}"),
            None => println!("no even number"),
        }
    }
}
```

```text
first even is 4
no even number
```

`first_even` returns the first even number of a list, if there is one. (`find` searches with a small function; what matters here is the return type.) For `[1, 3, 4]` the answer is `Some(4)`, and for `[1, 3]`, which has no even number, it is `None`. `match` forces you to write both cases.

## if let, let else, guards and @

When only one case matters to you, a full `match` gets long. **`if let`** handles just that one case and ignores the rest. **`let else`** is the opposite: if the pattern does not fit, the `else` block runs, and it must leave the function; if it fits, the variable is ready for the rest of the code:

```rust
if let Some(n) = first_even(&[7, 8]) {
    println!("found {n}");
}

fn parse_age(s: &str) -> u32 {
    let Ok(n) = s.parse::<u32>() else {
        return 0;
    };
    n
}
```

The first prints `found 8`, because 7 is odd and 8 is the first even number. `parse_age` converts a string to a number and returns 0 if that fails (`Err`): `parse_age("42")` gives `42` and `parse_age("abc")` gives `0`. (`Ok` and `Err` are the two outcomes a conversion can have; this gets completed in the error handling post.)

Two more features make patterns more precise. A **match guard** adds an `if` to an arm: the arm is chosen only when the pattern fits and the condition is true. The `@` sign binds a value to a name at the same time as matching it against a pattern. The function `describe` uses both:

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

Let us read it: a rectangle whose width equals its height counts as a "square" (guard). A circle whose radius is between 0 and 1 is a "small circle", and `r` holds the radius (`@`). Any other circle gets a generic text. And the last arm, `other`, takes everything that is left and prints it with `{:?}`. We run it on a list of shapes, with `println!("{:<40} area = {:.2}", describe(s), s.area())`. (`{:<40}` means "left-aligned in a width of 40" and `{:.2}` means two decimal digits.)

```text
small circle, r = 0.5                    area = 0.79
circle, r = 2                            area = 12.57
square with side 3                       area = 9.00
Rect { w: 2.0, h: 5.0 }                  area = 10.00
Triangle(3.0, 4.0, 5.0)                  area = 6.00
Empty                                    area = 0.00
```

Row one: the circle of 0.5 hit the `@` arm. Row two: radius 2 is outside the range, so it reached the generic circle arm (`{radius}` prints `2.0` as `2`). Row three: a 3 by 3 rectangle is a square. Row four: a 2 by 5 rectangle fails the guard and reaches `other`. The last two rows are `other` as well. Order matters too: arms are tried from top to bottom, which is why the small-circle arm must come before the generic circle.

## Where match surprises you

- **Order in `match` matters.** Arms are tried from top to bottom and the first match wins. A more specific arm (like `Rect` with a guard) must come before a more general one.
- **`{:?}` works only on types that derive or implement `Debug`.** Forgetting the derive is one of the most common early errors.
- **If you match on a reference (like `&Shape`), the fields become references too.** That is why `radius` worked above without a `*`.
- **`unwrap()` on `None` panics.** Unless you are sure, use `match`, `if let` or `unwrap_or`. (In the `shape` program I also ran `None.unwrap_or(-1)` and got `-1`.)
- **Comparison with Go.** `iota` constants are lighter to write but carry no data and have no exhaustiveness check. A Rust enum needs more thought at first and gives you both in return.

## Exercise

1. Add a variant `Square(f64)` to `Shape` without touching `area`. Read the E0004 error and then fix it.
2. Write `fn largest(shapes: &[Shape]) -> Option<&Shape>` that returns `None` for an empty slice.
3. Make an enum for an order status (`Pending`, `Paid { tx_id: String }`, `Cancelled(String)`) and write a method that returns a readable label.

## What's next

"Collections and strings in Rust". Now that we have our own types, it is natural to want to keep many of them: with `Vec` and `HashMap`, and with a closer look at `String`.
