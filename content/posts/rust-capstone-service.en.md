+++
date = '2027-03-18T10:00:00+03:30'
draft = false
title = 'Rust capstone: a complete service'
description = 'A Rust orders service combining Axum, SQLx, thiserror, tracing, NATS JetStream and graceful shutdown, tested on real Postgres, with honest production gaps.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "capstone", "axum", "sqlx", "tracing", "nats", "thiserror", "backend"]
cover = { image = "/images/covers/rust-capstone-service.png", alt = "Rust capstone: a complete service", hiddenInSingle = true }
+++

Every post in this series built one piece alone: an API with Axum, a database layer with SQLx, typed errors, logs with spans, a NATS client, a graceful stop, tests. Each piece worked in its own small demo. The real question is what happens when they meet in one program, because that is where the bugs hide: in the seams between pieces, not inside any one of them.

This last technical post builds nothing new. It wires the earlier pieces into one small `orders` service and shows what happens at the seams. One example of a seam: a NUL character in a customer name passed my validation, and then Postgres rejected it. The client got a generic 500, and the log got the real cause and the request id. We will reproduce that below, on purpose.

The service has the same API as the Go one from [Building an API with net/http in Go](/posts/go-http-api-stdlib/): `POST /orders`, `GET /orders/{id}`, `GET /orders`, `/healthz` and `/readyz`. It comes after [Rust and WebAssembly](/posts/rust-wasm/). The module split follows [Modules, crates and Cargo in Rust](/posts/rust-modules-crates-cargo/), and the Go side of the same idea is [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/).

> I re-ran everything below for this version of the post, with `rustc 1.90.0`, edition 2024, and the versions locked in the demo's `Cargo.lock`: `axum 0.8.9`, `sqlx 0.8.6`, `async-nats 0.50.0`, `tokio 1.54.1`, `tower-http 0.7.1`, `tracing-subscriber 0.3.23`. The database was a real PostgreSQL 18.3 and the broker a real nats-server 2.15.1, each started by a tiny Go program (embedded, no Docker) as a separate process on a random local port. I stopped both at the end and checked that none of my processes were left. `RUST_LOG` was `info`; I cut timestamps from the logs, and the port in the address (`<port>` below) changes every run.

## The map: which piece comes from which post

Before the code, here is how the parts fit together. A request enters at the top and goes down:

| piece | file | what it does | where we met it |
|---|---|---|---|
| config | `config.rs` | reads and checks the environment | new here; the Go idea is in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/) |
| error type | `error.rs` | one `AppError`, mapped to HTTP in one place | [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/) |
| routes | `routes.rs` | `Router`, handlers, timeout and request id layers | [Building an API with Axum in Rust](/posts/rust-http-axum-api/) |
| logs | `routes.rs` | a span per request | [Observability in Rust with tracing](/posts/rust-tracing-observability/) |
| store | `store.rs` | Postgres through a connection pool | [Databases with SQLx in Rust](/posts/rust-database-sqlx/) |
| events | `events.rs` | publishes `order.created` to JetStream | [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/) |
| shutdown | `main.rs` | stops cleanly on SIGTERM | [Building an API with Axum in Rust](/posts/rust-http-axum-api/), with `select!` from [async/await and Tokio in Rust](/posts/rust-async-tokio/) |
| tests | `tests/api.rs` | calls the router without opening a port | [Testing and documentation in Rust](/posts/rust-testing-docs/) and `oneshot` from the Axum post |

The flow of one `POST /orders` is: the router gives the request an id and opens a span, the handler validates the input, the store writes a row to Postgres, and only then does `events` publish the event. If anything fails, `AppError` decides the status code.

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

`main.rs` is thin: it reads the config, connects to Postgres and NATS, and starts the server. Everything else lives in the library crate, so the tests in `tests/` can import it like any outside user.

## Config that fails loudly

A service that starts with a broken configuration and fails later, in the middle of a request, is the worst kind. So the config is checked once, at startup, and all the problems are reported together. If you have ever fixed one environment variable only to find the next one wrong, you know why.

`Config::from_lookup` takes a closure instead of reading the environment directly, so unit tests do not touch process-wide state. `Debug` is written by hand so the password in `DATABASE_URL` never reaches a log. Here is a start with three wrong values:

```text
$ DATABASE_URL=mysql://x:pw@h/db ORDERS_ADDR=nope NATS_URL=http://x ./orders-service
Error: invalid configuration:
  - ORDERS_ADDR="nope": invalid socket address syntax
  - DATABASE_URL is required and must start with postgres://
  - NATS_URL="http://x": must start with nats://
```

