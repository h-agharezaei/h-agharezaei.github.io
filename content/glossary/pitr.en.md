+++
title = "PITR"
summary = "Point-in-time recovery: restore a base backup and replay archived WAL up to a chosen moment."
category = "Databases"
related = ["wal", "logical-backup"]
posts = ["db-backup-restore-pitr"]
+++

You need a base backup and every WAL segment since it. The target can be a timestamp, a named restore point created with `pg_create_restore_point`, an LSN or a transaction id. It is the tool for undoing a bad `DELETE`, which a replica cannot do.
