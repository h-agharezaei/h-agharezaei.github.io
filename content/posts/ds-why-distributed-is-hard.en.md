+++
date = '2027-04-15T10:00:00+03:30'
draft = false
title = 'Why distributed systems are hard'
description = 'Why distributed systems are hard: partial failure, retries, clock skew and slow nodes, shown with seeded Go simulations and one real loopback demo.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "go", "partial-failure", "clocks", "failure-detection"]
cover = { image = "/images/covers/ds-why-distributed-is-hard.png", alt = "Why distributed systems are hard", hiddenInSingle = true }
+++

A client calls `Withdraw(10)` on a bank service and gets a timeout. Did the money move? From the client's side there is no way to know. Maybe the request never arrived. Maybe the server crashed before it did anything. Maybe the server did everything right and only the reply got lost on the way back. The client sees the same thing in all three cases: silence.

That is the core of why distributed systems are hard. When one program runs on one machine, a function call either returns or the whole program dies, and you always know where you stand. When two machines talk over a network, one of them can fail while the other keeps running, and the network itself can lose or delay messages. The caller is left guessing.

I have used queues, replicas and RPC for years, and most of my worst bugs came from a few facts like this one, so this series starts by naming them. Earlier posts touched them from one side: [idempotency in JetStream](/posts/nats-jetstream-idempotency/), [the outbox pattern](/posts/go-outbox-pattern-nats/) and [replication](/posts/db-replication-streaming/). Here I want to put the whole map in one place, and make each problem visible with a small program.

> Honest labelling: sections 1, 2, 4 and 6 are **simulations**. They run in one process, with seeded randomness, so they print the same numbers every time. A simulated network is not a real one, so the numbers show the shape of each problem, not production rates. Section 5 uses real processes and real TCP, but only on loopback (`127.0.0.1`, your own machine). I re-ran everything with Go 1.27 and the output below is what I saw; the original run used Go 1.26.

## 1. Partial failure

Let me start with the failure we began with. A call can end in four different ways, and the simulation draws one of them at random for each call:

- the request is lost on the way to the server (8% of calls);
- the server crashes before applying it (4%);
- the server applies the withdrawal, but the reply is lost on the way back (15%);
- everything works (the rest).

On top of that, 2% of requests are duplicated by the network, so the server sees them twice. The program makes 1000 calls to `Withdraw(10)` with a fixed seed. For each outcome it prints how many calls ended that way, what the client sees, and whether money really moved:

```
outcome                          count  client sees   money moved
ok                                 702  reply         yes
request lost                        86  timeout       no
server crashed before applying      33  timeout       no
reply lost after applying          179  timeout       yes

timeouts: 298, requests applied by server: 897, replies received: 702
balance mismatch: client believes 7020 withdrawn, server withdrew 8970 (duplicated requests applied twice: 16)
```

Look at the middle column. Three different realities produce the same "timeout": 86 + 33 + 179 = 298 calls. The client cannot tell the first two (nothing happened) from the third (it did happen). This is {{< term "partial-failure" "partial failure" >}}: part of the system failed, the rest kept going, and the caller cannot see which part.

The last line is the damage. The client received 702 replies, so it believes 702 × 10 = 7020 was withdrawn. The server actually applied 897 requests (702 + 179 + 16 duplicates), so it withdrew 8970. The difference, 1950, is the 179 lost replies plus the 16 duplicates, ten each.

## 2. Retries without idempotency

The obvious fix for a timeout is to try again. The same simulation now retries each withdrawal up to 8 times until it gets a reply. It runs twice: once as is, and once with an {{< term "idempotency" "idempotency" >}} key. An idempotency key is a unique id the client attaches to the logical operation (here `w-0`, `w-1`, and so on, the same for every retry of one withdrawal). The server remembers the keys it has applied and ignores a second request with the same key.

```
no key  : logical withdrawals=1000 confirmed=1000 retries=338 server applied=1212 withdrawn=12120 expected=10000 extra=2120
with key: logical withdrawals=1000 confirmed=1000 retries=338 server applied=1000 withdrawn=10000 expected=10000 extra=0
```

