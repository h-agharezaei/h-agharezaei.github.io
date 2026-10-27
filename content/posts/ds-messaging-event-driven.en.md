+++
date = '2027-05-29T10:00:00+03:30'
draft = false
title = 'Messaging and event-driven architecture'
description = 'Event-driven architecture in Go over NATS: commands vs events, fan-out, envelopes, idempotent consumers, ordering, schema changes and loop limits.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "messaging", "event-driven", "nats", "go"]
cover = { image = "/images/covers/ds-messaging-event-driven.png", alt = "Messaging and event-driven architecture", hiddenInSingle = true }
+++

[The previous post](/posts/ds-cqrs-event-sourcing/) ended with events as a way to move state. This post is the architecture view of messaging. How JetStream works is already covered in the [NATS series](/posts/nats-jetstream-retry-dlq/); I use it here and do not repeat it.

> Honest labelling: everything runs on one machine, services are goroutines, and the "network" is loopback to an embedded nats-server. It shows the patterns, not a real network. Counts, no timings.

## Commands, events, queries

| | Command | Event | Query |
|---|---|---|---|
| Name | imperative: `PlaceOrder` | past tense: `OrderPlaced` | `GetOrder` |
| Meaning | please do this | this happened | tell me |
| Receivers | one | zero or many | one |
| Can be refused | yes | no, it is a fact | n/a |

## One receiver or many

I published 30 messages to three subscribers in three ways.

```
core pub/sub, 3 subscribers      : 30 30 30
core queue group, 3 members      : 13 10 7
JetStream work queue, 3 workers  : 10 10 10
```

Subject {{< term "fan-out" "fan-out" >}} gives everyone every message. A {{< term "queue-group" "queue group" >}} gives each message to one member, but the split is the server's choice (13/10/7 in this run). A JetStream work-queue stream with one shared durable gave 10 each here; I would not promise that, since workers pull as they are free ([scaling and lag](/posts/nats-jetstream-scaling-lag/)).

## Choreography or orchestration

Three goroutine services (orders, payments, shipping) talk with an {{< term "event-envelope" "event envelope" >}}: id, type, time, source, schema version, correlation id, causation id and data. CloudEvents is the standard for such envelopes; mine is similar, not conformant. In {{< term "choreography" "choreography" >}} each service reacts to an event. Tracing one correlation id:

```
orders    publish OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  receive OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  publish PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  receive PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  publish ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
orders    receive ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
```

The causation id rebuilds the chain; the correlation id finds it in the logs. In {{< term "orchestration" "orchestration" >}} one coordinator sends `CapturePayment`, waits for the reply, then sends `DispatchShipping`: the same three steps, but readable in one function, and the failure path (compensation) has an obvious home. In my experience: orchestration for flows with money, choreography for independent reactions like notifications.

## At-least-once and idempotent consumers

I published 50 events to a JetStream consumer with a 300 ms ack wait. Handlers "crash" after the side effect but before the ack for about 20% of first deliveries (seeded, so repeatable).

```
events=50 deliveries=59 redelivered=9
side effects without dedupe=59, with dedupe table=50
```

That is {{< term "at-least-once-delivery" "at-least-once delivery" >}}: 9 duplicate side effects without protection, none with a table keyed by event id. In a real service that table lives in the same transaction as the effect; see [idempotency](/posts/nats-jetstream-idempotency/) and the [outbox](/posts/go-outbox-pattern-nats/).

## Ordering

JetStream keeps order within a stream, nothing more. When one ack is lost, redelivery breaks it. Events v1 created, v2 paid and v3 shipped for one order, v2 not acked the first time:

```
arrived v1 created  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#1 applied-by-version-check=true
arrived v3 shipped  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#2 applied-by-version-check=false
last-arrival-wins state="paid", version-checked state="shipped" (v3)
```

Applying in arrival order ends in the wrong state; ignoring versions that are not newer ends right. With several workers, keep one aggregate's events on one subject keyed by its id; I did not run that.

## Schema evolution

A v2 event adds `currency` and `coupon`. A v1 consumer that is a {{< term "tolerant-reader" "tolerant reader" >}} keeps working; a strict one breaks:

```
tolerant v1 reader on v2 event: {OrderID:o-9 Amount:120} err=<nil>
strict v1 reader on v2 event:   err=json: unknown field "currency"
```

Only add fields, never rename or change meaning; the rules are those of [API versioning](/posts/eng-api-design-versioning-pagination/).

## Fat events, thin events, request/reply

The same order as event-carried state transfer is 624 bytes; as a thin notification with only the id it is 175 bytes, but then every consumer calls back with a request. That call needs a timeout ([timeouts and retries](/posts/ds-timeouts-retries-backoff/)):

```
callback, responder gone: err=nats: no responders available for request
callback, slow responder: err=nats: timeout
```

Fat events decouple availability but copy data around; thin events keep one source of truth but couple runtime.

## The dangers

{{< term "eventual-consistency" "Eventual consistency" >}} shows up as the user who paid and still sees "pending": show "processing" honestly. Worst are loops: two services answering each other. Without a limit mine ran until my kill switch at 200 messages; with a `hops` field in the envelope it stopped.

```
no hop limit  handled=200 dropped-by-hop-limit=0 killed-by-switch=true
max hops=5    handled=5 dropped-by-hop-limit=1 killed-by-switch=false
```

A {{< term "poison-message" "poison message" >}} is the sibling problem: cap deliveries and send it to a {{< term "dlq" "dead-letter queue" >}} ([retry and DLQ](/posts/nats-jetstream-retry-dlq/)).

## A few things to watch

- Assume duplicates and reordering; dedupe by id and compare versions.
- Put correlation and causation ids in every envelope from day one.
- Bound loops with hops or TTL, and bound retries.
- In my experience, if one team owns both sides and a plain call is enough, do not go event-driven; it buys decoupling you may not need.

Tests: unit tests for dedupe and versions plus one embedded-server test for the hop limit, run with `go test -race` ([testing JetStream](/posts/nats-jetstream-testing/)).

## Exercise

Add a `PaymentFailed` event to the choreography so orders cancels the order.

## What's next

The next post is “Service discovery and load balancing”.
