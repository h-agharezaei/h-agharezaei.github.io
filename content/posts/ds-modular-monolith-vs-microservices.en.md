+++
date = '2027-06-08T10:00:00+03:30'
draft = false
title = 'Modular monolith or microservices?'
description = 'Modular monolith vs microservices in Go: extract one module behind HTTP and count the new failure modes, hops, bytes and lost transactions.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "microservices", "modular-monolith", "architecture", "go"]
cover = { image = "/images/covers/ds-modular-monolith-vs-microservices.png", alt = "Modular monolith or microservices?", hiddenInSingle = true }
+++

Imagine a small team with one application that handles orders, stock and payments. The deploys are getting slower, two people keep editing the same files, and someone in the meeting says: "we should split it into microservices." Everybody nods. But what exactly would change?

The code would not change much. That is the dangerous part. In this post I take a tiny domain with three parts (orders, inventory, billing), build it first as a {{< term "modular-monolith" "modular monolith" >}}, which means one program whose parts talk to each other only through small, narrow interfaces. Then I move inventory behind HTTP, leave the calling code exactly as it was, and count what changes. The tests stay green. And yet 188 units of stock get reserved twice.

Every network boundary is a new place for the faults we injected in the [previous post](/posts/ds-fault-injection-testing/): lost requests, lost replies, slow calls. This post shows what those faults cost when you cut a service out of a monolith, and what you need to decide before you do it. If you want some background first: [bounded contexts](/posts/eng-ddd-basics/) explains what a "part" of a domain is, and [project layout](/posts/go-project-layout-clean-architecture/) shows how to organise Go code around such parts.

> How honest the demo is: the "service" is a goroutine listening on a loopback address, not a separate machine. The network faults come from a seeded wrapper I wrote, so they are simulated. The latency table at the end is a pure simulation too. I show counts, not timings. The "database" in the demo is a tiny in-memory store with all-or-nothing transactions, not a real SQL database. Statements marked "in my experience" are my opinion, not something the demo measures. I re-ran the demo and its tests (`go test -race`) with Go 1.27 and the outputs below are exactly what it printed.

## The monolith, with real boundaries

A monolith is not automatically a mess. The usual problem is that its parts reach into each other's internals, so nothing can ever be moved. In the demo each module (orders, inventory, billing) has a root package with a narrow interface called `Port`. The orders module sees only `inventory.Port` and `billing.Port`, never their internals.

A rule that only lives in people's heads does not last, so I made it a check. A small program parses the imports and fails if one module imports another module's internal packages. Here it runs once on the real code and once on a deliberately bad example:

```
$ go run ./cmd/archcheck .
ok: no module imports another module's internals
$ go run ./cmd/archcheck arch/testdata/bad
VIOLATION: orders/bad.go imports dsmod/modules/billing/internal/gateway
```

The first run passes. The second finds the planted violation: `orders` imports the billing module's internal `gateway` package.

In this version, placing an order is one database transaction over orders, inventory and billing. If the payment is declined, the order row and the stock change are both rolled back, because they are in the same transaction. I tested that, including 50 concurrent orders under `go test -race`. If transactions are new to you, see [ACID](/posts/db-transactions-acid/). Keep this property in mind, because it is exactly what we are about to lose.

## Extracting inventory

Now the experiment. The `Port` interface of inventory gets a second implementation: an HTTP client that calls the inventory module running as a server. One config value chooses between the in-process version and the HTTP version. The order-placing code, `PlaceOrder`, did not change at all.

To check that both versions behave the same, I wrote a {{< term "contract-test" "contract suite" >}}: one set of tests (reserve, insufficient stock, the same key twice, release) that runs against both implementations. It passes for both.

That is the easy part, and it is also the trap. A green suite says the two versions agree when the network behaves. It says nothing about what happens when the network does not. The rest of the post is about exactly what the suite does not cover.

## What extraction costs

### Duplicates

