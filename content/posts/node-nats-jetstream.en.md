+++
date = '2027-02-27T10:00:00+03:30'
draft = false
title = 'NATS JetStream from Node.js'
description = 'NATS JetStream from Node.js: publish with msgID, durable pull consumers, ack, nak, term, backoff, graceful drain and Go interop, all run for real.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "nats", "jetstream", "messaging", "graceful-shutdown"]
cover = { image = "/images/covers/node-nats-jetstream.png", alt = "NATS JetStream from Node.js", hiddenInSingle = true }
+++

A customer pays for an order. Your service saves it and sends the message "order 1 was created" so that the warehouse can start packing. Two things must hold. The message must not be lost, even if the warehouse worker is down at that moment. And the worker must not pack the order twice, even if the message arrives twice. A plain function call cannot promise either. A message system with storage can.

In [Postgres from Node.js with pg](/posts/node-postgres-pg/) we dealt with the database, the first pillar of a backend. Messaging is the second. Here I use {{< term "jetstream" "JetStream" >}}, the storage layer of the NATS message server, from Node.js. If you have read the Go and Rust versions, [A Simple Publisher and Worker with NATS JetStream in Go](/posts/nats-jetstream-go/), [Retry and Dead-Letter Queues](/posts/nats-jetstream-retry-dlq/), [Idempotency](/posts/nats-jetstream-idempotency/), [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/) and [An async NATS JetStream client in Rust](/posts/rust-nats-async-client/), the ideas are the same; only the client library changes. Everything here is explained from the start, so you do not need them.

> I ran everything with Node v20.13.1 and `nats` 2.29.3 (its `package.json` asks for Node >= 14). The server is a tiny Go program with an embedded nats-server (v2.15.1), run as a separate process on 127.0.0.1 and a random free port. For the interop demo I built a small Go client with nats.go v1.54.0. The scripts are local examples and the outputs are real. I show no timings.

## Four words you need

NATS is a message server. Programs connect to it and exchange messages, and every message is sent to a **subject**, a dotted name such as `orders.created`. Plain NATS hands a message to whoever is listening at that moment and forgets it. That is fast, but nothing is kept.

JetStream adds storage, and with it three more words:

- A **stream** is a named log that stores every message published to certain subjects. Ours is called `ORDERS` and keeps `orders.>` (the `>` means "any subject below `orders.`"). Each stored message gets a sequence number: 1, 2, 3...
- A **consumer** is a named reader of a stream. It remembers how far it has read, so a worker that restarts continues where it stopped. Ours is {{< term "durable-consumer" "durable" >}} (it keeps its position even when no program is connected) and {{< term "pull-consumer" "pull" >}} (the worker asks for messages; the server does not push them).
- An **ack** (acknowledgement) is the worker's answer after handling a message: "done". A message that is not acked is delivered again. That is the whole trick that makes loss unlikely. There are two other answers: `nak` ("failed, send it again", optionally after a delay) and `term` ("never send it again").

Now the code.

## Publishing, and the same msgID twice

`connect` returns a connection. `jetstreamManager()` creates streams and consumers, and `jetstream()` publishes and reads. This script creates the stream and publishes the same order twice with the same `msgID`. The server remembers message IDs for a time called the duplicate window and drops a second message with an ID it has already seen. I set the window to 60 seconds:

```js
const nc = await connect({ servers: process.env.NATS_URL });
const jsm = await nc.jetstreamManager();
const js = nc.jetstream();
const si = await jsm.streams.add({ name: 'ORDERS', subjects: ['orders.>'], duplicate_window: nanos(60_000) });
const h = headers(); h.set('Trace-Id', 'abc-123');
const ack1 = await js.publish('orders.created', jc.encode({ id: 1, total: 42 }), { msgID: 'order-1', headers: h });
const ack2 = await js.publish('orders.created', jc.encode({ id: 1, total: 42 }), { msgID: 'order-1' });
console.log('ack1', ack1.stream, ack1.seq, ack1.duplicate);
console.log('ack2', ack2.stream, ack2.seq, ack2.duplicate);
```

(`jc` is a `JSONCodec()`, which turns an object into bytes and back; `Trace-Id` is a header, a small label that travels with the message.) The output:

```text
ack1 ORDERS 1 false
ack2 ORDERS 1 true
```

`js.publish` returns a "publish ack" with the stream name, the sequence number and a `duplicate` flag. The first publish was stored as message 1. The second got the same sequence number and `duplicate: true`: the server recognised the ID and stored nothing new.

This protects only the publishing side. If you publish once and the worker receives the message twice, `msgID` does not help. That needs {{< term "idempotency" "idempotency" >}} in the handler, which we come back to in the pitfalls.

## A durable pull consumer, and a message that comes back

Next, a consumer. It has explicit acks (we must ack every message ourselves) and a short {{< term "ack-wait" "AckWait" >}} of one second: how long the server waits for an ack before it delivers the message again. The script gets the consumer with `consumers.get` and reads one message with `next()`. It deliberately does not ack the first delivery:

```js
await jsm.consumers.add('ORDERS', { durable_name: 'node-worker', ack_policy: AckPolicy.Explicit, ack_wait: nanos(1000) });
const c = await js.consumers.get('ORDERS', 'node-worker');
const m = await c.next({ expires: 2000 });
console.log('subject', m.subject, 'seq', m.seq, 'trace', m.headers.get('Trace-Id'));
console.log('via codec', jc.decode(m.data), '| via JSON.parse', JSON.parse(m.string()), '| m.json()', typeof m.json);
console.log('deliveryCount', m.info.deliveryCount, 'redelivered', m.redelivered);
// not acked on purpose: AckWait is 1s
const m2 = await c.next({ expires: 4000 });
console.log('again: deliveryCount', m2.info.deliveryCount, 'redelivered', m2.redelivered);
```

