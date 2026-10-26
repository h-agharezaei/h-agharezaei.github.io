+++
date = '2027-03-08T10:00:00+03:30'
draft = false
title = 'Capstone: an event pipeline with Go, Rust and NATS'
description = 'A Go and Rust event pipeline on NATS: Postgres, the outbox pattern, JetStream, a Rust worker and a KV read model, then kill pieces to check correctness.'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "nats", "jetstream", "outbox", "capstone", "postgres"]
cover = { image = "/images/covers/go-rust-event-pipeline-capstone.png", alt = "Capstone: an event pipeline with Go, Rust and NATS", hiddenInSingle = true }
+++

[The previous post](/posts/go-calls-rust-ffi/) put Rust inside a Go process. This last post of the series puts the pieces from the whole year side by side: Go services for the edges, a Rust worker for the business rule, and NATS in the middle. Nothing here is new technology. The point is how the parts fit, and what happens when one of them dies. I run it with one `run.sh`, then break it on purpose.

> Go 1.26, Rust 1.90, Postgres 18.3 (embedded launcher), nats-server 2.15 embedded, macOS arm64. Everything below was run locally. It is a demo: one node, no auth, no TLS. [JetStream in production](/posts/nats-jetstream-production/) lists what a real deployment needs.

## The shape

```text
 curl POST /orders
        |
   [Go api] --one tx--> Postgres: orders + outbox
                                    |
                       [Go relay] polls outbox
                                    | Nats-Msg-Id = outbox-<id>
                                    v
                         stream ORDERS (orders.created)
                                    |
                    [Rust pricer] pull consumer, validates + prices
                                    | Nats-Msg-Id = priced-<order>
                                    v
                 stream RESULTS (results.priced.<order>)
                                    |
                      [Go projector] consumer
                                    v
                     KV bucket ORDER_STATUS
                                    ^
 curl GET /orders/{id}/status ---[Go api]
```

Pieces I reuse: the transaction and relay from [the outbox post](/posts/go-outbox-pattern-nats/) with [pgx](/posts/go-postgres-pgx-sqlc/), the async consumer from [the async NATS client in Rust](/posts/rust-nats-async-client/), the bucket from [KV and Object Store](/posts/nats-kv-object-store/), and signal handling as in [graceful shutdown](/posts/go-graceful-shutdown-workers/). The `infra` command starts Postgres and NATS on fixed data directories, with both streams and the bucket on **file storage**.

## Write side: one transaction

The API never talks to NATS. It writes the order and the event together, so either both exist or neither does:

