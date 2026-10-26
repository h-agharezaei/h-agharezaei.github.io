+++
date = '2027-03-18T10:00:00+03:30'
draft = false
title = 'Rust capstone: a complete service'
description = 'A Rust orders service combining Axum, SQLx, thiserror, tracing, NATS JetStream and graceful shutdown, tested on real Postgres, with honest production gaps.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "capstone", "axum", "sqlx", "tracing", "nats", "thiserror", "backend"]
cover = { image = "/images/covers/rust-capstone-service.png", alt = "Rust capstone: a complete service", hiddenInSingle = true }
+++

The [previous post](/posts/rust-wasm/) was about WebAssembly. This one is the last technical post of the series, and it builds nothing new: it wires the earlier pieces into one small `orders` service. It has the same API as the Go one from [Building an API with net/http in Go](/posts/go-http-api-stdlib/): `POST /orders`, `GET /orders/{id}`, `GET /orders`, `/healthz` and `/readyz`. The module split follows [Modules, crates and Cargo in Rust](/posts/rust-modules-crates-cargo/), and the Go side of the same idea is [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/).

> Rust 1.90, edition 2024, `axum 0.8.9`, `sqlx 0.8.6`, `async-nats 0.50.0`, `tokio 1.54.1`, `tracing-subscriber 0.3.23`. Real PostgreSQL 18.3 and nats-server 2.15.1, each started from a tiny Go program (embedded, no Docker) as separate processes, stopped at the end. Everything below was run; `RUST_LOG` was `info` and timestamps are cut from logs.

## Layout

```text
orders-service
├── Cargo.toml
├── migrations/0001_create_orders.sql
├── src
│   ├── lib.rs      (just `pub mod` lines)
│   ├── config.rs   typed Config, errors reported together
│   ├── error.rs    AppError + IntoResponse
│   ├── store.rs    PgPool, query_as, migrations
│   ├── events.rs   JetStream publisher
│   ├── routes.rs   Router, handlers, request id, tracing
│   └── main.rs     wiring, shutdown, anyhow
└── tests/api.rs
```

`main.rs` is thin; everything else lives in the library, so the tests in `tests/` can import it.

## Config that fails loudly

`Config::from_lookup` takes a closure instead of reading the environment, so unit tests do not touch process-wide state. It collects every problem and returns them together. `Debug` is written by hand so the password in `DATABASE_URL` never reaches a log.

```text
$ DATABASE_URL=mysql://x:pw@h/db ORDERS_ADDR=nope NATS_URL=http://x ./orders-service
Error: invalid configuration:
  - ORDERS_ADDR="nope": invalid socket address syntax
  - DATABASE_URL is required and must start with postgres://
  - NATS_URL="http://x": must start with nats://
```

The exit code was 1. On a normal start the log says `cfg=Config { addr: 127.0.0.1:8123, database_url: "<redacted>", ... }`.

## One error type, one mapping

As in [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/), the library has a typed error and `anyhow` appears only in `main`. The variants and the single place that turns them into HTTP:

```rust
#[derive(Debug, Error)]
pub enum AppError {
    #[error("order {0} not found")]
    NotFound(i64),
    #[error("validation failed")]
    Validation(BTreeMap<&'static str, &'static str>),
    #[error("database error")]
    Db(#[from] sqlx::Error),
}
// into_response: NotFound -> 404, Validation -> 422,
// Db -> tracing::error!(error = %source) and a generic 500 body
```

Handlers return `Result<_, AppError>` and use `?`; `#[from]` converts `sqlx::Error` for free. The [Axum post](/posts/rust-http-axum-api/) covers extractors and `State`; here `AppState` holds a `Store` and `Events`, both cheap to clone.

## Requests, errors and logs

Each request gets a span with a `request_id` (the layer setup is from [Observability in Rust with tracing](/posts/rust-tracing-observability/)), so every line inside carries it. Real runs, with the matching log lines:

```text
$ curl -i localhost:8123/orders/999
HTTP/1.1 404 Not Found
x-request-id: req-4
{"error":"order not found"}

$ curl -i -X POST localhost:8123/orders -d '{"customer":" ","cents":0}' -H 'content-type: application/json'
HTTP/1.1 422 Unprocessable Entity
x-request-id: req-5
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -i -X POST localhost:8123/orders -d '{"customer":"bad\u0000name","cents":100}' ...
HTTP/1.1 500 Internal Server Error
x-request-id: req-6
{"error":"internal error"}
```

