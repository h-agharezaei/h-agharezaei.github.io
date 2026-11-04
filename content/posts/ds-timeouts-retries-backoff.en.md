+++
date = '2027-05-04T10:00:00+03:30'
draft = false
title = 'Timeouts, retries and backoff with jitter'
description = 'Timeouts and retries done right: a real loopback client, a seeded retry-storm simulation, retry budgets, deadline propagation and hedged requests in Go.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "retries", "backoff", "timeouts"]
cover = { image = "/images/covers/ds-timeouts-retries-backoff.png", alt = "Timeouts, retries and backoff with jitter", hiddenInSingle = true }
+++

A service has a bad minute and starts failing. Every client sees errors and does the sensible thing: it retries. A second later the server, which was struggling with 1000 requests, is receiving 3000. It falls over for real, the clients retry again, and a failure that would have healed in seconds becomes an outage that lasts for an hour. The thing that made it worse was the cure.

A {{< term "deadline" "timeout" >}} tells you only that you do not know what happened ([why distributed systems are hard](/posts/ds-why-distributed-is-hard/)), so the usual reaction is to try again. That is right, but only if it is done carefully: which errors to retry, how long to wait, how many times, and who else in the chain is retrying at the same moment. This post goes through those questions, first with a real client, then with simulations that show the arithmetic of retry storms. Just before this, [logical clocks](/posts/ds-logical-clocks/) ordered events without trusting time; here we decide what to do when a call goes quiet.

Retries only make sense for operations that are safe to repeat ([idempotency in JetStream](/posts/nats-jetstream-idempotency/)), and they interact with [rate limiting](/posts/go-rate-limiting-caching/).

> Honest labelling: section 1 is a real HTTP client and server on loopback (`httptest`), with seeded failures; I re-ran it with Go 1.27. Sections 2, 3 and 4 are **simulations** with a simulated clock and seeded randomness; a simulated network is not a real one. The machine was busy (load average around 4 when I re-ran), so I show counts, never timings. The demo is a local example, not a repo.

## 1. A real client against a flaky server

Let me start with a real client. The server fails by a seeded random draw for each request: 15% of the time it answers `503` with a `Retry-After: 1` header (meaning "come back in one second"), 15% of the time it is too slow for the client's 100 ms per-attempt timeout, 10% of the time it resets the connection, and the rest of the time it answers `200`. A path called `/forbidden` always answers `403`.

The client does this for each logical request:

- every attempt is wrapped in `context.WithTimeout`, 100 ms;
- all attempts together sit under one overall deadline (20 seconds);
- at most 5 attempts;
- between attempts it sleeps with a backoff: a random time between 0 and 10 ms, then 0 to 20 ms, 0 to 40 ms, and so on (doubling);
- if the server sent a `Retry-After` longer than that, it waits for that instead;
- a `403` is never retried, because retrying cannot fix a request that is simply not allowed.

It makes 30 requests to `/item/N` and one to `/forbidden`, and counts what went wrong:

```
logical requests: 31, attempts: 46, succeeded: 30, failed: 0
  HTTP 403 (not retried)       1
  HTTP 503                     8
  context deadline exceeded    6
  transport error              1
sample: Get "http://127.0.0.1:PORT/item/1": context deadline exceeded
sample: Get "http://127.0.0.1:PORT/item/3": read tcp 127.0.0.1:PORT->127.0.0.1:PORT: read: connection reset by peer
```

The first line says: 31 logical requests needed 46 attempts, and all 30 real requests eventually succeeded (the 31st is the `/forbidden` one). The 15 extra attempts are the 15 failures that were retried: 8 + 6 + 1. The `403` is in the table too, but it was not retried, so it adds no extra attempt.

The two samples show two different kinds of failure. A deadline means the client gave up waiting (the server may still be working on it). A `connection reset by peer` means the connection was torn down.

One thing to know about these numbers: they are not the same as in my original run (Go 1.26), which showed 52 attempts and 7 transport errors. In my Go 1.27 re-runs the attempts were 45 or 46 and the transport errors 0 or 1, while the counts of `503` (8) and timeouts (6) and the 30 successes were the same each time. To find out why, I counted what the server did in a scratch copy of the demo: in every run it drew 7 resets, and it received 51 requests in total, more than the 45 or 46 attempts our loop made. I did not trace each case, but I believe the transport inside Go's `net/http` re-sent the difference by itself: it can retry a GET when a reused connection dies before any response, without our code ever seeing an error. So the counts for resets depend on the Go version and on timing, and you should not expect to reproduce them exactly; the other counts are stable.

