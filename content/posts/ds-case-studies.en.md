+++
date = '2027-06-11T10:00:00+03:30'
draft = false
title = 'Case studies: a rate limiter and a notification system'
seoTitle = 'Case studies: rate limiter and notifications'
description = "Rate limiter and notification system case studies: requirements, estimates and failure modes, each built small in Go and run on seeded loads."
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "system-design", "rate-limiting", "notifications"]
cover = { image = "/images/covers/ds-case-studies.png", alt = "Case studies: a rate limiter and a notification system", hiddenInSingle = true }
+++

"Design a rate limiter." "Design a notification system." These two questions come up again and again, in interviews and in real work. The answers on a whiteboard always sound convincing. The trouble is that nobody checks them: how many bytes does the state take, what exactly happens when a node leaves, what does a crash do to the message that was just sent?

So I built small Go versions of both and ran them on seeded loads, to check the claims instead of repeating them. One result surprised me when I first saw it: in the notification system, one crash window sent 4 of 100 notifications twice, and only the provider's own idempotency key closed it. Everything else in this post is the road to a result like that.

Each case follows the same five steps: requirements, rough numbers (the arithmetic is from the [previous post](/posts/ds-capacity-estimation/)), the parts and the choice made for each, a small build, and then the failure modes. If you only want the lessons, they are at the end.

> How honest the demos are: it is all one machine. "Nodes" are in-process shards, the network is loopback, the senders are fake, the store is in memory (a mutex plays the role of the transaction), and NATS is embedded. The traffic numbers are invented, the loads are seeded, and I print counts, not timings. I re-ran everything with Go 1.27 and the outputs below are what it printed; a second run of the notification demo is identical.

## Case 1: a rate limiter as a service

The situation: an API wants to limit how many requests each key (a user, an API token) may make. Instead of every server counting by itself, one limiter service answers the question "is this request allowed?". The requirements I invented: 5 million daily users, 30 checks each per day, peak 5 times the average, and a limiter outage must not take the API down.

The arithmetic first. 5,000,000 users × 30 checks ÷ 86,400 s ≈ 1,736 checks/s on average, and ×5 gives about 8,681 checks/s at peak. For state, each key needs a counter. I measured the cost of 1 million keys in Go (a map, a 16-byte key and a bucket) and got 136 bytes per key, so 5 million active keys need 5,000,000 × 136 B ≈ 0.68 GB. All of it fits in memory.

```
avg checks/s        1736
peak checks/s (x5)  8681
measured bytes/key  136 (map + 16-byte key + bucket, 1M keys)
5M active keys      0.68 GB of state
```

Now the parts and my choice for each:

| Part | Choice |
|---|---|
| API | `POST /check {key, cost}` returns `{allowed, remaining, retry_after_ms}`; the API maps it to `X-RateLimit-Remaining`, `429` and `Retry-After` |
| Algorithms | {{< term "token-bucket" "token bucket" >}} and {{< term "sliding-window" "sliding window counter" >}} behind one interface |
| State | per key, in memory, sharded over nodes with {{< term "consistent-hashing" "consistent hashing" >}} |
| Client | per-request {{< term "deadline" "deadline" >}}, then {{< term "fail-open" "fail open" >}} to a local bucket |

A few of these need a sentence. A token bucket is a bucket that holds up to N tokens and is refilled at a fixed rate; every request takes a token, and when the bucket is empty the request is rejected. A sliding window counter counts the requests in the most recent time window instead. Consistent hashing is a way to assign keys to nodes so that when a node leaves, only its keys move to others (we will count that below). Fail open means that when the limiter itself is unavailable, the client lets requests through, instead of blocking everything.

### The two algorithms

The first run offers one key 300 requests per second for 10 seconds, against a limit of 100 per second:

```
token bucket 100/s burst 100   offered 3018 allowed 1099 max in any 1s window 199
sliding window 100 per 1s      offered 3018 allowed 991 max in any 1s window 102
token bucket ideal: burst 100 + 100/s*10s = 1100; sliding window ideal: 100 x 10 windows = 1000
```

Each line shows how many requests were offered, how many were allowed, and the largest number allowed in any one-second window. The token bucket allows a burst on top of the steady rate: it starts full with 100 tokens, so over 10 seconds it can let through about 100 + 100 × 10 = 1,100 (it allowed 1,099), and in one second it let 199 through. The window counter is smoother (at most 102 in any second) but approximate: it allowed 991 where the ideal is 1,000. Which one is right depends on whether a burst is a feature or a problem for you. See [distributed limiting](/posts/ds-distributed-rate-limiting/) and [rate limiting in Go](/posts/go-rate-limiting-caching/).

