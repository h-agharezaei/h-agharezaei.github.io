+++
title = "Rc"
summary = "A reference-counted smart pointer that lets several owners share one value; the value is freed when the last owner is gone."
category = "Rust"
related = ["smart-pointer", "refcell", "ownership"]
posts = ["rust-smart-pointers"]
+++

`Rc<T>` keeps a counter of how many owners a value has. `Rc::clone` only adds one to the counter; it does not copy the data. It gives read-only access and is not safe to send to another thread (use `Arc` there).
