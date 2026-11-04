+++
date = '2026-10-18T14:00:00+03:30'
draft = false
title = 'Retry and Dead-Letter Queues in NATS JetStream with Go'
seoTitle = 'Retry and Dead-Letter Queues in NATS JetStream'
description = 'A follow-up: retry failed messages with MaxDeliver and BackOff, then route the ones that never succeed to a dead-letter stream.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "retry"]
cover = { image = "/images/covers/nats-jetstream-retry-dlq.png", alt = "Retry and Dead-Letter Queues in NATS JetStream with Go", hiddenInSingle = true }
+++

Picture a message in your queue that fails every time you process it: the JSON is broken, or it points to a record that does not exist. The worker from the [previous post](/posts/nats-jetstream-go/) ignored this possibility. It assumed processing always succeeds and acked after every message. Now suppose we stop acking failed messages. Two bad things can happen. Either JetStream sends the same message again forever and the worker is stuck in an endless loop, or the message quietly disappears and nobody notices.

To avoid both, we need three things:

1. A cap on the number of attempts: `MaxDeliver`
2. A pause between attempts: `BackOff` and `NakWithDelay`
3. A place for messages that still fail after every attempt: a **dead-letter** stream

This post builds these one at a time and shows each with a real run.

> Everything ran on Go 1.27 with `nats.go` v1.54.0 and an embedded `nats-server` (v2.15.1) on 127.0.0.1 and a random port. The code is a local example, not a published repo. I rounded the times (0.0 means "the same moment"), and some values, such as the advisory's id and clock time, differ on every run.

## One message, three attempts: a consumer with explicit settings

In the previous post `PullSubscribe` created a consumer with default settings, and we saw that its delivery limit was `-1`, meaning unlimited. This time we create the consumer ourselves:

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

- `AckPolicy: AckExplicitPolicy` means the worker must ack every message individually and explicitly.
- `MaxDeliver: 3` means each message is delivered at most 3 times: the first delivery and two redeliveries.
- {{< term "ack-wait" "AckWait" >}} is how long the server waits for an ack. When none arrives, the server assumes the worker died or got stuck and sends the message again.
- `BackOff` is a list of delays: 500 milliseconds before the first redelivery, 1 second before the second.

One thing surprised me in the run: when `BackOff` is set, the server ignores `AckWait`. I asked for 30 seconds, but when I asked the server for the consumer's state it answered:

```
config: ackWait=500ms maxDeliver=3 backoff=[500ms 1s]
```

So `AckWait` became the first element of `BackOff`. I did not find this in the NATS docs; it is only what `ConsumerInfo` reported in this run. I tried both 2 and 30 seconds as `AckWait`, and the delivery timelines were exactly the same.

After the consumer exists, the worker binds to it as before:

```go
sub, _ := js.PullSubscribe("events.created", "worker-consumer")
```

## When work fails: Nak or silence?

When processing fails, the worker has two options. It can simply not ack and let the server redeliver after waiting. Or it can say "give me this message again" with `Nak`. There is also a `Nak` that takes a delay: `NakWithDelay`.

To compare them I sent a "poison" message, one that fails every time (that is what a {{< term "poison-message" "poison message" >}} is). The worker returned it each time, either without acking or with one of the two kinds of `Nak`, and I wrote down the second of each delivery, relative to the first. The consumer was the one above (`MaxDeliver: 3`, `BackOff` of 0.5 and 1 second):

| Worker reaction | Delivery 1 | Delivery 2 | Delivery 3 |
| --- | --- | --- | --- |
| `m.Nak()` | 0.0 s | 0.0 s | 0.0 s |
| `m.NakWithDelay(1 * time.Second)` | 0.0 s | 1.0 s | 2.5 s |
| nothing (no ack, no nak) | 0.0 s | 0.5 s | 1.5 s |

The three rows tell three different stories:

- **Plain `Nak()`** returns the message immediately, and `BackOff` has no effect. All three attempts finished at second zero. If the failure is temporary (say the database is unreachable for one second), all three attempts happen back to back at the same moment and all fail, without giving the database a chance to recover.
- **`NakWithDelay(1s)`** returns the message after the requested delay. Delivery 2 came exactly at 1.0 s. Delivery 3 came at 2.5 s, not 2.0. I repeated the experiment without `BackOff`, and there the times were exactly 0, 1.0 and 2.0. So the extra half second comes from `BackOff`, but I did not work out how the server computes it and I will not guess.
- **Silence** follows `BackOff`, and the arithmetic is simple. When the worker does not answer, the server sends delivery 2 after 0.5 s. Delivery 3 comes one second after delivery 2, so at 0.5 + 1 = 1.5 s. The `BackOff` list has two entries, and after delivery 3 we have reached the cap.

