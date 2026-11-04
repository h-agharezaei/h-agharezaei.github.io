+++
date = '2027-05-08T10:00:00+03:30'
draft = false
title = 'Circuit breakers and bulkheads'
description = 'A Go circuit breaker built from scratch with an injected clock, plus bulkheads and load shedding, shown with seeded simulations and real counts.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "circuit-breaker", "bulkhead", "resilience", "go"]
cover = { image = "/images/covers/ds-circuit-breaker-bulkhead.png", alt = "Circuit breakers and bulkheads", hiddenInSingle = true }
+++
Your service calls a recommendations service to decorate every page. One afternoon the recommendations service does not go down. It just gets slow: instead of answering in 50 ms it takes 30 seconds. Nothing is broken enough to return an error. Each of your requests now waits, holding a goroutine, a connection and some memory, and new requests keep arriving at the same rate as before. Soon your service is full of parked requests and is sick too. Then whoever calls you gets sick. The failure has spread up the chain, which is called a {{< term "cascading-failure" "cascading failure" >}}.

[The previous post](/posts/ds-timeouts-retries-backoff/) gave us timeouts and polite, jittered retries. They help with a dependency that fails now and then. They do not help with one that stays sick, because every caller keeps paying the cost of waiting for each attempt. What we want in that case is simple: stop calling it for a while, and do not let it take more than its share of our capacity. That gives this post its two tools:

- A {{< term "circuit-breaker" "circuit breaker" >}} notices that a dependency keeps failing and stops calling it for a while. It is named after the breaker in your fuse box, which cuts the power when something is wrong so the wiring does not burn.
- A {{< term "bulkhead" "bulkhead" >}} gives each dependency its own limited share of your resources. It is named after the walls inside a ship's hull: if one compartment floods, the others stay dry.

I build both in Go and measure what they do. For the concurrency tools used below, see [concurrency patterns in Go](/posts/go-concurrency-patterns/).

> Honest labelling: everything here is a simulation on one machine. Time is fake "ticks" from a clock I inject, randomness is seeded, and I show counts only, never timings. A simulated dependency is not a real network. I re-ran the demo with Go 1.27 and `go test -race` passes; the output is identical to the original Go 1.26 run, line for line. The demo is a local example, not a repo.

## The breaker: three states

A breaker is a small state machine with three states. Think of it as a guard standing in front of the dependency:

- **Closed** is normal operation. Calls go through, and the guard counts failures in a row. One success resets the count to zero.
- **Open** means "do not even try". The guard rejects every call immediately, without touching the dependency. A rejected call costs almost nothing, so the caller can answer fast with a fallback (a cached or default answer) or a clear error.
- **Half-open** is the careful test. After a while the guard lets one call through, a *probe*, to see if the dependency has recovered. If the probe succeeds, the breaker closes again. If it fails, the breaker goes back to open and the waiting time starts over.

A closed breaker trips to open when the number of failures in a row reaches a threshold. After `OpenFor` ticks of being open, it becomes half-open. That is all of it.

The code is two methods. Before each call you ask `Allow`, and after each call you tell the breaker the result with `Record`:

```go
func (b *Breaker) Allow() bool   // false means fail fast
func (b *Breaker) Record(ok bool)
```

The clock is a plain `func() int64` that I pass in. In the demo it returns a tick number I advance by hand, so the tests never sleep and the timeline is exactly reproducible. The tests are table-driven (one row per scenario: below the threshold, trips, half-open after `OpenFor`, probe limit, probes succeed, probe fails) and pass with `go test -race`.

Let's watch one timeline. The settings are: threshold 3, open for 10 ticks, one probe. A caller tries once every 2 ticks (tick 0, 2, 4, ...). The dependency is down until tick 24 and healthy after that. The loop is the same shape you would write in real code: ask `Allow`, and only if the answer is yes, make the call and `Record` the result. Each line below is a state change:

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

Reading it line by line:

- Calls at ticks 0, 2 and 4 all fail. The third failure reaches the threshold, so at tick 4 the breaker opens.
- It stays open for 10 ticks, until tick 14. The calls at ticks 6, 8, 10 and 12 are rejected immediately (4 rejections).
- At tick 14 it becomes half-open and lets one probe through. The dependency is still down, so the probe fails and the breaker opens again for another 10 ticks. The calls at 16, 18, 20 and 22 are rejected (4 more).
- At tick 24 the same thing happens: the probe fails, because the dependency only recovers at tick 25. Rejected at 26, 28, 30 and 32 (4 more).
- At tick 34 the probe succeeds and the breaker closes. Normal traffic resumes.

So `trips=3` (the breaker opened three times) and `rejected=12` (3 times 4 rejected calls). Of the 18 calls made between tick 0 and tick 34, only 6 (ticks 0, 2, 4, 14, 24 and 34) reached the dependency; the other 12 were turned away. I only implemented "consecutive failures" as the rule for tripping. A failure *rate* over a sliding window is the other common rule; I did not build it.

