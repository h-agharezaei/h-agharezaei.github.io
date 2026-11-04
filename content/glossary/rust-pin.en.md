+++
title = "Pin (Rust)"
summary = "A wrapper such as `Pin<&mut T>` that promises the value will not be moved in memory until it is dropped, which self-referential futures need."
category = "Rust"
related = ["rust-future", "rust-waker"]
posts = ["rust-pin-future-internals"]
+++

An `async` block can hold a reference to one of its own locals, so moving it would leave a dangling pointer. `poll` therefore takes `Pin<&mut Self>`. Most types are `Unpin` (pinning changes nothing for them); async blocks are not, and you pin them with `Box::pin` or `std::pin::pin!`.
