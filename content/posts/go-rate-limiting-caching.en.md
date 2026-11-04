+++
date = '2027-02-12T10:00:00+03:30'
draft = false
title = 'Rate limiting and caching in Go'
description = 'Go rate limiting and caching: a per-client token bucket with 429 responses, then a TTL cache, singleflight against stampedes and an LRU bound for GetOrder.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "rate-limiting", "caching", "singleflight", "middleware"]
cover = { image = "/images/covers/go-rate-limiting-caching.png", alt = "Rate limiting and caching in Go", hiddenInSingle = true }
+++

Imagine one script that was left in an infinite loop and now sends 500 requests a second to your API. The service is healthy, it answers every request, and still every other customer gets slow responses, because that one client is eating all the capacity. Now imagine the opposite problem: a hundred different clients, all asking for the same popular order, and each of those requests goes to the database. The database answers the same question a thousand times a second.

Both problems come from the same place: a service that is reachable also has to survive its callers. This post adds two defences to the orders service. The first is a {{< term "rate-limiting" "rate limit" >}}: a rule that says "each client may send only so many requests per second", and refuses the rest. The second is a cache in front of `GetOrder`, so a popular order is read from the database once and then served from memory.

I add them to the REST version from [the net/http post](/posts/go-http-api-stdlib/), not to the [gRPC front door](/posts/go-grpc-service/): a rate-limit middleware, and a cache with a `Pay` method that clears the cache entry when an order changes. The last Go post before this one, [Go and Rust talking over gRPC](/posts/go-rust-grpc-interop/), was about another kind of boundary; here we stay inside one service.

> Everything below was re-run with Go 1.27 on macOS (arm64), with `golang.org/x/time` v0.16.0, `golang.org/x/sync` v0.24.0 and `golang-lru/v2` v2.0.7. The programs use a clock I control, so the output has no timing in it and is the same on every run. The code is a local example, not a published repo. The real `cmd/api` program is not changed; the small demo programs build the same handler and add the new pieces to it.

## The token bucket, with numbers

The most common way to limit requests is a {{< term "token-bucket" "token bucket" >}}. Picture a bucket that holds at most `burst` tokens. Tokens drip into it at `rate` per second, and when it is full the extra drips are lost. Every request must take one token out. If the bucket is empty, the request is refused (or has to wait).

That gives you two numbers to choose. `rate` is the long-run average you allow. `burst` is how big a sudden spike you tolerate, because a client that has been quiet has a full bucket and can spend it all at once.

Here is a small example. Take a bucket of 3 that refills at 2 tokens per second, starting full:

- At time 0, three requests arrive. Each takes a token, and the bucket is empty. A fourth and a fifth request find nothing and are refused.
- Half a second later, 0.5 s × 2 tokens/s = 1 new token has dripped in. One request can pass.

`golang.org/x/time/rate` implements this. I ran `rate.NewLimiter(2, 3)` with its methods that take the time explicitly (`AllowN(t, n)` and friends), so that I decide what "now" is and need no `time.Sleep`:

```go
lim := rate.NewLimiter(2, 3)
lim.AllowN(t0, 1)                          // true x3, then false x2
lim.AllowN(t0.Add(500*time.Millisecond), 1) // true: one token refilled
r := lim.ReserveN(t0.Add(500*time.Millisecond), 1)
r.DelayFrom(t0.Add(500*time.Millisecond))   // 500ms
lim.Wait(ctx)                               // ctx has a 10ms deadline
```

The real output of `go run ./cmd/limiter` (I joined the five `Allow` lines into two for readability):

```
Allow #1..#3: true   Allow #4, #5: false   Allow at t+0.5s: true
Reserve delay: 500ms
Wait: rate: Wait(n=1) would exceed context deadline
```

The first line is exactly the walk-through above. The limiter has three ways to ask for a token, and they differ in what they do when the bucket is empty:

- `Allow` answers right now, yes or no. A "no" takes nothing from the bucket.
- `Reserve` always takes the token, even if it does not exist yet, and tells you how long to wait until it would. Here the bucket had just been emptied by the `Allow` at 0.5 s, and the next token is half a second away, so the delay is 500 ms.
- `Wait` blocks until a token is available. If the context's deadline comes before that, it does not wait for nothing: it returns an error immediately. Here the context allowed 10 ms and the token needed 500 ms.

