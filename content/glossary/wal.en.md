+++
title = "WAL"
summary = "Write-ahead log: PostgreSQL records every change in a sequential log before it touches the data files."
category = "Databases"
related = ["database-index"]
posts = ["db-indexes-btree-explain", "db-transactions-acid", "db-replication-streaming", "db-backup-restore-pitr", "db-slow-query-case-study"]
+++

The log makes crash recovery and replication possible. Every change to a table or an index produces WAL records, so the number of WAL bytes is a deterministic way to measure how much work a write did.
