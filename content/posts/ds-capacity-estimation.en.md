+++
date = '2027-06-10T10:00:00+03:30'
draft = false
title = 'Capacity estimation'
description = "Capacity estimation with Go and Postgres: peak QPS, Little's law, bytes per row, cache hit rates, the queueing knee, a server count and a tornado table."
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capacity-planning", "queueing", "performance", "go"]
cover = { image = "/images/covers/ds-capacity-estimation.png", alt = "Capacity estimation", hiddenInSingle = true }
+++

[The previous post](/posts/ds-deployment-strategies/) was about shipping a change safely. This one asks how many machines it runs on. {{< term "capacity-planning" "Capacity planning" >}} is arithmetic plus a few cheap measurements, and the goal is the right order of magnitude; within 2x is a good result.

> Honest labelling: the traffic numbers and prices are invented, the queue and cache runs are seeded Go simulations, and the memory and Postgres numbers were measured on my laptop (one machine, loopback). The load was high, so I show counts and bytes, no timings, and I did not measure any server's requests per second.

## Traffic: from users to peak

Invented service: 2,000,000 daily users, 20 requests per user per day, 5 orders per user per month, peak = 5x average, mean time in service 80 ms. The calculator gives:

```
avg QPS            463
peak QPS (x5)     2315
Little L=lambda*W  185 requests in flight at peak (W=80 ms)
order writes/s     3.9 average
rows after 1 year  120 million
```

{{< term "littles-law" "Little's law" >}}, L = λ × W, turns rate and latency into concurrency: about 185 requests in flight, so a pool of a few hundred connections, not thousands. See [connection pooling](/posts/db-connection-pooling/).

## Storage: measure bytes per row

Naive estimate: add the column sizes. I created an orders-like table (primary key plus two indexes) on a throwaway Postgres 18.3:

```
n=20000   heap 1417216  total 2998272  bytes/row 149.9
n=100000  heap 7069696  total 12845056 bytes/row 128.5   (heap 70.7 + indexes 57.4)
```

The columns add up to about 39 bytes (four 8-byte values plus a short status), so the real cost is 3.3x the naive number. According to the Postgres docs a heap tuple carries a header of about 23 bytes, plus a line pointer and alignment; the [indexes](/posts/db-indexes-btree-explain/) are the rest. Extrapolated linearly, 100M rows is about 12.9 GB per copy, a floor, since indexes deepen. The first 20k rows cost more per row (149.9) than the full 100k, so do not extrapolate from tiny samples.

## Memory: working set and cache

Access is rarely uniform. With a {{< term "zipf-distribution" "Zipf" >}} workload (100,000 keys, 1,000,000 seeded requests) I measured an {{< term "lru-cache" "LRU" >}} hit rate by cache size:

```
zipf s     1%      5%      10%
1.1       66.6%   79.2%   84.1%
1.3       88.3%   94.0%   95.6%
```

The skew `s` is the assumption that decides everything: caching 1% of keys gives 67% or 88%. Measure the real skew before sizing a cache.

Idle cost per client, measured in Go on this machine (depends on version and platform):

```
 10000 idle goroutines: StackInuse + 2.01 KB each
100000 idle goroutines: StackInuse + 2.18 KB each
2000 loopback connection pairs: heap +646 B, Sys +1049..1171 B per pair
```

The connection figure counts only the Go runtime; kernel socket buffers are extra. `ulimit -n` here was 1048576 and I stayed far below it.

## Bandwidth depends on the wire format

The same order with 3 items, encoded three ways:

```
one order: json=241 B, gob=240 B (fresh encoder), varint=60 B
100 orders streamed: json=244/order, gob=75/order, varint=62/order
gzip of the 100-order JSON batch: 24419 -> 3884 B (6.3x)
```

Varint here is my own protobuf-like layout, not protobuf. Gzip helps a lot on a repetitive batch, much less on one small payload (241 to 171 B).

## Queueing: why not 95%

For an M/M/1 queue the mean time in system is W = 1/(μ-λ). In units of the mean service time, formula against a seeded simulation of 2M requests:

```
util    W formula   W sim   p99 formula   p99 sim
0.50       2.00      2.00       9.2          9.2
0.80       5.00      4.99      23.0         23.1
0.90      10.00      9.92      46.1         45.5
0.95      20.00     19.39      92.1         87.1
0.99     100.00     86.39     460.5        350.6
```

At 99% the simulation has not converged (correlated waits), so trust the formula there. Latency is flat until about 70-80% and then explodes. That is the reason for a {{< term "utilization" "utilization" >}} target of 50-70% and for {{< term "load-shedding" "load shedding" >}} when you cross it, see [circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/).

Four servers of rate 1 sharing a queue (Erlang C) against one server of rate 4, at 80%: 1.75 against 1.25. One fast machine beats four slow ones at equal total capacity.

{{< term "tail-latency" "Tail latency" >}} amplifies with fan-out: 100 calls, each slow 1% of the time, give 1 - 0.99^100 = 63.4%; the simulation gave 63.2%.

## The model and a tornado

Assumed per-server capacity: 800 requests/s at 100% (not measured here), target 60%, one spare:

```
servers  ceil(2315 / (800*0.60)) + 1 = 6
DB size  15.4 GB per copy (120M rows x 128.5 B), 46.3 GB with 3 copies
cost     605 USD/month  (INVENTED prices)
```

One input moved at a time (low..high, servers needed):

```
DAU 1M..4M                    4 .. 11
requests/user/day 10..40      4 .. 11
peak factor 3..10             4 .. 11
per-server QPS 400..1600     11 ..  4
target utilisation 0.5..0.8   7 ..  5
bytes/row 64..256             6 ..  6 (but DB size 7.7..30.7 GB)
```

Demand and per-server capacity move the answer 2.8x; the utilisation target 1.4x. The biggest unmeasured input is per-server QPS.

## Validate and keep doing it

A model is a hypothesis. Load-test it with k6, wrk, vegeta or hey (I only name them) and find the knee. Targets come from [SLOs](/posts/eng-sli-slo-error-budgets/). Then repeat: forecast from real growth, keep N+1 or N+2 headroom, and remember autoscaling has limits. The well-known "latency numbers every programmer should know" list (attributed to Jeff Dean and Peter Norvig) is a useful shape of the hardware, but its figures date; re-measure.

## A few things to watch

- Peak, not average, sizes the system; peak-to-average is an assumption to check.
- Estimates of data size must use measured bytes per row, indexes included.
- Never plan for 90%+ utilisation of anything with a queue.
- Cache sizing depends on skew; in my experience it is the most guessed number.

## Exercise

Put your own service into the model and find the top two tornado entries. How would you measure each cheaply?

## What's next

The next post is "Case studies: a rate limiter and a notification system".
