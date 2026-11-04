+++
date = '2027-02-24T10:00:00+03:30'
draft = false
title = 'Calling Rust from Go over FFI'
description = 'Build a Rust static library, link it into a Go program with cgo, and handle strings, byte slices, structs, panics and ownership across the boundary.'
contentType = 'tutorial'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "ffi", "cgo", "interop", "intermediate"]
cover = { image = "/images/covers/go-calls-rust-ffi.png", alt = "Calling Rust from Go over FFI", hiddenInSingle = true }
+++

You have a Go service, and you have a small piece of Rust that does one job very well, say a checksum or a parser you do not want to rewrite. The [previous post](/posts/go-rust-grpc-interop/) connected the two languages with gRPC: two programs, a network between them, and a typed contract. That is a good default, but sometimes a network hop for a function that takes a microsecond is the wrong price. The other way is to compile the Rust code into a library and call it from Go inside the same process, as an ordinary function call.

There is one catch that decides the whole design: **Go and Rust do not know each other's calling conventions, but both can speak C's.** So the call goes Go, then C, then Rust. In Go, the tool for this is **cgo**: it lets Go code call C functions. On the Rust side, we export functions with the C calling convention (an {{< term "ffi" "FFI" >}}, a foreign function interface, over the C {{< term "abi" "ABI" >}}). Everything that crosses this line is plain C: integers, pointers, flat structs. Strings, slices and ownership are not part of it, and handling them by hand is what most of this post is about.

The library is the `ffi-lib` crate from [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/), which exports `add`, `greet`, `free_string`, `checksum`, `point_length` and `point_scale` behind a hand-written C header, `ffi_lib.h`. I use it unchanged (the only addition is a test function behind a feature flag, in a copy). On the Go side, the [pointers post](/posts/go-pointers-memory/) is useful background.

> Everything was re-run locally with Go 1.27, Rust 1.90, macOS arm64, `CGO_ENABLED=1` and the system `cc`. The Rust library was rebuilt from the crate's source for this run.

## What this costs you up front

The price of going in-process is that the two worlds share one fate: **a Rust panic inside a function that Go called kills the whole process.** I show that at the end of the post. Keep it in mind while we build the rest.

## Build the Rust side first

```text
$ cargo build --release
$ ls -l target/release | grep ffi_lib
-rw-r--r--  16577808  libffi_lib.a
-rwxr-xr-x    366704  libffi_lib.dylib
```

The crate is configured to produce two kinds of library. `libffi_lib.a` is a **static library**: an archive of compiled code that the linker copies into your final binary. `libffi_lib.dylib` is a **dynamic library** that a program loads when it starts (on Linux that would be `.so`). I copied `libffi_lib.a` and `ffi_lib.h` into a Go package `ffi/` (header next to the Go file, library in `ffi/lib/`).

## The Go package

In a Go file that uses cgo, the comment right above `import "C"` is not a comment: it is C code and cgo directives. Here is the first part of `ffi/ffi.go`:

```go
/*
#cgo LDFLAGS: -L${SRCDIR}/lib -lffi_lib
#include <stdlib.h>
#include "ffi_lib.h"
*/
import "C"

func Add(a, b int32) int32 {
	return int32(C.add(C.int32_t(a), C.int32_t(b)))
}
```

Reading it: `#cgo LDFLAGS` tells the linker where the library is (`-L`, relative to the source directory) and what it is called (`-lffi_lib` means `libffi_lib`). The `#include` lines bring in the declarations, so Go knows what `C.add` is. After that, C functions and types appear in Go under the `C.` prefix.

C types never convert implicitly. A Go `int32` is not a `C.int32_t` even though they look the same, so every argument is wrapped (`C.int32_t(a)`) and every result is converted back. It is verbose, but it makes each crossing of the boundary visible.

## Strings and ownership

Two string facts make this the part where mistakes happen. First, a Go string is a pointer and a length, with no NUL byte at the end, while C expects a NUL-terminated array. So `C.CString` makes a copy of a Go string in C memory, allocated with `malloc`, and that copy is yours to free with `C.free`. Second, `greet` returns a string that Rust allocated, with **Rust's allocator**. That is different memory with a different owner.

```go
func Greet(name string) (string, error) {
	cs := C.CString(name)
	defer C.free(unsafe.Pointer(cs)) // malloc'd by C: free with C.free

	g := C.greet(cs) // allocated by Rust
	if g == nil {
		return "", errors.New("greet failed")
	}
	defer C.free_string(g) // back to Rust, never C.free
	return C.GoString(g), nil // copies into Go memory
}
```

The rule: **memory must be released by the allocator that produced it.** `C.free` on a pointer from Rust, or `free_string` on a pointer from `C.CString`, is {{< term "undefined-behavior" "undefined behaviour" >}}: it can crash or corrupt memory, or appear to work by luck. I did not run it on purpose. That is also why the Rust library ships a `free_string` function: the only code that can safely free a Rust string is Rust.

`C.GoString` copies the C string into Go memory. After that the Go string is independent, which is why it is safe to call `free_string` right afterwards (the `defer` runs after the `return` expression has been evaluated).

## Byte slices

Slices are simpler to pass: C only needs a pointer to the first byte and a length.

```go
func Checksum(data []byte) uint64 {
	if len(data) == 0 { // &data[0] would panic
		return uint64(C.checksum(nil, 0))
	}
	return uint64(C.checksum((*C.uint8_t)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}
```

