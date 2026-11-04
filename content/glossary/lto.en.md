+++
title = "LTO"
summary = "Link-time optimization: the compiler optimizes across all crates together at the end of the build, giving smaller and often faster binaries at the cost of build time."
category = "Rust"
related = ["crate"]
posts = ["rust-docker-ci-release"]
+++

Normally each crate is optimized on its own and then linked. With LTO the compiler looks at the whole program, so it can remove unused code and inline functions across crate boundaries. In Cargo you turn it on with `lto = "thin"` or `lto = "fat"` in `[profile.release]`; fat is the most thorough and the slowest to build.
