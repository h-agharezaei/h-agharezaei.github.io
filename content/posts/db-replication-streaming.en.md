+++
date = '2027-02-13T10:00:00+03:30'
draft = false
title = 'Replication with two real instances'
description = 'PostgreSQL streaming replication with two real instances: setup, lag in bytes, synchronous commit blocking, promotion, and why a replica is no backup.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "replication", "wal", "high-availability"]
cover = { image = "/images/covers/db-replication-streaming.png", alt = "Replication with two real instances", hiddenInSingle = true }
+++

In the [previous post](/posts/db-partitioning/) we split one big table inside one server. This post is about the other direction: keeping a second copy of the whole server. {{< term "replication" "Replication" >}} gives you read capacity and a standby you can promote when the primary dies. It builds directly on the {{< term "wal" "WAL" >}} from [transactions and ACID](/posts/db-transactions-acid/) and on the dead rows from [MVCC and VACUUM](/posts/db-mvcc-vacuum/).

> Everything ran on two real PostgreSQL 18.3 instances on one machine (ports 55713 and 55714, loopback only, no Docker). There are no timings, only bytes and states. The embedded binaries had no `pg_basebackup`, and the only one on this machine is version 17.5, which refuses to talk to a 18.3 server. So I made the copy by hand: I stopped the primary, copied its data directory and wrote the two things `pg_basebackup -R` would write. On a live system use `pg_basebackup -D replica -R -X stream`; I did not run it.

## Configure the primary

I checked the defaults before touching anything: `wal_level` is `replica`, `max_wal_senders` is 10, `hot_standby` is `on`. Only `listen_addresses = '127.0.0.1'` was changed. A replication role and a `pg_hba.conf` line for it are needed; `initdb --auth-host=scram-sha-256` already generated the line:

```text
host    replication     all             127.0.0.1/32            scram-sha-256

CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '...';
```

## Make the replica

A standby is a copy of the data directory plus a file `standby.signal` (its mere presence means "stay in recovery") and a `primary_conninfo`. This is what `-R` writes into `postgresql.auto.conf`:

```text
primary_conninfo = 'host=127.0.0.1 port=55713 user=replicator password=... application_name=replica1'
```

After starting both, the primary sees the replica and the {{< term "lsn" "LSN" >}} positions match:

```text
primary> SELECT application_name, state, sent_lsn, replay_lsn, sync_state FROM pg_stat_replication;
 replica1 | streaming | 0/1830840 | 0/1830840 | async

replica> SELECT pg_is_in_recovery();   -- t        (primary: f)
replica> SELECT status, sender_port FROM pg_stat_wal_receiver;
 streaming | 55713
```

## Writes flow one way

I inserted a customer on the primary and polled the replica until it appeared (it took one poll here). The replica refuses writes:

```text
replica> INSERT INTO customers(name,email,country) VALUES ('x','x@example.com','NL');
ERROR:  cannot execute INSERT in a read-only transaction
```

## Lag in bytes

Replication is asynchronous by default, so a reader on the replica can see old data. I inserted 300000 rows into a table and asked the primary right after:

```text
SELECT pg_wal_lsn_diff(sent_lsn, replay_lsn) AS lag_bytes FROM pg_stat_replication;
 6291496
replica> SELECT count(*) FROM big;   -- 0   (the rows were not replayed yet)
```

One poll later the count was 300000 and the lag 0. The 6 MB figure is what I saw in this run; it varies from run to run. For a service this means a read-your-writes bug if you send the read to a replica right after the write.

## Synchronous commit

With `synchronous_standby_names = 'replica1'` (reload is enough) `sync_state` became `sync`, and a {{< term "synchronous-commit" "synchronous commit" >}} waits until the standby has the WAL. I stopped the replica and ran an INSERT in a background session. It hung, and `pg_stat_activity` showed the reason:

```text
IPC/SyncRep | active | insert into customers(name,email,country
```

I cancelled it with `pg_cancel_backend`:

```text
WARNING:  canceling wait for synchronous replication due to user request
DETAIL:  The transaction has already committed locally, but might not have been replicated to the standby.
```

The row was in fact committed on the primary. That is the price of the setting: with one synchronous standby, a dead standby stops all writes. After restarting the replica it caught up by itself.

## Promote

```text
replica> SELECT pg_promote(wait => true);   -- t
replica> SELECT pg_is_in_recovery();        -- f
replica> INSERT INTO customers(...) VALUES ('on_new_primary', ...);   -- INSERT 0 1
```

Now the dangerous part. I had left the old primary running, and it happily accepted its own write:

```text
old primary: 8|on_old_primary  7|sync
new primary: 39|on_new_primary  7|sync
```

That is {{< term "split-brain" "split-brain" >}}: two servers, both writable, with different histories. Core PostgreSQL does no automatic {{< term "failover" "failover" >}}; tools such as Patroni or repmgr exist for that (I did not run them). Whatever you use must make sure the old primary is fenced off before it comes back.

## A replica is not a backup

On the primary I deleted 10 rows from `products`. The replica showed 0 rows on the first poll. The DELETE is just another WAL record, so a bad `UPDATE`, `DELETE` or `DROP TABLE` replicates faithfully. The dead versions that [VACUUM](/posts/db-mvcc-vacuum/) would still need are not an undo log you can use. For recovery you need real backups.

## A few things to watch

- Async replicas lag. Do not read your own write from them without checking the LSN or using the primary.
- One synchronous standby turns its failure into a write outage; use several candidates or accept async.
- Promotion is one command; deciding who is the primary, and stopping the old one, is the hard part.
- Replicas hold the same bad data as the primary. They answer "the server died", not "someone ran DELETE".
- I only mention logical replication (publications and subscriptions, per table); I did not run it.

## Exercise

Start two instances, make the replica, then set `synchronous_commit = remote_apply` for one session and compare what a read on the replica sees right after commit with the default `on`. Explain the difference using the LSN columns.

## What's next

The next post is Backup, restore and PITR: how to get back to a moment before the bad DELETE.
