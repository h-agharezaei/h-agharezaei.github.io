+++
date = '2026-11-24T10:00:00+03:30'
draft = false
title = 'Idempotency and the meaning of exactly-once in JetStream'
seoTitle = 'JetStream Idempotency and Exactly-Once'
description = 'What exactly-once really means in NATS JetStream: publish dedup with Nats-Msg-Id and its time window, plus idempotent consumers, with real runs.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "idempotency", "exactly-once"]
cover = { image = "/images/covers/nats-jetstream-idempotency.png", alt = "Idempotency and the meaning of exactly-once in JetStream", hiddenInSingle = true }
+++

The [previous post](/posts/nats-jetstream-scaling-lag/) ended with an uncomfortable fact: when a worker dies without acking, the message is redelivered, so a job can run twice. People often answer this with "just use exactly-once". In this post I try to find out what that phrase can honestly mean, by testing the pieces JetStream gives us: deduplication at publish time, acks, and an {{< term "idempotency" "idempotent" >}} handler.

> Everything below ran against an embedded `nats-server` v2.15.1 and `nats.go` v1.54.0 on Go 1.26. The outputs are from those runs.

## Publish-side dedup with Nats-Msg-Id

If a publisher times out and retries, the stream could end up with two copies. To prevent that, you attach an ID with `nats.MsgId`, which sets the `Nats-Msg-Id` header. The stream remembers IDs for its **duplicate window** (the `Duplicates` setting). I set it to 2 seconds so I could also see what happens outside it:

```go
js.AddStream(&nats.StreamConfig{Name: "PAY", Subjects: []string{"pay.>"}, Duplicates: 2 * time.Second})
ack, err := js.Publish("pay.created", []byte("order-1001"), nats.MsgId("order-1001"))
fmt.Println(ack.Sequence, ack.Duplicate)
```

```
  0.0s publish #1: err=<nil> seq=1 duplicate=false
  0.0s publish #2: err=<nil> seq=1 duplicate=true
  0.0s stream messages: 1
  0.0s same payload, different MsgId: seq=2 duplicate=false
  0.0s stream messages: 2
  3.0s after 3s, same MsgId again: seq=3 duplicate=false
  3.0s stream messages: 3
```

The second publish succeeds without an error, but the `PubAck` says `Duplicate: true` and points to the original sequence, and the stream still holds one message. Two things to notice. Dedup is by ID, not by content: the same payload with another ID was stored. And dedup is time-bounded: after 3 seconds (past my 2-second window) the same ID was stored again as a new message. So a duplicate-window dedup is a safety net for quick retries, not a permanent uniqueness guarantee.

## Consumer-side: make the handler idempotent

Redelivery is not a bug, it is the at-least-once contract. So the handler must produce the same result whether it runs once or twice. The usual approach is to key the work by a **business ID** (an order ID, a payment ID) and record it as done. In my demo that is an in-memory map; in production it would be a unique constraint or an upsert in your database, written in the same transaction as the side effect, otherwise a crash between the two reintroduces the problem.

```go
if processed[id] {          // production: INSERT ... ON CONFLICT DO NOTHING
    m.Ack()                 // already done, just acknowledge
    continue
}
balance += amt
processed[id] = true
// ... crash here for order B, before m.Ack()
```

I published three messages: order A (+100), order B (+50), and another copy of order A with a different `Nats-Msg-Id`, simulating a producer retry that publish dedup cannot catch. The handler "crashes" after applying B but before the ack, with `AckWait` of 1 second:

```
  3.0s apply  order A +100 balance=100 (stream seq 1, delivery #1)
  3.0s apply  order B +50 balance=150 (stream seq 2, delivery #1)
  3.0s CRASH after side effect, before ack
  3.0s skip   order A (stream seq 3, delivery #1)
  4.0s skip   order B (stream seq 2, delivery #2)
  5.5s final balance=150 (expected 150)
```

Both kinds of duplicates were skipped: the retry of A (a different stream message) and the redelivery of B (the same message, delivery #2). Without the map, the balance would have been 300.

## What AckSync and double acks tell us

`m.Ack()` is fire-and-forget; `m.AckSync()` waits for the server to confirm. What I observed:

```
  5.6s AckSync #1: <nil>
  5.6s AckSync #2: nats: message was already acknowledged
  5.6s Ack     #3: nats: message was already acknowledged
  5.6s ackFloor=1 ackPending=0
```

Acking the same `*nats.Msg` twice is rejected by the client library itself, so a double ack from one object is harmless. A stale copy is different: I let `AckWait` expire so the message was redelivered, then acked the old copy and the new copy:

```
  6.9s old delivery #1, new delivery #2
  6.9s AckSync on OLD copy: <nil>
  6.9s ackFloor=2 ackPending=0
  6.9s AckSync on NEW copy: <nil>
```

The server accepted the late ack from the old delivery and moved the ack floor, and acking the new copy also returned no error. I only checked these outcomes, not the server's internals. The lesson is that a successful ack does not tell you that you were the only one who processed the message, which is exactly why the handler has to be idempotent.

## So what is "exactly-once"?

From what I saw, it is a combination, not a switch:

- **Publish dedup** (`Nats-Msg-Id`) keeps retries from creating duplicate stream messages, but only inside the duplicate window.
- **At-least-once delivery** with acks means messages are redelivered rather than lost.
- **Idempotent processing** makes the repeated deliveries harmless, which is the part only your code can do.

The effect on your data is exactly-once; the delivery is not. I did not test any other JetStream feature that claims to go further, so I am not making claims about them.

## A few things to watch

- Pick the business ID from the data (order ID), not from the message sequence: stream sequences differ for producer retries, as order A showed.
- Keep the duplicate window longer than your longest realistic retry period, and remember it costs memory proportional to the number of IDs in it.
- Store the processed marker and the side effect in one transaction. An in-memory map, like mine, is lost on restart.
- External side effects (emails, calls to third-party APIs) need their own idempotency key if the other side supports one.
- Ack after the work is done. Acking first turns a crash into a lost message.

## What's next

Redelivery during a deploy is the most common way to hit all of this. The next post, `go-graceful-shutdown-workers`, covers graceful shutdown for Go workers: context, signals, `Drain`, and finishing in-flight work.
