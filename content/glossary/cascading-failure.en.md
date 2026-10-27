+++
title = "Cascading failure"
summary = "A failure that spreads: one slow or failed component exhausts its callers, which then fail their own callers."
category = "Distributed"
related = ["circuit-breaker", "bulkhead", "partial-failure"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

Typical chain: a dependency gets slow, requests pile up waiting on it, threads or memory run out, and the service becomes slow for everyone. Timeouts, circuit breakers, bulkheads and load shedding are the standard brakes.
