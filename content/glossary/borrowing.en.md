+++
title = "Borrowing"
summary = "Using a value through a reference without taking ownership of it."
category = "Rust"
related = ["ownership", "lifetime"]
posts = ["rust-borrowing-references"]
+++

`&T` is a shared reference and `&mut T` an exclusive one. At any time you may have many `&T` or exactly one `&mut T`, never both. The borrow checker enforces this at compile time, which prevents data races and iterator invalidation.
