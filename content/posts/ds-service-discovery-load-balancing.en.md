+++
date = '2027-06-01T10:00:00+03:30'
draft = false
title = 'Service discovery and load balancing'
description = 'Service discovery and load balancing in Go: a TTL registry, the stale-entry window, round robin vs power of two choices, health checks and herds.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "service-discovery", "load-balancing", "nats", "go"]
cover = { image = "/images/covers/ds-service-discovery-load-balancing.png", alt = "Service discovery and load balancing", hiddenInSingle = true }
+++
One of your three payment-service instances crashes. It dies without telling anyone, so its address is still on the list that every client uses. Until that entry disappears, about a third of the requests go to an address where nobody answers. Even a working retry does not make this free: each request that hits the dead address has already wasted an attempt.

This is the question that direct service-to-service calls have to answer and that the message bus of the [previous post](/posts/ds-messaging-event-driven/) did not: where is the other service right now? Instances start, stop and move, so the answer keeps changing. Finding the current addresses is called {{< term "service-discovery" "service discovery" >}}. Choosing one of them for each request is load balancing. The basics of a {{< term "load-balancer" "load balancer" >}} at layers 4 and 7 are in [the networking post](/posts/net-load-balancer-l4-l7/). This post asks two other questions: who knows the addresses, and who picks one.

> Honest labelling: one machine, loopback only. The instances in the registry demo are real HTTP servers on random ports, but the clock is injected and the heartbeats come from my loop. The balancing, health-check and herd parts are seeded simulations of queues, not networks. I re-ran everything with Go 1.27 and `go test -race` passes. Counts, no timings.

## Static, DNS or registry

There are three common ways to know where a service lives.

A **static list** of addresses in a config file is the simplest. It breaks on the first deploy, when an address changes.

{{< term "dns" "DNS" >}} works everywhere, and one name can point to several addresses. But DNS answers are cached for their {{< term "ttl" "TTL" >}} (time to live), and that cache is not yours. For example, the Go resolver does not cache by itself, while the operating system or a language runtime may (the JVM has historically cached aggressively; check your version). SRV records, a DNS record type, can also carry the port and not only the address.

A {{< term "service-registry" "registry" >}} gives you control. It is a small service that stores which instances are alive. Each instance registers itself with a TTL and keeps renewing it with a small periodic message, a {{< term "heartbeat" "heartbeat" >}}. If the heartbeats stop, the entry expires and the instance disappears from the list. The registry never has to learn that an instance crashed: silence is the signal.

## A tiny registry and the stale window

I built a registry with four operations, `/register`, `/renew`, `/deregister` and `/list`. Expiry is checked against an injected clock, so the tests and the demo are deterministic.

The experiment: three instances, a, b and c, each renew every 2 ticks. Instance b crashes at tick 11 without deregistering. Its last renewal was at tick 10, the last time the registry heard from it. A client sends 3 requests per tick in round robin over the list it gets from the registry, so exactly one request per tick goes to each instance.

Follow b's entry with a TTL of 3 ticks. At ticks 11, 12 and 13 its last renewal is 1, 2 and 3 ticks old, which is not older than the TTL, so b is still listed and one request per tick goes to a dead address. At tick 14 the entry is 4 ticks old and expires. That is 3 stale ticks. I ran this for three TTLs, each with and without a retry on another instance when a call fails:

```
ttl= 3 retry=false stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 3
ttl= 3 retry=true  stale-ticks= 3 wasted-attempts= 3 user-visible-failures= 0
ttl= 6 retry=false stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 6
ttl= 6 retry=true  stale-ticks= 6 wasted-attempts= 6 user-visible-failures= 0
ttl=10 retry=false stale-ticks=10 wasted-attempts=10 user-visible-failures=10
ttl=10 retry=true  stale-ticks=10 wasted-attempts=10 user-visible-failures= 0
```

