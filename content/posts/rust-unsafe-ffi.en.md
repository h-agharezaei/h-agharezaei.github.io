+++
date = '2027-02-18T10:00:00+03:30'
draft = false
title = 'Unsafe and FFI in Rust'
description = 'Rust unsafe and FFI: what unsafe allows, wrapping it in a safe API, calling C from Rust and exposing a C-ABI library (cdylib, staticlib) to C.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "unsafe", "ffi", "c", "intermediate"]
cover = { image = "/images/covers/rust-unsafe-ffi.png", alt = "Unsafe and FFI in Rust", hiddenInSingle = true, hiddenInList = true }
+++

The [previous post](/posts/rust-macros/) was about macros. This one is about the escape hatch: `unsafe`. Everything we have learned so far ([ownership](/posts/rust-ownership/), [smart pointers](/posts/rust-smart-pointers/)) is what safe Rust guarantees for you. `unsafe` is how you say "I will uphold those guarantees myself" when the compiler cannot check them, mostly to talk to C. Go has the same idea in its `unsafe` package with `unsafe.Pointer`, as a [pointer post](/posts/go-pointers-memory/) readers may know. Here we build a tiny C-ABI library and link a C program to it.

> Everything below was compiled and run with Rust 1.90, edition 2024, on macOS. The demo lives in two local crates: `unsafe-demo` and `ffi-lib`.

## The five superpowers

Inside an `unsafe` block or function you can do exactly five extra things: dereference a raw pointer, call an unsafe function, access a mutable static, implement an unsafe trait, and access union fields. Here is all five:

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

`*const T` and `*mut T` are raw pointers. Creating one is safe (I made one from the address `0x1234` without `unsafe`); only dereferencing is not, because nobody checked it points to valid memory. Raw pointers have no lifetimes or borrow rules, and may be null.

An important point: `unsafe` does **not** turn off the borrow checker. It only unlocks those five operations. Ordinary references inside an `unsafe` block are still checked:

```rust
let mut v = vec![1, 2, 3];
unsafe {
    let first = &v[0];
    v.push(4);
    println!("{first}");
}
```

```text
error[E0502]: cannot borrow `v` as mutable because it is also borrowed as immutable
```

Inside the block the burden is on you: undefined behavior (UB) is possible for any broken promise, such as a dangling or misaligned pointer, or two live `&mut` to the same data.

## A safe abstraction

The good pattern is a small `unsafe` core behind a safe function. The standard library's `split_at_mut` is the classic case; the borrow checker cannot see that two halves of a slice do not overlap, so I wrote my own:

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

The `assert!` is what makes the function safe for every caller. I tested it with a normal split, `mid = 0`, and a `should_panic` case for `mid > len`; all 3 tests pass, and `[1,2,3,4,5]` split at 2 and edited became `[100, 2, 300, 4, 5]`. Convention: `// SAFETY:` on every block, a `# Safety` doc section on every `unsafe fn`.

## Calling C from Rust

Declaring foreign functions is an `unsafe extern` block. In edition 2024 a plain `extern "C" { }` is rejected. C strings need `CString` (owned, NUL-terminated) and `CStr` (borrowed):

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
Ok("hello")
```

The pitfall: C strings end at the first NUL, so `CString::new` refuses interior NULs. `CString::new("he\0llo")` returns `Err`, printed as `nul byte found in provided data at position: 2`.

## Exposing Rust through the C ABI

The `ffi-lib` crate has `crate-type = ["cdylib", "staticlib"]`. In edition 2024 the attribute is `#[unsafe(no_mangle)]`; the old `#[no_mangle]` fails with `unsafe attribute used without unsafe`, and the old `extern` block with `extern blocks must be unsafe`. Data that crosses the boundary must be C-compatible, hence `#[repr(C)]`:

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

`checksum(const uint8_t*, size_t)` (a FNV-1a hash) rebuilds a slice with `slice::from_raw_parts`, and `point_length`/`point_scale` take a `Point` by value and by pointer. The header `ffi_lib.h` is written by hand.

**Ownership** is the rule that matters: memory must be freed by the allocator that made it. `greet` allocates with Rust's allocator, so C must give it back with `free_string`, never `free()`. Freeing the same pointer twice is a double free, which is UB, so I did not run it. And panics must not unwind into C: `greet` wraps its body in `catch_unwind` and returns NULL. As a safe demonstration, a plain `extern "C" fn` that panics does not unwind; the runtime aborts:

```text
about to panic inside extern "C"
thread 'main' panicked at panic_abort.rs:3:5:
oops
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

Exit code was 134 (SIGABRT).

## Linking a C program

```c
char *g = greet("Roham");
printf("greet: %s\n", g);
free_string(g);
```

```text
$ cargo build --release
$ nm -gU target/release/libffi_lib.dylib
... T _add   T _checksum   T _free_string   T _greet   T _point_length   T _point_scale
$ cc main.c -I. target/release/libffi_lib.a -o main_static && ./main_static
add(2, 40) = 42
greet: Hello, Roham!
checksum("hello") = 11831194018420276491
length = 5.0
scaled = (6.0, 8.0)
```

Linking the `.dylib` with `-lffi_lib` gave the same output. This library stays unchanged for a later post where Go calls it.

For checking real `unsafe` code, use Miri (an interpreter that detects UB) and sanitizers (AddressSanitizer and friends). Both need a nightly toolchain, so I did not run them here.

## A few things to watch

- `unsafe` does not disable the borrow checker; it moves responsibility for five operations to you.
- Keep `unsafe` blocks tiny, and put a `// SAFETY:` comment on each.
- Never free memory with the wrong allocator, and never free twice.
- Never let a panic unwind across `extern "C"`; use `catch_unwind` and return an error code or NULL.
- Validate pointers and lengths at the boundary (null checks), because C cannot.

## Exercise

1. Add `fn reverse_in_place(data: *mut u8, len: usize)` to `ffi-lib` and call it from C.
2. Write a safe `fn my_swap(a: &mut [i32], i: usize, j: usize)` using raw pointers and a test.

## What's next

Next: performance and benchmarking with Criterion in Rust.
