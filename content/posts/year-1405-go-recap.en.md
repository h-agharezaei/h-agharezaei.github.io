+++
date = '2027-03-16T10:00:00+03:30'
draft = false
title = 'Go series recap for 1405'
description = 'A map of the 39 Go-related posts from 1405: fundamentals, Go backend, NATS JetStream and Go + Rust, with the lessons that kept coming back.'
categories = ["Meta"]
tags = ["go", "recap", "1405", "nats", "backend"]
cover = { image = "/images/covers/year-1405-go-recap.png", alt = "Go series recap for 1405", hiddenInSingle = true, hiddenInList = true }
+++

A map for readers arriving at the Go posts, and a reference for me. There are 39 Go-related posts: 14 in Go Fundamentals, 12 in Go Backend, 9 in NATS JetStream and 4 in Go + Rust. Most came out since Aban 1405; the first two NATS posts predate that calendar.

## The map

**Go Fundamentals (14)**

- [Getting started with Go: install, modules, tooling](/posts/go-getting-started/): `go run .` builds the package
- [Types, variables and control flow in Go](/posts/go-types-control-flow/): `:=` in inner blocks shadows
- [Functions, defer and error handling in Go](/posts/go-functions-defer-errors/): wrap errors with `%w`
- [Slices, maps and strings in Go](/posts/go-slices-maps-strings/): sub-slices share memory
- [Structs, methods and interfaces in Go](/posts/go-structs-methods-interfaces/): pointer receivers need `&C{}`
- [Pointers and the memory model in Go](/posts/go-pointers-memory/): measure before optimizing
- [Packages and modules: structuring a Go project](/posts/go-packages-modules/): over-structuring is the trap
- [Goroutines and channels in Go](/posts/go-goroutines-channels/): know how each goroutine ends
- [sync, select and context in Go](/posts/go-sync-select-context/): context is the first argument
- [Generics in Go](/posts/go-generics/): start concrete
- [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/): `-count=1` skips the cache
- [Files, io.Reader/Writer and JSON in Go](/posts/go-file-io-json/): lowercase fields are skipped silently
- [Building a command-line tool in Go](/posts/go-cli-tool/): decide the exit code in one place
- [Mini project: a URL shortener in Go](/posts/go-mini-project-url-shortener/): saved only on clean shutdown

**Go Backend (12)**

- [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/): start flat
- [Config, structured logging and errors in Go](/posts/go-config-logging-errors/): log an error once
- [Building an API with net/http in Go](/posts/go-http-api-stdlib/): middleware order matters
- [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/): a deadline on every request
- [Transactions and the repository pattern in Go](/posts/go-transactions-patterns/): keep transactions short
- [Concurrency patterns: worker pool and errgroup](/posts/go-concurrency-patterns/): give goroutines a way out
- [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/): ordering is not free
- [A gRPC service in Go](/posts/go-grpc-service/): always set client deadlines
- [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/): caching trades freshness
- [Profiling Go with pprof](/posts/go-profiling-pprof/): same load before and after
- [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/): `latest` is not a version
- [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/): profile before tuning `GOGC`

**NATS JetStream (9)**

- [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/): a durable pull consumer
- [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/): plain `Nak()` retries instantly
- [Multiple workers on one consumer and monitoring lag in JetStream](/posts/nats-jetstream-scaling-lag/): alert on growing pending
- [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/): a handler must tolerate repeats
- [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/): finish in-flight work
- [Observability for JetStream: metrics, logs and traces](/posts/nats-jetstream-observability/): the dead-letter depth should be zero
- [Testing JetStream services with an embedded nats-server](/posts/nats-jetstream-testing/): wait for conditions, not sleeps
- [KV and Object Store in NATS](/posts/nats-kv-object-store/): not a database
- [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/): replicas are not backups

**Go + Rust (4)**

- [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/): measure your own workload
- [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/): document what empty means
- [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/): free with the allocator that made it
- [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/): correctness from idempotent steps

## Lessons that kept coming back

- **Real output beats assumption.** In [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/) a plain `Nak()` ignored `BackOff` in my run.
- **At-least-once means idempotent.** [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/) shows a late ack being accepted. [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) says shutdown only shrinks redelivery.
- **Deadlines and cancellation everywhere.** [Concurrency patterns: worker pool and errgroup](/posts/go-concurrency-patterns/) watches `ctx.Done()`; [A gRPC service in Go](/posts/go-grpc-service/) sets deadlines.
- **Decide errors in one place.** [Config, structured logging and errors in Go](/posts/go-config-logging-errors/) logs at the boundary; [Building a command-line tool in Go](/posts/go-cli-tool/) picks the exit code once.
- **Measure before tuning.** [Profiling Go with pprof](/posts/go-profiling-pprof/) compares runs under the same load; [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/) says one microbenchmark is not evidence.

## What I would add next

Gaps the posts admit to:

- No real Docker build: [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/).
- No multi-host, disk failure or partition tests: [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/).
- `LISTEN/NOTIFY` untested: [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/).
- Invalidation race not reproduced: [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/).
- No throughput or metrics measured: [Capstone: an event pipeline with Go, Rust and NATS](/posts/go-rust-event-pipeline-capstone/).

## Where to go from here

New to Go:

1. [Getting started with Go: install, modules, tooling](/posts/go-getting-started/)
2. [Goroutines and channels in Go](/posts/go-goroutines-channels/)
3. [Mini project: a URL shortener in Go](/posts/go-mini-project-url-shortener/)

Building services:

1. [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/)
2. [Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/)
3. [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/)

Messaging:

1. [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/)
2. [Retry and Dead-Letter Queues in NATS JetStream with Go](/posts/nats-jetstream-retry-dlq/)
3. [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/)

Next: Rust series recap and a look back at 1405.