### Losing a node

With the state spread over nodes, what happens when one leaves? The run uses 1,000 keys, each offered 20 requests per second against a limit of 10 per second, 4 nodes, and node `n4` is removed at t = 5 s:

```
offered 200676 (1000 keys x 20/s x 10 s), limit 10/s burst 10 per key
keys that changed owner when n4 left: ring 288, hash mod N 731 (of 1000)
allowed, no failure 108202 | n4 removed at t=5s 110566 | extra 2364 (8.2 per moved key)
```

On the ring (see [sharding](/posts/ds-sharding-consistent-hashing/)), 288 keys changed owner. With the simple "hash mod N" assignment 731 of 1,000 would have moved. A key that moves starts again with a full bucket on its new node, so the limiter briefly lets through too much: 2,364 extra requests out of 200,676, which is 8.2 per moved key. The over-admission is bounded by the number of moved keys times the burst size (288 × 10 = 2,880 here), so it is small and does not grow without limit.

### A hot key

Sharding by key assumes keys are about equally busy. What if one key gets 60% of the traffic? The run sends 20,000 checks and counts how many land on each node, once with the hot key on one node and once with it split into four sub-keys that each get a quarter of the limit:

```
split=false checks per node n1..n4: 1930 1863 13878 2329 | hot key allowed 109
split=true  checks per node n1..n4: 4971 4863 4832 5334 | hot key allowed 108
```

Without splitting, one node got 13,878 of the 20,000 checks, while the others got around 2,000. With four sub-keys the load is almost even, and the hot key is still limited to about the same number of requests (109 against 108). That is a {{< term "hot-key" "hot key" >}} mitigation in one line.

### The client and the headers

Last, the client side over loopback HTTP, using a bucket that refills one token per hour, so that refilling does not matter during the run. First the limiter is up with a limit of 5, then it is stopped, then it is made slow (300 ms) while the client has a 50 ms deadline:

```
-- limiter up (limit 5)
request 1: 200  X-RateLimit-Remaining=4 Retry-After=""
request 2: 200  X-RateLimit-Remaining=3 Retry-After=""
request 3: 200  X-RateLimit-Remaining=2 Retry-After=""
request 4: 200  X-RateLimit-Remaining=1 Retry-After=""
request 5: 200  X-RateLimit-Remaining=0 Retry-After=""
request 6: 429  X-RateLimit-Remaining=0 Retry-After="3600"
request 7: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- limiter stopped: client fails open to a local bucket (burst 2)
request 1: 200  X-RateLimit-Remaining=1 Retry-After=""
request 2: 200  X-RateLimit-Remaining=0 Retry-After=""
request 3: 429  X-RateLimit-Remaining=0 Retry-After="3600"
request 4: 429  X-RateLimit-Remaining=0 Retry-After="3600"
-- slow limiter (300 ms) with a 50 ms deadline: decision came from "local", fallbacks=1
```

While the limiter is up, the remaining count goes 4, 3, 2, 1, 0, and the sixth request gets `429` with `Retry-After` of 3,600 seconds (the time for one token to refill). When the limiter is stopped, the client does not fail: it falls back to a small local bucket with burst 2, so it allows two requests and then rejects. With a slow limiter, the 50 ms deadline expires and the decision comes from the local bucket (`fallbacks=1`).

The failure modes of this design: a lost node means brief over-admission (measured above); a slow or dead limiter means fail open, bounded by the local bucket. For something like login I would fail closed instead, since there letting everything through is the dangerous direction. A hot key needs splitting. What I did not build: gRPC and persistence.

## Case 2: a notification system

The situation: your product has to send email, SMS and push messages. Some are urgent (a login code), some are not (a newsletter). The provider (the company that actually delivers email or SMS) is slow and sometimes fails. The requirements I invented: three channels, two priorities, 3 million notifications per day with a peak of 10 times that rate, a provider call takes 300 ms, 99% of high-priority messages must be sent within 10 seconds (this is an [SLO](/posts/eng-sli-slo-error-budgets/)), and a user's opt-outs must be honoured at the moment of sending.

