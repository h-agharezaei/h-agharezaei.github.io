+++
date = '2027-06-10T10:00:00+03:30'
draft = false
title = 'Capacity estimation'
description = "Capacity estimation with Go and Postgres: peak QPS, Little's law, bytes per row, cache hit rates, the queueing knee, a server count and a tornado table."
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "capacity-planning", "queueing", "performance", "go"]
cover = { image = "/images/covers/ds-capacity-estimation.png", alt = "Capacity estimation", hiddenInSingle = true }
+++

Imagine a launch is two weeks away and someone asks the simple question: how many servers do we need? Nobody knows. Some people say "ten, to be safe", others say "we will see on the day". Both are guesses. There is a better way, and it needs only arithmetic and a few cheap measurements.

This is called {{< term "capacity-planning" "capacity planning" >}}. The goal is not a precise answer. The goal is the right order of magnitude: is it 5 servers or 500, 15 GB of data or 15 TB? Within 2x of the truth is already a good result. One lesson from this post, as a warning: a row of an orders-like table whose columns add up to about 39 bytes took 128.5 bytes in Postgres, once its header and indexes were counted. That is 3.3 times the naive guess. Estimates that skip this step are wrong by a lot.

The [previous post](/posts/ds-deployment-strategies/) shipped a change safely. This one asks how many machines that change needs. We will go through traffic, storage, memory, bandwidth and queueing, and then put everything into one small model.

> Honest labelling: the traffic numbers and prices are invented. The queue and cache runs are seeded Go simulations, so they reproduce exactly. The memory and Postgres numbers were measured on my laptop (one machine, loopback). I show counts and bytes, no timings, and I did not measure any server's requests per second. I re-ran every demo with Go 1.27 and the Postgres part on a throwaway PostgreSQL 18.3; where a number differs from the original run, I say so.

## Traffic: from users to peak

Our invented service has 2,000,000 daily active users. Each user makes 20 requests per day and places 5 orders per month. At the busiest time, the load is 5 times the average (the "peak factor"). A request spends 80 ms in the service on average.

Step by step, with units:

1. Average rate: 2,000,000 users × 20 requests/user/day = 40,000,000 requests/day. One day has 86,400 seconds, so 40,000,000 ÷ 86,400 ≈ **463 requests/s**.
2. Peak rate: 463 × 5 = **2,315 requests/s**. We size for this number, not for the average, because the system must survive the busiest moment.
3. Concurrency: this is where {{< term "littles-law" "Little's law" >}} helps. It says L = λ × W: the number of requests in the system (L) equals the arrival rate (λ) times the time each one stays (W). So 2,315 requests/s × 0.080 s ≈ **185 requests in flight** at peak.
4. Order writes: 2,000,000 users × 5 orders/month = 10,000,000 orders per month. With a 30-day month that is 10,000,000 ÷ (30 × 86,400 s) ≈ **3.9 orders/s** on average.
5. Rows after one year: 2,000,000 × 5 × 12 months = **120 million**.

`go run . model` prints these (the first five lines of its output):

```
avg QPS            463
peak QPS (x5)     2315
Little L=lambda*W  185 requests in flight at peak (W=80 ms)
order writes/s     3.9 average
rows after 1 year  120 million
```

The 185 matters in practice. It means you need a connection pool of a few hundred connections, not thousands. See [connection pooling](/posts/db-connection-pooling/).

## Storage: measure bytes per row

For storage, the naive way is to add up the column sizes. I wanted to see how wrong that is, so I created an orders-like table with a primary key and two more indexes on a throwaway Postgres 18.3, filled it with generated rows, and asked Postgres how big it is. It does this at 20,000 rows and again at 100,000:

```
n=20000   heap 1417216  total 2998272  bytes/row 149.9
n=100000  heap 7069696  total 12845056 bytes/row 128.5   (heap 70.7 + indexes 57.4)
```

"Heap" is the table's own data, and "total" includes the three indexes and some small bookkeeping files. The 39 bytes of the naive guess are four 8-byte values plus a short status text ("shipped" is 7 bytes). According to the Postgres docs, every row in the heap carries a header of about 23 bytes, plus a line pointer and some alignment padding, and the [indexes](/posts/db-indexes-btree-explain/) are the rest. The row itself, measured with `pg_column_size`, averaged 66.0 bytes. In the heap each row costs 70.7 bytes, the rest being page and row bookkeeping, and the three indexes add 57.4 more.

