+++
date = '2027-05-23T10:00:00+03:30'
draft = false
title = 'Sagas or two-phase commit?'
description = 'Sagas or two-phase commit: a 2PC simulation that blocks, real PREPARE TRANSACTION on Postgres, and exhaustively checked order sagas with compensations.'
contentType = 'engineering'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "saga", "two-phase-commit", "transactions", "go", "postgres"]
cover = { image = "/images/covers/ds-saga-vs-2pc.png", alt = "Sagas or two-phase commit?", hiddenInSingle = true }
+++

A customer places an order. Three separate services have to act: stock must be reserved, the card must be charged, and a shipment must be created. Each service has its own database. The first two steps succeed and the third fails, because there is no courier for that address. Now the customer has been charged for something that will never ship, and one item of stock is reserved for nobody.

Inside one database this is easy: put the three steps in one transaction and let it roll back. Here there is no single database. The Raft log from [the previous post](/posts/ds-consensus-raft/) agrees on the order of writes for one group of nodes, but it does not cover three independent services. What we want is still **atomicity**: either all three steps happen, or none of them. And we want to know what each approach costs.

There are two classic answers:

- {{< term "two-phase-commit" "Two-phase commit" >}} (2PC) keeps atomicity. A coordinator asks every service whether it is ready, and only if all say yes does it tell them all to commit. The price is that services hold locks while they wait.
- A {{< term "saga" "saga" >}} gives up isolation. Each service commits its own step right away. If a later step fails, the earlier steps are undone by new actions that reverse them, called {{< term "compensating-transaction" "compensations" >}}, such as a refund. The price is that other readers can see the in-between states.

This post runs both in simulation, shows the real 2PC building block in PostgreSQL, and then checks a saga against crashes. For the single-database background, see [ACID](/posts/db-transactions-acid/); for related patterns, [the outbox](/posts/go-outbox-pattern-nats/), [idempotency](/posts/nats-jetstream-idempotency/) and [retries](/posts/ds-timeouts-retries-backoff/).

> The 2PC and saga parts are **simulations** in Go on one machine: a simulated clock, a simulated network (seeded latency of 1 to 3 ticks), and in-process services. I show counts and ticks, no timings. I re-ran them with Go 1.27, including `go test -race` (the original run used Go 1.26), and the outputs are the same. The Postgres part is a real PostgreSQL 18.3 on loopback, driven with `psql`; I re-ran it too.

## Two-phase commit in a simulation

The setup has a coordinator and three participants: inventory, payment and shipping. Each one locks a single row for the order. The protocol has two phases:

1. **Prepare.** The coordinator sends `PREPARE`. Each participant does its work, makes it durable, **keeps the lock**, and votes YES. A participant that cannot do its part votes NO and rolls back.
2. **Decide.** The coordinator writes its decision to its own log, then sends `COMMIT` (if all voted YES) or `ABORT` (if anyone voted NO). Participants release their locks when they hear it.

Here is the happy path, in the demo's own output. Times are simulation ticks, and each message takes 1 to 3 ticks:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping PREPARED (row locked, durable), votes YES
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping YES
t=  6  coord <- inventory YES
t=  6  coord LOG "COMMIT"
t=  8  inventory COMMIT, lock released after 5 ticks
t=  8  payment COMMIT, lock released after 7 ticks
t=  8  shipping COMMIT, lock released after 7 ticks
t=  9  coord <- inventory ACK
t= 10  coord <- shipping ACK
t= 11  coord <- payment ACK
t= 11  coord LOG "END"
decision: COMMIT lock ticks: map[inventory:5 payment:7 shipping:7]
```

The coordinator logs `COMMIT` at `t=6`, the moment the last YES arrives. Each participant's lock was held from its own `PREPARED` line until the decision reached it: 5 to 7 ticks. That is the cost of 2PC even when nothing goes wrong: during this window nobody else can touch those rows.

Now the same run where shipping votes NO:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping votes NO (rolls back, no lock kept)
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping NO
t=  4  coord LOG "ABORT"
t=  6  coord <- inventory YES
t=  6  inventory ABORT, lock released after 3 ticks
t=  6  payment ABORT, lock released after 5 ticks
t=  7  coord <- inventory ACK
t=  9  coord <- payment ACK
decision: ABORT lock ticks: map[inventory:3 payment:5 shipping:0]
```

Shipping's NO reaches the coordinator at `t=4`, and it logs `ABORT` at once, without waiting for inventory's vote. Shipping never kept a lock (`shipping:0`). Inventory and payment, which had voted YES, release their locks when the `ABORT` arrives. All three end in the same state: nothing happened. That is atomicity.

