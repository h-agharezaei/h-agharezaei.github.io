+++
title = "Deterministic simulation"
summary = "Running a system in a simulated world driven by a seed so any failure can be replayed exactly."
category = "Distributed"
related = ["fault-injection", "flaky-test"]
posts = ["ds-fault-injection-testing"]
+++

Time, network and faults all come from one seeded random source, so the same seed gives the same run. A flaky failure becomes a seed you can re-run.
