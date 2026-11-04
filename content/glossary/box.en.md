+++
title = "Box"
summary = "A smart pointer with one owner that stores its value on the heap and keeps only a pointer on the stack."
category = "Rust"
related = ["smart-pointer", "heap-memory", "stack-memory"]
posts = ["rust-smart-pointers"]
+++

`Box<T>` moves a value to the heap and gives you a pointer of fixed size. You need it for recursive types (a type that contains itself) and for `Box<dyn Trait>`, where values of different types sit behind one trait. When the box goes out of scope, the value on the heap is freed.
