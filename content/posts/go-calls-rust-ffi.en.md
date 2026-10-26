+++
date = '2027-02-24T10:00:00+03:30'
draft = false
title = 'Calling Rust from Go over FFI'
description = 'Build a Rust static library, link it into a Go program with cgo, and handle strings, byte slices, structs, panics and ownership across the boundary.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "ffi", "cgo", "interop", "intermediate"]
cover = { image = "/images/covers/go-calls-rust-ffi.png", alt = "Calling Rust from Go over FFI", hiddenInSingle = true }
+++

[The previous post of this series](/posts/go-rust-grpc-interop/) connected Go and Rust over the network with gRPC. This one is the in-process way: one binary, Rust compiled into a library, and Go calling it through the C ABI with **cgo**. The library is the `ffi-lib` crate from [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/), which exports `add`, `greet`, `free_string`, `checksum`, `point_length` and `point_scale` behind a hand-written `ffi_lib.h`. I use it unchanged. For pointers on the Go side, see the [pointers post](/posts/go-pointers-memory/).

> Go 1.26, Rust 1.90, macOS arm64, `CGO_ENABLED=1` with the system `cc`. Everything below was run locally.

## Build the Rust side first

```text
$ cargo build --release
$ ls -l target/release | grep ffi_lib
-rw-r--r--  16577808  libffi_lib.a
-rwxr-xr-x    366704  libffi_lib.dylib
```

I copied `libffi_lib.a` and `ffi_lib.h` into a Go package `ffi/` (header next to the Go file, library in `ffi/lib/`).

## The Go package

The comment right above `import "C"` is C code and cgo directives. Here is the first part of `ffi/ffi.go`:

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

My `LDFLAGS` needed no extra macOS libraries; the link line shows cgo adding `-framework CoreFoundation -lresolv` itself. C types never convert implicitly, so each argument is wrapped (`C.int32_t`) and each result converted back.

## Strings and ownership

Go strings are not NUL-terminated, so `C.CString` copies one into C memory allocated with `malloc`. That copy is yours to free with `C.free`. `greet` returns a different kind of memory: it was allocated by **Rust's allocator**.

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

The rule: memory must be released by the allocator that produced it. `C.free` on a Rust pointer (or `free_string` on a `CString`) is undefined behavior, so I did not run it. `C.GoString` copies, so the Go string stays valid after `free_string`.

## Byte slices

```go
func Checksum(data []byte) uint64 {
	if len(data) == 0 { // &data[0] would panic
		return uint64(C.checksum(nil, 0))
	}
	return uint64(C.checksum((*C.uint8_t)(unsafe.Pointer(&data[0])), C.size_t(len(data))))
}
```

`&data[0]` gives C a pointer into Go memory without copying. I compared it with a Go FNV-1a implementation in the demo's `main`:

```text
add(2, 40) = 42
greet: Hello, Roham! <nil>
checksum("hello") rust=11831194018420276491 go=11831194018420276491 same=true
checksum("") rust=14695981039346656037 go=14695981039346656037 same=true
length = 5
scaled = {6 8}
```

The last two lines are the `#[repr(C)]` struct round trip: `Length` passes a `C.Point` by value, and `Scale` copies the Go struct into a C one and passes its address to `point_scale`.

## cgo pointer rules

In short: a Go pointer may be passed to C only if the Go memory it points to holds no Go pointers, and C must not keep it after the call. The runtime checks this by default (`GODEBUG=cgocheck=1`). I broke the rule on purpose with a struct holding a `*int`:

```go
type holder struct{ p *int }

n := 42
h := &holder{p: &n}
C.take(unsafe.Pointer(h)) // static void take(void *p) {}
```

```text
panic: runtime error: argument of cgo function has Go pointer to unpinned Go pointer
```

`go vet` was clean on this program; the check happens at run time. That is why `Scale` passes a C copy.

## When Rust panics

A panic cannot unwind out of an `extern "C"` function; the process aborts. In my copy of the crate I added `ffi_test_panic` behind a `test-panic` feature (the original is untouched) and called it from Go:

```text
calling Rust that panics
thread '<unnamed>' panicked at src/lib.rs:95:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
SIGABRT: abort
```

With `GOTRACEBACK=crash` the exit code was 134; by default Go's crash handler exited with 2. Either way the process dies, so exported functions should use `catch_unwind` and return an error value, as `greet` does.

## Clean checkout, static or dynamic

The order is fixed: `cargo build --release`, copy the artifacts, then `go build`. Without the archive, linking fails with `ld: library 'ffi_lib' not found`. With the `.a`, the Go binary has no dependency on the Rust library:

```text
$ otool -L ffidemo
  CoreFoundation.framework/.../CoreFoundation
  /usr/lib/libresolv.9.dylib
  /usr/lib/libSystem.B.dylib
```

Building against the `.dylib` instead adds a line for `libffi_lib.dylib`, recorded as an absolute path into the Cargo build directory, so shipping it means fixing that. Cross-compiling needs a C cross toolchain; I only mention it.

## Cost of the boundary

The machine load was above 3, so I ran no benchmark and give no numbers. Qualitatively, a cgo call costs more than a Go call (the Go docs say so too), and the compiler cannot inline it. Prefer coarse calls: one call with a big buffer, not a million tiny ones.

## FFI, gRPC or wasm?

- **{{< term "ffi" "FFI" >}}**: one process and no serialization, but `unsafe`, manual ownership, a C toolchain, and a Rust abort kills your Go service.
- **gRPC**: separate processes, a typed contract, independent deploys. You pay for a network hop and encoding.
- **wasm**: the guest is sandboxed and has its own linear memory, so data is copied in and out, and you need a runtime.

## A few things to watch

- Build Rust before Go.
- Free memory with the allocator that made it: `C.free` for `CString`, `free_string` for `greet`.
- Never keep a Go pointer in C after the call, and never pass Go memory that contains Go pointers.
- Guard empty slices before `&data[0]`.
- A Rust panic in a called function aborts the whole process.

## Exercise

1. C reads a `CString` only up to the first NUL byte. Make `Greet` return an error for names containing `\x00` (use `strings.IndexByte`) and test it.
2. Add `reverse_in_place` to the Rust crate (the exercise from the previous Rust post) and wrap it in Go.

## What's next

Next: Futures, Pin and async internals in Rust.
