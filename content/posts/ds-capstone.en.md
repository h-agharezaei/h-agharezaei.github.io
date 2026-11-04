+++
date = '2027-06-12T10:00:00+03:30'
draft = false
title = 'Distributed systems capstone'
description = 'A distributed systems capstone: an order pipeline with retries, breaker, saga, outbox events and an invariant checker, run on 200 fault campaigns.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capstone", "fault-injection", "saga", "go", "simulation"]
cover = { image = "/images/covers/ds-capstone.png", alt = "Distributed systems capstone", hiddenInSingle = true }
+++

A customer clicks "buy". Behind that click, a system has to reserve stock, charge a card and ship the goods, while the payment service sometimes answers 503, sometimes answers too late and sometimes dies after it has already taken the money. Meanwhile one of our own servers crashes in the middle of an order, and the messages that update the order page get lost or arrive twice. What do we need to build so that, at the end, every order is either completely done or completely undone, and no money or stock is lost?

This last post puts the whole series into one small order pipeline and tests exactly that question. The test has two parts. First, a checker that reads the final state and verifies a list of rules, in the style of the safety checker we used for [Raft](/posts/ds-consensus-raft/). Second, a large number of random but replayable runs with {{< term "fault-injection" "fault injection" >}}, the technique from [failure testing](/posts/ds-fault-injection-testing/). Over 200 campaigns and 10,000 orders the checker found zero violations.

That result only means something if the checker can fail. So I also switch each mechanism off, one at a time, and show that the checker then catches the damage. The post follows the previous one, [Case studies: a rate limiter and a notification system](/posts/ds-case-studies/).

> How honest the demo is: Go 1.26 for the original run, re-run with Go 1.27 on one Mac. The 200-seed campaign is a **simulation**: a single-threaded event loop with a virtual clock, a simulated network and a simulated message bus, all seeded, counts only. One separate **live run** uses real loopback HTTP and a real embedded nats-server. The topology is static (no service registry) and everything is on one machine. The outputs below are identical to the original ones, with one exception that I mark where it appears.

## The system

An order passes through these steps: reserve the stock, charge the payment, ship, and mark it completed. If a step fails for good, the earlier steps are undone: the charge is cancelled (refunded) and the stock is released, and the order ends as "compensated". Every step is also written to an event log. A "read model" (the data an order page would show) is built from that log through a message bus.

The table shows each part, the mechanism that protects it, and in plain words what it does.

| Part | Mechanism | In plain words |
|---|---|---|
| API | {{< term "idempotency-key" "idempotency key" >}} per intent | A customer who clicks twice sends the same "intent" twice. The key lets the system recognise it and create only one order. |
| Order service | event log written with the state, {{< term "outbox-pattern" "outbox" >}} style | State and events are written together, so no event is lost or invented. |
| Orchestrator | {{< term "saga" "saga" >}} reserve, charge, ship; {{< term "compensating-transaction" "compensations" >}}; resumes from the log after a crash | The coordinator that walks an order through the steps, undoes them on failure, and after a crash reads the log to continue unfinished orders. |
| Payment (HTTP) | 50 ms timeout, 600 ms deadline, {{< term "jitter" "jitter" >}}, {{< term "retry-budget" "retry budget" >}}, {{< term "circuit-breaker" "breaker" >}} | Each attempt waits at most 50 ms; a whole call at most 600 ms. Retries wait a random time, are limited to a share of the traffic, and stop completely while the breaker is open. |
| Inventory | {{< term "optimistic-concurrency" "optimistic concurrency" >}} | Two orders for the same product cannot overwrite each other: a write fails if the version changed since it was read. |
| Bus, {{< term "read-model" "read model" >}} | at-least-once, idempotent projection | The bus may lose and repeat messages. The projection (the code that builds the read model) ignores messages it has already applied. |

