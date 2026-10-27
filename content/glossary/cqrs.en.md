+++
title = "CQRS"
summary = "Command Query Responsibility Segregation: the model that handles writes is separate from the model that serves reads."
category = "Distributed"
related = ["projection", "event-sourcing", "eventual-consistency"]
posts = ["ds-cqrs-event-sourcing"]
+++

The read side is usually a projection of the write side, so it can lag behind and is eventually consistent.
