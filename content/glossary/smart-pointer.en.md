+++
title = "Smart pointer"
summary = "A type that acts like a pointer but also owns the data it points to and runs code when it goes away, such as Box, Rc and String."
category = "Rust"
related = ["box", "rc", "refcell", "ownership"]
posts = ["rust-smart-pointers"]
+++

A smart pointer is a struct that behaves like a reference (you can use `*` on it) but also owns what it points to and cleans it up through the `Drop` trait. `Box`, `Rc` and `RefCell` are the ones this blog covers; `String` and `Vec` are smart pointers too.
