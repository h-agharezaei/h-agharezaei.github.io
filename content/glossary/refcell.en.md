+++
title = "RefCell"
summary = "A type that checks the borrowing rules at run time instead of compile time, so you can change a value through a shared reference."
category = "Rust"
related = ["interior-mutability", "rc", "borrowing"]
posts = ["rust-smart-pointers"]
+++

`RefCell<T>` hands out `borrow()` and `borrow_mut()`, which follow the usual rule (many readers or one writer). If you break the rule it panics at run time, or `try_borrow_mut` returns an `Err`. It is for single-threaded code.
