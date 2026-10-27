+++
title = "At-least-once delivery"
summary = "The broker delivers every message one or more times, never zero, so duplicates are possible."
category = "Distributed"
related = ["idempotency", "jetstream", "dlq"]
posts = ["ds-messaging-event-driven", "ds-cqrs-event-sourcing"]
+++

It is what you get when an unacknowledged message is redelivered. Consumers must therefore be idempotent.
