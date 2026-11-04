+++
title = "musl"
summary = "A small C standard library that lets Rust build fully static Linux binaries (target names ending in -musl), with no dependency on the system libc."
category = "Rust"
related = ["multi-stage-build"]
posts = ["rust-docker-ci-release"]
+++

Most Linux programs call into the system's C library (glibc) when they run. A Rust binary built for a `...-linux-musl` target links musl into itself instead, so the result is one static file that runs on any Linux of the same CPU architecture, including a nearly empty container image. You add the target with `rustup target add aarch64-unknown-linux-musl` and pass `--target` to `cargo build`.
