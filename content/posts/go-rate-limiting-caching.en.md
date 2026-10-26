+++
date = '2027-02-12T10:00:00+03:30'
draft = false
title = 'Rate limiting and caching in Go'
description = 'Go rate limiting and caching: a per-client token bucket with 429 responses, then a TTL cache, singleflight against stampedes and an LRU bound for GetOrder.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "rate-limiting", "caching", "singleflight", "middleware"]
cover = { image = "/images/covers/go-rate-limiting-caching.png", alt = "Rate limiting and caching in Go", hiddenInSingle = true }
+++

The [previous post](/posts/go-grpc-service/) gave `orders` a gRPC front door. A service that is reachable also has to survive its callers: one noisy client should not starve the others, and the same hot order should not hit the database a thousand times a second. This post adds both defences to the REST version from [the net/http post](/posts/go-http-api-stdlib/): a rate-limit middleware in its chain, and a cache in front of `GetOrder`. The code copies that demo and adds a `Pay` method, an update we need for invalidation.

> Go 1.26, macOS arm64, `golang.org/x/time` v0.16.0, `golang.org/x/sync` v0.24.0, `golang-lru/v2` v2.0.7.

## Token bucket

A **token bucket** holds up to `burst` tokens and refills at `rate` tokens per second. Each request takes one token; with none left, the request is refused or delayed. So `rate` is the long-run average and `burst` is how much spike you tolerate. I ran `rate.NewLimiter(2, 3)` with the time-explicit `...N(time, n)` methods:

```go
lim := rate.NewLimiter(2, 3)
lim.AllowN(t0, 1)                          // true x3, then false x2
lim.AllowN(t0.Add(500*time.Millisecond), 1) // true: one token refilled
r := lim.ReserveN(t0.Add(500*time.Millisecond), 1)
r.DelayFrom(t0.Add(500*time.Millisecond))   // 500ms
lim.Wait(ctx)                               // ctx has a 10ms deadline
```

```
Allow #1..#3: true   Allow #4, #5: false   Allow at t+0.5s: true
Reserve delay: 500ms
Wait: rate: Wait(n=1) would exceed context deadline
```

`Allow` answers now. `Reserve` always takes the token and tells you the wait. `Wait` blocks, and returns an error immediately when the context deadline is earlier than the needed wait. For an HTTP API we reject instead of queueing, so `Allow` semantics fit.

## One limiter per client

A global bucket lets one client eat everything, so we keep a bucket per key in a map guarded by a mutex. The key is the `X-API-Key` header if present, otherwise the peer IP (not `X-Forwarded-For`, which a client can forge). `Take` spends a token, and when it is empty it undoes the reservation to learn the retry delay:

```go
res := e.lim.ReserveN(now, 1)
if d := res.DelayFrom(now); d > 0 {
	res.CancelAt(now) // no token now: give the reservation back
	return false, 0, d
}
return true, int(e.lim.TokensAt(now)), 0
```

The trap is the map. Nothing ever removes a key, so every new IP stays forever. `cmd/leak` sends one request each from 100,000 distinct addresses:

```
entries after 100000 one-off clients: 100000
cleanup right away removed: 0 - still 100000
cleanup after 11 idle minutes removed: 99999 - still 1
```

Each entry records when it was last seen, and `Cleanup(idle)` deletes the ones older than `idle` (one client came back, so it stayed). A goroutine calls it from a ticker:

```go
go limiter.Run(ctx, time.Minute, 10*time.Minute)
```

## The middleware

`RateLimit` goes at the end of the chain, so request IDs and the access log still cover rejected requests. A refusal reuses the error path: a new `errLimited` maps to `429` in the one `statusOf` function.

```go
ok, remaining, retry := t.Take(clientKey(r))
w.Header().Set("X-RateLimit-Limit", strconv.Itoa(burst))
w.Header().Set("X-RateLimit-Remaining", strconv.Itoa(remaining))
if !ok {
	w.Header().Set("Retry-After", strconv.Itoa(ratelimit.Seconds(retry)))
	writeErr(w, r, errLimited)
	return
}
```

`cmd/burst` starts a real server over `httptest` with a clock we control (rate 1/s, burst 5), and a real HTTP client:

```
  first 429: Retry-After=1 Limit=5 Remaining=0
burst of 20 at t+0s:  5 passed, 15 denied
10 more at t+3s:      3 passed, 7 denied
10 with an API key:   5 passed, 5 denied
```

Exactly 5, then 3 refilled tokens after three fake seconds, and a different key has its own bucket. The tests assert the same numbers without sleeping. The limiter lives in this process: with N replicas each keeps its own buckets, so a client can get up to N times the limit. A shared limit needs shared state, such as Redis (not run here).

## A cache for GetOrder

`cache.TTL` is a generic map with an `RWMutex` (many readers, one writer), an expiry per entry, an injectable clock and atomic hit/miss counters. `cached.Service` wraps the real service: `Get` goes through the cache, and `Pay` deletes the entry after a successful update. Ten GETs, then a payment, then one more GET:

```
after 10 GETs:        hits=9 misses=1
pay -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
get -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
after pay and 1 GET:  hits=9 misses=2
```

The last GET missed on purpose and returned the fresh status; without the `Delete` it would have served `new` until the TTL ran out.

## Stampede and singleflight

When a hot key expires, every concurrent request misses together and all of them call the database. `cmd/stampede` fires 50 goroutines at one missing key with a 50ms loader, once with the obvious get/load/set and once with `singleflight`:

```
naive          50 requests -> 50 loader calls
singleflight   50 requests -> 1 loader calls
```

`GetOrLoad` runs the loader inside `singleflight.Group.Do`: callers with the same key wait for the first call and share its result. The callers are lined up with a short real sleep, so the test is not fully deterministic; it passed 20 runs under `-race`.

## Bounded size

Our TTL map only drops entries when you read them after expiry, so it can grow. For a hard bound I used `hashicorp/golang-lru/v2`, which evicts the least recently used entry. Capacity 3, with `a` read after inserting `a b c`:

```
add d:
  evicted b=2
add e:
  evicted c=3
keys oldest to newest: [a d e] len: 3
```

`a` survived because reading it made it recent.

## A few things to watch

- Caching is a freshness trade-off. A longer TTL means fewer loads and more stale data; invalidate on writes you control, and accept the TTL as the worst case for changes you do not.
- An invalidation can race with a slow load that started earlier: it may write the old value back after your `Delete`. I did not reproduce this; keep the TTL short as a safety net.
- With `singleflight`, everyone shares the first caller's context and error. If that caller is cancelled, the others see it too.
- Rate limits keyed by IP punish clients behind one NAT; prefer API keys where you have them.

## What's next

Next: profiling Go with pprof, to find out where the time and memory really go instead of guessing.