Both runs tell every client "success", and both made exactly the same 338 retries. The difference is on the server. Without a key, a retry after a lost reply withdraws again, and a duplicated request does too, so the server applied 1212 requests and the customer lost 2120 more than they should have. With a key, the server applied exactly 1000 and the balance is exact.

So a retry is only safe when the operation can be repeated without harm. Later posts in the series come back to this idea again and again.

The demo also has a test, run with `go test -race`. It starts 8 goroutines that all retry withdrawals with keys against the same server, and checks that the server never applies more than 8 × 500 withdrawals, which is the number of different keys. It passes.

## 3. The well-known fallacies

Engineers keep making the same wrong assumptions about networks. There is a well-known list called the fallacies of distributed computing, usually credited to Peter Deutsch and colleagues at Sun, with James Gosling often named for the eighth (I am hedging on the exact attribution). The series returns to each row:

| Fallacy | Where it bites |
|---|---|
| The network is reliable | sections 1 and 2 |
| Latency is zero | section 6 |
| Bandwidth is infinite | big payloads, replication lag |
| The network is secure | trust between nodes |
| Topology doesn't change | membership, failover |
| There is one administrator | upgrades, versions |
| Transport cost is zero | serialisation, chatty APIs |
| The network is homogeneous | mixed clients and versions |

## 4. Clocks

A natural idea is to settle questions about order with timestamps: whoever has the later time wrote last. This fails because every machine has its own clock, and no two clocks are exactly the same.

First, a detail about one machine. Go's `time.Now()` holds two readings: a wall-clock reading (the date and time) and a {{< term "monotonic-clock" "monotonic" >}} reading, a counter that only moves forward and is meant for measuring durations. The wall clock can jump, for example when it is corrected, so you should not use it to measure how long something took. To see both readings, the demo prints the shape of `t.String()` with every digit replaced by `N`:

```
has monotonic reading: true
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN m=+N.NNNNNNNNN
has monotonic after Round(0): false
NNNN-NN-NN NN:NN:NN.NNNNNN +NNNN +NNNN
```

The `m=+...` part at the end is the monotonic reading. `Round(0)` is the documented way to strip it, and after that the value has only the wall clock. (The number of digits after the seconds can differ between runs, because Go drops trailing zeros. In my 1.27 run the fraction had five digits, in the original six.)

Across machines the problem is worse. The difference between two machines' clocks is called {{< term "clock-skew" "clock skew" >}}. It breaks the simplest conflict rule, {{< term "last-write-wins" "last write wins" >}}, where every write carries a timestamp and replicas keep the one with the highest. The simulation gives three nodes clocks with errors: n1 is exact, n2 runs 300 ms behind and n3 runs 500 ms ahead.

```
simulated clock offsets (ms): map[n1:0 n2:-300 n3:500]
true t=1000ms  write x="A" via n1  stamp=1000
true t=1100ms  write x="B" via n2  stamp=800
after replication (keep highest stamp): x="A"  <- B was written later but lost
true t=800ms  write x="C" via n3  stamp=1300
then an OLDER write from the fast node: x="C"
```

At real time 1000 ms, n1 writes `"A"` with stamp 1000. A hundred milliseconds later n2 writes `"B"`, but its clock is behind, so the stamp is only 800. Replicas keep the highest stamp, so `"A"` wins and the newer `"B"` is silently lost. Then n3 writes `"C"` at real time 800 ms, which is earlier than both, but its fast clock gives it the stamp 1300, so the oldest write wins over everything. No error appears anywhere. That is why a later post talks about logical clocks, which do not depend on the wall time.

## 5. A real failure, on loopback

Simulations are tidy, so here is the same problem with real processes. The demo starts a small server and a client as separate Go processes talking TCP on `127.0.0.1`. The server applies the withdrawal first (it writes the new balance to a file) and only then waits 3 seconds before replying, to play the part of a slow reply. The demo breaks it in three ways. Ports are masked as `PORT`:

```
A) nobody listening:
client error: dial tcp 127.0.0.1:PORT: connect: connection refused
B) server SIGKILLed mid-call (after it applied the withdrawal):
client error: EOF
   balance file on the server side: 90
C) server frozen with SIGSTOP (alive but silent), client deadline 800 ms:
client error: read tcp 127.0.0.1:PORT->127.0.0.1:PORT: i/o timeout
   balance file on the server side: 90
```

These are three real error messages, and each one means something different:

- **A.** Nothing is listening on the port. The client gets `connection refused` immediately. This is the clean case: nothing happened, and the client knows.
- **B.** The server is killed with `SIGKILL` while the client waits. The client sees only `EOF`, the connection closed. But the balance file says 90, so the money moved. The client has no way to know that.
- **C.** The server is frozen with `SIGSTOP`. The process is alive, the connection is open, and it simply does not answer. The only signal the client gets is its own {{< term "deadline" "deadline" >}} (800 ms): `i/o timeout`. The balance file says 90 here too: the server applied the withdrawal before it froze.

## 6. It is never just a crash

If a client cannot tell a dead server from a slow one, can a system at least detect dead nodes? The usual tool is a {{< term "failure-detector" "failure detector" >}}: every node sends a {{< term "heartbeat" "heartbeat" >}} (a small "I am alive" message) at a fixed interval, and a node is suspected dead when no heartbeat has arrived for longer than a timeout.

The simulation covers 60 seconds with a heartbeat every 100 ms. A heartbeat takes 10 ms plus a random extra (average 15 ms) to arrive, and 2% of them take 400 ms longer, as if the network hiccuped. There are three nodes: a healthy one, one 5 times slower (all its delays multiplied by 5), and one that dies at second 30. For each timeout the table shows how many times the failure detector wrongly suspected the healthy node and the slow node, and how long after its death it noticed the dead one:

```
false suspicions over 60 simulated seconds (heartbeat every 100 ms)
timeout   healthy  slow(5x)  dead-node detection delay
  150 ms      24       120      66 ms
  250 ms       0        15     166 ms
  500 ms       0         0     416 ms
 1000 ms       0         0     916 ms
 2000 ms       0         0    1916 ms

requests with a 100 ms deadline that time out: healthy 2.1%, slow(5x) 52.5%
```

Read the table row by row. With a 150 ms timeout, even the healthy node is wrongly suspected 24 times, and the slow node 120 times, but the dead node is noticed fast. With 2000 ms nobody is wrongly suspected, but a dead node is only noticed after almost two seconds. (The detection delay is counted from the moment of death. It is a little less than the timeout, because the last heartbeat arrived shortly before the node died.) A short timeout flags healthy nodes; a long one finds death late. You cannot have both.

The last line is the worse news. Look at the 500 ms row: the slow node is never suspected, so the detector thinks it is fine. But I used the same delay model for requests, and with a 100 ms deadline more than half of them (52.5%) time out. The node is alive, answers heartbeats in time, and still fails most of its work. That is a {{< term "gray-failure" "gray failure" >}}: in my experience, harder to deal with than a clean crash, because nothing tells you to react.

## Where intuition fails

- A timeout means "unknown", not "failed". The operation may have happened (section 1, sections 5B and 5C), so never treat a timeout as proof it did not.
- Retries need idempotency. Without it, every retry after a lost reply repeats the operation, and the damage is multiplied (section 2).
- Do not order events across machines by wall time. Clocks disagree, and the wrong write can silently win (section 4).
- Health is not the same as heartbeat. A node can answer heartbeats on time and still be too slow to be useful (section 6).
- Simulations teach the shape of a problem. They do not replace testing on a real network, and the percentages above say nothing about real systems.

## Exercise

Change the seed and the loss rates in `pickFate` and run section 1 again. Does the mismatch between what the client believes and what the server did grow in a straight line with the loss rate? Then change the server so that its idempotency keys expire after a while, and watch the double withdrawals return when a retry arrives late.

## What's next

“CAP and PACELC, correctly” comes next: once the network can split, it names what you give up when it does.
