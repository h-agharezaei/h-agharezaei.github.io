+++
title = "Newtype"
summary = "A struct with a single field that wraps another type to give it a distinct identity, such as UserId(u64) versus OrderId(u64)."
category = "Rust"
related = ["type-state"]
posts = ["rust-typestate-patterns"]
+++

`struct UserId(u64);` and `struct OrderId(u64);` hold the same data as a plain `u64`, but the compiler treats them as different types, so passing one where the other is expected is an error. If the field is private and the only constructor validates its input, every value of the type is known to be valid. A newtype costs nothing at runtime: `UserId` has the same size as `u64`.