## Why you want it: a slow dependency

Now back to the opening story. The simulation sends 5 requests per tick for 120 ticks. The dependency is healthy (it answers in 1 tick) except during ticks 20 to 79, when it is slow (a call would take 30 ticks). Every call in flight is a parked goroutine in the demo, so we can count them. A client timeout of 10 ticks ends a slow call as failed.

I ran three versions: no timeout and no breaker, a timeout only, and a timeout plus a breaker (threshold 5, open for 15 ticks, one probe):

```
  no breaker, no timeout       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak=150 mean=77.5, goroutines peak=150, trips=0
  no breaker, timeout 10       reached-dependency=600 ok=295 failed=300 fallback=  0 | in-flight peak= 50 mean=27.5, goroutines peak= 50, trips=0
  breaker, timeout 10          reached-dependency=273 ok=216 failed= 52 fallback=327 | in-flight peak= 50 mean= 6.2, goroutines peak= 50, trips=3
```

The columns: `reached-dependency` is how many calls were actually sent to the dependency, `ok` how many came back healthy, `failed` how many were slow, `fallback` how many requests the breaker answered without calling anything. After the bar, `in-flight` is the number of calls waiting at the same time (its peak and its average over the 120 ticks).

- **No timeout.** A slow call lasts 30 ticks, and 5 new ones arrive every tick, so the waiting calls pile up to 5 times 30 = 150, the peak. The load on you grows with the dependency's slowness, without limit.
- **With a timeout of 10 ticks.** A slow call is cut after 10 ticks, so the peak is 5 times 10 = 50, and the mean drops from 77.5 to 27.5. The timeout puts a ceiling on the damage, but you still send all 600 calls into a dependency that is failing.
- **With the breaker.** The peak is the same 50. That is expected: the breaker knows nothing until the first slow calls have timed out, so for ticks 20 to 29 it lets 50 calls through. What changes is everything after. The mean falls to 6.2, only 273 calls reach the dependency, and 327 requests get their fallback immediately.

To see why the numbers come out like this, I printed the state changes in a scratch copy of the demo (the same run, one extra `OnChange` line; the repo demo is unchanged). The breaker opened at tick 30, when the first five slow calls timed out. It probed at tick 45 and 70 (both slow, so it reopened), and at tick 80 the dependency became healthy. The next probe was at tick 95, it succeeded, and the breaker closed at tick 96. This also explains the other columns: `failed=52` is the 50 slow calls before the breaker opened plus the 2 failed probes, and `trips=3` is the three times it opened (at ticks 30, 55 and 80).

There is a price in the `ok` column: 216 against 295. The dependency was healthy again from tick 80, but the breaker kept rejecting until its next probe at tick 95 succeeded. Those are healthy calls we did not make. A breaker trades a bit of availability right after recovery for protection during the failure. Also, the simulation does not model the dependency recovering faster because it was relieved of load, which is one of the reasons people use breakers. I did not measure that.

## Bulkheads and load shedding

A breaker protects you from one dependency that has gone bad. A bulkhead handles the cases a breaker cannot see, like a dependency that is slow but not failing enough to trip anything. The idea is a limit per dependency: a fixed number of workers (or of concurrent calls) that only calls to that dependency may use. In Go that can be a {{< term "semaphore" "semaphore" >}}, for example a buffered channel with one slot per allowed call.

Here is a small example. Dependency A is slow: each call takes 30 ticks, and 2 requests per tick arrive for it. Dependency B is healthy: each call takes 1 tick, and 3 requests per tick arrive for it. B gets 300 requests in 100 ticks. Our service has 20 workers. Do the arithmetic for A: 2 requests per tick, each holding a worker for 30 ticks, would need 60 workers in steady state. We have 20. So A can use up the whole pool by itself, in about 10 ticks, and B, which only needs about 3 workers, gets nothing.

I tried four ways of handling this. A client gives up if it has waited 10 ticks in a queue (`gave-up`). *Shedding* ({{< term "load-shedding" "load shedding" >}}) means a full pool rejects a request at once, for example with an HTTP 503 or 429, instead of letting it wait. (In the table `ok` is counted when a request gets a worker.)

```
  shared 20, unbounded queue         B: ok= 27 shed=  0 gave-up=240 | A: ok= 79 shed=  0 gave-up=100 | max queue=149
  shared 20, shed at once            B: ok= 26 shed=274 gave-up=  0 | A: ok= 80 shed=120 gave-up=  0 | max queue=0
  shared 20, queue limit 10          B: ok= 80 shed=201 gave-up= 15 | A: ok= 74 shed=105 gave-up= 15 | max queue=10
  separate 10 + 10, shed at once     B: ok=300 shed=  0 gave-up=  0 | A: ok= 40 shed=160 gave-up=  0 | max queue=0
```

