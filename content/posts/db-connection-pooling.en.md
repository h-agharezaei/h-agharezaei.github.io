+++
date = '2027-03-09T10:00:00+03:30'
draft = false
title = 'Connection pooling and its failure modes'
description = 'PostgreSQL connection pooling with a real max_connections limit and a pgxpool demo: waiting callers, leaked connections, idle in transaction and timeouts.'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "connection-pooling", "pgxpool", "timeouts"]
cover = { image = "/images/covers/db-connection-pooling.png", alt = "Connection pooling and its failure modes", hiddenInSingle = true }
+++

In the [previous post](/posts/db-backup-restore-pitr/) we made sure we can get data back. This post is about getting to the data at all. Every query needs a connection, and PostgreSQL gives each one its own server process, so the number is limited. A {{< term "connection-pool" "connection pool" >}} sits between your code and that limit. I used it in [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/); here I break it on purpose. It also ties into [transactions and ACID](/posts/db-transactions-acid/) and [transactions in Go](/posts/go-transactions-patterns/).

> Everything ran against a real PostgreSQL 18.3 on loopback with `max_connections = 10`, and a Go program with `pgxpool` (pgx v5.11.0). The machine was busy, so there are no timings, only counts and errors.

## The server limit

I opened connections until the server refused:

```text
connection 10 failed: ... FATAL: sorry, too many clients already (SQLSTATE 53300)
open connections: 9
max_connections: 10  client backends: 10
```

Nine were mine; the tenth slot was taken by the launcher's own idle connection (I saw it in `pg_stat_activity`). With a normal role the limit comes sooner, because `superuser_reserved_connections` (3 by default) keeps slots for superusers:

```text
connection 7 failed: ... FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute (SQLSTATE 53300)
open connections: 6
```

Ten services with a pool of 20 each already need 200 connections. So the pool size is a budget shared by every process, not a per-process whim.

## A pool of 4 and 20 goroutines

`MaxConns = 4`, 20 goroutines each call `pool.Acquire` and hold the connection until I open a gate. `pool.Stat()` has no "waiting" counter, so I counted the goroutines myself:

```text
while holding: goroutines=20 got=4 waiting=16 acquired=4 idle=0 total=4 max=4
after: acquireCount=20 emptyAcquireCount=20 newConnsCount=4 acquired=0 idle=4 total=4
server-side client backends after 20 goroutines: 5
```

Sixteen callers wait inside `Acquire`; the server saw only 4 of my connections (5 backends counts the launcher's one). `EmptyAcquireCount` is the number of acquires that found the pool empty and had to wait; here it was all 20, since every goroutine asked before any connection was free. After the release the 4 connections stay idle for reuse.

## Leak: forgetting to release

With `MaxConns = 1` I acquired a connection and never called `Release`. The next caller does not fail, it waits until its context ends:

```text
second Acquire: context deadline exceeded
pool.Exec: context deadline exceeded
acquired=1 idle=0 canceledAcquireCount=2
```

Even `pool.Exec` stalls, because it acquires internally. Without a {{< term "deadline" "deadline" >}} on the context it would block forever. In my first run I forgot `Release` at the end too, and `pool.Close()` hung until the Go runtime reported "all goroutines are asleep - deadlock!". Always `defer c.Release()` right after a successful `Acquire`, and always pass a context with a timeout.

## Idle in transaction

A connection can be taken without being used. I started a transaction, ran `select 1` and stopped. Another session saw:

```text
state="idle in transaction" last_query="select 1"
```

That connection is lost to the pool, and, according to the docs, an open transaction also holds its snapshot, which keeps [VACUUM](/posts/db-mvcc-vacuum/) from removing dead rows newer than it. A common cause is an HTTP call or a `return` that skips `Rollback` inside a transaction.

## Guard rails

Two settings turn these bugs into errors. I set both per session:

```text
SET idle_in_transaction_session_timeout = '1s'
after 1.5 s idle, next statement: FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)

SET statement_timeout = '200ms'; select pg_sleep(5)
slow statement: ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
same connection afterwards: <nil> 1
```

The first kills the connection, so the pool must discard it and open a new one. The second only cancels the statement. Lock waits have their own {{< term "lock-timeout" "lock_timeout" >}}. In production set them per role or in the connection string, not by hand.

## PgBouncer-style pooling

I did not run {{< term "pgbouncer" "PgBouncer" >}} (it is not available here), so this is from its documentation, not from a run. An external pooler lets thousands of client connections share a few server connections. In session mode a client keeps a server connection for its whole session. In transaction mode it gets one only during a transaction, which packs connections much tighter, but session state (`SET`, session-level advisory locks) must not be relied on between transactions.

## A few things to watch

- Total pool sizes across all services must stay under `max_connections` minus reserved slots.
- Always use a context with a deadline for `Acquire` and queries.
- `defer Release()` (or `Rollback()`) immediately after acquiring or beginning.
- Set `idle_in_transaction_session_timeout` and `statement_timeout` as defaults, and log when they fire.
- A bigger pool is not a faster database; if 4 connections saturate it, 40 only queue inside the server.

## Exercise

Reproduce the leak with `MaxConns = 2` and 5 goroutines, one of which forgets `Release`. Predict `acquired`, `idle` and `canceledAcquireCount`, then run it and compare.

## What's next

The next post is Case study: finding and fixing a slow query, where we use `EXPLAIN` and the tools of this series on one problem.
