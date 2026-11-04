+++
title = "Iterator (Rust)"
summary = "A value with a next method that hands out items one at a time until it returns None."
category = "Rust"
related = ["rust-closure", "trait"]
posts = ["rust-closures-iterators"]
+++

Anything that implements the `Iterator` trait: it has one required method, `next`, which returns `Some(item)` until the items run out and then `None`. Adapters such as `map` and `filter` wrap one iterator in another and do no work until a consumer such as `collect` or `sum` pulls items through.