### The famous flaw: a coordinator that dies

The dangerous moment is after a participant has voted YES and before it hears the decision. At that point the participant cannot decide on its own. If it commits, the coordinator may have decided ABORT. If it aborts, the coordinator may have decided COMMIT. So it has to wait and keep its lock. In the next run the coordinator crashes after all three voted YES but before it writes a decision, and comes back at `t=60`:

```
t=  0  coord LOG "BEGIN"
t=  1  payment PREPARED (row locked, durable), votes YES
t=  1  shipping PREPARED (row locked, durable), votes YES
t=  2  coord <- payment YES
t=  3  inventory PREPARED (row locked, durable), votes YES
t=  4  coord <- shipping YES
t=  6  coord <- inventory YES
t=  6  coord CRASH: all voted yes, no decision written yet
t= 60  coord RESTART, reads its log [BEGIN]
t= 60  coord found BEGIN without a decision -> presumed ABORT
t= 60  coord LOG "ABORT"
t= 61  inventory ABORT, lock released after 58 ticks
t= 61  payment ABORT, lock released after 60 ticks
t= 63  shipping ABORT, lock released after 62 ticks
t= 63  coord <- inventory ACK
t= 64  coord <- payment ACK
t= 65  coord <- shipping ACK
t= 65  coord LOG "END"
(32 INQUIRE lines and their lost replies left out)
decision: ABORT lock ticks: map[inventory:58 payment:60 shipping:62] competing writes refused: 12 of 13
```

Read it as a timeline. Between `t=6` and `t=60` nothing happens, because the coordinator is down. During those 54 ticks all three participants sit holding their locks. They are not idle: every 10 ticks each one asks the coordinator "what was decided?" (the demo leaves these `INQUIRE` lines out of the printout and says so: 32 lines about the questions and their lost replies, since the coordinator is down). This waiting is called **blocking**. At `t=60` the coordinator restarts, reads its log, finds `BEGIN` with no decision, and takes the safe choice, abort. The locks were held for 58, 60 and 62 ticks, instead of 3 to 7. The last number counts a competing writer who wants the inventory row every 5 ticks: 12 of its 13 attempts were refused because of the lock.

If the coordinator had written `COMMIT` to its log before crashing, recovery works the other way. The demo run for that case (it also prints its full trace, which I leave out here) ends with the lines `coord RESTART, reads its log [BEGIN COMMIT]` and `coord found COMMIT without END -> resend COMMIT`. The decision is `COMMIT`, with the same lock times of 58, 60 and 62 ticks: the log is what turns "unknown" into a decision.

How long the locks last depends on how long the coordinator stays down. I ran the crash-before-decision case with four recovery times:

```
recover at t=10    decision=ABORT  lock ticks inventory=9    payment=11   shipping=11   refused=2/4
recover at t=60    decision=ABORT  lock ticks inventory=58   payment=60   shipping=62   refused=12/13
recover at t=200   decision=ABORT  lock ticks inventory=198  payment=202  shipping=202  refused=40/42
recover at t=1000  decision=ABORT  lock ticks inventory=1000 payment=1000 shipping=1000 refused=200/202
```

The lock time follows the downtime almost tick for tick, and the competing writer is refused almost every time (200 of 202 at the end). A coordinator outage becomes an outage of every row that is locked by a prepared transaction.

## The real building block in Postgres

Real databases expose the participant side of 2PC. In Postgres it is a {{< term "prepared-transaction" "prepared transaction" >}}: `PREPARE TRANSACTION` ends your session's involvement but keeps the transaction, with its locks, on disk. It needs `max_prepared_transactions` above 0; the instance I started had it at 5. One database stands in for two separate resource managers here, with an `account` table and a `stock` table.

```sql
begin; update account set balance = balance - 30 where id = 1;
       update stock set qty = qty - 1 where sku = 'A';
prepare transaction 'order-42';
```

After the session ended, the data still showed the old values (balance 100, qty 5), but the transaction existed, and so did its locks. This is the real output:

```
   gid    | has_ts | owner | database 
----------+--------+-------+----------
 order-42 | t      | app   | orders

 locktype |   rel   |       mode       | granted | no_session 
----------+---------+------------------+---------+------------
 relation | account | RowExclusiveLock | t       | t
 relation | stock   | RowExclusiveLock | t       | t
```

The first table is `pg_prepared_xacts`: a transaction named `order-42` that belongs to no session (`has_ts` only says that its prepare time is recorded). The second is `pg_locks`: both tables are locked, and `no_session = t` means no live session owns those locks. They belong to the prepared transaction now. A second session with `lock_timeout = '500ms'` that tries to update the same row:

```
ERROR:  canceling statement due to lock timeout
CONTEXT:  while updating tuple (0,1) in relation "account"
```

That is blocking, with a real database. Then I restarted Postgres on the same data directory: `order-42` was still listed. A brand-new session ran `COMMIT PREPARED 'order-42'`, and the values became 70 and 4, with no prepared transactions left. I also tried the other path: `ROLLBACK PREPARED` leaves the data unchanged.

So the promise of the prepare phase is real: after `PREPARE` the participant can no longer say no, even across a crash. And the cost is real too. According to the Postgres docs, `PREPARE TRANSACTION` "is not intended for use in applications"; it exists for an external transaction manager, and a forgotten prepared transaction keeps its locks and can hold back VACUUM. XA is the standard interface for such managers; I did not run one.

## Sagas: undo with a new action

A saga avoids all that by not holding locks across services. It splits the order into local steps, each with a compensation:

| Step | Compensation (undo) |
|---|---|
| reserve stock | release stock |
| charge the card | refund |
| create the shipment | (last step, nothing after it) |

Each step commits in its own service immediately. If a step fails, the saga runs the compensations of the earlier steps in reverse order. I wrote both common styles:

- {{< term "orchestration" "Orchestration" >}}: one coordinator, a state machine with a persisted log (`begin`, `done`, `failed`, `comp`), calls the steps in order and, on failure, the compensations. It is the 2PC coordinator's cousin, but it only drives calls; it does not hold locks.
- {{< term "choreography" "Choreography" >}}: no coordinator. Services react to events on a durable queue that delivers at least once. `ShippingFailed` makes payment refund; `PaymentRefunded` makes stock release.

The demo checks this property at the end of every run: **money is charged if and only if the order shipped, and stock is reserved if and only if it shipped.** In other words, no half-finished order is left behind. The cases cover every combination of: each step failing (or none), every call delivered twice or once, the first undo call of each service failing once or not, a crash before every single log write and every service call, and a second crash during recovery:

```
orchestration (persisted log) cases=3468 violations=0
choreography (events)     cases=2508 violations=0
```

Every case ends consistent. The checker can fire: a test makes a refund that does nothing, and the invariant flags it. It holds because of three rules in the code. Calls are **idempotent**: each service keeps the outcome per saga id, so a repeated call changes nothing. A compensation leaves a marker that makes the service refuse a late forward call for the same saga. And a compensation is retried until it succeeds. Note what is checked: the final state. During the run, the invariant is allowed to be broken, which brings us to the cost.

## What a saga lets you see

With 2PC, other readers cannot see the in-between state because the rows are locked. A saga has no such protection: after the charge step the money really is charged, even if the next step is about to fail and refund it. The demo shows this with a reader that looks at the order after every durable action while shipping fails:

```
reads=20  naive view saw 'charged'=7, final charged=false
PENDING view (status exposed only when the saga ends): reads that showed 'charged'=0
```

Seven of the twenty reads saw money that was later refunded. The countermeasures are application-level: show a `PENDING` state to the customer until the saga has ended (the second line: the pending view never showed "charged"), use a **semantic lock**, which is a flag on the order that makes other operations wait or fail while the saga runs, and prefer updates that commute. I implemented only the pending view.

## Comparison

| | 2PC | Saga |
|---|---|---|
| Atomicity | all or nothing | eventual, via compensation |
| Isolation | locks held during prepare | none, intermediate states visible |
| Availability | blocks on coordinator | keeps going, repairs later |
| Latency | two round trips with locks | no cross-service locks |
| Complexity | in the protocol | in your compensations |
| Coupling | needs 2PC-capable resources | any service with an API |

In my experience, sagas fit separate services and 2PC fits a few databases you control. According to its paper, Spanner runs 2PC between groups of replicas that are themselves replicated with Paxos, so the coordinator and the participants do not die as single machines; I only name it. TCC (try-confirm-cancel) is a way of structuring a saga where the "try" step is a reservation that is later confirmed or cancelled.

## Where sagas go wrong

- **Log your intent before the call and the outcome after it.** Crashes live in the gap between the two, and the saga needs the log to know where to resume.
- **A compensation is not a rollback.** A refund is a new fact that appears on the customer's statement, and an email that was sent cannot be unsent.
- **Put the step that cannot fail or cannot be undone last.** Then nothing after it needs a compensation.
- **Publish saga events through an outbox**, or you can lose them between the database write and the message.
- **The simulation is a simulation.** It has no network partitions and no real disks, and its services are in-process objects.

## What's next

The next post is "CQRS and event sourcing". A saga leans on a log of what happened. The next step is to make that log the source of truth for the data itself, and to read from separate views built from it.
