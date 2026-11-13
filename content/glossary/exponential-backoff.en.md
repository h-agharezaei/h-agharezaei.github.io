+++
title = "Exponential backoff"
summary = "Waiting longer after each failed attempt, doubling the delay up to a cap."
category = "Distributed"
related = ["jitter", "retry-storm"]
posts = ["ds-timeouts-retries-backoff", "ds-case-studies", "microsoft-365-outage-exchange-online-2026"]
+++

After attempt n the client waits roughly `min(cap, base * 2^n)`. It gives an overloaded server room to recover, but clients that fail together still retry together unless [jitter](/glossary/jitter/) is added.
