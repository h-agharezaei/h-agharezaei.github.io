+++
title = "Circuit breaker"
summary = "A wrapper that stops calling a failing dependency for a while and fails fast instead."
category = "Distributed"
related = ["bulkhead", "load-shedding", "cascading-failure"]
posts = ["ds-circuit-breaker-bulkhead", "eng-postmortems-blameless"]
+++

It is a small state machine: closed (calls pass), open (calls are rejected at once) and half-open (a few probe calls decide whether to close again). It protects the caller's resources and gives the dependency room to recover.
