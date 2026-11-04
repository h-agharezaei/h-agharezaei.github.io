+++
date = '2027-05-22T10:00:00+03:30'
draft = false
title = 'Memory safety: C versus Rust'
description = 'Memory safety in C, Go and Rust: out-of-bounds, use-after-free, double free, overflow and data races, with real sanitizer and compiler output.'
contentType = 'analysis'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "memory-safety", "c", "rust", "sanitizers"]
cover = { image = "/images/covers/sec-memory-safety-c-vs-rust.png", alt = "Memory safety: C versus Rust", hiddenInSingle = true }
+++

Here is a C program that allocates four integers, stores 42 in the first one, frees the memory, and then prints the first integer anyway. It compiles without a single warning. It runs, exits with status 0, and prints a number. In my first run that number was `4`, not 42. In three re-runs for this rewrite it was `5`. No crash, no error, just wrong data that nobody asked about.

That is the heart of this post. {{< term "memory-safety" "Memory safety" >}} is the property that a program cannot read or write memory it does not own. C does not give you that property: the compiler trusts you, and when you are wrong, the result is not an error but whatever happens to be in memory. Rust gives it to you by default, and checks most of it before the program ever runs.

[Common cryptography mistakes](/posts/sec-crypto-mistakes/) was about sound primitives used wrongly; this is a lower layer, where the memory under your program is itself the weak point. The ideas behind Rust's side are in [Ownership in Rust](/posts/rust-ownership/), [Borrowing and references in Rust](/posts/rust-borrowing-references/) and [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/); Go's are in [Pointers and the memory model in Go](/posts/go-pointers-memory/).

> Defensive only. These are tiny programs of my own, each triggering one bug class on purpose, and they only touch their own memory. No payloads, no exploitation. I ran them on macOS arm64 with Apple clang 21 and rustc 1.90; the original run used Go 1.26 and I re-ran the Go part with Go 1.27.3. The demo sources are local examples.

## C: the bugs

I wrote four small C files, each with one mistake (plus a fixed version of the first). For each bug I did the same thing: build it normally, then build it again with a **sanitizer**, a compiler option that adds checks to the program and reports the bug while it runs. Normal build means `cc -Wall -Wextra`, which turns on the compiler's usual warnings.

**Buffer overflow.** The first file writes 10 bytes into a buffer of 8:

```c
char buf[8];
memset(buf, 'A', n);   /* n == 10 */
```

Writing past the end of a buffer is a {{< term "buffer-overflow" "buffer overflow" >}}. The compiler printed one warning, about an unused parameter, and nothing about the overflow. The normal build aborted with exit code 133 and no message. Why? I looked at the binary with `nm`: it calls `___memset_chk` instead of plain `memset`, which is a checked version the compiler substituted; so I believe the abort comes from that check. When I turned this fortification off (`-D_FORTIFY_SOURCE=0`), the program still did not run to a normal exit but aborted with a different code, 134, and the binary also references `___stack_chk_fail`, the stack protector. I did not dig further into which check fired in that second case. The point is that on this machine the system's default hardening happened to stop this particular bug, silently. Now with AddressSanitizer (`-fsanitize=address`):

```
ERROR: AddressSanitizer: stack-buffer-overflow on address 0x00016f325da8 ...
WRITE of size 10 at 0x00016f325da8 thread T0
    #1 ... in main oob.c:6
```

{{< term "addresssanitizer" "AddressSanitizer" >}} says what happened (a write of 10 bytes, onto the stack, past the buffer) and where (`oob.c`, line 6). It also prints a frame description that says the object `buf` has 8 bytes (offsets 32 to 40) and that the access "overflows this variable". The address changes on every run; the shape of the message does not.

**Use-after-free.** The second file is the one from the opening:

```c
int *p = malloc(4 * sizeof *p);
p[0] = 42;
free(p);
printf("%d\n", p[0]);           /* use after free */
```

Reading memory after you freed it is a {{< term "use-after-free" "use-after-free" >}}. The normal build printed a number that was not 42 (`4` in the original run, `5` in all three of my re-runs) and exited with code 0. The value is whatever the allocator left in that memory when it took it back, so it is not stable between machines or versions. This is the dangerous kind of bug: the program keeps running with wrong data. With AddressSanitizer:

```
ERROR: AddressSanitizer: heap-use-after-free on address 0x602000000970 ...
READ of size 4 at 0x602000000970 thread T0
    #0 ... in main uaf.c:7
```

It says: a read of 4 bytes, from memory that was already freed, at line 7. Further down its report also names the line that freed the memory (line 6) and the line that allocated it, so you see the whole life of the pointer.

**Double free.** `free(p); free(p);` aborted the normal build with exit code 133 and no text. AddressSanitizer said `attempting double-free`, and again named both `free` calls.

**Integer overflow.** The last file multiplies a count by 4 to compute a size in bytes. The count is 2^30, so the result does not fit in a signed `int`:

```c
int count = INT_MAX / 2 + 1 + (argc - 1);   /* 2^30 */
int bytes = count * 4;                      /* signed overflow */
```