`&data[0]` gives C a pointer straight into Go's memory, with no copy. An empty slice has no first element, so it needs its own branch.

To see that both languages really agree, the demo program computes the same checksum with a small Go implementation of FNV-1a and compares. This is the real output of `go run ./cmd/demo`:

```text
add(2, 40) = 42
greet: Hello, Roham! <nil>
checksum("hello") rust=11831194018420276491 go=11831194018420276491 same=true
checksum("") rust=14695981039346656037 go=14695981039346656037 same=true
length = 5
scaled = {6 8}
```

The first two lines are the simple call and the string round trip. The two `checksum` lines show that Rust and Go compute the same 64-bit number for both a normal input and an empty one. The last two lines are a `#[repr(C)]` struct round trip: `Length` passes a `C.Point` by value, so `Point{3, 4}` has length 5, and `Scale` copies the Go struct into a C one and passes its address to `point_scale`, which doubles it in place.

## The cgo pointer rules

Passing pointers to C has a rule, because Go's garbage collector can move and free Go memory, and C does not know that. In short: a Go pointer may be passed to C only if the Go memory it points to contains no Go pointers, and C must not keep the pointer after the call returns. The runtime checks the first part by default (`GODEBUG=cgocheck=1`, according to the cgo documentation).

I broke the rule on purpose with a struct that holds a `*int`, and passed it to an empty C function:

```go
type holder struct{ p *int }

n := 42
h := &holder{p: &n}
C.take(unsafe.Pointer(h)) // static void take(void *p) {}
```

```text
panic: runtime error: argument of cgo function has Go pointer to unpinned Go pointer
```

`go vet` found nothing wrong with this program, so the check happens at run time and only if that code path runs. That is the reason `Scale` above does not pass `&p` directly: it builds a C copy of the struct and passes the address of that.

## When Rust panics

A Rust panic normally unwinds the stack, but it must not unwind through an `extern "C"` function into foreign code. Rust turns this into an abort instead. To see what that means for a Go program, I added a function `ffi_test_panic` that just calls `panic!("boom from Rust")`. It sits behind a `test-panic` feature in a copy of the crate (the original is untouched). Go calls it, and this is what happened (the Rust backtrace lines are cut):

```text
calling Rust that panics
thread '<unnamed>' panicked at src/lib.rs:95:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
SIGABRT: abort
```

The Go program never reached its next line. With `GOTRACEBACK=crash` the exit code was 134 (the process was killed by SIGABRT); by default, Go's crash handler exited with code 2. Either way, the whole process is gone. So an exported Rust function must not let a panic escape: wrap the body in `catch_unwind` and return an error value, as `greet` does (it returns NULL on failure, which is why the Go side checks `g == nil`).

## A clean checkout, static or dynamic

The order of steps is fixed: `cargo build --release`, copy the artifacts, then `go build`. If you forget the first two, linking fails, because the Go tool cannot find the library:

```text
ld: library 'ffi_lib' not found
```

With the `.a` file, the Go binary has no dependency on the Rust library at run time, because the code is inside it. `otool -L` (macOS's `ldd`) lists only system libraries:

```text
$ otool -L ffidemo
  /usr/lib/libresolv.9.dylib
  /usr/lib/libSystem.B.dylib
```

(The version numbers on each line are cut. The original run, with Go 1.26, also listed `CoreFoundation`; the Go 1.27 run did not.)

If you link against the `.dylib` instead, a new line for `libffi_lib.dylib` appears, and it is recorded as an absolute path into the Cargo build directory (`.../target/release/deps/libffi_lib.dylib` in my build). Shipping that binary to another machine means fixing that path. Cross-compiling needs a C cross toolchain; I only mention it and did not try.

## The cost of the boundary

The machine was busy during my runs (load average around 4), so I ran no benchmark and I give no numbers. What I can say qualitatively: a cgo call costs more than a plain Go call (the Go documentation says so too), and the compiler cannot inline it. So prefer **coarse** calls: one call with a big buffer instead of a million calls with tiny ones.

## FFI, gRPC or wasm?

- **{{< term "ffi" "FFI" >}}**: one process and no serialization. In return you get `unsafe` code, manual ownership, a C toolchain in the build, and a Rust abort that kills your Go service.
- **gRPC**: separate processes, a typed contract, independent deploys and a failure in one does not kill the other. You pay for a network hop and encoding.
- **wasm** (WebAssembly): the guest code is sandboxed and has its own memory, so data is copied in and out, and you need a runtime to host it.

## Where the boundary bites

- Build Rust before Go; the Go build does not do it for you.
- Free memory with the allocator that made it: `C.free` for `C.CString`, `free_string` for what `greet` returned.
- Never keep a Go pointer in C after the call, and never pass Go memory that contains Go pointers.
- Check for an empty slice before taking `&data[0]`.
- A Rust panic in a function that Go called aborts the whole process.

## Exercise

1. C reads a `CString` only up to the first NUL byte. Make `Greet` return an error for names containing `\x00` (use `strings.IndexByte`) and test it.
2. Add `reverse_in_place` to the Rust crate (exercise 1 of [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/)) and wrap it in Go.

## What's next

The next post in this series is "Capstone: an event pipeline with Go, Rust and NATS". After gRPC and FFI, the capstone wires Go and Rust services together through NATS events.