The first problem is retries. If a call to the inventory service times out, the client tries again, up to 3 attempts. But a timeout does not tell you whether the server did the work. Sometimes the request was lost on the way in, and sometimes the server did the work and the reply was lost on the way back. In the second case a retry does the work twice.

The demo places 2000 reservations with 3 attempts each, while 10% of the requests and 10% of the responses are lost. It runs twice: once without an {{< term "idempotency" "idempotency key" >}} and once with one. An idempotency key is a unique ID the client attaches to a request so the server can recognise a repeat and not do the work again.

```
key=false orders=2000 client-calls=2441 server-executions=2188 units-reserved=2188 extra=188
key=true  orders=2000 client-calls=2441 server-executions=2188 units-reserved=1999 extra=-1
```

Read the first line like this: the 2000 orders needed 2441 client calls because of retries. The server executed 2188 of them, so 188 more than the 2000 orders. Without a key every execution reserved stock, so 188 units were reserved twice (`extra=188`). With a key the server recognises the repeats, and only 1999 units were reserved. Why 1999 and not 2000? One order never reached the server at all, because all of its attempts were lost (`extra=-1`). For more on retries, see [timeouts and retries](/posts/ds-timeouts-retries-backoff/).

### The lost transaction

The second problem is the transaction we had in the monolith. The demo places 1000 orders where 10% of payments are declined:

```
monolith (one transaction)         confirmed=901 reserved-for-no-order=0
extracted, no net faults, naive    confirmed=901 reserved-for-no-order=99
extracted, 5%+5% faults, naive     confirmed=829 reserved-for-no-order=124
extracted, 5%+5% faults, saga+key  confirmed=900 reserved-for-no-order=0
```

`confirmed` is the number of orders that completed. `reserved-for-no-order` counts reservations that stay in inventory even though no order exists. That is stock held for nothing.

- **Monolith:** 901 orders confirmed and nothing leaked. A declined payment rolls everything back, including the stock.
- **Extracted, perfect network, naive code:** the same 901 confirmed, but 99 reservations leaked. The inventory service had already committed its change when billing said no. The order row is rolled back, but the other service's commit cannot be rolled back by a database that is not its own. Note that this happens with no network faults at all.
- **Extracted, 5% + 5% faults, naive:** worse in both columns: fewer orders confirmed (829) and more leaked stock (124).
- **Extracted, 5% + 5% faults, with a saga and an idempotency key:** 900 confirmed, nothing leaked.

What fixed it is a release step that runs as a {{< term "compensating-transaction" "compensation" >}} when something fails after the reservation, plus retries. A release is safe to repeat, so it can be sent even when the outcome of the reservation is unknown. This is a small {{< term "saga" "saga" >}}, covered in [sagas and 2PC](/posts/ds-saga-vs-2pc/). The point for this post: it is code I had to write and test, and in the monolith I got the same behaviour for free.

### Hops and bytes

The third cost is how many calls one operation makes. In-process, a function call is almost free, so nobody notices how many are made. Over HTTP each one is a network round trip. The demo places one order with 5 lines in two ways, batched (one call for the whole order) and chatty (check availability and reserve, for each line), and counts calls and body bytes:

```
batched  http-calls= 1 request-bytes= 127 response-bytes=  11
chatty   http-calls=10 request-bytes= 225 response-bytes= 160
in-process: http-calls=0 request-bytes=0 response-bytes=0
```

Both versions do the same business work. The chatty one makes 10 calls (2 per line, 5 lines) and the batched one makes 1. In-process, you cannot see the difference, as the last line shows: zero HTTP calls either way. The number of calls per request is the one to watch, and it is the reason to keep ports coarse.

### Versioning

Once two programs talk over a wire, they are no longer deployed at the same moment, so the old and the new version have to understand each other. The demo tries three changes on the server:

```
server renamed qty->quantity, old client: inventory: status 400: json: unknown field "qty"
server added response field, tolerant client: <nil>
server added response field, strict client:   json: unknown field "warehouse"
```

