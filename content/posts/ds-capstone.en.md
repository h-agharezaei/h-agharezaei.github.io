+++
date = '2027-06-12T10:00:00+03:30'
draft = false
title = 'Distributed systems capstone'
description = 'A distributed systems capstone: an order pipeline with retries, breaker, saga, outbox events and an invariant checker, run on 200 fault campaigns.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capstone", "fault-injection", "saga", "go", "simulation"]
cover = { image = "/images/covers/ds-capstone.png", alt = "Distributed systems capstone", hiddenInSingle = true }
+++

[The previous post](/posts/ds-case-studies/) walked through two designs. Now the whole series goes into one order pipeline, which I try to break with {{< term "fault-injection" "fault injection" >}} and a checker like the one in [Raft](/posts/ds-consensus-raft/).

> Honest labelling: Go 1.26 on one Mac. The 200-seed campaign is a **simulation** (single-threaded event loop, virtual clock, simulated network and bus, all seeded, counts only). One separate **live run** uses real loopback HTTP and a real embedded nats-server. Static topology, no registry, one machine.

## The system

| Part | Mechanism |
|---|---|
| API | {{< term "idempotency-key" "idempotency key" >}} per intent |
| Order service | event log written with the state, {{< term "outbox-pattern" "outbox" >}} style |
| Orchestrator | {{< term "saga" "saga" >}} reserve, charge, ship; {{< term "compensating-transaction" "compensations" >}}; resumes from the log after a crash |
| Payment (HTTP) | 50 ms timeout, 600 ms deadline, {{< term "jitter" "jitter" >}}, {{< term "retry-budget" "retry budget" >}}, {{< term "circuit-breaker" "breaker" >}} |
| Inventory | {{< term "optimistic-concurrency" "optimistic concurrency" >}} |
| Bus, {{< term "read-model" "read model" >}} | at-least-once, idempotent projection |

Each seed sends 50 intents in 5 bursts; a quarter are submitted twice. Payment answers 503 (8%), applies but answers late (6%) or resets after applying (6%), and is blackholed for 500 ms. The orchestrator crashes twice mid-burst. The bus drops and duplicates 12% each.

## The steady state

Checked after quiescence:

- **I1** each intent gives one order in exactly one terminal state, never stuck.
- **I2** charged minus refunded equals the money of completed orders.
- **I3** stock is never negative and equals initial minus completed quantity.
- **I4** the read model equals the fold of the log.
- **I5** no order ships twice.
- **I6, I7** at most 1.6 attempts per call and 8 retries in 25 ms. These limits are mine; 8 is the worst value seen with everything on.

## One seed, then 200

```
seed 7: payment blackhole window t=825..1325 ms (virtual)
  t= 380  orchestrator CRASH, memory lost (flows, breaker, budget), 2 orders not yet terminal
  t= 480  orchestrator restarted, replaying the log: resuming 2 non-terminal orders
  t=1074  orchestrator CRASH, memory lost (flows, breaker, budget), 10 orders not yet terminal
  t=1174  orchestrator restarted, replaying the log: resuming 10 non-terminal orders
  t=1225  breaker OPEN after a failed charge (order 35)
  orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  violations: []
```

```
ALL MECHANISMS ON: 200 seeds x 50 intents (10000 orders)  seeds with a violation: 0
  I1 violations: 0
  I2 violations: 0
  I3 violations: 0
  I4 violations: 0
  I5 violations: 0
  I6 violations: 0
  I7 violations: 0
SLI counts over the campaign (no timings):
  orders completed=7497 compensated=2503 (out of stock=786) stuck=0
  payment calls=13252 attempts=15077 retries=3734 short-circuited=16265 retries denied by budget=691 breaker trips=386
  duplicates suppressed: api=2499 payment=1517 shipping=91 projection=5777
  bus: redelivered=6509 duplicated=5777 | inventory OCC conflicts=13340 | orchestrator crashes=400, orders resumed from log=2714
  attempts that hit the blackholed service=2696, worst retry wave (retries within 25 ms) in any seed=8
```

Zero violations. Keys absorbed 1517 payment replays and 2499 API replays, the projection 5777 duplicates, and 2714 orders resumed after crashes.

## Taking mechanisms away

A checker that never fires may be blind, so each mechanism goes off in turn:

```
mechanism removed       broken    bad      attempts  blackhole wave  first failing seed per invariant: I:seed(count)
(nothing: all on)       -           0/200  15077     2696      8    
idempotency keys        I1,I2,I5  200/200  15975     2565      6     I1:1(200) I2:1(200) I5:1(67)
retry budget            I7          1/200  14999     2689      11    I7:174(1)
jitter                  I7          5/200  15034     2665      11    I7:73(5)
circuit breaker         I7          2/200  20580     8056      10    I7:44(2)
saga compensation       I1,I2,I3  200/200  12552     2547      6     I1:1(200) I2:1(187) I3:1(200)
log recovery            I1,I2,I3  198/200  11292     2090      6     I1:1(198) I2:1(182) I3:1(198)
idempotent projection   I4        200/200  15077     2696      8     I4:1(200)
optimistic concurrency  I3        200/200  16420     3063      7     I3:1(200)
```

