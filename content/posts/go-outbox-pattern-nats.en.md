+++
date = '2027-01-31T10:00:00+03:30'
draft = false
title = 'The outbox pattern with Postgres and NATS in Go'
description = 'Solve the dual-write problem in Go: an outbox table written in the same transaction, a relay with SKIP LOCKED publishing to JetStream, and real crash runs.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "outbox", "postgres", "nats", "jetstream", "transactions"]
cover = { image = "/images/covers/go-outbox-pattern-nats.png", alt = "The outbox pattern with Postgres and NATS in Go", hiddenInSingle = true }
+++

After [concurrency patterns in Go](/posts/go-concurrency-patterns/) we have the tools to run background loops. Here is a classic job for one: telling the rest of the system that something happened. When an order is saved, other services want an `order.created` event. Saving to Postgres and publishing to NATS are two systems, and no transaction spans both. This is the **dual-write problem**, and the **{{< term "outbox-pattern" "outbox" >}} pattern** is the standard answer. I build on the orders table from [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/), use the transaction idea from [transaction patterns in Go](/posts/go-transactions-patterns/), and publish with the dedup from [idempotency in JetStream](/posts/nats-jetstream-idempotency/).

> Everything ran on Go 1.26 against a real PostgreSQL 18.3 (embedded-postgres v1.34.0, pgx v5.11.0) and an embedded nats-server v2.15.1 with nats.go v1.54.0. Each step is a separate process, so a crash is a real `os.Exit(1)`. The machine was busy (load average around 4 to 10), so I make no timing claims.

## The failure, for real

Write to the database, then publish. The process dies between the two:

```go
pool.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ('o-a', 'ali', 1500)`)
os.Exit(1) // crash here
js.Publish("orders.created", []byte(`{"order_id":"o-a"}`))
```

```
[2089] order o-a committed
[2091] orders=[o-a] outbox rows=0 unpublished=0 stream messages=0
```

The order exists and nobody will ever hear about it. Flip the order, publish first and write second, with a database write that fails:

```
[2093] event for o-b published
[2093] insert o-b: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
[2095] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2095]   stream seq 1: {"order_id":"o-b"}
```

Now there is an event for an order that does not exist. Retrying does not fix either case, because the crash takes the retry state with it.

## The outbox table

Instead of publishing, the service writes the event as a row, in the same transaction as the business row. Postgres makes both commit or neither:

```sql
CREATE TABLE outbox (
    id           bigserial   PRIMARY KEY,
    aggregate    text        NOT NULL,
    aggregate_id text        NOT NULL,
    type         text        NOT NULL,
    payload      jsonb       NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    published_at timestamptz
);
CREATE INDEX outbox_unpublished_idx ON outbox (id) WHERE published_at IS NULL;
```

`withTx` is my own small helper around `pgx.BeginFunc` (commit on nil, rollback on error):

```go
err := withTx(ctx, pool, func(tx pgx.Tx) error {
    if _, err := tx.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ($1, 'ali', $2)`, id, cents); err != nil {
        return err
    }
    _, err := tx.Exec(ctx, `INSERT INTO outbox (aggregate, aggregate_id, type, payload)
        VALUES ('order', $1, 'created', $2)`, id, payload)
    return err
})
```

I crashed the process right before commit, then ran it again normally:

```
[2097] CRASH before commit
[2099] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2103] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=1
```

The crashed order left nothing behind, neither row. The successful one left both, and the event is waiting.

## The relay

A separate loop reads unpublished rows, publishes them, and marks them. One transaction wraps the batch:

```go
rows, _ := tx.Query(ctx, `SELECT id, aggregate, type, payload FROM outbox
    WHERE published_at IS NULL ORDER BY id LIMIT $1 FOR UPDATE SKIP LOCKED`, n)
// ... collect the batch, then for each row:
ack, err := js.Publish(r.aggregate+"s."+r.typ, r.payload,
    nats.MsgId("outbox-"+strconv.FormatInt(r.id, 10)))
// ... after the loop:
tx.Exec(ctx, `UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, ids)
```

`FOR UPDATE` locks the rows; `SKIP LOCKED` makes a second relay skip rows the first one holds instead of waiting. The `Nats-Msg-Id` is the outbox id, so a repeated publish is a no-op.

Delivery is **at least once**: the relay can publish, then die before the `UPDATE`. I forced that with `os.Exit(1)` after the publish, then started a healthy relay:

```
[2105] CRASH after publishing 1 event(s), before marking them
[2107] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=2
[2109] outbox id=2: PubAck Duplicate=true (stream seq 2)
[2109] relay R2: published=1 duplicates=1
[2111] orders=[o-a,o-c2] outbox rows=1 unpublished=0 stream messages=2
```

The row stayed unpublished (the transaction rolled back), the second relay published it again, and JetStream answered `Duplicate=true`. The stream still holds one copy. The dedup window is limited (I set 5 minutes), so consumers must still be idempotent, as in the idempotency post. My demo consumer keys on `Nats-Msg-Id` and reported `applied=2 skipped=0`, because inside the window the stream already removed the duplicate.

## Two relays at once

I seeded 200 orders and started two relay processes together:

```
[3412] relay A: published=100 duplicates=0
[3413] relay B: published=100 duplicates=0
[3416] orders=[202 orders] outbox rows=201 unpublished=0 stream messages=202
```

100 plus 100 is 200, with no duplicates seen by either. (The 100/100 split is what this run produced; it will vary.) The stream has 202 messages: these 200 plus the two from earlier.

## Cleanup

Published rows are dead weight. A periodic `DELETE FROM outbox WHERE published_at < now() - interval '7 days'` removes them; I backdated some rows and it deleted 99. Keep them for a few days if you want to debug or replay.

## A few things to watch

- **Ordering.** Two relays can publish events of the same aggregate out of order, because they take different batches. Even one relay only follows `id` order, and a bigserial `id` is not commit order when transactions overlap. If order matters, run one relay per shard of `aggregate_id`, or make consumers tolerate it by carrying a version in the payload.
- The relay holds a transaction (and row locks) while it talks to NATS. Keep batches small and put a timeout on publishing.
- `bigserial` has gaps: the crashed create above consumed id 1, so the first real event got id 2.
- Polling costs latency or load, depending on the interval. Postgres `LISTEN/NOTIFY` can wake the relay sooner, but I did not test it here; keep polling as the fallback anyway.
- The relay is a worker like any other: stop it cleanly on shutdown, as in [graceful shutdown and workers](/posts/go-graceful-shutdown-workers/). If it is killed mid-batch, the transaction rolls back and the rows are retried.
- A growing table needs the cleanup job and that partial index.

## What's next

Next I will build a gRPC service in Go.
