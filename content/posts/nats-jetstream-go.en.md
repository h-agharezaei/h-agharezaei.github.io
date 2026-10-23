+++
date = '2026-10-18T12:00:00+03:30'
draft = false
title = 'A Simple Publisher and Worker with NATS JetStream in Go'
seoTitle = 'Publisher and Worker with NATS JetStream in Go'
description = 'Building a pair of Go services with Docker Compose and NATS JetStream that process messages through a durable consumer.'
categories = ["Go"]
series = ["NATS JetStream"]
tags = ["go", "nats", "jetstream", "messaging"]
cover = { image = "/images/covers/nats-jetstream-go.png", alt = "A Simple Publisher and Worker with NATS JetStream in Go", hiddenInSingle = true, hiddenInList = true }
+++

When I want to really understand a concept, I build the smallest runnable example of it. This time it was **NATS JetStream**. The result is [go-nats-demo](https://github.com/h-agharezaei/go-nats-demo): a publisher, a worker and NATS itself, all wired together with Docker Compose.

## Why JetStream?

Core NATS only delivers messages to subscribers that are connected at that moment. If the worker is down, the message is gone. **JetStream** adds persistence on top of NATS: messages are stored in a stream, and consumers can read them later and acknowledge them.

## Layout

```
go-nats-demo/
├── docker-compose.yml
├── publisher/   (Dockerfile + main.go)
└── worker/      (Dockerfile + main.go)
```

- **NATS** with JetStream and the monitoring dashboard on port `8222`
- **Publisher** sends a message to `events.created` every 2 seconds
- **Worker** reads messages, logs them and acks

## Connecting with retry

Docker Compose doesn't guarantee NATS is up before our services. So both services try to connect up to 10 times, 2 seconds apart:

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

## Publisher: create the stream and publish

The publisher creates the stream if it doesn't exist, then publishes in a loop:

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

## Worker: a pull consumer with a durable name

The key detail is that the worker has a durable name (`worker-consumer`). JetStream keeps this consumer's read position, so if the worker restarts it resumes where it left off and receives the messages it missed:

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

`Fetch(10, ...)` pulls up to 10 messages at once and `Ack()` tells JetStream processing is done. A message that isn't acked gets redelivered.

## Running it

```bash
git clone git@github.com:h-agharezaei/go-nats-demo.git
cd go-nats-demo
docker compose up --build
```

Then open the NATS dashboard at `http://localhost:8222/`. To see the durable consumer in action, stop only the worker service, start it again and watch the logs.

## Next steps

This example is intentionally simple. For real workloads I want to dig into retry policy and `MaxDeliver`, dead-lettering, multiple workers on one consumer, and monitoring processing lag.