An {{< term "integer-overflow" "integer overflow" >}} is dangerous in C because signed overflow is {{< term "undefined-behavior" "undefined behavior" >}}: the language does not say what happens. The normal build printed `bytes=0`, a size that is too small, the kind of number that later goes into an allocation and makes it too small for the data copied into it. With `-fsanitize=undefined` the report is:

```
intov.c:6:23: runtime error: signed integer overflow: 1073741824 * 4 cannot be represented in type 'int'
```

That is exact: file, line, column, the two numbers, and the type.

**The fix for the first bug** is to never trust `n`: clamp it to `sizeof buf`. The fixed file, built with `-Wall -Wextra -fsanitize=address,undefined`, ran clean and printed `A`. I only state what I ran. Compiler hardening options such as stack protectors exist (and as seen above, some are on by default here), but I did not test them systematically.

## Rust: the same mistakes

Now the same kinds of mistakes in Rust. I compiled each file with plain `rustc` (rustc 1.90).

**Out of bounds.** `v[10]` on a 3-element vector. The program first prints `v.get(10)`, then indexes:

```
None
thread 'main' panicked at oob.rs:5:21:
index out of bounds: the len is 3 but the index is 10
```

`get(10)` returned `None`, a value that says "there is nothing there", and the code is forced to handle it. Plain indexing panicked, with the length, the index and the position in the source. A panic is a clean stop. It is not a silent read of whatever was next to the vector.

**Dangling reference.** A reference to a value that has already been dropped. This does not compile:

```
error[E0597]: `x` does not live long enough
5 |         r = &x;
  |             ^^ borrowed value does not live long enough
6 |     }
  |     - `x` dropped here while still borrowed
```

Reading it: the code stores a reference to `x` in `r` (line 5), then the inner block ends and `x` is dropped (line 6), but `r` is used later. The compiler marks the borrow, the place where the value dies, and the later use. This is the same idea as the C use-after-free, except the compiler refuses to build it. The real message has a few more lines, which I left out.

**Drop while borrowed.** The Rust version of the C `free; read` pair is `drop(s)` while a reference `r` to `s` is still used afterwards:

```
error[E0505]: cannot move out of `s` because it is borrowed
```

The compiler says exactly the same thing in another form: you cannot give up a value while somebody still holds a reference to it.

**Sending a non-thread-safe value to a thread.** `Rc` is a reference-counted pointer whose counter is not safe to update from two threads. Moving one into a new thread gives:

```
error[E0277]: `Rc<i32>` cannot be sent between threads safely
```

This is the compile-time version of a data race: the type system knows which types may cross threads and which may not.

**Overflow depends on the build.** `250 + 5 + 1` in a `u8` (an 8-bit unsigned number whose maximum is 255): with `-C opt-level=0` (debug-like) it panics with `attempt to add with overflow`; with `-O` it printed `0`, which means it wrapped around. So release builds do not check unless you ask. When you care, say what you mean: `checked_add` returns an `Option`, and `wrapping_add` wraps on purpose.

## Go in between

Go sits between the two. Indexing is bounds-checked at runtime: `panic: runtime error: index out of range [10] with length 3`. Data races are not prevented by the language, but its race detector found one in my demo, where two goroutines increment the same counter. Running `go run -race . race` printed `WARNING: DATA RACE`, with the goroutine that read, and the goroutine that did the previous write, each with its line. (The memory address and goroutine numbers change from run to run.) See [Concurrency patterns: worker pool and errgroup](/posts/go-concurrency-patterns/).

| Bug class | C | Go | Rust (safe) |
|---|---|---|---|
| Out-of-bounds | silent or abort | panic | panic, or `get()` |
| Use-after-free | wrong data, no crash | not possible | compile error E0505/E0597 |
| Double free | abort, no message | not possible | not possible |
| Integer overflow | UB, found by UBSan | wraps | panic (debug), wraps (release) |
| Data race | not checked | `-race` finds it | compile error E0277 |

The table summarises what I ran, plus what the language rules say (Go's garbage collector makes use-after-free and double free impossible in normal code; safe Rust cannot express them).

## The unsafe boundary

Rust is not "nothing can go wrong". Safe Rust gives the guarantees above. Code inside an `unsafe` block takes those checks off, so that the compiler trusts you again, but the block marks exactly where reviewers must look. I did not run Miri or `cargo geiger`; I only name them as tools to check or count unsafe code. Other defences I did not run: CHERI hardware, Fil-C, and sanitizers in CI. I also did not verify any industry statistics, so I quote none.

## What the runs show

- Warnings caught none of these four C bugs. Sanitizers caught all of them.
- A silent wrong answer (`4`, or `5`) is worse than a crash, because nobody notices it.
- Release builds in Rust wrap on overflow by default.
- `unsafe` is a promise you make to the compiler, not a switch that makes code fast.

## What's next

The next post is "Fuzzing to find security bugs". Here I wrote the bad input by hand; fuzzing lets a machine search for the inputs that trigger bugs like these.
