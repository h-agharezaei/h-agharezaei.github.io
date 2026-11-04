+++
date = '2027-06-03T10:00:00+03:30'
draft = false
title = 'Distributed rate limiting'
description = 'Distributed rate limiting in Go: why N local limiters over-admit, window algorithms compared, an exact NATS KV compare-and-set limiter, and failure modes.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "rate-limiting", "nats", "kv", "go"]
cover = { image = "/images/covers/ds-distributed-rate-limiting.png", alt = "Distributed rate limiting", hiddenInSingle = true }
+++
You promise each API client at most 100 requests per second. On one server that is easy: keep a counter per client and refuse requests when it is used up. Then the service grows to 10 replicas behind a load balancer, and each replica keeps its own counter. A client that sends requests to all of them can now send up to 1000 per second. In the simulation below I put a 100 req/s {{< term "token-bucket" "token bucket" >}} on each of 10 replicas and routed randomly: all 19922 requests got through. The limit was still there, but nothing was limited.

The single-process bucket from [rate limiting and caching in Go](/posts/go-rate-limiting-caching/) now exists N times, while "100 requests per second per client" has to mean 100 across the whole fleet. That is the problem of this post: the counter must be shared, or at least coordinated, and each way of doing that has a price. The [previous post](/posts/ds-service-discovery-load-balancing/) spread the requests over replicas; here we see what that does to a limit.

> Honest labelling: everything except the NATS section is a seeded Go **simulation** on one machine, with counts instead of timings. I re-ran all of it with Go 1.27 and `go test -race` passes. The simulated outputs are identical to the original run. The NATS section is real: an embedded nats-server (v2.15.1) on loopback. I did not run Redis.

## N local limiters

Start with the broken setup, and with the arithmetic of what it should give. Four clients each offer about 500 requests per second for 10 seconds. Every replica has its own token bucket for each client: it refills at 100 tokens per second, holds at most 10, and spends one token per request. (Think of a bucket with a small hole being filled by a tap: a full bucket lets a short burst through, an empty one lets requests through only at the refill rate.) One client may therefore get 100 × 10 + 10 = 1010 requests through in 10 seconds, and four clients about 4040.

I ran it with different numbers of replicas N. "Sticky" means a client's requests always go to the same replica. "Offered" is how many requests arrived:

```
N=1  sticky=true  offered=19875 allowed=4036
N=3  sticky=true  offered=19875 allowed=4036
N=3  sticky=false offered=19922 allowed=12097
N=10 sticky=false offered=19922 allowed=19922
```

With one replica, or with sticky routing, the total is 4036, close to the ideal 4040. With random routing and N=3 it is 12097, about 3 times as much, because each replica allows the full rate on its own. At N=10 the rate each replica sees is only about 50 requests per second per client, which is below its limit, so nothing is limited: 19922 offered and 19922 allowed. The effective limit is N times larger, and with enough replicas it disappears.

Sticky routing by client key (see [consistent hashing](/posts/algo-bloom-filter-consistent-hashing/)) fixes this without any shared state: a client's counter lives on one replica. The price is {{< term "hot-key" "hot keys" >}}: one very busy client loads one replica, however many replicas you have. And it only works while the routing is stable, which is not always true during deploys and failures.

## The algorithms on the same traffic

Before sharing a counter, which counter? A "rate limit" can be counted in several ways, and they behave differently at the edges. Here are five, in plain words:

- **Fixed window.** Count requests in each whole second and reset at the boundary. Cheap, but if a client sends 100 requests at 999 ms and 100 more at 1000 ms, both are allowed, 200 requests in 2 ms.
- **Sliding log.** Keep the timestamp of every allowed request and count those in the last 1000 ms. Exact, but it stores up to as many timestamps as the limit allows, per client.
- **Sliding window counter.** Keep two counts, for the current and the previous window, and weight the previous one by how much of it still overlaps the last second. An approximation that needs very little memory.
- **Token bucket.** As above: refill at the limit rate, up to a capacity. Allows bursts up to the capacity.
- **Leaky meter.** The mirror image: a level that rises by 1 per request and drains at the limit rate, and a request is rejected if the level would pass the capacity. (My name for it; it is the same idea as a leaky bucket used as a meter.)

I ran all five on the same 495 requests with a limit of 100 per 1000 ms: some background noise, a 100-request burst just before the boundary at 1000 ms, another one just after it, and a third one in the middle of a window. The columns: `allowed` is how many requests each algorithm let through, `max/1000ms` is the most allowed requests in any 1000 ms span, `in[950,1050)` is how many were allowed during the 100 ms around the boundary, and `diff-exact` is how many of the 495 decisions differ from the exact sliding log.

