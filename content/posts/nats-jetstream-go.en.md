+++
date = '2026-10-18T12:00:00+03:30'
draft = false
title = 'A Simple Publisher and Worker with NATS JetStream in Go'
seoTitle = 'Publisher and Worker with NATS JetStream in Go'
description = 'Building a pair of Go services with Docker Compose and NATS JetStream that process messages through a durable consumer.'
contentType = 'tutorial'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging"]
cover = { image = "/images/covers/nats-jetstream-go.png", alt = "A Simple Publisher and Worker with NATS JetStream in Go", hiddenInSingle = true }
+++

Imagine a service that sends a message after every purchase: "order 12 was placed". Another service, a worker, has to receive it and create the invoice. The simplest design is a worker that connects to a message server and waits. But what if the worker is restarting at the exact moment the message arrives? In many messaging systems the answer is: the message is gone, because nobody was listening.

When I want to really understand a concept, I build the smallest runnable example of it. This time it was **NATS JetStream**, because it answers exactly this question: it stores the message, so the worker can come back whenever it likes and continue from where it stopped. The result is [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo): a publisher, a worker and NATS itself, all wired together with Docker Compose.

This is the first post of the series. It does not assume you know NATS or JetStream, only a little Go.

> The publisher and worker code is from the go-nats-demo project. I have no Docker on this machine, so I did not run the Compose file. Instead I ran the same code with Go 1.27 and `nats.go` v1.54.0 against an embedded `nats-server` (v2.15.1) on 127.0.0.1 and a random port. The only code differences: the server address came from the command line, and the messages were `event-1`, `event-2`, ... instead of timestamps, to make the output easier to read. The outputs below are from that run; the clock times differ on every run.

## Why JetStream?

Plain NATS works like a public address system. A message sent to a **subject** (a dotted name such as `events.created`) reaches only the programs that are listening to that subject at that moment. If the worker is down, the message is lost. That is fast and simple, and often exactly what you want, but it is not enough for "the invoice must be created".

{{< term "jetstream" "JetStream" >}} is the persistence layer on top of NATS. It brings three new ideas:

- **stream**: a named log that stores, on disk, the messages of one or more subjects. Every stored message gets a sequence number: 1, 2, 3, and so on.
- **consumer**: a named reader of a stream. The server remembers how far this reader has read.
- **{{< term "acknowledgement" "ack" >}}** (acknowledgement): the worker's reply after it has finished a message, meaning "I did this one". Until the ack arrives, the server assumes the message is not done and sends it again.

So the key difference is the order of events: the message is stored in the stream first, and the consumer reads it from there. If the worker is down, the message simply waits in the stream.

## Project layout

```
go-nats-demo/
├── docker-compose.yml
├── publisher/   (Dockerfile + main.go)
└── worker/      (Dockerfile + main.go)
```

- **NATS** with JetStream enabled and the monitoring port `8222`. That port serves a few JSON pages about the server's state, not a graphical dashboard.
- **Publisher** sends a message to `events.created` every 2 seconds.
- **Worker** reads messages, logs them and acks.

## Connecting with retry

In Docker Compose there is no guarantee that NATS is ready when our services start. `depends_on` only controls the start order, not readiness. So both services try to connect up to 10 times, 2 seconds apart:

```go
func connectNATS(url string) *nats.Conn {
    for i := 0; i < 10; i++ {
        nc, err := nats.Connect(url)
        if err == nil {
            return nc
        }
        log.Println("Waiting for NATS to be ready...", err)
        time.Sleep(2 * time.Second)
    }
    log.Fatal("Failed to connect to NATS after 10 attempts")
    return nil
}
```

(The project has the same logic with a bit more logging.)

## Publisher: create the stream and publish

The publisher creates the stream first. It is called `EVENTS` and keeps only the messages of the subject `events.created`. Then it publishes one message every 2 seconds in a loop:

```go
js, _ := nc.JetStream()

_, err := js.AddStream(&nats.StreamConfig{
    Name:     "EVENTS",
    Subjects: []string{"events.created"},
})
if err != nil && err != nats.ErrStreamNameAlreadyInUse {
    log.Fatal(err)
}

for {
    msg := []byte(time.Now().Format(time.RFC3339))
    if _, err := js.Publish("events.created", msg); err != nil {
        log.Println("publish error:", err)
    }
    time.Sleep(2 * time.Second)
}
```

`js.Publish` differs from a plain NATS publish in one important way: it does not return until the server has stored the message and sent a confirmation. So if no error comes back, the message is in the stream.

