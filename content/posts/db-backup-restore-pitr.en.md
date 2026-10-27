+++
date = '2027-02-25T10:00:00+03:30'
draft = false
title = 'Backup, restore and PITR'
description = 'PostgreSQL backup and restore by hand: logical copy, cold and online base backups, WAL archiving and point-in-time recovery to a named restore point.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "backup", "pitr", "wal-archiving"]
cover = { image = "/images/covers/db-backup-restore-pitr.png", alt = "Backup, restore and PITR", hiddenInSingle = true }
+++

In [the previous post](/posts/db-replication-streaming/) a `DELETE` on the primary showed up on the replica a moment later. A replica protects you from a dead server, not from a bad statement. This post is about the thing that does: a base backup plus an archive of the {{< term "wal" "WAL" >}} from [transactions and ACID](/posts/db-transactions-acid/), which lets you replay history up to a chosen moment. That is {{< term "pitr" "point-in-time recovery" >}} (PITR).

> Everything ran on a real PostgreSQL 18.3 started from the embedded binaries, with a small database (two tables, 100 customers, 500 orders, about 40 MB on disk). There are no timings. The only `pg_dump` and `pg_basebackup` on this machine are version 17.5, so I did **not** run either successfully. Where I use hand-made equivalents I say so. Temp paths below are replaced by `<archive>`.

## 1. A logical backup, by hand

```text
$ pg_dump shop
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.3; pg_dump version: 17.5
$ pg_basebackup -D pbb
pg_basebackup: error: incompatible server version 18.3
```

So I made a {{< term "logical-backup" "logical backup" >}} with `\copy`, which only needs a normal connection. The table definitions I kept in a `schema.sql` file I wrote myself (real `pg_dump` would produce it, with constraints, grants and sequences; mine covers only these two tables):

```text
\copy customers TO customers.csv CSV     -- COPY 100
\copy orders TO orders.csv CSV           -- COPY 500
CREATE DATABASE shop_restored;
\i schema.sql ; \copy ... FROM ... CSV
shop|100|500|187875.00
shop_restored|100|500|187875.00
```

Row counts and `sum(total)` match. A logical backup is portable between versions, but it is a snapshot of one moment, and restoring means rebuilding every index.

## 2. A cold physical backup

Stop the server, copy the data directory, change the port, start the copy:

```text
pg_ctl -D data stop ; cp -R data cold_copy ; pg_ctl -D cold_copy start
cold|100|500
```

The log of the copy says `database system was shut down at ...`, so no recovery was needed. It is simple and correct, and it needs downtime.

## 3. An online base backup

Copying a running data directory is only valid if the server knows you are doing it. The low-level API does this, and **the session that calls `pg_backup_start` must stay open until `pg_backup_stop`**. I kept one `psql` alive by reading from a FIFO and wrote to it from the shell:

```text
SELECT pg_backup_start('base1', true);    -- 0/3000028
-- in another shell: cp -R data/. base/   (I inserted an order during the copy)
SELECT * FROM pg_backup_stop(true) \gset
\o base/backup_label
\qecho :labelfile
NOTICE:  all required WAL segments have been archived
stopped at 0/30034E0
```

The `backup_label` file that `pg_backup_stop` returns must be written into the copy, not into the live data directory. It starts like this:

```text
START WAL LOCATION: 0/3000028 (file 000000010000000000000003)
CHECKPOINT LOCATION: 0/3000080
BACKUP METHOD: streamed
LABEL: base1
```

In the copy I then deleted `postmaster.pid` and the files inside `pg_wal`, because the archive provides the WAL (the docs allow omitting these). The copy went from 70 MB to 38 MB. I did not test other exclusions.

## 4. WAL archiving

The archive is just a directory that every finished WAL segment is copied into:

```text
archive_mode = on
archive_command = 'test ! -f <archive>/%f && cp %p <archive>/%f'
SELECT pg_switch_wal();
16777216 000000010000000000000002
16777216 000000010000000000000003
     322 000000010000000000000003.00000028.backup
16777216 000000010000000000000004
```

The `test ! -f` part refuses to overwrite an existing file, as the docs recommend. `pg_switch_wal()` closes the current 16 MB segment so it is archived now instead of when it fills. A failing `archive_command` keeps WAL on the primary until the disk fills, so monitor it.

## 5. Point-in-time recovery

After the base backup, on the primary:

```text
INSERT ... 100 orders        -- 601 rows
SELECT clock_timestamp();    -- 09:27:07.594437 (noted)
INSERT ... 50 orders         -- 651 rows
SELECT pg_create_restore_point('before_oops');
DELETE FROM orders;          -- DELETE 651  (forgot the WHERE)
SELECT pg_switch_wal();
```

To restore, copy the base backup, add `restore_command = 'cp <archive>/%f %p'`, a target, `recovery_target_action = 'promote'`, create an empty `recovery.signal` and start. I also set `archive_mode = off` in the copy so it does not write into the archive. With `recovery_target_name = 'before_oops'`:

```text
restored by name|651
LOG:  starting point-in-time recovery to "before_oops"
LOG:  restored log file "000000010000000000000004" from archive
LOG:  recovery stopping at restore point "before_oops"
LOG:  selected new timeline ID: 2
LOG:  archive recovery complete
```

The 651 orders are back. The `cp: ...00000002.history: No such file` lines in the log are normal: PostgreSQL probes for a newer timeline. With `recovery_target_time = '2026-10-27 09:27:07.594437+03:30'` (from a fresh copy of the same base):

```text
restored by time|601|1000
LOG:  recovery stopping before commit of transaction 764, time 2026-10-27 09:27:08.632306+03:30
```

Time targets are less exact than names: you need the right clock and time zone. A restore point costs one function call, so create one before every risky migration (see [zero-downtime migrations](/posts/db-zero-downtime-migrations/)). A target that never occurs is an error, not a silent partial restore:

```text
FATAL:  recovery ended before configured recovery target was reached
```

## A few things to watch

- A replica is not a backup: the bad `DELETE` replicates. Keep both.
- A backup you never restored is a hope. Restore into a scratch instance on a schedule and run a real query.
- Keep the archive off the primary's disk, and watch for a failing `archive_command`.
- For real systems use `pg_basebackup` or tools such as pgBackRest and Barman. I only name those two; I did not run them.
- Not tested here: backups of a busy system, backup encryption, tablespaces, and restores across timelines beyond the first.

## Exercise

Take a base backup of a database you can break. Add two restore points around a `DROP TABLE`, then recover to each one and compare. What happens if you also set a time target that lies before the base backup started?

## What's next

The next post is Connection pooling and its failure modes.