```text
consumer node-worker explicit
subject orders.created seq 1 trace abc-123
via codec { id: 1, total: 42 } | via JSON.parse { id: 1, total: 42 } | m.json() function
deliveryCount 1 redelivered false
again: deliveryCount 2 redelivered true
```

The first message has the subject we published to, the sequence number 1 and the header we set (`m.headers.get('Trace-Id')`). The payload can be decoded with the codec or with plain `JSON.parse(m.string())`; both give the same object, so the codec is optional. Notice that neither one checks that the object has the right shape. The payload is still input from outside, and the next post is about that.

The last two lines are the point. The first delivery had `deliveryCount` 1. I did not ack it, and after one second the server delivered the same message again: `deliveryCount` 2 and `redelivered` true. A crashed worker would produce exactly this, and that is how the message survives.

## ack, nak, term and backoff

Real handlers need more than "ack or nothing". The next consumer allows at most 3 deliveries (`max_deliver: 3`) and waits 100 ms and then 200 ms between redeliveries (`backoff`). It uses `deliver_policy: New`, so it ignores the old messages in the stream and sees only what is published after it is created. I published four messages and answered each one differently:

```js
if (name === 'paid') m.ack();
else if (name === 'flaky') n === 1 ? m.nak(100) : m.ack();
else if (name === 'poison') m.term();
// 'broken': never acked, the backoff decides when it comes back
```

So `paid` is acked, `flaky` fails once and succeeds on the second try (`nak(100)` asks for a redelivery after 100 ms), `poison` is terminated, and `broken` is never answered. What did the consumer see?

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

Read it by message. `paid` and `poison` appear once and never again: an {{< term "acknowledgement" "acknowledgement" >}}, either `ack` or `term`, ends the story. `flaky` comes back once after the `nak` and is acked. `broken` comes back on the backoff schedule and stops at delivery 3, because `max_deliver` is 3. Afterwards `ack_pending` and `pending` are 0: nothing is still waiting for an answer. (The last number is the server's own redelivery counter; I do not rely on it.) The order of the `flaky` and `broken` lines depends on timing and can change from run to run.

A message that has used all its deliveries is simply not delivered to this consumer any more. Nothing moves it anywhere for you. A {{< term "dlq" "dead-letter queue" >}}, a place where failing messages are parked for a human to look at, is something you build yourself, as in the retry post.

## Graceful shutdown with drain

A worker that is killed in the middle of a job leaves a message unacked, so it will be redelivered and the job may run twice. A {{< term "graceful-shutdown" "graceful shutdown" >}} avoids that: on `SIGTERM` the worker stops taking new messages, lets the running job finish, and then calls `drain()`. According to the nats.js docs, `drain()` lets messages that are already being processed and data waiting to be sent go through before the connection closes.

```js
process.once('SIGTERM', async () => {
  it.stop();
  await inflight;
  await nc.drain();
  process.exit(0);
});
```

`it.stop()` stops fetching, `await inflight` waits for the current job, and `drain()` closes the connection cleanly. The script processes one message, `job-1`, which takes a fake 1.5 seconds. I started it, sent `SIGTERM` while the job was running, and the output was:

```text
start job-1
SIGTERM: stop fetching
acked job-1
in-flight done, draining
closed
exit code 0
```

The signal arrived after `job-1` had started. The worker stopped fetching, but the job still finished and was acked, then the connection drained and the process exited with code 0. This is the same idea as in the Go post, built here from Node's [event loop](/posts/node-event-loop/) and [promises](/posts/node-promises-async-await/) instead of a context.

## Node and Go on the same stream

Messages are just bytes plus headers, so the language of the client does not matter. Node published `{"id":7,"total":99}` with a `Trace-Id` header to `orders.interop`, and then a short Go program using nats.go fetched it:

```text
node published ORDERS 7
go got subject=orders.interop data={"id":7,"total":99} header[Trace-Id]=abc-123 stream_seq=7
```

The sequence number is 7 because the earlier scripts of this post had already put six messages into the same stream. The data and the header arrived unchanged.

## Compared with nats.go

Facts I am sure of: nats.go has `js.Publish` and `PullSubscribe` with `Fetch`, and the acks are methods on the message (`Ack`, `Nak`, `Term`), as here. In Node everything returns promises, and `consume()` is an async iterator you read with `for await`. The config keys use the server's snake_case names (`max_deliver`, `ack_wait`), and durations are in nanoseconds, which is why the scripts use the `nanos()` helper.

## How messages loop or vanish

- **No limit on deliveries.** Always set a bounded `max_deliver` and a `backoff`. Otherwise a message that always fails is retried forever.
- **Ack that may not arrive.** `m.ack()` is fire-and-forget. If you need to know the server received it, use `await m.ackAck()`.
- **A handler that throws.** An `async` handler that throws without being caught becomes an unhandled rejection and can kill the worker. See [Errors and unhandled rejections in Node.js](/posts/node-errors-unhandled-rejections/).
- **Closing in a hurry.** Call `drain()` before `process.exit`, not `close()`, so acks and in-flight work are not cut off.
- **Duplicates.** A message can arrive more than once, a property called {{< term "at-least-once-delivery" "at-least-once delivery" >}}, so make the handler idempotent: handling it twice must have the same effect as once.

## Exercise

Write a handler that publishes a message to `orders.dlq` once `m.info.deliveryCount` reaches the limit, and then calls `term()` on it. Check with a second consumer that the dead letter arrived.

## What's next

The next post is "Input validation with Zod". A payload that arrives from a stream is still input from outside, and that post shows how to check it before using it.
