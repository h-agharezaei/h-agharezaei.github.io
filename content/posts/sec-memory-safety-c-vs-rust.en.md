+++
date = '2027-05-22T10:00:00+03:30'
draft = false
title = 'Memory safety: C versus Rust'
description = 'Memory safety in C, Go and Rust: out-of-bounds, use-after-free, double free, overflow and data races, with real sanitizer and compiler output.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "memory-safety", "c", "rust", "sanitizers"]
cover = { image = "/images/covers/sec-memory-safety-c-vs-rust.png", alt = "Memory safety: C versus Rust", hiddenInSingle = true }
+++

The previous post, [Common cryptography mistakes](/posts/sec-crypto-mistakes/), was about sound primitives used wrongly. This one is about a lower layer: code that reads or writes memory it does not own. {{< term "memory-safety" "Memory safety" >}} is the property that this cannot happen. The ideas behind Rust's side are in [Ownership in Rust](/posts/rust-ownership/), [Borrowing and references in Rust](/posts/rust-borrowing-references/) and [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/); Go's are in [Pointers and the memory model in Go](/posts/go-pointers-memory/).

> Defensive only. These are tiny programs of my own, each triggering one bug class on purpose, run on macOS arm64 with Apple clang 21, rustc 1.90 and Go 1.26. No payloads, no exploitation. Demo sources are local.

## C: the bugs

Four files, each with one mistake. First a write of 10 bytes into `char buf[8]`:

```c
char buf[8];
memset(buf, 'A', n);   /* n == 10 */
```

`cc -Wall -Wextra` printed only an unused-parameter warning, nothing about the overflow. The plain build aborted with exit code 133 and no message (I believe a fortified `memset` check, but I did not verify that). With `-fsanitize=address`:

```
ERROR: AddressSanitizer: stack-buffer-overflow on address 0x00016f325da8 ...
WRITE of size 10 at 0x00016f325da8 thread T0
    #1 ... in main oob.c:6
```

A {{< term "buffer-overflow" "buffer overflow" >}} caught, with the line. A {{< term "use-after-free" "use-after-free" >}}: `free(p); printf("%d", p[0]);`. The plain build printed `4`, not the 42 I stored, and exit code 0: wrong data with no crash. The compiler warned about nothing. {{< term "addresssanitizer" "AddressSanitizer" >}}:

```
ERROR: AddressSanitizer: heap-use-after-free on address 0x602000000970 ...
READ of size 4 at 0x602000000970 thread T0
    #0 ... in main uaf.c:7
```

A double free (`free(p); free(p);`) aborted the plain build with exit code 133 and no text; ASan said `attempting double-free`. Last, an {{< term "integer-overflow" "integer overflow" >}}: `count * 4` with `count` = 2^30. Plain build printed `bytes=0`, the kind of too-small size that later feeds an allocation. With `-fsanitize=undefined`:

```
intov.c:6:23: runtime error: signed integer overflow: 1073741824 * 4 cannot be represented in type 'int'
```

Fix for the first one: clamp `n` to `sizeof buf`. The fixed file built with `-Wall -Wextra -fsanitize=address,undefined` ran clean and printed `A`. I only state what I ran; compiler hardening flags such as `-D_FORTIFY_SOURCE` and stack protectors exist, but I did not test them here.

## Rust: the same mistakes

Out-of-bounds `v[10]` on a 3-element vector:

```
None
thread 'main' panicked at oob.rs:5:21:
index out of bounds: the len is 3 but the index is 10
```

`v.get(10)` returned `None`; indexing panicked. A panic is a clean stop, not a silent read. Dangling references do not compile:

```
error[E0597]: `x` does not live long enough
5 |         r = &x;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `x` dropped here while still borrowed
```

Dropping a value while borrowed gives `error[E0505]: cannot move out of `s` because it is borrowed`. Sending an `Rc` to a thread gives:

```
error[E0277]: `Rc<i32>` cannot be sent between threads safely
```

Overflow depends on the build. `250 + 5 + 1` in a `u8`: with `-C opt-level=0` it panics with `attempt to add with overflow`; with `-O` it printed `0` (wrapped). So release builds do not check unless you ask. Use `checked_add` or `wrapping_add` to say what you mean.

## Go in between

Go bounds-checks at runtime: `panic: runtime error: index out of range [10] with length 3`. Races are not prevented, but `go run -race` found one on a shared counter: `WARNING: DATA RACE`, with the read and the previous write goroutines. See [Concurrency patterns](/posts/go-concurrency-patterns/).

| Bug class | C | Go | Rust (safe) |
|---|---|---|---|
| Out-of-bounds | silent or abort | panic | panic, or `get()` |
| Use-after-free | wrong data, no crash | not possible | compile error E0505/E0597 |
| Double free | abort, no message | not possible | not possible |
| Integer overflow | UB, found by UBSan | wraps | panic (debug), wraps (release) |
| Data race | not checked | `-race` finds it | compile error E0277 |

## The unsafe boundary

Rust's `unsafe` blocks mark where the compiler stops checking, so reviewers know where to look. I did not run Miri or `cargo geiger`; I only name them as tools to check or count unsafe code. Other defences I did not run: CHERI hardware, Fil-C, and sanitizers in CI. I also did not verify any industry statistics, so I quote none.

## A few things to watch

- Warnings caught none of these four; sanitizers caught all.
- A silent wrong answer (`4`) is worse than a crash.
- Release builds in Rust wrap on overflow by default.
- `unsafe` is a promise you make, not a switch that makes code fast.

## Exercise

Write a C function that copies a string into a small buffer, break it, and find it with ASan. Then port it to Rust and see which error you get.

## What's next

The next post is Fuzzing to find security bugs.
