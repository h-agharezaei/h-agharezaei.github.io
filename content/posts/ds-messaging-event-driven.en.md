+++
date = '2027-05-29T10:00:00+03:30'
draft = false
title = 'Messaging and event-driven architecture'
description = 'Event-driven architecture in Go over NATS: commands vs events, fan-out, envelopes, idempotent consumers, ordering, schema changes and loop limits.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "messaging", "event-driven", "nats", "go"]
cover = { image = "/images/covers/ds-messaging-event-driven.png", alt = "Messaging and event-driven architecture", hiddenInSingle = true }
+++
A customer places an order. The order service calls the payment service, which calls the shipping service. If shipping is down at that moment, the whole chain fails, even though the customer's payment went through. Every service has to know about the next one, and has to be up at the same time as the others.

There is another way to wire the same flow. The order service does not call anyone. It just announces a fact: "order o-1 was placed". Whoever cares, payments, shipping or an email service, hears the announcement and does its own part when it is ready. The announcement travels through a **message broker**, a server whose job is to receive messages and hand them to the services that asked for them. In this post the broker is NATS. This style is called event-driven architecture, and it is what this post is about.

It removes real coupling, but it does not come free. The same flow now has duplicates, reordering, schema drift and loops. In my run, 50 events became 59 side effects. So this post goes through each of these problems, with a small experiment for each one. The [previous post](/posts/ds-cqrs-event-sourcing/) ended with events moving state from one model to another; JetStream, the persistent part of NATS, is covered in the [NATS series](/posts/nats-jetstream-retry-dlq/).

> Honest labelling: everything runs on one machine. The services are goroutines, and the "network" is loopback to an embedded nats-server (v2.15.1, with nats.go v1.54.0), started on a random port. It shows the patterns, not a real network. I re-ran the demo with Go 1.27 and `go test -race` passes. I show counts and no timings.

## Commands, events, queries

Before any code, there are three kinds of messages, and mixing them up causes most of the confusion:

| | Command | Event | Query |
|---|---|---|---|
| Name | imperative: `PlaceOrder` | past tense: `OrderPlaced` | `GetOrder` |
| Meaning | please do this | this happened | tell me |
| Receivers | one | zero or many | one |
| Can be refused | yes | no, it is a fact | n/a |

A command asks one specific service to do something, and that service may say no. An event reports something that already happened, so nobody can refuse it, and the publisher does not even know how many services listen: it can be zero or ten. A query asks for information and expects an answer. The rest of the post is mostly about events, but we meet all three.

## One receiver or many

The first question for a broker is who gets a message. I published 30 messages to three receivers in three different ways and counted how many each one got:

```
core pub/sub, 3 subscribers      : 30 30 30
core queue group, 3 members      : 13 10 7
JetStream work queue, 3 workers  : 10 10 10
```

- **Core pub/sub.** With {{< term "publish-subscribe" "publish-subscribe" >}}, publishers send to a named *subject* (a dotted name like `events.order.placed`), and every subscriber of that subject gets every message. That is why each subscriber has 30. This is how an event reaches payments, shipping and email at once.
- **Queue group.** Subscribers that share a group name form a {{< term "queue-group" "queue group" >}}, and each message goes to only one member. This is how you share work between several copies of the same service. The split is the server's choice and it is not even: 13, 10 and 7 in the original run. It also changes from run to run; my Go 1.27 re-runs gave 12, 7, 11 and 13, 8, 9.
- **JetStream work queue.** This is a stored stream where each message is removed once a worker acknowledges it. Three workers share one named consumer and pull messages when they are free. Here each got 10 (also in my re-runs), but I would not promise that: a worker that is free pulls the next message, so the split depends on how fast each one is ([scaling and lag](/posts/nats-jetstream-scaling-lag/)).

## Choreography or orchestration

Now a real flow. Three services, orders, payments and shipping, must cooperate for one order. There are two ways to organise this.

In {{< term "choreography" "choreography" >}} nobody is in charge. Each service reacts to the event it cares about and publishes its own. Think of dancers who each know their own part. In {{< term "orchestration" "orchestration" >}} one coordinator is in charge: it sends a command to payments, waits for the reply, then sends a command to shipping.

For choreography the services talk with an {{< term "event-envelope" "event envelope" >}}, a fixed wrapper around every event with the same metadata fields: an `id`, a `type`, a time, the `source` service, a schema version, a **correlation id** that stays the same for the whole business flow, and a **causation id** that names the event that directly caused this one. Then comes the `data`. CloudEvents is a well-known specification for such envelopes; mine is similar, not conformant (the field names are my own).

