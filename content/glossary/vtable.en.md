+++
title = "vtable"
summary = "A small table of method addresses that a `dyn Trait` pointer uses to find the right function at run time."
category = "Rust"
related = ["trait-object", "trait"]
posts = ["rust-trait-objects-dyn"]
+++

For each concrete type used as `dyn Trait`, the compiler builds a table with the addresses of that type's methods. A `&dyn Trait` is a fat pointer of two words: one points to the data, the other to this table, so calling a method means looking its address up in the table.
