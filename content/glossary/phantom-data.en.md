+++
title = "PhantomData"
summary = "A zero-sized marker that lets a struct have a type parameter it does not actually store; the basis of type-state markers."
category = "Rust"
related = ["type-state"]
posts = ["rust-typestate-patterns"]
+++

Rust does not allow a struct to declare a type parameter `S` and never use it. `PhantomData<S>` is a field that "uses" `S` for the compiler but takes no space: `size_of::<PhantomData<T>>()` is 0. It is how a type like `Order<S>` can carry its state `S` in the type only, with nothing stored in memory.
