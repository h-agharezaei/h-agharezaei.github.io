+++
title = "Compensating transaction"
summary = "A new action that semantically undoes an earlier committed step, such as a refund for a charge."
category = "Distributed"
related = ["saga", "idempotency"]
posts = ["ds-saga-vs-2pc", "ds-modular-monolith-vs-microservices"]
+++

It does not roll back: the original step really happened and stays in history. A compensation must be idempotent and retryable, because it can be delivered twice or fail and be repeated.
