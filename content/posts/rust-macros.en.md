+++
date = '2027-02-14T10:00:00+03:30'
draft = false
title = 'Macros in Rust'
description = 'Rust macros: write declarative macros with macro_rules! and a derive procedural macro with syn and quote, with hygiene, hand expansion and compiler errors.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "macros", "proc-macro", "intermediate"]
cover = { image = "/images/covers/rust-macros.png", alt = "Macros in Rust", hiddenInSingle = true }
+++

You have used macros since your very first Rust program, maybe without noticing. Take `println!("{} and {}", a, b)`: it accepts any number of arguments of any types, and it checks the format string at compile time. An ordinary Rust function does none of this, because its parameters have a fixed number and fixed types. The `!` at the end of the name is the sign that says "this is not a function, it is a macro". `vec![1, 2, 3]` is a macro too, and so is `#[derive(Debug)]`.

A **macro** is code that writes code, and it does so at compile time, before the program runs. In this post we write two kinds from scratch: the simpler `macro_rules!` kind (also called a {{< term "macro-rules" "declarative" >}} macro), and then a `derive` macro, the same kind as `#[derive(Serialize)]` in [Serde and JSON in Rust](/posts/rust-serde-json/). This post follows [Trait objects and dyn in Rust](/posts/rust-trait-objects-dyn/): there we saw how a trait puts several types under one name, and here we see another tool for avoiding repeated code.

> I re-ran all the code below with Rust 1.90 (`rustc 1.90.0`), `syn` 2.0.119, `quote` 1.0.47 and `proc-macro2` 1.0.107 (taken from the `Cargo.lock` of the same demo). The outputs are copied from real runs of a local workspace. Two small examples (`add!`, and `square!` with an argument that has a side effect) I wrote and ran as separate programs, only to show them here. In the error messages I replaced the temporary directory path with `<tmp>` and removed the "For more information…" lines.

## What does a macro take, and what does it return?

A function takes values: the number 5, the string `"hello"`. A macro takes **tokens**. A token is the smallest meaningful piece of the program text: a name (`x`), a number (`5`), a symbol (`+`) or a pair of parentheses. Before anything else, the compiler breaks the program into tokens, and a macro works at this stage: it receives some tokens and hands back other tokens. In place of the macro call, the compiler puts the new tokens and compiles those. This replacement is called **expansion**.

The smallest example:

```rust
macro_rules! add {
    ($a:expr, $b:expr) => {
        $a + $b
    };
}

fn main() {
    println!("{}", add!(2, 3));
    println!("{}", add!(10 * 2, 5));
}
```

```text
5
25
```

A `macro_rules!` definition is one or more "rules", and each rule has two halves separated by `=>`:

- **The pattern** (left side): the shape of tokens the macro should see. `$a:expr` means "take an expression and call it `$a`". The part after the `:` is the **fragment specifier**, and it tells the compiler what kind of piece to accept. Common ones: `expr` (an expression), `ident` (a name), `ty` (a type) and `tt` (a "token tree": one token or one group of tokens inside brackets, the most flexible one).
- **The template** (right side): the code that is written in place of the call, with `$a` and `$b` filled in with what we captured.

So `add!(2, 3)` expands to `2 + 3`, and `add!(10 * 2, 5)` expands to `10 * 2 + 5`. The output 25 shows that. I saw both output lines myself by running this small program.

## A slightly more serious macro: square! and two surprises

Now `square!`:

```rust
macro_rules! square {
    ($x:expr) => { $x * $x };
}
```

If you wrote `square!(3 + 1)` in C with `#define`, the text would be substituted as-is and you would get `3 + 1 * 3 + 1`, which is 7. Here the demo prints:

```text
square!(3 + 1) = 16
```

The reason is that a fragment of type `expr` stays a complete expression node: `3 + 1` is substituted as one unit, as if it had invisible parentheses around it. So the textual-substitution trap of C does not exist here. `cargo expand`, which shows the expanded macro, needs, as far as I know, a nightly compiler, and I did not install it. Instead I prove the expansion with a test:

```rust
assert_eq!(square!(3 + 1), (3 + 1) * (3 + 1));
```

```text
test tests::square_expansion_is_equivalent ... ok
```

The test says `square!(3 + 1)` is the same as writing `(3 + 1) * (3 + 1)` ourselves, and both are 16.

But there is another surprise. The template `$x * $x` writes the expression **twice**, so if the expression does something (prints, increments a counter), it happens twice:

```rust
fn next(counter: &mut i32) -> i32 {
    *counter += 1;
    println!("next() called, counter = {counter}");
    *counter
}

let mut c = 0;
let r = square!(next(&mut c));
println!("result = {r}");
```

```text
next() called, counter = 1
next() called, counter = 2
result = 2
```

`next` was called twice: once for the first `$x` (value 1) and once for the second `$x` (value 2), and the result was 1 × 2 = 2, not 1 × 1. If you do not want this, store the value in a variable first. The next macro does exactly that.

