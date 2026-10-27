+++
title = "Event envelope"
summary = "A fixed wrapper around every event with metadata (id, type, time, source, schema version, correlation id) separate from the payload."
category = "Distributed"
related = ["idempotency", "tolerant-reader"]
posts = ["ds-messaging-event-driven"]
+++

CloudEvents is a published specification for such an envelope. A consumer can route, deduplicate and trace an event by reading only the envelope.
