+++
title = "CREATE INDEX CONCURRENTLY"
summary = "A way to build an index without blocking writes, at the cost of more passes and a possible INVALID index on failure."
category = "Databases"
related = ["lock", "migration"]
posts = ["db-zero-downtime-migrations"]
+++

It cannot run inside a transaction block. If it fails, the half-built index stays with `indisvalid = false` and must be dropped.
