+++
date = '2027-03-04T10:00:00+03:30'
draft = false
title = 'Observability in Rust with tracing'
description = 'Structured events, spans, EnvFilter, JSON output and the lost-span trap with tokio::spawn: how the tracing crate makes async Rust services debuggable.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "tracing", "observability", "async", "logging"]
cover = { image = "/images/covers/rust-tracing-observability.png", alt = "Observability in Rust with tracing", hiddenInSingle = true }
+++

A service writes this in its log:

```text
done
```

Which request was it? If a thousand requests are running at the same time, that line is useless. You would want something like "request 42, charging the card, took 30 ms, failed with `card declined`". Getting from the first line to the second is what this post is about.

Rust has a crate for it called `tracing`. We use it on the kind of async code from [async/await and Tokio](/posts/rust-async-tokio/), right after [async internals](/posts/rust-pin-future-internals/), and the same ideas apply to a service like the one in [Building an API with Axum](/posts/rust-http-axum-api/). At the end I compare it with `slog` from [Config, structured logging and errors in Go](/posts/go-config-logging-errors/).

> I ran everything below with Rust 1.90 (`rustc 1.90.0`), edition 2024, `tracing 0.1.44`, `tracing-subscriber 0.3.23` (features `env-filter` and `json`) and `tokio 1.54.1`, the versions locked in the demo's `Cargo.lock`. I re-ran every demo for this version of the post. Outputs are real, with colors turned off using `NO_COLOR=1`. Timestamps and the order of lines between concurrent tasks change from run to run; the outputs that show them are copied from my first run, and when I re-ran them the content was the same.

## Why plain logs are not enough

Here is the smallest version of the problem. Three tasks run at the same time, and each prints three lines with `println!`:

```rust
async fn handle(order_id: u32) {
    println!("start");
    sleep(Duration::from_millis(10 * order_id as u64)).await;
    println!("charging card");
    sleep(Duration::from_millis(10)).await;
    println!("done");
}
```

I ran it and got:

```text
start
start
start
charging card
charging card
charging card
done
done
done
```

Which `done` belongs to which order? You cannot tell. The three tasks hand control to each other at every `.await`, so their lines are woven together, and with real work in them the order changes from run to run. You could add an id to the start of every line by hand, but it is enough to forget it once, in one place, and that is the line you will need in the middle of the night.

The fix is to attach the id once, to a whole stretch of work, and let every line inside it carry the id by itself. That is exactly what a span does.

## Events and spans

`tracing` has two basic ideas:

- An **event** is a single point in time. It is what you used to call a log line: `info!`, `warn!`, `debug!`.
- A {{< term "tracing-span" "span" >}} is a stretch of time with a name and fields. Every event that happens inside it carries the span's fields automatically. Think of a stamp on a folder: whatever you put into the folder is stamped too.

Both can have **fields**: named values such as `order_id=42` that stay separate from the message text. This is what "structured" means here. A tool can later find all lines with `order_id=42` without parsing a sentence.

First, events with fields:

```rust
let order = Order { id: 42, total: 19.5 };   // derives Debug
let user = "roham";
info!(order_id = order.id, "created");
info!(%user, ?order, "details");
debug!(step = "validate", "checking stock");
warn!(retry_in = ?Duration::from_millis(250), "payment slow");
```

`order_id = order.id` records a field with an explicit name. `%user` records the variable `user` using its `Display` implementation, and `?order` records `order` using `Debug`. The text in quotes is the message.

These macros only announce that something happened. Nothing is printed until the program installs a {{< term "tracing-subscriber" "subscriber" >}}, the part that receives events and decides what to do with them. The simplest one prints to the console, and we give it a filter that reads the `RUST_LOG` environment variable:

```rust
tracing_subscriber::fmt()
    .with_env_filter(EnvFilter::from_default_env())
    .init();
```

Events have levels, from most to least important: `error`, `warn`, `info`, `debug`, `trace`. The filter keeps what you ask for. `RUST_LOG=info` means "`info` and everything more important"; `RUST_LOG=info,basic=debug` means "`info` in general, but `debug` for the crate named `basic`" (our demo binary).

I ran the same program three ways. With no `RUST_LOG`, the filter is empty and nothing was printed at all. With `RUST_LOG=info`, only the `info` and `warn` lines appeared. With `RUST_LOG=info,basic=debug`:

```text
2026-10-23T21:26:02.055509Z  INFO basic: created order_id=42
2026-10-23T21:26:02.055634Z  INFO basic: details user=roham order=Order { id: 42, total: 19.5 }
2026-10-23T21:26:02.055669Z DEBUG basic: checking stock step="validate"
2026-10-23T21:26:02.055694Z  WARN basic: payment slow retry_in=250ms
2026-10-23T21:26:02.055723Z DEBUG basic::other: inside module other
2026-10-23T21:26:02.055744Z  INFO basic::other: module other done
```

Each line has a timestamp, the level, the module that logged it (`basic` or `basic::other`, a function in a module of the demo), the message and then the fields. Notice `user=roham` (from `%user`) and `order=Order { id: 42, total: 19.5 }` (from `?order`). The demo also has a `trace!("very noisy")` line, and it never appears: trace is below debug, so even this setting hides it. The filter is read when the program starts, so you change the verbosity by changing the variable, without recompiling.

## Spans on async functions