The rules I follow, which the demo's client implements:

- Retry only idempotent operations, or operations that carry an idempotency key. Otherwise a retry after a lost reply does the work twice, as in the first post.
- Retry only errors that may go away: timeouts, connection errors, `5xx`. Never `4xx`, which means the request itself is wrong.
- Honour `Retry-After` if it is longer than your own delay: the server knows better how long it needs.
- Bound everything: a cap on attempts per call, and one overall deadline for the whole thing.

## 2. The retry storm (simulation)

Now the opening story, with numbers. The {{< term "retry-storm" "retry storm" >}} simulation has 1000 clients and one server that can handle 300 requests per tick (a tick is a unit of simulated time). Each client's first attempt arrives at tick 0 or 1, about 500 clients per tick. On ticks 1, 2 and 3 there is an outage where every request fails. Outside the outage the server serves up to 300 requests per tick and rejects the rest. A client gives up after 12 failures.

The only thing that changes between runs is how long a client waits before retrying after the n-th failure (n = 1, 2, 3, ...). The formulas are as I remember them from the AWS Architecture Blog article "Exponential Backoff And Jitter" (details hedged; the implementation is my own), with base 2 and cap 32 ticks:

- **immediate**: no wait (the retry comes at the next tick);
- **fixed 4**: always 4 ticks;
- **{{< term "exponential-backoff" "exponential" >}}, no jitter**: `min(cap, base × 2^n)`, so 4, 8, 16, 32 ticks;
- **full {{< term "jitter" "jitter" >}}**: a random number between 0 and the exponential value;
- **equal jitter**: half the exponential value plus a random number between 0 and the other half;
- **decorrelated**: `min(cap, random(base, previous × 3))`, based on the previous wait.

```
strategy           requests   served  gaveUp  lastTk  peak
immediate              3800     1000       0       6   700
fixed 4                1900     1000       0       9   500
exp, no jitter         1900     1000       0      13   500
exp, full jitter       2254     1000       0      27   586
exp, equal jitter      1979     1000       0      11   500
decorrelated           1881     1000       0      12   500

exp, no jitter:   500 500 0 0 200 500 0 0 0 0 0 0 0 200
exp, full jitter: 500 586 247 221 191 158 65 57 58 64 55 22 1 6 5 2 4 4 4 3 0 0 0 0 0 0 0 1
```

Columns: `requests` is the total number of requests the server received, `served` how many clients finally succeeded (all 1000 in every row; nobody gave up), `lastTk` the last tick with any request, and `peak` the largest number of requests in one tick.

Before the discussion, let me trace "exp, no jitter" by hand, because the second block of output is exactly this. At tick 0, 500 requests arrive; 300 are served and 200 rejected. The 200 wait 4 ticks, so 200 come back at tick 4. At tick 1, 500 more arrive during the outage and all fail; they come back at tick 5. At tick 4 the outage is over, so the 200 are all served. At tick 5 the 500 arrive together, 300 are served and 200 are rejected, and they wait 8 ticks (their second failure), so 200 come back at tick 13. That is the series `500 500 0 0 200 500 0 0 0 0 0 0 0 200` above: the clients stay synchronised, and each wave hits the server at the same moment.

Now compare. Immediate retries send nearly four requests per client (3800 for 1000 clients) and the peak is 700 in one tick. Without jitter, the waves of 500 and 200 repeat with empty ticks between. Full jitter turns the waves into a slope (500, 586, 247, 221, 191, ...), at the cost of a longer tail (the last request is at tick 27) and more total requests here (2254 against 1900). So jitter is not "fewer requests"; it is smoother load. In my experience that smoothness is what lets a recovering server actually recover. The numbers depend on my parameters; do not read them as general rates.

## 3. Amplification and the retry budget (simulation)

Retries at one level are manageable. The danger is retries at several levels at once. Picture a chain: a client calls service A, A calls B, B calls C, and C is down. The client retries A up to 3 times, A retries B up to 3 times for each request, and B retries C up to 3 times for each of its requests. How many requests reach C for one user call, when everything fails?

3 × 3 × 3 = 27. Each layer multiplies the one before it: A receives 3 requests, B receives 3 × 3 = 9, and C receives 3 × 3 × 3 = 27. A service that is already failing gets 27 times its normal load, from one click.

