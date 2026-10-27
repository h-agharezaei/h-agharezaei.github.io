+++
title = "LSN"
summary = "Log sequence number: a position in the WAL, shown like 0/1830840."
category = "Databases"
related = ["wal","replication"]
posts = ["db-replication-streaming"]
+++

Subtracting two LSNs with `pg_wal_lsn_diff` gives a distance in bytes, which is how replication lag is measured.