Events alone do not solve our opening problem. Now we need the span. The easiest way is the `#[instrument]` attribute: it wraps the whole function in a span named after the function, and it records the arguments as fields. Here are two functions of the demo, `handle` and the `charge` it calls (the body of `handle` is shortened to a comment):

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

The options on `charge` do four things:

- `skip(token)` keeps the argument `token` out of the fields. By default every argument is recorded with `Debug`, and a secret does not belong in a log.
- `fields(user = "roham")` adds an extra field.
- `amount_cents = field::Empty` reserves a field with no value yet. A few lines later `Span::current().record(...)` fills it in, which is useful when the value is only known midway.
- `err` means "if this function returns `Err`, log it as an `ERROR` event".

The demo runs three `handle` calls at the same time with a `JoinSet`, and order 3 fails with `card declined`. Output (timestamps cut):

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

Look at the front of each line. `handle{order_id=1}` is the span, and the fields are inside the braces. `handle{order_id=1}:charge{...}` means "the `charge` span, running inside the `handle` span of order 1". The lines are still interleaved, order 3 starts before order 1, but now each line tells you whose it is. The last two lines tell the whole story of the failed order: the `ERROR` came from `charge` (thanks to `err`), and `handle` then logged `order failed`.

This is the main payoff. The span follows its task across every `.await`, even when the runtime moves the work between threads, so you never pass an id around by hand.

## JSON output

A console is for you. A log pipeline wants machines to read the lines. Replace `.init()` with `.json().init()` and every event becomes one JSON object. This is the `ERROR` line from above:

```text
{"timestamp":"2026-10-23T21:25:56.264438Z","level":"ERROR","fields":{"error":"card declined"},"span":{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"},"spans":[{"order_id":3,"name":"handle"},{"amount_cents":1003,"order_id":3,"user":"roham","name":"charge"}]}
```

`fields` holds the event's own fields, `span` is the innermost span, and `spans` is the whole chain from outside to inside. A log tool can now filter by `order_id` without any text parsing.

## The tokio::spawn trap

Spans follow a task, but `tokio::spawn` creates a new task. A spawned task is a fresh top-level one, so it does not inherit the span of the code that spawned it. Here is a request that spawns a background audit:

```rust
let span = info_span!("request", request_id = "req-7");
async {
    info!("handling");
    tokio::spawn(background_audit()).await.unwrap();   // lost context
    info!("responded");
}.instrument(span).await;
```

(`.instrument(span)` runs the whole async block inside the span. It comes from the `Instrument` trait.) Output:

```text
INFO request{request_id="req-7"}: handling
INFO audit written
INFO request{request_id="req-7"}: responded
```

The line `audit written` has no request id. If that audit fails at night, you cannot tell which request it came from. The fix is to hand the current span to the spawned future yourself, with the same `.instrument(...)`:

```rust
tokio::spawn(background_audit().instrument(tracing::Span::current()))
```

```text
INFO request{request_id="req-7"}: handling
INFO request{request_id="req-7"}: audit written
INFO request{request_id="req-7"}: responded
```

Now all three lines carry `request_id="req-7"`.

## Span timing

A span knows when it opened and closed, so it can also tell you how long the work took. `.with_span_events(FmtSpan::CLOSE)` makes the subscriber print one extra line when a span closes. The demo function sleeps for 50 ms and then spins the CPU for 20 ms. The load average on this machine was about 3.8 when I re-ran it, so treat the numbers as rough. This is the line from my first run (load about 3):

```text
INFO work: close time.busy=20.1ms time.idle=52.9ms
```

`busy` is the time the future was actually being polled, that is, running code: our 20 ms spin. `idle` is the time it spent waiting between polls: our 50 ms sleep, plus a little timer slack. In the re-run, `busy` was again `20.1ms` and `idle` was a bit higher, `58.2ms`, which fits a loaded machine.

## Beyond the console

Sending spans to Jaeger or any OpenTelemetry backend is done by adding one more layer, `tracing-opentelemetry`, to the same subscriber. I only mention it and did not run it.

Compared with Go: `log/slog` gives structured key-value logs, and `With` attaches fields to a logger, but it has no span concept. To correlate lines across goroutines you pass a logger or a context yourself. In `tracing`, the span carries that information.

## tracing traps in async code

- **`tokio::spawn` loses the span.** The spawned task starts with no parent span, so its lines have no ids. Use `.instrument(Span::current())`, as above.
- **`#[instrument]` records every argument with `Debug` by default.** That can leak a token or print a huge buffer on every call. Use `skip` for secrets and large values.
- **Do not hold a `Span::enter()` guard across an `.await`.** The guard marks the span as active on the current thread. When the task is suspended and another task runs on that thread, the span can be attributed to the wrong work. Use `#[instrument]` or `.instrument(span)`, which enter and leave the span at every poll.
- **Without `RUST_LOG` (or a default directive), `EnvFilter` prints nothing.** That looks like a bug in your logging, but it is the filter doing what it was told.
- **Use `FmtSpan::CLOSE` timing as a hint, not a benchmark.** It measures one run on a possibly busy machine.

## Exercise

Add a `request_id` field to a span around your own handler, spawn a background task from it, and check that its lines carry the id. Then switch to JSON and filter the output by that id.

## What's next

*The type-state pattern and API design in Rust* moves one step before any log line: encoding the valid states in types so wrong usage does not compile.