Renaming a field (`qty` to `quantity`) broke the old client at once. Adding a field to the response broke only the client that rejects unknown fields. A client that ignores fields it does not know, a {{< term "tolerant-reader" "tolerant reader" >}}, is fine. So be a tolerant reader, and rename a field in two steps: first accept both names, then, when nobody sends the old one any more, remove it.

### Latency (a simulation)

Chaining calls also changes latency. This table is a simulation, not a measurement. Each hop has a log-normal latency (a common shape for response times: most are fast and a few are slow), with a median of 40 ms and a {{< term "percentile" "p99" >}} of 100 ms. Those two numbers are my assumption. The hops run one after another, and the demo simulates 200000 chains:

```
hops=1 end-to-end p50=  39.9 ms p99= 100.0 ms p99/p50=2.50  chains with >=1 hop over its p99=1.0%
hops=3 end-to-end p50= 126.1 ms p99= 217.6 ms p99/p50=1.73  chains with >=1 hop over its p99=3.0%
hops=5 end-to-end p50= 212.5 ms p99= 326.1 ms p99/p50=1.53  chains with >=1 hop over its p99=4.9%
```

p50 is the typical request and p99 is the slow one that only 1 in 100 exceeds. I expected the ratio between them to grow with more hops, but for sums it shrinks (2.50, 1.73, 1.53), because independent slow hops tend to average out with fast ones. What does grow is the absolute p99 (100 ms to 326 ms) and the chance that a request meets at least one slow hop: 1.0%, 3.0% and 4.9%. Also note that adding up the p99 of each hop (5 times 100 ms is 500 ms) overestimates the real chain p99 (326 ms). I only simulated sequential chains. A parallel fan-out takes the slowest branch instead of the sum, and I did not simulate that.

### The operational surface

Finally, there is simply more to run. This is what I counted in my demo:

| | Monolith | + inventory service |
|---|---|---|
| Deployables | 1 | 2 |
| Health endpoints to watch | 1 | 2 |
| New config values | 0 | URL, timeout, retries |
| Failure modes | process down | also timeout, lost reply, duplicate |

A real service adds more to this list, for example [circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/), which protect a caller from a slow dependency.

## What you get in return

Extraction is not a mistake. It buys four things: independent deploys, scaling each part separately, freedom to use different technology, and failure isolation (the inventory service can crash without taking billing down with it).

When are these worth the costs above? {{< term "conways-law" "Conway's law" >}} says a system's structure tends to mirror the communication structure of the organisation that builds it. So services pay off when several teams really need to ship independently, when load is very uneven between parts, or when parts need different reliability. In my experience, a small team with unclear boundaries ends up with a {{< term "distributed-monolith" "distributed monolith" >}}: services that still deploy in lockstep, share one database and call each other constantly. The calls-per-request number above is the one to watch for that.

## A decision and a path

As I remember it, Martin Fowler's "MonolithFirst" argues for starting with a monolith and splitting later, while others argue that services from day one force discipline. This is my opinion, not something the demo proves:

1. Start as a modular monolith with boundaries enforced by a test.
2. Extract only at a seam that pain has proven: scaling, team ownership or reliability.
3. Give the new service its own data. Never let two services share one database.
4. Move gradually, one piece at a time, the way the [strangler approach](/posts/eng-legacy-code/) does.

## Before you extract a module

- **Enforce the boundaries with a test, not with goodwill.** An import check like `archcheck` costs almost nothing and keeps the option of extraction open.
- **Prepare before the first request.** Idempotency keys, timeouts and compensation have to exist before the service goes live, because each of the failures above happens with the very first retry.
- **Keep ports coarse.** One call per use case, not one per line.
- **Read the simulation as a shape, not as a forecast.** The numbers show how the effects behave, not what your production will measure.

## What's next

The next post is "Deployment strategies: blue-green and canary". Once you have more than one deployable piece, the question is how each new version reaches users without taking anything down.
