+++
date = '2027-05-24T10:00:00+03:30'
draft = false
title = 'Calling Rust from Python with ctypes and PyO3'
description = 'Calling Rust from Python with ctypes and PyO3: C ABI, freeing memory, panics, maturin, exceptions, releasing the GIL, abi3 wheels and when not to.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "rust", "ffi", "ctypes", "pyo3", "maturin"]
cover = { image = "/images/covers/py-ffi-pyo3-ctypes.png", alt = "Calling Rust from Python with ctypes and PyO3", hiddenInSingle = true }
+++

Imagine a loop in your Python program that is simply too slow: millions of iterations of plain arithmetic, and Python spends most of its time running the interpreter rather than your math. You already have the same logic in Rust, fast and tested. Can Python just call it?

It can, through an {{< term "ffi" "FFI" >}} (foreign function interface): a way for one language to call functions written in another. After [Small data processing with csv and sqlite3](/posts/py-data-csv-sqlite/), this last post of the Python series shows two ways to call Rust. `ctypes` ships with Python and needs no build step on the Python side: you load a compiled library and call its functions. {{< term "pyo3" "PyO3" >}} with maturin is the other way: it builds a real Python module, with Python types and exceptions, from Rust code.

The first thing you will see is a warning. Without type declarations, ctypes silently turns a Rust function's 5,000,000,000 into 705,032,704. Crossing the language boundary is where the compiler stops helping you, so this post is mostly about what crosses, who owns it, and what can go wrong. The boundary rules are the same as in [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/) and [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/). Python threads and the lock are in [The GIL and threading](/posts/py-gil-threading/).

> I re-ran everything with Python 3.14.0, Rust 1.90, macOS arm64, {{< term "uv" "uv" >}} 0.10.9, maturin 1.15.0 and PyO3 pinned to `=0.30.1`, in scratch copies of the demos that I deleted afterwards. The installs came from offline caches. The machine was busy, so I publish **no timings**. Paths are shown as `<tmp>`; Rust prints a stack backtrace on the abort in Part 1, which I cut out (it is 28 frames of addresses that change on every run).

## Part 1: ctypes and the C {{< term "abi" "ABI" >}}

How can Python call into a Rust library at all? Through the C ABI, the shared binary convention for how functions receive their arguments and return values. Almost every language can speak it, so it works as a common ground. On the Rust side you build a `cdylib` crate (a dynamic library with a C interface) and mark each exported function `extern "C"` with `#[no_mangle]`, which keeps its name readable by others. My demo exports five functions that show the typical cases:

- `add(i32, i32)`, plain numbers.
- `big() -> i64`, which returns 5,000,000,000, a number that does not fit in 32 bits.
- `checksum(*const u8, usize)`, a hash (FNV-1a) of a buffer of bytes.
- `greet`, which returns a string allocated by Rust on the heap, and `free_string`, which frees it.
- `each_square`, which calls back into Python.

On macOS the library is `libdemo.dylib` (`.so` on Linux). In Python you load it and **declare the types** of each function: what it takes (`argtypes`) and what it returns (`restype`):

```python
lib = ctypes.CDLL("<tmp>/libdemo.dylib")
lib.add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.add.restype = ctypes.c_int32
lib.checksum.argtypes = [ctypes.c_char_p, ctypes.c_size_t]
lib.checksum.restype = ctypes.c_uint64
```

With the declarations in place, calling `add` and `checksum` and comparing the checksum with the same algorithm written in Python gives:

```text
add(2, 40) = 42
checksum(b'hello') = 11831194018420276491
python fnv-1a      = 11831194018420276491
```

The Rust and Python checksums agree, so the bytes crossed the boundary intact. Now the trap. A library is just machine code, and it carries no type information that Python can read. So when you do not declare types, ctypes guesses, and it guesses `int` (32 bits). `big()` actually returns a 64-bit integer:

```text
big() with default restype: 705032704
big() with c_int64:         5000000000
```