Two lessons from the output. First, you can extrapolate: 100 million rows at 128.5 bytes is about 12.9 GB per copy of the data. That is a floor, since index trees get deeper as they grow. Second, do not extrapolate from a tiny sample. The first 20,000 rows cost more per row (149.9 bytes) than the full 100,000 (128.5), probably because the index pages are less full early on. I did not dig into the reason, but it is a good reason not to size from a small sample.

## Memory: working set and cache

Traffic and storage were the easy parts. Memory is harder, because access is rarely uniform: a small set of keys gets most of the requests. This pattern is described by a {{< term "zipf-distribution" "Zipf distribution" >}}, with a skew parameter `s`. The larger `s` is, the more the traffic concentrates on the few popular keys.

I simulated a Zipf workload (100,000 keys, 1,000,000 requests, seeded) in front of an {{< term "lru-cache" "LRU cache" >}}, which keeps the most recently used keys and evicts the oldest. The table shows the hit rate for a cache sized as a share of all keys:

```
zipf s           1%       5%      10%
1.1           66.6%    79.2%    84.1%
1.3           88.3%    94.0%    95.6%
1.6           98.3%    99.2%    99.3%
```

Read it by rows. If the workload has skew 1.1, a cache holding 1% of the keys answers 66.6% of requests. At skew 1.3 the same cache answers 88.3%. So the skew `s` is the assumption that decides everything. Measure the real skew of your traffic before you size a cache. In my experience this is the most-guessed number in a capacity plan.

Memory also goes to clients. I measured the idle cost of a goroutine and of a loopback connection in Go on this machine (it depends on the Go version and the platform):

```
 10000 idle goroutines: StackInuse + 2.01 KB each
100000 idle goroutines: StackInuse + 2.18 KB each
2000 loopback connection pairs: heap +646 B, Sys +1049..1171 B per pair
```

That is the output of the original run. In the re-run with Go 1.27 the same demo printed 2.01 KB and 2.17 KB per goroutine and 646 B heap and 918 B Sys per connection pair, so these figures move a little from run to run and I would only trust them to about this precision. The connection figure counts only the Go runtime. Kernel socket buffers are extra. The file descriptor limit (`ulimit -n`) was 1048576 and I stayed far below it.

## Bandwidth depends on the wire format

How big is a message on the wire? I encoded the same order with 3 items in three ways: JSON, Go's gob, and a compact layout of my own with variable-length integers ("varint"). The varint layout is similar in spirit to protobuf but it is not protobuf.

```
one order (3 items): json=241 B, gob=240 B (fresh encoder, includes type info), varint=60 B
100 orders streamed: json=24419 B (244/order), gob=7513 B (75/order), varint=6224 B (62/order)
gzip: one json order 241 -> 168 B; the 100-order json batch 24419 -> 3982 B (6.1x)
```

Gob looks no better than JSON for one order, because a fresh encoder sends its type description once. Over a stream of 100 orders that cost is paid once, and gob drops to 75 bytes per order. The varint layout is the smallest in both cases. Gzip helps a lot on a repetitive batch (24419 down to 3982 bytes, 6.1 times smaller) and much less on one small payload (241 down to 168 bytes). The original run showed 3884 bytes (6.3 times) and 171 bytes for gzip; those two numbers depend on the compression library, and the numbers above come from Go 1.27.

## Queueing: why not run at 95%

Here is the part that surprises people the most. A server at 95% utilisation sounds efficient. It is a disaster, because of queues.

For a simple queue (called M/M/1: random arrivals, random service times, one server), the mean time a request spends in the system is W = 1/(μ − λ), where μ is the service rate and λ the arrival rate. I measure time in units of the mean service time. The table compares this formula with a seeded simulation of 2 million requests, for the mean (W) and for the 99th percentile (p99):

```
util    W formula      W sim  p99 formula      p99 sim
0.50         2.00       2.00          9.2          9.2
0.70         3.33       3.33         15.4         15.4
0.80         5.00       4.99         23.0         23.1
0.90        10.00       9.92         46.1         45.5
0.95        20.00      19.39         92.1         87.1
0.99       100.00      86.39        460.5        350.6
```

At 50% utilisation a request spends 2 service-times in the system (1 being its own service). At 80% it is 5, at 90% it is 10 and at 95% it is 20. The simulation matches the formula well until 90%. At 99% the simulation has not converged (waits are correlated, so 2 million requests are not enough), so trust the formula there.

