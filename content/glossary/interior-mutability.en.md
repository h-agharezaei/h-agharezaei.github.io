+++
title = "Interior mutability"
summary = "Changing a value through a shared reference, with the borrowing check moved from compile time to run time."
category = "Rust"
related = ["refcell", "borrowing"]
posts = ["rust-smart-pointers"]
+++

Normally a shared reference (`&T`) means read-only. Types such as `RefCell` and `Mutex` allow changes through `&T` by checking the rules themselves while the program runs. The compiler cannot prove this safe, so the check becomes the type's job.
