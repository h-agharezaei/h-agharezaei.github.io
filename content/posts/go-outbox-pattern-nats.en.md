+++
date = '2027-01-31T10:00:00+03:30'
draft = false
title = 'The outbox pattern with Postgres and NATS in Go'
description = 'Solve the dual-write problem in Go: an outbox table written in the same transaction, a relay with SKIP LOCKED publishing to JetStream, and real crash runs.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "outbox", "postgres", "nats", "jetstream", "transactions"]
cover = { image = "/images/covers/go-outbox-pattern-nats.png", alt = "The outbox pattern with Postgres and NATS in Go", hiddenInSingle = true }
+++

A customer places an order. Your service saves it in Postgres, and it should also tell the rest of the system: the warehouse needs to reserve stock, the email service needs to send a confirmation. So the service publishes an `order.created` event to a message broker, here NATS.

Those are two steps in two different systems. Postgres can make its own writes all-or-nothing with a transaction ([transactions and the repository pattern in Go](/posts/go-transactions-patterns/)), but no transaction spans both Postgres and NATS. So what happens if the process dies between the two steps? If it died after the save, the order exists and nobody ever hears about it. If you publish first and the save fails, everybody hears about an order that does not exist. This is called the **dual-write problem**: you write to two places and there is no way to make both writes succeed or fail together.

The standard answer is the **{{< term "outbox-pattern" "outbox pattern" >}}**. The idea is plain. Do not publish from the request. Instead, write the event as a row into an `outbox` table in the *same* database transaction as the order. Now the order and its event commit together or not at all, because it is one Postgres transaction. A separate background loop, called the **relay**, reads the unpublished rows and sends them to the broker later. Think of the tray on an office desk: you put the letter in the tray in the same movement as you file the paperwork, and the post clerk collects the tray later. The letter cannot get lost between your desk and the mailbox, though the clerk might occasionally hand the same letter over twice. We will see that this is exactly what happens, and what to do about it.

I build on the orders table from [Postgres with pgx and sqlc](/posts/go-postgres-pgx-sqlc/). The relay is a background loop of the kind from [concurrency patterns in Go](/posts/go-concurrency-patterns/). Publishing uses JetStream's duplicate detection, which I described in [idempotency in JetStream](/posts/nats-jetstream-idempotency/).

> Everything was re-run with Go 1.27 against a real PostgreSQL 18.3 (embedded-postgres v1.34.0, pgx v5.11.0) and an embedded nats-server v2.15.1 with nats.go v1.54.0, and the outputs below are from that run. Each step is a separate process, so a crash is a real `os.Exit(1)`. I make no timing claims. The numbers in square brackets in the outputs are process IDs and change on every run (I kept the ones from the original run). The code is a local example, not a published repo.

## The failure, for real

First the broken versions, so we can see the problem and not only believe it. The first one writes to the database and then publishes. The process dies between the two:

```go
pool.Exec(ctx, `INSERT INTO orders (id, customer, cents) VALUES ('o-a', 'ali', 1500)`)
os.Exit(1) // crash here
js.Publish("orders.created", []byte(`{"order_id":"o-a"}`))
```

After that, a small `report` command prints what is in Postgres and what is in the stream:

```
[2089] order o-a committed
[2091] orders=[o-a] outbox rows=0 unpublished=0 stream messages=0
```

The order is saved, and the stream has zero messages. Nobody will ever hear about order `o-a`.

Now flip the order: publish first, then write, with a database write that fails (the demo inserts a negative amount, which the `CHECK` constraint refuses):

```
[2093] event for o-b published
[2093] insert o-b: ERROR: new row for relation "orders" violates check constraint "orders_cents_check" (SQLSTATE 23514)
[2095] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2095]   stream seq 1: {"order_id":"o-b"}
```

Now there is an event in the stream for an order that does not exist. Adding a retry does not fix either case, because the crash takes the retry state down with the process.

## The outbox table

Instead of publishing, the service writes the event as a row. Here is the table:

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

`aggregate` is the kind of thing the event is about (`order`), `aggregate_id` is which one, `type` is what happened (`created`) and `payload` is the event body. `published_at` stays empty until the relay has sent the row, and the partial index on those empty rows keeps "give me the unpublished ones" fast even when the table grows.

`withTx` is my own small helper around `pgx.BeginFunc` (commit on nil, rollback on error). The service writes the order and its event inside it:

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

To test it, I crashed the process right before the commit, then ran the same step again normally:

The output of those two steps, each followed by a report:

```
[2097] CRASH before commit
[2099] orders=[o-a] outbox rows=0 unpublished=0 stream messages=1
[2103] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=1
```

The first report (after the crash) shows no `o-c1` order and no outbox row: both inserts rolled back together. The second report (after the normal run) shows the order `o-c2` and exactly one outbox row waiting to be published. (The stream still holds only the orphan `o-b` event from the previous experiment.) The order and its event can no longer exist separately.

## The relay

