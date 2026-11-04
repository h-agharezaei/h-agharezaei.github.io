+++
date = '2027-03-16T10:00:00+03:30'
draft = false
title = 'Go series recap for 1405'
description = 'A map of the 39 Go-related posts from 1405: fundamentals, Go backend, NATS JetStream and Go + Rust, with the lessons that kept coming back.'
contentType = 'analysis'
categories = ["Meta"]
tags = ["go", "recap", "1405", "nats", "backend"]
cover = { image = "/images/covers/year-1405-go-recap.png", alt = "Go series recap for 1405", hiddenInSingle = true }
+++

Say you have heard that I wrote a lot about Go this year, and you want to know where to begin. Thirty-nine posts is a lot to open one by one. This post is the map: what the Go posts cover, in which order they build on each other, the one idea each post is about, and the lessons that kept coming back.

The 39 posts fall into four groups: 14 in Go Fundamentals, 12 in Go Backend, 9 in NATS JetStream and 4 in Go + Rust. Most were published from Aban 1405 on; the first two NATS posts came out a little earlier, in Mehr. Within a group the posts are listed in the order I published them, and each one builds on the one before it. You do not need to have read any of them to follow this page.

## The map

### Go Fundamentals (14 posts): the language itself

These posts start from zero. They assume you can program, not that you know Go.

- [Getting started with Go: install, modules, tooling](/posts/go-getting-started/): install Go, create a module and learn the everyday commands. Go is strict from the first program: an unused variable or import is a compile error, not a warning.
- [Types, variables and control flow in Go](/posts/go-types-control-flow/): every variable has a zero value, there is no implicit conversion between number types, and `:=` inside an inner block creates a new variable that hides the outer one.
- [Functions, defer and error handling in Go](/posts/go-functions-defer-errors/): errors are ordinary values that a function returns and the caller checks right away; `defer` does the cleanup; wrap an error with `%w` if the caller may need to inspect it later.
- [Slices, maps and strings in Go](/posts/go-slices-maps-strings/): a slice is a window onto an array, so a sub-slice shares memory with the original.
- [Structs, methods and interfaces in Go](/posts/go-structs-methods-interfaces/): Go has no classes; an interface is satisfied without any type naming it. A value type does not get the methods that have a pointer receiver, so you write `&C{}`.
- [Pointers and the memory model in Go](/posts/go-pointers-memory/): Go always passes copies, a pointer lets a function change the original, and the compiler decides where each value lives.
- [Packages and modules: structuring a Go project](/posts/go-packages-modules/): a package is one directory of code, a module is a set of packages versioned together, and the compiler enforces who can see what.
- [Goroutines and channels in Go](/posts/go-goroutines-channels/): how to start concurrent work, why two goroutines touching one variable give wrong answers without any error, and how channels and the race detector help.
- [sync, select and context in Go](/posts/go-sync-select-context/): a mutex protects shared memory, `select` waits on several things at once, and `context` carries cancellation and timeouts.
- [Generics in Go](/posts/go-generics/): one function for several types, still checked by the compiler, and when to leave generics alone.
- [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/): tests and benchmarks ship with the toolchain. If you see `(cached)`, Go is reusing an old result; `-count=1` turns that off.
- [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/): write against `io.Reader` and `io.Writer`, and the same code works on files, buffers and network connections. `encoding/json` skips lowercase (unexported) fields without any error.
- [Building a command-line tool in Go](/posts/go-cli-tool/): the `flag` package, subcommands and exit codes. `os.Exit` skips deferred calls, so keep it in one place and let a `run` function return the exit code.
- [Mini project: a URL shortener in Go](/posts/go-mini-project-url-shortener/): a small HTTP service with only the standard library. The interesting part is the order at shutdown: wait for running requests first, save the data afterwards.

### Go Backend (12 posts): one service, built piece by piece

Most of these posts work on the same small `orders` service, so each post adds one real concern to code you already know.

- [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/): keep business rules, storage and HTTP in separate places, and let the Go toolchain show who imports whom. For a very small tool, start flat.
- [Config, structured logging and errors in Go](/posts/go-config-logging-errors/): load configuration once, log in a structured way, and decide how errors are logged and answered in one place, at the boundary.
- [Building an API with net/http in Go](/posts/go-http-api-stdlib/): the one-line `ListenAndServe` hides decisions; the post adds timeouts, middleware, safe JSON decoding and shutdown, and shows that middleware order matters.
- [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/): a database is just a second implementation of an interface the service already declares. Put a deadline on every query.
- [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/): first lose money on purpose with two writes and no transaction, then fix it. Keep transactions short.
- [Concurrency patterns: worker pool and errgroup](/posts/go-concurrency-patterns/): run work concurrently but bounded, and give every goroutine a way to stop.
- [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/): no transaction spans both the database and the broker, so write the event into the same transaction as the order and publish it later. Delivery is at least once, and ordering is not free.
- [A gRPC service in Go](/posts/go-grpc-service/): put the contract in a `.proto` file so a renamed field breaks the build and not production. Set a deadline on every client call.
- [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/): a token bucket per client protects the service from one noisy caller, and a cache protects the database from repeated questions, at the price of possibly stale data.
- [Profiling Go with pprof](/posts/go-profiling-pprof/): find where time and memory go instead of guessing, change one thing at a time, and compare before and after.
- [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/): a static binary, a container image, a CI workflow and health endpoints. A platform stops a container with SIGTERM, so graceful shutdown matters here.
- [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/): small experiments that show what the runtime does behind `go f()` and `make`.

