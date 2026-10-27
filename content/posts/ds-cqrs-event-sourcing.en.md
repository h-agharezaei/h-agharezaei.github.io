+++
date = '2027-05-26T10:00:00+03:30'
draft = false
title = 'CQRS and event sourcing'
description = 'CQRS and event sourcing in Go on a real Postgres: optimistic concurrency, snapshots, upcasting, stale projections, replay, and when not to use it.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cqrs", "event-sourcing", "postgres", "go"]
cover = { image = "/images/covers/ds-cqrs-event-sourcing.png", alt = "CQRS and event sourcing", hiddenInSingle = true }
+++

[The previous post](/posts/ds-saga-vs-2pc/) coordinated several services with a saga. This one changes what a service stores: not the current state, but the facts that led to it. That is {{< term "event-sourcing" "event sourcing" >}}, and {{< term "cqrs" "CQRS" >}} is its usual companion. See also [transactions and ACID](/posts/db-transactions-acid/), [consistency models](/posts/ds-consistency-models/), [the outbox pattern](/posts/go-outbox-pattern-nats/) and [idempotency in JetStream](/posts/nats-jetstream-idempotency/).

> Honest labelling: a Go 1.26 program on one machine against a real PostgreSQL 18.3 on loopback. Randomness is seeded, I show counts, not timings; `go test -race` passes. The "poller schedule" and the "crash" in the last section are simulated.

## State as a fold of events

An `Account` is never stored. Its state is a fold over `Opened`, `Deposited`, `Withdrawn`, `Closed`. A command checks the rules against the current state and returns events; it never mutates anything. The table has `PRIMARY KEY (stream_id, version)` plus a `bigserial` position for ordering across streams.

Two sessions load the same stream at version 2 (balance 10000 cents) and both withdraw 7000, in a fixed order:

```
A append: <nil>
B append: version conflict: ERROR: duplicate key value violates unique constraint "events_pkey" (SQLSTATE 23505)
B reloads and decides again: retries=0 err=insufficient funds
```

That is {{< term "optimistic-concurrency" "optimistic concurrency" >}}: no lock, the primary key refuses the second version 3, B reloads and now the rule rejects it. An `UPDATE` on an event is possible in SQL (`UPDATE 1`, I rolled it back); the app simply never issues one. I did not try to forbid it with a trigger or a revoked privilege.

## Replay, snapshots, upcasting, time travel

A stream of 10,123 events, with a {{< term "event-snapshot" "snapshot" >}} written every 500:

```
no snapshot : version=10123 balance=989607 replayed=10123 events
snapshot/500: version=10123 balance=989607 replayed=123 events
state at 2027-03-01: version=1416 balance=138314 (replayed 1416 events)
```

Same state, 123 events instead of 10,123. The snapshot is a cache, not truth. The last line is a temporal query: replay up to a version (found from `created_at`, which in this demo is one hour per version) and you have the past, with no audit table. Events also give an audit trail for free.

Event shapes change. Version 1 stored `{"amount": 5}` (dollars); version 2 stores `amount_cents` and `currency`. Never edit old events: {{< term "upcasting" "upcast" >}} while reading. Legacy rows inserted by raw SQL:

```
stored Deposited {"amount": 5}  -> upcast {"amount_cents":500,"currency":"USD"}
stored Deposited {"currency": "USD", "amount_cents": 250} -> unchanged
stored Withdrawn {"amount": 2}  -> upcast {"amount_cents":200,"currency":"USD"}
legacy balance=550 cents
```

A unit test checks this and that the input is untouched.

## The query side is eventually consistent

Writes go to `events`. Reads go to `account_balances` and `daily_totals`, built by a {{< term "projection" "projection" >}}: a poller reads events after a checkpoint and updates the read model in the same transaction as the checkpoint. 300 deposits on 5 accounts, each followed by an immediate read of the read model; the poller runs on a seeded coin flip, 5 events at most per run:

```
300 writes ... 222 stale reads, max lag 10 events
after the projector catches up, read model == truth: true
```

That is {{< term "eventual-consistency" "eventual consistency" >}} you chose on purpose: 222 of 300 read-your-writes failed. In my experience the UI must be designed for it.

Projections can be rebuilt. I reset the checkpoint and replayed all 10,435 events again:

```
balances unchanged=true; daily_totals deposited 2048518 -> 4097036 (naive counter doubled)
rebuild from scratch: 10435 events replayed -> 8 balance rows, 422 daily rows, deposited 2048518 (== first run: true)
```

The balance handler is {{< term "idempotency" "idempotent" >}}: `ON CONFLICT ... DO UPDATE ... WHERE last_version < EXCLUDED.last_version` skips versions already applied. The daily counter is not, so it doubled; the fix is to truncate and replay, which restored the first-run value. Several projections from one log are the same loop with different handlers.

## The log as an outbox

The events table can double as an {{< term "outbox-pattern" "outbox" >}}: a publisher is just another reader with its own checkpoint. If it dies between publishing and saving the checkpoint, the batch repeats, which is {{< term "at-least-once-delivery" "at-least-once delivery" >}}. I simulated 69 such crashes by rewinding the checkpoint:

```
events=10435 deliveries=13885 distinct=10435 simulated-crashes=69
```

3,450 duplicates, and a consumer that dedupes on `(stream_id, version)` ends with exactly 10,435 effects.

## When not to use it

In my opinion most CRUD apps should not: you pay in complexity, eventual consistency and upcasters forever. A plain table plus an audit table gives history with far less machinery; events earn their place when the history is the domain (ledgers, orders with complex lifecycles). Immutable logs also collide with deletion requests. One known answer is {{< term "crypto-shredding" "crypto-shredding" >}}: encrypt personal fields per person and destroy the key. I did not implement it. Also, a `bigserial` position can become visible out of order under concurrent transactions, so a poller can skip an event; I did not reproduce this.

## A few things to watch

- Commands validate against state and emit events; handlers must not write state directly.
- Snapshots and projections are disposable; the events are the truth.
- Never edit stored events; upcast on read.
- Make every consumer idempotent; delivery is at-least-once.

## Exercise

Add a `daily_seen` table keyed by `(stream_id, version)` and make `daily_totals` idempotent. Rerun the double replay: should it stay at 2048518?

## What's next

The next post is “Messaging and event-driven architecture”.
