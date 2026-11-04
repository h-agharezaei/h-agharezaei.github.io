+++
date = '2026-11-24T10:00:00+03:30'
draft = false
title = 'Idempotency and the meaning of exactly-once in JetStream'
seoTitle = 'JetStream Idempotency and Exactly-Once'
description = 'What exactly-once really means in NATS JetStream: publish dedup with Nats-Msg-Id and its time window, plus idempotent consumers, with real runs.'
contentType = 'engineering'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "idempotency", "exactly-once"]
cover = { image = "/images/covers/nats-jetstream-idempotency.png", alt = "Idempotency and the meaning of exactly-once in JetStream", hiddenInSingle = true }
+++

Suppose the message "order A was paid, add 100 to the balance" reaches a worker twice. If the worker applies both, the customer gets 200, not 100. This is not rare. When a worker dies without acking, the message is redelivered, so a job can run twice; the [previous post](/posts/nats-jetstream-scaling-lag/) ended on that uncomfortable fact.

The usual answer is one sentence: "just use exactly-once". But what exactly does that phrase promise? Here I test what it can honestly mean, using three tools: deduplication at publish time, acks, and a handler that is {{< term "idempotency" "idempotent" >}}, meaning that running it twice has the same effect as running it once.

> Everything below was re-run with Go 1.27, an embedded `nats-server` v2.15.1 and `nats.go` v1.54.0. The original run of this post used Go 1.26. The outputs are from these runs; the seconds can differ by a tenth or two between runs. The code is a local example.

## Publish-side dedup with Nats-Msg-Id

The first problem: a publisher sends a message, the confirmation does not arrive in time (a timeout), and it sends again. Maybe the first one was stored after all. Now the stream holds two copies.

The fix: send every message with an ID. `nats.MsgId` sets the `Nats-Msg-Id` header. The stream remembers recent IDs, and if a message with a repeated ID arrives, it does not store it. How long it remembers is the **duplicate window** (the `Duplicates` setting). I set it to 2 seconds so I could also see what happens outside the window. (The default, as the DLQ stream in the Retry post showed, is 2 minutes.)

```go
js.AddStream(&nats.StreamConfig{Name: "PAY", Subjects: []string{"pay.>"}, Duplicates: 2 * time.Second})
ack, err := js.Publish("pay.created", []byte("order-1001"), nats.MsgId("order-1001"))
fmt.Println(ack.Sequence, ack.Duplicate)
```

The program publishes one message twice with the same ID, then the same content with another ID, and after 3 seconds once more with the first ID. After each step it asks for the number of messages in the stream:

```
  0.0s publish #1: err=<nil> seq=1 duplicate=false
  0.0s publish #2: err=<nil> seq=1 duplicate=true
  0.0s stream messages: 1
  0.0s same payload, different MsgId: seq=2 duplicate=false
  0.0s stream messages: 2
  3.0s after 3s, same MsgId again: seq=3 duplicate=false
  3.0s stream messages: 3
```

Line two: the second publish succeeds without an error, but the server's confirmation (`PubAck`) says `Duplicate: true` and points to the original message (sequence 1). Line three shows the stream still holds one message. Two things to notice:

- **Dedup is by ID, not by content.** The same text with another ID was stored, and the stream had two messages.
- **Dedup is time-bounded.** After 3 seconds, past my 2-second window, the same ID was stored again as a new message (`seq=3`). So this mechanism is a safety net for quick retries, not a permanent uniqueness guarantee.

This is only half the story. The mechanism only prevents duplicate storage. If one stored message is delivered twice to a worker, it can do nothing. That problem has to be solved on the worker's side.

## Consumer-side: make the handler idempotent

Redelivery is not a bug, it is the {{< term "at-least-once-delivery" "at-least-once" >}} contract: a message may arrive more than once, but it is never lost. So the handler must give the same result whether it runs once or twice.

The usual approach is to key the work by a **business ID** (an order ID, a payment ID) and record it as done. In my demo that is an in-memory map. In production it would be a unique constraint or an upsert in your database, written in the same transaction as the side effect; otherwise a crash between the two brings the problem back.

