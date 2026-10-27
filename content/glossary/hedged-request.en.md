+++
title = "Hedged request"
summary = "Sending a second copy of a slow request to another replica and using the first reply."
category = "Distributed"
related = ["retry-budget", "idempotency"]
posts = ["ds-timeouts-retries-backoff"]
+++

The client waits a short time (near the typical latency), then sends the same request elsewhere. It cuts slow outliers at the price of some extra load, and the operation must be safe to run twice ([idempotency](/glossary/idempotency/)).
