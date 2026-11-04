+++
date = '2027-02-18T10:00:00+03:30'
draft = false
title = 'Unsafe and FFI in Rust'
description = 'Rust unsafe and FFI: what unsafe allows, wrapping it in a safe API, calling C from Rust and exposing a C-ABI library (cdylib, staticlib) to C.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "unsafe", "ffi", "c", "intermediate"]
cover = { image = "/images/covers/rust-unsafe-ffi.png", alt = "Unsafe and FFI in Rust", hiddenInSingle = true }
+++

We want to split a slice into two mutable halves, one from the start up to `mid` and the other from `mid` to the end. We know the two halves do not overlap, so changing both at the same time is fine. Let us write it:

```rust
fn split(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    (&mut s[..mid], &mut s[mid..])
}
```

```text
error[E0499]: cannot borrow `*s` as mutable more than once at a time
 --> c.rs:2:26
  |
1 | fn split(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
  |             - let's call the lifetime of this reference `'1`
2 |     (&mut s[..mid], &mut s[mid..])
  |     ---------------------^--------
  |     |     |              |
  |     |     |              second mutable borrow occurs here
  |     |     first mutable borrow occurs here
  |     returning this value requires that `*s` is borrowed for `'1`
  |
  = help: use `.split_at_mut(position)` to obtain two mutable non-overlapping sub-slices
```

The compiler sees two mutable borrows of `*s` and rejects it. From `..mid` and `mid..` it cannot conclude that these are two separate ranges; the borrow checker's rules look only at `s` itself. The last line of the message tells us to use `split_at_mut`, and where does the standard library's `split_at_mut` come from? From what this post is about: `unsafe`.

In Rust, `unsafe` means "here the compiler cannot prove it is correct; I promise it is". The promise is yours. This post shows exactly what `unsafe` unlocks, what it does **not** unlock, and what your promise is. Then we use the same idea to talk to C: we build a small library with a **C ABI** (a binary contract that C understands too) and link a C program against it.

This post follows [Macros in Rust](/posts/rust-macros/). What we have learned so far, [ownership](/posts/rust-ownership/) and [smart pointers](/posts/rust-smart-pointers/), is what safe Rust guarantees for you. `unsafe` is where you take over part of that guarantee yourself. Go has something similar with its `unsafe` package ([the pointers post](/posts/go-pointers-memory/)).

> I recompiled and re-ran all the code below with Rust 1.90 (`rustc 1.90.0`), edition 2024, on macOS (arm64) with `cc` (Apple clang). The demo is two local crates, `unsafe-demo` and `ffi-lib`, with no external dependencies. A few small examples (the `split` error, dereferencing without `unsafe`, `static mut` with `println!`, and `unsafe fn`) I wrote and ran as separate programs, only to show the errors. From the error messages I removed the `note:` lines and the "For more information…" lines. **Miri** (an interpreter that finds {{< term "undefined-behavior" "UB" >}}) is not installed on this machine, so I did not run any of this code under it.

## What does `unsafe` unlock?

Inside an `unsafe` block or an `unsafe fn`, exactly **five** extra things become allowed (according to the Rust Book and the Rust Reference):

1. dereferencing a {{< term "raw-pointer" "raw pointer" >}}
2. calling an `unsafe` function
3. reading or writing a `static mut`
4. implementing an `unsafe` trait
5. reading the fields of a `union`

These five have something in common: the compiler cannot check that they are correct. If you try them without `unsafe`, you get an error:

```text
error[E0133]: dereference of raw pointer is unsafe and requires unsafe block
 --> a.rs:4:20
  |
4 |     println!("{}", *p);
  |                    ^^ dereference of raw pointer
```

```text
error[E0133]: call to unsafe function `abs` is unsafe and requires unsafe block
 --> d.rs:6:20
  |
6 |     println!("{}", abs(-5));
  |                    ^^^^^^^ call to unsafe function
```

Both messages say the same thing: "this is unsafe and needs an `unsafe` block". Here are all five in one program:

```rust
static mut COUNTER: u32 = 0;

