+++
title = "UTF-8"
summary = "The standard way to store Unicode text as bytes, using one to four bytes per character."
category = "Rust"
related = ["borrowing"]
posts = ["rust-collections-strings"]
+++

UTF-8 turns each Unicode character into one to four bytes. English letters take one byte, most Persian letters two, and an emoji four. Rust's `String` and `&str` are always valid UTF-8, so `len()` counts bytes while `chars().count()` counts characters.
