+++
date = '2026-10-25T10:00:00+03:30'
draft = false
title = 'Multiple workers on one consumer and monitoring lag in JetStream'
seoTitle = 'Scaling Workers and Monitoring JetStream Lag'
description = 'Scale processing by running several workers on one durable JetStream consumer, see what happens when one crashes, and monitor lag with ConsumerInfo.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging", "scaling", "monitoring"]
cover = { image = "/images/covers/nats-jetstream-scaling-lag.png", alt = "Multiple workers on one consumer and monitoring lag in JetStream", hiddenInSingle = true }
+++

One worker is enough as long as messages arrive slower than it can process them. Suppose each job takes 200 milliseconds. One worker finishes 5 jobs per second. If 30 messages arrive at once, the last one is processed 6 seconds later, and if 10 messages arrive every second, the queue never empties. Then two questions come up: how do I add workers without processing anything twice? And how do I find out the queue is backing up before a customer complains? The [previous post](/posts/nats-jetstream-retry-dlq/) left both open.

> Everything below ran against an embedded `nats-server` (v2.15.1, JetStream enabled, temp store dir) and `nats.go` v1.54.0. The original run of this post used Go 1.26; for this rewrite I re-ran everything with Go 1.27. The code is a local example. Times, and which worker gets which message, differ a little on every run.

## Many workers, one durable consumer

The first answer is simple: there is no trick. Every worker binds to the **same** {{< term "durable-consumer" "durable consumer" >}}, and the server hands each message to only one of them. Think of the consumer as one ticket-number dispenser that several counters share: each number is called by only one counter, and there is only one ledger.

Because the consumer is a {{< term "pull-consumer" "pull" >}} consumer, each worker asks for messages itself, and the server only answers requests. The code of each worker:

```go
sub, err := js.PullSubscribe("jobs.new", "workers", nats.Bind("JOBS", "workers"))
// ...
msgs, err := sub.Fetch(1, nats.MaxWait(500*time.Millisecond))
// process msgs[0], then m.Ack()
```

`nats.Bind("JOBS", "workers")` means "attach to the existing consumer named `workers` in the stream named `JOBS`, and do not create anything new".

The demo is one Go file that starts the embedded server, creates the stream `JOBS` and the durable consumer `workers` with `AckExplicitPolicy`, and runs the workers as goroutines. I pick each experiment with an argument.

**Experiment one:** three goroutines (`w1`, `w2`, `w3`), each with its own subscription, each taking 200 milliseconds per job. I published 30 messages. The first six log lines, and the last line the program prints:

```
  0.0s w3 got job-01 (stream seq 1, delivery #1)
  0.0s w1 got job-02 (stream seq 2, delivery #1)
  0.0s w2 got job-03 (stream seq 3, delivery #1)
  0.2s w3 got job-06 (stream seq 6, delivery #1)
  0.2s w1 got job-04 (stream seq 4, delivery #1)
  0.2s w2 got job-05 (stream seq 5, delivery #1)
  ...
deliveries=30 unique=30 pending=0 ackPending=0 redelivered=0
```

Each line says: how many seconds after the start, which worker got which job, the job's sequence number in the stream, and the delivery number (`delivery #1` means the first time). At second zero each of the three workers took one job, and at 0.2 s the next three. The last line says 30 deliveries happened, for 30 different jobs (`unique`), nothing is left, and nothing was redelivered. So no job ran twice.

The whole batch took about 2 seconds: 30 × 0.2 s divided by 3 workers. One worker alone would have needed 6. There is also a subtle point in the log: the order is not strict. At 0.2 s job 6 started before job 4.

## A worker dies mid-job

Now the worst case. I set `AckWait` to 2 seconds, published 10 jobs, and made `w2` "crash" on its second message, that is, stop without acking. The full log:

```
  0.0s w1 got job-02 (stream seq 2, delivery #1)
  0.0s w2 got job-01 (stream seq 1, delivery #1)
  0.0s w3 got job-03 (stream seq 3, delivery #1)
  0.1s w1 got job-06 (stream seq 6, delivery #1)
  0.1s w2 got job-04 (stream seq 4, delivery #1)
  0.1s w2 CRASHED while holding job-04 (no ack)
  0.1s w3 got job-05 (stream seq 5, delivery #1)
  0.2s w1 got job-07 (stream seq 7, delivery #1)
  0.2s w3 got job-08 (stream seq 8, delivery #1)
  0.3s w3 got job-09 (stream seq 9, delivery #1)
  0.3s w1 got job-10 (stream seq 10, delivery #1)
  2.1s w3 got job-04 (stream seq 4, delivery #2)
deliveries=11 unique=10 pending=0 ackPending=0 redelivered=0
```

(Which worker crashes, and on which job, differs from run to run. In this run it was `w2` and `job-04`.)

`w2` took job 4 and died without acking. The other jobs finished by 0.3 s. Then silence until 2.1 s. The arithmetic is simple: the job was delivered at about 0.1 s and `AckWait` is 2 s, so 0.1 + 2 = 2.1. After that time the server assumed the worker was dead and gave the same message to a worker that was still alive (`w3`) as `delivery #2`. The last line: 11 deliveries for 10 different jobs. The extra delivery is the redelivery.

That is the entire safety net: no ack means the message is not lost, it comes back. Two consequences:

- **Delivery is {{< term "at-least-once-delivery" "at-least-once" >}}.** Each message arrives one or more times. The crashed worker may have done half the work or all of it, so processing must be safe to repeat.
- **Ordering across workers is not guaranteed.** `job-04` was processed long after `job-10`. If you need strict order per key, you need a different design, such as one consumer with one worker, or splitting work by subject.

## Reading lag with ConsumerInfo

Now the second question: how do we know the queue is backing up? We ask the server about the consumer. My tiny monitor is just a ticker that calls this every second:

```go
i, err := js.ConsumerInfo("JOBS", "workers")
fmt.Printf("pending=%d ackPending=%d redelivered=%d delivered=%d ackFloor=%d\n",
    i.NumPending, i.NumAckPending, i.NumRedelivered,
    i.Delivered.Consumer, i.AckFloor.Consumer)
```

What each number means:

- `NumPending`: messages in the stream that have not been delivered to the consumer yet. This is the number to alert on for "lag".
- `NumAckPending`: delivered but not acked yet, that is, in the workers' hands right now. With two busy workers it is 2.
- `NumRedelivered`: messages that are being redelivered.
- `Delivered.Consumer`: the sequence number of the last delivery, from the consumer's point of view. It also counts redeliveries.
- `AckFloor.Consumer`: the number up to which every delivery has been acked.

For this run I used two slow workers (500 milliseconds per job). I published 40 jobs at 1.5 s, set `AckWait` to 3 seconds, and made `w2` crash on its 5th message. The output:

```
  1.0s pending=0   ackPending=0  redelivered=0  delivered=0   ackFloor=0
  1.5s publishing 40 jobs
  2.0s pending=38  ackPending=2  redelivered=0  delivered=2   ackFloor=0
  3.0s pending=34  ackPending=2  redelivered=0  delivered=6   ackFloor=4
  3.6s w2 CRASHED while holding job-09 (no ack)
  4.0s pending=30  ackPending=2  redelivered=0  delivered=10  ackFloor=8
  5.0s pending=28  ackPending=2  redelivered=0  delivered=12  ackFloor=8
  6.0s pending=26  ackPending=2  redelivered=0  delivered=14  ackFloor=8
  7.0s pending=25  ackPending=1  redelivered=1  delivered=16  ackFloor=8
  8.0s pending=23  ackPending=1  redelivered=0  delivered=18  ackFloor=17
  9.0s pending=21  ackPending=1  redelivered=0  delivered=20  ackFloor=19
 ...
 19.0s pending=1   ackPending=1  redelivered=0  delivered=40  ackFloor=39
 20.0s pending=0   ackPending=0  redelivered=0  delivered=41  ackFloor=41
```

(I left out the lines for 10 to 18 seconds for brevity; they follow the same pattern, with `pending` dropping by 2 each second. The program kept printing the same zero line until second 25.)

Reading from the top:

- At 1.5 s, 40 messages suddenly arrive. At 2.0 s `pending` is 38: 40 messages minus the 2 that are in the two workers' hands (`ackPending=2`).
- With two workers, each doing 2 jobs per second (500 ms per job), the queue drains at 4 messages per second: 38, 34, 30.
- At 3.6 s `w2` crashes holding `job-09`. From then on only `w1` works, and `pending` drops by 2 per second (30, 28, 26).
- The crash shows in two places. First, `AckFloor` stayed at 8, because the stuck message was never acked and the floor cannot move past it. Second, `ackPending` stayed at 2 (one for `w1`'s current job, one for `w2`'s stuck message).
- `AckWait` is 3 s, so the stuck message's deadline passes at about 3.6 + 3 = 6.6 s. At 7.0 the `redelivered` counter is 1 and `ackPending` has gone from 2 to 1: the server no longer counts the message as in someone's hands and is waiting to redeliver it. At 8.0 `redelivered` is back to 0 and `AckFloor` jumped from 8 to 17, meaning the redelivered message was acked and every delivery up to 17 is now confirmed. I did not measure exactly when between 7 and 8 seconds this happened.
- At the end `delivered` is 41 for 40 jobs: the one extra delivery.

## The same numbers over HTTP

If the server runs with an HTTP monitoring port, you can read the same numbers without any client. I started the embedded server with a free HTTP port, put 5 messages in the stream that nobody reads, and ran:

```bash
curl 'localhost:<port>/jsz?consumers=true'
```

In the returned JSON, the consumer of the stream `JOBS` showed `num_pending` 5, `num_ack_pending` 0 and `num_redelivered` 0. That is handy for Prometheus-style scraping or a quick check from the shell.

## Reading the numbers right

- Alert on `NumPending` **growing** over time, not on a single high value. Bursts are normal; a steadily rising line is the problem.
- A growing `NumAckPending` with a flat `AckFloor` means workers are stuck or crashing, even if pending looks fine.
- {{< term "ack-wait" "AckWait" >}} must be longer than your slowest legitimate job. Otherwise a healthy worker's message is given to another worker mid-job, and the work runs twice. For long jobs, according to the `nats.go` docs, you can extend the deadline with `m.InProgress()`.
- More workers help only when the work itself is the bottleneck. Check that the database or API behind the workers can take the extra concurrency.
- `NumRedelivered` showed up for only a moment in my run, so a monitor that reads every few minutes can miss it. Treat it as a hint, not a count of all retries.

## What's next

Redelivery means a job can run twice. Idempotency and the meaning of exactly-once in JetStream deals with exactly that: `Nats-Msg-Id`, the duplicate window, and idempotent consumers.
