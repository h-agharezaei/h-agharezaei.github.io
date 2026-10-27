+++
date = '2027-06-11T10:00:00+03:30'
draft = false
title = 'Case studies: a rate limiter and a notification system'
seoTitle = 'Case studies: rate limiter and notifications'
description = "Rate limiter and notification system case studies: requirements, estimates and failure modes, each built small in Go and run on seeded loads."
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "system-design", "rate-limiting", "notifications"]
cover = { image = "/images/covers/ds-case-studies.png", alt = "Case studies: a rate limiter and a notification system", hiddenInSingle = true }
+++

[The previous post](/posts/ds-capacity-estimation/) gave us the arithmetic. This one applies the series to two classic interview questions and builds a small version of each, so the claims are checked.

> Honest labelling: one machine. "Nodes" are in-process shards, the network is loopback, senders are fake, the store is in memory (a mutex plays the transaction), NATS is embedded. Traffic numbers are invented, loads are seeded, I print counts, not timings.

## Case 1: a rate limiter as a service

Requirements (invented): 5M daily users, 30 checks each, peak 5x; a limiter outage must not take the API down.

```
avg checks/s        1736
peak checks/s (x5)  8681
measured bytes/key  136 (map + 16-byte key + bucket, 1M keys)
5M active keys      0.68 GB of state
```

| Part | Choice |
|---|---|
| API | `POST /check {key, cost}` returns `{allowed, remaining, retry_after_ms}`; the API maps it to `X-RateLimit-Remaining`, `429`, `Retry-After` |
| Algorithms | {{< term "token-bucket" "token bucket" >}} and {{< term "sliding-window" "sliding window counter" >}} behind one interface |
| State | per key, in memory, sharded over nodes with {{< term "consistent-hashing" "consistent hashing" >}} |
| Client | per-request {{< term "deadline" "deadline" >}}, then {{< term "fail-open" "fail open" >}} to a local bucket |

One key, 300 requests per second offered for 10 s, limit 100 per second:

```
token bucket 100/s burst 100   offered 3018 allowed 1099 max in any 1s window 199
sliding window 100 per 1s      offered 3018 allowed 991 max in any 1s window 102
```

The bucket allows a burst on top of the rate (199 in one second); the window counter is smoother but approximate ([distributed limiting](/posts/ds-distributed-rate-limiting/), [in Go](/posts/go-rate-limiting-caching/)).

Then 1000 keys, each offered 20 per second against 10 per second, 4 nodes, node `n4` removed at t=5 s:

```
keys that changed owner when n4 left: ring 288, hash mod N 731 (of 1000)
allowed, no failure 108202 | n4 removed at t=5s 110566 | extra 2364 (8.2 per moved key)
```

The ring ([sharding](/posts/ds-sharding-consistent-hashing/)) moves 288 keys, mod N 731. A moved key restarts with a full bucket, so over-admission is bounded by moved keys times burst: 2364 extra of 200,676 requests. Next, a {{< term "hot-key" "hot key" >}} with 60% of 20,000 checks:

```
split=false checks per node n1..n4: 1930 1863 13878 2329 | hot key allowed 109
split=true  checks per node n1..n4: 4971 4863 4832 5334 | hot key allowed 108
```

Four sub-keys with a quarter of the limit each spread the load. Last, the client and headers on loopback HTTP, with a bucket refilling 1 token per hour (exact output):

```
request 5: 200  X-RateLimit-Remaining=0 Retry-After=""
request 6: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- limiter stopped: client fails open to a local bucket (burst 2)
request 1: 200  X-RateLimit-Remaining=1 Retry-After=""
request 3: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- slow limiter (300 ms) with a 50 ms deadline: decision came from "local", fallbacks=1
```

Failure modes: node lost (brief over-admission), limiter slow or down (fail open, bounded by the local bucket; for login I would fail closed), hot key (split). Not built: gRPC, persistence.

