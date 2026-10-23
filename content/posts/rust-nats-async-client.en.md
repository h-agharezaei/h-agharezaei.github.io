+++
date = '2027-02-02T10:00:00+03:30'
draft = false
title = 'An async NATS JetStream client in Rust'
description = 'A JetStream publisher and pull-consumer worker in Rust with async-nats and tokio: PubAck, dedup, Nak, Term, MaxDeliver, graceful shutdown, and Go interop.'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "nats", "jetstream", "async", "tokio"]
cover = { image = "/images/covers/rust-nats-async-client.png", alt = "An async NATS JetStream client in Rust", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/rust-thiserror-anyhow/) we used typed errors with `thiserror` and `anyhow` at the application level. Now I put them to work on something I already know from Go: a JetStream publisher and a worker with retry and a maximum number of deliveries. The Go versions are in [the first JetStream post](/posts/nats-jetstream-go/) and [the retry and dead-letter post](/posts/nats-jetstream-retry-dlq/). This is the Rust counterpart, built on `async-nats` and the Tokio setup from [the async post](/posts/rust-async-tokio/). The best part comes at the end: the Rust worker consumes messages published by a Go program.

> I ran everything below with Rust 1.90, `async-nats` 0.50.0, `tokio` 1.54.1, and an embedded nats-server 2.15.1 started from a tiny Go program as a separate process. The machine was heavily loaded (load average around 11), so I show no timing claims.

## Connecting and creating the stream

```rust
async fn connect() -> Result<async_nats::Client> {
    ConnectOptions::new()
        .name("rust-demo")
        .retry_on_initial_connect()
        .max_reconnects(None)
        .connection_timeout(Duration::from_secs(5))
        .connect(URL)
        .await
        .context("connecting to NATS")
}
```

`retry_on_initial_connect` makes the client keep trying even if the server is not up yet. I tested it: I started the worker with no server running, then started the server a few seconds later, and the worker printed `worker: ready` on its own. `max_reconnects(None)` means unlimited reconnects later.

The stream is created idempotently, like `AddStream` in Go but safe to call from every process:

```rust
let js = jetstream::new(connect().await?);
js.get_or_create_stream(jetstream::stream::Config {
    name: "ORDERS".into(),
    subjects: vec!["orders.>".into()],
    ..Default::default()
}).await?;
```

## Publishing: why two awaits

```rust
let mut headers = HeaderMap::new();
headers.insert("Nats-Msg-Id", format!("rust-{i}").as_str());
let ack = js
    .publish_with_headers("orders.created", headers, body.into())
    .await?   // 1st await: send the request
    .await?;  // 2nd await: wait for the server's PubAck
```

The first `await` sends the message and returns a `PublishAckFuture`. The second waits for the server's **PubAck**, the proof that the message is stored. Splitting them lets you publish many messages and collect the acks later, but if you forget the second await you have not confirmed anything. I publish four messages, then the first id again:

```
rust pub: id=rust-0 ok          seq=1 dup=false
rust pub: id=rust-1 flaky       seq=2 dup=false
rust pub: id=rust-2 poison      seq=3 dup=false
rust pub: id=rust-3 always-fail seq=4 dup=false
rust pub: id=rust-0 again       seq=1 dup=true
```

The `Nats-Msg-Id` header is what the server uses for deduplication: the repeat was not stored again, and the ack says `duplicate` with the original sequence.

## The consumer and the processing loop

```rust
let consumer = stream.get_or_create_consumer("rust-worker", pull::Config {
    durable_name: Some("rust-worker".into()),
    ack_policy: AckPolicy::Explicit,
    ack_wait: Duration::from_secs(5),
    max_deliver: 4,
    backoff: vec![Duration::from_secs(3), Duration::from_secs(5)],
    ..Default::default()
}).await?;
let mut messages = consumer.messages().await?;
```

`messages()` gives an async stream, so the loop is `messages.next().await` from `futures::StreamExt`. Failures are a small `thiserror` enum, `Transient` or `Poison`, and each maps to a different acknowledgement:

```rust
let action = match process(&payload, delivered).await {
    Ok(()) => { msg.ack().await?; "ack" }
    Err(ProcessError::Poison(_)) => { msg.ack_with(AckKind::Term).await?; "term" }
    Err(e @ ProcessError::Transient(_)) => {
        msg.ack_with(AckKind::Nak(Some(Duration::from_millis(500)))).await?;
        "nak"
    }
};
```

