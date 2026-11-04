+++
date = '2027-03-20T10:00:00+03:30'
draft = false
title = 'Rust series recap and a look back at 1405'
description = 'Rust series recap for the Persian year 1405: a map of all 30 posts, recurring lessons, an honest Go and Rust comparison, real counts and open gaps.'
contentType = 'analysis'
categories = ["Meta"]
tags = ["rust", "go", "recap", "1405"]
cover = { image = "/images/covers/year-1405-rust-recap.png", alt = "Rust series recap and a look back at 1405", hiddenInSingle = true }
+++

Today is the last day of the Persian year 1405. After the [Go series recap for 1405](/posts/year-1405-go-recap/), this is the Rust one. Say you are curious about Rust but have not read any of my posts: this page tells you what the Rust series covers, in what order, the one idea each post is about, and what I would tell you to read first.

The series has 30 posts. They are listed here in the order I published them, which is also the order that makes sense to read them: each post builds on the ones before it. The takeaway under each link comes from that post.

## The Rust series, in reading order

### First steps

- [Getting started with Rust: install, Cargo and a first program](/posts/rust-getting-started/): you almost never call the compiler directly. `rustup` installs the tools and Cargo builds and runs your code, a bit like the `go` command. While editing, `cargo check` gives the fastest feedback.
- [Types, variables and control flow in Rust](/posts/rust-types-control-flow/): the basic vocabulary, and a few defaults that differ from Go. Adding 1 to a `u8` holding 255 panics in a debug build and silently wraps to 0 in a release build.

### Ownership and the core types

This is the part of Rust that is new for most people. Every value has one owner, and the compiler checks the rules before the program runs.

- [Ownership in Rust](/posts/rust-ownership/): `let b = a;` moves a `String` instead of copying it, so using `a` afterwards does not compile. This is how Rust manages memory without a garbage collector.
- [Borrowing and references in Rust](/posts/rust-borrowing-references/): instead of giving a value away, you lend it through a reference. The compiler errors you meet here are the main way you learn the rules.
- [Structs, enums and pattern matching in Rust](/posts/rust-structs-enums-pattern-matching/): each enum variant can carry data, and `match` must handle every case, so adding a variant later shows you every place to update.
- [Collections and strings in Rust](/posts/rust-collections-strings/): `Vec`, `HashMap` and the two string types, where ownership meets everyday work. A function that only reads text should take `&str`.
- [Error handling with Result and Option in Rust](/posts/rust-error-handling-result/): the possibility of failure is part of the type of the returned value, so you cannot forget it.

### Organizing code and abstractions

- [Modules, crates and Cargo in Rust](/posts/rust-modules-crates-cargo/): items are private by default, and a file without a `mod` declaration is simply ignored.
- [Generics and traits in Rust](/posts/rust-generics-traits/): one function for several types, and the compiler asks first what the type can do, which you answer with a trait bound.
- [Lifetimes in Rust](/posts/rust-lifetimes/): a lifetime annotation describes how references relate to each other; it never makes a value live longer.
- [Closures and iterators in Rust](/posts/rust-closures-iterators/): closures can use variables from the code around them, and iterators are lazy: nothing runs until something asks for the items.
- [Smart pointers: Box, Rc and RefCell in Rust](/posts/rust-smart-pointers/): three standard tools for the cases the single-owner rule does not fit, such as shared ownership.
- [Testing and documentation in Rust](/posts/rust-testing-docs/): the test runner is part of Cargo, and the examples in your documentation run as tests too.

### Concurrency and async

- [Concurrency with threads in Rust](/posts/rust-concurrency-threads/): the compiler refuses code with data races. It does not prevent deadlocks.
- [async/await and Tokio in Rust](/posts/rust-async-tokio/): an async function does nothing until you await it, many tasks share a few threads, and blocking a thread inside a task is the big mistake.

### Building services

- [Serde and JSON in Rust](/posts/rust-serde-json/): JSON is checked at the door: you get either a well-formed value or a clear error.
- [Building an API with Axum in Rust](/posts/rust-http-axum-api/): the same orders API as in the Go series, with careful status codes. The extractor that reads the body must come last.
- [Databases with SQLx in Rust](/posts/rust-database-sqlx/): plain queries are checked when they run, and the `query!` macros check them while the program compiles.
- [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/): one kind of error is for code that must decide, another is for humans who must understand what happened, and the original cause must not be lost.
- [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/): a publisher that knows its message was stored, and a worker that retries a failing message a limited number of times.

### Going deeper