A {{< term "retry-budget" "retry budget" >}} is the usual defence. Each retrying caller has a token bucket that earns tokens as requests flow and spends one token per retry. When the bucket is empty, there is no retry, and the call fails fast instead. In the demo the bucket earns 0.1 token at the start of every attempt and holds at most 10. The simulation runs 1000 calls against a bottom service that fails 100% or 50% of the time, with and without budgets. "Requests per layer" is how many requests A, B and C received in total:

```
bottom fails 100%, budget=false: top calls 1000, ok 0, requests per layer [3000 9000 27000], last layer 27.00x
bottom fails 100%, budget=true : top calls 1000, ok 0, requests per layer [1222 1493 1824], last layer 1.82x
bottom fails  50%, budget=false: top calls 1000, ok 1000, requests per layer [1003 1145 1995], last layer 2.00x
bottom fails  50%, budget=true : top calls 1000, ok 760, requests per layer [1137 1305 1510], last layer 1.51x
```

Read the first two lines. Without a budget the chain turns 1000 user calls into 3000, 9000 and 27000 requests, exactly the 3 × 3 × 3. With budgets, each layer adds only about 22% extra requests: 1222 / 1000 = 1.222, 1493 / 1222 = 1.222 and 1824 / 1493 = 1.222, and 1.222³ is about 1.82. (Why 22% and not 10%? The bucket in this implementation earns its 0.1 at the start of every attempt, including a retry that is then refused, so a failing call earns about 0.2 token, and each retry it makes earns a little more. Solving that balance gives 2/9, about 22% retries per call.)

The last two lines are the price. When the bottom fails only half the time, no-budget retries rescue every call (1000 of 1000 succeeded, with 2x load on the bottom). With budgets, only 760 of 1000 succeeded, because some retries were refused. That is the trade: retry less, protect the dependency. A common piece of advice is to retry in one layer only, and to let the others fail fast.

## 4. Deadline budgets and hedging

Another way retries cause waste is when the caller has already given up but the work continues. The fix is to give the whole request one deadline and pass the **remaining** time down the chain, so that every hop knows how long it is worth working. In a simulated chain where each hop spends 50 ms before calling the next, with a 300 ms total budget:

```
overall budget 300 ms; hop work 50 ms each
  gateway  sees remaining deadline 300 ms
  orders   sees remaining deadline 250 ms
  stock    sees remaining deadline 200 ms
  db       sees remaining deadline 150 ms
static 300 ms timeout per hop: db may still be working at t=300+ when the caller gave up at t=300
```

Each hop sees the budget minus what has already been spent. With a fixed 300 ms per hop, by contrast, the database can keep working long after the original caller left, wasting capacity on an answer nobody will read. gRPC carries this idea as a `grpc-timeout` header ([gRPC over HTTP/2](/posts/net-grpc-over-http2/)). Too-long timeouts also hold scarce resources such as connections ([connection pooling](/posts/db-connection-pooling/)).

The last tool is the opposite of waiting. A {{< term "hedged-request" "hedged request" >}} sends a second copy of a request if the first one has not answered after a short time (here 20 ms), and takes whichever reply arrives first. In the simulation, 95% of latencies are around 10 ms and 5% are 200 to 300 ms, and 10000 requests are made:

```
hedging: 10000 requests, >100 ms: 502 without hedge, 25 with hedge; extra requests sent: 502 (5.0%)
```

Without hedging, 502 requests (about 5%) took more than 100 ms. With hedging there are only 25. The arithmetic is simple: a request is slow only if both copies are slow, and 0.05 × 0.05 = 0.0025, which is 25 in 10000. The extra load is also 502 requests (5.0%): only the slow first requests were hedged, because the fast ones answered before 20 ms. The simulation assumes the two latencies are independent. Real slowness is often correlated (both copies hit the same overloaded machine), so do not expect this result in production.

## Hidden costs of retrying

- Every retry loop needs a cap on attempts and an overall deadline. Without them, a retry loop is an infinite loop that happens to sleep.
- Add jitter to every backoff. The simulation shows smoother load; I did not measure a real production benefit here.
- Retrying at several layers multiplies (3 × 3 × 3 = 27). Use a budget, or retry in a single place.
- A timeout is "unknown": make the operation idempotent first, then retry.
- Hedging needs calls that are safe to repeat and spare capacity, since it adds load by design.

## What's next

Next, “Circuit breakers and bulkheads”: when a dependency stays down, the better move is to stop calling it.
