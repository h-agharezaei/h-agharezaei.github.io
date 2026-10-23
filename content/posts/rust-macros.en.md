+++
date = '2027-02-14T10:00:00+03:30'
draft = false
title = 'Macros in Rust'
description = 'Rust macros: write declarative macros with macro_rules! and a derive procedural macro with syn and quote, with hygiene, hand expansion and compiler errors.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "macros", "proc-macro", "intermediate"]
cover = { image = "/images/covers/rust-macros.png", alt = "Macros in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-trait-objects-dyn/) traits were the topic. Now to the other tool for abstraction: **macros**. You already use them every day: `println!`, `vec!`, and the `#[derive(Serialize)]` from [Serde and JSON in Rust](/posts/rust-serde-json/). In this post we write both kinds ourselves, a declarative macro with `macro_rules!` and a derive macro in its own crate.

> I ran everything with Rust 1.90, `syn` 2.0.119, `quote` 1.0.47 and `proc-macro2` 1.0.107. Outputs come from real runs of a local workspace.

## A macro is code that writes code

A function runs at runtime and receives values. A macro runs at compile time, receives *tokens* and returns new code that the compiler then compiles. That is why `println!` can take a variable number of arguments, which a normal function cannot. The `!` marks a macro call.

## Declarative macros

A `macro_rules!` macro is a list of patterns and templates. `$x:expr` captures an expression; the part after `:` is the **fragment specifier**. Others: `ident` (a name), `ty` (a type), `tt` (a single token tree, the most flexible).

```rust
macro_rules! square {
    ($x:expr) => { $x * $x };
}

macro_rules! max {
    ($x:expr) => ($x);
    ($x:expr, $($rest:expr),+) => {{
        let a = $x;
        let b = $crate::max!($($rest),+);
        if a > b { a } else { b }
    }};
}
```

`$(...),+` is repetition: one or more comma-separated items. `max!` calls itself with the tail, so it works for any count and any `PartialOrd` type:

```text
square!(3 + 1) = 16
max!(3, 9, 4) = 9
max!(2.5, 1.5) = 2.5
```

Note `square!(3 + 1)` is 16, not `3 + 1 * 3 + 1 = 7`. An `expr` fragment stays one expression node, so Rust does not have C's textual-substitution trap.

A literal for `HashMap`, using `$(...),*` and an optional trailing comma:

```rust
macro_rules! hashmap {
    ($($k:expr => $v:expr),* $(,)?) => {{
        let mut m = ::std::collections::HashMap::new();
        $( m.insert($k, $v); )*
        m
    }};
}
```

`hashmap!{ "a" => 1, "b" => 2, }` gave `[("a", 1), ("b", 2)]` (sorted before printing). Macros can also generate items. This one takes an `ident` and a list of variants:

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

Iterating `Color::ALL` and printing `c.name()` gave `Red`, `Green`, `Blue`. I also wrote `make_struct!(Point { x: i32, y: i32 })` with `ty` fragments; it printed `Point::field_names()` as `["x", "y"]`. A `tt` counter, `count_tts!(a b c d)`, returned 4.

### Expansion by hand, and hygiene

`cargo expand` needs nightly, so I expand by hand. `square!(3 + 1)` becomes `(3 + 1) * (3 + 1)`, with the argument kept as a unit. A test proves it:

```rust
assert_eq!(square!(3 + 1), (3 + 1) * (3 + 1));
```

```text
test tests::square_expansion_is_equivalent ... ok
```

**Hygiene** means variables created inside a macro live in their own scope. `max!` has an internal `a`, and I called it with my own `a`:

```rust
let a = 100;
let r = max!(a, 7);  // a = 100, max!(a, 7) = 100
let x = 10;
double_with_temp!(x) // macro has `let x = 2; $e * x` -> 20
```

The second prints 20, not 4: the macro's `x` and mine are different variables.

### The error when you misuse it

`square!(3, 4)` does not match any rule:

```text
error: no rules expected `,`
 --> demo/src/bin/bad_square.rs:3:29
  |
3 |     println!("{}", square!(3, 4));
  |                             ^ no rules expected this token in macro call
  |
note: while trying to match meta-variable `$x:expr`
```

Read it as: "the rule wanted one `expr` and met a comma". Errors like this point at the call site, and also at the macro definition.

## A derive macro

Procedural macros are Rust functions from tokens to tokens, and must live in a crate with `proc-macro = true`. So we use a workspace: `describe_derive` (the macro) and `demo` (the user). Dependencies: `syn = "2"` parses tokens into a syntax tree, `quote = "1"` builds tokens from a template, `proc-macro2` is the shared token type.

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

Using it: `#[derive(Describe)] struct User { name: String, age: u32, tags: Vec<String>, email: Option<String> }` and `println!("{}", User::describe())`:

```text
User
  name: String
  age: u32
  tags: Vec<String>
  email: Option<String>
```

On an `enum`, the macro returns a `compile_error!` tied to a span (the name `Shape`), so the message shows up in the right place:

```text
error: Describe can only be derived for structs
 --> demo/src/bin/bad_derive.rs:4:6
  |
4 | enum Shape {
  |      ^^^^^
```

That is what `serde` does conceptually: its derive reads your struct with `syn`, then generates `impl Serialize` code with `quote`, honoring attributes like `#[serde(rename)]`. There are two more kinds of procedural macros: attribute-like (`#[route(GET, "/")]`, which replaces the item it is attached to) and function-like (`sql!(...)`, called like `macro_rules!` but written in Rust code).

## A few things to watch

- Prefer a function or generics. Reach for a macro only for variable arguments, new syntax, or generating repetitive items.
- Macros cost compile time (a proc-macro crate and `syn` must be built) and readability; error messages get worse.
- Debug with small tests and small inputs; the by-hand expansion above is a good habit.
- Always use `$crate::` and full paths like `::std::collections::HashMap` inside exported macros.
- Return `syn::Error` with a good span instead of panicking.

## Exercise

1. Write `min!` like `max!`, and test `min!(5, 2, 8)`.
2. Extend `Describe` so it also generates `field_count() -> usize`.

## What's next

Next is unsafe and FFI in Rust: what `unsafe` really allows, and how to call C code.