All three problems are in one message, and the exit code was 1. On a normal start the first log line shows the config with the password hidden: `starting cfg=Config { addr: 127.0.0.1:<port>, database_url: "<redacted>", nats_url: "nats://127.0.0.1:<port>" }`.

## One error type, one mapping

As in [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/), the library has a typed error and `anyhow` appears only in `main`. These are the variants, and the single place that turns them into HTTP:

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

Handlers return `Result<_, AppError>` and use `?`; `#[from]` converts a `sqlx::Error` automatically. The mapping has one rule that matters for security: the detail of a database error goes to the log, and the client gets only `{"error":"internal error"}`. The [Axum post](/posts/rust-http-axum-api/) covers extractors and `State`; here `AppState` holds a `Store` and `Events`, and both are cheap to clone.

## Requests, errors and logs

Each request gets a {{< term "request-id" "request id" >}} (`req-1`, `req-2`, and so on, from a simple counter) and a span that carries it, so every log line inside the request has it too. The span setup is the one from [Observability in Rust with tracing](/posts/rust-tracing-observability/). The layers are the ones from the Axum post. They are added bottom-up, and the last one added runs first: `SetRequestIdLayer` creates the id, then `TraceLayer` reads it for the span, and `PropagateRequestIdLayer` copies it into the response header `x-request-id`. There is also a 10-second `TimeoutLayer` around everything. Because the id is also in the response, a user can send you `req-6` and you can find the exact log lines.

I started the service and made the requests below, in order. First two successful creates and a list (`req-1` to `req-3`), then three failures. Responses, with the `date` and `content-length` headers cut:

```text
$ curl -i localhost:<port>/orders/999
HTTP/1.1 404 Not Found
x-request-id: req-4
{"error":"order not found"}

$ curl -i -X POST localhost:<port>/orders -d '{"customer":" ","cents":0}' -H 'content-type: application/json'
HTTP/1.1 422 Unprocessable Entity
x-request-id: req-5
{"error":"validation failed","fields":{"cents":"must be positive","customer":"is required"}}

$ curl -i -X POST localhost:<port>/orders -d '{"customer":"bad\u0000name","cents":100}' ...
HTTP/1.1 500 Internal Server Error
x-request-id: req-6
{"error":"internal error"}
```

The first is a missing order: `404`. The second breaks both validation rules at once, and the answer lists every field, not only the first. The third is the NUL character from the opening: the JSON is valid, the validation passes (the name is not empty), and Postgres refuses to store a NUL byte in text. The matching log lines:

```text
WARN request{method=GET path=/orders/999 request_id="req-4"}: orders_service::error: not found error=order 999 not found
WARN request{method=POST path=/orders request_id="req-5"}: orders_service::error: validation failed fields={"cents": "must be positive", "customer": "is required"}
ERROR request{method=POST path=/orders request_id="req-6"}: orders_service::error: request failed error=error returned from database: invalid byte sequence for encoding "UTF8": 0x00
```

Compare the two sides of `req-6`. The client saw `internal error` and nothing else, and the log has the real cause with the same request id. (The log also has the usual `finished processing request` line for each request, and for `req-6` a second `ERROR` line from the trace layer that says the response was classified as a failure with status 500; I left those out.) The 500 is the real failure from the opening. Fixing the validation is a one-line change that I left out on purpose, to show this path.

## Store, then event

`Store` is the `PgPool` handle from [Databases with SQLx in Rust](/posts/rust-database-sqlx/): a {{< term "connection-pool" "connection pool" >}}, `query_as`, `fetch_optional`, and `sqlx::migrate!("./migrations")` at startup, which applies the {{< term "migration" "migration" >}} that creates the `orders` table. The interesting part is the handler, because it touches two systems:

```rust
let order = st.store.create(&input.customer, input.cents).await?;
// Publish only after the row is committed. A failure here must not fail the request.
match st.events.order_created(&order).await {
    Ok(duplicate) => tracing::info!(order_id = order.id, duplicate, "published order.created"),
    Err(e) => tracing::warn!(order_id = order.id, error = %e, "event not published"),
}
```

The order of the two steps is a decision. We publish only after the row is saved, so we never announce an order that does not exist. And a failed publish is logged as a warning, not returned as an error, because the order is already in the database and telling the client "failed" would invite a retry that creates a second order. The price of this choice is in the production gaps at the end.

`Events` uses `async-nats` as in [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/), with the header `Nats-Msg-Id: order-{id}-created`. A small Go subscriber printed what arrived on the stream while I created the two orders:

```text
event seq=1 subject=order.created msg-id=order-1-created body={"id":1,"customer":"roham","cents":1990,"status":"new"}
event seq=2 subject=order.created msg-id=order-2-created body={"id":2,"customer":"sara","cents":500,"status":"new"}
```

One event per created order, each with the id the service chose. That id is what makes a retry safe. From Go I published `order-2-created` again, twice:

```text
publish order-2-created: seq=2 duplicate=true, stream messages=2
publish order-2-created: seq=2 duplicate=true, stream messages=2
```

The server answered with the original sequence number, flagged `duplicate=true`, and the stream still had 2 messages. The background of this {{< term "idempotency" "idempotency" >}} is in [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/).

## Graceful shutdown

When a platform stops the service it sends `SIGTERM`, and we want requests that are already running to finish. `axum::serve(...).with_graceful_shutdown(...)` waits for a future that listens for Ctrl+C and `SIGTERM` with `tokio::signal`, as in [Building an API with Axum in Rust](/posts/rust-http-axum-api/) (the `select!` that waits for either signal is the one from [async/await and Tokio in Rust](/posts/rust-async-tokio/)). After the server drains, `main` closes the pool and logs `stopped`.

To test this I needed a request that is really in flight when the signal arrives. I wrote a small client script that sends a POST with complete headers, waits 3 seconds, and only then sends the body, so the handler is stuck waiting for the body. (My first try with `nc` did not deliver the request on this machine, so I used a few lines of Python with a socket.) One second in, I sent `SIGTERM`, then tried a new connection:

```text
SIGTERM at 17:58:25
new connection during drain: 000
service gone at 17:58:28
HTTP/1.1 201 Created
x-request-id: req-1
{"id":3,"customer":"in-flight","cents":700,"status":"new"}
```

```text
INFO orders_service: shutdown requested, draining in-flight requests
INFO request{... request_id="req-1"}: ... published order.created order_id=3 duplicate=false
INFO request{... request_id="req-1"}: ... finished processing request latency=3010 ms status=201
INFO orders_service: stopped
```

A new connection during the drain got no answer (`000` is curl's code for "no HTTP response"). The slow request finished with `201` after about 3 seconds, as the `latency` shows, and its event was published before the process stopped. I repeated the run with the service as a child of my shell, to read its exit code: it was 0. The latency and the order id vary from run to run. The Go version of this idea is [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/), and the term is {{< term "graceful-shutdown" "graceful shutdown" >}}.

## Tests

As in [Testing and documentation in Rust](/posts/rust-testing-docs/), the {{< term "rust-integration-test" "integration tests" >}} call the `Router` directly with `tower::ServiceExt::oneshot`, so no port is opened, but the database is the real Postgres. (`Events::disabled()` skips NATS.) I ran them with `TEST_DATABASE_URL` pointing at the embedded Postgres:

```text
$ TEST_DATABASE_URL=postgres://... cargo test
test config::tests::reports_all_problems_together ... ok
test config::tests::debug_hides_the_password ... ok
test invalid_input_is_422_with_all_fields ... ok
test missing_order_is_404 ... ok
test create_then_get_then_list ... ok
```

The first two are unit tests inside `config.rs`; the other three are in `tests/api.rs`. `cargo clippy --all-targets -- -D warnings` and `cargo fmt --check` both passed with no output.

## What is missing for production

- No authentication or authorization.
- No rate limiting; see [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) for the ideas.
- Writing the row and publishing are two steps: a crash in between loses the event. The {{< term "outbox-pattern" "outbox pattern" >}} is the fix, and [The outbox pattern with Postgres and NATS in Go](/posts/go-outbox-pattern-nats/) shows it.
- `sqlx::migrate!` at startup is fine here, but with several replicas you need a real migration strategy.
- The request id is a counter, so it restarts at `req-1` after every restart and repeats across replicas. It is good for a demo, not for a fleet.
- No metrics, and the JetStream side (retention, replicas, security) is in [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/).

## Where failures stay quiet

- **Log the error source, return a generic body.** Never send database text to clients; `req-6` shows the pattern.
- **Axum's own extractor rejections use their own plain-text bodies,** not `AppError`: bad JSON or a non-numeric id gets Axum's message, not our JSON shape.
- **Publish after commit, and treat a failed publish as a warning only if you accept the gap above.**
- **The integration tests skip silently when `TEST_DATABASE_URL` is unset.** I ran them once without it: all three `api` tests printed `ok` without touching a database, and the only trace is a `skipping` line on stderr that `cargo test` hides. Set the variable in CI, or the tests prove nothing.

## What's next

*Rust series recap and a look back at 1405* closes the series with a map of all its posts.
