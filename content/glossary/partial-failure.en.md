+++
title = "Partial failure"
summary = "One part of a system fails while the rest keeps running, so the caller cannot tell what happened."
category = "Distributed"
related = ["failure-detector", "gray-failure", "idempotency"]
posts = ["ds-why-distributed-is-hard"]
+++

In a distributed system a call can fail in the request, in the server or in the reply. A timeout looks the same in all three cases, so the caller does not know whether the operation was applied.