The shape is what matters: latency is almost flat until about 70-80% and then explodes. That is why a {{< term "utilization" "utilization" >}} target of 50-70% is a sensible default, and why you need {{< term "load-shedding" "load shedding" >}} when you cross it. Rejecting some requests early is better than letting every request wait. See also [circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/).

A second comparison. Take four servers, each of rate 1, sharing one queue (this is the M/M/4 model, solved with the Erlang C formula), and compare them with one server of rate 4. Both have the same total capacity and the same arrivals:

```
util      4x slow F  4x slow sim    1x fast F
0.50          1.087        1.087        0.500
0.80          1.746        1.751        1.250
0.90          2.969        2.971        2.500
```

At 80% utilisation, mean time in the system is 1.75 for the four slow servers and 1.25 for the one fast server. In this model one fast machine beats four slow ones at equal total capacity, because a request never waits while the fast server is idle. (Several small servers still have other advantages, such as failure isolation.)

Queues are not the only trap. {{< term "tail-latency" "Tail latency" >}} gets worse with fan-out. If one user request makes 100 calls and each call is slow 1% of the time, the chance that at least one is slow is 1 − 0.99^100 = 0.634. The simulation (100,000 requests) gave 0.6316, close to the formula. So even a rare slowness becomes the normal case for the user.

## The model and a tornado

Now we can put it together. The model needs one more assumption that I did not measure: how many requests per second one server can handle. I assumed 800 requests/s at 100% load. With a target utilisation of 60% and one spare server:

1. Usable capacity per server: 800 × 0.60 = 480 requests/s.
2. Servers for peak: 2,315 ÷ 480 = 4.82, rounded up to 5.
3. Add one spare: 5 + 1 = **6 servers**.
4. Data: 120 million rows × 128.5 B = 15.4 GB per copy, and 46.3 GB with 3 copies.
5. Cost: with the invented prices in the code (100 USD per server-month and 0.10 USD per GB-month), 6 × 100 + 46.3 × 0.10 ≈ **605 USD/month**.

```
servers  ceil(2315 / (800*0.60)) + 1 = 6
DB size  15.4 GB per copy (120M rows x 128.5 B), 46.3 GB with 3 copies
cost     605 USD/month  (INVENTED prices)
```

The model also prints a peak egress of 4.7 MB/s, assuming 2 KB responses (an invented size).

Which input matters most? A "tornado" table answers that: move one input at a time from a low to a high value, keep the others at default, and see how the number of servers changes:

```
DAU 1M..4M                    4 .. 11
requests/user/day 10..40      4 .. 11
peak factor 3..10             4 .. 11
per-server QPS 400..1600     11 ..  4
target utilisation 0.5..0.8   7 ..  5
bytes/row 64..256             6 ..  6 (but DB size 7.7..30.7 GB)
```

Demand (users, requests per user, peak factor) and per-server capacity each move the answer by 2.8 times (4 to 11 servers). The utilisation target moves it by 1.4 times. Bytes per row does not change the server count at all, but it changes the database size from 7.7 to 30.7 GB. The largest input that I did not measure is per-server QPS, so that is the first number I would go and measure.

## Validate it, and keep doing it

A model is a hypothesis. Test it with a load test and find the point where latency starts to climb, the "knee". Tools like k6, wrk, vegeta and hey exist for this; I only name them and did not run them here. The targets come from your [SLOs](/posts/eng-sli-slo-error-budgets/).

Then repeat: forecast from real growth, keep N+1 or N+2 spare machines, and remember that autoscaling has limits too. The well-known "latency numbers every programmer should know" list (attributed to Jeff Dean and Peter Norvig) is a useful picture of how hardware behaves, but its figures date, so measure your own.

## Common estimation mistakes

- **Sizing for the average.** Peak sizes the system, not the average. The peak-to-average ratio is an assumption, so check it against real traffic.
- **Adding up column sizes.** Estimates of data size must use measured bytes per row, indexes included.
- **Planning for 90% or more utilisation** of anything with a queue. The table above shows what happens to latency.
- **Guessing cache sizes.** The hit rate depends on the skew, and the skew is a property of your traffic, not of your cache.

## Exercise

Put your own service into the model and find the top two tornado entries. How would you measure each of them cheaply?

## What's next

The next post is "Case studies: a rate limiter and a notification system". It applies this arithmetic to two classic design questions.
