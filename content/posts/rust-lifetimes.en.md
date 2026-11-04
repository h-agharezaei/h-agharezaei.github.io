+++
date = '2026-12-22T10:00:00+03:30'
draft = false
title = 'Lifetimes in Rust'
description = "Rust lifetimes with runnable code: the longest function, real E0106 and E0597 errors, elision rules, structs holding references and what T: 'static means."
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "lifetimes", "intermediate", "borrowing"]
cover = { image = "/images/covers/rust-lifetimes.png", alt = "Lifetimes in Rust", hiddenInSingle = true }
+++

Here is the smallest program that makes Rust complain. We declare a variable `r`, inside a pair of braces we create another variable and point `r` at it, and after the braces we print `r`. In C this code compiles and its behaviour is undefined. In Go it also works silently, because the Go compiler moves the variable to the heap for you. In Rust it does not compile. The idea behind that complaint is called a {{< term "lifetime" "lifetime" >}}, and the idea itself is simpler than its name. In this post we start from that small program and go step by step to the `'a` symbol you see in function signatures.

If you have read [Borrowing and references in Rust](/posts/rust-borrowing-references/), you know the rule: a reference must not outlive the value it points to. This post takes that rule deeper. It comes after [Generics and traits in Rust](/posts/rust-generics-traits/), because where a lifetime is needed it is, just like a trait bound, a parameter in `<>` that the compiler uses to check something.

> I compiled and ran all the code below with Rust 1.90, and the outputs and compiler messages come from those runs. A few small programs (for example the dangling reference, two lifetimes, and `'a` on a function that returns a reference to a local) I wrote myself and ran to show the messages; where that is the case I say so in the text. I removed the "For more information…" line from the messages, and from one message an unrelated "unused variable" warning.

## The smallest example: a dangling reference

The program is this:

```rust
fn main() {
    let r;
    {
        let x = 5;
        r = &x;
    }
    println!("r: {r}");
}
```

```text
error[E0597]: `x` does not live long enough
 --> src/bin/dangling.rs:5:13
  |
4 |         let x = 5;
  |             - binding `x` declared here
5 |         r = &x;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `x` dropped here while still borrowed
7 |     println!("r: {r}");
  |                   - borrow later used here
```

Let us read the error together, because the three labels tell one complete story:

- Line 4: the variable `x` is created here.
- Line 5: `r` takes a reference to `x`, that is, it keeps its address.
- Line 6: the brace closes and `x` is gone ("dropped here"), while someone still points to it ("while still borrowed").
- Line 7: and then `r` is used ("later used here"). In other words, we would read from an address that is no longer valid.

A reference that points to a value that no longer exists is called a **dangling** reference (like a wire connected to nothing). Rust makes it impossible to create one, at compile time. How? For every reference the compiler keeps a question in mind: "for which part of the program is this reference valid?" And for every value another: "how long does this value live?" If the first reaches beyond the second, it reports an error. In our example `x` lives until line 6, but `r` is used on line 7.

That "part of the program where it is valid" is called a **lifetime**. One thing to know right from the start: a lifetime exists only at compile time. Nothing of it is in the final program and it does nothing at run time. It is only a check. And in most code you write, the compiler guesses the lifetimes itself and you write nothing, like the example above, which had no `'` in it. The question is when the compiler cannot guess.

## When the compiler cannot see through a function

Suppose we write a function that takes two strings and returns the longer one. It does not create a new string; it only hands back one of the two references:

```rust
fn longest(x: &str, y: &str) -> &str {
    if x.len() >= y.len() { x } else { y }
}
```

```text
error[E0106]: missing lifetime specifier
 --> src/bin/missing_annotation.rs:1:33
  |
1 | fn longest(x: &str, y: &str) -> &str {
  |               ----     ----     ^ expected named lifetime parameter
  |
  = help: this function's return type contains a borrowed value, but the signature does not say whether it is borrowed from `x` or `y`
help: consider introducing a named lifetime parameter
  |
1 | fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
  |           ++++     ++          ++          ++
```

Why does the compiler get stuck here? Imagine someone calls `longest` like this: `a` is a long-lived variable, and `b` was created in an inner pair of braces and dies early. If the result is `a`, it can be used after the braces. If it is `b`, it cannot, and we get the same problem as `x` and `r`. But which one is returned is decided by `x.len() >= y.len()` at **run time**, and the compiler can never know it. The compiler checks each function separately, and when it checks the places that call it, it looks only at the **signature**. So the signature has to say which inputs the result depends on. The error message says exactly this: "the signature does not say whether it is borrowed from `x` or `y`".

## What does `'a` say?

We apply the compiler's suggestion:

```rust
fn longest<'a>(x: &'a str, y: &'a str) -> &'a str {
    if x.len() >= y.len() { x } else { y }
}
```

Let us read it first. `<'a>` declares a **name** for a lifetime, like `<T>` declared a name for a type. `&'a str` means "a reference to `str` whose lifetime is `'a`". So the signature says: "`x`, `y` and the result all share one lifetime called `'a`". In plainer words: **"the result is valid only as long as both inputs are valid."** (According to the Rust Book, in practice `'a` becomes the smaller of the two input lifetimes.)

