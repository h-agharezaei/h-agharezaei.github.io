+++
title = "Trait"
summary = "A set of methods a type can implement, Rust's way of sharing behavior."
category = "Rust"
related = ["ownership"]
posts = ["rust-generics-traits", "rust-trait-objects-dyn"]
+++

Traits play the role of interfaces, and are used both as generic bounds (`T: Display`, static dispatch) and as trait objects (`dyn Display`, dynamic dispatch). Unlike Go interfaces, a type must explicitly `impl` a trait.
