+++
title = "JetStream"
summary = "The persistence layer of NATS: streams that store messages, and consumers that read them."
category = "Messaging"
related = ["durable-consumer", "dlq", "idempotency"]
posts = ["nats-jetstream-go", "nats-jetstream-production", "node-nats-jetstream", "eng-adr-documentation"]
+++

Core NATS is fire-and-forget. JetStream adds durable storage, acknowledgements, replay and delivery guarantees. A *stream* captures subjects; a [durable consumer](/glossary/durable-consumer/) tracks progress through it.
