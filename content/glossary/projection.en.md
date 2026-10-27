+++
title = "Projection"
summary = "A read model built by consuming events and maintaining a table shaped for queries; it can be dropped and rebuilt by replay."
category = "Distributed"
related = ["cqrs", "event-sourcing", "idempotency"]
posts = ["ds-cqrs-event-sourcing"]
+++

A checkpoint records the last event position processed, so a restart continues where it stopped.
