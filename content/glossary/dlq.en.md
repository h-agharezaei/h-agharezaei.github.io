+++
title = "Dead-letter queue"
summary = "A place where messages that keep failing are moved so they do not block the main flow."
category = "Messaging"
related = ["jetstream", "idempotency"]
posts = ["nats-jetstream-retry-dlq", "node-nats-jetstream"]
+++

After a bounded number of retries (usually with backoff), a poison message is republished to a DLQ stream together with its error context. Engineers can inspect and replay it later without losing data or stalling healthy messages.
