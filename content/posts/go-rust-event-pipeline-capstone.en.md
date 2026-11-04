+++
date = '2027-03-08T10:00:00+03:30'
draft = false
title = 'Capstone: an event pipeline with Go, Rust and NATS'
description = 'A Go and Rust event pipeline on NATS: Postgres, the outbox pattern, JetStream, a Rust worker and a KV read model, then kill pieces to check correctness.'
contentType = 'engineering'
categories = ["Go", "Rust"]
series = ["Go + Rust"]
tags = ["go", "rust", "nats", "jetstream", "outbox", "capstone", "postgres"]
cover = { image = "/images/covers/go-rust-event-pipeline-capstone.png", alt = "Capstone: an event pipeline with Go, Rust and NATS", hiddenInSingle = true }
+++

A customer sends an order. Your system answers "accepted". Right after that, something crashes: the process that saves orders, the one that publishes events, or the worker that calculates the price. Which of these must still be true when everything is running again?

- The accepted order is not lost.
- The price is calculated and applied once, not twice, even if a message is delivered twice.
- The customer can ask "what is the status of my order?" and get a correct answer.

This post is the last of the Go and Rust series, and it is built around that question. Over the year we built the pieces one by one. Here I put them side by side: Go services at the edges, a Rust worker that holds the business rule, and NATS in the middle. Nothing in it is new technology. The point is **how the parts fit together, and what happens when one of them dies.** I start everything with one script, `run.sh`, and then kill pieces on purpose.

The series so far went from [Go and Rust over gRPC](/posts/go-rust-grpc-interop/) (a network call between two languages) to [putting Rust inside a Go process](/posts/go-calls-rust-ffi/) (a library call). The capstone uses neither. It connects the two languages through messages, which is the third common way.

> Everything was re-run with Go 1.27, Rust 1.90, Postgres 18.3 (a launcher that embeds it), nats-server 2.15.1 embedded in a Go program, and macOS arm64. It is a demo: one node, no authentication, no TLS. [JetStream in production](/posts/nats-jetstream-production/) lists what a real deployment needs. The demo hard-codes its ports, so I ran a copy with free ones and write `<port>` below. Timings do not appear in the post.

## The map

There are five programs. Four are Go (one binary with several subcommands; a fifth subcommand, `report`, only counts what is stored) and one is Rust:

| Program | Language | Its one job |
|---|---|---|
| `infra` | Go | Starts Postgres and NATS, and creates the streams and the KV bucket. |
| `api` | Go | Accepts `POST /orders`, serves `GET /orders/{id}/status`. |
| `relay` | Go | Moves events from the Postgres `outbox` table to NATS. |
| `pricer` | Rust | Reads an order event, applies the business rule, publishes a result. |
| `projector` | Go | Reads results and stores the latest status per order in NATS KV. |

And this is how data flows between them:

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

Follow one order down the left side. The API writes it to Postgres. The relay picks it up and publishes an event into the `ORDERS` stream. The Rust pricer reads that event, decides the price, and publishes a result into the `RESULTS` stream. The projector copies the result into a key-value bucket. And the API reads the status from that bucket when the customer asks.