This is the real output with one correlation id (`corr-42`). Read it from top to bottom:

```
orders    publish OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  receive OrderPlaced       id=evt-1 corr=corr-42 cause=-
payments  publish PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  receive PaymentCaptured   id=evt-2 corr=corr-42 cause=evt-1
shipping  publish ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
orders    receive ShippingDispatched id=evt-3 corr=corr-42 cause=evt-2
```

Orders publishes `OrderPlaced` and has no cause (`-`). Payments reacts, and its `PaymentCaptured` event has `cause=evt-1`, so you can see which event produced it. Shipping reacts to that one, and orders finally hears that shipping is done. No service called another. The causation id lets you rebuild the chain of who reacted to what, and the correlation id lets you find every log line of this order across all services.

Orchestration does the same three steps differently. The coordinator sends `CapturePayment` and waits for the reply, then sends `DispatchShipping`. This is the real output of that run, which uses request and reply on NATS:

```
orchestrator send CapturePayment  id=evt-4
payments     command CapturePayment  id=evt-4
orchestrator got  PaymentCaptured id=evt-5
orchestrator send DispatchShipping id=evt-6
shipping     command DispatchShipping id=evt-6
orchestrator got  ShippingDispatched id=evt-7
```

The flow is readable in one place, a single function, and the failure path has an obvious home: if a step fails, the coordinator is where compensation (undoing the earlier steps, as in [the saga post](/posts/ds-saga-vs-2pc/)) would start. In my experience, orchestration suits flows with money, and choreography suits independent reactions like sending a notification.

## Delivery guarantees: why duplicates happen

Back to the number from the opening. A broker can promise one of three things about delivery, and a small example shows the difference. Say a message says "charge the customer 10" and the consumer does the charge and then replies "done" (an {{< term "acknowledgement" "acknowledgement" >}}, or ack).

- **At-most-once.** The broker sends the message once and never again. If the consumer crashes before it charges, the message is lost and nobody is charged. Nothing is ever done twice, but something may be done zero times.
- **At-least-once.** The broker keeps the message until it receives the ack, and sends it again if the ack does not arrive within a time limit (JetStream calls this the {{< term "ack-wait" "ack wait" >}}). Now suppose the consumer charges, then crashes before it sends the ack. The broker sees no ack and redelivers, and the customer is charged twice. Nothing is lost, but something may be done twice. This is {{< term "at-least-once-delivery" "at-least-once delivery" >}}, and it is the usual choice, because losing a message is usually worse.
- **Exactly-once effect.** What people actually want. As far as I know, a network cannot reliably give "exactly once" delivery, because the broker cannot tell whether the message or only its ack was lost. What you can build is at-least-once delivery plus a consumer that is {{< term "idempotency" "idempotent" >}}: it remembers the event ids it has already handled and ignores a repeat. The delivery happens twice, but the effect happens once.

Let me show that with numbers. The demo publishes 50 events to a JetStream consumer with an ack wait of 300 ms. The handler "crashes" after the side effect but before the ack for about 20% of first deliveries (chosen by a seeded random generator, so it is the same every run). Two counters run side by side: one counts every side effect, the other only counts an event id the first time it is seen, which is what a dedupe table does.

```
events=50 deliveries=59 redelivered=9
side effects without dedupe=59, with dedupe table=50
```

There were 50 events and 59 deliveries: 9 events were not acked the first time, JetStream waited 300 ms and sent them again. Without protection, the handler did its side effect 59 times, 9 of them duplicates. With a table keyed by event id, it did it 50 times, once per event. The result was the same in my Go 1.27 re-runs. In a real service that table must live in the same database transaction as the effect, or a crash can still sit between the two; see [idempotency in JetStream](/posts/nats-jetstream-idempotency/) and the [outbox pattern](/posts/go-outbox-pattern-nats/).

## Ordering

The second thing a broker does not promise is order. As far as I know, a JetStream stream stores messages in the order they were published, but ordering can still be broken for a consumer, and the ack problem above is enough to do it. Take three events for one order: v1 created, v2 paid, v3 shipped. The consumer does not ack v2 the first time. What it sees:

```
arrived v1 created  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#1 applied-by-version-check=true
arrived v3 shipped  delivery#1 applied-by-version-check=true
arrived v2 paid     delivery#2 applied-by-version-check=false
last-arrival-wins state="paid", version-checked state="shipped" (v3)
```