- [Trait objects and dyn in Rust](/posts/rust-trait-objects-dyn/): when you need one list holding different types, `Box<dyn Trait>` finds the method at run time.
- [Macros in Rust](/posts/rust-macros/): code that writes code at compile time. Prefer a function or generics when one does the job.
- [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/): `unsafe` means the compiler cannot prove something and you promise it instead, so keep those blocks small and hide them behind a safe function. The same post builds a library that C can call.
- [Performance and benchmarking with Criterion in Rust](/posts/rust-performance-criterion/): repeat the work, take statistics, and make sure the compiler did not delete the work you meant to measure.
- [Futures, Pin and async internals in Rust](/posts/rust-pin-future-internals/): build a future and a tiny executor by hand to see what `.await` really does and why `Pin` exists.

### Running a service

- [Observability in Rust with tracing](/posts/rust-tracing-observability/): plain log lines cannot tell which request they belong to; structured events and spans can. A span is lost when you `tokio::spawn` a task unless you hand it over.
- [The type-state pattern and API design in Rust](/posts/rust-typestate-patterns/): write facts such as "this order is still a draft" into the types, so the wrong call does not compile.
- [Docker, CI and releasing a Rust service](/posts/rust-docker-ci-release/): a smaller static binary, a multi-stage image and a CI workflow. I never ran `docker build`, and the post says so.
- [Rust and WebAssembly](/posts/rust-wasm/): run the same Rust code inside a host such as Node. Only numbers cross the boundary, so a string is passed as a pointer and a length.
- [Rust capstone: a complete service](/posts/rust-capstone-service/): the pieces of the series wired into one `orders` service, to see the bugs that live in the seams. One example: a NUL character in a name passed validation and was then rejected by Postgres, so the client saw a generic 500 and the log had the real cause.

## Lessons that kept coming back

1. **The compiler teaches.** [Borrowing and references in Rust](/posts/rust-borrowing-references/) says to look at the labels of an error, not only its title: "first borrow occurs here" and "later used here" show which two lines conflict.
2. **Owned or borrowed is a design choice.** [Ownership in Rust](/posts/rust-ownership/) says not to reach for `.clone()` every time the compiler complains; it hides a copy and is usually a sign that the design should borrow instead of own.
3. **Errors are values in the type, and their causes matter.** [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/) warns that `{}` shows only the outermost message, so log with `{:#}` or `{:?}` or you lose the reason.
4. **Async needs a runtime, and blocking it hurts.** [async/await and Tokio in Rust](/posts/rust-async-tokio/) names blocking the thread inside a task as the one big mistake to avoid.
5. **Measure carefully, or say you did not.** [Performance and benchmarking with Criterion in Rust](/posts/rust-performance-criterion/) explains that a result around 0.3 nanoseconds means the work was deleted. [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/) gives no numbers, because the machine was busy with a load average around 4.

## Go and Rust side by side

In [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/) I counted words in a generated text of 10 million words. In my original run, on a laptop that was not idle, the median counting time was 249 ms for Go and 357 ms for Rust. Rust used less memory (81 MB against 167 to 207 MB) and made a much smaller binary (445,600 bytes against 2,544,610). Then I swapped Rust's default hasher for a simple one, and the median became 214 ms, faster than both. The post's own conclusion is that one microbenchmark is not evidence about your workload, and that this test says nothing about network services.

[Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/) shows both languages working from one `.proto` file. [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/) says that its demo measures nothing about speed. I still pick Go for most services, and I am learning Rust to know when it is the better tool.

## The year in numbers

Counted from the post dates, 180 posts are published by today, counting the two recaps, and each exists in a Persian and an English version. The Rust series has 30 posts, from 29 October 2026 to 18 March 2027. The Go-related posts add up to 39: Go Fundamentals 14, Go Backend 12, NATS JetStream 9 and Go + Rust 4.

## What the posts say is still missing

These are gaps the posts admit to themselves, not promises.

- A real `docker build` and `cargo audit` for [Docker, CI and releasing a Rust service](/posts/rust-docker-ci-release/); neither was run.
- [Rust and WebAssembly](/posts/rust-wasm/) in a browser: no browser was available, and only Node was used.
- Miri and sanitizers for [Unsafe and FFI in Rust](/posts/rust-unsafe-ffi/): neither was installed, so neither was run.
- Exporting spans with `tracing-opentelemetry` in [Observability in Rust with tracing](/posts/rust-tracing-observability/): the post only mentions it and did not run it.

## Where to start

If you are new to Rust:

1. [Ownership in Rust](/posts/rust-ownership/)
2. [Borrowing and references in Rust](/posts/rust-borrowing-references/)
3. [Rust capstone: a complete service](/posts/rust-capstone-service/)

If you are coming from Go:

1. [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/)
2. [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/)

If you have not installed Rust yet, begin with [Getting started with Rust: install, Cargo and a first program](/posts/rust-getting-started/).

## Goodbye to 1405

Tomorrow is Nowruz and 1406 begins. Thank you for reading along. Happy new year.
