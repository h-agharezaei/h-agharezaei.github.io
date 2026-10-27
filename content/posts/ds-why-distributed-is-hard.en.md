+++
date = '2027-04-15T10:00:00+03:30'
draft = false
title = 'Why distributed systems are hard'
description = 'Why distributed systems are hard: partial failure, retries, clock skew and slow nodes, shown with seeded Go simulations and one real loopback demo.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "partial-failure", "clocks", "failure-detection"]
cover = { image = "/images/covers/ds-why-distributed-is-hard.png", alt = "Why distributed systems are hard", hiddenInSingle = true }
+++

This is the first post of a new series about distributed systems. I have used queues, replicas and RPC for years, and most of my worst bugs came from the same few facts, so I want to start by naming them. Earlier posts touched them from one side: [idempotency in JetStream](/posts/nats-jetstream-idempotency/), [the outbox pattern](/posts/go-outbox-pattern-nats/) and [replication](/posts/db-replication-streaming/). Here is the map.

> Honest labelling: sections 1, 2, 4 and 6 are **simulations** in one process with seeded randomness (Go 1.26). A simulated network is not a real one; the numbers show the shape of the problem, not production rates. Section 5 uses real processes and real TCP, but only on loopback. I show counts, never timings.

## 1. Partial failure

In one process a call either returns or the program dies. Across a network, one side can fail while the other lives, so the caller is left guessing. This is {{< term "partial-failure" "partial failure" >}}. My simulated `Withdraw(10)` over 1000 seeded calls (8% requests lost, 4% server crashes before applying, 15% replies lost, 2% duplicated requests):

```
outcome                          count  client sees   money moved
ok                                 702  reply         yes
request lost                        86  timeout       no
server crashed before applying      33  timeout       no
reply lost after applying          179  timeout       yes

timeouts: 298, requests applied by server: 897, replies received: 702
balance mismatch: client believes 7020 withdrawn, server withdrew 8970
```

Three different realities produce the same "timeout". The client cannot tell the first two (nothing happened) from the third (it happened). Hence the mismatch.

## 2. Retries without idempotency

The obvious fix is to retry. Same simulation, up to 8 attempts per withdrawal, with and without an idempotency key (the server remembers keys it has applied; see {{< term "idempotency" "idempotency" >}}):

```
no key  : logical=1000 confirmed=1000 retries=338 server applied=1212 withdrawn=12120 expected=10000 extra=2120
with key: logical=1000 confirmed=1000 retries=338 server applied=1000 withdrawn=10000 expected=10000 extra=0
```

Every client was told "success", yet without a key the customer lost 2120 extra. With a key the balance is exact. A test with `go test -race` checks that concurrent callers never apply a key twice.

## 3. The well-known fallacies

There is a well-known list called the fallacies of distributed computing (usually credited to Peter Deutsch and colleagues at Sun, with James Gosling often named for the eighth; I am hedging on exact attribution). The series revisits each row:

| Fallacy | Where it bites |
|---|---|
| The network is reliable | sections 1 and 2 |
| Latency is zero | section 6 |
| Bandwidth is infinite | big payloads, replication lag |
| The network is secure | trust between nodes |
| Topology doesn't change | membership, failover |
| There is one administrator | upgrades, versions |
| Transport cost is zero | serialisation, chatty APIs |
| The network is homogeneous | mixed clients and versions |

## 4. Clocks

Go's `time.Now()` holds a wall reading and a {{< term "monotonic-clock" "monotonic" >}} reading. I printed the shape of `String()` with digits replaced by `N`:

```
has monotonic reading: true
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN m=+N.NNNNNNNNN
has monotonic after Round(0): false
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN
```

`Round(0)` strips the `m=` part, so durations between such values use the wall clock. Use monotonic time for durations. For ordering events across machines, clocks are the problem: with {{< term "clock-skew" "clock skew" >}}, {{< term "last-write-wins" "last write wins" >}} breaks. Simulated offsets: n1 0, n2 -300 ms, n3 +500 ms.

```
true t=1000ms  write x="A" via n1  stamp=1000
true t=1100ms  write x="B" via n2  stamp=800
after replication (keep highest stamp): x="A"  <- B was written later but lost
```

That is why later posts talk about logical clocks.

## 5. A real failure, on loopback

Two Go processes over TCP on `127.0.0.1`. The server applies the withdrawal (writes a file), then waits 3 seconds before replying. Ports are masked as `PORT`.

```
A) nobody listening:
client error: dial tcp 127.0.0.1:PORT: connect: connection refused
B) server SIGKILLed mid-call (after it applied the withdrawal):
client error: EOF
   balance file on the server side: 90
C) server frozen with SIGSTOP (alive but silent), client deadline 800 ms:
client error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
```

Three real error strings. In B the client saw only `EOF` while the money had moved. In C the process is alive but silent; the {{< term "deadline" "deadline" >}} is the only signal.

## 6. It is never just a crash

A {{< term "failure-detector" "failure detector" >}} suspects a node when {{< term "heartbeat" "heartbeats" >}} stop for longer than a timeout. Simulated: 60 seconds, a heartbeat every 100 ms, a healthy node, a node 5x slower, and a node that dies at 30 s:

```
timeout   healthy  slow(5x)  dead-node detection delay
  150 ms      24       120      66 ms
  250 ms       0        15     166 ms
  500 ms       0         0     416 ms
 1000 ms       0         0     916 ms
 2000 ms       0         0    1916 ms
requests with a 100 ms deadline that time out: healthy 2.1%, slow(5x) 52.5%
```

A short timeout flags healthy nodes; a long one detects death late. Worse, at 500 ms the slow node is never suspected, yet over half its requests miss a 100 ms deadline. That is a {{< term "gray-failure" "gray failure" >}}: in my experience, harder than a clean crash.

## A few things to watch

- A timeout means "unknown", not "failed".
- Retries need idempotency, or they multiply damage.
- Do not order events across machines by wall time.
- Health is not the same as heartbeat.
- Simulations teach shape; they do not replace real tests.

## Exercise

Change the seed and the loss rates in `pickFate`. Does the mismatch grow linearly? Then add a key that expires and see the double-apply return.

## What's next

The next post is “CAP and PACELC, correctly”.
