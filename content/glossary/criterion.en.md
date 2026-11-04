+++
title = "Criterion"
summary = "A statistics-driven benchmark crate for Rust: it warms up, collects many samples, reports a confidence interval and compares against earlier runs."
category = "Rust"
related = ["black-box"]
posts = ["rust-performance-criterion"]
+++

You add it as a dev-dependency, write a `benches/*.rs` file with `harness = false`, and run `cargo bench`. The output `time: [low estimate high]` is a confidence interval, and a second run prints whether the change from the previous run is statistically significant.
