+++
title = "Event sourcing"
summary = "State is not stored; the append-only list of events that led to it is, and current state is a fold of them."
category = "Distributed"
related = ["cqrs", "event-snapshot", "upcasting"]
posts = ["ds-cqrs-event-sourcing"]
+++

An account is not a row with a balance but the events Opened, Deposited, Withdrawn. Commands check rules against the folded state and emit new events; nothing is edited in place.