- **Shared pool, unbounded queue.** Everyone waits in one line. B almost never gets served (27 of 300); 240 of its requests waited 10 ticks and gave up. The queue grew to 149 requests. This is what happens when nothing pushes back on the producer, the missing {{< term "backpressure" "backpressure" >}}. (In this simulation a request that has given up is dropped when it reaches the front, so no worker is wasted on it. A real server often does not know the client has left and does the work anyway; I did not simulate that.)
- **Shared pool, shed at once.** No queue, so nobody waits, but B is still starved: 26 served and 274 rejected. Shedding makes the failure fast, but it does not fix the sharing problem.
- **Shared pool, queue limit 10.** A short queue helps B a bit (80 served), but A's slow calls still hold the workers.
- **Separate pools, 10 + 10.** Now A can hold at most its own 10 workers. B needs about 3, so all 300 of its requests succeed. A takes its own losses: its 10 workers are busy for 30 ticks at a time, so only 10 requests start at each of ticks 0, 30, 60 and 90, 40 in total, and 160 are shed. Exactly what you want: A's problem stays A's problem.

## Breaker and retries: which goes outside?

The last question is how a breaker and retries fit together. There are two orderings, and they behave differently. With 3 attempts per request, breaker threshold 5, open for 20 ticks, and 200 requests (one per tick):

- **Retry inside**: every *attempt* asks the breaker, so the breaker sees each failed attempt.
- **Breaker outside**: the breaker wraps the whole retry loop and sees one result per *request*.

I tried both against a dependency that is completely down, and against one that is flaky: 60% of calls fail, with a seeded random generator.

```
  dependency down, retry inside      dependency calls= 14 ok requests=  0 fast-fails=199 trips=10
  dependency down, breaker outside   dependency calls= 42 ok requests=  0 fast-fails=186 trips=10
  flaky 60%, retry inside            dependency calls=169 ok requests= 74 fast-fails=113 trips=6
  flaky 60%, breaker outside         dependency calls=380 ok requests=161 fast-fails=  0 trips=0
```

When the dependency is dead, "inside" is cheaper: 14 calls against 42. The arithmetic: with retry inside, the breaker trips after 5 failed attempts, and then each of the 9 later probes is a single call, so 5 + 9 = 14. With the breaker outside, a request that fails has already used 3 attempts, so it takes 5 requests times 3 = 15 calls to trip, and each of the 9 probes costs 3 calls: 15 + 27 = 42.

When the dependency is merely flaky, the picture flips. With "inside", the breaker sees every single failed attempt, so ordinary noise trips it (a streak of 5 failures in a row is not unusual when 60% of calls fail). It rejected 113 requests outright, and only 74 succeeded. With "outside", the breaker sees a request fail only when all 3 attempts fail, which happens about 0.6 × 0.6 × 0.6 = 22% of the time. Five of those in a row is rare, so it never trips and 161 requests succeed, at the cost of 380 calls to the dependency. Notice the trade: "inside" protected the dependency (169 calls instead of 380) but gave up most of the work.

My rule: for a flaky but useful dependency I put the breaker outside, and I never retry when the error is `ErrOpen` (the breaker's own "circuit open" error), because retrying a rejection only burns attempts. Whichever way you nest them, retries need {{< term "idempotency" "idempotent" >}} calls, as in the previous post.

## What to emit

A breaker that nobody can see is hard to trust. Expose its state as a gauge, and count trips, rejections and fallbacks served. In my experience, alert on "open for longer than N minutes" and on the rejection rate, not on every single trip, because a trip is the breaker doing its job. A breaker that flaps between open and half-open for a long time hints at a {{< term "gray-failure" "gray failure" >}}: the dependency is not dead, but too slow or too flaky to be useful.

In production I would use a library rather than my own. According to its README, `sony/gobreaker` has closed, open and half-open states, a `MaxRequests` setting for half-open, an open `Timeout`, a `ReadyToTrip` function that decides when to trip, and an `OnStateChange` hook. I read the README and did not run it. Hystrix and Resilience4j are, as far as I know, where the pattern became popular in the Java world.

## Getting a breaker wrong

- **No fallback.** If an open breaker just returns an error, your users see a faster failure, nothing more. Decide up front what the caller does when the breaker is open: a cached value, a default, a degraded page, or at least a clear error.
- **Using the breaker instead of a timeout.** The breaker only opens after it has seen failures, and a call that hangs is not a failure the breaker can see until something ends it. Without a client timeout, calls pile up behind the slow dependency before the breaker learns anything.
- **Counting the wrong failures.** Count only real dependency failures (timeouts, connection errors, 5xx). If your own validation errors or a 404 count, bad user input can open the breaker and cut off everyone else.
- **Trusting my numbers.** Pool sizes, thresholds and open times here are made up for the simulation. For a real system they need load tests, and they depend on your traffic.

## What's next

[Replication and quorums](/posts/ds-replication-quorum/) is the next post. Here we guarded ourselves against one sick dependency; there we keep several copies of the data and decide how many of them must agree.
