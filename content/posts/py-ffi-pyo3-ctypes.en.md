+++
date = '2027-05-24T10:00:00+03:30'
draft = false
title = 'Calling Rust from Python with ctypes and PyO3'
description = 'Calling Rust from Python with ctypes and PyO3: C ABI, freeing memory, panics, maturin, exceptions, releasing the GIL, abi3 wheels and when not to.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "rust", "ffi", "ctypes", "pyo3", "maturin"]
cover = { image = "/images/covers/py-ffi-pyo3-ctypes.png", alt = "Calling Rust from Python with ctypes and PyO3", hiddenInSingle = true }
+++

In the [previous post](/posts/py-data-csv-sqlite/) we stayed inside the standard library. Sometimes a hot loop is too slow in Python, and you already have Rust. This last post of the Python series shows two {{< term "ffi" "FFI" >}} ways to call Rust: `ctypes` (no build step on the Python side) and {{< term "pyo3" "PyO3" >}} with maturin (a real module). The boundary rules are the same as in [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/) and [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/). Python threads and the lock are in [The GIL and threading](/posts/py-gil-threading/).

> Python 3.14.0, Rust 1.90, macOS arm64, {{< term "uv" "uv" >}} 0.10.9, maturin 1.15.0, PyO3 pinned to `=0.30.1`. Everything below was run, in throwaway directories I deleted afterwards. The machine load was 6, so I publish **no timings**.

## Part 1: ctypes and the C {{< term "abi" "ABI" >}}

A `cdylib` crate exports `extern "C"` functions with `#[no_mangle]`: `add(i32, i32)`, `big() -> i64` (returns 5,000,000,000), `checksum(*const u8, usize)` (FNV-1a), `greet` (returns a heap string) and `free_string`. On macOS the library is `libdemo.dylib` (`.so` on Linux). Load it and declare types:

```python
lib = ctypes.CDLL("<tmp>/libdemo.dylib")
lib.add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.add.restype = ctypes.c_int32
lib.checksum.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
lib.checksum.restype = ctypes.c_uint64
```

```text
add(2, 40) = 42
checksum(b'hello') = 11831194018420276491
python fnv-1a      = 11831194018420276491
```

Without declarations ctypes guesses, and it guesses `int`. `big()` returns an `int64`:

```text
big() with default restype: 705032704
big() with c_int64:         5000000000
```

5,000,000,000 minus 2^32 is 705,032,704: silent truncation. The same default accepted `add(1, 2, 3, 4)` silently. So always set `argtypes` and `restype`.

## Strings and ownership

`greet` returns memory allocated by Rust, so Python must hand it back to `free_string`, never to C's `free`. This is the allocator rule from the Go post. One trap: if `restype` is `c_char_p`, ctypes copies into a `bytes` and you lose the pointer you must free. Use `c_void_p`:

```python
lib.greet.restype = ctypes.c_void_p
p = lib.greet(b"Roham")
print(ctypes.string_at(p).decode())  # Hello, Roham!
lib.free_string(p)
```

A callback works through `CFUNCTYPE`; keep a reference to the callback object alive for the whole call. `each_square(4, cb)` made Python record `[(0, 0), (1, 1), (2, 4), (3, 9)]`.

## A panic crosses the boundary

I added `boom()` that panics and ran it in a subprocess. Modern Rust refuses to unwind out of `extern "C"`:

```text
exit code -6
calling boom()
thread '<unnamed>' panicked at src/lib.rs:49:5:
boom from Rust
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

`-6` is SIGABRT: the whole Python process died, with no `except` to catch it. The fix is `catch_unwind` inside the Rust function and an error value (`-1`, or a null pointer) the caller checks; `boom_safe()` returned `-1`.

## Part 2: PyO3 and maturin

```text
$ uv venv && uv pip install maturin
$ maturin develop --release
```

The crate declares `pyo3 = "=0.30.1"`, `crate-type = ["cdylib"]` and a `#[pymodule]`. Types and errors are handled for you:

```rust
#[pyfunction]
fn count_multiples(n: i64) -> PyResult<u64> {
    if n < 0 { return Err(PyValueError::new_err("n must be >= 0")); }
    Ok((0..n).filter(|i| i % 3 == 0 || i % 5 == 0).count() as u64)
}
```

A `#[pyclass] Counter` with `#[new]`, `incr` and a read-only `value` field completes the demo. The build took 8 seconds here. From Python:

```text
correct on 5 sizes; count_multiples(10) = 5
ValueError: n must be >= 0
TypeError: 'str' object cannot be interpreted as an integer
15 15
ValueError: overflow
AttributeError: attribute 'value' of 'builtins.Counter' objects is not writable
```

The first line compares against a pure-Python version for five values of `n`. Wrong argument types become `TypeError` before your code runs, and `Err(PyValueError)` becomes a normal exception. According to the PyO3 docs, a Rust panic becomes a Python exception too (I did not trigger one here).

## Releasing the GIL

A Rust function that holds the {{< term "gil" "GIL" >}} blocks other Python threads. In PyO3 0.30.1 the method is `py.detach(|| ...)`; I verified that it compiles and that the old name `allow_threads` is not in this version's `marker.rs`. I wrote `count_multiples_nogil` with it. My ticker-thread test of its effect was flawed (the compiler can fold that loop), so I claim no speedup. Python-versus-Rust speed: not measured.

## Types, wheels and abi3

Ship a `_core.pyi` stub and an empty `py.typed` file so mypy sees the {{< term "type-hint" "type hints" >}} ([Type hints and mypy](/posts/py-type-hints-mypy/)). `maturin build --release` made a {{< term "wheel" "wheel" >}}, `fastcount-0.1.0-cp314-cp314-macosx_11_0_arm64.whl`, usable only on that Python. With the feature `abi3-py310` it made `fastcount-0.1.0-cp310-abi3-macosx_11_0_arm64.whl`, which according to the PyO3 docs targets the stable ABI for Python 3.10 and later. I installed it only into Python 3.14 and checked that import works; other versions I did not run. The wheel contained `_core.abi3.so`, even on macOS. For publishing see [Packaging and publishing](/posts/py-packaging-publishing/); for environments see [venv and uv](/posts/py-environment-uv-venv/).

## When not to use FFI (my opinion)

- Each call has overhead and converts arguments; many tiny calls can lose to plain Python. Pass whole buffers.
- Crashes in native code have no Python traceback, and debugging is harder.
- Alternatives: `cffi`, Cython, pybind11 (for C++). For Rust, I would reach for PyO3.

## A few things to watch

- Set `argtypes` and `restype` for every ctypes function.
- Free memory with the allocator that made it.
- Never let a panic cross `extern "C"`.
- Pin PyO3 and read its changelog; names like `detach` changed between versions.

## Exercise

Add `reverse(data: bytes) -> bytes` to the PyO3 crate and a test that compares it with `data[::-1]`.

## What's next

The Python series ends here. Next, continue with the Distributed Systems or Software Engineering series.