Why so many hops? Because each hop makes one failure survivable, as the next section shows. A **stream** in {{< term "jetstream" "JetStream" >}} (NATS's persistent layer) is a log of messages that is stored on disk; the demo puts both streams and the bucket on **file storage**, so they survive a restart.

The pieces come from earlier posts: the transaction and relay from [the outbox post](/posts/go-outbox-pattern-nats/) with [pgx](/posts/go-postgres-pgx-sqlc/), the async consumer from [the async NATS client in Rust](/posts/rust-nats-async-client/), the bucket from [KV and Object Store](/posts/nats-kv-object-store/), and signal handling as in [graceful shutdown](/posts/go-graceful-shutdown-workers/).

## Three ideas that hold it together

Before the code, three ideas, each in one paragraph:

1. **The outbox.** The API cannot write to Postgres and to NATS in one transaction, because no transaction spans both. So it writes the order *and* an event row into Postgres in one transaction. Later a separate process (the relay) publishes the row. This is the {{< term "outbox-pattern" "outbox pattern" >}}.
2. **At-least-once delivery.** If a consumer does not acknowledge a message in time, JetStream sends it again. That is good: nothing is lost. But the same message can arrive twice. This is {{< term "at-least-once-delivery" "at-least-once delivery" >}}.
3. **Idempotent steps.** Because of the second idea, every step must be safe to repeat. This is {{< term "idempotency" "idempotency" >}}. We do not get "exactly once" from the broker; we build it from steps that give the same result when repeated, with duplicates dropped using a message ID.

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

The relay runs in a loop, in one transaction per batch. It selects unpublished rows with `FOR UPDATE SKIP LOCKED` ({{< term "skip-locked" "skip locked" >}}: rows that another relay holds are skipped, so two relays do not take the same rows). It publishes each row with the message ID `outbox-<id>`, and only then runs `UPDATE outbox SET published_at`. The gap between "published" and "marked as published" is where it can die, and we will test exactly that.

## The Rust worker

The business rule is a pure function: an order goes in, a result comes out. That makes it easy to test, and it has nothing to do with NATS:

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

An order of zero or less, or above 1,000,000 cents, is rejected. Otherwise the worker adds 9% tax rounded to the nearest cent and attaches a small checksum, so we can compare results later.

Around this function, the worker's loop reads messages from a {{< term "pull-consumer" "pull consumer" >}} (the worker asks for messages instead of the server pushing them). For each message it does three things: skip the order if it already has a result, publish the result with its own message ID, and ack only after the publish was confirmed:

```rust
let subject = format!("results.priced.{}", order.order_id);
if results.get_last_raw_message_by_subject(&subject).await.is_ok() {
    msg.ack().await.map_err(|e| anyhow!("{e}"))?; // already processed
    continue;
}
// ... price, publish_with_headers(subject, Nats-Msg-Id: priced-<id>).await?.await?;
msg.ack().await.map_err(|e| anyhow!("{e}"))?;
```

The subject contains the order id, so the question "does this order already have a result?" is a lookup in the stream itself, not in the worker's memory. That matters: a worker that was killed and restarted has no memory, but the stream remembers. This is the idea from [idempotency in JetStream](/posts/nats-jetstream-idempotency/). The consumer's {{< term "ack-wait" "ack wait" >}} is 5 seconds: if the worker does not ack within that time, JetStream delivers the message again.

The projector is the last hop. For each result it does `kv.Put(orderID, result)` and acks. Putting the same value twice changes nothing, so this step is safe to repeat.

## Happy path

First, nothing fails. I post two orders and read their status. The second order is above the limit, so it should be rejected. Then I post `o-1` a second time. (`curl` and the output are as in `run.sh`, with the port removed.)

```text
$ curl -X POST localhost:<port>/orders -d '{"id":"o-1","customer":"ali","cents":2500}'
{"id":"o-1","accepted":true}
$ curl localhost:<port>/orders/o-1/status
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
$ curl -X POST localhost:<port>/orders -d '{"id":"o-2","customer":"sara","cents":5000000}'
$ curl localhost:<port>/orders/o-2/status
{"order_id":"o-2","status":"rejected","total_cents":0,"checksum":""}
```

2500 plus 9% is 2725, as expected. The second order is rejected by the Rust rule. Posting `o-1` again gets an error from Postgres (`duplicate key value violates unique constraint "orders_pkey"`), which the API turns into a 409, and no outbox row is created because the transaction rolled back. Then the `report` command counts everything in Postgres and NATS:

```text
report: orders=2 outbox=2 (unpublished=0) ORDERS msgs=2 RESULTS msgs=2 KV keys=2
```

Two orders, two outbox rows (none waiting), two events, two results and two keys. This line is what we compare against after each failure.

## Kill the worker mid-message

Now the first failure. The worker has a test switch: with `STALL=before` it sleeps after receiving a message and before publishing, so I have a safe moment to kill it. I start such a worker, post `o-3`, and `kill -9` it while it holds the message. Then I ask for the status: nothing is there yet. Then I start a normal worker:

```text
killed worker2 (SIGKILL)
{"id":"o-3","status":"unknown"}
(a normal worker is started; the message is redelivered once the 5 s ack wait expires)
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
```

The worker's own log lines show what it saw:

```text
worker: stalling before publish, kill me now
worker: o-3 delivered=2 -> priced total=1090
```

The message was delivered twice (`delivered=2`): the first time to the worker that died, and the second to the new one. It was processed once. The total, 1090, is 1000 plus 9%. (In the log timestamps of my run, the result for `o-3` appeared about five seconds after the relay had published it, which fits the 5 s ack wait.)

The harder case is `STALL=after`: the worker publishes the result for `o-4` and then dies before acking. Now the result already exists, and the message will still be redelivered. What should the next worker do? It must not publish again:

```text
worker: o-4 delivered=1 -> priced total=1089
worker: stalling after publish, kill me now
--- worker killed, a new worker started ---
worker: o-4 delivered=2 already processed, skipping
report: orders=4 outbox=4 (unpublished=0) ORDERS msgs=4 RESULTS msgs=4 KV keys=4
```

The first worker published and stalled. The new worker received the message a second time (`delivered=2`), found the existing result for `o-4` in the `RESULTS` stream, and skipped it. The report says four orders and four results: the redelivery happened, but the effect was applied once.

## Kill the relay between publish and mark

Now the other side. `CRASH_AFTER_PUBLISH=1` makes the relay exit right after the publish succeeds and before the database update. Postgres still shows the row as unpublished, while NATS already holds the event:

```text
relay: outbox id=5 published seq=5 duplicate=false
relay: CRASH between publish and mark-published
report: orders=5 outbox=5 (unpublished=1) ORDERS msgs=5 ...
--- normal relay started ---
relay: outbox id=5 published seq=5 duplicate=true
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

The `report` in the middle shows the dangerous state: one unpublished row, while the stream already has 5 events. A normal relay starts, sees the row as unpublished, and publishes it again. This time NATS answers `duplicate=true` with the same sequence number 5. The stream recognised the message ID `outbox-5` and dropped the second copy. So the pricer never sees `o-5` twice, and the final report is consistent.

## Restart everything

Last, the whole system. I stopped the API, relay, projector and worker, then stopped `infra` itself and started it again on the same data directory. If the data was only in memory, it would be gone:

```text
{"order_id":"o-1","status":"priced","total_cents":2725,"checksum":"239b2934"}
{"order_id":"o-3","status":"priced","total_cents":1090,"checksum":"d22b576c"}
{"order_id":"o-5","status":"priced","total_cents":4578,"checksum":"7d5392b2"}
report: orders=5 outbox=5 (unpublished=0) ORDERS msgs=5 RESULTS msgs=5 KV keys=5
```

The statuses and counts are the same as before the restart: Postgres kept its rows and JetStream kept its files. A new order `o-6` (100 cents, priced at 109) then flowed through all the stages as usual, and the last report said six of everything.

## Limits of this design

- **The "already processed" check is check-then-act.** With several workers on the same order, two of them could both pass the check before either publishes. The message ID `priced-<order>` and the stream's duplicate window (5 minutes here) cover that for a while, but a real fix is a unique key in your own store.
- **Everything is at-least-once.** Correctness comes from idempotent steps, not from an "exactly once" switch.
- **`ack_wait` sets the recovery time.** Recovery after a worker crash waits for it, so tune it against your slowest message: too short and slow messages are delivered twice, too long and recovery is slow.
- **This demo measures nothing about speed.** There are no metrics and no throughput numbers. Add the ones from [observability for JetStream](/posts/nats-jetstream-observability/) before trusting it with real load.
- **Messages are not answers.** NATS between services buys durability and redelivery, but the caller of `POST /orders` only learns "accepted". If you need a synchronous answer, use gRPC as in [Go and Rust over gRPC](/posts/go-rust-grpc-interop/).

## What's next

This post closes the Go and Rust series. Next on the calendar is "Docker, CI and releasing a Rust service", which takes a Rust service beyond a local run like this one.