Now the faults. Each seed sends 50 intents in 5 bursts, and a quarter of them are submitted twice. Payment answers 503 in 8% of attempts, applies the request but answers too late in 6%, and applies it but resets the connection before answering in 6%. Late and reset answers are the nasty ones: the money was taken but the caller does not know. On top of that, payment is blackholed (accepts the connection and never answers) for a window of 500 ms. The orchestrator crashes twice in the middle of a burst and loses its memory. And the bus drops 12% of deliveries and duplicates another 12%.

## The steady state

After the system settles (the checker runs after "quiescence", when nothing is left to do), seven properties must hold. They are called invariants: things that must be true however the faults fell.

- **I1** each intent gives exactly one order, in exactly one terminal state, and no order is stuck.
- **I2** the money adds up: charged minus refunded equals the amount of the completed orders.
- **I3** stock is never negative and equals the initial stock minus the quantity of completed orders.
- **I4** the read model equals what you get by folding (replaying) the log.
- **I5** no order ships twice.
- **I6** at most 1.6 attempts per payment call on average.
- **I7** at most 8 retries inside any 25 ms window, so there is no retry storm.

I1 to I5 are correctness. I6 and I7 are about protecting the payment service from our own retries. The limits of I6 and I7 are my choice, not a standard: 8 is simply the worst value seen with everything switched on.

## One seed, then 200

First one seed, number 7, so that we can see the faults at work. The demo prints a trace of the important events:

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

All times are virtual milliseconds. The blackhole window starts at 825 ms. Before it, at 380 ms, the orchestrator crashed with 2 orders unfinished and, 100 ms later, restarted and resumed them from the log. The second crash, at 1074 ms, caught 10 orders unfinished and landed inside the blackhole window. The breaker opened at 1225 ms after a failed charge. At the end: of 50 orders, 38 completed and 12 were compensated (undone), 38 shipped, and the checker found no violations. The ledger has 48 entries, the log 240 events, and the remaining stock of the three products is 3, 4 and 7.

Now the same thing over 200 seeds, 10,000 orders in total:

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

Zero violations in all seven invariants. The counts below the result show that the faults really happened, which matters: a campaign where nothing went wrong would prove nothing. Of 10,000 orders, 7,497 completed and 2,503 were compensated (786 of them because the product was out of stock), and none was stuck. The keys absorbed 1,517 payment replays and 2,499 API replays, the projection ignored 5,777 duplicate messages, and after 400 orchestrator crashes, 2,714 orders were resumed from the log. The breaker tripped 386 times, and the budget denied 691 retries.

## Taking mechanisms away

A passing checker could also be a checker that never fails. To find out, I switch each mechanism off in turn and run all 200 seeds again. Columns: which invariants broke, in how many of the 200 seeds ("bad"), the total payment attempts, how many attempts hit the blackholed service, the worst retry wave, and for each broken invariant the first failing seed with the number of failing seeds in parentheses:

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

To see what a violation looks like, the demo prints the checker's own words for one failing seed per mechanism, next to the same seed with everything on:

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

One value in this output varies: in the idempotency case the checker reports the first order it finds that shipped twice, which comes from iterating a map, so it printed "order 16" in the original run and "order 52" in some of my re-runs. Everything else was identical in the re-run.

What each failure means:

- **Without idempotency keys,** the same intent creates 2 orders, the ledger no longer matches (1,595 charged net, against 1,430 for completed orders, because duplicate orders and replayed charges are applied again), and an order ships twice.
- **Without compensation,** a failed order stays failed: the money stays charged (1,230 with 0 refunded) and the stock stays reserved (stock 2, but 9 expected).
- **Without log recovery,** an order interrupted by the crash ends in the middle of its undo (state "cancel-charge") and never finishes.
- **Without an idempotent projection,** the read model counts duplicate messages, so its money (1,330) is higher than the fold of the log (1,200).
- **Without optimistic concurrency,** two reservations overwrite each other and the stock is wrong (29 instead of 9).