The crashed instance stays listed for exactly TTL ticks (`stale-ticks`), because it renewed just before it crashed. One request per tick hits it, so the number of `wasted-attempts` equals the stale ticks. Without a retry every one of those wasted attempts is a failure the user sees (`user-visible-failures`). With a retry on another instance, users see nothing, but the attempt was still wasted: a retry hides the problem, it does not remove its cost.

There are two trade-offs in this table. A short TTL shrinks the stale window but needs frequent heartbeats, and a TTL close to the heartbeat interval expires a healthy instance when a single renewal is lost. In my experience a TTL of at least 3 times the interval is a sane start. And bound those retries ([timeouts and backoff](/posts/ds-timeouts-retries-backoff/)), or a stale entry can turn into a retry storm.

## Picking an instance

Once the client has the list, someone must choose an instance for each request. With client-side balancing the client takes the registry snapshot and chooses. There are four simple rules:

- **Random**: pick any instance.
- **Round robin**: take them in turn, 1, 2, 3, 1, 2, 3.
- **Least in flight**: look at every instance and pick the one with the shortest queue.
- **{{< term "power-of-two-choices" "Power of two choices" >}}**: pick two instances at random and send the request to the one with the shorter queue.

Here is a made-up example to feel the difference (not from the demo). Four servers have queues of 4, 1, 6 and 0 requests, and the next request arrives. Round robin does not look at queues at all: if it is the turn of the third server, the request goes there, and its queue becomes 7. Least in flight reads all four queues and picks the fourth (length 0). Power of two picks two at random, say the first and the third, compares 4 with 6 and takes the first. It did not find the best server, but it avoided the worst of the two, with only two readings instead of four.

Now the simulation. There are 8 servers with different speeds: 4, 4, 4, 4, 2, 2, 1 and 1 requests served per tick. Arrivals are bursty: 20% of ticks bring 40 requests, the others 8. The run is 2000 ticks and seeded, and "queue" means requests waiting at a server:

```
random           max-queue=1742 avg-queue= 202.40
round-robin      max-queue=1581 avg-queue= 197.50
least-in-flight  max-queue=  14 avg-queue=   1.18
power-of-two     max-queue=  19 avg-queue=   1.81
```

Why are the first two so bad? Do the arithmetic. The average arrival is 0.8 × 8 + 0.2 × 40 = 14.4 requests per tick, and the servers can serve 4+4+4+4+2+2+1+1 = 22 per tick, so in total there is enough capacity. But random and round robin give each of the 8 servers the same share on average, 14.4 / 8 = 1.8 requests per tick, and the two slowest servers can serve only 1 per tick. Their queues grow by about 0.8 every tick, forever. Over 2000 ticks that is roughly 1600, which is the size of the maximum queue in the first two rows. The average queue in those rows, about 200, fits too: two queues that grow to about 1600 average about 800 each, and spread over 8 servers that is about 200. Least in flight and power of two avoid the problem because they look at the queue: a long queue stops getting requests. Power of two is nearly as good as asking everybody, with two readings instead of N. The workload is made up, so take the shape of the result and not the numbers.

## Where the balancer lives

The code that picks an instance can sit in three places:

| | Client-side | Proxy / server-side | {{< term "service-mesh" "Service mesh" >}} sidecar |
|---|---|---|---|
| Who picks | the app library | a central proxy | a proxy next to each app |
| Extra hop | none | one | local hop |
| Language-agnostic | no | yes | yes |
| Cost | library per language | proxy is a bottleneck/SPOF | one more process per instance |

(SPOF means single point of failure.) Envoy, Istio and Linkerd are the usual names here; I did not run them.

## NATS: discovery without a registry

The message broker from the previous post gives a surprising shortcut. With a {{< term "queue-group" "queue group" >}} on an embedded nats-server, I started three responders to the same subject and sent 30 requests, then killed responder r2 and sent 30 more, then killed the rest:

```
30 requests, 3 responders: r1=17 r2=2 r3=11
r2 killed, 30 more:        r1=12 r2=0 r3=18
all responders gone:       err = nats: no responders available for request
```

