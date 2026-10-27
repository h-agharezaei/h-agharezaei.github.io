+++
title = "Read model"
summary = "A copy of the data shaped for queries, built by applying the events of the write side; it may lag behind but must converge."
category = "Distributed"
related = ["projection","event-sourcing","eventual-consistency"]
posts = ["ds-capstone"]
+++

In CQRS and event sourcing the read model is a [projection](/glossary/projection/) of the event log. If it is deleted it can be rebuilt by folding the log again, so a correct read model always equals the fold of the log once the events have all arrived.
