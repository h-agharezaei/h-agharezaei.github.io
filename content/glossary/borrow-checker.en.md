+++
title = "Borrow checker"
summary = "The part of the Rust compiler that checks references against the borrowing rules."
category = "Rust"
related = ["borrowing", "ownership", "lifetime"]
posts = ["rust-borrowing-references"]
+++

It verifies at compile time that you never have a mutable reference together with any other reference to the same value, and that no reference outlives its value. Violations are compile errors such as E0499, E0502 and E0515, so these bugs cannot reach run time.
