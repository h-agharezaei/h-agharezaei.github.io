+++
date = '2027-06-03T10:00:00+03:30'
draft = false
title = 'Distributed rate limiting'
description = 'Distributed rate limiting in Go: why N local limiters over-admit, window algorithms compared, an exact NATS KV compare-and-set limiter, and failure modes.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "rate-limiting", "nats", "kv", "go"]
cover = { image = "/images/covers/ds-distributed-rate-limiting.png", alt = "Distributed rate limiting", hiddenInSingle = true }
+++

[The previous post](/posts/ds-service-discovery-load-balancing/) spread requests over many replicas. That breaks a limit that worked on one machine: the single-process token bucket from [rate limiting and caching in Go](/posts/go-rate-limiting-caching/) now exists N times. Here "100 requests per second per client" must mean 100 across the fleet.

> Honest labelling: everything except the NATS section is a seeded Go 1.26 **simulation** on one machine, with counts instead of timings. The NATS section is real: an embedded nats-server on loopback. I did not run Redis.

## N local limiters

Four clients each offer about 500 req/s for 10 s. Every replica has its own {{< term "token-bucket" "token bucket" >}} per client, 100 req/s, burst 10. The ideal total is about 4040.

```
N=1  sticky=true  offered=19875 allowed=4036
N=3  sticky=true  offered=19875 allowed=4036
N=3  sticky=false offered=19922 allowed=12097
N=10 sticky=false offered=19922 allowed=19922
```

With random routing the effective limit is N times larger, and at N=10 nothing is limited. Sticky routing by client key (see [consistent hashing](/posts/algo-bloom-filter-consistent-hashing/)) keeps each client's counter on one replica, at the price of {{< term "hot-key" "hot keys" >}}.

## The algorithms on the same traffic

Same 495 requests, limit 100 per 1000 ms: noise, a 100-request burst just before the boundary at 1000 ms, one just after, and one mid-window.

```
algorithm                 allowed   max/1000ms in[950,1050) diff-exact
fixed window                  436          199          180        135
sliding log (exact)           351          100           81          0
sliding counter               355          104           84         10
token bucket (cap 20)         247           49           29        124
leaky meter (cap 20)          247           49           29        124
```

The fixed window let 180 requests through in 100 ms and 199 within one second, almost twice the limit, because the counter resets at the boundary. The sliding log is exact but stores up to 100 timestamps per key. The {{< term "sliding-window" "sliding window counter" >}} keeps two numbers and made 10 different decisions out of 495, with at most 104 in a second. Token bucket and leaky meter decided identically (tested). Both allow bursts, so use them when bursts are fine.

| | memory per key | accuracy | burst behaviour |
|---|---|---|---|
| fixed window | 2 numbers | up to 2x at boundary | double burst |
| sliding log | O(limit) | exact | none |
| sliding counter | 3 numbers | approximate | small error |
| token / leaky | 2 numbers | exact for its model | capacity allowed |

## A shared store with compare-and-set

Now the real run. A JetStream KV bucket (see [KV and Object Store in NATS](/posts/nats-kv-object-store/)) holds one counter. Three goroutines, each with its own connection, make 600 attempts against a limit of 1000. The naive version reads then writes. The CAS version uses `Update` with the revision it read, and retries when it fails, the {{< term "optimistic-concurrency" "optimistic concurrency" >}} idea.

```
naive  limit=1000 attempts=1800 granted=[600 600 600] total=1800 final-counter=729 cas-conflicts=0
cas    limit=1000 attempts=1800 granted=[323 351 326] total=1000 final-counter=1000 cas-conflicts=1518
```

The naive version admitted all 1800 and lost updates: the counter never reached the limit. The CAS version granted exactly 1000 and paid 1518 conflicts. Conflicts vary per run; the limit does not. Production systems often use Redis `INCR` with `EXPIRE`, a Lua script or a GCRA module; I did not run those.

## Fewer store calls: leased tokens

A store call per request adds latency and a dependency. Instead each replica takes B tokens and spends them locally. Simulation: 3 replicas, limit 1000 per window, quiet even seconds, busy odd seconds, unspent tokens kept.

```
B=1   store-calls=16485 busiest-window=1000
B=10  store-calls=  669 busiest-window=1017
B=50  store-calls=  150 busiest-window=1097
B=100 store-calls=   85 busiest-window=1197
```

Store calls fall up to 190-fold, at the price of over-admission: tokens from a quiet window are spent in the next. My bound is limit + N·B, since each replica holds at most B; a test checks it, but it is not a proof.

## Failure modes

**Store down.** Seconds 4 and 5 without the store, about 150 req/s offered, limit 100:

```
fail open              served-in-outage= 307 rejected-in-outage=   0
fail closed            served-in-outage=   0 rejected-in-outage= 307
local fallback (L/3)   served-in-outage= 198 rejected-in-outage= 109
```

In my experience: fail closed for login and expensive endpoints, fail open for cheap reads, local fallback in between.

**Clock skew.** Replicas that derive the window id from their own clock, skewed 0, +2 s and -2 s, disagreed on the id for 20087 requests and allowed 300 and 200 in the first two seconds, 1300 in total instead of 1000. With the store's time it was 100 every second. Use the store's clock.

**Retry storms.** 500 clients, limit 100/s, retries after a 429:

```
retry every 50 ms                      attempts= 20254 peak-retries-per-100ms=800
Retry-After (next window)              attempts=  1500 peak-retries-per-100ms=400
Retry-After + jitter 0-1 s             attempts=  1500 peak-retries-per-100ms= 50
full-jitter backoff (100 ms, cap 8 s)  attempts=  2358 peak-retries-per-100ms=274
```

A `Retry-After` header cuts attempts 13 times, and jitter flattens the peak; see [timeouts, retries and backoff](/posts/ds-timeouts-retries-backoff/).

**Fairness and cost.** With a global limit of 1000, a tenant offering 5000 took 898 and three tenants offering 200 each got 33 to 36. A per-tenant cap of 300 gave 300, 200, 200, 200, hence hierarchical limits: global, tenant, user. For 300 mixed reads (cost 1) and writes (cost 5), a count limit of 100 admitted cost 208; a cost budget of 100 admitted 44 requests.

## A few things to watch

- Check the limit in one place, or it is N times larger.
- Decide fail open or closed per endpoint before the outage.
- Send `Retry-After`.

## Exercise

Add a user level inside each tenant in the fairness test and check that no cap is passed.

## What's next

Next: “Failure testing with fault injection”.
