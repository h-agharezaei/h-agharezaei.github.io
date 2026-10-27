+++
title = "Retry storm"
summary = "Overload made worse by clients that retry failed requests all at once."
category = "Distributed"
related = ["exponential-backoff", "jitter", "retry-budget"]
posts = ["ds-timeouts-retries-backoff", "ds-fault-injection-testing"]
+++

A short outage makes many requests fail; their retries arrive together with new traffic and can keep the server overloaded after the original fault is gone. Backoff with [jitter](/glossary/jitter/) and a [retry budget](/glossary/retry-budget/) limit it.