## Case 2: a notification system

Requirements (invented): email, SMS, push; two priorities; 3M per day, peak 10x; provider call 300 ms; 99% of high priority sent within 10 s ([SLO](/posts/eng-sli-slo-error-budgets/)); opt-outs honoured at send time.

| Part | Choice |
|---|---|
| API | `POST /notify {user, template, channels, priority, idempotency_key}`; validate, one transaction for notification and outbox rows |
| Relay | publishes outbox rows to {{< term "jetstream" "JetStream" >}} with a message id ([outbox](/posts/go-outbox-pattern-nats/)) |
| Lanes | consumers `high` and `low`, `high` tried first ({{< term "priority-lane" "priority lanes" >}}) |
| Worker | opt-out, quiet hours, per-user limit (case 1 code), breaker, send, {{< term "dlq" "DLQ" >}} after `MaxDeliver` |
| Status | queued, sent, skipped, dead; "delivered" needs provider webhooks (not built) |

What ran (identical on two runs):

```
100 API calls, 40 distinct keys: notifications 40, deduped by key 60, rejected 0
relay published 80 rows; crash-and-republish sent 80 more, JetStream duplicate acks 80, stream holds 80
backlog: 200 low enqueued first, then 20 high; one worker
position of the last high-priority send: 20 (of 220)
200 emails, MaxDeliver 4, backoff 10/20/40 ms + jitter, provider: 30% 5xx, 10% timeout per attempt
sent on attempt 1/2/3/4: 131 / 45 / 15 / 5 | dead-lettered: 4 | provider calls: 302 (timeouts 25)
at 23:00 after alice opted out: statuses map[queued:1 sent:1 skipped:1], deferred (quiet hours, low priority) 1
10 push for one user, limit 20/s burst 3 (virtual clock): sent 10, limiter denials 80
1 campaign -> 10000 recipients: 20 batches of 500, limiter waits 18, virtual time 1.8 s
published 10000, stream holds 10000 messages, 1780000 bytes (178 bytes per message)
```

Retries use {{< term "exponential-backoff" "exponential backoff" >}} with jitter ([retries](/posts/ds-timeouts-retries-backoff/), [DLQ](/posts/nats-jetstream-retry-dlq/)). Capacity: 35/s average, 347/s peak, about 104 provider calls in flight ({{< term "littles-law" "Little's law" >}}), 1.6 GB for 9M messages at the measured 178 bytes. The campaign is one call and 20 rate-limited batches.

Failure walk-through:

| Failure | Result in my runs |
|---|---|
| Provider down, no breaker | 240 calls, 60 DLQ |
| Provider down, breaker (opens after 5 failures, probes every 10th call) | 28 calls, 60 DLQ ([breakers](/posts/ds-circuit-breaker-bulkhead/)) |
| Crash after the provider accepted, before recording | 4 of 100 sent twice; with a provider idempotency key 0 |
| Crash after recording, before ack | 9 redeliveries suppressed by the sent table |
| Relay crash after publish | JetStream drops the republished rows |
| NATS down | I did not run this; rows would wait in the outbox |

The first crash row is the unavoidable {{< term "at-least-once-delivery" "at-least-once" >}} edge ([idempotency](/posts/nats-jetstream-idempotency/)): only the provider's key closes it. The breaker run dead-letters everything because the provider never recovers; a real system should park. Success was 98.0%, below the 99% target; in my experience the fix is a second provider, not more retries. Lane order can break if a slow reply looks like an empty `high` lane.

## A few things to watch

- Every number is simulated or invented.
- Choose fail open or closed before the incident.
- Check preferences at send time.
- Count duplicates at the provider too.
- Watch the oldest message age ([observability](/posts/nats-jetstream-observability/)).

## Exercise

Add a `delivered` status with simulated webhooks that arrive late, twice or never.

## What's next

"Distributed systems capstone", the last post, combines the pieces into one project.
