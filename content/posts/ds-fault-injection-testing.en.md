+++
date = '2027-06-06T10:00:00+03:30'
draft = false
title = 'Failure testing with fault injection'
description = 'Fault injection testing in Go: a loopback fault proxy and RoundTripper wrapper that expose four real client bugs, with seeded runs you can replay.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "fault-injection", "chaos-engineering", "testing", "go"]
cover = { image = "/images/covers/ds-fault-injection-testing.png", alt = "Failure testing with fault injection", hiddenInSingle = true }
+++
In one run of the demo below, every order "succeeded", and yet 16 customers paid twice. Nothing crashed, no error reached the user, and a test that only checks "did the order succeed?" would have passed. The payment went through, the reply was lost on its way back, and the client, doing what a careful client does, tried again.

That is the property we want here: an order is charged once, even when the network misbehaves. [Timeouts and retries](/posts/ds-timeouts-retries-backoff/) and [circuit breakers](/posts/ds-circuit-breaker-bulkhead/) are code for the day a dependency misbehaves, and code that has never run on that day is a guess. {{< term "fault-injection" "Fault injection" >}} makes the bad day happen on purpose, cheaply: you put something between the client and the server that delays, drops or breaks requests, and watch what your code does. The method around it, with a hypothesis and a measurable result, is called {{< term "chaos-engineering" "chaos engineering" >}}. This post answers three practical questions: what to inject, what to assert afterwards, and how to keep a failure reproducible, so that a test that failed once can fail again. The [previous post](/posts/ds-distributed-rate-limiting/) was about limits; for test basics see [Go testing](/posts/go-testing-basics/) and [JetStream tests](/posts/nats-jetstream-testing/).

> Honest labelling: everything runs on loopback on one machine. A proxy on 127.0.0.1 is a model of a bad network, not a bad network. I re-ran the whole demo with Go 1.27, twice, and `go test -race` passes; the two runs gave byte-identical output, and the numbers below match the original run. Randomness is seeded and I print counts, not timings (the machine was busy for the original run; the re-runs were at a load average of about 2.5).

## A taxonomy of faults

First, what can go wrong between two services? A short list: latency, errors (5xx, 4xx), connection reset or refused, hangs (the connection is accepted and nothing ever comes back), truncated responses, corrupted payloads, slow bodies, clock skew, resource exhaustion, and a killed process. My demo covers latency, 503, resets, hangs, truncated bodies and slow bodies at the proxy, and the in-process wrapper below also injects errors and corrupted bodies. It does not cover 4xx, connection refused, clock skew (that is the exercise), resource exhaustion or a killed process.

## Two injectors

There are two ways to inject a fault, and I built one of each.

The first is a TCP proxy that sits between the client and the server. The client talks to the proxy, and the proxy talks to the real server and misbehaves in a chosen way for each connection. The idea is the one used by Toxiproxy, which I know by name and did not run. The faults my proxy can apply:

- **latency**: wait before forwarding (in a `Schedule` I draw 20 to 39 ms at random);
- **bandwidth**: forward the response very slowly;
- **close_after**: forward N bytes of the response (headers included) and then close;
- **reset**: reset the connection immediately;
- **blackhole**: accept the connection and never answer;
- **status503**: answer a canned 503 without involving the server;
- **drop_response**: forward the request, let the server finish its work, then reset the client's connection. The server did the job and the client does not know. This is the nastiest one.

The second is an `http.RoundTripper` wrapper for unit tests that need no socket at all. The `RoundTripper` is the part of Go's HTTP client that actually sends the request, so wrapping it lets a test inject an error, a 503, latency, a truncated body or a corrupted body without any network.

A *fault plan* decides which fault each call gets. It is a `Schedule{Seed, weights}`, and the fault for connection number `i` depends only on `(seed, i)`, never on timing or arrival order. That is the whole trick for reproducibility, and we will use it at the end.

To see what each fault looks like from the client's side I made one GET of a 100-byte body per fault, with a 300 ms deadline:

```
  pass           -> status 200, 100 body bytes, read: ok
  latency        -> status 200, 100 body bytes, read: ok
  bandwidth      -> deadline exceeded
  close_after    -> status 200, 13 body bytes, read: unexpected EOF
  reset          -> connection reset (or broken pipe)
  blackhole      -> deadline exceeded
  status503      -> status 503, 0 body bytes, read: ok
  drop_response  -> connection reset (or broken pipe)
```