5,000,000,000 minus 2^32 is 705,032,704: the upper bits were silently cut off. The same lack of declaration let `add(1, 2, 3, 4)` run with two extra arguments and no error. Nothing warns you. So always set `argtypes` and `restype`, for every function.

## Strings and ownership

Numbers are the easy case. Strings are harder, because a string is memory, and someone must free it. `greet` creates its result inside Rust, with Rust's allocator. That means Python must hand the pointer back to Rust's `free_string`, never to C's `free`: memory has to be released by the allocator that made it. This is the same rule as in the Go post.

There is a trap on the Python side. If you declare `restype = ctypes.c_char_p`, then, according to the ctypes docs, ctypes converts the result into a Python `bytes` and the original pointer is lost, so you can never free it. Use `c_void_p` to keep the raw pointer, read the text with `string_at`, then free:

```python
lib.greet.restype = ctypes.c_void_p
p = lib.greet(b"Roham")
print(ctypes.string_at(p).decode())  # Hello, Roham!
lib.free_string(p)
```

The demo printed `greet: Hello, Roham!`. A callback goes the other direction: Rust calls a Python function. In ctypes you wrap it with `CFUNCTYPE`, and you must keep the callback object alive for the whole call, because if Python garbage-collects it, Rust would be calling freed memory. `each_square(4, cb)` made Python record `[(0, 0), (1, 1), (2, 4), (3, 9)]`: the index and its square, for each of 4 steps.

## A panic crosses the boundary

What if the Rust code panics? A panic normally unwinds the stack, but there is nothing on the other side of a C boundary that understands Rust unwinding. Modern Rust therefore refuses to unwind out of an `extern "C"` function and aborts. I called a function `boom()` that just panics, in a subprocess, and checked the exit code:

```text
exit code -6
calling boom()

thread '<unnamed>' panicked at src/lib.rs:49:5:
boom from Rust
note: run with `RUST_BACKTRACE=1` environment variable to display a backtrace

thread '<unnamed>' panicked at library/core/src/panicking.rs:225:5:
panic in a function that cannot unwind
thread caused non-unwinding panic. aborting.
```

`-6` is Python's way to say "killed by signal 6", SIGABRT. The whole Python process died on the spot, with no exception and nothing to catch with `except`. So the rule is that a panic must never leave an `extern "C"` function. The fix is `catch_unwind` inside the Rust function, turning a panic into an error value the caller checks, such as `-1` or a null pointer. My `boom_safe()` does that and returned `-1`. (Rust still prints the panic message to stderr, but the process lives on.)

## Part 2: PyO3 and maturin

ctypes works with any library but makes you handle every detail yourself. PyO3 goes the other way: you write Rust functions that look like Rust, and PyO3 generates a real Python extension module, with argument conversion and exceptions handled for you. **maturin** is the build tool that compiles the crate and installs it into your environment:

```text
$ uv venv && uv pip install maturin
$ maturin develop --release
```

The crate declares `pyo3 = "=0.30.1"` (pinned, because the API changes between versions), `crate-type = ["cdylib"]` and a `#[pymodule]`. A function becomes callable from Python with `#[pyfunction]`. Types and errors are handled for you:

```rust
#[pyfunction]
fn count_multiples(n: i64) -> PyResult<u64> {
    if n < 0 { return Err(PyValueError::new_err("n must be >= 0")); }
    Ok((0..n).filter(|i| i % 3 == 0 || i % 5 == 0).count() as u64)
}
```

It counts the integers below `n` that are divisible by 3 or 5. A `#[pyclass] Counter` with `#[new]`, an `incr` method and a read-only `value` field completes the demo. Here is the output of `check.py`, which uses the module from Python (the first build compiles PyO3 itself, so it takes a while):

```text
correct on 5 sizes; count_multiples(10) = 5
ValueError: n must be >= 0
TypeError: 'str' object cannot be interpreted as an integer
15 15
ValueError: overflow
AttributeError: attribute 'value' of 'builtins.Counter' objects is not writable
```