For an HTTP API we do not want to queue requests, we want to say "too many" quickly, so `Allow`-style behaviour fits. As the next section shows, I still use `Reserve`, because it also tells us how long the client should wait.

## One bucket per client

A single bucket for the whole service would be useless: the noisy client from the introduction would empty it and everyone else would be refused. So we keep one bucket per client, in a map from a key to a limiter, protected by a {{< term "mutex" "mutex" >}} because many requests touch the map at once.

What is the key? If the request carries an `X-API-Key` header, we use it. Otherwise we use the IP address of the peer, taken from the connection itself. We deliberately do not read `X-Forwarded-For`, because that header is just text the client sends, and a client that is being limited could write a new value in each request.

`Take` spends one token for a key. When the bucket is empty it must also answer "how long until I can try again?", and for that it uses `Reserve`. But `Reserve` has already taken the token, so on a refusal we give it back with `CancelAt`:

```go
res := e.lim.ReserveN(now, 1)
if d := res.DelayFrom(now); d > 0 {
	res.CancelAt(now) // no token now: give the reservation back
	return false, 0, d
}
return true, int(e.lim.TokensAt(now)), 0
```

Without the cancel, every refused request would borrow a token from the future, and a client that keeps hammering would dig a deeper and deeper hole. The demo in the next section shows the result: after the refused burst, the bucket still refills normally.

### The trap in this map

Nothing in that map ever removes a key. Every new IP address stays in memory forever, and on a public service there is an endless supply of new addresses. `cmd/leak` sends one request each from 100,000 different addresses:

```
entries after 100000 one-off clients: 100000
cleanup right away removed: 0 - still 100000
cleanup after 11 idle minutes removed: 99999 - still 1
```

Every entry remembers when its client was last seen, and `Cleanup(idle)` deletes the entries that have been idle longer than `idle`. Right after the requests nothing is old enough, so nothing is removed. In the demo the clock then moves forward 11 minutes and one client comes back; that client is the one entry that survives and the other 99,999 are removed. In the real server a goroutine calls the cleanup from a ticker, every minute here:

```go
go limiter.Run(ctx, time.Minute, 10*time.Minute)
```

Dropping an idle client is safe as long as a full refill takes less than the idle time: such a client would have a full bucket anyway, which is exactly what a brand new entry starts with.

## The middleware

Now we connect the limiter to HTTP. A middleware is a function that wraps a handler: it runs before the real handler and decides whether to call it. `RateLimit` is added at the end of the existing chain, after the request ID, the access log and the recover middleware. This order matters: a refused request still gets a request ID and still appears in the access log, so you can see who is being limited. A refusal goes through the same error path as every other error: a new `errLimited` maps to `429 Too Many Requests` in the one `statusOf` function.

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

Every response tells the client its limit and how many requests it has left, and a refusal adds `Retry-After`, the number of seconds to wait (rounded up to a whole second). A well-behaved client can use these instead of guessing.

To test it end to end, `cmd/burst` starts a real server with `httptest`, rate 1 per second and burst 5, and talks to it with a real HTTP client. The clock is a variable that the program moves by hand. It sends 20 requests at once, then moves the clock forward 3 seconds and sends 10 more, then sends 10 more with an API key:

```
  first 429: Retry-After=1 Limit=5 Remaining=0
burst of 20 at t+0s:  5 passed, 15 denied
10 more at t+3s:      3 passed, 7 denied
10 with an API key:   5 passed, 5 denied
```

The program prints the "first 429" line once for each group that had a refusal; I show it once. Reading the rest:

- Of the first 20 requests, exactly 5 pass: the burst. The first refusal carries `Retry-After=1`, because at 1 token per second the next token is one second away.
- After three fake seconds, 3 of the next 10 pass. Three seconds of refill is three tokens. This also proves that the 15 refused requests did not go into debt, thanks to `CancelAt`.
- The requests with `X-API-Key` have their own bucket, so 5 pass even though the IP's bucket is empty.

