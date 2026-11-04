+++
date = '2027-03-12T10:00:00+03:30'
draft = false
title = 'Docker, CI and releasing a Rust service'
description = 'Ship a Rust axum service: release profile size tuning with real byte counts, a static musl binary, a multi-stage Dockerfile and GitHub Actions.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "docker", "ci", "github-actions", "release", "backend"]
cover = { image = "/images/covers/rust-docker-ci-release.png", alt = "Docker, CI and releasing a Rust service", hiddenInSingle = true }
+++

The service works on my laptop. That sentence is where most deployment stories begin. To run it anywhere else, someone has to answer three questions. How do we package it so it runs the same on every machine, and keep the package small? How do we know that every change still builds and passes its checks before it gets there? And what happens at the moment the platform wants to stop the old version and start a new one?

This post answers them for a small `orders` service in the style of [the Axum post](/posts/rust-http-axum-api/), with three routes: `/orders`, `/healthz` and `/readyz`. It is the Rust twin of [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/). We shrink the release binary, build it as a static file, put it into a {{< term "container" "container" >}} image with a {{< term "multi-stage-build" "multi-stage" >}} Dockerfile, and let {{< term "ci" "CI" >}} (continuous integration: a server that runs the checks on every push) check and publish it. It comes after [the type-state post](/posts/rust-typestate-patterns/): the service is well designed, and now it has to leave my laptop.

> **Honest disclaimer.** The Docker daemon is off on this machine and I left it off, so I never ran `docker build`. The Dockerfile below is written to be correct, but the image was not built, and there are no image sizes or layer outputs here. What I did run for this version of the post, with `rustc 1.90.0` on macOS arm64 and the crate versions locked in the demo's `Cargo.lock`: the release builds and their sizes, the linux/arm64 musl cross build, the endpoints, SIGTERM, `rustfmt`, `clippy` and `cargo test`. I did not re-run `actionlint` this time (it needs a Go download that was not possible here), so its results below are from my original run of this post.

## Shrinking the release binary

A release build is already optimized for speed, but it is not small. Size matters because the file is pushed and pulled on every deploy, and a small binary also fits in a tiny image.

I built the service for `aarch64-unknown-linux-musl` (a static Linux target, explained in the next section) with one profile setting changed at a time. The settings go into the `[profile.release]` section of `Cargo.toml`; here I set them through `CARGO_PROFILE_RELEASE_*` environment variables instead, with a clean target directory each time and `--locked`. Each number is one build. I re-ran the whole table for this version of the post and every number came out exactly the same, so these sizes are stable. I quote no build times, because the machine was under load.

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

What the settings mean:

- {{< term "lto" "lto" >}} (link-time optimization) lets the compiler optimize across all crates together at the end of the build. `thin` is the cheaper version and `fat` the thorough one.
- `codegen-units = 1` stops the compiler from splitting the crate into parallel pieces. One piece is slower to build, but it can optimize more.
- `strip = true` removes the symbols and debug information from the file. The cost is that stack traces of a crashed binary have less to show.
- `opt-level = "z"` asks the compiler to optimize for size instead of speed.
- `panic = "abort"` removes the machinery for unwinding the stack on a panic. A panic then kills the process right away.

Each setting alone helps modestly (`strip` and `lto = "fat"` the most), but together they cut 2.09 MB to 0.90 MB. One result surprised me: `opt-level = "z"` alone made the binary bigger, 2431520 bytes against 2091720. On top of the other four it did make it smaller (787192). I did not investigate why. About `panic = "abort"`: it is a behavior change, not just a size change. Under an orchestrator that restarts a crashed process I accept it, but if any code relies on `catch_unwind` you should not use it. I chose fat + cgu 1 + strip + abort and kept the default `opt-level`, because speed matters more to me than the last 100 KB:

```toml
[profile.release]
lto = "fat"
codegen-units = 1
strip = true
panic = "abort"
```

## A static binary from macOS

Why `musl` at all? A normal Linux binary built with Rust uses the system's C library (glibc) when it runs, so it only works where that library exists. If you build for a {{< term "musl" "musl" >}} target, the C library is linked into the binary. The result is one static file that needs nothing from the system, and that is what lets the final image be almost empty.

