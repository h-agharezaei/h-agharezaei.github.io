+++
title = "PyO3"
summary = "A Rust library for writing Python extension modules (and calling Python from Rust)."
category = "Python"
related = ["ffi", "gil", "wheel"]
posts = ["py-ffi-pyo3-ctypes"]
+++

With PyO3 you mark Rust functions and structs with `#[pyfunction]`, `#[pyclass]` and `#[pymodule]`, and a build tool such as maturin turns the crate into an importable Python module. Argument conversion and error-to-exception mapping are generated for you.
