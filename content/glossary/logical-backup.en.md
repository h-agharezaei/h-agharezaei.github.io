+++
title = "Logical backup"
summary = "A backup made of SQL or row data (pg_dump, COPY) instead of copies of the data files."
category = "Databases"
related = ["pitr", "wal"]
posts = ["db-backup-restore-pitr"]
+++

It is portable across versions and can restore a single table, but it captures one moment and rebuilds indexes on restore. A physical backup copies the data files and can be combined with WAL for point-in-time recovery.
