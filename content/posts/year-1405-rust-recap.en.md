+++
date = '2027-03-20T10:00:00+03:30'
draft = false
title = 'Rust series recap and a look back at 1405'
description = 'Rust series recap for the Persian year 1405: a map of all 30 posts, recurring lessons, an honest Go and Rust comparison, real counts and open gaps.'
categories = ["Meta"]
tags = ["rust", "go", "recap", "1405"]
cover = { image = "/images/covers/year-1405-rust-recap.png", alt = "Rust series recap and a look back at 1405", hiddenInSingle = true, hiddenInList = true }
+++

Today is the last day of the Persian year 1405. After the [Go series recap for 1405](/posts/year-1405-go-recap/), this is the Rust one: a map of all 30 posts, what kept coming back, and what is missing. Each takeaway comes from the post it links to.

## The Rust series, in reading order

**First steps**

- [Getting started with Rust: install, Cargo and a first program](/posts/rust-getting-started/): `cargo check` while editing
- [Types, variables and control flow in Rust](/posts/rust-types-control-flow/): a stray semicolon bites

**Ownership and core types**

- [Ownership in Rust](/posts/rust-ownership/): do not `.clone()` reflexively
- [Borrowing and references in Rust](/posts/rust-borrowing-references/): read the error labels
- [Structs, enums and pattern matching in Rust](/posts/rust-structs-enums-pattern-matching/): `match` covers every case
- [Collections and strings in Rust](/posts/rust-collections-strings/): take `&str`, return `String`
- [Error handling with Result and Option in Rust](/posts/rust-error-handling-result/): errors live in the type

**Abstractions**

- [Modules, crates and Cargo in Rust](/posts/rust-modules-crates-cargo/): no `mod`, file ignored
- [Generics and traits in Rust](/posts/rust-generics-traits/): add bounds as asked
- [Lifetimes in Rust](/posts/rust-lifetimes/): annotations describe, never extend
- [Closures and iterators in Rust](/posts/rust-closures-iterators/): iterators are lazy
- [Smart pointers: Box, Rc and RefCell in Rust](/posts/rust-smart-pointers/): borrow first
- [Testing and documentation in Rust](/posts/rust-testing-docs/): doc examples run as tests
- [Trait objects and dyn in Rust](/posts/rust-trait-objects-dyn/): runtime polymorphism
- [Macros in Rust](/posts/rust-macros/): prefer functions

**Concurrency and async**

- [Concurrency with threads in Rust](/posts/rust-concurrency-threads/): no data races, still deadlocks
- [async/await and Tokio in Rust](/posts/rust-async-tokio/): futures wait for `.await`
- [Futures, Pin and async internals in Rust](/posts/rust-pin-future-internals/): no wake-up, no progress

**Building services**

- [Serde and JSON in Rust](/posts/rust-serde-json/): pick enum representation
- [Building an API with Axum in Rust](/posts/rust-http-axum-api/): body extractor goes last
- [Databases with SQLx in Rust](/posts/rust-database-sqlx/): avoid `SELECT *`
- [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/): no `anyhow` in libraries
- [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/): `ack_wait` above handling time
- [Observability in Rust with tracing](/posts/rust-tracing-observability/): `spawn` loses the span
- [Docker, CI and releasing a Rust service](/posts/rust-docker-ci-release/): I never ran `docker build`
- [Rust capstone: a complete service](/posts/rust-capstone-service/): log the cause only

**Going deeper**

- [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/): keep `unsafe` tiny
- [Performance and benchmarking with Criterion in Rust](/posts/rust-performance-criterion/): 0.3 ns means deleted work
- [The type-state pattern and API design in Rust](/posts/rust-typestate-patterns/): invalid states unrepresentable
- [Rust and WebAssembly](/posts/rust-wasm/): only numbers cross

## Lessons that kept coming back

1. **The compiler teaches.** [Borrowing and references in Rust](/posts/rust-borrowing-references/) says to read the labels, not just the headline.
2. **Owned or borrowed is a design choice.** [Ownership in Rust](/posts/rust-ownership/) says a `.clone()` often means the design wants a borrow.
3. **Errors are values in the type.** [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/) warns that `{}` hides causes.
4. **Async needs a runtime.** [async/await and Tokio in Rust](/posts/rust-async-tokio/): never block inside a task.
5. **Measure when quiet.** [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/) gives no numbers because the load was above 3.

## Go and Rust side by side

In [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/), one word-count test on a not-idle laptop gave Go a median of 249 ms and Rust 357 ms; Rust used less memory. The post calls it "one microbenchmark" that "says nothing about network services". [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) worked both ways from one proto. [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/) says: "I did not measure speed or throughput here". I still pick Go for most services.

## The year in numbers

From the post index: 72 posts when I wrote this, every one a Persian and English pair; 74 with the two recaps. Rust 30, Go Fundamentals 14, Go Backend 12, NATS JetStream 9, Go + Rust 4, no series 3. The Rust series ran from 2026-10-29 to 2027-03-18.

## What I would add next

Ideas from the posts' own gaps, not promises:

- A real `docker build` and `cargo audit` for [Docker, CI and releasing a Rust service](/posts/rust-docker-ci-release/).
- [Rust and WebAssembly](/posts/rust-wasm/) in a browser; only Node was used.
- Miri and sanitizers for [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/).
- Exporting spans with `tracing-opentelemetry`; it was not run.

## Where to go from here

New to Rust:

1. [Ownership in Rust](/posts/rust-ownership/)
2. [Borrowing and references in Rust](/posts/rust-borrowing-references/)
3. [Rust capstone: a complete service](/posts/rust-capstone-service/)

Coming from Go:

1. [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/)
2. [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/)

## Goodbye to 1405

Tomorrow is Nowruz and 1406 begins. Thank you for reading along. Happy new year.