Here is the key point, and we must stop on it: **`'a` does not make anything live longer.** The symbol keeps nothing alive. It only describes a **relationship** between the references that pass through the function, so the compiler can check them at every place the function is called. Let us run the code with two ordinary strings:

```rust
fn main() {
    let a = String::from("salam donya");
    let b = String::from("hi");
    let result = longest(&a, &b);
    println!("longest: {result}");
}
```

```text
longest: salam donya
```

Both strings live until the end of `main` and `result` is inside the same span, so there is no problem. Now let us do the same thing but create `b` in an inner pair of braces and print `result` after them:

```rust
fn main() {
    let a = String::from("salam donya");
    let result;
    {
        let b = String::from("hi");
        result = longest(&a, &b);
    }
    println!("longest: {result}");
}
```

```text
error[E0597]: `b` does not live long enough
  --> src/bin/short_lived.rs:10:30
   |
 9 |         let b = String::from("hi");
   |             - binding `b` declared here
10 |         result = longest(&a, &b);
   |                              ^^ borrowed value does not live long enough
11 |     }
   |     - `b` dropped here while still borrowed
12 |     println!("longest: {result}");
   |                         ------ borrow later used here
```

The same story as before: `b` is gone on line 11 and `result` is used on line 12. Notice that the compiler complains even though in this run `a` is longer than `b` and the result would in fact be `a`. That is because the signature says the result depends on both, and the compiler trusts the signature, not the values. If we print `result` inside the same braces (I ran that too), it prints the same `longest: salam donya` without an error, because at that moment both are still alive.

Now let us see that the relationship can be changed. If a function returns only `x`, why should the result be tied to `y`? We declare two separate lifetimes:

```rust
fn first_of<'a, 'b>(x: &'a str, _y: &'b str) -> &'a str {
    x
}
```

(This is also a separate small program.) Now the result depends on `x` only. If we repeat the inner-braces experiment with it, that is, create `b` inside the braces, pass it as the second argument and print `result` outside, it compiles and prints `first: salam donya`. `b` has nothing to do with the result any more.

And the compiler makes sure the body agrees with the signature. If we write that the result is from `'a` but return `y`, which has `'b`:

```rust
fn first_of<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
    y
}
```

```text
error: lifetime may not live long enough
 --> src/bin/wrong_relation.rs:2:5
  |
1 | fn first_of<'a, 'b>(x: &'a str, y: &'b str) -> &'a str {
  |             --  -- lifetime `'b` defined here
  |             |
  |             lifetime `'a` defined here
2 |     y
  |     ^ function was supposed to return data with lifetime `'a` but it is returning data with lifetime `'b`
  |
  = help: consider adding the following bound: `'b: 'a`
```

The message says: "the function was supposed to return data with lifetime `'a` but it is returning data with lifetime `'b`". The promise we made in the signature was not kept. This is what I wanted to show: the signature is a contract, and the compiler checks the body against it as well as the callers.

And one last example, to prove that `'a` does not revive anything. A function that returns a reference to its own local variable is not fixed even by writing `'a`:

```rust
fn make<'a>() -> &'a String {
    let s = String::from("salam");
    &s
}
```

```text
error[E0515]: cannot return reference to local variable `s`
 --> src/bin/extend.rs:3:5
  |
3 |     &s
  |     ^^ returns a reference to data owned by the current function
```

`s` is dropped when `make` ends, and no label can hold it. The right way is to return the `String` itself (as in the borrowing post).

## Lifetime elision: why you do not always write `'a`

You may have asked: then why did we write nothing in `fn length(s: &String) -> usize` or `fn first_word(s: &str) -> &str`? Because the compiler applies three fixed rules to the signature, and in most cases it fills in the blanks itself. This is called **elision** (leaving out what can be inferred):

1. Each reference in the parameters gets its own lifetime.
2. If there is exactly one lifetime in the inputs, it is given to all the references in the output.
3. If one of the inputs is `&self` or `&mut self` (in a method), the lifetime of `self` is given to all the references in the output.

If after applying these rules the output lifetime is still unknown, you get the same E0106. `longest` is exactly that case: two inputs (rule 2 does not work) and no `self` (rule 3 does not work either). Now let us see one function in both forms, what you write and what the compiler infers:

```rust
// one input reference: elision gives the output the same lifetime
fn first_word(s: &str) -> &str {
    s.split(' ').next().unwrap_or("")
}

// written out in full, this is what the compiler infers
fn first_word_explicit<'a>(s: &'a str) -> &'a str {
    s.split(' ').next().unwrap_or("")
}
```

```text
salam
salam
```

The program calls both functions on `"salam donya"`, and both return `salam`. Rule 2 applies, so the result is borrowed from the input and returning part of it is safe.

## Structs that hold references

So far the references were function parameters. If a struct wants to hold a reference, it has the same problem: the struct must not outlive what it points to. So the struct's type also takes a lifetime parameter, just like a generic parameter:

```rust
struct Excerpt<'a> {
    part: &'a str,
}

impl<'a> Excerpt<'a> {
    // elision rule 3: the output gets the lifetime of &self
    fn part(&self) -> &str {
        self.part
    }
}

fn main() {
    let novel = String::from("Call me Ishmael. Some years ago...");
    let first_sentence = novel.split('.').next().unwrap();
    let e = Excerpt { part: first_sentence };
    println!("{}", e.part());
}
```

```text
Call me Ishmael
```

`Excerpt<'a>` means "an `Excerpt` that is valid as long as the data `part` points to is alive". That is why we must write `impl<'a>` as well, because `'a` is part of the type. The method `part` writes nothing because rule 3 does the job. In `main`, `novel` owns the text, `first_sentence` borrows a piece of it and `e` holds that piece. Everything is in one scope, so `Call me Ishmael` is printed. What if the `Excerpt` outlives `novel`?

```rust
let e;
{
    let novel = String::from("Call me Ishmael. Some years ago...");
    e = Excerpt { part: novel.split('.').next().unwrap() };
}
println!("{}", e.part);
```

```text
error[E0597]: `novel` does not live long enough
  --> src/bin/excerpt_dies.rs:9:29
   |
 8 |         let novel = String::from("Call me Ishmael. Some years ago...");
   |             ----- binding `novel` declared here
 9 |         e = Excerpt { part: novel.split('.').next().unwrap() };
   |                             ^^^^^ borrowed value does not live long enough
10 |     }
   |     - `novel` dropped here while still borrowed
11 |     println!("{}", e.part);
   |                    ------ borrow later used here
```

The same E0597 again, with the same three labels: `novel` was created, dropped at the closing brace, and `e.part` was used after that.

## `'static`

There is one special lifetime: `'static`, meaning "for the whole life of the program". String literals have it, because their text is stored inside the program itself and is never freed:

```rust
let greeting: &'static str = "salam";
```

There is a common misunderstanding about the bound `T: 'static`. It does not mean "the value lives forever". It means that **the type `T` contains no short-lived references**. An owned `String` or an `i32` satisfies this (they are not references at all), and they are dropped like any other value. The program below gives three values to a function that requires `T: Debug + 'static`:

```rust
fn takes_static<T: Debug + 'static>(value: T) {
    println!("got {value:?}");
}

let greeting: &'static str = "salam";
println!("{greeting}");

let owned = String::from("owned");
takes_static(owned);
takes_static(42);
takes_static(greeting);
```

```text
salam
got "owned"
got 42
got "salam"
```

It accepts all three. But if we hand it a reference to a local variable, that is `takes_static(&owned)`:

```text
error[E0597]: `owned` does not live long enough
  --> src/bin/static_fail.rs:9:18
   |
 8 |     let owned = String::from("owned");
   |         ----- binding `owned` declared here
 9 |     takes_static(&owned);
   |     -------------^^^^^^-
   |     |            |
   |     |            borrowed value does not live long enough
   |     argument requires that `owned` is borrowed for `'static`
10 | }
   | - `owned` dropped here while still borrowed
```

The message says the argument requires `owned` to be borrowed for `'static`, which is impossible because `owned` is dropped at the end of `main`. Do not reach for `'static` to fix a lifetime error unless the data really is a literal or a constant. Adding `'static` usually only moves the error somewhere else.

## When you are fighting the borrow checker

While you are learning, you do not need to stick lifetimes everywhere. If `Excerpt` gives you trouble, you can hold a `String` instead of borrowing and call `.to_string()` (or `.clone()`) once:

```rust
struct Excerpt {
    part: String, // owned: no lifetime parameter needed
}
```

I ran this version with the same inner-scope trick that broke the borrowing version (`e` is created inside braces and used outside), and it prints `Call me Ishmael` without an error. Why? Because `Excerpt` now owns its text and depends on nothing elsewhere. The cost is one allocation and copying the text. Using a reference with a lifetime is really a kind of optimisation: go for it when you have a reason.

## Common lifetime mistakes

- Lifetime annotations describe a relationship and never make a value live longer. If a value dies early, `'a` does not save it.
- Where elision works, write nothing. Add `'a` only when the compiler gives you E0106.
- A function cannot return a reference to its own local variable; return an owned value (for example the `String` itself).
- `'a` on a struct means "this struct does not outlive the borrowed data".
- Read the E0597 labels: "declared here", "dropped here" and "later used here". Once you find all three, it is usually clear what you have to move.

## Exercise

1. Write `fn longer_or_default<'a>(x: &'a str, default: &'static str) -> &'a str` that returns whichever is longer. (I ran it with `"ab"` and `"xyz"` and it prints `xyz`.) It compiles, because a reference with `'static` can be used wherever a shorter-lived reference is needed. Try to explain why.
2. Add a method `fn first_word(&self) -> &str` to `Excerpt` and call it.
3. Change `Excerpt` to hold a `String` and remove all the `'a`s.

## What's next

Now you know why the compiler sometimes asks for `'a` and what it is checking. The next place where these rules show up again is closures: a closure captures the variables around it and has to follow the same rules. That is why the next step is "Closures and iterators in Rust".
