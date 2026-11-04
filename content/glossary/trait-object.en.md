+++
title = "Trait object"
summary = "A value used through `dyn Trait`: its concrete type is forgotten and only the trait's methods are known, found at run time."
category = "Rust"
related = ["trait", "vtable", "box"]
posts = ["rust-trait-objects-dyn"]
+++

`Box<dyn Shape>` is a pointer to some value that implements `Shape`; you can call `Shape`'s methods on it without knowing whether it is a `Square` or a `Circle`. This lets one `Vec` hold different types, at the price of a [vtable](/glossary/vtable/) lookup per call. Not every trait can be used this way (it must be dyn compatible).