The unit tests assert the same numbers, also without sleeping.

One limit of this design: the buckets live in the memory of one process. If you run N replicas of the service behind a load balancer, each has its own buckets, and a client can get up to N times the limit. A limit shared by all replicas needs shared state, for example Redis. I did not run that here.

## A cache for GetOrder

The second problem: the same order read again and again. A cache keeps recent answers in memory. `cache.TTL` is a small generic map with three ideas:

- A read-write lock (`RWMutex`): many goroutines can read together, and a write takes the lock alone.
- An expiry time on every entry, the {{< term "ttl" "TTL" >}}. After it, the entry counts as missing.
- Hit and miss counters, so we can see what the cache does.

`cached.Service` wraps the real orders service. `Get` goes through the cache. `Pay` changes the order, so after a successful payment it deletes the cached entry; otherwise readers would see the old status until the TTL expired. The demo creates an order, reads it ten times, pays it, and reads it once more:

```
after 10 GETs:        hits=9 misses=1
pay -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
get -> {"id":"1","customer":"ali","cents":1500,"status":"paid"}
after pay and 1 GET:  hits=9 misses=2
```

The first read missed and loaded the order from the store; the other nine were hits. After the payment, the next read was a miss on purpose: the entry had been deleted, so it loaded the fresh order, and it shows `paid`. Without the `Delete`, that last read would have returned the old `new` status until the TTL ran out.

## Stampede and singleflight

There is a subtler problem. When a popular entry expires, every request that arrives before it is reloaded misses at the same moment, and all of them go to the database with the same question. This is called a {{< term "cache-stampede" "cache stampede" >}}. The cache that was supposed to protect the database sends a herd to it at the worst moment.

The cure is simple: let the first request do the loading, and make the others wait for its answer. Go has this in `golang.org/x/sync/singleflight`, which I call {{< term "singleflight" "singleflight" >}} below. `GetOrLoad` runs the loader inside `singleflight.Group.Do`: callers with the same key share the result of the first call.

`cmd/stampede` fires 50 goroutines at one missing key. The loader sleeps 50 ms, like a slow query, and counts how often it runs. It does this once with the obvious "check, load, store" code and once with `singleflight`:

```
naive          50 requests -> 50 loader calls
singleflight   50 requests -> 1 loader calls
```

Fifty identical queries became one. The demo is not fully deterministic, because the 50 goroutines must overlap inside that 50 ms window; I did not change that and it printed the same here, but I would not build a strict test on timing like this.

## Bounded size

Our TTL map has a quiet problem: it never removes an expired entry. A read of an expired key just reports a miss, and the old value stays in the map until the same key is loaded again. With many different keys the map keeps growing. For a hard upper bound I used `hashicorp/golang-lru/v2`, an {{< term "lru-cache" "LRU cache" >}}: when it is full, it evicts the entry that was used least recently. Here is capacity 3: we add `a`, `b`, `c`, read `a`, then add `d` and `e`:

```
add d:
  evicted b=2
add e:
  evicted c=3
keys oldest to newest: [a d e] len: 3
```

Reading `a` made it the most recently used one, so when `d` arrived, the oldest was `b`, and when `e` arrived, `c`. `a` survived both times.

## Where these defences break

- **Caching trades freshness for speed.** A longer TTL means fewer loads and more stale data. Delete entries on the writes you control (as `Pay` does) and accept the TTL as the worst case for changes you do not control.
- **An invalidation can lose a race.** A slow load that started before a `Delete` may finish after it and write the old value back. I did not reproduce this; a short TTL is the safety net.
- **`singleflight` shares the first caller's context and error.** If that caller is cancelled, the callers waiting behind it see the same failure.
- **Limits by IP punish innocent people.** Many users behind one NAT share one address and one bucket. Prefer API keys where you have them. Note also that this demo does not check API keys: any string works as a key, so a limit keyed by an unchecked header can be dodged by inventing keys. In a real service the key must be validated first.

## What's next

The limiter and the cache are guesses about where the load is. The next post, "Profiling Go with pprof", shows how to measure where time and memory really go instead of guessing.
