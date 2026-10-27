+++
date = '2027-05-04T10:00:00+03:30'
draft = false
title = 'Timeouts, retries and backoff with jitter'
description = 'Timeouts and retries done right: a real loopback client, a seeded retry-storm simulation, retry budgets, deadline propagation and hedged requests in Go.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "retries", "backoff", "timeouts"]
cover = { image = "/images/covers/ds-timeouts-retries-backoff.png", alt = "Timeouts, retries and backoff with jitter", hiddenInSingle = true }
+++

A {{< term "deadline" "timeout" >}} tells you only that you do not know ([why distributed systems are hard](/posts/ds-why-distributed-is-hard/)), so the usual reaction is to retry. In the previous post, [logical clocks](/posts/ds-logical-clocks/), we ordered events without trusting time; here we decide what to do when a call goes quiet. Retries are the cure and also a classic cause of outages. They only make sense for operations that are safe to repeat ([idempotency in JetStream](/posts/nats-jetstream-idempotency/)), and they interact with [rate limiting](/posts/go-rate-limiting-caching/).

> Honest labelling: section 1 is a real HTTP client and server on loopback (Go 1.26, `httptest`), with seeded failures. Sections 2, 3 and 4 are **simulations** with a simulated clock and seeded randomness; a simulated network is not a real one. The machine was busy, so I show counts, never timings. Demo: a local example, not a repo.

## 1. A real client against a flaky server

The server fails by seeded draw: 15% `503` with `Retry-After: 1`, 15% too slow for the client's 100 ms per-attempt timeout, 10% connection reset, the rest `200`. The client wraps each attempt in `context.WithTimeout`, sits under one overall deadline, retries at most 5 times and sleeps with jittered backoff. A `403` is never retried.

```
logical requests: 31, attempts: 52, succeeded: 30, failed: 0
  HTTP 403 (not retried)       1
  HTTP 503                     8
  context deadline exceeded    6
  transport error              7
sample: Get "http://127.0.0.1:PORT/item/1": context deadline exceeded
sample: Get "http://127.0.0.1:PORT/item/3": read tcp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection reset by peer
```

The two error strings mean different things: a deadline means the client gave up (the server may still be working), a reset means the connection was torn down. The rules I follow:

- Retry only idempotent operations, or ones carrying an idempotency key.
- Retry only errors that may go away: timeouts, connection errors, `5xx`. Never `4xx`.
- Honour `Retry-After` if it is longer than your own delay.
- Bound everything: attempts per call and one overall deadline.

## 2. The retry storm (simulation)

The {{< term "retry-storm" "retry storm" >}}: 1000 clients, a server that handles 300 requests per tick, an outage on ticks 1-3 where every request fails, and rejection of anything above capacity. A client gives up after 12 tries. Formulas are as I remember them from the AWS Architecture Blog article "Exponential Backoff And Jitter" (details hedged, my own implementation): base 2, cap 32; {{< term "exponential-backoff" "exponential" >}} `min(cap, base*2^n)`; full {{< term "jitter" "jitter" >}} random in `[0, that]`; equal jitter half plus random half; decorrelated `min(cap, random(base, prev*3))`.

```
strategy           requests   served  gaveUp  lastTk  peak
immediate              3800     1000       0       6   700
fixed 4                1900     1000       0       9   500
exp, no jitter         1900     1000       0      13   500
exp, full jitter       2254     1000       0      27   586
exp, equal jitter      1979     1000       0      11   500
decorrelated           1881     1000       0      12   500

exp, no jitter:   500 500 0 0 200 500 0 0 0 0 0 0 0 200
exp, full jitter: 500 586 247 221 191 158 65 57 58 64 55 22 1 6 5 2 4 ...
```

Immediate retries send nearly four requests per client. Without jitter the clients stay synchronised: waves of 500, 200, 500, 200 with empty ticks between. Full jitter turns the waves into a slope, at the cost of a longer tail (tick 27) and more total requests here. So jitter is not "fewer requests"; it is smoother load. In my experience that smoothness is what lets a recovering server actually recover. The numbers depend on my parameters; do not read them as general rates.

## 3. Amplification and the retry budget (simulation)

Three layers, each making 3 attempts, and a bottom service that is down. Each layer multiplies: 3 x 3 x 3 = 27 requests reach the bottom per user call. A {{< term "retry-budget" "retry budget" >}} gives each layer a token bucket that earns 0.1 token per request and spends 1 per retry (cap 10).

```
bottom fails 100%, budget=false: top calls 1000, ok 0, requests per layer [3000 9000 27000], last layer 27.00x
bottom fails 100%, budget=true : top calls 1000, ok 0, requests per layer [1222 1493 1824], last layer 1.82x
bottom fails  50%, budget=false: top calls 1000, ok 1000, requests per layer [1003 1145 1995], last layer 2.00x
bottom fails  50%, budget=true : top calls 1000, ok 760, requests per layer [1137 1305 1510], last layer 1.51x
```

The budget caps the damage in a full outage (27x down to 1.82x) but costs successes under partial failure (760 of 1000 here). That is the trade: retry less, protect the dependency. The usual advice is to retry in one layer only.

## 4. Deadline budgets and hedging

Give the whole request one deadline and pass the **remaining** time down. In a simulated chain where each hop spends 50 ms of a 300 ms budget:

```
gateway  sees remaining deadline 300 ms
orders   sees remaining deadline 250 ms
stock    sees remaining deadline 200 ms
db       sees remaining deadline 150 ms
```

With a fixed 300 ms per hop, the database can keep working long after the caller left. gRPC carries this as a `grpc-timeout` header ([gRPC over HTTP/2](/posts/net-grpc-over-http2/)). Too-long timeouts also hold scarce resources such as connections ([connection pooling](/posts/db-connection-pooling/)).

A {{< term "hedged-request" "hedged request" >}} sends a second copy after 20 ms and takes the first reply. Simulated latencies, 95% around 10 ms and 5% 200-300 ms, 10000 requests:

```
hedging: 10000 requests, >100 ms: 502 without hedge, 25 with hedge; extra requests sent: 502 (5.0%)
```

Slow outliers dropped from 502 to 25, for 5% extra load. The simulation assumes independent latencies; real slowness is often correlated.

## A few things to watch

- Every retry loop needs a cap on attempts and an overall deadline.
- Add jitter to every backoff; I did not measure a real production benefit here.
- Retrying at several layers multiplies; budget or centralise it.
- A timeout is "unknown": make the operation idempotent first.
- Hedging needs safe, repeatable calls and spare capacity.

## Exercise

In `sim.go` set `capacity` to 150 and `outageTo` to 5. Which strategy gives up clients first? Then add a `Retry-After` rule to the simulated server.

## What's next

The next post is “Circuit breakers and bulkheads”.
