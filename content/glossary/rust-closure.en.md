+++
title = "Closure (Rust)"
summary = "An anonymous function written |args| body that can use variables from the place where it was created."
category = "Rust"
related = ["trait", "borrowing", "ownership"]
posts = ["rust-closures-iterators"]
+++

A closure is a small function without a name that can read, change or take over variables from the scope around it. Rust chooses how each variable is captured (by reference, by mutable reference or by move) and gives the closure one or more of the `Fn`, `FnMut` and `FnOnce` traits accordingly. Example: `let add = |x| x + n;`.