The relay is the second half. It runs in a separate process and does the same thing in a loop: read a batch of unpublished rows, publish each one to JetStream, and mark them published. One transaction wraps the whole batch:

```go
rows, _ := tx.Query(ctx, `SELECT id, aggregate, type, payload FROM outbox
    WHERE published_at IS NULL ORDER BY id LIMIT $1 FOR UPDATE SKIP LOCKED`, n)
// ... collect the batch, then for each row:
ack, err := js.Publish(r.aggregate+"s."+r.typ, r.payload,
    nats.MsgId("outbox-"+strconv.FormatInt(r.id, 10)))
// ... after the loop:
tx.Exec(ctx, `UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, ids)
```

Two details are worth explaining. `FOR UPDATE` locks the selected rows until the transaction ends. `SKIP LOCKED` tells Postgres: if some of those rows are already locked by someone else, do not wait for them, just skip them. That is what lets several relays work on the same table without blocking each other or taking the same rows. And `nats.MsgId(...)` sets the `Nats-Msg-Id` header to the outbox row's id. JetStream remembers recent message IDs, and if it sees the same ID twice inside its duplicate window, it does not store the second one but answers with `Duplicate=true`. I will explain why we need that in a moment. In the demo the loop uses batches of 10 rows and keeps going until nothing is left.

Notice the order of operations: publish first, mark after. If the relay dies between those two, the row stays unpublished and will be sent again. So the delivery is **at least once**: an event is never lost, but it can be sent more than once. I forced this on purpose with `os.Exit(1)` right after the publish (before the `UPDATE`), then started a healthy relay:

```
[2105] CRASH after publishing 1 event(s), before marking them
[2107] orders=[o-a,o-c2] outbox rows=1 unpublished=1 stream messages=2
[2109] outbox id=2: PubAck Duplicate=true (stream seq 2)
[2109] relay R2: published=1 duplicates=1
[2111] orders=[o-a,o-c2] outbox rows=1 unpublished=0 stream messages=2
```

Line by line. The first relay published the event and died. The report then shows `stream messages=2` (the old orphan plus the new event) but `unpublished=1`: the transaction rolled back, so the database still thinks the row was never sent. The second relay publishes the same row again, with the same message ID, and JetStream answers `Duplicate=true`. The last report shows `unpublished=0` and still `stream messages=2`, so the stream holds a single copy of the event.

That protection has limits. JetStream's duplicate detection only remembers IDs for a window of time (I set 5 minutes), so a duplicate that arrives later gets through. Consumers of events should therefore be idempotent anyway, meaning that handling the same event twice has the same effect as handling it once ({{< term "idempotency" "idempotency" >}}, as in the idempotency post). My demo consumer keys on `Nats-Msg-Id` and reported `applied=2 skipped=0`: here it had nothing to skip, because the stream had already dropped the duplicate.

## Two relays at once

One relay is a single point of failure, so you may want two. I seeded 200 orders and started two relay processes at the same time:

```
[3412] relay A: published=100 duplicates=0
[3413] relay B: published=100 duplicates=0
[3416] orders=[202 orders] outbox rows=201 unpublished=0 stream messages=202
```

Each relay published 100 events and neither saw a duplicate. That is `SKIP LOCKED` doing its job: they never fought over the same rows. (The 100/100 split is what this run produced; it will vary.) The stream has 202 messages: these 200 plus the two from earlier experiments. The outbox has 201 rows, because the first order of the crash test left none behind.

## Cleanup

Published rows are dead weight. A periodic `DELETE FROM outbox WHERE published_at < now() - interval '7 days'` removes them. To test it, I backdated some published rows and ran the delete, which removed 99. Keep rows for a few days if you want to debug or replay.

## Hidden costs of the outbox

- **Ordering.** Two relays can publish events of the same aggregate out of order, because they take different batches. Even a single relay only follows `id` order, and a `bigserial` id is not commit order when transactions overlap. If order matters, run one relay per shard of `aggregate_id`, or make consumers tolerate it by carrying a version in the payload.
- **The relay holds a transaction (and row locks) while it talks to NATS.** Keep batches small and put a timeout on publishing, or a slow broker will keep rows locked.
- **`bigserial` has gaps.** The crashed create above consumed id 1, so the first real event got id 2. Never treat the id sequence as "no gaps".
- **Polling costs latency or load, depending on the interval.** Postgres `LISTEN/NOTIFY` can wake the relay sooner, but I did not test it here; keep polling as the fallback anyway.
- **The relay is a worker like any other.** Stop it cleanly on shutdown, as in [graceful shutdown and workers](/posts/go-graceful-shutdown-workers/). If it is killed mid-batch, the transaction rolls back and the rows are retried.
- **The table grows.** It needs the cleanup job and that partial index.

## What's next

The next post is "A gRPC service in Go". Events now leave the service reliably, but some callers need an answer right now, so the `orders` service gets a second front door for synchronous calls, with a typed contract. (That demo uses an in-memory store and is not wired to the outbox.)
