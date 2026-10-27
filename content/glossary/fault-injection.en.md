+++
title = "Fault injection"
summary = "Deliberately causing latency, errors or crashes in a dependency to see how the system reacts."
category = "Distributed"
related = ["chaos-engineering", "blast-radius", "idempotency"]
posts = ["ds-fault-injection-testing"]
+++

Faults can be injected by a proxy between client and server, by a wrapper around the HTTP client in a unit test, or by killing processes. The goal is to find missing timeouts, unsafe retries and wrong assumptions before production does.
