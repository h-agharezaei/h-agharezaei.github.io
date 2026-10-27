+++
date = '2027-05-23T10:00:00+03:30'
draft = false
title = 'Sagas or two-phase commit?'
description = 'Sagas or two-phase commit: a 2PC simulation that blocks, real PREPARE TRANSACTION on Postgres, and exhaustively checked order sagas with compensations.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "saga", "two-phase-commit", "transactions", "go", "postgres"]
cover = { image = "/images/covers/ds-saga-vs-2pc.png", alt = "Sagas or two-phase commit?", hiddenInSingle = true }
+++

[The previous post](/posts/ds-consensus-raft/) agreed on one log. Real orders touch several services (stock, payment, shipping), and no single log covers them. Two answers exist: {{< term "two-phase-commit" "two-phase commit" >}} (2PC), which keeps atomicity, and a {{< term "saga" "saga" >}}, which gives up isolation. See [ACID](/posts/db-transactions-acid/), [outbox](/posts/go-outbox-pattern-nats/), [idempotency](/posts/nats-jetstream-idempotency/) and [retries](/posts/ds-timeouts-retries-backoff/).

> Honest labelling: the 2PC and saga parts are **simulations** in Go 1.26 on one machine: simulated clock, simulated network (seeded latency 1 to 3 ticks), in-process services. Counts and ticks only, no timings. Part 2 is a real PostgreSQL 18.3 on loopback, driven with `psql`.

## 2PC in a simulation

A coordinator and three participants (inventory, payment, shipping), each locking one row. Phase 1: `PREPARE`; each participant makes its work durable, keeps the lock and votes. Phase 2: the coordinator logs its decision, then sends `COMMIT` or `ABORT`. A trimmed run where shipping votes no:

```
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping votes NO (rolls back, no lock kept)
t=  4  coord <- shipping NO
t=  4  coord LOG "ABORT"
t=  6  inventory ABORT, lock released after 3 ticks
t=  6  payment ABORT, lock released after 5 ticks
```

The happy path holds locks 5 to 7 ticks. The famous flaw: the coordinator crashes after all three voted yes, before logging a decision.

```
t=  6  coord CRASH: all voted yes, no decision written yet
t= 60  coord RESTART, reads its log [BEGIN]
t= 60  coord found BEGIN without a decision -> presumed ABORT
t= 61  inventory ABORT, lock released after 58 ticks
decision: ABORT lock ticks: map[inventory:58 payment:60 shipping:62] competing writes refused: 12 of 13
```

A participant that voted yes cannot decide alone: the answer could be commit. It can only ask (every 10 ticks here; queries are lost while the coordinator is down) and wait. That is **blocking**. If the log already holds `COMMIT`, recovery resends it. Lock time follows the outage:

```
recover at t=10    lock ticks inventory=9    payment=11   shipping=11   refused=2/4
recover at t=200   lock ticks inventory=198  payment=202  shipping=202  refused=40/42
recover at t=1000  lock ticks inventory=1000 payment=1000 shipping=1000 refused=200/202
```

"Refused" counts a competing writer that wants the inventory row every 5 ticks.

## The real primitive on Postgres

Postgres exposes the participant side as a {{< term "prepared-transaction" "prepared transaction" >}}. It needs `max_prepared_transactions` above 0 (I started my own instance with 5). One database stands in for two resource managers.

```
begin; update account set balance = balance - 30 where id = 1;
       update stock set qty = qty - 1 where sku = 'A';
prepare transaction 'order-42';
```

The session ends; the data is still the old values (balance 100, qty 5), but:

```
   gid    | owner | database 
 order-42 | app   | orders
 locktype |   rel   |       mode       | granted | no_session 
 relation | account | RowExclusiveLock | t       | t
```

Another session with `lock_timeout = '500ms'` updating that row:

```
ERROR:  canceling statement due to lock timeout
CONTEXT:  while updating tuple (0,1) in relation "account"
```

After restarting Postgres on the same data directory, `order-42` was still listed. A new session ran `COMMIT PREPARED 'order-42'` and the values became 70 and 4. The docs say it "is not intended for use in applications", only for an external transaction manager, and warn that a forgotten prepared transaction keeps its locks and blocks VACUUM. XA is the standard interface for such managers; I did not run one.

## Sagas: orchestration and choreography

A saga splits the order into local steps with {{< term "compensating-transaction" "compensations" >}}: reserve stock (undo: release), charge (undo: refund), ship (last step). I wrote both styles. Orchestration: a state machine whose persisted log records `begin`, `done`, `failed`, `comp`. Choreography: services react to events on a durable at-least-once queue (`ShippingFailed` makes payment refund, `PaymentRefunded` makes stock release).

The checker asserts: charged iff shipped, and stock reserved iff shipped. Cases: each step failing (or none), calls delivered twice or not, first compensation failing or not, a crash before every log write and call, and a second crash during recovery.

```
orchestration (persisted log) cases=3468 violations=0
choreography (events)     cases=2508 violations=0
```

A test with a refund that does nothing is flagged, so the checker can fire. It holds because calls are idempotent (stored outcome per saga id), compensation leaves a tombstone that refuses a late forward call, and it is retried until it succeeds.

## What a saga lets you see

Isolation is gone. When shipping fails, a reader polling at each step sees:

```
reads=20  naive view saw 'charged'=7, final charged=false
PENDING view (status exposed only when the saga ends): reads that showed 'charged'=0
```

Seven reads saw money later refunded. Countermeasures: a visible `PENDING` state, a **semantic lock** (a flag that makes other operations on the order wait or fail), and commutative updates. I implemented only the pending view.

## Comparison

| | 2PC | Saga |
|---|---|---|
| Atomicity | all or nothing | eventual, via compensation |
| Isolation | locks held during prepare | none, intermediate states visible |
| Availability | blocks on coordinator | keeps going, repairs later |
| Latency | two round trips with locks | no cross-service locks |
| Complexity | in the protocol | in your compensations |
| Coupling | needs 2PC-capable resources | any service with an API |

In my experience, sagas fit separate services and 2PC fits a few databases you control. Percolator and Spanner run 2PC over consensus groups to avoid a single coordinator; I only name them. TCC (try-confirm-cancel) is a saga with reservations as the "try".

## A few things to watch

- Log intent before the call and outcome after; crashes live in the gap.
- Compensation is not rollback: a refund is a new fact; an email cannot be undone.
- Put the step that cannot fail or be undone last.
- Publish saga events through an outbox, or you lose them.
- The simulation has no partitions and no real disks.

## Exercise

Move shipping first. Which compensations become costly, and does the checker still report zero violations?

## What's next

"CQRS and event sourcing": keeping an event log as the source of truth and reading from separate views.
