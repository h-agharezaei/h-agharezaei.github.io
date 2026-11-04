+++
date = '2027-02-25T10:00:00+03:30'
draft = false
title = 'Backup, restore and PITR'
description = 'PostgreSQL backup and restore by hand: logical copy, cold and online base backups, WAL archiving and point-in-time recovery to a named restore point.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "backup", "pitr", "wal-archiving"]
cover = { image = "/images/covers/db-backup-restore-pitr.png", alt = "Backup, restore and PITR", hiddenInSingle = true }
+++

One `DELETE FROM orders;` with the `WHERE` forgotten removes every order at once. In [Replication with two real instances](/posts/db-replication-streaming/) we saw such a `DELETE` appear on the replica a moment later: a replica protects you from a dead server, not from a bad statement. So the question for this post is: how do you get back to the moment just before the mistake?

The answer has two ingredients. The first is a **base backup**: a full copy of the database files taken at some moment. The second is an **archive of the {{< term "wal" "WAL" >}}**: a safe place where every finished piece of the write-ahead log is kept. We met the WAL in [transactions and ACID](/posts/db-transactions-acid/): a sequential record of every change, written before the change reaches the data files. A copy of the files from last night plus all the log since then is, in principle, everything needed to rebuild the database at any moment after last night, by starting from the copy and replaying the log, and stopping where you choose. That is {{< term "pitr" "point-in-time recovery" >}}, PITR. The rest of the post builds it by hand and then restores to a point before a deliberate `DELETE`.

> Everything ran on a real PostgreSQL 18.3 started from the embedded binaries, with a small database (two tables, 100 customers, 500 orders; the whole data directory is 47 MB at the start). I re-ran the demo for this version of the post. There are no timings. The only `pg_dump` and `pg_basebackup` on this machine are version 17.5, and I ran both against the 18.3 server: neither works, so I did **not** run either successfully. Where I use a hand-made equivalent I say so. Times in the logs are UTC, and the temporary paths in the commands are replaced by `<archive>`. Everything runs on one machine here; the archive directory is on the same disk as the data, which a real system must not do.

## 1. A logical backup, by hand

A {{< term "logical-backup" "logical backup" >}} is a copy of the data as rows and SQL, not of the files. `pg_dump` makes one, so first, what happens when I try it:

```text
$ pg_dump shop
pg_dump: error: aborting because of server version mismatch
pg_dump: detail: server version: 18.3; pg_dump version: 17.5
$ pg_basebackup -D pbb
pg_basebackup: error: incompatible server version 18.3
```

(The first message came from this run; the `pg_basebackup` message is the same one I showed in the replication post.) So I made a logical backup with `\copy`, which only needs a normal connection. The table definitions come from a `schema.sql` file that I wrote myself. Real `pg_dump` would generate it, with constraints, grants and sequences; mine covers only these two tables:

```text
\copy customers TO customers.csv CSV     -- COPY 100
\copy orders TO orders.csv CSV           -- COPY 500
CREATE DATABASE shop_restored;
\i schema.sql ; \copy ... FROM ... CSV
shop|100|500|126425.95
shop_restored|100|500|126425.95
```

