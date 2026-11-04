+++
title = "Subscriber (tracing)"
summary = "The part of the tracing ecosystem that receives events and spans and decides what to do with them: filter, print, format as JSON or export."
category = "Rust"
related = ["tracing-span"]
posts = ["rust-tracing-observability"]
+++

Code instrumented with `tracing` only announces events and spans. Nothing is printed until a program installs a subscriber, usually once at the start of `main`. The `tracing-subscriber` crate provides a ready-made one, `fmt`, which prints lines to the console and can be combined with a filter (`EnvFilter`) and a JSON formatter. Without a subscriber the events are dropped.
