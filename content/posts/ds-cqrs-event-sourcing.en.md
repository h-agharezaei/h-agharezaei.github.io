+++
date = '2027-05-26T10:00:00+03:30'
draft = false
title = 'CQRS and event sourcing'
description = 'CQRS and event sourcing in Go on a real Postgres: optimistic concurrency, snapshots, upcasting, stale projections, replay, and when not to use it.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "cqrs", "event-sourcing", "postgres", "go"]
cover = { image = "/images/covers/ds-cqrs-event-sourcing.png", alt = "CQRS and event sourcing", hiddenInSingle = true }
+++

You deposit money into an account. The app answers "done". You open the balance page, and it still shows the old balance. A second later it shows the right one. Is that a bug?

In the design of this post it is not a bug, it is the price of a choice. The write was stored as one record, and the balance page reads from a *different* table that is filled in a moment later. The two models of the data, the one you write to and the one you read from, do not match for a short time. This post is about why anyone would build a system like that, what it gives you in return, and what it costs. It also measures how often the mismatch happens in the demo.

Two ideas are involved, and they are often used together:

- {{< term "event-sourcing" "Event sourcing" >}}: instead of storing the current state ("balance: 3000"), store the list of facts that led to it ("account opened", "10000 deposited", "7000 withdrawn"). The current state is calculated from the list.
- {{< term "cqrs" "CQRS" >}} (Command Query Responsibility Segregation): use one model for **commands** (writes that change something) and a separate model for **queries** (reads). The read side is shaped for the questions you ask, and it is built from the events.

Sagas were the [previous post](/posts/ds-saga-vs-2pc/), and a saga already needs a log of what happened. Here the log becomes the data itself. For the background, see [transactions and ACID](/posts/db-transactions-acid/), [consistency models](/posts/ds-consistency-models/), [the outbox pattern](/posts/go-outbox-pattern-nats/) and [idempotency in JetStream](/posts/nats-jetstream-idempotency/).

> This is a Go program on one machine against a real PostgreSQL 18.3 on loopback. I re-ran it with Go 1.27 (the original run used Go 1.26) and the output matches the original exactly; `go test -race` passes. The tests use an in-memory store, not Postgres. Randomness is seeded, and I show counts, not timings. The "poller schedule" in section 3 and the "crash" in section 4 are simulated, as I explain there.

## State as a fold of events

Here is the idea with the smallest example. One account, stored as its events, in order:

```
1  Opened
2  Deposited 10000
3  Withdrawn 7000
```

Nothing stores "balance 3000". To get it, start from an empty account and apply each event in turn: opened, then +10000, then −7000. That operation, going through the list and updating the state at each step, is a **fold**. The balance is whatever the fold gives: 3000.

The code follows the same shape. An `Account` is never stored. It has an `Apply(event)` method that changes the state and never refuses anything. The rules live in **commands**: a command looks at the current state and either returns new events or an error. It never changes anything itself. For example, `Withdraw(99999)` on an account with 10000 returns `insufficient funds`, and no event is stored. Events are only ever added. The table has `PRIMARY KEY (stream_id, version)`, so each account (a "stream") has its events numbered 1, 2, 3, and a `bigserial` position column gives a global order across streams.

## Two writers at once: optimistic concurrency

What if two requests change the same account at the same time? Both load the account, see 10000, and both decide to withdraw 7000. With state stored in a row, you would use a lock or lose one update. Here the version number does the job. The demo runs two sessions in a fixed order, both loading version 2 with a balance of 10000:

```
withdraw 99999 -> insufficient funds (no event stored)
A and B both loaded version 2 balance 10000
A append: <nil>
B append: version conflict: ERROR: duplicate key value violates unique constraint "events_pkey" (SQLSTATE 23505)
B reloads and decides again: retries=0 err=insufficient funds
   1 Opened {"owner": "demo"}
   2 Deposited {"currency": "USD", "amount_cents": 10000}
   3 Withdrawn {"currency": "USD", "amount_cents": 7000}
raw UPDATE on an event: UPDATE 1 <nil> (rolled back)
```