Line by line:

- The first line checks the Rust function against a pure-Python version for five values of `n`, then shows `count_multiples(10) = 5` (the numbers 0, 3, 5, 6 and 9).
- `Err(PyValueError)` in Rust became a normal Python `ValueError` for `-1`.
- Passing the string `"x"` became a `TypeError` before the Rust code even ran: PyO3 converts arguments and rejects the wrong type.
- `Counter(10).incr(5)` returned 15 and `value` read 15.
- `Counter(2**64 - 1).incr(1)` overflowed the `u64`, and the `checked_add` turned that into `ValueError: overflow` instead of wrapping around.
- Assigning to `value` failed with `AttributeError`, because the field was declared read-only (`get` but not `set`).

According to the PyO3 docs, a Rust panic becomes a Python exception too; I did not trigger one here.

## Releasing the GIL

Python has a global lock, the {{< term "gil" "GIL" >}}, and while a thread runs Python code it holds it, so other Python threads wait. A Rust function called from Python keeps the lock unless it gives it up, so it blocks other Python threads even though it does not need them. PyO3 lets Rust code release it while it works. In PyO3 0.30.1 the method is `py.detach(|| ...)`. I wrote `count_multiples_nogil` with it, verified that it compiles and that the old name `allow_threads` does not appear in this version's `marker.rs` (the name changed between versions, which is why pinning matters). My attempt to test the effect with a ticker thread was flawed, because the compiler can fold that loop away, so I claim no speedup.

## Types, wheels and abi3

For the Python side to know the types, ship a stub file `_core.pyi` and an empty `py.typed` so mypy sees the {{< term "type-hint" "type hints" >}} ([Type hints and mypy](/posts/py-type-hints-mypy/)). Then you build a {{< term "wheel" "wheel" >}}. A wheel with compiled code is tied to a platform, and by default to one Python version. Building with `maturin build --release` without any special feature gave:

```text
fastcount-0.1.0-cp314-cp314-macosx_11_0_arm64.whl
```

Read the name: `cp314` is CPython 3.14, so this wheel works only on that Python, on macOS arm64. Turning on the feature `abi3-py310` in `Cargo.toml` (as in the demo) gave a different name:

```text
fastcount-0.1.0-cp310-abi3-macosx_11_0_arm64.whl
```

According to the PyO3 docs, `abi3` targets Python's stable ABI, so one wheel works for Python 3.10 and later. I installed it into a fresh Python 3.14 environment and checked that `import fastcount` works and `count_multiples(10)` returns 5; I did not run other Python versions. The wheel contains `_core.abi3.so` (even on macOS), against `_core.cpython-314-darwin.so` in the version-specific one. The package files in both are `fastcount/__init__.py`, `_core.pyi` and `py.typed`. (My first listing also had a stray `__pycache__` file left over from earlier runs, which I leave out.) For publishing see [Packaging and publishing a Python project](/posts/py-packaging-publishing/); for environments see [The Python environment: venv and uv](/posts/py-environment-uv-venv/).

## When not to use FFI (my opinion)

- Each call has overhead and converts its arguments, so many tiny calls can lose to plain Python. Pass whole buffers, and let Rust do a lot of work per call.
- A crash in native code has no Python traceback, and debugging is harder. Remember the SIGABRT above.
- There are alternatives: `cffi`, Cython and pybind11 (for C++). For Rust, I would reach for PyO3.

## Rules at the FFI boundary

- Set `argtypes` and `restype` for every ctypes function, or accept silent truncation.
- Free memory with the allocator that made it, and never convert the pointer you must free into a copy.
- Never let a panic cross `extern "C"`; catch it and return an error value.
- Pin PyO3 and read its changelog; names like `detach` changed between versions.

## Exercise

Add `reverse(data: bytes) -> bytes` to the PyO3 crate and a test that compares it with `data[::-1]`.

## What's next

The Python series ends here. Next, continue with the Distributed Systems or Software Engineering series.
