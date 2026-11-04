+++
date = '2027-03-09T10:00:00+03:30'
draft = false
title = 'Connection pooling and its failure modes'
description = 'PostgreSQL connection pooling with a real max_connections limit and a pgxpool demo: waiting callers, leaked connections, idle in transaction and timeouts.'
contentType = 'tutorial'
categories = ["Databases"]
series = ["Databases"]
tags = ["databases", "postgresql", "connection-pooling", "pgxpool", "timeouts"]
cover = { image = "/images/covers/db-connection-pooling.png", alt = "Connection pooling and its failure modes", hiddenInSingle = true }
+++

Your service runs fine with three instances. You scale it to thirty to survive a busy day, and suddenly requests start failing with `sorry, too many clients already`. The database is not slow and its CPU is idle. It simply refuses to accept one more connection. A database connection looks like a cheap thing, a line to the server, but it is the resource that runs out first, and it deserves some thought.

[Backup, restore and PITR](/posts/db-backup-restore-pitr/) made sure the data can come back; this post is about being able to reach the data at all. A {{< term "connection-pool" "connection pool" >}} is the standard answer: instead of opening a connection for every query, the application opens a few at the start, lends one for each piece of work and takes it back afterwards. I used a pool in [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/); here I break it on purpose to see how it fails. It also ties into [transactions and ACID](/posts/db-transactions-acid/) and [transactions in Go](/posts/go-transactions-patterns/).

> Everything ran against a real PostgreSQL 18.3 on loopback with `max_connections = 10`, and a Go program with `pgxpool` (pgx v5.11.0), which is a pool that lives inside the application process. I re-ran the demo for this version of the post. The machine was busy, so there are no timings, only counts and errors. PgBouncer is not installed here and I did not run it; its part below is from the documentation.

## Why a connection is expensive

PostgreSQL serves each connection with its own operating-system process. The server does not have a thread pool that shares work between clients: when a client connects, the main process (the postmaster) starts a new process just for it, and that process lives as long as the connection. That has a plain consequence: more connections means more processes, each with its own memory and its own share of the scheduler's attention, even when they are all idle. So the server has a hard limit, `max_connections`, and the default is not large.

I checked the one-process-per-connection claim on the demo server. I counted the processes whose title is `postgres: app orders ...`, which is how PostgreSQL labels a client's process, with `ps`. Then I opened three more connections that each ran `select pg_sleep(8)`:

```text
client-backend processes before: 1
with 3 more connections: 4
after the sleeps ended: 1
```

Each new connection added one process, and when they closed the processes went away. (The `1` is a connection that the demo's launcher keeps open, which will matter in the next section.) This is the cost a pool avoids: it keeps a small, fixed number of these processes, and reuses them.

## The server limit

To see the limit, I opened connections until the server refused:

```text
connection 10 failed: ... FATAL: sorry, too many clients already (SQLSTATE 53300)
open connections: 9
max_connections: 10  client backends: 10
```

The limit is 10, and the tenth attempt of mine failed. Nine were mine; the tenth slot was taken by the launcher's own idle connection (`pg_stat_activity` lists a session running `SELECT 1` that is not mine). With a normal role, as opposed to the superuser I used above, the limit comes sooner, because `superuser_reserved_connections` (3 by default) keeps slots only superusers can use. I created a role without superuser rights and repeated it:

```text
connection 7 failed: ... FATAL: remaining connection slots are reserved for roles with the SUPERUSER attribute (SQLSTATE 53300)
open connections: 6
```

Six of mine plus the launcher's one fill the seven slots that a normal role can use (10 minus 3 reserved). Now think about a real deployment: ten services with a pool of 20 each already need 200 connections. So the pool size is a budget shared by every process that connects to this database, not a per-process whim. Thirty instances with a pool of 10 each is 300 connections.

## A pool of 4 and 20 goroutines

What does a pool do when there are more callers than connections? In the demo `MaxConns = 4`, and 20 goroutines each call `pool.Acquire` and hold the connection until I open a gate. `pool.Stat()` has no "waiting" counter, so I counted the goroutines myself:

```text
while holding: goroutines=20 got=4 waiting=16 acquired=4 idle=0 total=4 max=4
after: acquireCount=20 emptyAcquireCount=20 newConnsCount=4 acquired=0 idle=4 total=4
server-side client backends after 20 goroutines: 5
```

In the first line, only 4 goroutines got a connection (`got=4`) and the other 16 are waiting inside `Acquire`. Nothing fails; the callers simply queue. All 4 connections are lent out (`acquired=4`) and none is idle. In the second line, after the gate opened, all 20 acquires finished (`acquireCount=20`), but only 4 connections were ever created (`newConnsCount=4`). `emptyAcquireCount` counts the acquires that found the pool empty and had to wait; here that is all 20, because every goroutine asked before any connection was free. The 4 connections now sit idle, ready for reuse. The last line is the server's side: it saw only 4 connections from me (5 backends counts the launcher's one), not 20.