## Worker: a durable pull consumer

Now the main part. The worker attaches to the stream and gets a consumer named `worker-consumer`:

```go
sub, err := js.PullSubscribe("events.created", "worker-consumer")
if err != nil {
    log.Fatal(err)
}

for {
    msgs, err := sub.Fetch(10, nats.MaxWait(5*time.Second))
    if err != nil && err != nats.ErrTimeout {
        log.Println("fetch error:", err)
        continue
    }
    for _, m := range msgs {
        log.Println("Received:", string(m.Data))
        m.Ack()
    }
}
```

Two words in this code need explanation.

First, {{< term "durable-consumer" "durable" >}}. Because the consumer has a name (`worker-consumer`), the server keeps its read position even while no worker is connected. If the worker restarts, it comes back under the same name and continues from where it stopped.

Second, {{< term "pull-consumer" "pull" >}}. The worker asks for messages; the server does not push them. `Fetch(10, ...)` means "give me up to 10 messages, but do not wait longer than 5 seconds". If no message arrives in that time, `ErrTimeout` is returned. That is why our loop does not treat `ErrTimeout` as an error: it only means there is nothing right now.

After each message, `m.Ack()` tells the server the work is done. A message that is not acked is delivered again.

## Seeing "durable" in action

The claim "it continues from where it stopped" should be seen, not just believed. I started the server and the publisher, and the worker a moment later. After about 7 seconds I stopped the worker, waited 7 seconds and started it again. The logs were these (I added the `---` lines as markers):

```
20:48:58 Published: event-1
20:48:58 Received: event-1
20:49:00 Published: event-2
20:49:00 Received: event-2
20:49:02 Published: event-3
20:49:02 Received: event-3
20:49:04 Published: event-4
20:49:04 Received: event-4
--- worker stopped
20:49:06 Published: event-5
20:49:08 Published: event-6
20:49:10 Published: event-7
20:49:12 Published: event-8
--- worker restarted
20:49:12 Received: event-5
20:49:12 Received: event-6
20:49:12 Received: event-7
20:49:12 Received: event-8
20:49:14 Published: event-9
20:49:14 Received: event-9
```

Before `worker stopped`, each message is received the moment it is published. While the worker is away, the publisher keeps publishing events 5 to 8, and none of them has a `Received` line. As soon as the worker returns, all four arrive within the same second, in order, in one `Fetch(10)`. After that, normal behaviour resumes.

To check that the server really held the position, I asked it for the consumer's state. These two lines were printed after the worker had been away for 7 seconds and before it returned:

```
stream EVENTS: messages=8 first=1 last=8
consumer worker-consumer: delivered=4 ackFloor=4 pending=4 ackPending=0 ackPolicy=AckExplicit ackWait=30s maxDeliver=-1
```

The stream holds eight messages. The consumer has been delivered and acked up to number 4 (`delivered=4`, `ackFloor=4`), and 4 messages are waiting (`pending=4`). The worker does not need to remember anything: the position lives on the server. After the worker returned, the same query printed `delivered=10 ackFloor=10 pending=0`.

The last two values on the consumer line are interesting too. We created the consumer only by name, so the server filled in defaults. `ackWait=30s` means that if no ack arrives for 30 seconds the message comes again, and `maxDeliver=-1` means there is no limit on the number of deliveries. That "no limit" is a problem the next post solves.

## Running it with Docker Compose

On your machine it is (I did not run this step, because I have no Docker):

```bash
git clone git@github.com:h-agharezaei/go-nats-demo.git
cd go-nats-demo
docker compose up --build
```

Then open the NATS monitoring page at `http://localhost:8222/`. To see the durable consumer, stop only the worker service, wait a few seconds and start it again, like I did above.

## Where this example is weak

The example is intentionally simple, so a few things make it unfit for real work:

- **Start order matters.** Only the publisher creates the stream. When I started the worker against an empty server before the publisher, it connected and then stopped with `nats: no stream matches subject`, because `PullSubscribe` found no stream yet. In Compose, which one comes up first is not guaranteed.
- **The worker acks everything.** Real work can fail, and this worker has no plan for failure.
- **No delivery limit.** As you saw, `maxDeliver=-1`.
- **A `Fetch` error is retried without a pause.** In the worker loop, any error other than a timeout immediately calls `Fetch` again. If the error persists, the loop spins at full speed and floods the log.

## What's next

This worker acks every message and has no plan for a message that keeps failing. Retry and Dead-Letter Queues in NATS JetStream with Go shows how to limit the number of attempts, space them out, and set the "burned" messages aside.
