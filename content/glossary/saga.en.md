+++
title = "Saga"
summary = "A long business transaction split into local transactions, each with a compensating action that undoes it if a later step fails."
category = "Distributed"
related = ["two-phase-commit", "compensating-transaction", "idempotency"]
posts = ["ds-saga-vs-2pc", "ds-modular-monolith-vs-microservices"]
+++

A saga gives up isolation: other readers can see the intermediate states. It can be run by an orchestrator that keeps a persisted state machine, or by services reacting to each other's events (choreography).
