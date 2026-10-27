+++
title = "Eventual consistency"
summary = "If writes stop, all replicas end up with the same value; before that, reads may be stale or out of order."
category = "Distributed"
related = ["causal-consistency","replication"]
posts = ["ds-consistency-models", "ds-cqrs-event-sourcing", "ds-messaging-event-driven"]
+++

The weakest useful promise. It says nothing about how long convergence takes or what a read returns in the meantime.
