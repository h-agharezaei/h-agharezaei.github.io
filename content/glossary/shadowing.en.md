+++
title = "Shadowing"
summary = "Declaring a new variable with the same name as an earlier one, which hides the old one."
category = "Rust"
related = ["ownership"]
posts = ["rust-types-control-flow"]
+++

In Rust, `let x = ...` again creates a brand-new variable that hides the old `x` from then on. Unlike mutation (`let mut` and assignment) it may change the type: `let spaces = spaces.len();` turns a string into a number.
