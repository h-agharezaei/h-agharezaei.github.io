+++
date = '2027-06-06T10:00:00+03:30'
draft = false
title = 'Failure testing with fault injection'
description = 'Fault injection testing in Go: a loopback fault proxy and RoundTripper wrapper that expose four real client bugs, with seeded runs you can replay.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "fault-injection", "chaos-engineering", "testing", "go"]
cover = { image = "/images/covers/ds-fault-injection-testing.png", alt = "Failure testing with fault injection", hiddenInSingle = true }
+++

[The previous post](/posts/ds-distributed-rate-limiting/) was about limits. [Timeouts and retries](/posts/ds-timeouts-retries-backoff/) and [circuit breakers](/posts/ds-circuit-breaker-bulkhead/) are code for the day a dependency misbehaves, and code never run on that day is a guess. {{< term "fault-injection" "Fault injection" >}} makes the bad day happen on purpose, cheaply. The method around it is {{< term "chaos-engineering" "chaos engineering" >}}. Test basics: [Go testing](/posts/go-testing-basics/), [JetStream tests](/posts/nats-jetstream-testing/).

> Honest labelling: everything is Go 1.26 on loopback, one machine. A proxy on 127.0.0.1 models a bad network; it is not one. Randomness is seeded and I print counts, not timings (the machine was busy).

## A taxonomy of faults

Latency, errors (5xx, 4xx), connection reset or refused, hangs, truncated responses, corrupted payloads, slow bodies, clock skew, resource exhaustion, process kill. My demo covers the first seven; I did not build the last three.

## Two injectors

First, a TCP proxy between client and server (the idea of Toxiproxy, which I know by name and did not run). Per connection it can add latency with jitter, limit bandwidth, close after N bytes, reset, blackhole (accept, never answer), answer a canned 503, or `drop_response`: forward the request, let the server finish, then reset the client. Second, an `http.RoundTripper` wrapper for socket-free unit tests: error, 503, latency, truncate, corrupt.

A fault plan is `Schedule{Seed, weights}`; the fault for connection `i` depends only on `(seed, i)`. One GET per fault, 300 ms deadline:

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

`close_after` gives a 200 and then a broken body; `reset` sometimes surfaced as a broken pipe, so I classify both together.

## The experiment method

The Principles of Chaos Engineering, as I understand them: define a {{< term "steady-state" "steady state" >}} as a measurable metric, hypothesise it holds under a fault, inject, observe, compare, and keep the {{< term "blast-radius" "blast radius" >}} small. Here the steady state is the SLO idea from [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/): at least 99% of 200 orders succeed within a 300 ms {{< term "deadline" "deadline" >}}.

Hypothesis: with 10% injected 503 (seed 7), retries keep the steady state.

```
  no retries                         ok=174/200 ( 87.0%) attempts=200
    steady state: VIOLATED
  3 attempts, no budget              ok=200/200 (100.0%) attempts=226
    steady state: HOLDS
  3 attempts, budget 20%, jitter     ok=198/200 ( 99.0%) attempts=224
    steady state: HOLDS
```

The budgeted client sits exactly on the line: no comfortable margin. A {{< term "retry-budget" "retry budget" >}} caps retries at a share of traffic; {{< term "jitter" "jitter" >}} spreads them.

## Four bugs it finds

**a) Retry without an idempotency key.** Fault: the response is lost after the server applied the charge (15% `drop_response`, 5% 503, 100 orders).

```
  retry, no key (before)             ok=100/100 attempts=122 charges=118 double-charged=16
  retry + Idempotency-Key (after)    ok=100/100 attempts=122 charges=100 double-charged=0
```

Every order "succeeded", yet 16 customers paid twice. The success rate never shows it; the check must include the server's own count. The fix is an {{< term "idempotency" "idempotency" >}} key.

**b) No timeout.** Fault: blackhole. The test waits 2 seconds:

```
  no timeout (before)        returned within 2s: false
  300ms deadline (after)     returned within 2s: true
```

**c) Retry storm.** Upstream down, 40 orders, 5 attempts. A {{< term "retry-storm" "retry storm" >}} multiplies the load on something already sick:

```
  5 attempts, no budget (before)     upstream-hits=200 for 40 orders (x5.00 amplification)
  5 attempts, budget 10% (after)     upstream-hits= 43 for 40 orders (x1.07 amplification)
```

The outage is not survived either way; the budget only stops us making it worse.

**d) A {{< term "circuit-breaker" "circuit breaker" >}} that never closes.** My injected bug: a successful half-open probe does not close the circuit. The dependency fails during ticks 20 to 49 (fake ticks, in-process wrapper):

```
  probe bug (before)   final state=half-open rejected= 94 ok in ticks 65..119:  0/55
  probe fixed (after)  final state=closed    rejected= 27 ok in ticks 65..119: 55/55
```

I planted the breaker bug myself; real bugs will be stranger. Tests pass with `go test -race`.

## Reproducing a failure by seed

Same seed, same transcript (fault log, per-order outcomes, charges). The md5 of the transcript:

```
  seed 42, run 1: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 42, run 2: md5 1a6089762f2084ba9da0a3e6ab92b0b8
  seed 43, run 1: md5 3a1de6b1fe8c0b3e9b36d2e12f23983d
```

Two full runs of the program gave byte-identical output. A sweep of seeds 1 to 30 (20 orders, 3% dropped responses, no key) hit a double charge in 14 seeds, and replaying seed 3 twice gave the same double-charged order, 4. A {{< term "flaky-test" "flaky failure" >}} became reproducible. That works only because the client is sequential; concurrency would reorder connections.

Going further is {{< term "deterministic-simulation" "deterministic simulation" >}}, where time and network are simulated too; as far as I know FoundationDB, TigerBeetle and Antithesis work this way. Jepsen tests [consistency models](/posts/ds-consistency-models/) with injected faults. Chaos Monkey, LitmusChaos, Gremlin and AWS FIS target real infrastructure. I used none of these.

## Where to run it

In my experience: RoundTripper unit tests in CI on every commit, the proxy in CI or staging, production only with guardrails. A {{< term "game-day" "game day" >}} needs a runbook, named roles, abort conditions and a communication channel. I would never inject faults in production without them.

## A few things to watch

- State the hypothesis first, with a number.
- Check correctness (double charges), not only availability.
- Keep the blast radius small.
- A simulated network misses real behaviour such as packet loss.

## Exercise

Add a clock-skew fault to the RoundTripper (shift the `Date` header) and test a client that trusts it.

## What's next

The next post is “Modular monolith or microservices?”.
