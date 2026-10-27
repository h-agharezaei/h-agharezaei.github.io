+++
date = '2027-06-01T10:00:00+03:30'
draft = false
title = 'Service discovery and load balancing'
description = 'Service discovery and load balancing in Go: a TTL registry, the stale-entry window, round robin vs power of two choices, health checks and herds.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "service-discovery", "load-balancing", "nats", "go"]
cover = { image = "/images/covers/ds-service-discovery-load-balancing.png", alt = "Service discovery and load balancing", hiddenInSingle = true }
+++

[The previous post](/posts/ds-messaging-event-driven/) ended with services talking through a bus. With direct calls you must first answer "where is the other service right now?". That is {{< term "service-discovery" "service discovery" >}}. The layer 4 and layer 7 basics of a {{< term "load-balancer" "load balancer" >}} are in [the earlier post](/posts/net-load-balancer-l4-l7/); here: who knows the addresses and who picks one.

> Honest labelling: one machine, loopback only. Instances in the registry demo are real HTTP servers on random ports, but the clock is injected and heartbeats come from my loop. The balancing and herd parts are seeded simulations of queues, not networks. Counts, no timings.

## Static, DNS or registry

A static list breaks on the first deploy. {{< term "dns" "DNS" >}} works everywhere, but answers are cached for their TTL and the cache is not yours: the Go resolver does not cache by itself, while the OS or a runtime may (the JVM has historically cached aggressively; check your version). SRV records carry ports. A {{< term "service-registry" "registry" >}} gives you control: instances register with a {{< term "ttl" "TTL" >}} and keep renewing it with a {{< term "heartbeat" "heartbeat" >}}.

## A tiny registry and the stale window

`/register`, `/renew`, `/deregister` and `/list`, with expiry checked against an injected clock so tests are deterministic. Three instances renew every 2 ticks; instance b crashes at tick 11 without deregistering. The client sends 3 requests per tick over the list:

```
ttl= 3 retry=false stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 3
ttl= 3 retry=true  stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 0
ttl= 6 retry=false stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 6
ttl= 6 retry=true  stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 0
ttl=10 retry=false stale-ticks=10 wasted-attempts=10 user-visible-failures=10
ttl=10 retry=true  stale-ticks=10 wasted-attempts=10 user-visible-failures= 0
```

The crashed instance stays listed for exactly TTL ticks, and a fraction of requests hit it (one per tick here). Retrying on another instance hides it from users but still wastes the attempt. A short TTL shrinks the window but needs frequent heartbeats; a TTL close to the interval expires healthy instances on one lost renewal. In my experience TTL of at least 3 times the interval is a sane start. Bound those retries ([timeouts and backoff](/posts/ds-timeouts-retries-backoff/)) or a stale entry becomes a retry storm.

## Picking an instance

Client-side balancing takes the registry snapshot and chooses. I simulated 8 servers with speeds 4,4,4,4,2,2,1,1 requests per tick and bursty arrivals (20% of ticks bring 40 requests, else 8), 2000 ticks, seeded:

```
random           max-queue=1742 avg-queue= 202.40
round-robin      max-queue=1581 avg-queue= 197.50
least-in-flight  max-queue=  14 avg-queue=   1.18
power-of-two     max-queue=  19 avg-queue=   1.81
```

Random and round robin give slow servers an equal share, which exceeds what they can serve, so queues grow without bound. {{< term "power-of-two-choices" "Power of two choices" >}} samples two instances and takes the shorter queue: nearly as good as asking everybody, with two readings instead of N. One made-up workload: the shape, not your numbers.

## Where the balancer lives

| | Client-side | Proxy / server-side | {{< term "service-mesh" "Service mesh" >}} sidecar |
|---|---|---|---|
| Who picks | the app library | a central proxy | a proxy next to each app |
| Extra hop | none | one | local hop |
| Language-agnostic | no | yes | yes |
| Cost | library per language | proxy is a bottleneck/SPOF | one more process per instance |

Envoy, Istio and Linkerd are the usual names; not run here.

## NATS: discovery without a registry

With a {{< term "queue-group" "queue group" >}} on an embedded nats-server (random port), three responders and 30 requests:

```
30 requests, 3 responders: r1=17 r2=2 r3=11
r2 killed, 30 more:        r1=12 r2=0 r3=18
all responders gone:       err = nats: no responders available for request
```

Nobody registered anything; the subscription is the registration, and the server drops it on disconnect. The split varies between runs. I waited 200 ms after each kill; without that wait one request timed out in an early run, which is the same stale window in miniature.

## Health checks and flapping

Liveness asks "restart me?", readiness asks "send me traffic?", startup protects slow boots; those are the Kubernetes terms. Active {{< term "health-check" "health checks" >}} probe on a schedule; passive ones watch real traffic ([circuit breakers](/posts/ds-circuit-breaker-bulkhead/)). A flapping instance (55% of probes succeed, 120 probes) flips constantly unless you add {{< term "hysteresis" "hysteresis" >}}:

```
need 1 ok / 1 fail: route changes=58
need 3 ok / 3 fail: route changes=11
need 5 ok / 5 fail: route changes=3
really down from probe 20, need 3 fails: ejected at probe 22
really down from probe 20, need 5 fails: ejected at probe 24
```

## The herd after a registry restart

500 instances re-register at once after the registry restarts, as a seeded simulation:

```
spread= 0 ticks: peak registrations in one tick=500
spread=10 ticks: peak registrations in one tick=64
spread=50 ticks: peak registrations in one tick=16
```

This is the {{< term "thundering-herd" "thundering herd" >}}; random {{< term "jitter" "jitter" >}} spreads it. The registry is itself a distributed system: Consul, etcd and ZooKeeper favour consistency, Eureka favours availability (per their docs); see [CAP and PACELC](/posts/ds-cap-pacelc/).

## A few things to watch

- Treat the list as a hint: always have timeouts and a retry elsewhere.
- Deregister on graceful shutdown ([graceful shutdown](/posts/go-graceful-shutdown-workers/)); TTL only covers crashes.
- Add hysteresis and jitter to anything that polls or re-registers.
- The registry logic is tested with `go test -race` and the injected clock.

## Exercise

Add a `weight` to each instance and make power of two choices compare queue divided by weight.

## What's next

The next post is “Distributed rate limiting”.
