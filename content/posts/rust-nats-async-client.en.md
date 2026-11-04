+++
date = '2027-02-02T10:00:00+03:30'
draft = false
title = 'An async NATS JetStream client in Rust'
description = 'A JetStream publisher and pull-consumer worker in Rust with async-nats and tokio: PubAck, dedup, Nak, Term, MaxDeliver, graceful shutdown, and Go interop.'
contentType = 'tutorial'
categories = ["Rust"]
series = ["Rust"]
tags = ["rust", "nats", "jetstream", "async", "tokio"]
cover = { image = "/images/covers/rust-nats-async-client.png", alt = "An async NATS JetStream client in Rust", hiddenInSingle = true }
+++

You publish an event, "order created", and your function returns. Was the event really stored, or did it only leave your network card? And on the other side, a worker reads the event and crashes halfway through processing it. Is the event lost, or will someone try again? A message system has to answer both questions, and the answers are the whole reason to use a persistent one instead of a plain function call.

In this post we build both sides in Rust: a publisher that knows its message was stored, and a worker that retries a failing message a limited number of times. The typed errors from [Errors in real apps: thiserror and anyhow](/posts/rust-thiserror-anyhow/) have a real job here: they decide whether a failed message is tried again or dropped. It is the Rust twin of [the first JetStream post in Go](/posts/nats-jetstream-go/) and [the retry and dead-letter post](/posts/nats-jetstream-retry-dlq/), built on the async client `async-nats` and the Tokio setup from [async/await and Tokio in Rust](/posts/rust-async-tokio/). At the end the Rust worker consumes messages published by a Go program.

> I ran everything below with Rust 1.90, `async-nats` 0.50.0, `tokio` 1.54.1 and an embedded nats-server 2.15.1, started from a tiny Go program (using `nats.go` 1.54.0) as a separate process on a random local port. I re-ran every demo for this version of the post. The outputs below are from that run, with the leading time column removed. I make no timing claims.

## Four words you need

Here is just enough about NATS to read the rest. NATS is a message server. Programs connect to it and exchange messages, and every message is sent to a **subject**, a dotted name such as `orders.created`. Plain NATS delivers a message to whoever is listening at that moment and forgets it, which is fast but not durable.

{{< term "jetstream" "JetStream" >}} is the part of NATS that adds storage, and it brings three more words:

- A **stream** is a named log that stores every message published to certain subjects. Ours is called `ORDERS` and stores `orders.>` (the `>` means "any subjects below `orders.`").
- A **consumer** is a named reader of a stream. It remembers how far it has read, so a worker that restarts continues where it stopped. Ours is a {{< term "durable-consumer" "durable" >}} one (it keeps its position even when the program is gone) and a {{< term "pull-consumer" "pull" >}} one (the worker asks for messages instead of the server pushing them).
- An **ack** (acknowledgement) is the worker's answer after processing a message. A message that is not acked is delivered again. There are also `nak` ("failed, try again", optionally after a delay) and `term` ("never send this again").

Now the code.

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

`retry_on_initial_connect` makes the client keep trying even if the server is not up yet, and `max_reconnects(None)` means unlimited reconnects later. I tested the first: I started the worker with no server running, started the server a few seconds later, and the worker printed `worker: ready` on its own, with no restart.

The stream is created with `get_or_create_stream`, which is idempotent: it creates the stream if it is missing and returns it if it exists. This is like `AddStream` in Go, but safe to call from every process, so the publisher and the worker both do it and it does not matter which starts first:

```rust
let js = jetstream::new(connect().await?);
js.get_or_create_stream(jetstream::stream::Config {
    name: "ORDERS".into(),
    subjects: vec!["orders.>".into()],
    ..Default::default()
}).await?;
```

## Publishing: why two awaits

Now the first question of the post: how does the publisher know the message was stored?

```rust
let mut headers = HeaderMap::new();
headers.insert("Nats-Msg-Id", format!("rust-{i}").as_str());
let ack = js
    .publish_with_headers("orders.created", headers, body.into())
    .await?   // 1st await: send the request
    .await?;  // 2nd await: wait for the server's PubAck
```

The first `await` sends the message and returns a future for the answer (a `PublishAckFuture`). The second `await` waits for the server's **PubAck**, its "I stored it" reply. Only after that do you know the message is safe. Splitting the two lets you publish many messages and collect the acks later, which is faster; if you forget the second `await`, you have no confirmation at all.