The catch is that I am on a Mac, and the container will run Linux. So I have to cross-compile. After `rustup target add aarch64-unknown-linux-musl`, a plain `cargo build --release --target aarch64-unknown-linux-musl` failed at the link step (the output is shortened):

```
WARN rustc_codegen_ssa::back::link Linker does not support -no-pie command line option. Retrying without.
error: linking with `cc` failed: exit status: 1
  = note: ld: unknown options: --as-needed -Bstatic -Bdynamic --eh-frame-hdr -z --gc-sections -z -z --strip-all
          clang: error: linker command failed with exit code 1
```

The reason: `cc` on macOS is Apple's linker, which does not understand the flags for Linux (ELF) files. Normally you need a cross linker, such as `zig` (via `cargo-zigbuild`) or a musl gcc; neither is installed here. But rustup ships a linker called `rust-lld` inside the toolchain, and that was enough. I pointed Cargo at it with an environment variable and built again:

```
$ CARGO_TARGET_AARCH64_UNKNOWN_LINUX_MUSL_LINKER=<sysroot>/lib/rustlib/aarch64-apple-darwin/bin/rust-lld \
    cargo build --release --locked --target aarch64-unknown-linux-musl
$ file .../release/orders-svc
ELF 64-bit LSB executable, ARM aarch64, version 1 (SYSV), statically linked, stripped
$ stat -f %z .../release/orders-svc
895872
```

`file` says what we wanted: a Linux ELF executable for ARM64, statically linked, and stripped (the final profile is in `Cargo.toml` now). The size, 895872 bytes, is the same as the row for the final profile in the table. I cannot run a Linux ELF here, so this proves that the build and the link work, not that the program runs. The runs below use a normal build for my own machine.

## Health, readiness and SIGTERM

When a platform runs your service, it needs to ask it two different questions, and mixing them up is a classic mistake:

- **Liveness** (`/healthz`): "is the process alive?" If this fails, the platform restarts the process.
- **Readiness** (`/readyz`): "should I send you traffic right now?" If this fails, the platform keeps the process but stops sending it requests.

The third thing is the stop itself. A platform stops a container by sending the process {{< term "sigterm" "SIGTERM" >}}, and then waits a while before it kills it. We want the service to finish the requests it is handling and exit cleanly: that is {{< term "graceful-shutdown" "graceful shutdown" >}}. Readiness is an `AtomicBool` that is set after `bind` and cleared when the signal arrives; then `with_graceful_shutdown` lets the requests in flight finish. Failing readiness first means the platform stops sending new requests while the old ones complete.

There is one more thing. A distroless image (more about it below) has no shell and no `curl`, so a normal {{< term "health-check" "health check" >}} command has nothing to run. So the binary has its own `--healthcheck` flag, which calls the service's own `/healthz` through a plain `TcpStream` and exits with 0 or 1. The part that handles the shutdown:

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

`select!` waits for either SIGTERM or Ctrl-C. When one arrives, the code clears readiness, prints `shutting down`, and the future completes, which tells `axum::serve` to stop accepting new connections and wait for the current ones.

Here is a real run of the release build with the final profile. I started it on a random free port (the demo reads the address from the `ADDR` variable; the port number `<port>` below varies), called the endpoints, ran the health check and then sent SIGTERM:

```
$ curl -si localhost:<port>/healthz | sed -n '1p;$p'
HTTP/1.1 200 OK
ok
$ curl -si localhost:<port>/readyz | sed -n '1p;$p'
HTTP/1.1 200 OK
ready
$ curl -s localhost:<port>/orders
[{"id":1,"item":"book"},{"id":2,"item":"pen"}]
$ orders-svc --healthcheck; echo $?
0
$ kill -TERM $PID; wait $PID; echo exit=$?
exit=0
```

The `sed` keeps only the first line (the status) and the last line (the body). The checks return `200` with `ok` and `ready`, the orders come back as JSON, `--healthcheck` returns 0, and after `SIGTERM` the process exits with status 0. The service's own log was:

```
listening on 127.0.0.1:<port>
shutting down
stopped
```

`stopped` is printed after the server has finished, so it appears only if the shutdown was graceful. With no server running, `--healthcheck` prints `healthcheck: Connection refused (os error 61)` and exits with 1.

## The Dockerfile

Now the image. Cargo has no built-in "download and build only the dependencies" step. Docker caches each step (layer) and reuses it when its inputs have not changed, so we want the slow dependency build to be a layer of its own. The trick is a dummy `main.rs`: build once with only the manifests and an empty program, then copy the real source. The `cargo-chef` tool automates the same idea.

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

Read it in two halves. The first stage, named `build`, starts from the official `rust:1.90` image, which is large because it has the whole toolchain. It adds the musl target, copies only `Cargo.toml` and `Cargo.lock`, builds a dummy program (this downloads and compiles all dependencies into a cached layer), removes the dummy source, and only then copies the real `src`. The `touch` makes sure Cargo sees the real source as newer than the dummy build. Then it builds again, which now compiles only our own code.

The second stage starts from `distroless/static`, an image that has almost nothing in it: no shell, no package manager. It copies just the finished binary from the first stage, switches to a non-root user and starts the program. The compiler and the sources never reach the final image. A static musl binary fits `distroless/static`; according to the distroless project, a build that uses glibc needs the `cc` variant instead. A `.dockerignore` keeps `target`, `.git` and logs out of the build context. I did not build this file, and the musl link inside the `rust` image is untested.

## CI and release workflows

CI here means two GitHub Actions workflows. `ci.yml` runs on pushes to `main` and on pull requests, and does three checks:

- `cargo fmt --check` fails if the code is not formatted.
- `cargo clippy --locked --all-targets -- -D warnings` runs the linter, and `-D warnings` turns every warning into an error.
- `cargo test --locked` runs the tests.

I ran all three locally with `rustc 1.90.0`: they pass. A note on honesty: this small demo has no tests, so `cargo test` ran 0 tests and "passes" trivially.

`release.yml` runs when you push a tag that starts with `v`. It builds a matrix of three targets (x86-64 and arm64 Linux with musl, and arm64 macOS) and uploads each binary with `upload-artifact`, and a separate `image` job logs in to GHCR (GitHub's container registry) and pushes the image. Only that job gets the `packages: write` permission; everything else has read-only access. The actions are pinned to release tags that I looked up from the GitHub API in my original run: `actions/checkout@v7.0.1`, `Swatinem/rust-cache@v2.9.3`, `docker/build-push-action@v7.4.0`, and so on. I have not re-checked them for this version. I ran `actionlint` (a linter for workflow files) on both files in the original run, and both passed:

```
$ go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.12 .github/workflows/ci.yml
$ go run ... .github/workflows/release.yml
exit=0 (both)
```

I also broke the matrix on purpose (`matrix.targt`), and actionlint reported `property "targt" is not defined in object type {os: string; target: string}`. Keep in mind what it checks: syntax and types in the workflow, not whether the push to the registry works.

## Supply-chain hygiene

Everything your service is built from, its dependencies and its build tools, is part of its {{< term "software-supply-chain" "software supply chain" >}}. Three small habits help:

- Commit `Cargo.lock` for binaries and use `--locked` everywhere, so that CI builds exactly what you reviewed.
- Run `cargo audit` or `cargo deny` in CI. I did not run them here (they are not installed); I only mention them.
- Pin the toolchain (`1.90.0`) so that a new compiler release does not change your build by surprise.

## Before you trust this setup

- **The Dockerfile is untested.** Run `docker build` yourself before relying on it. In particular, the musl link inside the `rust` image was not tried here.
- **`panic = "abort"` changes what a panic does.** Check that nothing in your code relies on `catch_unwind`.
- **The size table is for this service.** Other programs will give different numbers; measure your own before copying the profile.
- **The workflow check is a lint.** It does not prove that the release job succeeds on GitHub.

## What's next

*Rust and WebAssembly*: the same language compiled for a very different target.