#[repr(C)]
union IntOrFloat { i: u32, f: f32 }

unsafe trait Zeroable {}
unsafe impl Zeroable for u32 {}

fn zeroed<T: Zeroable>() -> T {
    // SAFETY: Zeroable promises that all-zero bytes are a valid T.
    unsafe { std::mem::zeroed() }
}

unsafe fn read_twice(p: *const i32) -> (i32, i32) {
    unsafe { (*p, *p) }
}

fn main() {
    let mut x = 10;
    let (r1, r2) = (&raw const x, &raw mut x);   // raw pointers
    unsafe { *r2 += 1; println!("raw: {} {}", *r1, *r2); }
    println!("{:?}", unsafe { read_twice(&x) });
    unsafe { COUNTER += 1; COUNTER += 1; let c = COUNTER; println!("COUNTER = {c}"); }
    let z: u32 = zeroed();
    let u = IntOrFloat { f: 1.0 };
    println!("zeroed = {z}, 1.0f32 bits = {:#x}", unsafe { u.i });
}
```

```text
raw: 11 11
(11, 11)
COUNTER = 2
zeroed = 0, 1.0f32 bits = 0x3f800000
```

One by one:

- **Raw pointer** (`*const T` and `*mut T`): a bare address. `&raw const x` and `&raw mut x` make two of them from `x`. Creating a raw pointer is safe (in the demo I made one from the number `0x1234` and printed it, and no `unsafe` was needed); only dereferencing it is unsafe, because nobody has checked that it points to valid memory. A raw pointer has no lifetime, no borrow rules, and can be null. That is why `*r2 += 1` and `*r1` are both in an `unsafe` block, and both see 11: two pointers to one variable, which ordinary `&mut` and `&` would not allow.
- **An `unsafe` function** (`read_twice`): a function whose safety depends on a contract the caller must uphold (here: `p` must be a valid pointer to an `i32`). Calling it needs an `unsafe` block. The second output line, `(11, 11)`, is its result.
- **`static mut`**: a mutable global variable. Because any thread can touch it at any time, Rust cannot rule out a {{< term "data-race" "data race" >}}, and you are responsible. Notice that I wrote `let c = COUNTER;` separately and did not put `COUNTER` inside `println!`. The reason is that `println!` takes a reference to its argument, and in edition 2024 taking a reference to a `static mut` is a compile error (a lint that is an error by default in this edition):

  ```text
  error: creating a shared reference to mutable static
   --> b.rs:6:24
    |
  6 |         println!("{}", COUNTER);
    |                        ^^^^^^^ shared reference to mutable static
  ```

  Reading the value into a local variable (`let c = COUNTER;`) avoids the problem.
- **`unsafe trait`** (`Zeroable`): a trait whose implementation is itself a promise: "all-zero bytes are a valid value of this type". Code that calls `std::mem::zeroed()` relies on that promise. `unsafe impl Zeroable for u32` means I give this promise for `u32` (and for `u32` it is true).
- **`union`**: like a struct, but all fields share the same memory. Writing `f: 1.0` and reading `i` means "look at the bits of `1.0f32` as an integer", which is `0x3f800000`. The compiler does not know which field is currently valid, so reading one is unsafe.

## What does `unsafe` **not** turn off?

A common misunderstanding: "inside `unsafe` all checks are off". That is not true. Only those five extra things become allowed. All other rules, including the borrow checker on ordinary references, keep working:

```rust
let mut v = vec![1, 2, 3];
unsafe {
    let first = &v[0];
    v.push(4);
    println!("{first}");
}
```

```text
warning: unnecessary `unsafe` block
 --> bc_still_on.rs:3:5
  |