## Repetition and recursion: max!

We want `max!(3, 9, 4)` to work with any number of arguments. The idea: the larger of the first one and "the largest of the rest". The first rule handles the single-element case, and the second rule calls the macro again with the rest:

```rust
macro_rules! max {
    ($x:expr) => ($x);
    ($x:expr, $($rest:expr),+) => {{
        let a = $x;
        let b = $crate::max!($($rest),+);
        if a > b { a } else { b }
    }};
}
```

The expression `$(...),+` is a **repetition**: "one or more of this pattern, separated by commas". `$($rest:expr),+` captures all the remaining expressions, and `$($rest),+` in the template writes them back one after another with commas. `$crate::max!` means "this same macro from this same crate"; write it this way for exported macros so they work outside the crate too. The double `{{ }}` means the template is a block and can contain `let`. Because the first expression goes into `a`, each expression is evaluated only once here (unlike `square!`).

```text
max!(3, 9, 4) = 9
max!(2.5, 1.5) = 2.5
```

It works for any type that can be compared with `>`, because the macro only writes code and the compiler checks the types afterwards.

## Macros for repetitive definitions

A literal for `HashMap`, which Rust does not have. This time we use `$(...),*`, meaning "zero or more", and `$(,)?` lets you write one extra trailing comma at the end of the list:

```rust
macro_rules! hashmap {
    ($($k:expr => $v:expr),* $(,)?) => {{
        let mut m = ::std::collections::HashMap::new();
        $( m.insert($k, $v); )*
        m
    }};
}
```

The pattern says "several pairs of `key => value`". In the template, `$( m.insert($k, $v); )*` writes one `insert` line per pair. `hashmap!{ "a" => 1, "b" => 2, }` printed `[("a", 1), ("b", 2)]` (I sorted it before printing, because `HashMap` order is not fixed). I wrote the full path `::std::collections::HashMap` so the macro works anywhere, even where `HashMap` is not imported.

A macro can also generate whole definitions: structs, enums and `impl` blocks. This one takes a name and a list of variants, and builds both the enum and a method that returns the name of each variant:

```rust
macro_rules! make_enum {
    ($name:ident { $($variant:ident),+ $(,)? }) => {
        #[derive(Debug, Clone, Copy, PartialEq)]
        pub enum $name { $($variant),+ }
        impl $name {
            pub const ALL: &'static [$name] = &[$($name::$variant),+];
            pub fn name(&self) -> &'static str {
                match self { $($name::$variant => stringify!($variant)),+ }
            }
        }
    };
}
make_enum!(Color { Red, Green, Blue });
```

`stringify!($variant)` turns the variant's name into a string. Iterating over `Color::ALL` and printing `c.name()` gave three lines, `Red -> Red`, `Green -> Green` and `Blue -> Blue` (the first part is the `{:?}` output and the second is `name()`, which happen to be the same here). I also wrote a `make_struct!(Point { x: i32, y: i32 })` with `ty` fragments, and `Point::field_names()` printed `["x", "y"]`, and a `tt`-based counter, `count_tts!(a b c d)`, returned 4.

## Hygiene: the macro's variables do not mix with yours

In `max!` we created a temporary variable called `a`. What if your program also has a variable called `a` and you pass it to `max!`? In C macros such a clash is a headache. In Rust it is not: this is called **hygiene**. Names created inside a macro and names that come from outside are separate variables, even if they look the same. In the demo:

```rust
let a = 100;
let r = max!(a, 7);  // a = 100, max!(a, 7) = 100
let x = 10;
double_with_temp!(x) // macro has `let x = 2; $e * x` -> 20
```

```text
a = 100, max!(a, 7) = 100
double_with_temp!(x) = 20
```

In `double_with_temp!` the template is `let x = 2; $e * x`. If the macro's `x` and my `x` were the same variable, `$e * x` would be 2 × 2 = 4. The result is 20: `$e` is my own `x` (10), multiplied by the macro's internal `x` (2) gives 20.

## When you call a macro wrongly

Because a macro has patterns, a bad call also gets a message. `square!(3, 4)` matches no rule:

```text
error: no rules expected `,`
 --> demo/src/bin/bad_square.rs:3:29
  |
3 |     println!("{}", square!(3, 4));
  |                             ^ no rules expected this token in macro call
  |
note: while trying to match meta-variable `$x:expr`
 --> <tmp>/demo/src/lib.rs:3:6
  |
3 |     ($x:expr) => {
  |      ^^^^^^^
```

Line by line: the error is at the comma (column 29), because our rule accepts only one `$x:expr` and expects no further token after it. The `note` says which part of the pattern the compiler was matching, and by showing the macro definition (`lib.rs:3:6`) it tells you what the pattern was. So these messages point both at the call site and at the macro definition.

## Procedural macros: a macro as a Rust function

