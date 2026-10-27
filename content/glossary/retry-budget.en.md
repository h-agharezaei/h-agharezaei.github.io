+++
title = "Retry budget"
summary = "A cap on retries as a fraction of normal requests, often kept in a token bucket."
category = "Distributed"
related = ["retry-storm", "exponential-backoff"]
posts = ["ds-timeouts-retries-backoff"]
+++

Each request adds a fraction of a token (for example 0.1) and each retry spends one, so retries stay near 10% of traffic. When the budget is empty the client fails fast instead of piling onto a struggling server.
