+++
date = '2027-05-08T10:00:00+03:30'
draft = false
title = 'Circuit breakers and bulkheads'
description = 'A Go circuit breaker built from scratch with an injected clock, plus bulkheads and load shedding, shown with seeded simulations and real counts.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "circuit-breaker", "bulkhead", "resilience", "go"]
cover = { image = "/images/covers/ds-circuit-breaker-bulkhead.png", alt = "Circuit breakers and bulkheads", hiddenInSingle = true }
+++

[The previous post](/posts/ds-timeouts-retries-backoff/) ended with retries that wait politely. Politeness does not help when the dependency stays sick: callers pile up behind it until they are sick too, which is a {{< term "cascading-failure" "cascading failure" >}}. A {{< term "circuit-breaker" "circuit breaker" >}} stops calling for a while, and a {{< term "bulkhead" "bulkhead" >}} limits how much of your capacity one dependency can take. See also [concurrency patterns](/posts/go-concurrency-patterns/).

> Honest labelling: all of this is Go 1.26 on one machine. Time is fake "ticks" from an injected clock, randomness is seeded, and I show counts only, no timings. It is a simulation, not a real network.

## The state machine

Closed passes calls and counts consecutive failures. At the threshold it goes open and rejects instantly. After `OpenFor` ticks it goes half-open and lets a few probes through: success closes it, one failure reopens it with a fresh timer. The clock is a `func() int64`, so the tests never sleep. They are table-driven and pass with `go test -race`.

```go
func (b *Breaker) Allow() bool   // false means fail fast
func (b *Breaker) Record(ok bool)
```

A scripted run (threshold 3, open 10 ticks, one probe, dependency down until tick 24):

```
  tick   4  closed    -> open
  tick  14  open      -> half-open
  tick  14  half-open -> open
  tick  24  open      -> half-open
  tick  24  half-open -> open
  tick  34  open      -> half-open
  tick  34  half-open -> closed
  trips=3 rejected=12
```

I only implemented consecutive failures. A failure rate over a sliding window is the other common rule; I did not build it.

## Why you want it

5 requests per tick for 120 ticks; the dependency is slow during ticks 20 to 79. Each in-flight call is a parked goroutine. A client timeout of 10 ticks ends a slow call as failed.

```
  no breaker, no timeout       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak=150 mean=77.5, goroutines peak=150, trips=0
  no breaker, timeout 10       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak= 50 mean=27.5, goroutines peak= 50, trips=0
  breaker, timeout 10          reached-dependency=273 ok=216 failed= 52 fallback=327 | in-flight peak= 50 mean=6.2, goroutines peak= 50, trips=3
```

Without any bound, in-flight work grows with the slowness. The timeout caps it. The breaker has the same peak, because it learns only after the first timeouts, but the mean falls from 27.5 to 6.2 and 327 requests got the fallback (a cached or default answer) without touching the dependency. Fewer ok responses at the end (216 vs 295) is the price: the breaker also refused some calls while the dependency was healthy again, until a probe succeeded. The simulation does not model the dependency recovering faster when relieved; I did not measure that.

## Bulkheads and load shedding

A is slow (30 ticks per call, 2 requests per tick), B is healthy (1 tick, 3 per tick). B has 300 requests. Clients give up after waiting 10 ticks. {{< term "load-shedding" "Shedding" >}} means a full pool answers 503 or 429 at once.

```
  shared 20, unbounded queue         B: ok= 27 shed=  0 gave-up=240 | A: ok= 79 shed=  0 gave-up=100 | max queue=149
  shared 20, shed at once            B: ok= 26 shed=274 gave-up=  0 | A: ok= 80 shed=120 gave-up=  0 | max queue=0
  shared 20, queue limit 10          B: ok= 80 shed=201 gave-up= 15 | A: ok= 74 shed=105 gave-up= 15 | max queue=10
  separate 10 + 10, shed at once     B: ok=300 shed=  0 gave-up=  0 | A: ok= 40 shed=160 gave-up=  0 | max queue=0
```

In a shared pool A's slow calls hold every worker and B starves. Shedding does not fix that; it just fails quickly. Separate pools (a {{< term "semaphore" "semaphore" >}} per dependency in Go) let all 300 B requests succeed, and A takes its own losses. An unbounded queue is the worst: 240 B requests waited and then were abandoned, and the work was still done for nobody. That is missing {{< term "backpressure" "backpressure" >}}.

## Breaker and retries

Two orderings, 3 attempts, threshold 5, 200 requests, one per tick. "Inside" means each attempt asks the breaker; "outside" means the breaker sees one result per request.

```
  dependency down, retry inside      dependency calls= 14 ok requests=  0 fast-fails=199 trips=10
  dependency down, breaker outside   dependency calls= 42 ok requests=  0 fast-fails=186 trips=10
  flaky 60%, retry inside            dependency calls=169 ok requests= 74 fast-fails=113 trips=6
  flaky 60%, breaker outside         dependency calls=380 ok requests=161 fast-fails=  0 trips=0
```

When the dependency is dead, inside is cheaper (14 calls vs 42), because retries against an open breaker are free failures. When it is merely flaky, inside trips on ordinary noise and turned 113 requests away, while outside rode it out with 161 ok at the cost of 380 calls. In my experience I put the breaker outside for flaky-but-useful dependencies, and never retry on `ErrOpen`. Retrying needs {{< term "idempotency" "idempotent" >}} calls either way.

## What to emit

Metrics: state (a gauge), trips, rejections and fallbacks served. In my experience, alert on "open for longer than N minutes" and on the rejection rate, not on every single trip. A breaker flapping between open and half-open hints at a {{< term "gray-failure" "gray failure" >}}.

In production I would use a library. According to its README, `sony/gobreaker` has closed, open and half-open states, a `MaxRequests` for half-open, an open `Timeout`, a `ReadyToTrip` function and an `OnStateChange` hook. I read the README and did not run it. Hystrix and Resilience4j are, as far as I know, where the pattern became popular in the Java world.

## A few things to watch

- Always give the breaker a fallback or a clear error, or users just see a faster failure.
- A client timeout is still needed; the breaker opens only after failures are seen.
- Count only real dependency failures, not your own validation errors.
- Pool sizes and thresholds need load tests; mine are made up.

## Exercise

Add a failure-rate rule over a sliding window and compare it with the consecutive rule on the flaky scenario.

## What's next

The next post is “Replication and quorums”.
