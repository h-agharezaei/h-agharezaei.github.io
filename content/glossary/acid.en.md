+++
title = "ACID"
summary = "The four guarantees of a transaction: Atomicity, Consistency, Isolation, Durability."
category = "Databases"
related = ["transaction", "wal"]
posts = ["db-transactions-acid", "db-isolation-levels-anomalies"]
+++

Atomicity means all-or-nothing, consistency means constraints always hold after a commit, isolation means concurrent transactions do not see each other's half-done work, and durability means a committed change survives a crash.