The `Nats-Msg-Id` header deserves a note. It is an id that *we* choose, and the server uses it to drop duplicates: if the same id arrives again (within the stream's deduplication window, which is two minutes by default according to the NATS docs), the message is not stored a second time. The demo publishes four messages with the bodies `ok`, `flaky`, `poison` and `always-fail`, and then sends the id `rust-0` again:

```text
rust pub: id=rust-0 ok          seq=1 dup=false
rust pub: id=rust-1 flaky       seq=2 dup=false
rust pub: id=rust-2 poison      seq=3 dup=false
rust pub: id=rust-3 always-fail seq=4 dup=false
rust pub: id=rust-0 again       seq=1 dup=true
```

`seq` is the position of the message in the stream. The first four are new messages, numbered 1 to 4. The fifth is the repeat: the server did not store it again, and its ack says `dup=true` and gives back the original sequence, 1. A publisher that retries after a timeout can therefore never create two orders.

## The consumer and the processing loop

Now the second question: what happens to a message that fails? The consumer is configured with the rules:

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

- `durable_name` gives the consumer its identity, so its position survives a restart.
- `AckPolicy::Explicit` means every message must be acknowledged one by one by our code.
- {{< term "ack-wait" "ack_wait" >}} is how long the server waits for an ack before it delivers the message again. If the worker crashes, this is what brings the message back.
- `max_deliver: 4` is the cap: after four deliveries the server stops sending the message to this consumer. According to the NATS docs `max_deliver` should be larger than the number of entries in `backoff`; here 4 is larger than 2.
- `backoff` is a list of waits between redeliveries (3 s, then 5 s). According to the NATS docs it takes the place of `ack_wait` for redelivery timing.

`messages()` gives an async stream (here "stream" means a sequence of values that arrive over time, not a JetStream stream), so the loop is `messages.next().await`, using `StreamExt` from the `futures` crate. For each message the worker runs a pretend piece of business logic and then answers with an ack, `nak` or `term`. Failures are a small `thiserror` enum with two cases, `Transient` ("try again may work") and `Poison` ("this message can never succeed", a {{< term "poison-message" "poison message" >}}), and each case maps to a different acknowledgement:

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

(The snippet is shortened. In the real file the errors from `ack` are turned into `anyhow` errors with `anyhow!`, because they are boxed errors, and `delivered` comes from `msg.info()?.delivered`.)

The payload decides what happens: `ok` succeeds, `flaky` fails until its third delivery, `poison` can never succeed, and `always-fail` fails every time. The worker's output for our four messages (the number after `delivered=` is how many times the server has handed that message out):

```text
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

Read it by message:

- `ok` (seq 1) is acked on the first delivery and never seen again.
- `flaky` (seq 2) fails twice with a `nak`, so the server redelivers it after the 500 ms delay. On delivery 3 it succeeds and is acked.
- `poison` (seq 3) gets `term` on its first delivery. The server will never send it again, which is right: trying a message that cannot succeed only wastes time.
- `always-fail` (seq 4) is naked on deliveries 1, 2, 3 and 4. After delivery 4 it does not come back, because of `max_deliver: 4`. As in the Go post, it stays in the stream; it is just not delivered to this consumer any more. A real system would send it to a dead-letter place before giving up (see the exercise).

## Graceful shutdown

A deploy sends `SIGTERM` while the worker is in the middle of a message. We want that message finished and acked, not abandoned:

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

`select!` waits for whichever happens first, and it only races the shutdown signal against the *next message*. Once a message is taken, its processing runs to the end before the loop checks again, so the message in hand is finished and acked. This is {{< term "graceful-shutdown" "graceful shutdown" >}} for a worker. To test it, I published eight messages from Go and sent `SIGTERM` to the worker while it was processing them:

```text
 seq=7 delivered=1 id=go-20 ... -> ack
 seq=8 delivered=1 id=go-21 ... -> ack
 seq=9 delivered=1 id=go-22 ... -> ack
 seq=10 delivered=1 id=go-23 ... -> ack
worker: shutdown requested
worker: bye
```

Four messages were processed and acked, then the worker stopped cleanly. The other four had already been handed to the client but not processed, so they were not acked. After I started the worker again they came back:

```text
worker: ready
 seq=11 delivered=2 id=go-24 ... -> ack
 seq=12 delivered=2 id=go-25 ... -> ack
 seq=13 delivered=2 id=go-26 ... -> ack
 seq=14 delivered=2 id=go-27 ... -> ack
```

Nothing was lost. Notice `delivered=2` on messages that were never processed before: the server counts a delivery when it *hands the message out*, not when your code processes it. We come back to that in the traps.

## Interop: Go publishes, Rust consumes

The Go side is a short program that sets the same header and publishes to the same subject with `nats.go`. Here is its output, and then what the running Rust worker printed for those two messages:

```text
go pub: seq=5 dup=false
go pub: seq=6 dup=false
```

```text
 seq=5 delivered=1 id=go-1 body={"id":101,"from":"go"} -> ack
 seq=6 delivered=1 id=go-2 body={"id":102,"from":"go"} -> ack
```

Nothing special was needed. The stream, the headers and the acks are part of the NATS protocol, not of a language, so both sides see the same thing, including the id `go-1` that Go put in a header and Rust read from a `HeaderMap`.

## Compared with nats.go

Only facts I am sure of. In `nats.go`, `js.Publish` blocks until it has the `PubAck`, and the library also has `PublishAsync`; in `async-nats` the same split is visible in the types, as the double `await`. The Go post used the older `JetStream()` API, and `nats.go` also ships a newer `jetstream` package with consumers much like the Rust ones. The real difference is not the API but the handling of errors: Rust made me decide, in types, which errors are `Transient` and which are `Poison`.

## Retry and redelivery traps

- **Delivery timers start at delivery, not when you begin processing.** In my original run, my first backoff was 300 ms and handling took 300 ms, and messages I had already acked were delivered again. Keep the first backoff and `ack_wait` well above the time a message waits in the queue plus the handling time.
- **Forgetting the second `await` on publish means you have no confirmation** that the message was stored.
- **A plain `Nak(None)` can retry in a tight loop.** Pass a delay, as the demo does.
- **`max_deliver` should be larger than the length of `backoff`,** as mentioned above.
- **Buffered, unacked messages count as delivered.** As we saw after the shutdown, do not read `delivered` as "attempts that actually ran".

## Exercise

1. On the last allowed delivery (`delivered == 4`), publish the payload to `orders.dead` before giving up.
2. Compute the `Nak` delay from `delivered` instead of using a constant.

## What's next

The worker chose between `Transient` and `Poison` with a `match` on an enum. The next post, *Trait objects and dyn in Rust*, shows how Rust gets the runtime polymorphism that Go interfaces give for free.
