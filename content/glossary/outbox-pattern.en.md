+++
title = "Outbox pattern"
summary = "Writing an event to a database table in the same transaction as the data change, then publishing it afterwards."
category = "Messaging"
related = ["idempotency", "jetstream"]
posts = ["go-outbox-pattern-nats", "eng-adr-documentation", "ds-cqrs-event-sourcing", "ds-capstone"]
+++

It removes the dual-write problem: you can never commit the row but lose the event, or the reverse. A relay process reads the outbox table and publishes to the broker, so delivery is at-least-once and consumers must be [idempotent](/glossary/idempotency/).