3 |     unsafe {
  |     ^^^^^^ unnecessary `unsafe` block

error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
 --> bc_still_on.rs:5:9
  |
4 |         let first = &v[0];
  |                      - immutable borrow occurs here
5 |         v.push(4);
  |         ^^^^^^^^^ mutable borrow occurs here
6 |         println!("{first}");
  |                    ----- immutable borrow later used here
```

Two things show up in the message. First, the compiler warns that this `unsafe` block was not needed at all, because none of the five things is in it. Second, we get the usual borrow checker error: `first` is a reference into `v`, `v.push` takes a mutable borrow of `v`, and after that `first` is used again. The `unsafe` block changed nothing.

So in practice it is not a lawless land. But inside those five things, the responsibility is yours. If you break your promise, you get **undefined behavior** (UB). This means the language makes no commitment about what the program does, and the compiler is allowed to assume that it never happens. The result can be a crash, it can be wrong output, and it can seem to work until the day the compiler or the machine changes. According to the Rust Reference, examples include dereferencing a dangling pointer (one that is no longer valid) or a misaligned one, two live `&mut` to the same data, a data race, and producing a value that is invalid for its type (for example a `bool` with the value 3). I did not run any of these and I show no UB output: the result differs from run to run and proves nothing.

## `unsafe fn` and the `unsafe` block: two different roles

The word `unsafe` has two complementary meanings:

- On a **definition** (`unsafe fn`, `unsafe trait`): "to use this, the caller must uphold a condition". Write that condition in the documentation, in a section called `# Safety`.
- On a **use** (an `unsafe { ... }` block): "I have upheld the condition". Write the reason above the block in a `// SAFETY:` comment.

In edition 2024 these two are even separated: the body of an `unsafe fn` is itself considered "safe", and needs an `unsafe` block for unsafe operations inside it. That is why `read_twice` above has an `unsafe { (*p, *p) }` inside. If we remove it:

```rust
unsafe fn read_first(p: *const i32) -> i32 {
    *p
}
```

```text
warning[E0133]: dereference of raw pointer is unsafe and requires unsafe block
 --> e.rs:2:5
  |
2 |     *p
  |     ^^ dereference of raw pointer
  |
note: an unsafe function restricts its caller, but its body is safe by default
```

(In this example, the call `read_first(&x)` from `main` also produced the same E0133 error, because calling an `unsafe` function needs a block.) The `note` says it: `unsafe fn` only restricts the caller, and the body is safe by default.

## A safe abstraction: back to `split_at_mut`

The good pattern is a small `unsafe` core behind a **safe** function. Callers never write `unsafe`, and correctness has to be proved in only one place. This is what the standard library's `split_at_mut` does. To show it, I wrote my own version:

```rust
pub fn my_split_at_mut(s: &mut [i32], mid: usize) -> (&mut [i32], &mut [i32]) {
    let len = s.len();
    assert!(mid <= len, "mid out of range");
    let ptr = s.as_mut_ptr();
    // SAFETY: mid <= len, so [0, mid) and [mid, len) are in bounds and do not
    // overlap; `s` is mutably borrowed for the returned lifetime, so nothing
    // else can touch the memory meanwhile.
    unsafe {
        (
            std::slice::from_raw_parts_mut(ptr, mid),
            std::slice::from_raw_parts_mut(ptr.add(mid), len - mid),
        )
    }
}
```

Reading it:

1. `assert!(mid <= len, ...)` checks the condition that the code below relies on. If `mid` is larger, the program panics before anything gets damaged. This check is what makes the function safe for **every** caller.
2. `s.as_mut_ptr()` gives a raw pointer to the first element.
3. `from_raw_parts_mut(ptr, mid)` builds a slice from a start address and a length: the first half. `from_raw_parts_mut(ptr.add(mid), len - mid)` starts the second half at the middle.
4. The `SAFETY:` comment says why this is right: both ranges are inside the slice, they do not overlap, and because `s` is mutably borrowed for the lifetime of the result, nobody else touches that memory.

I wrote three tests: a normal split, `mid = 0`, and a `should_panic` case for `mid > len`. All three passed (`3 passed`). In `main` I also split `[1,2,3,4,5]` at 2, changed the first element of each half, and `[100, 2, 300, 4, 5]` was printed.

## Calling C from Rust

Now the same idea for another language. {{< term "rust-ffi" "FFI" >}} (Foreign Function Interface) means calling code written in another language. Rust talks to C through the **C ABI**, a contract about how arguments reach a function and how the result comes back. Any C function we call from Rust is unknown to the compiler, so calling it is `unsafe`.

The foreign function is declared inside an `unsafe extern` block. In edition 2024 the plain `extern "C" { }` is rejected (you will see this error in the next section). For C strings we need `CString` (an owned string with a trailing NUL) and `CStr` (a borrowed view):

```rust
unsafe extern "C" {
    fn abs(x: i32) -> i32;
    fn strlen(s: *const c_char) -> usize;
}

let s = CString::new("hello").unwrap();
println!("abs(-5) = {}", unsafe { abs(-5) });
println!("strlen = {}", unsafe { strlen(s.as_ptr()) });
println!("{:?}", unsafe { CStr::from_ptr(s.as_ptr()) }.to_str());
```

```text
abs(-5) = 5
strlen = 5
back to Rust: Ok("hello")
```

`abs` and `strlen` come from the system's C library and needed no extra linking. `strlen` wants a `*const c_char`, the address of a string that ends with a zero byte (NUL). `CString` adds that final NUL and `as_ptr()` gives its address. The last line is the way back: `CStr::from_ptr` turns the address into a borrowed string again and `to_str()` converts it to a `&str` (it was `Ok("hello")`, because it is valid UTF-8).

A trap: a C string ends at the first NUL, so `CString::new` refuses a string with a NUL in the middle. `CString::new("he\0llo")` returns an `Err`, which prints as `nul byte found in provided data at position: 2`. The reason is that C would have seen only `he` and silently dropped the rest.

## Offering Rust to C

Now the opposite direction: make Rust code that a C program can call. The crate called `ffi-lib` has `crate-type = ["cdylib", "staticlib"]` in its `Cargo.toml`: it builds a dynamic library (`.dylib` on macOS) and a static one (`.a`) for C. Three things are needed:

- `extern "C"` so the function is called with the C ABI.
- `#[unsafe(no_mangle)]` so the function's name in the built file stays `add` and the compiler does not turn it into an internal mangled name.
- `#[repr(C)]` on every struct that crosses the boundary, so its memory layout is like C's.

In edition 2024 the `unsafe(...)` around the attribute is required. I tried the old form:

```text
error: unsafe attribute used without unsafe
 --> old_syntax.rs:1:3
  |
1 | #[no_mangle]
  |   ^^^^^^^^^ usage of unsafe attribute
  |
help: wrap the attribute in `unsafe(...)`

error: extern blocks must be unsafe
 --> old_syntax.rs:3:1
  |
3 | extern "C" { fn abs(x: i32) -> i32; }
  | ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
```

(I shortened the compiler's suggested fix under `help:`.) The library:

```rust
#[repr(C)]
pub struct Point { pub x: f64, pub y: f64 }

#[unsafe(no_mangle)]
pub extern "C" fn add(a: i32, b: i32) -> i32 { a.wrapping_add(b) }

#[unsafe(no_mangle)]
pub unsafe extern "C" fn greet(name: *const c_char) -> *mut c_char {
    catch_unwind(|| {
        if name.is_null() { return std::ptr::null_mut(); }
        // SAFETY: caller promised a valid NUL-terminated string.
        let Ok(name) = unsafe { CStr::from_ptr(name) }.to_str() else { return std::ptr::null_mut() };
        CString::new(format!("Hello, {name}!")).map_or(std::ptr::null_mut(), CString::into_raw)
    }).unwrap_or(std::ptr::null_mut())
}

#[unsafe(no_mangle)]
pub unsafe extern "C" fn free_string(s: *mut c_char) {
    if !s.is_null() {
        // SAFETY: `s` came from CString::into_raw in `greet`, freed once.
        drop(unsafe { CString::from_raw(s) });
    }
}
```

A few notes:

- `add` uses `wrapping_add` so that overflow has a defined result (in debug builds ordinary overflow panics, and a panic in a function called from C is not good; see below).
- `greet` takes a C string and returns a new string on the heap. It checks for NULL, because C will not do that for you. `CString::into_raw` takes the string's ownership away from Rust and hands only the address to C.
- The function is `unsafe extern "C"` and has a `# Safety` section (in the real code): the safety of `name` is guaranteed by the C caller.
- `checksum(const uint8_t*, size_t)` (an FNV-1a hash) builds a slice from the address and length with `slice::from_raw_parts`, and `point_length` and `point_scale` take a `Point` by value and by pointer respectively. I wrote the header `ffi_lib.h` by hand.

The most important rule is **memory ownership**: memory must be freed by the same allocator that allocated it. `greet` allocates with Rust's own allocator, so C must give it back with `free_string`, not with `free()`. Freeing the same pointer twice is also a double free and UB; I did not run that.

The second rule is about panics. If a panic reaches C code from inside a Rust function, C knows nothing about it. That is why `greet` puts its body in `catch_unwind` and returns NULL instead of panicking. To see what happens without it, I built a plain `extern "C" fn` that panics. In this Rust version it does not unwind, and the runtime aborts the program:

```text
about to panic inside extern "C"

thread 'main' panicked at panic_abort.rs:3:5:
oops
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

(I removed the `note:` lines and the stack trace, because the trace contains paths from my machine.) The program's exit code was 134, which means the SIGABRT signal.

## Linking the C program

The C program calls all the functions. Its important part is string ownership: C gets the string from `greet`, prints it, and must give it back to `free_string`:

```c
char *g = greet("Roham");
printf("greet: %s\n", g);
free_string(g);
```

First we build the library with `cargo build --release`. `nm -gU` shows the exported function names of the `.dylib` (I removed the addresses). Then we link the C program against the static library and run it:

```text
$ cargo build --release
$ nm -gU target/release/libffi_lib.dylib
T _add   T _checksum   T _free_string   T _greet   T _point_length   T _point_scale
$ cc main.c -I. target/release/libffi_lib.a -o main_static && ./main_static
add(2, 40) = 42
greet: Hello, Roham!
checksum("hello") = 11831194018420276491
length = 5.0
scaled = (6.0, 8.0)
```

The symbol type `T` means the function is in the library's code section and is visible from outside. The six functions we marked with `#[unsafe(no_mangle)]` are exactly these. Reading the output: `add(2, 40)` is 42; the string that Rust made and C printed and then returned to Rust; the FNV-1a hash of `hello`; the length of the vector (3, 4), which is 5; and the same vector after doubling, `(6.0, 8.0)` (`point_scale` changed it in place through the pointer). Linking against the `.dylib` with `-lffi_lib` printed the same five lines. We will reuse this library later to call it from Go.

## How do we check `unsafe` code?

Tests only show that the paths you tried work. For `unsafe` code there is another tool: Miri, an interpreter that runs the program step by step and stops when it meets UB (for example an out-of-bounds access or a dangling pointer). Sanitizers can be used too. Neither is installed on this machine, so I did not run them; but for code with a lot of `unsafe` I would run Miri on it for sure.

## Rules at the `unsafe` boundary

- **`unsafe` does not turn off the borrow checker.** It only allows five things and gives you the responsibility for them (the demo above showed this with `E0502`).
- **Keep `unsafe` blocks small** and write `// SAFETY:` on each one. Put the rest of your program behind a safe function.
- **Never free memory with the wrong allocator and never free it twice.** Whatever Rust allocates, Rust must free.
- **Never let a panic cross an `extern "C"` boundary.** Use `catch_unwind` and an error code or NULL.
- **Validate pointers and lengths at the boundary** (null check), because C will not do it for you.

## Exercise

1. Add a function `fn reverse_in_place(data: *mut u8, len: usize)` to `ffi-lib` and call it from C.
2. Write a safe function `fn my_swap(a: &mut [i32], i: usize, j: usize)` using raw pointers, with a test.

## What's next

"Performance and benchmarking with Criterion in Rust": now that it works, how fast is it?
