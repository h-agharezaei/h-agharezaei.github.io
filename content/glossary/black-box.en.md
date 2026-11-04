+++
title = "black_box"
summary = "`std::hint::black_box`: a function that hides a value from the optimizer so a benchmark's work is not deleted or folded at compile time."
category = "Rust"
related = ["criterion"]
posts = ["rust-performance-criterion"]
+++

Wrap the input (`black_box(n)`) so the compiler cannot treat it as a constant, and use the result so it is not discarded. Without it, a benchmark of a pure function can report a fraction of a nanosecond because nothing ran.
