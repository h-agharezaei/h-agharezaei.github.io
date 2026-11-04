+++
title = "Undefined behavior"
summary = "What happens when a program breaks the rules of the language in a way the language does not define: anything can happen, including seemingly working."
category = "Rust"
related = ["raw-pointer", "rust-ffi"]
posts = ["rust-unsafe-ffi"]
+++

The compiler is allowed to assume UB never happens, so a program with UB may crash, print wrong results, or work until the compiler or machine changes. Safe Rust cannot cause UB; in `unsafe` code it is your job to avoid it, for example dangling pointers, two live `&mut` to the same data or data races.