### NATS JetStream (9 posts): messaging with Go

NATS JetStream is a message system that stores messages, so a worker that was down can come back and continue where it stopped. These posts build one worker step by step.

- [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/): a publisher, a worker and a durable pull consumer, so a message is not lost while the worker restarts.
- [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/): cap the attempts, pause between them and move hopeless messages aside. A plain `Nak()` retries at once.
- [Multiple workers on one consumer and monitoring lag in JetStream](/posts/nats-jetstream-scaling-lag/): add workers by sharing one durable consumer, and watch the pending count to see the queue backing up.
- [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/): what "exactly-once" can honestly promise, and why the handler must still tolerate a message arriving twice.
- [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/): on a stop signal, stop taking new jobs, finish the ones in progress and only then exit.
- [Observability for JetStream: metrics, logs and traces](/posts/nats-jetstream-observability/): three signals that show whether the worker is healthy and what happened to one message. The dead-letter stream should normally be empty.
- [Testing JetStream services with an embedded nats-server](/posts/nats-jetstream-testing/): every test starts its own private server, and waits for a condition instead of a fixed sleep.
- [KV and Object Store in NATS](/posts/nats-kv-object-store/): JetStream can also hold small shared state and files. It is not a database.
- [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/): three servers instead of one, a retention plan, and users, permissions and TLS. Replicas are not backups.

### Go + Rust (4 posts): the two languages together

- [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/): one small measurement and a list of documented differences, then a guide to choosing. Measure your own workload.
- [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/): one `.proto` generates both sides. The contract still leaves questions open, such as what an empty filter means.
- [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/): call Rust inside the same process through the C calling convention. Release memory with the allocator that created it.
- [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/): the outbox, JetStream, a Rust worker and a read model together, tested by killing pieces. Correctness comes from steps that are safe to repeat, not from an "exactly once" switch.

## Lessons that kept coming back

These are the points the posts themselves return to.

- **Real output beats assumption.** In [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/), a plain `Nak()` ignored `BackOff` in my run, and all three attempts finished at second zero.
- **At-least-once delivery means the handler must be idempotent.** [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/) shows the server accepting a late ack from an old delivery, so a successful ack does not prove you were the only one who processed the message. [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) says a graceful shutdown only shrinks the window in which a job can be cut off; it reduces redelivery but does not remove it, so the handler still has to tolerate repeats.
- **Put deadlines and cancellation everywhere.** [Concurrency patterns: worker pool and errgroup](/posts/go-concurrency-patterns/) shows goroutines that watch `ctx.Done()` and stop, and [A gRPC service in Go](/posts/go-grpc-service/) says to always set a client deadline.
- **Decide errors in one place.** [Config, structured logging and errors in Go](/posts/go-config-logging-errors/) logs an error once, at the boundary. [Building a command-line tool in Go](/posts/go-cli-tool/) picks the exit code in one place.
- **Measure before tuning.** [Profiling Go with pprof](/posts/go-profiling-pprof/) compares before and after under the same load, and [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/) says that one microbenchmark is not evidence about your workload.

## What the posts say is still missing

These are gaps the posts admit to themselves, not promises of new posts.

- A real `docker build` was never run: see [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/).
- Nodes on different hosts, a real disk failure and a partition between nodes were not tested: see [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/).
- Postgres `LISTEN/NOTIFY` for waking the relay was not tested: see [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/).
- A cache invalidation that loses a race was described but not reproduced: see [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/).
- The capstone measures nothing about speed, with no metrics and no throughput numbers: see [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/).

## Where to start

If you are new to Go:

1. [Getting started with Go: install, modules, tooling](/posts/go-getting-started/)
2. [Goroutines and channels in Go](/posts/go-goroutines-channels/)
3. [Mini project: a URL shortener in Go](/posts/go-mini-project-url-shortener/)

If you want to build services:

1. [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/)
2. [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/)
3. [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/)

If you want messaging:

1. [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/)
2. [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/)
3. [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/)

Next is the Rust series recap and a look back at 1405.