```
algorithm                 allowed   max/1000ms in[950,1050) diff-exact
fixed window                  436          199          180        135
sliding log (exact)           351          100           81          0
sliding counter               355          104           84         10
token bucket (cap 20)         247           49           29        124
leaky meter (cap 20)          247           49           29        124
sliding log max stored timestamps: 100
```

- The **fixed window** let 180 requests through in 100 ms and 199 within one second, almost twice the limit, because the counter resets at the boundary.
- The **sliding log** never exceeded 100 in any second, and it stored at most 100 timestamps (the last line). That is the memory cost of being exact.
- The **sliding counter** made 10 different decisions out of 495 and let at most 104 through in a second. It is slightly wrong in exchange for storing two counts and a window number.
- The **token bucket** and the **leaky meter** gave the same counts in every column (the test checks that both differ from the exact log equally often; I did not compare their decisions one by one). They are stricter here because their capacity is only 20: the burst is cut, and at most 49 were allowed in a second. Both allow bursts up to the capacity, so use them when bursts are fine.

| | memory per key | accuracy | burst behaviour |
|---|---|---|---|
| fixed window | 2 numbers | up to 2x at boundary | double burst |
| sliding log | O(limit) | exact | none |
| sliding counter | 3 numbers | approximate | small error |
| token / leaky | 2 numbers | exact for its model | capacity allowed |

Any of these can be the counter. Now the question is where it lives.

## A shared store with compare-and-set

The obvious answer is a shared store that every replica asks. Here is the trap with doing it naively. Two replicas read the counter, both see 5, both decide "5 is below the limit", and both write 6. Two requests were admitted but the counter went up by one. This is a lost update, and it makes the limiter admit more than it should.

The fix is *compare-and-set*: write only if nobody has written since I read. In a JetStream KV bucket (see [KV and Object Store in NATS](/posts/nats-kv-object-store/)) every key has a revision number, and `Update` takes the revision you read and fails if the key has changed. On failure you read again and retry. This is the {{< term "optimistic-concurrency" "optimistic concurrency" >}} idea.

The experiment: one counter key and three goroutines, each with its own connection, making 600 attempts each (1800 in total) against a limit of 1000. The naive version reads, then writes. The CAS version uses `Update` with the revision it read:

```
naive  limit=1000 attempts=1800 granted=[600 600 600] total=1800 final-counter=729 cas-conflicts=0
cas    limit=1000 attempts=1800 granted=[323 351 326] total=1000 final-counter=1000 cas-conflicts=1518
```

The naive version admitted all 1800 attempts and lost updates: the counter ended at 729 and never even reached the limit, so it never refused anyone. The CAS version granted exactly 1000, split between the three roughly evenly, and the final counter is exactly 1000. What it paid was 1518 conflicts, retries that lost the race. The conflicts, the split and the naive final counter vary from run to run (these are the original numbers; in my two Go 1.27 re-runs the naive counter ended at 718 and 726 and CAS had 1506 and 1533 conflicts). The limit of 1000 does not vary.

So a shared store gives an exact limit, at the cost of a round trip and a possible retry loop on every request, and the store becomes a dependency. As far as I know, production systems often use Redis `INCR` with `EXPIRE`, a Lua script, or a GCRA-based limiter; I did not run those.

## Fewer store calls: leased tokens

A store call per request adds latency and a dependency. A middle way: each replica takes a batch of B tokens from the shared counter and then spends them locally, without asking again. This is a lease on a slice of the limit.

The simulation: 3 replicas, random routing, a limit of 1000 per one-second window in the shared store. Even seconds are quiet (about 300 requests per second) and odd seconds are busy (3000 per second). A replica keeps its unspent tokens across the window boundary. In the rows with B above 1 a replica that has been refused also remembers it until the end of the window, instead of asking again for every request; the B=1 row does not, so it is the baseline of one store call per request.

```
B=1   cacheDeny=false store-calls= 16485 allowed= 6485 busiest-window=1000 (limit+N*B=1003) per-window=[283 1000 303 1000 292 1000 281 1000 326 1000]
B=10  cacheDeny=true  store-calls=   669 allowed= 6540 busiest-window=1017 (limit+N*B=1030) per-window=[283 1017 303 1007 292 1008 281 1009 326 1014]
B=50  cacheDeny=true  store-calls=   150 allowed= 6750 busiest-window=1097 (limit+N*B=1150) per-window=[283 1067 303 1097 292 1008 281 1019 326 1074]
B=100 cacheDeny=true  store-calls=    85 allowed= 7000 busiest-window=1197 (limit+N*B=1300) per-window=[283 1117 303 1197 292 1008 281 1019 326 1174]
```

