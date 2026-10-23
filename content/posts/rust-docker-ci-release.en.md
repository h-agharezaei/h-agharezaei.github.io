+++
date = '2027-03-12T10:00:00+03:30'
draft = false
title = 'Docker, CI and releasing a Rust service'
description = 'Ship a Rust axum service: release profile size tuning with real byte counts, a static musl binary, a multi-stage Dockerfile and GitHub Actions.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "docker", "ci", "github-actions", "release", "backend"]
cover = { image = "/images/covers/rust-docker-ci-release.png", alt = "Docker, CI and releasing a Rust service", hiddenInSingle = true, hiddenInList = true }
+++

API design was the previous topic, in [typestate patterns](/posts/rust-typestate-patterns/). Now the service has to leave my laptop. This is the Rust twin of [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/), and I use a small `orders` service in the style of [the Axum post](/posts/rust-http-axum-api/): `/orders`, `/healthz`, `/readyz`.

> **Honest disclaimer.** The Docker daemon is off on this machine and I left it off, so I never ran `docker build`. The Dockerfile below is written to be correct but the image was not built, and there are no image sizes or layer outputs here. What I did run, on Rust 1.90.0 (macOS arm64): the release builds and their sizes, a linux/arm64 musl cross build, the endpoints, SIGTERM, clippy, rustfmt and `actionlint`.

## Shrinking the release binary

I built the service for `aarch64-unknown-linux-musl` with one profile setting changed at a time (via `CARGO_PROFILE_RELEASE_*`, a clean target dir each time, `--locked`). Sizes are in bytes, one build each. The machine was under load, so I quote no build times.

| profile | bytes |
|---|---|
| default release | 2091720 |
| `lto = "thin"` | 2012584 |
| `lto = "fat"` | 1504536 |
| `codegen-units = 1` | 1647288 |
| `strip = true` | 1331864 |
| `opt-level = "z"` | 2431520 |
| `panic = "abort"` | 1522992 |
| fat + cgu 1 + strip + abort | 895872 |
| the same + `opt-level = "z"` | 787192 |

Each setting alone helps modestly (`strip` and `lto = "fat"` the most), but together they cut 2.09 MB to 0.90 MB. `opt-level = "z"` alone made the binary bigger; I did not investigate why. `panic = "abort"` removes unwinding, so a panic kills the process; under an orchestrator that restarts it that is acceptable to me, but it is a behavior change. I chose fat + cgu 1 + strip + abort and kept the default `opt-level`, since speed matters more to me than the last 100 KB:

```toml
[profile.release]
lto = "fat"
codegen-units = 1
strip = true
panic = "abort"
```

## A static binary from macOS

`cargo build --target aarch64-unknown-linux-musl` after `rustup target add` failed at the link step:

```
WARN rustc_codegen_ssa::back::link Linker does not support -no-pie command line option. Retrying without.
error: linking with `cc` failed: exit status: 1
  = note: ld: unknown options: --as-needed -Bstatic -Bdynamic --eh-frame-hdr -z --gc-sections ...
          clang: error: linker command failed with exit code 1
```

The reason: `cc` on macOS is Apple's linker, which does not understand ELF flags. You normally need a cross linker such as `zig` (via `cargo-zigbuild`) or a musl gcc; neither is installed here. But rustup ships `rust-lld` inside the toolchain, and that was enough:

```
$ CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=<sysroot>/lib/rustlib/aarch64-apple-darwin/bin/rust-lld \
    cargo build --release --locked --target aarch64-unknown-linux-musl
$ file .../release/orders-svc
ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, not stripped
```

I cannot run a Linux ELF here, so this proves the build and link, not the run; the runs below use the host build.

## Health, readiness and SIGTERM

Readiness is an `AtomicBool` set after `bind` and cleared when the signal arrives, then `with_graceful_shutdown` lets in-flight requests finish. A distroless image has no `curl`, so the binary also has a `--healthcheck` flag that calls its own `/healthz` over a plain `TcpStream`:

```rust
axum::serve(listener, app)
    .with_graceful_shutdown(async move {
        let mut term = signal(SignalKind::terminate()).unwrap();
        tokio::select! { _ = term.recv() => {} _ = tokio::signal::ctrl_c() => {} }
        ready.store(false, Ordering::SeqCst); // fail readiness first
        println!("shutting down");
    })
    .await
    .unwrap();
```

A real run of the release build with the final profile:

```
$ curl -si localhost:18432/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:18432/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ curl -s localhost:18432/orders
[{"id":1,"item":"book"},{"id":2,"item":"pen"}]
$ orders-svc --healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo exit=$?
exit=0
```

The log shows `shutting down` then `stopped`. With no server running, `--healthcheck` prints `Connection refused (os error 61)` and exits 1.

## The Dockerfile

Cargo has no built-in "download dependencies only" step, so I use the dummy `main.rs` trick (the `cargo-chef` tool automates the same idea): build once with only the manifests, then copy the real source.

```dockerfile
FROM rust:1.90 AS build
ARG RUST_TARGET=aarch64-unknown-linux-musl
RUN rustup target add ${RUST_TARGET}
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs \
 && cargo build --release --locked --target ${RUST_TARGET} && rm -rf src
COPY src ./src
RUN touch src/main.rs \
 && cargo build --release --locked --target ${RUST_TARGET} \
 && cp target/${RUST_TARGET}/release/orders-svc /orders-svc

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /orders-svc /orders-svc
USER nonroot:nonroot
ENV ADDR=0.0.0.0:8080
ENTRYPOINT ["/orders-svc"]
```

The `touch` makes sure Cargo sees the real source as newer. A static musl binary fits `distroless/static`; a glibc build would need `distroless/cc`. `.dockerignore` excludes `target`, `.git` and logs. I did not build this file, and the musl link inside the `rust` image is untested.

## CI and release workflows

`ci.yml` runs `cargo fmt --check`, `cargo clippy --locked --all-targets -- -D warnings` and `cargo test --locked`. I ran all three locally: they pass. `release.yml` triggers on `v*` tags, builds a matrix of three targets with `upload-artifact`, and a separate `image` job pushes to GHCR; only that job gets `packages: write`. Actions are pinned to the latest release tags I queried from the GitHub API: `actions/checkout@v7.0.1`, `Swatinem/rust-cache@v2.9.3`, `docker/build-push-action@v7.4.0`, and so on. Both pass:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ go run ... .github/workflows/release.yml
exit=0 (both)
```

I also broke the matrix on purpose (`matrix.targt`): actionlint reported `property "targt" is not defined in object type {os: string; target: string}`. It checks syntax, not whether the push works.

## Supply-chain hygiene

- Commit `Cargo.lock` for binaries and use `--locked` everywhere, so CI builds what you reviewed.
- Run `cargo audit` or `cargo deny` in CI (I did not run them here; I only mention them).
- Pin the toolchain (`1.90.0`).

## A few things to watch

- Run `docker build` yourself before trusting the Dockerfile.
- `panic = "abort"` changes panic behavior; check that nothing relies on `catch_unwind`.

## What's next

Next: Rust and WebAssembly, the same language compiled for a very different target.
