+++
title = "Bulkhead"
summary = "Separate resource limits per dependency so one slow dependency cannot use up everything."
category = "Distributed"
related = ["circuit-breaker", "semaphore", "load-shedding"]
posts = ["ds-circuit-breaker-bulkhead"]
+++

The name comes from the compartments of a ship. In code it is usually a separate worker pool or a [semaphore](/glossary/semaphore/) per dependency, so the failure of one part floods only its own compartment.