The pool turned 20 callers into 4 server processes. To check this with short jobs, which is closer to a real service, I ran a scratch variant (I added it to a throwaway copy of the demo; it is not in the demo directory): 200 goroutines, each running one `select pg_sleep(0.02)` through a pool of 4, while a separate connection sampled the number of client backends every few milliseconds:

```text
200 goroutines, pool of 4: completed=200 newConnsCount=4 maxClientBackendsSeen=6
```

All 200 finished, with 4 connections created in total. The maximum number of client backends the sampler ever saw was 6: my 4, the launcher's one and the sampler's own connection. (I ran it twice and got the same.) The server never had more than my 4 working for my 200 callers.

## Leak: forgetting to release

The danger of lending is that someone does not return. With `MaxConns = 1` I acquired a connection and never called `Release`. The next caller does not fail, it waits until its context ends:

```text
second Acquire: context deadline exceeded
pool.Exec: context deadline exceeded
acquired=1 idle=0 canceledAcquireCount=2
```

Both waits (`Acquire` and `pool.Exec`, which acquires internally) ended with `context deadline exceeded`, after 500 ms, because I gave them a context with a timeout. `canceledAcquireCount=2` counts these two cancelled waits. Without a {{< term "deadline" "deadline" >}} on the context they would block forever, and a leak in one request path slowly turns into a frozen service. In my first run I forgot `Release` at the end too, and `pool.Close()` hung until the Go runtime reported "all goroutines are asleep - deadlock!". Always `defer c.Release()` right after a successful `Acquire`, and always pass a context with a timeout.

## Idle in transaction

A connection can also be lost without being leaked. A session that started a transaction and stopped sending statements is {{< term "idle-in-transaction" "idle in transaction" >}}: the pool thinks it is busy, so nobody else can use it. I started a transaction, ran `select 1` and stopped. Another session saw:

```text
seen from another session: state="idle in transaction" last_query="select 1"
```

That connection is lost to the pool. According to the docs, an open transaction also keeps its snapshot, which stops [VACUUM](/posts/db-mvcc-vacuum/) from removing dead rows newer than it. A common cause is an HTTP call made in the middle of a transaction, or an early `return` that skips `Rollback`.

## Guard rails

Two settings turn these bugs into errors instead of silent stalls. I set both per session:

```text
SET idle_in_transaction_session_timeout = '1s'
after 1.5 s idle, next statement: FATAL: terminating connection due to idle-in-transaction timeout (SQLSTATE 25P03)
idle-in-transaction sessions now: 0

SET statement_timeout = '200ms'; select pg_sleep(5)
slow statement: ERROR: canceling statement due to statement timeout (SQLSTATE 57014)
same connection afterwards: <nil> 1
```

The first one kills the forgotten session: after 1.5 seconds the server had terminated it (the count of idle-in-transaction sessions fell to 0), and the next statement on it failed with `FATAL`. The pool must then discard that connection and open a new one. The second only cancels the statement and leaves the connection usable (`<nil> 1` means the next `select 1` worked and returned 1). Waiting for locks has its own {{< term "lock-timeout" "lock_timeout" >}}. In production set these per role or in the connection string, not by hand in each session.

## What an external pooler changes

I did not run {{< term "pgbouncer" "PgBouncer" >}} (it is not available here), so this part is from its documentation, not from a run. The pools above live inside each application process: thirty instances with 10 connections each still make 300 server connections. An external pooler is a separate program placed between all the applications and PostgreSQL, so that thousands of client connections share a few server connections. In session mode a client keeps a server connection for its whole session. In transaction mode it gets one only for the length of a transaction and then returns it, which packs connections much tighter. The 200-goroutine run above is the same idea in miniature: many callers, each holding a connection only while it works, over a few real connections. The price in transaction mode is that session state (`SET`, session-level advisory locks) must not be relied on between transactions, because the next transaction may run on a different server connection.

## The connection budget and its traps

- **Total pool sizes across all services must stay under `max_connections` minus the reserved slots.** Count every instance of every service, and the migrations and admin tools that also connect.
- **Always use a context with a deadline for `Acquire` and for queries,** so that a leak becomes an error and not a hang.
- **`defer Release()` (or `Rollback()`) immediately after acquiring or beginning.**
- **Set `idle_in_transaction_session_timeout` and `statement_timeout` as defaults, and log when they fire.**
- **A bigger pool is not a faster database.** If 4 connections already saturate it, 40 only queue inside the server, and cost more processes.

## Exercise

Reproduce the leak with `MaxConns = 2` and 5 goroutines, one of which forgets `Release`. Predict `acquired`, `idle` and `canceledAcquireCount`, then run it and compare.

## What's next

The next post is [Case study: finding and fixing a slow query](/posts/db-slow-query-case-study/), where we use `EXPLAIN` and the tools of this series on one problem, from the first complaint to the fix.
