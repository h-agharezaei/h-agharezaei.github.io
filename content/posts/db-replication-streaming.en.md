+++
date = '2027-02-13T10:00:00+03:30'
draft = false
title = 'Replication with two real instances'
description = 'PostgreSQL streaming replication with two real instances: setup, lag in bytes, synchronous commit blocking, promotion, and why a replica is no backup.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "replication", "wal", "high-availability"]
cover = { image = "/images/covers/db-replication-streaming.png", alt = "Replication with two real instances", hiddenInSingle = true }
+++

Picture a database server that dies at three in the morning. Everything is on that one machine, so until somebody restores it, the whole service is down. The obvious fix is to keep a second machine with an up-to-date copy of the data, ready to take over, and to let it answer read queries in the meantime. That is {{< term "replication" "replication" >}}.

But there is a misunderstanding that costs people their data, and I want to show it early: a replica is a second copy of the whole server, kept up to date all the time, and that is exactly why it is not a backup. If you delete ten rows on the primary, the replica deletes them too, within moments. We will see that happen in the last section.

[Table partitioning](/posts/db-partitioning/) split one big table inside one server; this post goes the other direction and makes a copy of the whole server. It builds on the {{< term "wal" "WAL" >}} from [transactions and ACID](/posts/db-transactions-acid/) and on the dead rows from [MVCC and VACUUM](/posts/db-mvcc-vacuum/).

## The idea: ship the log

Before the demo, one idea. When PostgreSQL changes anything (inserts a row, updates one, builds an index), it first appends a short description of the change to a sequential file called the write-ahead log, or WAL, and only later writes the change into the table files. The log exists so that after a crash the server can read it from the last safe point and redo the changes it had not finished writing. In other words, the log is a recipe: replaying it on a copy of the data brings that copy to the state the log describes.

Streaming replication uses the same recipe across machines. The first server, the **primary**, accepts writes. A second server, the **standby** (or replica), starts from a copy of the primary's data, connects to it, and receives the WAL as the primary produces it. It replays each record, so it follows the primary a short moment behind. A position in this log is called an {{< term "lsn" "LSN" >}} (log sequence number); it looks like `0/E40F7A0` and always grows. Comparing LSNs is how we measure how far behind a standby is.

> Everything ran on two real PostgreSQL 18.3 instances on one machine (random loopback-only ports, no Docker). I re-ran the whole demo for this version of the post. There are no timings, only bytes and states. The binaries I use here have no `pg_basebackup`, and the only one on this machine is version 17.5, which answers `pg_basebackup: error: incompatible server version 18.3` (I ran it to check). So I made the copy by hand: I stopped the primary, copied its data directory and wrote the two things `pg_basebackup -R` would write. On a live system you would use `pg_basebackup -D replica -R -X stream` to copy a running primary; I did not run it. Two instances on one machine also means that "the replica machine" and "the network between them" are not real: everything below shows the mechanism, not the behaviour of two data centres.

## Configure the primary

I checked the defaults before touching anything: `wal_level` is `replica`, `max_wal_senders` (how many standbys may connect) is 10, and `hot_standby` (a standby may answer read queries) is `on`. The only setting I changed was `listen_addresses = '127.0.0.1'`. A standby connects as a special role that has the `REPLICATION` attribute, and `pg_hba.conf` must allow it. `initdb --auth-host=scram-sha-256` had already generated the line for local connections:

```text
host    replication     all             127.0.0.1/32            scram-sha-256

CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '...';
```

## Make the replica

A standby is three things: a copy of the primary's data directory, an empty file named `standby.signal` (its mere presence tells PostgreSQL "stay in recovery and keep replaying, do not become a primary"), and a `primary_conninfo` setting that says where the primary is. This is what `-R` would write into `postgresql.auto.conf`, and what I wrote by hand (the port is random in each run):

```text
primary_conninfo = 'host=127.0.0.1 port=52951 user=replicator password=... application_name=replica1'
```

After starting both, I asked the primary who is connected, and asked the replica what it is. Both LSN columns are equal, which means everything the primary sent has already been replayed:

```text
primary> SELECT application_name, state, sent_lsn, replay_lsn, sync_state FROM pg_stat_replication;
 replica1 | streaming | 0/E40F7A0 | 0/E40F7A0  | async

replica> SELECT pg_is_in_recovery();   -- t        (primary: f)
replica> SELECT status, sender_port FROM pg_stat_wal_receiver;
 streaming | 52951
```

`pg_stat_replication` is the primary's view of its standbys: `streaming` is the state we want, `sent_lsn` is how far the primary has sent, `replay_lsn` how far the standby has applied, and `async` means asynchronous (more about that below). The LSN values change in every run, but they should be equal, as they are here. `pg_is_in_recovery()` is `t` on the standby; the receiver on the standby confirms it is streaming from the primary's port.

## Writes flow one way

I inserted a customer on the primary and polled the replica until it appeared; here it was there on the first poll. The replica does not accept writes of its own:

```text
replica> INSERT INTO customers(name,email,country) VALUES ('x','x@example.com','NL');
ERROR:  cannot execute INSERT in a read-only transaction
```

## Lag in bytes

Replication is asynchronous by default: the primary commits without waiting for the standby, so a reader on the replica can see old data. I inserted 600,000 rows into a new table and asked the primary right after the insert how far behind the standby was, then counted the rows on the replica:

```text
SELECT pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes FROM pg_stat_replication;
 20803360
replica> SELECT count(*) FROM big;   -- 0   (the rows were not replayed yet)
```

`pg_wal_lsn_diff` subtracts two LSNs and gives bytes of WAL: about 20 MB were still waiting to be replayed, so the replica still saw an empty table. One poll later the count was 600,000 and the lag 0. The 20 MB figure is from this run and changes every time (earlier runs of mine gave anything from about 6 MB to 21 MB, and sometimes the replica had already caught up by the time I counted). For a service this means a read-your-writes bug: if you write to the primary and read from a replica right away, you may not see your own write.

## Synchronous replication

We can make the primary wait. With `synchronous_standby_names = 'replica1'` (a reload is enough) `sync_state` became `sync`, and a {{< term "synchronous-commit" "synchronous commit" >}} then returns only after the standby has the WAL. That removes the lag problem for committed data, and it adds a new one. To see it, I stopped the replica and ran an `INSERT` in a background session. It hung, and `pg_stat_activity` showed why:

```text
IPC/SyncRep | active | insert into customers(name,email,country
```

The wait event `SyncRep` means "waiting for the synchronous standby". I cancelled the query with `pg_cancel_backend`:

```text
WARNING:  canceling wait for synchronous replication due to user request
DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.
```

Read the warning carefully: the row was in fact committed on the primary (a count there returned 1); only the wait was cancelled. That is the price of the setting. With one synchronous standby, a dead standby stops every write on the primary. After I restarted the replica, it caught up by itself and had the row.

## Promote, and the danger of two primaries

Now the planned failure. `pg_promote` turns a standby into a primary: it leaves recovery and starts accepting writes.

```text
replica> SELECT pg_promote(wait => true);   -- t
replica> SELECT pg_is_in_recovery();        -- f
replica> INSERT INTO customers(...) VALUES ('on_new_primary', ...);   -- INSERT 0 1
```

(Before promoting I removed `synchronous_standby_names` again, so the old primary would not wait for a standby that was no longer following it.) Now the dangerous part. I had left the old primary running, and it happily accepted its own write:

```text
old primary: 20003|on_old_primary
new primary: 20034|on_new_primary
```

Both rows were inserted into `customers` at about the same time, on two servers, and each server has only its own row. (The two ids differ too: each server now hands out ids by itself.) This is {{< term "split-brain" "split-brain" >}}: two servers, both writable, with different histories. Neither knows about the other, and merging the two histories later is manual and often loses data. Core PostgreSQL does no automatic {{< term "failover" "failover" >}}; it gives you the `pg_promote` command. Tools such as Patroni or repmgr exist for the rest (I did not run them). Whatever you use must make sure the old primary is fenced off, that is, cannot accept writes, before it comes back.

## A replica is not a backup

Back to the misunderstanding from the start. I rebuilt a primary and replica pair, created a table `keep_me` with 10 rows (the replica had them too), and then deleted them on the primary:

```text
before: primary 10 replica 10
DELETE 10
replica poll 1: 0
replica poll 2: 0
replica poll 3: 0
```

The replica showed 0 rows on the first poll. The `DELETE` is just one more WAL record, and the replica faithfully replays whatever the log says. So does a bad `UPDATE`, and so does `DROP TABLE`: dropping the table on the primary made `select * from keep_me` on the replica fail with `relation "keep_me" does not exist`. The old row versions that [VACUUM](/posts/db-mvcc-vacuum/) still has not cleaned are not an undo log that you can use for recovery. If you need to get back to the moment before the mistake, you need real backups, which is the next post.

(An earlier version of this post said I deleted 10 rows from `products`. In the shop schema that fails because `order_items` references them, so I used this scratch table instead.)

## What replication does not solve

- **Async replicas lag.** Do not read your own write from a replica without checking the LSN, or send such reads to the primary.
- **One synchronous standby turns its failure into a write outage.** Use several candidates, or accept asynchronous replication and its small window of possible data loss.
- **Promotion is one command; deciding who is the primary, and stopping the old one, is the hard part.**
- **Replicas hold the same bad data as the primary.** They answer "the server died", not "someone ran DELETE".
- **Logical replication** (publications and subscriptions, per table) is a different tool. I only mention it; I did not run it.

## Exercise

Start two instances, make the replica, then set `synchronous_commit = remote_apply` for one session and compare what a read on the replica sees right after the commit with the default `on`. Explain the difference using the LSN columns.

## What's next

The next post is [Backup, restore and PITR](/posts/db-backup-restore-pitr/): how to get back to a moment before the bad `DELETE`.
