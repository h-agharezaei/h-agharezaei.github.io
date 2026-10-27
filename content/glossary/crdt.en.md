+++
title = "CRDT"
summary = "A conflict-free replicated data type: replicas update independently and a merge function that is commutative, associative and idempotent makes them converge."
category = "Distributed"
related = ["last-write-wins"]
posts = ["ds-cap-pacelc"]
+++

Examples: a grow-only set merged by union, a G-counter (one slot per node, merge by per-slot maximum, value is the sum).
