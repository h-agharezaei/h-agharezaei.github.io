+++
title = "Snapshot isolation"
summary = "Each transaction reads from a consistent snapshot of the data taken when it started."
category = "Databases"
related = ["isolation-level", "write-skew"]
posts = ["db-isolation-levels-anomalies"]
+++

In PostgreSQL, REPEATABLE READ works this way. Reads never block and never see later commits, but write skew is still possible.