The last three rows of the table are different from the others: the retry budget, jitter and the breaker protect the payment service rather than correctness, and the evidence for them is weaker. Without the breaker the attempts that hit the dead service triple (2,696 to 8,056), yet only 2 seeds cross my I7 limit. Without a budget or without jitter, only 1 and 5 seeds cross it. In my experience these matter under real load, which this model does not have.

## Same code, real sockets

Everything above ran on a simulated network. To check that the simulation is not hiding something, the same orchestrator code also ran once against a real HTTP payment server on loopback, with the faults injected in a `RoundTripper` in front of it (the clock stays virtual), and the bus replaced by a real embedded nats-server with JetStream, started on a random port with a temporary store:

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

The final state of the live run equals the simulated one (`same final state: true`). The payment server saw only 54 of the 78 attempts, because faults like an injected 503 or a blackhole never reach the server. On the bus, 277 messages were published for a log of 240 events (duplicates), 29 were redelivered after a nak, the idempotent projection suppressed 37 duplicates and ended with no violations, and the naive projection failed I4. `go test -race` passes, including this comparison.

## The series map

Each part of the capstone comes from an earlier post. This table says which, and what it contributed. Two topics, quorums and sharding, were not needed for this system, and three posts were not exercised here.

| Post | What it gave the capstone |
|---|---|
| [Why distributed systems are hard](/posts/ds-why-distributed-is-hard/) | the fault model: lost, late and duplicated messages, crashes |
| [CAP and PACELC, correctly](/posts/ds-cap-pacelc/) | the read model may lag but stays readable: availability for reads |
| [Consistency models](/posts/ds-consistency-models/) | eventual convergence of the read model to the log |
| [Logical clocks: Lamport and vector clocks](/posts/ds-logical-clocks/) | sequence numbers on events, not wall-clock time |
| [Timeouts, retries and backoff with jitter](/posts/ds-timeouts-retries-backoff/) | deadline, jitter, retry budget |
| [Circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/) | the breaker |
| [Replication and quorums](/posts/ds-replication-quorum/) | not built |
| [Sharding and consistent hashing](/posts/ds-sharding-consistent-hashing/) | not built |
| [Consensus and Raft](/posts/ds-consensus-raft/) | the style of the checker |
| [Sagas or two-phase commit?](/posts/ds-saga-vs-2pc/) | the orchestrator |
| [CQRS and event sourcing](/posts/ds-cqrs-event-sourcing/) | the log and the projection |
| [Messaging and event-driven architecture](/posts/ds-messaging-event-driven/) | the at-least-once bus |
| [Service discovery and load balancing](/posts/ds-service-discovery-load-balancing/) | skipped: the topology is static |
| [Distributed rate limiting](/posts/ds-distributed-rate-limiting/) | a cousin of the retry budget |
| [Failure testing with fault injection](/posts/ds-fault-injection-testing/) | the seeded fault plan |
| [Modular monolith or microservices?](/posts/ds-modular-monolith-vs-microservices/) | one process here, only payment behind HTTP in the live run |
| [Deployment strategies: blue-green and canary](/posts/ds-deployment-strategies/) | not exercised |
| [Capacity estimation](/posts/ds-capacity-estimation/) | not exercised |
| [Case studies: a rate limiter and a notification system](/posts/ds-case-studies/) | design habits |

## Not covered

Real multi-machine networks and partitions, disk failures, clock hardware, Paxos variants, CRDTs in depth, geo-replication, mesh security, and operating Kubernetes.

## Where to go next

The Raft paper, "Designing Data-Intensive Applications" (Martin Kleppmann), the Jepsen analyses, "Distributed systems for fun and profit", and the Google SRE book. I name them here and do not quote them.

## Limits of this result

- Other limits for I6 and I7 would give another table.
- 0 violations in 200 seeds is evidence, not proof.
- Inventory and shipping are in process, and the bus replays the finished log.
- The live run is one seed.

## What's next

The series ends here; thank you for reading. The others are Go, Rust, NATS, Git, Node.js, Databases, Algorithms, Networking, Python, Security, Engineering, Linux and Distributed Systems. New posts will come as I learn things.