```go
if processed[id] {          // production: INSERT ... ON CONFLICT DO NOTHING
    m.Ack()                 // already done, just acknowledge
    continue
}
balance += amt
processed[id] = true
// ... crash here for order B, before m.Ack()
```

I published three messages: order A (+100), order B (+50), and another copy of order A with a different `Nats-Msg-Id`. That last one simulates a producer retry that publish dedup cannot catch, because its ID differs. The worker "crashes" after applying B and **before the ack** (the program just does not call ack). `AckWait` is 1 second:

```
  3.1s apply  order A +100 balance=100 (stream seq 1, delivery #1)
  3.1s apply  order B +50 balance=150 (stream seq 2, delivery #1)
  3.1s CRASH after side effect, before ack
  3.1s skip   order A (stream seq 3, delivery #1)
  4.1s skip   order B (stream seq 2, delivery #2)
  5.6s final balance=150 (expected 150)
```

(The clock counts from the program's start, and the first 3 seconds belong to the previous section, which waited 3 seconds.)

Line by line: A and B were applied once and the balance became 150. After the crash, the third message (the duplicate A, number 3 in the stream) arrived and the worker **skipped** it, because A was already done. One second later (3.1 + 1 = 4.1, the `AckWait`) message B came back as `delivery #2` and was skipped too. The last line was printed 1.5 seconds later (4.1 + 1.5 = 5.6), because the program waits that long for a new message and then gives up. The final balance is 150, the expected value. Without the map it would have been 300 (100 + 50 + 100 + 50).

Both kinds of duplicates were caught: the retry of A, which was a different message in the stream, and the redelivery of B, which was the same message.

## ack, AckSync and acking twice

Now a subtler question. `m.Ack()` sends the ack and moves on; `m.AckSync()` waits for the server to confirm. What happens if we ack a message twice, or ack late? Three acks in a row on the same message:

```
  5.6s AckSync #1: <nil>
  5.6s AckSync #2: nats: message was already acknowledged
  5.6s Ack     #3: nats: message was already acknowledged
  5.6s ackFloor=1 ackPending=0
```

The first `AckSync` succeeded. The second and third acked the same `*nats.Msg` object again, and the client library itself refused ("already acknowledged"). So acking twice from one object is harmless.

A stale copy is different. I took a message, let `AckWait` expire so it was redelivered, and then acked both the old copy and the new copy:

```
  6.9s old delivery #1, new delivery #2
  6.9s AckSync on OLD copy: <nil>
  6.9s ackFloor=2 ackPending=0
  6.9s AckSync on NEW copy: <nil>
```

The server accepted the late ack from the old delivery and moved the ack floor, and acking the new copy also returned no error. I only checked these outcomes, not the server's internals. The lesson: a successful ack does not tell you that you were the only one who processed the message. That is exactly why the handler has to be idempotent.

## So what is "exactly-once"?

From what I saw, it is a combination, not a switch:

- **Publish dedup** (`Nats-Msg-Id`) keeps retries from creating duplicate stream messages, but only inside the duplicate window.
- **At-least-once delivery** with acks means messages are redelivered rather than lost.
- **Idempotent processing** makes the repeated deliveries harmless, which is the part only your code can do.

The effect on your data is exactly-once; the delivery is not. I did not test any other JetStream feature that claims to go further, so I am not making claims about them.

## Where duplicates still slip through

- Take the ID from the **data** (the order ID), not from the message's stream sequence: as order A showed, a producer retry gets a different sequence.
- Keep the duplicate window longer than your longest realistic retry period. The longer it is, the more IDs have to be remembered; I did not measure the memory cost.
- Record "done" and the side effect in one transaction. An in-memory map, like mine, is lost on restart.
- External side effects (emails, calls to third-party APIs) need their own idempotency key, if the other side supports one.
- Ack **after** the work is done. If you ack first, a crash becomes a lost message.

## What's next

Redelivery during a deploy is the most common way to run into all of this, which is why Graceful shutdown for Go workers comes next: context, signals, `Drain`, and finishing in-flight work.