```
without idempotency keys, seed 1:
  I1 intent 0 produced 2 orders
  I2 charged 1615 - refunded 20 = 1595, completed orders = 1430
  I5 order 16 shipped 2 times
  same seed, all on: 0 violations
without jitter, seed 73:
  I7 9 retries inside 25 ms (limit 8)
  same seed, all on: 0 violations
without circuit breaker, seed 44:
  I7 9 retries inside 25 ms (limit 8)
  same seed, all on: 0 violations
without saga compensation, seed 1:
  I1 order 19 ends in state "failed"
  I2 charged 1230 - refunded 0 = 1230, completed orders = 1200
  I3 sku 0 stock 2, expected 9
  same seed, all on: 0 violations
without log recovery, seed 1:
  I1 order 19 ends in state "cancel-charge"
  I2 charged 1105 - refunded 30 = 1075, completed orders = 1055
  I3 sku 0 stock 6, expected 11
  same seed, all on: 0 violations
without idempotent projection, seed 1:
  I4 read model money 1330 used [28 30 30], fold money 1200 used [23 26 29]
  same seed, all on: 0 violations
without optimistic concurrency, seed 1:
  I3 sku 0 stock 29, expected 9
  same seed, all on: 0 violations
```

Without keys the ledger and shipments double; without compensation failed orders keep stock and money; without recovery orders stay stuck; a naive projection counts duplicates; without versions reservations overwrite each other.

The last three protect the dependency and the evidence is weaker. No breaker triples the attempts hitting the dead service (2696 to 8056), yet only 2 seeds cross my I7 limit; no budget or jitter crosses it in 1 and 5. In my experience they matter under real load, which this model lacks.

## Same code, real sockets

```
live run, seed 7: payment service = real HTTP server on loopback behind a fault-injecting RoundTripper
  http requests served by the payment service: 54 (simulated run made 78 attempts)
  simulated: orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  live:      orders=50 completed=38 compensated=12 ledger=48 log=240 stock=[3 4 7] shipped=38
  same final state: true
  embedded nats-server with JetStream started (random port, temporary store)
  idempotent projection      published=277 (log has 240) acked=277 redelivered(nak)=29 duplicates suppressed=37 -> violations []
  non-idempotent projection  published=277 (log has 240) acked=277 redelivered(nak)=29 duplicates suppressed=0 -> violations [I4]
  nats-server stopped, store deleted: true
```

The final state matches the simulation; the server saw 54 of 78 attempts, the rest being injected 503s and blackholes. A naive projection fails I4. `go test -race` passes, including this comparison.

## The series map

| Post | Gave the capstone |
|---|---|
| [Why hard](/posts/ds-why-distributed-is-hard/) | the fault model |
| [CAP](/posts/ds-cap-pacelc/) | availability for reads |
| [Consistency](/posts/ds-consistency-models/) | eventual convergence |
| [Clocks](/posts/ds-logical-clocks/) | sequence numbers, not time |
| [Retries](/posts/ds-timeouts-retries-backoff/) | deadline, jitter, budget |
| [Breakers](/posts/ds-circuit-breaker-bulkhead/) | the breaker |
| [Quorums](/posts/ds-replication-quorum/) | not built |
| [Sharding](/posts/ds-sharding-consistent-hashing/) | not built |
| [Raft](/posts/ds-consensus-raft/) | checker style |
| [Sagas](/posts/ds-saga-vs-2pc/) | the orchestrator |
| [CQRS](/posts/ds-cqrs-event-sourcing/) | log and projection |
| [Messaging](/posts/ds-messaging-event-driven/) | at-least-once bus |
| [Discovery](/posts/ds-service-discovery-load-balancing/) | skipped: static |
| [Rate limiting](/posts/ds-distributed-rate-limiting/) | budget's cousin |
| [Fault injection](/posts/ds-fault-injection-testing/) | seeded fault plan |
| [Monolith](/posts/ds-modular-monolith-vs-microservices/) | one process here |
| [Deployment](/posts/ds-deployment-strategies/) | not exercised |
| [Capacity](/posts/ds-capacity-estimation/) | not exercised |
| [Case studies](/posts/ds-case-studies/) | design habits |

## Not covered

Real multi-machine networks and partitions, disk failures, clock hardware, Paxos variants, CRDTs in depth, geo-replication, mesh security, operating Kubernetes.

## Where to go next

The Raft paper, "Designing Data-Intensive Applications" (Martin Kleppmann), the Jepsen analyses, "Distributed systems for fun and profit", the Google SRE book. Named, not quoted.

## A few things to watch

- Other I6 and I7 limits give another table.
- 0 violations in 200 seeds is evidence, not proof.
- Inventory and shipping are in process; the bus replays the finished log.
- The live run is one seed.

## Exercise

Let shipping apply a request, then fail its response. With keys on, does any invariant fire? Off?

## What's next

The series ends here; thank you for reading. The others are Go, Rust, NATS, Git, Node.js, Databases, Algorithms, Networking, Python, Security, Engineering, Linux and Distributed Systems. New posts will come as I learn things.
