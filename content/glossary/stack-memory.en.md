+++
title = "Stack (memory)"
summary = "The fast, tidy region of memory where each function call keeps its fixed-size local values."
category = "Rust"
related = ["heap-memory", "ownership"]
posts = ["rust-ownership"]
+++

Each function call takes a frame on the stack and gives it back when it returns. Only values whose size is known at compile time (integers, `bool`, fixed-size arrays, the small header of a `String`) live there. Not to be confused with the stack data structure.