Read the first and last rows. With B=1 every one of the 16485 requests calls the store, and every busy window admits exactly 1000. With B=100 there are only 85 store calls (194 times fewer), but the busy windows admit up to 1197. The over-admission comes from the quiet seconds: tokens a replica took in a quiet window are still in its hands, and are spent in the next window on top of that window's 1000. The more tokens a replica holds, the more can leak. My bound is the limit plus N times B (the last column before `per-window`), since each replica holds at most B unspent tokens. A test checks that the busiest window stays within it for these four values of B, which is a check on one seeded run, not a proof.

## Failure modes

A limiter that needs a shared store has its own failures. Four that I simulated.

**The store is down.** What should the limiter do when it cannot reach its counter? In the simulation the store is unavailable for seconds 4 and 5, with about 150 requests per second offered and a limit of 100 per second. Three policies: *fail open* (let everything through), *fail closed* (reject everything), and a local fallback where each of the 3 replicas allows a third of the limit by itself. Over the two seconds of outage 307 requests were offered:

```
no outage              served-in-outage=   0 rejected-in-outage=   0 total-served=1000
fail open              served-in-outage= 307 rejected-in-outage=   0 total-served=1107
fail closed            served-in-outage=   0 rejected-in-outage= 307 total-served=800
local fallback (L/3)   served-in-outage= 198 rejected-in-outage= 109 total-served=998
```

Normally the limit allows 100 per second, so 200 in two seconds. Fail open served all 307, 107 more than the limit. Fail closed served none, and the service looked down to every client. The local fallback served 198: each replica allowed at most a third of the limit, 33 per second, and since each was offered about 50 per second it always reached that cap, so 3 × 33 × 2 seconds = 198, just under the 200 we wanted. It rejected the other 109. In my experience: fail closed for login and expensive endpoints, fail open for cheap reads, and local fallback in between.

**Clock skew.** If each replica builds the window id (which second is it?) from its own clock, then replicas whose clocks differ count in different windows. I gave three replicas clocks that were 0, +2 s and -2 s off. They disagreed on the window id for 20087 of 30000 requests. In the first two seconds they allowed 300 and 200 requests instead of 100, so 1300 requests in total over the run instead of 1000. (After the first two seconds the other windows' counters had already been used up, so later seconds show 100; that is a property of this short, small model.) When the window id came from the store's clock, every second allowed exactly 100. So use the store's clock for windows.

**Retry storms.** What do clients do after a `429 Too Many Requests`? Here 500 clients arrive at once against a limit of 100 per second. I compared four retry policies:

```
retry every 50 ms                      attempts= 20254 peak-retries-per-100ms= 800 last-success= 4049 ms stuck=0
Retry-After (next window)              attempts=  1500 peak-retries-per-100ms= 400 last-success= 4000 ms stuck=0
Retry-After + jitter 0-1 s             attempts=  1500 peak-retries-per-100ms=  50 last-success= 4994 ms stuck=0
full-jitter backoff (100 ms, cap 8 s)  attempts=  2358 peak-retries-per-100ms= 274 last-success= 8899 ms stuck=0
```

Retrying every 50 ms means 20254 attempts to get 500 requests through. If the server tells clients when to come back with a `Retry-After` header (here: the start of the next window) there are only 1500 attempts, which is easy to check: 500 + 400 + 300 + 200 + 100, since each second 100 clients succeed. That cuts attempts more than 13 times. But all 400 waiting clients return in the same moment (peak 400 in 100 ms), and adding jitter of 0 to 1 s flattens that peak to 50, at the price of finishing later (4994 ms instead of 4000 ms). Backoff with full jitter lands in between on attempts and peak (2358 and 274), but it is the slowest to finish (8899 ms). See [timeouts, retries and backoff](/posts/ds-timeouts-retries-backoff/).

**Fairness and cost.** One global limit of 1000 does not divide it fairly. With a global limit of 1000, a tenant offering 5000 requests took 898 and three tenants offering 200 each got 33 to 36. A per-tenant cap of 300 gave 300, 200, 200 and 200, and so the usual design is hierarchical: a global limit, a tenant limit and a user limit. And not every request costs the same: for 300 mixed requests (70% reads at cost 1 and 30% writes at cost 5), a count limit of 100 admitted a total cost of 208, while a cost budget of 100 admitted 44 requests with a total cost of exactly 100.

## Decisions to make early

- **Check the limit in one place**, or it is effectively N times larger. Decide between sticky routing (no shared state, hot keys) and a shared counter (exact, but a dependency).
- **Decide fail open or fail closed for each endpoint before the outage**, not during it.
- **Send `Retry-After`** with every 429, ideally with some jitter, so that rejected clients do not come back all at the same moment.
- **Use one clock for windows**: the store's, not each replica's.

## What's next

[Failure testing with fault injection](/posts/ds-fault-injection-testing/): failures like the retry storms simulated here can be injected on purpose into a real client, to see whether it survives them.