`delivery#N` is how many times this message was delivered. After v2's first delivery got no ack, the broker went on to v3, and 300 ms later it delivered v2 again, after v3. A handler that applies events in arrival order ends in `paid`, which is wrong because the order has already shipped. The second approach stores a version number with the order and ignores any event that is not newer. It rejects the late v2 (`applied-by-version-check=false`) and ends in `shipped`, which is right. With several workers, keep one order's events on one subject keyed by its id; I did not run that.

## Schema evolution

Events live longer than the code that publishes them, and publishers and consumers are deployed at different times. Suppose a new version 2 of an event adds two fields, `currency` and `coupon`, while a consumer written for version 1 is still running. A consumer that ignores fields it does not know, a {{< term "tolerant-reader" "tolerant reader" >}}, keeps working. A strict one breaks:

```
tolerant v1 reader on v2 event: {OrderID:o-9 Amount:120} err=<nil>
strict v1 reader on v2 event:   err=json: unknown field "currency"
```

The two readers are the same Go struct. The tolerant one uses plain `json.Unmarshal`, which ignores unknown fields. The strict one uses a decoder with `DisallowUnknownFields`, and fails on the first new field. So the rule for publishers: only add fields, and never rename a field or change its meaning. These are the same rules as in [API versioning](/posts/eng-api-design-versioning-pagination/).

## Fat events, thin events, request/reply

How much should an event carry? One choice is a **fat** event that carries all the data (this is called event-carried state transfer): the consumer needs nothing else. The other is a **thin** event, a notification that only says "order o-5 changed" with its id, and the consumer calls back to ask for the details. In the demo, the same order is 624 bytes as a fat event and 175 bytes as a thin one. But the thin event makes every consumer send a request back, and that call needs a timeout ([timeouts and retries](/posts/ds-timeouts-retries-backoff/)). Here are the three possible results of the call:

```
callback with responder: 622 bytes, err=<nil>
callback, responder gone: err=nats: no responders available for request (no-responders=true)
callback, slow responder: err=nats: timeout (timeout=true)
```

When the orders service answers, the consumer gets the full order (622 bytes). When nobody is subscribed any more, NATS reports "no responders" instead of making the caller wait for its timeout. When the responder is alive but slow (it answers after 600 ms and the caller waits 200 ms), the call ends with a timeout. So: fat events copy data to many places, and thin events couple services at runtime.

## The dangers

{{< term "eventual-consistency" "Eventual consistency" >}} shows up as the user who has just paid and still sees "pending" because the event has not been processed yet. Show "processing" honestly instead of pretending.

The worst problem is a loop: two services that each answer the other's event with a new event. In the demo, service A and B do exactly that. Without a limit it ran until my kill switch stopped it at 200 messages. With a `hops` counter in the envelope, which every service increments and refuses to go past a maximum, it stopped by itself:

```
no hop limit  handled=200 dropped-by-hop-limit=0 killed-by-switch=true
max hops=5    handled=5 dropped-by-hop-limit=1 killed-by-switch=false
```

The first line is the loop being cut off by the kill switch after 200 messages. In the second, the fifth hop was handled and the sixth message was dropped because it had reached the limit.

A {{< term "poison-message" "poison message" >}} is the sibling problem: a message that makes its consumer fail every single time, so redelivery never helps. Cap the number of deliveries and send the message to a {{< term "dlq" "dead-letter queue" >}} ([retry and DLQ](/posts/nats-jetstream-retry-dlq/)).

## Messaging traps

- **Assume duplicates and reordering.** Dedupe by event id, and compare versions before applying an event.
- **Put correlation and causation ids in every envelope from day one.** You cannot add them afterwards to events that already happened, and without them debugging a flow across services is guesswork.
- **Bound every loop.** Use a hop counter or a TTL, and bound the number of retries too.
- **Do not go event-driven by default.** In my experience, if one team owns both sides and a plain call is enough, do not use events; they buy decoupling you may not need.

The tests are unit tests for dedupe and versions, plus one embedded-server test for the hop limit, run with `go test -race` ([testing JetStream](/posts/nats-jetstream-testing/)).

## Exercise

Add a `PaymentFailed` event to the choreography so that orders cancels the order.

## What's next

[Service discovery and load balancing](/posts/ds-service-discovery-load-balancing/): direct calls, unlike messages through a bus, first need to know where the other service is.