Nobody registered anything. The subscription is the registration, and the server drops it when the connection closes. After r2 was killed it got 0 requests, and when everyone was gone the client got a "no responders" error. The split between responders varies from run to run (these are the numbers from the original run; my Go 1.27 re-runs gave 8, 13, 9 and 8, 9, 13 on the first line). I waited 200 ms after each kill so that the server could notice the closed connection. Without that wait one request timed out in an early run, which is the same stale window in miniature.

## Health checks and flapping

A registry knows an instance is alive, not that it is healthy. {{< term "health-check" "Health checks" >}} close that gap. In Kubernetes terms, a liveness check asks "should I restart this instance?", a readiness check asks "should it receive traffic?", and a startup check protects a slow boot. Active checks probe on a schedule; passive ones watch the real traffic and eject an instance that keeps failing, which is what a [circuit breaker](/posts/ds-circuit-breaker-bulkhead/) does.

A problem appears with an instance that is neither up nor down. In the simulation 55% of probes succeed, 120 probes in total. If we flip the instance in or out of rotation on every probe it flips constantly. {{< term "hysteresis" "Hysteresis" >}} means requiring several probes in a row before changing state. `need 3 ok / 3 fail` means three successes in a row to come back, three failures in a row to be ejected. The first three lines count how many times the route changed. The last three use a different input: an instance that is healthy for the first 20 probes and really dead from probe 20 on (probes are counted from 0), and show at which probe it was ejected:

```
need 1 ok / 1 fail: route changes=58
need 3 ok / 3 fail: route changes=11
need 5 ok / 5 fail: route changes=3
really down from probe 20, need 1 fails: ejected at probe 20
really down from probe 20, need 3 fails: ejected at probe 22
really down from probe 20, need 5 fails: ejected at probe 24
```

Requiring 3 in a row cuts the flips from 58 to 11, and 5 in a row cuts them to 3. The price is the second half: with a need of 3 a really dead instance is ejected 2 probes later than with 1, and with 5 it is 4 probes later. Less flapping costs slower detection.

## The herd after a registry restart

One more failure that comes from synchronisation. If the registry restarts and loses its entries, 500 instances re-register at once. This is a seeded simulation where each instance waits a random number of ticks between 0 and a `spread` before it re-registers. The output is the largest number of registrations in a single tick:

```
spread= 0 ticks: peak registrations in one tick=500
spread=10 ticks: peak registrations in one tick=64
spread=50 ticks: peak registrations in one tick=16
```

With no spread all 500 arrive in the same tick. With a spread of 10 ticks the perfectly even case would be 50 per tick; random draws gave a peak of 64. With 50 ticks the even case is 10, and the peak was 16. This is a thundering herd: many clients doing the same thing at the same moment. Random {{< term "jitter" "jitter" >}} spreads them out. The registry capacity is not in this model, so I only show the peak, not whether the registry would fall over.

The registry is itself a distributed system. As I understand their documentation, Consul, etcd and ZooKeeper favour consistency, and Eureka favours availability; see [CAP and PACELC](/posts/ds-cap-pacelc/). I did not run any of them.

## Where the service list misleads

- **Treat the list as a hint, not as the truth.** It can be stale for a whole TTL. Always have timeouts and a retry on another instance.
- **Deregister on graceful shutdown** ([graceful shutdown](/posts/go-graceful-shutdown-workers/)). The TTL only covers crashes, and it should not be what removes instances during a normal deploy.
- **Add hysteresis and jitter to anything that polls or re-registers.** Without them, flapping and herds appear exactly when the system is already struggling.
- **Test the registry logic with an injected clock.** The demo's tests run with `go test -race` and never sleep.

## Exercise

Add a `weight` to each instance and make power of two choices compare queue divided by weight.

## What's next

[Distributed rate limiting](/posts/ds-distributed-rate-limiting/): a rate limit that works on one machine stops working when the service has several replicas.
