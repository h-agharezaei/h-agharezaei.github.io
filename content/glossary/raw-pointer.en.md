+++
title = "Raw pointer"
summary = "A bare address (`*const T` or `*mut T`) with no lifetime and no borrow rules; creating one is safe, dereferencing it needs `unsafe`."
category = "Rust"
related = ["rust-ffi", "undefined-behavior"]
posts = ["rust-unsafe-ffi"]
+++

`&raw const x` makes a `*const i32` pointing at `x`. The compiler does not check that the address is valid, aligned or not null, so reading through it with `*p` is something you promise is correct. Raw pointers are what you use at the C boundary and inside safe abstractions such as `split_at_mut`.
