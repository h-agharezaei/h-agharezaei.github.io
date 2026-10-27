+++
title = "Idempotency"
summary = "Processing the same operation more than once has the same effect as processing it once."
category = "Messaging"
related = ["jetstream", "dlq", "outbox-pattern"]
posts = ["nats-jetstream-idempotency", "node-nats-jetstream", "eng-api-design-versioning-pagination", "ds-why-distributed-is-hard", "net-load-balancer-l4-l7", "eng-adr-documentation", "ds-circuit-breaker-bulkhead", "ds-cqrs-event-sourcing"]
+++

Message systems with at-least-once delivery can redeliver, so handlers must tolerate duplicates. Typical techniques are an idempotency key stored in the database, a unique constraint, or JetStream's `Nats-Msg-Id` deduplication on the publishing side.