The first line is the control: no fault, and the client gets the body. `latency` of 50 ms is invisible because it finishes inside the deadline. `bandwidth` (200 bytes per second) and `blackhole` both end the same way for the client, with the deadline exceeded, although the causes are different. `close_after` is the interesting one: the proxy forwarded 150 bytes, the headers used most of them, so only 13 bytes of body arrived. The client gets a `200` status and only finds out while reading the body that it is broken (an unexpected EOF). `reset` sometimes showed up as a broken pipe, so I classify the two together. `drop_response` looks to the client like a plain reset, which is exactly why it is dangerous: the client cannot tell it from a request that never arrived.

## The experiment method

A fault is only a test if you know what you expect. The Principles of Chaos Engineering, as I understand them, give a recipe: define a {{< term "steady-state" "steady state" >}} as a measurable metric, hypothesise that it holds under a fault, inject the fault, observe, compare, and keep the {{< term "blast-radius" "blast radius" >}} (how many users or requests can be hurt) small.

Here the steady state is the SLO idea from [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/): at least 99% of 200 orders succeed within a 300 ms {{< term "deadline" "deadline" >}}. The hypothesis: with 10% injected 503s (seed 7), retries keep the steady state. I tried three clients. The `attempts` column is the total number of requests sent:

```
  no retries                         ok=174/200 ( 87.0%) attempts=200
    steady state: VIOLATED
  3 attempts, no budget              ok=200/200 (100.0%) attempts=226
    steady state: HOLDS
  3 attempts, budget 20%, jitter     ok=198/200 ( 99.0%) attempts=224
    steady state: HOLDS
```

(The demo prints more columns, upstream hits and charges; they are not needed here.) Without retries, 26 orders fail and the steady state is violated: 87% is below 99%. With 3 attempts every order succeeds, at the cost of 26 extra attempts. The third client is limited by a {{< term "retry-budget" "retry budget" >}}, which caps retries at a share of the traffic (here 20%), and by {{< term "jitter" "jitter" >}}, which spreads them in time. It sits exactly on the line: 198 of 200 is 99.0%, and my check is "at least 99%", so it holds, but with no margin. It sent 224 attempts instead of 226, so the budget refused a couple of retries; I did not trace each order.

## Four bugs it finds

The point of injecting faults is to find bugs that ordinary tests miss. Here are four, each with a fault, a check, and a before and after.

**a) Retry without an idempotency key.** The fault: the response is lost after the server applied the charge (15% `drop_response` and 5% 503, over 100 orders). The client retries up to 3 times. The check: not just the success rate, but the server's own count of charges.

```
  retry, no key (before)             ok=100/100 attempts=122 charges=118 double-charged=16
  retry + Idempotency-Key (after)    ok=100/100 attempts=122 charges=100 double-charged=0
```

In both rows every one of the 100 orders reported success. In the first row the server recorded 118 charges for 100 orders: when a response was lost, the retry charged the customer again, and 16 orders were charged more than once (118 − 100 is 18 extra charges for 16 orders, so some orders were charged three times). The success rate never shows this, so the test must also check the server's own count. The fix is an {{< term "idempotency" "idempotency" >}} key: the client sends the same `Idempotency-Key` header with every attempt of an order, and the server recognises a repeat and does not charge again. The second row has the same 122 attempts and exactly 100 charges.

**b) No timeout.** The fault: blackhole, which accepts the connection and never answers. The test waits up to 2 seconds for the call to return:

```
  no timeout (before)        returned within 2s: false
  300ms deadline (after)     returned within 2s: true
```

Without a timeout the call is stuck on a server that never answers, and it would be stuck forever: the test only waited 2 seconds and then closed the proxy to free it. With a 300 ms deadline the call comes back.

**c) Retry storm.** The fault is not a random one this time: the upstream is down, every request gets a 503, and the client makes 5 attempts for each of 40 orders. A {{< term "retry-storm" "retry storm" >}} multiplies the load on something that is already sick:

```
  5 attempts, no budget (before)     upstream-hits=200 for 40 orders (x5.00 amplification)
  5 attempts, budget 10% (after)     upstream-hits= 43 for 40 orders (x1.07 amplification)
```