```go
err := pgx.BeginFunc(ctx, pool, func(tx pgx.Tx) error {
	if _, err := tx.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ($1,$2,$3)`,
		in.ID, in.Customer, in.Cents); err != nil {
		return err
	}
	payload, _ := json.Marshal(map[string]any{"order_id": in.ID, "cents": in.Cents})
	_, err := tx.Exec(ctx, `INSERT INTO outbox (payload) VALUES ($1)`, payload)
	return err
})
```

The relay selects unpublished rows with `FOR UPDATE SKIP LOCKED`, publishes each with `Nats-Msg-Id` set to `outbox-<id>`, and only then runs `UPDATE outbox SET published_at`. That gap is where it can die.

## The Rust worker

The business rule is a pure function, so it is easy to test and has nothing to do with NATS:

```rust
fn price(o: &Order) -> Priced {
    if o.cents <= 0 || o.cents > 1_000_000 {
        return Priced { order_id: o.order_id.clone(), status: "rejected", total_cents: 0, checksum: String::new() };
    }
    let total = o.cents + (o.cents * 9 + 50) / 100; // 9% tax, rounded
    let checksum = format!("{:08x}", fnv1a(format!("{}:{}", o.order_id, total).as_bytes()));
    Priced { order_id: o.order_id.clone(), status: "priced", total_cents: total, checksum }
}
```

Around it, the loop does three things: skip orders that already produced a result, publish the result with its own `Nats-Msg-Id`, and ack only after the publish was confirmed:

```rust
let subject = format!("results.priced.{}", order.order_id);
if results.get_last_raw_message_by_subject(&subject).await.is_ok() {
    msg.ack().await.map_err(|e| anyhow!("{e}"))?; // already processed
    continue;
}
// ... price, publish_with_headers(subject, Nats-Msg-Id: priced-<id>).await?.await?;
msg.ack().await.map_err(|e| anyhow!("{e}"))?;
```

The subject contains the order id, so "has this order a result?" is a lookup in the stream itself, not in worker memory. This is the idea from [idempotency in JetStream](/posts/nats-jetstream-idempotency/). The projector is the last hop: it does `kv.Put(orderID, result)` for each result and acks. Putting the same value twice is harmless.

## Happy path

```text
$ curl -X POST localhost:18080/orders -d '{"id":"o-1","customer":"ali","cents":2500}'
{"id":"o-1","accepted":true}
$ curl localhost:18080/orders/o-1/status
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
$ curl -X POST localhost:18080/orders -d '{"id":"o-2","customer":"sara","cents":5000000}'
$ curl localhost:18080/orders/o-2/status
{"order_id":"o-2","status":"rejected","total_cents":0,"checksum":""}
```

2500 plus 9% is 2725. Posting `o-1` again gets a 409 from Postgres (`duplicate key`), and no outbox row is created because the transaction rolled back. Then `report` counts everything:

```text
report: orders=2 outbox=2 (unpublished=0) ORDERS msgs=2 RESULTS msgs=2 KV keys=2
```

## Kill the worker mid-message

With `STALL=before` the worker sleeps after receiving `o-3` and before publishing. I `kill -9` it there:

```text
killed worker2 (SIGKILL)
{"id":"o-3","status":"unknown"}
(restarted worker; redelivery arrives once the 5 s ack_wait expires)
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
worker: o-3 delivered=2 -> priced total=1090
```

The message was redelivered (`delivered=2`) and processed once. The harder case is `STALL=after`: the result for `o-4` is already published when the worker dies, so the ack never happens:

```text
worker: o-4 delivered=1 -> priced total=1089
worker: stalling after publish, kill me now
--- restarted worker ---
worker: o-4 delivered=2 already processed, skipping
report: orders=4 outbox=4 (unpublished=0) ORDERS msgs=4 RESULTS msgs=4 KV keys=4
```

Four orders, four results. Redelivery happened, but the effect was applied once.

## Kill the relay between publish and mark

`CRASH_AFTER_PUBLISH=1` makes the relay exit right after the publish succeeds. Postgres still shows the row as unpublished, while the stream already holds the event:

```text
relay: outbox id=5 published seq=5 duplicate=false
relay: CRASH between publish and mark-published
report: orders=5 outbox=5 (unpublished=1) ORDERS msgs=5 ...
--- normal relay started ---
relay: outbox id=5 published seq=5 duplicate=true
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

The retry got `duplicate=true` with the same sequence 5. The stream dropped it by `Nats-Msg-Id`, so the worker never saw a second copy.

## Restart everything

I stopped the API, relay, projector and worker, then stopped `infra` itself and started it again on the same data directory. Postgres rows and the JetStream files were still there:

```text
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
{"order_id":"o-5","status":"priced","total_cents":4578,"checksum":"7d5392b2"}
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

A new `o-6` then flowed through all stages as usual.

## A few things to watch

- The "already processed" check is check-then-act. With several workers on one order, two could both pass it. The 5-minute dedup window on the `Nats-Msg-Id` covers that, but a real fix is a unique key in your own store.
- Everything is at-least-once; correctness comes from idempotent steps, not from "exactly once".
- `ack_wait` is why recovery took about five seconds. Tune it against your slowest message.
- I did not measure speed or throughput here, and the demo has no metrics. Add the ones from [observability for JetStream](/posts/nats-jetstream-observability/) first.
- NATS between services buys durability and redelivery. If you need a synchronous answer instead, use gRPC as in [Go and Rust over gRPC](/posts/go-rust-grpc-interop/).

## What's next

Next on the calendar: Docker, CI and releasing a Rust service.