| Part | Choice |
|---|---|
| API | `POST /notify {user, template, channels, priority, idempotency_key}`; validate, then one transaction for the notification and its outbox rows |
| Relay | publishes the outbox rows to {{< term "jetstream" "JetStream" >}} (the persistent message stream of NATS) with a message id ([outbox](/posts/go-outbox-pattern-nats/)) |
| Lanes | two consumers, `high` and `low`; `high` is tried first ({{< term "priority-lane" "priority lanes" >}}) |
| Worker | opt-out, quiet hours, per-user limit (the case 1 code), breaker, send, and a {{< term "dlq" "dead-letter queue" >}} after `MaxDeliver` attempts |
| Status | queued, sent, skipped, dead; "delivered" would need provider webhooks (not built) |

The "outbox" part solves a classic problem: how to be sure that a message is published if and only if the database change was committed. The API writes the notification and the rows to be published in one transaction, and a relay publishes them afterwards.

### What ran

The demo runs eight experiments. This is its full output:

```
== E1 API idempotency and outbox
100 API calls, 40 distinct keys: notifications 40, deduped by key 60, rejected 0
validation: bad priority | bad channel fax
relay published 80 rows (2 channels each); crash-and-republish sent 80 more, JetStream duplicate acks 80, stream holds 80
== E2 priority lanes
queue depth before the worker runs: high 20, low 200
backlog: 200 low enqueued first, then 20 high; one worker
completions: 220, position of the last high-priority send: 20 (of 220)
== E3 retries and DLQ
200 emails, MaxDeliver 4, backoff 10/20/40 ms + jitter, provider: 30% 5xx, 10% timeout per attempt
sent on attempt 1/2/3/4: 131 / 45 / 15 / 5 | dead-lettered: 4 | provider calls: 302 (timeouts 25)
success rate 98.0% | retries scheduled 102
queue depth after: pending 0, ack-pending 0
== E4 crash windows
provider idempotency key=false crashes 13 | worker suppressed 9 redeliveries | provider accepted 104 sends for 100 notifications (4 notifications sent twice), provider deduped 0
provider idempotency key=true  crashes 13 | worker suppressed 9 redeliveries | provider accepted 100 sends for 100 notifications (0 notifications sent twice), provider deduped 4
== E5 preferences at send time
at 23:00 after alice opted out: statuses map[queued:1 sent:1 skipped:1], deferred (quiet hours, low priority) 1
at 08:00: statuses map[sent:2 skipped:1], opted-out skips 1
== E6 per-user rate limit
10 push notifications for one user, limit 20/s burst 3 (virtual clock): sent 10, limiter denials (nak + redelivery) 80, provider calls 12
== E7 fan-out
1 campaign -> 10000 recipients: 20 batches of 500, limiter waits 18, virtual time 1.8 s
published 10000, stream holds 10000 messages, 1780000 bytes (178 bytes per message)
-- capacity (invented traffic): 3M notifications/day, peak x10, provider latency 300 ms, 3-day retention
avg 35/s, peak 347/s, provider calls in flight at peak (Little) 104, stream 1.6 GB for 9M messages
== E8 circuit breaker
provider down, breaker=false: calls that reached the provider 240, rejected locally 0, dead-lettered 60
provider down, breaker=true : calls that reached the provider 28, rejected locally 212, dead-lettered 60
```

Let me go through them.

**E1, the API.** 100 calls with only 40 distinct idempotency keys created 40 notifications; the other 60 were recognised as repeats. Invalid priorities and channels are rejected. The relay published 80 rows (40 notifications × 2 channels). Then I simulated a relay that crashed after publishing and before marking the rows done: it published the same 80 rows again, and JetStream answered with 80 duplicate acknowledgements, so the stream still holds 80. The message id makes the republish harmless.

**E2, priority lanes.** 200 low-priority messages were queued first, then 20 high-priority ones, with one worker. Because the worker always tries `high` first, the last high-priority message was sent at position 20 of 220, not 220.

**E3, retries.** 200 emails against a provider that fails with a 5xx 30% of the time and times out 10% of the time, per attempt. Each message gets up to 4 attempts, waiting 10, 20 and 40 ms between them plus some random jitter (this is {{< term "exponential-backoff" "exponential backoff" >}}; see [retries](/posts/ds-timeouts-retries-backoff/) and [DLQ](/posts/nats-jetstream-retry-dlq/)). 131 were sent on the first attempt, 45 on the second, 15 on the third and 5 on the fourth. 4 never succeeded and went to the dead-letter queue, so 196 of 200 (98.0%) were sent, with 302 provider calls in total.

