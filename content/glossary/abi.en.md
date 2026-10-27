+++
title = "ABI"
summary = "Application Binary Interface: the binary-level contract (calling convention, type layout, symbol names) between compiled code."
category = "Python"
related = ["ffi", "pyo3", "wheel"]
posts = ["py-ffi-pyo3-ctypes"]
+++

Two compiled pieces can call each other only if they agree on the ABI. Rust has no stable ABI of its own, so FFI goes through the C ABI (`extern "C"`). CPython also defines a limited, stable ABI (`abi3`) that lets one compiled extension work across several Python versions.
