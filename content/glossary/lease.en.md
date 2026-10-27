+++
title = "Lease"
summary = "A grant of a resource or a quota to a holder for a limited share or time."
category = "Distributed"
related = ["rate-limiting", "fail-open"]
posts = []
+++

In rate limiting a replica leases B tokens from the shared store and spends them locally, trading store calls for a bounded over-admission.
