+++
title = "Snapshot (event sourcing)"
summary = "A saved copy of folded state at some version, so loading replays only the events after it."
category = "Distributed"
related = ["event-sourcing"]
posts = ["ds-cqrs-event-sourcing"]
+++

It is an optimization, not a source of truth: it can be deleted and recomputed from the events.
