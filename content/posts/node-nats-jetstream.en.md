+++
date = '2027-02-27T10:00:00+03:30'
draft = false
title = 'NATS JetStream from Node.js'
description = 'NATS JetStream from Node.js: publish with msgID, durable pull consumers, ack, nak, term, backoff, graceful drain and Go interop, all run for real.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "nats", "jetstream", "messaging", "graceful-shutdown"]
cover = { image = "/images/covers/node-nats-jetstream.png", alt = "NATS JetStream from Node.js", hiddenInSingle = true }
+++

In the previous post, [Postgres from Node.js with pg](/posts/node-postgres-pg/), we talked to a database. Now the second pillar of a backend: messaging. I use {{< term "jetstream" "JetStream" >}} from Node.js and compare with [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/). The ideas are those of [Retry and Dead-Letter Queues](/posts/nats-jetstream-retry-dlq/), [Idempotency](/posts/nats-jetstream-idempotency/), [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) and [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/); only the client changes.

> Node v20.13.1, `nats` 2.29.3 (its `package.json` asks for Node >= 14). The server is a tiny Go program with an embedded nats-server, run as a separate process on 127.0.0.1. Local example scripts, real outputs, no timings.

## Publish, and the same msgID twice

`connect` returns a connection, `jetstreamManager()` creates streams and consumers, `jetstream()` publishes and consumes. Setting `msgID` makes the server drop duplicates inside the stream's duplicate window:

```js
const nc = await connect({ servers: process.env.NATS_URL });
const jsm = await nc.jetstreamManager();
const js = nc.jetstream();
await jsm.streams.add({ name: 'ORDERS', subjects: ['orders.>'] });
const h = headers(); h.set('Trace-Id', 'abc-123');
const a1 = await js.publish('orders.created', jc.encode({ id: 1 }), { msgID: 'order-1', headers: h });
const a2 = await js.publish('orders.created', jc.encode({ id: 1 }), { msgID: 'order-1' });
console.log(a1.stream, a1.seq, a1.duplicate, a2.seq, a2.duplicate);
```

```text
ORDERS 1 false 1 true
```

The PubAck has `stream`, `seq` and `duplicate`. The second publish got the same sequence and `duplicate: true`. This is a publish-side guard, not full end-to-end {{< term "idempotency" "idempotency" >}}; the consumer still has to cope with redelivery.

## A durable pull consumer

A {{< term "durable-consumer" "durable" >}} {{< term "pull-consumer" "pull consumer" >}} is created with explicit acks and a short {{< term "ack-wait" "AckWait" >}}, then fetched with `consumers.get` and `next()`:

```text
subject orders.created seq 1 trace abc-123
via codec { id: 1, total: 42 } | via JSON.parse { id: 1, total: 42 }
deliveryCount 1 redelivered false
again: deliveryCount 2 redelivered true
```

I deliberately did not ack the first delivery. After the AckWait the same message came back with `deliveryCount` 2 and `redelivered` true. Headers are read with `m.headers.get(...)`. This version has `JSONCodec`, but `JSON.parse(m.string())` gives the same object, so the codec is optional. Neither validates anything: the payload is still untrusted input (the next post is about that).

## ack, nak, term and backoff

The consumer had `max_deliver: 3` and `backoff` of 100 ms then 200 ms. I published four messages and handled each differently: `ack`, `nak(100)` on the first try, `term()`, and no answer at all:

```text
paid    delivery 1
flaky   delivery 1
poison  delivery 1
broken  delivery 1
broken  delivery 2
flaky   delivery 2
broken  delivery 3
ack_pending 0 pending 0 redelivered 1
```

{{< term "acknowledgement" "Acknowledgement" >}} decides the fate: `paid` and `poison` were never seen again; `flaky` returned once after `nak` and was acked; `broken` came back on the backoff schedule and stopped at delivery 3, because of `max_deliver`. Afterwards nothing was pending. The order of the `flaky` and `broken` lines depends on timing, so do not rely on it. As in the retry post, a message that exhausts its deliveries is not parked anywhere by itself; a {{< term "dlq" "DLQ" >}} is something you build around it.

## Graceful shutdown with drain

On SIGTERM the worker stops fetching, waits for the running job, then calls `drain()`, which flushes pending acks before closing:

```js
process.once('SIGTERM', async () => {
  it.stop();
  await inflight;
  await nc.drain();
  process.exit(0);
});
```

```text
start job-1
SIGTERM: stop fetching
acked job-1
in-flight done, draining
closed
exit code 0
```

The signal arrived while `job-1` was running (a 1.5 second fake job), the job finished and was acked, and the exit code was 0. This is the same {{< term "graceful-shutdown" "graceful shutdown" >}} idea as in Go, built from Node's [event loop](/posts/node-event-loop/) and [promises](/posts/node-promises-async-await/) instead of a context.

## Interop with Go

Node published `{"id":7,"total":99}` with a `Trace-Id` header to `orders.interop`, then a short Go program with nats.go fetched it:

```text
node published ORDERS 7
go got subject=orders.interop data={"id":7,"total":99} header[Trace-Id]=abc-123 stream_seq=7
```

The wire format is just bytes plus headers, so the languages do not matter.

## Compared with nats.go

Facts I am sure of: nats.go has `js.Publish` and `PullSubscribe` with `Fetch`, and acks are methods on the message (`Ack`, `Nak`, `Term`), as here. In Node everything returns promises and `consume()` is an async iterator; the config keys use the server's snake_case (`max_deliver`, `ack_wait`) and durations are nanoseconds, so use the `nanos()` helper.

## A few things to watch

- Always set a bounded `max_deliver` and a `backoff`; otherwise a broken message loops.
- `m.ack()` is fire-and-forget; `await m.ackAck()` confirms the server got it.
- Do not let an `async` handler throw unhandled: see [Errors and unhandled rejections](/posts/node-errors-unhandled-rejections/).
- `drain()` before `process.exit`, never `close()` in a hurry.
- Duplicates are possible, so make handlers idempotent.

## Exercise

Write a handler that publishes a message to `orders.dlq` once `m.info.deliveryCount` reaches the limit, then `term()` it. Check with a second consumer that the dead letter arrived.

## What's next

The next post is "Input validation with Zod".