```text
WARN request{method=GET path=/orders/999 request_id="req-4"}: orders_service::error: not found error=order 999 not found
WARN request{method=POST path=/orders request_id="req-5"}: orders_service::error: validation failed fields={"cents": "must be positive", "customer": "is required"}
ERROR request{method=POST path=/orders request_id="req-6"}: orders_service::error: request failed error=error returned from database: invalid byte sequence for encoding "UTF8": 0x00
```

The 500 is a real, unexpected failure: a NUL character in the customer name passes my validation and Postgres rejects it. The client sees a generic body, the log has the cause and the id. Fixing the validation is a one-line change that I left out on purpose to show this path.

## Store, then event

`Store` is the `PgPool` handle from [Databases with SQLx in Rust](/posts/rust-database-sqlx/): `query_as`, `fetch_optional`, and `sqlx::migrate!("./migrations")` at startup. The interesting part is the handler:

```rust
let order = st.store.create(&input.customer, input.cents).await?;
// Publish only after the row is committed. A failure here must not fail the request.
match st.events.order_created(&order).await {
    Ok(duplicate) => tracing::info!(order_id = order.id, duplicate, "published order.created"),
    Err(e) => tracing::warn!(order_id = order.id, error = %e, "event not published"),
}
```

`Events` uses `async-nats` as in [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/), with the header `Nats-Msg-Id: order-{id}-created`. A small Go subscriber printed what arrived:

```text
event seq=1 subject=order.created msg-id=order-2-created body={"id":2,"customer":"roham","cents":1990,"status":"new"}
event seq=2 subject=order.created msg-id=order-3-created body={"id":3,"customer":"sara","cents":500,"status":"new"}
```

Republishing the same id twice from Go:

```text
publish order-2-created: seq=1 duplicate=true, stream messages=2
publish order-2-created: seq=1 duplicate=true, stream messages=2
```

The server answered with the original sequence, flagged `duplicate=true`, and the stream still had 2 messages. The idempotency background is in [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/).

## Graceful shutdown

`axum::serve(...).with_graceful_shutdown(...)` waits for a future that listens for Ctrl+C and `SIGTERM` with `tokio::signal`, as in [async/await and Tokio in Rust](/posts/rust-async-tokio/). To get a request that is truly in flight, I sent a POST with full headers through `nc` and delayed the body by 3 seconds; one second in, I sent `SIGTERM`:

```text
SIGTERM at 01:00:57
new connection during drain: 000
service exit code: 0 at 01:00:59
HTTP/1.1 201 Created
{"id":5,"customer":"in-flight","cents":700,"status":"new"}
```

```text
INFO orders_service: shutdown requested, draining in-flight requests
INFO request{... request_id="req-1"}: ... published order.created order_id=5 duplicate=false
INFO request{... request_id="req-1"}: ... finished processing request latency=3004 ms status=201
INFO orders_service: stopped
```

A new connection during the drain got no answer (`000` is curl's code for "no HTTP response"), the slow request finished with 201, and the process exited with 0. The Go version of this idea is [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/).

## Tests

As in [Testing and documentation in Rust](/posts/rust-testing-docs/), integration tests call the `Router` with `tower::ServiceExt::oneshot`, so no port is opened, but the database is the real Postgres (`Events::disabled()` skips NATS):

```text
$ TEST_DATABASE_URL=postgres://... cargo test
test config::tests::debug_hides_the_password ... ok
test config::tests::reports_all_problems_together ... ok
test invalid_input_is_422_with_all_fields ... ok
test missing_order_is_404 ... ok
test create_then_get_then_list ... ok
```

`cargo clippy --all-targets -- -D warnings` and `cargo fmt --check` both passed with no output.

## What is missing for production

- No authentication or authorization.
- No rate limiting; see [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) for the ideas.
- Writing the row and publishing are two steps: a crash in between loses the event. [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/) is the fix.
- `sqlx::migrate!` at startup is fine here, but with several replicas you need a real migration strategy.
- No metrics, and the JetStream side (retention, replicas, security) is in [JetStream in production](/posts/nats-jetstream-production/).

## A few things to watch

- Log the error source, return a generic body; never send database text to clients.
- Axum's own extractor rejections (bad JSON, non-numeric id) use their own plain-text bodies, not `AppError`.
- Publish after commit, and treat a failed publish as a warning only if you accept the gap above.
- The integration tests skip silently when `TEST_DATABASE_URL` is unset; set it in CI.

## What's next

The next post is the year-end recap of the Rust series and 1405.