`macro_rules!` is patterns and templates. Sometimes that is not enough: for example you want to write `#[derive(Describe)]` on a struct, and have the macro **read the struct's fields** and build code from them. For this we use the other kind: a {{< term "procedural-macro" "procedural macro" >}}. It is an ordinary Rust function that the compiler runs at compile time: it takes tokens and returns tokens. Anything you know in Rust can be used inside it.

One restriction: a procedural macro must live in a separate crate with `proc-macro = true` in its `Cargo.toml`. So the demo is a workspace with two crates: `describe_derive` (the macro itself) and `demo` (its user). Three dependencies help: `syn = "2"` turns the tokens into a syntax tree you can read (for example "this is a struct with these fields"), `quote = "1"` builds tokens from a template that looks like Rust code, and `proc-macro2` is the token type they share.

```rust
#[proc_macro_derive(Describe)]
pub fn derive_describe(input: TokenStream) -> TokenStream {
    let ast = parse_macro_input!(input as DeriveInput);
    let name = &ast.ident;
    let fields = match &ast.data {
        Data::Struct(s) => match &s.fields {
            Fields::Named(f) => &f.named,
            _ => return syn::Error::new_spanned(name,
                "Describe needs a struct with named fields").to_compile_error().into(),
        },
        _ => return syn::Error::new_spanned(name,
            "Describe can only be derived for structs").to_compile_error().into(),
    };
    let lines: Vec<String> = fields.iter().map(|f| {
        let ty = &f.ty;
        format!("{}: {}", f.ident.as_ref().unwrap(),
                quote!(#ty).to_string().replace(" ", ""))
    }).collect();
    let title = name.to_string();
    quote! {
        impl #name {
            pub fn describe() -> String {
                let mut out = String::from(#title);
                #( out.push_str("\n  "); out.push_str(#lines); )*
                out
            }
        }
    }.into()
}
```

Step by step:

1. `#[proc_macro_derive(Describe)]` tells the compiler this function answers `#[derive(Describe)]`. `input` holds the tokens of the struct itself.
2. `parse_macro_input!` uses `syn` to turn those tokens into a `DeriveInput`: the type's name is in `ast.ident` and its contents are in `ast.data`.
3. The `match` accepts only structs with named fields. For anything else we return a `syn::Error`, which becomes a `compile_error!`, that is, an ordinary compiler error and not a panic.
4. For each field we build a string `name: type`.
5. `quote!` builds the code to be written: an `impl` with a `describe` method. `#name` and `#title` put the values from above into the template, and `#( ... )*` repeats once for each member of `lines`, like `$(...)*` in `macro_rules!`.

Usage: `#[derive(Describe)] struct User { name: String, age: u32, tags: Vec<String>, email: Option<String> }` and then `println!("{}", User::describe())`:

```text
User
  name: String
  age: u32
  tags: Vec<String>
  email: Option<String>
```

The macro never ran `User`; at compile time it only wrote an `impl` from its definition, and we called that like any other function. On an `enum`, the macro returns an error tied to a span (a specific place in the code, here the name `Shape`), so the message appears in the right place:

```text
error: Describe can only be derived for structs
 --> demo/src/bin/bad_derive.rs:4:6
  |
4 | enum Shape {
  |      ^^^^^
```

You can look at `serde` the same way: as far as I know, its derive also reads your struct's fields with `syn`, writes the `impl Serialize` code with `quote`, and applies attributes such as `#[serde(rename)]`. That is the same general shape as our `Describe`, only much more complete.

There are two other kinds of procedural macro that I did not write: **attribute-like** ones, which look like `#[route(GET, "/")]` and replace the item they are attached to, and **function-like** ones, which are called like `macro_rules!` (`sql!(...)`) but are written in Rust code. The core is the same in all three: tokens come in, tokens go out.

## Costs and good habits

- **Prefer functions or generics.** Reach for a macro only for variable arguments, new syntax, or generating repetitive definitions. If a function does the job, you do not need a macro.
- **Macros have a cost.** Building the macro crate and `syn` adds compile time, a macro is harder for others to read, and its error messages are usually more confusing than those of a function.
- **Debug with small inputs and small tests.** Expanding by hand like `square!` and writing an `assert_eq!` is a good habit.
- **Inside exported macros** always use `$crate::` and full paths like `::std::collections::HashMap`, because you do not know what the caller has imported.
- **Return a `syn::Error` with a proper span instead of panicking**, so the macro's user sees the error on their own code.
- **Watch for double evaluation.** If the template writes a `$x` more than once, capture it in a `let`, as `max!` did.

## Exercise

1. Write a `min!` macro like `max!` and test `min!(5, 2, 8)`.
2. Extend `Describe` so that it also generates `field_count() -> usize`.
3. Change `square!` so the argument is evaluated only once, and run the `next` example again.

## What's next

"Unsafe and FFI in Rust": what `unsafe` really allows, and how to call C code.
