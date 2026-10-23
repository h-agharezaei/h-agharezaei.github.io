+++
date = '2026-10-25T10:00:00+03:30'
draft = false
title = 'Multiple workers on one consumer and monitoring lag in JetStream'
seoTitle = 'Scaling Workers and Monitoring JetStream Lag'
description = 'Scale processing by running several workers on one durable JetStream consumer, see what happens when one crashes, and monitor lag with ConsumerInfo.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "scaling", "monitoring"]
cover = { image = "/images/covers/nats-jetstream-scaling-lag.png", alt = "Multiple workers on one consumer and monitoring lag in JetStream", hiddenInSingle = true, hiddenInList = true }
+++

At the end of the [previous post](/posts/nats-jetstream-retry-dlq/) I promised two topics: running more than one worker, and watching how far behind the workers are. One worker is fine until messages arrive faster than it can process them. This post answers two questions: how do I add workers without processing anything twice, and how do I know the queue is backing up?

> Everything below ran against an embedded `nats-server` (JetStream enabled, temp store dir) and `nats.go` v1.54.0, on Go 1.26. The outputs are from those runs.

## Many workers, one durable consumer

The trick is that there is no trick. Every worker binds to the **same durable consumer**, and the server hands each message to only one of them:

```go
sub, err := js.PullSubscribe("jobs.new", "workers", nats.Bind("JOBS", "workers"))
// ...
msgs, err := sub.Fetch(1, nats.MaxWait(500*time.Millisecond))
// process msgs[0], then m.Ack()
```

The consumer was created once with `AckExplicitPolicy`. I started three goroutines (`w1`, `w2`, `w3`), each with its own pull subscription, each taking 200ms per job, and published 30 messages. A sample of the log:

```
  0.0s w3 got job-01 (stream seq 1, delivery #1)
  0.0s w2 got job-02 (stream seq 2, delivery #1)
  0.0s w1 got job-03 (stream seq 3, delivery #1)
  0.2s w2 got job-06 (stream seq 6, delivery #1)
  0.2s w3 got job-04 (stream seq 4, delivery #1)
  0.2s w1 got job-05 (stream seq 5, delivery #1)
  ...
deliveries=30 unique=30 pending=0 ackPending=0 redelivered=0
```

30 deliveries, 30 unique jobs, nothing redelivered. The whole batch finished in about 2 seconds instead of the 6 a single worker would need. Notice that the order is not strict: `job-06` started before `job-04`.

## A worker dies mid-job

Now the interesting part. I set `AckWait` to 2 seconds, published 10 jobs, and made `w2` "crash" on its second message: it stops without acking.

```
  0.1s w2 got job-06 (stream seq 6, delivery #1)
  0.1s w2 CRASHED while holding job-06 (no ack)
  ...
  2.1s w1 got job-06 (stream seq 6, delivery #2)
deliveries=11 unique=10 pending=0 ackPending=0 redelivered=0
```

The server waited for `AckWait`, then redelivered `job-06` to a worker that was still alive (`w1`). That is the whole safety net: no ack means the message is not lost. Two consequences:

- **Delivery is at-least-once.** The crashed worker may have done half the work or all of it, so processing must be safe to repeat. That is the topic of the next post.
- **Ordering across workers is not guaranteed.** `job-06` was processed long after `job-10`. If you need strict order per key, one consumer with one worker, or partitioning by subject, is a different design.

## Reading lag with ConsumerInfo

To see backlog, ask the server about the consumer. My tiny monitor is just a ticker:

```go
i, err := js.ConsumerInfo("JOBS", "workers")
fmt.Printf("pending=%d ackPending=%d redelivered=%d delivered=%d ackFloor=%d\n",
    i.NumPending, i.NumAckPending, i.NumRedelivered,
    i.Delivered.Consumer, i.AckFloor.Consumer)
```

What each number means:

- `NumPending`: messages in the stream the consumer has not delivered yet. This is the number to alert on for "lag".
- `NumAckPending`: delivered but not acked yet, i.e. in flight right now. With two busy workers it sits at 2.
- `NumRedelivered`: messages that are being redelivered.
- `Delivered.Consumer`: the consumer sequence of the last delivery. It also counts redeliveries.
- `AckFloor.Consumer`: the consumer sequence below which everything has been acked.

For this run I used two slow workers (500ms per job), published 40 jobs at 1.5s, and made `w2` crash on its 5th message. `AckWait` was 3s.

```
  1.0s pending=0   ackPending=0  redelivered=0  delivered=0   ackFloor=0
  1.5s publishing 40 jobs
  2.0s pending=38  ackPending=2  redelivered=0  delivered=2   ackFloor=0
  3.0s pending=34  ackPending=2  redelivered=0  delivered=6   ackFloor=4
  3.5s w2 CRASHED while holding job-09 (no ack)
  4.0s pending=30  ackPending=2  redelivered=0  delivered=10  ackFloor=8
  5.0s pending=28  ackPending=2  redelivered=0  delivered=12  ackFloor=8
  6.0s pending=26  ackPending=2  redelivered=0  delivered=14  ackFloor=8
  7.0s pending=25  ackPending=1  redelivered=1  delivered=16  ackFloor=8
  8.0s pending=23  ackPending=1  redelivered=0  delivered=18  ackFloor=17
 ...
 19.0s pending=1   ackPending=1  redelivered=0  delivered=40  ackFloor=39
 20.0s pending=0   ackPending=0  redelivered=0  delivered=41  ackFloor=41
```

Pending jumps to 38 when the burst arrives and drains at about 4 per second with two workers, then falls by about 2 per second after the crash, since only one worker is left. The crash itself shows in two places: `AckFloor` froze at 8 while the stuck message waited, and `NumRedelivered` showed 1 at 7.0s, after `AckWait` expired, then went back to 0 once the message was acked and the floor jumped to 17. At the end, `delivered` is 41 for 40 jobs: the extra one is the redelivery.

## The HTTP monitoring endpoint

If the server runs with an HTTP monitoring port, you can read the same numbers without a client. With the embedded server started with `HTTPPort: 8222` and 5 unconsumed messages in the stream, I ran `curl 'localhost:8222/jsz?consumers=true'`. In the JSON, the consumer under stream `JOBS` showed `num_pending` 5, `num_ack_pending` 0 and `num_redelivered` 0. That is handy for Prometheus-style scraping or a quick check from the shell.

## A few things to watch

- Alert on `NumPending` growing over time, not on a single high value. Bursts are normal, a steadily rising line is the problem.
- A growing `NumAckPending` with a flat `AckFloor` means workers are stuck or crashing, even if pending looks fine.
- `AckWait` must be longer than your slowest legitimate job, otherwise healthy workers get their messages redelivered to someone else. Use `m.InProgress()` to extend it for long jobs.
- More workers only helps when the work is the bottleneck. Check that the database or API behind the workers can take the extra concurrency.
- `NumRedelivered` showed up for only a moment in my run, so a scrape every few minutes can miss it. Treat it as a hint, not a counter of total retries.

## What's next

Redelivery means a job can run twice, so the next post covers idempotency and what "exactly-once" really means in JetStream: `Nats-Msg-Id`, the duplicate window, and idempotent consumers.
