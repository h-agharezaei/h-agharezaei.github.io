+++
date = '2026-10-18T14:00:00+03:30'
draft = false
title = 'Retry and Dead-Letter Queues in NATS JetStream with Go'
seoTitle = 'Retry and Dead-Letter Queues in NATS JetStream'
description = 'A follow-up: retry failed messages with MaxDeliver and BackOff, then route the ones that never succeed to a dead-letter stream.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "retry"]
cover = { image = "/images/covers/nats-jetstream-retry-dlq.png", alt = "Retry and Dead-Letter Queues in NATS JetStream with Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/nats-jetstream-go/) we built a simple publisher and worker on JetStream. But that worker assumed processing always succeeds. In real systems some messages fail every single time, and if you do nothing they either retry forever or get lost.

This post adds three things:

1. Limiting attempts with `MaxDeliver`
2. Spacing out attempts with `BackOff` and `NakWithDelay`
3. Routing "poison" messages to a **dead-letter** stream

> I tested every behavior below against an embedded NATS server (with JetStream) and the `nats.go` client, and the outputs come from that run.

## Creating the consumer explicitly

Instead of letting `PullSubscribe` create a default consumer, we create it with the settings we want:

```go
_, err = js.AddConsumer("EVENTS", &nats.ConsumerConfig{
    Durable:       "worker-consumer",
    AckPolicy:     nats.AckExplicitPolicy,
    AckWait:       30 * time.Second,
    MaxDeliver:    3,
    BackOff:       []time.Duration{500 * time.Millisecond, time.Second},
    FilterSubject: "events.created",
})
```

- `MaxDeliver: 3` means each message is delivered at most 3 times.
- `AckWait` is how long the server waits for an ack before redelivering.
- `BackOff` sets the delays between redeliveries.

The worker then binds to that same consumer as before:

```go
sub, _ := js.PullSubscribe("events.created", "worker-consumer")
```

## What does Nak do?

When processing fails you can either not ack and wait for `AckWait`, or explicitly ask for redelivery with `Nak`. I tried both against a "poison" message that always fails:

| Approach | Observed behavior |
| --- | --- |
| `m.Nak()` | Redelivered **immediately**. `BackOff` has no effect. All 3 attempts happened at second zero. |
| `m.NakWithDelay(1 * time.Second)` | Redelivered after the given delay (attempts 2 and 3 at roughly 1s and 2.5s). |
| Not acking | Redelivered following `BackOff` (attempts 2 and 3 at 0.5s and 1.5s in my run; I used a 2s `AckWait` for the experiment). |

Practical takeaway: a plain `Nak()` is dangerous for transient failures because it spins the worker in a tight retry loop. For errors that probably clear up with a little patience (say, the database is briefly unavailable) use `NakWithDelay`.

A more complete worker loop:

```go
for _, m := range msgs {
    if err := process(m.Data); err != nil {
        log.Println("process failed:", err)
        m.NakWithDelay(time.Second)
        continue
    }
    m.Ack()
}
```

## When attempts run out: the advisory

Once `MaxDeliver` is reached, JetStream stops delivering the message to this consumer. The message stays in the stream, but JetStream publishes an **advisory** on this subject:

```
$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.<stream>.<consumer>
```

The JSON payload contains the message's sequence number in the stream (`stream_seq`) and the number of deliveries (`deliveries`). With that sequence we can fetch the original message.

## Building the dead-letter stream

We create a separate stream for failed messages and a small service that listens for the advisory:

```go
js.AddStream(&nats.StreamConfig{
    Name:     "DLQ",
    Subjects: []string{"dlq.events"},
})

nc.Subscribe("$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.EVENTS.worker-consumer",
    func(m *nats.Msg) {
        var adv struct {
            Stream     string `json:"stream"`
            StreamSeq  uint64 `json:"stream_seq"`
            Deliveries int    `json:"deliveries"`
        }
        json.Unmarshal(m.Data, &adv)

        raw, err := js.GetMsg(adv.Stream, adv.StreamSeq)
        if err != nil {
            log.Println("getmsg:", err)
            return
        }
        // MsgId prevents storing the same message twice
        js.Publish("dlq.events", raw.Data,
            nats.MsgId(fmt.Sprintf("dlq-%d", adv.StreamSeq)))
    })
```

In my test I published three messages: `good-1`, `poison` and `good-2`. The two good ones were delivered once and acked. `poison` was delivered three times, and then exactly **one** message landed in the `DLQ` stream. At the end the consumer had no pending or ack-pending messages.

## A few caveats

- **Advisories are core NATS messages, not JetStream ones.** If the DLQ service is down at the moment the advisory is published, it misses it. For critical systems you need a fallback, such as periodically inspecting the consumer with `ConsumerInfo` or persisting advisories into a stream.
- The original message is not removed from the stream after hitting `MaxDeliver`. How long it stays depends on that stream's retention policy.
- Permanent failures (like a corrupt payload) are pointless to retry. If you can detect them, call `m.Term()` right away so JetStream never delivers the message again.
- The `MsgId` above only deduplicates within the stream's duplicate-detection window.

## What's next

Two topics remain for the next post: running multiple workers on one consumer, and monitoring processing lag. The full code for the base example is in [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo).