The practical result: a plain `Nak()` is dangerous for temporary failures, because it spins the worker in a tight retry loop. For errors that probably clear up with a little patience, use `NakWithDelay`. A more complete worker loop:

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

The poison message came three times and failed three times. What then? After `MaxDeliver` is reached, the server stops delivering it to this consumer. The message itself stays in the stream, but JetStream publishes an **advisory**, a small notice on this subject:

```
$JS.EVENT.ADVISORY.CONSUMER.MAX_DELIVERIES.<stream>.<consumer>
```

I printed the notice's content in the DLQ run below. Here it is (the JSON is a single line in the output):

```json
{"type":"io.nats.jetstream.advisory.v1.max_deliver","id":"6Hz2NBCGpth11TGJ05piQy","timestamp":"2026-11-04T17:21:20.971697Z","stream":"EVENTS","consumer":"worker-consumer","stream_seq":2,"deliveries":3}
```

Two fields matter to us: `stream_seq`, the message's sequence number in the stream, and `deliveries`, the number of deliveries. With the sequence number we can pull the original message out of the stream.

## Building the dead-letter stream

The idea of a {{< term "dlq" "dead-letter" >}} stream is simple: create a separate stream for failed messages and a small piece of code that listens for the advisory. Whenever a notice arrives, it reads the original message from `EVENTS` by its sequence number and puts it into the new stream:

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

`MsgId` is an identifier we attach to a message so the server can recognise a duplicate. The post [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/) covers it in full. All you need here: publishing twice with the same ID stores only one message, as long as less than the stream's "duplicate window" has passed between the two publishes. In this run I asked the server for the `DLQ` window, and it was `2m0s`.

Now I sent three messages: `good-1`, `poison` and `good-2`. The worker returns the poison one with `NakWithDelay(1s)` and acks the rest. The output:

```
  t=0.0s good-1 delivery #1 (stream seq 1)
  t=0.0s poison delivery #1 (stream seq 2)
  t=0.0s good-2 delivery #1 (stream seq 3)
  t=1.0s poison delivery #2 (stream seq 2)
  t=2.5s poison delivery #3 (stream seq 2)
advisory: {"type":"io.nats.jetstream.advisory.v1.max_deliver","id":"6Hz2NBCGpth11TGJ05piQy","timestamp":"2026-11-04T17:21:20.971697Z","stream":"EVENTS","consumer":"worker-consumer","stream_seq":2,"deliveries":3}
second publish with same MsgId: duplicate=true
end: EVENTS msgs=3 pending=0 ackPending=0 redelivered=1 | DLQ msgs=1 advisories=1
```

Line by line:

- The first three messages arrived at second zero. `good-1` and `good-2` were acked and never came back: each has only `delivery #1`.
- `poison`, which is number 2 in the stream, arrived at 0.0, 1.0 and 2.5 seconds, the same timeline as the table above.
- After the third delivery failed, one advisory arrived, and our code put exactly **one** message into `DLQ`. The line `second publish with same MsgId: duplicate=true` comes from my test code: to show duplicate detection it published the same message once more with the same ID, and the server recognised it as a duplicate.
- At the end `EVENTS` still holds all three messages (the original poison message is not removed from the stream), `DLQ` holds one, and the consumer has no pending or ack-pending messages. The `redelivered=1` is the server's own counter; I do not rely on it.

## `Term`: when retrying is pointless

Some failures do not go away with patience. Broken JSON is still broken the second time. In that case you can call `m.Term()` right away, which means "never deliver this message again". I did exactly that in one run: only `delivery #1` appeared, and no further delivery came during the next 6 seconds. The message was still in the stream (`msgs=1`).

## Where this DLQ falls short

- **An advisory is a core NATS message, not a JetStream one.** From what I know of the NATS docs, advisories are published on ordinary subjects and are not stored. If the DLQ service is down at the moment the notice is published, it misses it. Critical systems need a fallback, such as periodically inspecting the consumer with `ConsumerInfo`, or storing advisories in a stream.
- **The original message is not removed.** We saw that `EVENTS` still holds all three. How long it stays depends on that stream's retention policy.
- **Not every failure deserves a retry.** If you recognise a permanent error, call `Term` and do not waste three attempts.
- **Duplicate protection is limited to a window.** `MsgId` only works while less than the stream's duplicate window has passed since the earlier publish.

## What's next

A DLQ collects failed messages, but it does nothing for a queue that fills faster than one worker can drain it. Multiple workers on one consumer and monitoring lag in JetStream shows how to add workers and how to tell that the queue is backing up. The full code for the base example is in [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo).