(In the real file the errors from `ack` go through `anyhow!`, because they are boxed errors, and `delivered` comes from `msg.info()?.delivered`.) The payload decides the outcome: `ok` succeeds, `flaky` fails until the third delivery, `poison` can never succeed, and `always-fail` fails every time. The real output:

```
worker: ready
 seq=1 delivered=1 id=rust-0  body=ok          -> ack
 seq=2 delivered=1 id=rust-1  body=flaky       -> nak(500ms): temporary failure on attempt 1
 seq=3 delivered=1 id=rust-2  body=poison      -> term
 seq=4 delivered=1 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 1
 seq=2 delivered=2 id=rust-1  body=flaky       -> nak(500ms): temporary failure on attempt 2
 seq=4 delivered=2 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 2
 seq=2 delivered=3 id=rust-1  body=flaky       -> ack
 seq=4 delivered=3 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 3
 seq=4 delivered=4 id=rust-3  body=always-fail -> nak(500ms): temporary failure on attempt 4
```

(I removed the time column.) `Term` ended the poison message after one delivery, `flaky` succeeded on delivery 3, and `always-fail` stopped at delivery 4 because of `max_deliver: 4`. As in the Go post, it stays in the stream; it is just not delivered to this consumer again.

## Graceful shutdown

```rust
let mut sigterm = signal(SignalKind::terminate())?;
let mut sigint = signal(SignalKind::interrupt())?;
let shutdown = async { tokio::select! { _ = sigint.recv() => {}, _ = sigterm.recv() => {} } };
tokio::pin!(shutdown);
loop {
    let msg = tokio::select! {
        _ = &mut shutdown => break,
        next = messages.next() => match next { Some(m) => m?, None => break },
    };
    // process and ack msg ...
}
```

`select!` only races the shutdown signal against the *next message*. Once a message is taken, its processing runs to the end before the loop checks again, so the in-flight message is finished and acked. I published eight messages and sent `SIGTERM` during processing:

```
 seq=16 delivered=1 id=go-20 ... -> ack
 seq=17 delivered=1 id=go-21 ... -> ack
 seq=18 delivered=1 id=go-22 ... -> ack
 seq=19 delivered=1 id=go-23 ... -> ack
worker: shutdown requested
worker: bye
```

The other four were already fetched but not acked. After a restart they came back with `delivered=2` (seq 21, 22, 23, then 20): the server counts a delivery when it hands the message out, not when you process it.

## Interop: Go publishes, Rust consumes

The Go side is a short program using `nats.go` v1.54.0 that sets the same header and publishes to the same subject. Its output, and what the Rust worker printed for it:

```
go pub: seq=5 dup=false
go pub: seq=6 dup=false
```
```
 seq=5 delivered=1 id=go-1 body={"id":101,"from":"go"} -> ack
 seq=6 delivered=1 id=go-2 body={"id":102,"from":"go"} -> ack
```

Nothing special was needed: the stream, headers and acks are protocol-level, so both languages see the same thing, including the `go-1` id in a Rust `HeaderMap`.

## Compared with nats.go

Facts I am sure of: `nats.go` `js.Publish` blocks and returns the `PubAck`, while it also has `PublishAsync`; in `async-nats` that split is visible in the types (the double await). The Go post used the older `JetStream()` API, and `nats.go` also ships a newer `jetstream` package with consumers much like the Rust ones. The real difference is in handling: Rust makes me decide, in types, which errors are `Transient` and which are `Poison`.

## A few things to watch

- Delivery timers start at delivery, not when you begin processing. In my first run the first backoff was 300 ms and handling took 300 ms, and messages I had already acked were delivered again. Keep the first backoff and `ack_wait` well above queue wait plus handling time.
- Forgetting the second `await` on publish means no confirmation.
- A plain `Nak(None)` can retry in a tight loop; pass a delay.
- `max_deliver` should be larger than the length of `backoff`.
- Unacked buffered messages count as delivered; do not treat `delivered` as "attempts that ran".

## Exercise

1. On the last allowed delivery (`delivered == 4`), publish the payload to `orders.dead` before giving up.
2. Compute the `Nak` delay from `delivered` instead of using a constant.

## What's next

Next: trait objects and `dyn` in Rust.
