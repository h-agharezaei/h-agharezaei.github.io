+++
title = "Happens-before"
summary = "The partial order of causality: program order, send before receive, and transitivity; events with no such path are concurrent."
category = "Distributed"
related = ["lamport-clock", "vector-clock", "causal-consistency"]
posts = ["ds-logical-clocks"]
+++

If a happens before b, a could have influenced b. If neither precedes the other, the events are concurrent and no clock can order them truthfully.
