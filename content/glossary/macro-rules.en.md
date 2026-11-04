+++
title = "Declarative macro"
summary = "A macro written with `macro_rules!` as patterns and templates: it matches the tokens of a call and writes new code from a template."
category = "Rust"
related = ["procedural-macro"]
posts = ["rust-macros"]
+++

`macro_rules! add { ($a:expr, $b:expr) => { $a + $b }; }` says: when you see two expressions separated by a comma, write the first plus the second. The compiler replaces each call with the template (this is called expansion) before it type-checks the program.