Without a budget every order hits the failing service 5 times: 40 × 5 = 200. With a 10% budget, retries are limited to about a tenth of the first attempts: 43 hits, which is 40 first attempts plus 3 retries. The outage is not survived either way, since the service is down. The budget only stops us making it worse.

**d) A {{< term "circuit-breaker" "circuit breaker" >}} that never closes.** I planted this bug on purpose in a small tick-clocked breaker (the same idea as in [circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/)), to see whether the test finds it: a successful half-open probe does not close the circuit. The dependency fails during ticks 20 to 49 (fake ticks, with the in-process wrapper). The check: after the dependency recovers, do requests succeed again? I counted successes in ticks 65 to 119, 55 ticks:

```
  probe bug (before)   final state=half-open rejected= 94 ok in ticks 65..119:  0/55
  probe fixed (after)  final state=closed    rejected= 27 ok in ticks 65..119: 55/55
```

Follow the fixed breaker (threshold 3, open for 10 ticks): three failures at ticks 20, 21 and 22 open it; it rejects ticks 23 to 31 (9 requests), probes at tick 32 (the dependency is still down, so it opens again), rejects 33 to 41, probes at 42 (still down), rejects 43 to 51, and probes at tick 52. That probe succeeds and the breaker closes. That is 27 rejected, and 55 out of 55 in the later window. With the bug, the probe at tick 52 succeeds but the breaker stays half-open, and a half-open breaker allows no other request: it rejects every tick from 53 to 119 (67 more), 27 + 67 = 94, and not one request succeeds, long after the dependency is healthy. Real bugs will be stranger than this one. The tests pass with `go test -race`.

## Reproducing a failure by seed

A failure you cannot reproduce is only an anecdote. Because the fault for connection `i` depends only on `(seed, i)`, the same seed should give the same run. To check, I record a transcript of a run (the fault log, the outcome of each order, and the final charges) and print its md5, which is a short fingerprint of the whole text:

```
  seed 42, run 1: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 42, run 2: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 43, run 1: md5 3a1de6b1fe8c0b3e9b36d2e12f23983d
```

The same seed gives the same fingerprint, a different seed gives a different one, and two full runs of the program gave byte-identical output. Then a sweep of seeds: for seeds 1 to 30, 20 orders each, 3% dropped responses, retry without a key. The demo prints which seeds produced a double charge, and then replays the first one twice:

```
  seeds with a double charge: [3 6 7 8 12 13 15 18 19 21 23 28 29 30] (14 of 30)
  replay seed 3 (run 1): double-charged orders [4]
  replay seed 3 (run 2): double-charged orders [4]
```

14 of the 30 seeds hit a double charge, and replaying seed 3 twice gave the same double-charged order, order 4. A {{< term "flaky-test" "flaky failure" >}} became a reproducible one: "seed 3, order 4" is something you can debug. This works only because the client in the demo is sequential. With concurrent clients the connections would arrive in a different order each time and the same index would not mean the same request.

Going further is {{< term "deterministic-simulation" "deterministic simulation" >}}, where time and the network are simulated too, so that any failure can be replayed exactly; as far as I know FoundationDB, TigerBeetle and Antithesis work this way. Jepsen tests [consistency models](/posts/ds-consistency-models/) with injected faults. Chaos Monkey, LitmusChaos, Gremlin and AWS FIS inject faults into real infrastructure. I used none of these.

## Where to run it

In my experience: RoundTripper unit tests in CI on every commit, the proxy in CI or staging, and production only with guardrails. A {{< term "game-day" "game day" >}}, a planned session where the team injects failures on purpose, needs a runbook, named roles, abort conditions and a communication channel. I would never inject faults in production without them.

## Rules for a fault experiment

- **State the hypothesis first, with a number.** "Retries keep at least 99% of orders under 300 ms" can fail. "The system is resilient" cannot.
- **Check correctness, not only availability.** All 100 orders succeeded and 16 were charged twice. The server's own record of what happened is part of the assertion.
- **Keep the blast radius small.** Start with one client, one dependency and a low fault rate, and increase only when the result is understood.
- **Remember what the model misses.** A proxy on loopback is not a real network: packet loss, congestion and real routing behaviour are not here.

## Exercise

Add a clock-skew fault to the RoundTripper (shift the `Date` header) and test a client that trusts it.

## What's next

[Modular monolith or microservices?](/posts/ds-modular-monolith-vs-microservices/) Each network boundary is a new place for these faults to happen. Should you create more of them?
