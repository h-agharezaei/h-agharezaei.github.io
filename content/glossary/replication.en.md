+++
title = "Replication"
summary = "Keeping a second, continuously updated copy of a database on another server."
category = "Databases"
related = ["wal","lsn","failover"]
posts = ["db-replication-streaming", "ds-replication-quorum"]
+++

In PostgreSQL streaming replication the primary sends its WAL to standbys, which replay it. Standbys serve read-only queries and can be promoted. It is not a backup: bad writes replicate too.