Each row is database name, number of customers, number of orders and the sum of `total`. The original and the restored database agree on all three numbers. (The sum differs from run to run because the demo's totals are random.) A logical backup has two properties worth remembering. It is portable between versions, because it is just data. But it is a snapshot of one moment, and restoring means loading all rows and rebuilding every index.

## 2. A cold physical backup

A physical backup copies the database's files instead. The simplest way is to stop the server, copy the data directory, and start the copy (on another port here):

```text
pg_ctl -D data stop ; cp -R data cold_copy ; pg_ctl -D cold_copy start
cold|100|500
```

The log of the copy says `database system was shut down at ...`, which means it was a clean shutdown, so no recovery was needed. It is simple and correct, and it needs downtime. That is why the next step matters.

## 3. An online base backup

Why can't we just copy the files of a server that is running? Because the files change while we copy. By the time `cp` finishes, the beginning of the copy is from one moment, and the end from another, and the pages inside are in a mix of states. PostgreSQL's solution is to let the copy be inconsistent, and then repair it with the WAL: the server writes down where the log was when the copy started, and replaying the log from that point brings every page to a consistent state. For this it must know that you are copying. The low-level API does that, and **the session that calls `pg_backup_start` must stay open until `pg_backup_stop`**. I used one `psql` script, which ran the copy from inside the session with `\!` and also inserted an order from another connection during the copy, to show that a change made while copying is not lost:

```text
SELECT pg_backup_start('base1', true);    -- 0/4000028
\! cp -R data base                         -- (and, meanwhile, INSERT of order 501)
SELECT * FROM pg_backup_stop(true) \gset
\o base/backup_label
\qecho :labelfile
NOTICE:  all required WAL segments have been archived
```

`pg_backup_start` returned the WAL position where the backup begins, `0/4000028` (LSNs differ in every run). `pg_backup_stop` returned the text of a `backup_label` file, and `\qecho` wrote it into the copy. This file must be in the copy, not in the live data directory: at startup it tells the restored server where to start replaying. Its first lines in this run:

```text
START WAL LOCATION: 0/4000028 (file 000000010000000000000004)
CHECKPOINT LOCATION: 0/4000080
BACKUP METHOD: streamed
BACKUP FROM: primary
START TIME: 2026-11-04 16:36:37 UTC
LABEL: base1
START TIMELINE: 1
```

The `NOTICE` says that, because archiving is on, `pg_backup_stop` waited until all the WAL needed for this backup was safely in the archive. In the copy I then deleted `postmaster.pid` and the contents of `pg_wal`, because the archive will provide the WAL (the docs allow leaving these out). The copy went from 86 MB to 38 MB. I did not test other exclusions.

## 4. WAL archiving

The archive is just a directory that every finished WAL segment is copied into. WAL is written in fixed files called segments, 16 MB each by default. These settings turn archiving on (on this machine I passed them on the command line):

```text
archive_mode = on
archive_command = 'test ! -f <archive>/%f && cp %p <archive>/%f'
SELECT pg_switch_wal();
```

and this is what the archive looked like at the end of the demo, after the writes of the next section (size in bytes, then name):

```text
16777216 000000010000000000000001
16777216 000000010000000000000002
16777216 000000010000000000000003
16777216 000000010000000000000004
     318 000000010000000000000004.00000028.backup
16777216 000000010000000000000005
```

`%p` is the path of the segment and `%f` its file name. The `test ! -f` part refuses to overwrite a file that is already there, as the docs recommend. The small `.backup` file is the history of the base backup we took. `pg_switch_wal()` closes the current segment so that it is archived now instead of when it fills; I use it after the last write so that this write is in the archive. According to the docs, a failing `archive_command` makes PostgreSQL keep the unarchived WAL on the primary, which can fill the disk, so a real system must monitor it.

## 5. Point-in-time recovery

After the base backup, on the primary, I played the incident, with a deliberate mistake at the end:

```text
INSERT ... 100 orders        -- 601 rows
SELECT clock_timestamp();    -- 2026-11-04 16:36:48.389665+00  (noted)
INSERT ... 50 orders         -- 651 rows
SELECT pg_create_restore_point('before_oops');
DELETE FROM orders;          -- DELETE 651  (forgot the WHERE)
SELECT pg_switch_wal();
```

`pg_create_restore_point` writes a named marker into the WAL. It is a label you can later say "stop right here" to, and it costs almost nothing.

To restore I copied the base backup into a new directory, and added to its configuration a `restore_command` (how to fetch an archived segment: `cp <archive>/%f %p`), a recovery target, and `recovery_target_action = 'promote'` (when the target is reached, become a normal read-write server). Then I created an empty file `recovery.signal`, whose presence tells PostgreSQL to start in recovery mode, and started the server. With `recovery_target_name = 'before_oops'`, the restored database had its 651 orders back:

```text
restored by name|651|651
LOG:  starting backup recovery with redo LSN 0/4000028, checkpoint LSN 0/4000080, on timeline ID 1
LOG:  restored log file "000000010000000000000004" from archive
LOG:  starting point-in-time recovery to "before_oops"
LOG:  restored log file "000000010000000000000005" from archive
LOG:  consistent recovery state reached at 0/4003800
LOG:  recovery stopping at restore point "before_oops", time 2026-11-04 16:36:49.463056+00
LOG:  selected new timeline ID: 2
LOG:  archive recovery complete
```

The first line is order count and largest id (651 and 651; the word before them is a label my query prints). Order 501, inserted while the copy was running, is among them. The log reads like a story. It started from the `backup_label` position, fetched segment 4 and then 5 from the archive, reached a consistent state, replayed up to the restore point and stopped there, before the `DELETE`. Then it chose **timeline 2**: a timeline is a numbered branch of history. After a recovery that stops in the past, the server starts a new branch, so that its new writes cannot be confused with the old history that continued to a `DELETE`. (The log also contains `cp: ...00000002.history: No such file` lines. They are normal: PostgreSQL probes for a history file of a newer timeline, and the archive has none.)

A restore point is a name. You can also stop at a time. With `recovery_target_time` set to the noted `2026-11-04 16:36:48.389665+00`, in a fresh copy of the same base backup:

```text
restored by time|601|601
LOG:  starting point-in-time recovery to 2026-11-04 16:36:48.389665+00
LOG:  recovery stopping before commit of transaction 765, time 2026-11-04 16:36:49.460867+00
```

601 orders: exactly the state before the 50-row insert. The server replayed until the first commit after the target time and stopped before it. Time targets are less exact than names: you need to know the right moment, in the right time zone, and the server clock must be trustworthy. A restore point costs one function call, so create one before every risky operation, like the migrations in [zero-downtime migrations](/posts/db-zero-downtime-migrations/). Finally, a target that never occurs is an error, not a silent partial restore. I asked for a restore point `no_such_point` and the server did not come up:

```text
FATAL:  recovery ended before configured recovery target was reached
```

## What a real backup needs

- **A replica is not a backup.** The bad `DELETE` replicates, as we saw. Keep both.
- **A backup you never restored is a hope.** The whole post is built on restoring, because that is the only way to know it works. Restore into a scratch instance on a schedule and run a real query on it.
- **Keep the archive off the primary's disk**, and watch for a failing `archive_command`.
- **For real systems use `pg_basebackup`, or tools such as pgBackRest and Barman.** I only name them; I did not run any of them, and my hand-made base backup is a way to see what they do, not what you should run.
- **Not tested here:** backups of a busy system, backup encryption, tablespaces, and restores across timelines beyond the first.

## Exercise

Take a base backup of a database you can break. Add two restore points around a `DROP TABLE`, then recover to each one and compare. What happens if you also set a time target that lies before the base backup started?

## What's next

The next post is [Connection pooling and its failure modes](/posts/db-connection-pooling/). Once we know the data can come back, the next question is reaching it at all: every query needs a connection, and connections are limited.
