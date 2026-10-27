+++
title = "Optimistic concurrency"
summary = "Do not lock; write with the version you read and fail if someone else wrote first, then reload and retry."
category = "Distributed"
related = ["event-sourcing", "idempotency"]
posts = ["ds-cqrs-event-sourcing", "ds-distributed-rate-limiting"]
+++

In an event store a primary key on (stream_id, version) does this: the second writer of version 3 gets a unique violation.
