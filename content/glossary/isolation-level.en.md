+++
title = "Isolation level"
summary = "The setting that decides how much one transaction sees of others running at the same time."
category = "Databases"
related = ["transaction", "acid", "snapshot-isolation"]
posts = ["db-isolation-levels-anomalies"]
+++

The SQL standard names READ UNCOMMITTED, READ COMMITTED, REPEATABLE READ and SERIALIZABLE. Stronger levels forbid more anomalies but can abort more transactions. PostgreSQL's default is READ COMMITTED.
