+++
title = "Load shedding"
summary = "Rejecting some requests early so the rest can still be served in time."
category = "Distributed"
related = ["bulkhead", "backpressure", "circuit-breaker"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

A bounded queue or pool answers HTTP 503 or 429 when full instead of letting the queue grow without limit. A fast, honest refusal is usually better for the client than a slow answer that arrives after its timeout.