Line by line:

- The first line is the rule at work: a command that breaks the rule stores nothing.
- A and B both loaded version 2, so both want to write version 3. A's append succeeds (`<nil>` means no error).
- B's append is refused by the database: there is already a version 3 for this stream, and the primary key `(stream_id, version)` does not allow a second one. The code turns that error into a "version conflict".
- B reloads, now sees a balance of 3000, runs the command again, and this time the rule rejects it: `insufficient funds`.
- The three lines with numbers are the final stream: Opened, Deposited 10000, Withdrawn 7000.

This is {{< term "optimistic-concurrency" "optimistic concurrency" >}}: nobody took a lock. Both tried, one lost, and the loser looked again before deciding.

The last line is a warning about "immutable" events. In SQL an event *can* be updated: the `UPDATE` changed one row (`UPDATE 1`), and I rolled it back. The application simply never issues one. I did not try to forbid it with a trigger or a revoked privilege.

## Replay, snapshots and time travel

Loading an account means replaying all its events, and that gets slower as the stream grows. A {{< term "event-snapshot" "snapshot" >}} fixes that: every so often you save the folded state at a version, and loading starts from the snapshot and replays only the events after it. The demo builds a stream of 10,123 events with a snapshot every 500 events and loads it both ways:

```
no snapshot : version=10123 balance=989607 replayed=10123 events
snapshot/500: version=10123 balance=989607 replayed=123 events
state at 2027-03-01: version=1416 balance=138314 (replayed 1416 events)
```

Both loads give the same state, but the second replayed 123 events instead of 10,123 (the last snapshot was at version 10000). The snapshot is a cache: you can delete it and nothing is lost. The events stay the truth.

The last line is the nice side effect of keeping the history: **time travel**. To know the balance on 1 March 2027, replay the events up to that date. In this demo each event's `created_at` is one hour after the previous one, starting from 1 January, so 1 March (31 + 28 days, 59 × 24 = 1416 hours) is version 1416. No audit table was needed.

## When the event shape changes

Events live forever, but your code changes. Suppose version 1 of the code stored a deposit as `{"amount": 5}` (whole dollars), and version 2 stores `{"amount_cents": 500, "currency": "USD"}`. You must not edit the old rows. Instead you convert while reading, which is called {{< term "upcasting" "upcasting" >}}. To test it, I inserted legacy rows with raw SQL and read them through the upcaster:

```
  stored Deposited {"amount": 5}                                    -> upcast {"amount_cents":500,"currency":"USD"}
  stored Deposited {"currency": "USD", "amount_cents": 250}         -> upcast {"currency": "USD", "amount_cents": 250}
  stored Withdrawn {"amount": 2}                                    -> upcast {"amount_cents":200,"currency":"USD"}
legacy balance=550 cents
```

The first and third rows are old-shape events, converted to cents. The second is already in the new shape, so it passes through unchanged. (Its keys look reordered compared to what I inserted, `{"amount_cents": 250, "currency": "USD"}`, because the column is `jsonb`, which does not keep the order of keys.) The balance checks out: 500 + 250 − 200 = 550. A unit test checks the conversion and that the input is not modified.

## The query side is eventually consistent

Now back to the opening question. Writes go to the `events` table. Reads go to two other tables, `account_balances` and `daily_totals`, which hold the read model: tables shaped for the questions the screens ask. They are built by a {{< term "projection" "projection" >}}: a poller that reads the events after a **checkpoint** (the position of the last event it handled), updates the read tables, and saves the new checkpoint, all in the same database transaction. If it crashes, the transaction and the checkpoint stay together, so nothing is applied twice or skipped.

To see the mismatch, the demo makes 300 deposits spread over 5 accounts. After each deposit it immediately reads the account's balance from the read model. The poller does not run on a timer: a seeded coin flip decides, one time in three, whether it runs after a write, and then it handles at most 5 events. It is a deliberately slow projector, so the lag is visible:

```
300 writes, each followed by an immediate read of the read model: 222 stale reads, max lag 10 events
after the projector catches up, read model == truth: true
```

In 222 of the 300 cases the read model had not yet seen the deposit that had just been acknowledged. At the worst moment it was 10 events behind the log. Once the poller caught up, the read model matched the truth exactly. That is {{< term "eventual-consistency" "eventual consistency" >}}, chosen on purpose: 222 of 300 "read your own write" checks failed. These numbers come from my artificial schedule, not from a real projector's behaviour. In my experience the UI has to be designed for it: show the result of the command you just made instead of re-reading it, or wait for the projection.

The advantage of the log is that projections are disposable. I reset the checkpoint to 0 and replayed all 10,435 events a second time over the existing read tables:

```
replayed 10435 events twice over: balances unchanged=true; daily_totals deposited 2048518 -> 4097036 (naive counter doubled)
rebuild from scratch: 10435 events replayed -> 8 balance rows, 422 daily rows, deposited 2048518 (== first run: true)
```

The two read tables behaved differently. The balance handler is {{< term "idempotency" "idempotent" >}}: its SQL is `ON CONFLICT ... DO UPDATE ... WHERE last_version < EXCLUDED.last_version`, which skips a version that was already applied, so the balances did not change. The daily counter just adds, so it counted everything twice: 2,048,518 became 4,097,036. The fix is the second line: empty the read tables, reset the checkpoint and replay everything. That rebuilt 8 balance rows and 422 daily rows and the total returned to 2,048,518, the same as the first run. Several different projections from one log are the same loop with different handlers.

## The log as an outbox

The events table can also serve as an {{< term "outbox-pattern" "outbox" >}}: a publisher is just another reader with its own checkpoint, sending each event to a message broker. If it dies after publishing but before saving its checkpoint, the batch is published again. That is {{< term "at-least-once-delivery" "at-least-once delivery" >}}. In the demo the "broker" is an in-memory list, and I simulated 69 crashes by moving the checkpoint back by one batch of 50 events every fourth batch:

```
events=10435 deliveries=13885 distinct=10435 simulated-crashes=69
```

There were 13,885 deliveries of 10,435 different events, so 3,450 were duplicates (69 × 50). A consumer that ignores an event it has already seen, using `(stream_id, version)` as the key, ends with exactly 10,435 effects. This is the same pattern as in [the outbox pattern](/posts/go-outbox-pattern-nats/): duplicates are fine if the consumer is idempotent.

## When not to use it

In my opinion most CRUD applications should not use event sourcing. You pay for it in complexity, in eventual consistency and in upcasters that you must keep forever. A plain table plus an audit table gives you history with far less machinery. Events earn their place when the history *is* the domain, as in ledgers or orders with a complex lifecycle.

An immutable log also collides with requests to delete personal data. One known answer is {{< term "crypto-shredding" "crypto-shredding" >}}: encrypt the personal fields with a key per person and destroy the key when asked to forget. I did not implement it. One more caveat, which I did not reproduce here: a `bigserial` position can become visible out of order when transactions run concurrently, so a poller that moves its checkpoint past a position can skip an event that commits late.

## Common traps

- **Commands validate against state and emit events; handlers must not write state directly.** If the read side is allowed to change the truth, there are two truths.
- **Snapshots and projections are disposable; the events are the truth.** You should be able to delete a projection and rebuild it.
- **Never edit stored events; convert them when you read.** Upcasters accumulate, which is part of the cost.
- **Make every consumer idempotent.** Delivery is at-least-once, and a replay is a delivery of everything again, as the doubled counter showed.

## Exercise

Add a `daily_seen` table keyed by `(stream_id, version)` and make `daily_totals` idempotent by using it. Rerun the double replay. Should the total stay at 2,048,518?

## What's next

The next post is "Messaging and event-driven architecture". Here events stayed inside one database. Once they travel between services, duplicates and ordering stop being details and become architecture problems.
