+++
date = '2027-06-08T10:00:00+03:30'
draft = false
title = 'Modular monolith or microservices?'
description = 'Modular monolith vs microservices in Go: extract one module behind HTTP and count the new failure modes, hops, bytes and lost transactions.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "microservices", "modular-monolith", "architecture", "go"]
cover = { image = "/images/covers/ds-modular-monolith-vs-microservices.png", alt = "Modular monolith or microservices?", hiddenInSingle = true }
+++

[The previous post](/posts/ds-fault-injection-testing/) injected faults into a system. This one asks whether you should create more network boundaries to inject them into. I took a tiny domain (orders, inventory, billing), built it as a {{< term "modular-monolith" "modular monolith" >}}, then moved inventory behind HTTP and counted what changed. Background: [bounded contexts](/posts/eng-ddd-basics/) and [project layout](/posts/go-project-layout-clean-architecture/).

> Honest labelling: the "service" is a goroutine on a loopback listener, not a separate machine. Network faults come from a seeded wrapper I wrote (a simulation), and the latency table is a simulation too. Counts, no timings. Judgements marked "in my experience" are opinion.

## The monolith with real boundaries

Each module has a root package with a narrow `Port` interface; orders sees only `inventory.Port` and `billing.Port`. A test parses imports and fails if a module imports another module's internals:

```
$ go run ./cmd/archcheck .
ok: no module imports another module's internals
$ go run ./cmd/archcheck arch/testdata/bad
VIOLATION: orders/bad.go imports dsmod/modules/billing/internal/gateway
```

Placing an order is one database transaction over orders, inventory and billing. If payment is declined, the order row and the stock change both roll back (tested, also with 50 concurrent orders, under `go test -race`); see [ACID](/posts/db-transactions-acid/).

## Extract inventory

The same `Port` now has two implementations: in-process and an HTTP client, chosen by one config value. `PlaceOrder` did not change. A behavioural {{< term "contract-test" "contract suite" >}} (reserve, insufficient stock, same key twice, release) passes against both. Passing the suite is the easy part; the rest of the post is what it does not cover.

## What extraction costs

**Duplicates.** 2000 reservations, 3 attempts each, 10% of requests and 10% of responses lost:

```
key=false orders=2000 client-calls=2441 server-executions=2188 units-reserved=2188 extra=188
key=true  orders=2000 client-calls=2441 server-executions=2188 units-reserved=1999 extra=-1
```

Without an {{< term "idempotency" "idempotency key" >}}, 188 units were reserved twice. With one the server deduplicates (1999: one order never arrived). See [timeouts and retries](/posts/ds-timeouts-retries-backoff/).

**The lost transaction.** 1000 orders, 10% declined payments:

```
monolith (one transaction)         confirmed=901 reserved-for-no-order=0
extracted, no net faults, naive    confirmed=901 reserved-for-no-order=99
extracted, 5%+5% faults, naive     confirmed=829 reserved-for-no-order=124
extracted, 5%+5% faults, saga+key  confirmed=900 reserved-for-no-order=0
```

Even with a perfect network, a decline leaves stock held for nothing. A release as a {{< term "compensating-transaction" "compensation" >}} plus retries fixed it here: a small {{< term "saga" "saga" >}} ([sagas and 2PC](/posts/ds-saga-vs-2pc/)). Code I had to add.

**Hops and bytes** for one 5-line order (request/response body bytes):

```
batched  http-calls= 1 request-bytes= 127 response-bytes=  11
chatty   http-calls=10 request-bytes= 225 response-bytes= 160
in-process: http-calls=0 request-bytes=0 response-bytes=0
```

The chatty version (check and reserve per line) is invisible in-process and ten calls over HTTP.

**Versioning.** A server that renames `qty` to `quantity` breaks old clients; an added response field breaks only a strict client:

```
server renamed qty->quantity, old client: inventory: status 400: json: unknown field "qty"
server added response field, tolerant client: <nil>
server added response field, strict client:   json: unknown field "warehouse"
```

Be a {{< term "tolerant-reader" "tolerant reader" >}}, and rename in two steps (accept both, then remove).

**Latency (simulation).** Each hop is log-normal, median 40 ms, p99 100 ms (my assumption), chained sequentially, 200000 chains:

```
hops=1 end-to-end p50=  39.9 ms p99= 100.0 ms p99/p50=2.50  chains with >=1 hop over its p99=1.0%
hops=3 end-to-end p50= 126.1 ms p99= 217.6 ms p99/p50=1.73  chains with >=1 hop over its p99=3.0%
hops=5 end-to-end p50= 212.5 ms p99= 326.1 ms p99/p50=1.53  chains with >=1 hop over its p99=4.9%
```

I expected the ratio to grow; for sums it shrinks, because independent slow hops average out. What grows is the absolute {{< term "percentile" "p99" >}} and the chance a request meets a slow hop. Adding per-hop p99s (500 ms) overestimates the chain (326 ms). Parallel fan-out takes a maximum instead; I did not simulate that.

**Operational surface**, counted in my demo:

| | Monolith | + inventory service |
|---|---|---|
| Deployables | 1 | 2 |
| Health endpoints to watch | 1 | 2 |
| New config values | 0 | URL, timeout, retries |
| Failure modes | process down | also timeout, lost reply, duplicate |

Add [circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/) to that list.

## What you buy

Independent deploys, scaling per service, separate technology and failure isolation. {{< term "conways-law" "Conway's law" >}} says structure follows communication, so these pay off when several teams need to ship independently, load is uneven, or reliability needs differ. In my experience a small team with unclear boundaries gets a {{< term "distributed-monolith" "distributed monolith" >}}: lockstep deploys, a shared database, chatty calls (calls-per-request above is the number to watch).

## Decision and path

As I remember it, Martin Fowler's “MonolithFirst” argues for starting with a monolith; others argue that early services force discipline. My opinion: start modular, extract at a seam that is proven by pain (scaling, team, reliability), give the service its own data and never share a database, and move gradually ([strangler](/posts/eng-legacy-code/)).

## A few things to watch

- Enforce boundaries with a test, not with goodwill.
- Extraction needs idempotency keys, timeouts and compensation before the first request.
- Keep ports coarse: one call per use case.
- The simulation shows shapes, not production numbers.

## Exercise

Make `Release` also fail 10% of the time and find how many retries keep orphans at zero.

## What's next

The next post is “Deployment strategies: blue-green and canary”.
