+++
date = '2027-03-04T10:00:00+03:30'
draft = false
title = 'Observability in Rust with tracing'
description = 'Structured events, spans, EnvFilter, JSON output and the lost-span trap with tokio::spawn: how the tracing crate makes async Rust services debuggable.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "tracing", "observability", "async", "logging"]
cover = { image = "/images/covers/rust-tracing-observability.png", alt = "Observability in Rust with tracing", hiddenInSingle = true, hiddenInList = true }
+++

The [previous post](/posts/rust-pin-future-internals/) opened up async internals. Now the practical question: when a service runs thousands of tasks at once, how do you see what happened to one request? This post uses the `tracing` crate on the kind of code from [async/await and Tokio](/posts/rust-async-tokio/), and the same ideas apply to a service like the one in [Building an API with Axum](/posts/rust-http-axum-api/). I compare it with `slog` from [Config, structured logging and errors in Go](/posts/go-config-logging-errors/) at the end.

> Rust 1.90, edition 2024, `tracing 0.1.44`, `tracing-subscriber 0.3.23` (features `env-filter`, `json`), `tokio 1.54.1`. All output below was copied from real runs (colors turned off with `NO_COLOR=1`).

## Why plain logs are not enough

Three tasks, each printing three lines with `println!`:

```text
start
start
start
charging card
charging card
done
done
charging card
done
```

Which "done" belongs to which order? You cannot tell. Threads and `.await` interleave the lines, and the order differs between runs. You could prefix every line with an id by hand, but forgetting once is enough.

## Events and spans

An **event** is a point in time: `info!`, `warn!`, `debug!`. A **span** is a period of time with fields; every event inside it carries the span's context automatically. Fields are structured, not formatted into the message:

```rust
let order = Order { id: 42, total: 19.5 };   // derives Debug
let user = "roham";
info!(order_id = order.id, "created");
info!(%user, ?order, "details");
debug!(step = "validate", "checking stock");
warn!(retry_in = ?Duration::from_millis(250), "payment slow");
```

`%x` records the value with `Display`, `?x` with `Debug`. Nothing is printed until you install a **subscriber**:

```rust
tracing_subscriber::fmt()
    .with_env_filter(EnvFilter::from_default_env())
    .init();
```

With no `RUST_LOG` the filter is empty, and this program printed nothing at all. With `RUST_LOG=info`, only the `info` and `warn` lines appeared. With `RUST_LOG=info,basic=debug` (debug for the crate named `basic`):

```text
2026-10-23T21:26:02.055509Z  INFO basic: created order_id=42
2026-10-23T21:26:02.055634Z  INFO basic: details user=roham order=Order { id: 42, total: 19.5 }
2026-10-23T21:26:02.055669Z DEBUG basic: checking stock step="validate"
2026-10-23T21:26:02.055694Z  WARN basic: payment slow retry_in=250ms
2026-10-23T21:26:02.055723Z DEBUG basic::other: inside module other
2026-10-23T21:26:02.055744Z  INFO basic::other: module other done
```

The `trace!` line never appears, because trace is below debug. The filter is read at startup, so you change verbosity without recompiling.

## Spans on async functions

`#[instrument]` wraps a function in a span named after it, with the arguments as fields:

```rust
#[instrument(skip(token), fields(user = "roham", amount_cents = field::Empty), err)]
async fn charge(order_id: u32, token: &str) -> Result<(), PaymentError> {
    sleep(Duration::from_millis(10)).await;
    Span::current().record("amount_cents", 1000 + order_id as u64);
    info!("charging card");
    if order_id == 3 { return Err(PaymentError("card declined")); }
    Ok(())
}

#[instrument]
async fn handle(order_id: u32) { /* info!("start"); sleep; charge(...).await; info!("done") */ }
```

`skip(token)` keeps the secret out of the fields, `fields(...)` adds extra ones, `field::Empty` reserves a slot to `record` later, and `err` logs an `Err` as an `ERROR` event. Running three `handle` calls concurrently with `JoinSet`:

```text
INFO handle{order_id=3}: start
INFO handle{order_id=1}: start
INFO handle{order_id=2}: start
INFO handle{order_id=1}:charge{order_id=1 user="roham" amount_cents=1001}: charging card
INFO handle{order_id=1}: done
INFO handle{order_id=2}:charge{order_id=2 user="roham" amount_cents=1002}: charging card
INFO handle{order_id=2}: done
INFO handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: charging card
ERROR handle{order_id=3}:charge{order_id=3 user="roham" amount_cents=1003}: error=card declined
WARN handle{order_id=3}: order failed error=card declined
```

(timestamps cut). The lines are still interleaved, but now every line says which request it belongs to, and `charge` is nested inside `handle`. That is the payoff: the span follows the task across every `.await`.

## JSON output

For log pipelines, swap `.init()` for `.json().init()`. One line looks like this:

```text
{"timestamp":"2026-10-23T21:25:56.264438Z","level":"ERROR","fields":{"error":"card declined"},"span":{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"},"spans":[{"order_id":3,"name":"handle"},{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"}]}
```

The full span chain is in `spans`, ready to filter by `order_id`.

## The tokio::spawn trap

A spawned task is a new top-level task, so it does not inherit the current span:

```rust
let span = info_span!("request", request_id = "req-7");
async {
    info!("handling");
    tokio::spawn(background_audit()).await.unwrap();   // lost context
    info!("responded");
}.instrument(span).await;
```

```text
INFO request{request_id="req-7"}: handling
INFO audit written
INFO request{request_id="req-7"}: responded
```

"audit written" has no request id. The fix is `Instrument::instrument`, passing the current span:

```rust
tokio::spawn(background_audit().instrument(tracing::Span::current()))
```

```text
INFO request{request_id="req-7"}: handling
INFO request{request_id="req-7"}: audit written
INFO request{request_id="req-7"}: responded
```

## Span timing

`.with_span_events(FmtSpan::CLOSE)` prints one line when a span closes. For a function that slept 50 ms and then spun the CPU for 20 ms, on this machine (load average around 3, so treat it as rough):

```text
INFO work: close time.busy=20.1ms time.idle=52.9ms
```

Busy is time spent being polled, idle is time waiting between polls.

## Beyond the console

Exporting spans to Jaeger or any OpenTelemetry backend is done by adding another layer, `tracing-opentelemetry`, to the same subscriber. I only mention it here and did not run it.

Compared with Go: `log/slog` gives structured key-value logs and `With` for attaching fields to a logger, but it has no span concept; correlating lines across goroutines means passing a logger or a context yourself. In `tracing`, the span is the carrier.

## A few things to watch

- `tokio::spawn` loses the span; use `.instrument(Span::current())`.
- `#[instrument]` records all arguments with `Debug` by default; use `skip` for secrets and large values.
- A `Span::enter()` guard held across `.await` is wrong in async code; use `#[instrument]` or `.instrument(span)`.
- Without `RUST_LOG` (or a default directive) the `EnvFilter` prints nothing, which looks like a bug.
- Pick `FmtSpan::CLOSE` timing for hints, not for benchmarks.

## Exercise

Add a `request_id` field to a span around your own handler, spawn a background task from it, and check that its lines carry the id. Then switch to JSON and filter the output by that id.

## What's next

The next post is about the type-state pattern and API design in Rust: encoding valid states in types so wrong usage does not compile.