**E4, crash windows.** This is the experiment behind the opening claim. The worker is made to "crash" at two points. The first is after the provider accepted the message but before the worker recorded it. The second is after recording but before acknowledging it to the queue. In the second case the message is redelivered and the worker sees from its record that it was already sent, so it suppresses the duplicate: 9 redeliveries were suppressed. In the first case the worker has no record, so on redelivery it sends again: the provider accepted 104 sends for 100 notifications, and 4 notifications went out twice. With an idempotency key that the provider honours, the provider itself dropped the 4 repeats (`provider deduped 4`) and nobody got a duplicate.

**E5, preferences at send time.** Three messages were queued: a low-priority promo for alice, a low-priority promo for bob, and a high-priority code for bob. Bob has quiet hours from 22:00 to 24:00. After the messages were queued, alice opted out of email. At 23:00 the worker skipped alice's message because of the opt-out, sent bob's high-priority code, and deferred bob's promo because of quiet hours (it stays `queued`). At 08:00 the deferred promo was sent too, and the opted-out message was still skipped. The point is that the opt-out was applied at send time, although it came after the message was queued.

**E6, per-user limit.** 10 push notifications to one user, with a limit of 20 per second and a burst of 3, on a virtual clock. All 10 were eventually sent. The limiter denied 80 attempts; each denial makes the message wait and be redelivered.

**E7, fan-out.** One campaign to 10,000 recipients is one API call that becomes 20 batches of 500, rate-limited (the limiter made the publisher wait 18 times, 1.8 seconds of virtual time). The stream holds 10,000 messages in 1,780,000 bytes, which is 178 bytes per message. For the capacity numbers: 3,000,000 ÷ 86,400 ≈ 35 notifications/s on average and 347/s at peak; by {{< term "littles-law" "Little's law" >}} 347 × 0.3 s ≈ 104 provider calls in flight; and with 3 days of retention, 9 million messages × 178 B ≈ 1.6 GB.

**E8, the breaker.** With the provider completely down, a system without a breaker made 240 provider calls (60 messages × 4 attempts) and dead-lettered 60. With the simple count-based breaker (opens after 5 failures and lets every 10th call through as a probe) only 28 calls reached the provider and 212 were rejected locally. Both dead-lettered the same 60 messages. The breaker protects the provider and saves the work, but it does not save the messages ([breakers](/posts/ds-circuit-breaker-bulkhead/)).

### Failure walk-through

| Failure | Result in my runs |
|---|---|
| Provider down, no breaker | 240 calls, 60 DLQ |
| Provider down, breaker (opens after 5 failures, probes every 10th call) | 28 calls, 60 DLQ |
| Crash after the provider accepted, before recording | 4 of 100 sent twice; with a provider idempotency key, 0 |
| Crash after recording, before ack | 9 redeliveries suppressed by the sent table |
| Relay crash after publish | JetStream drops the republished rows |
| NATS down | I did not run this; the rows would wait in the outbox |

The first crash row is the unavoidable edge of {{< term "at-least-once-delivery" "at-least-once delivery" >}}: if you cannot tell whether a message was sent, you either risk sending it twice or risk not sending it. The only real fix is to make the provider call idempotent too ([idempotency](/posts/nats-jetstream-idempotency/)).

A few honest limits. The breaker run dead-letters everything because the simulated provider never recovers; a real system should park the messages and retry later instead. In E3, 98.0% of the emails were sent, but I should be careful with the 99% target: that SLO is about how fast high-priority messages are sent, and E3 does not measure time or priority, so I can only say 4 of 200 emails were lost to the dead-letter queue. In my experience the fix for that is a second provider, not more retries. Finally, the lane order can break: if a slow reply from `high` is mistaken for an empty lane, the worker takes a `low` message first. The demo gives a busy `high` lane a longer wait for this reason.

## Lessons shared by both designs

- **Every number here is simulated or invented.** Treat them as shapes, and measure your own system.
- **Choose fail open or fail closed before the incident**, not during it.
- **Check preferences at send time**, not when the message is queued, since they can change in between.
- **Count duplicates at the provider too.** Your own records cannot see a send you are not sure happened.
- **Watch the age of the oldest message**, not only the queue length ([observability](/posts/nats-jetstream-observability/)).

## What's next

The next post is "Distributed systems capstone", the last one in the series. It combines the pieces from all the posts into one project.
