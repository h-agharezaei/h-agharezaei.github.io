+++
date = '2027-05-10T10:00:00+03:30'
draft = false
title = 'SLIs, SLOs and error budgets'
description = 'SLI, SLO and error budget in Go: availability and latency SLIs, 99.9% budget maths, burn-rate alerts on a seeded incident, and why p99 beats the mean.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["sli", "slo", "error-budget", "sre", "software-engineering", "go", "alerting"]
cover = { image = "/images/covers/eng-sli-slo-error-budgets.png", alt = "SLIs, SLOs and error budgets", hiddenInSingle = true }
+++

The previous post, [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/), is about shipping safely. "Fast and up" is not a number, though. An {{< term "sli" "SLI" >}} measures it, an {{< term "slo" "SLO" >}} sets the target, and an {{< term "error-budget" "error budget" >}} is what the target lets you spend. Related: [Observability for JetStream](/posts/nats-jetstream-observability/), [Profiling Go with pprof](/posts/go-profiling-pprof/), [Case study: finding and fixing a slow query](/posts/db-slow-query-case-study/), [Timeouts, retries and backoff](/posts/ds-timeouts-retries-backoff/). Opinions are marked.

> Go 1.26, `go test -race` passes. The demo is a local example: a handler on loopback with seeded failures and an injected clock. Prometheus rules below are **not run** (no `promtool` here).

## SLI, SLO, SLA

| Term | Meaning | Example |
|---|---|---|
| SLI | a measured ratio, good events / total events | 99.37% of requests were not 5xx |
| SLO | an internal target for an SLI over a window | 99.9% over 30 days |
| SLA | a contract with consequences if missed | refund if below 99.5% |


## Recording the SLIs

A middleware records each request into a ring of one-minute windows: total, good (status below 500) and fast (under 300 ms). It takes the clock as a parameter, and the handler advances a fake clock by its simulated latency, so a run is deterministic. 3000 requests over a seeded handler (0.5% failures, 3% slow tail):

```text
simulated minutes: 103
total=3000 good=2981 fast(<=300ms)=2897
availability SLI = 0.9937
latency SLI      = 0.9657
```

Choose SLIs per service type (my opinion): request/response services use availability and latency; a pipeline uses freshness ("data is under 5 minutes old"); storage uses durability.

## The budget

Allowed downtime per 30 days is `(1 - SLO) * 43200` minutes, computed by code:

```text
99.00   %   432.00 min
99.90   %    43.20 min
99.95   %    21.60 min
99.99   %     4.32 min
```

In requests: I assumed 100 requests per minute, 4,320,000 per month, so 99.9% allows 4320 bad ones; after 1500, 2820 (65.3%) remain. The {{< term "burn-rate" "burn rate" >}} is observed error rate divided by allowed error rate: a steady 0.1% error rate is burn 1 and uses exactly the whole budget; 1.44% is burn 14.4 and empties it in 50 hours.

## Alerting on burn rate

A threshold such as "5-minute error rate above 0.1%" is noisy. The SRE Workbook chapter on alerting on SLOs (I read it on sre.google) recommends paging when 2% of the budget burns in an hour (burn 14.4) or 5% in six hours (burn 6), and a ticket for 10% in three days (burn 1). Each rule needs a long window and a short window (1/12 of the long one) both over the limit, so the alert also stops soon after the errors do.

I ran this on a seeded timeline: 5 days, 1000 requests per minute, baseline 0.03% errors, and three events: a fast burn (5% for 30 min at minute 1000), a slow burn (0.3% from 3000 to 5399) and a blip (30% for one minute at 6500).

```text
naive 5m >= 0.1%     38 firing periods: [453-455] [459-459] [700-700] [759-761] [1000-1033] [1077-1077] ...
page  14.4x 1h&5m     1 firing periods: [1017-1032]
page  6x    6h&30m    0 firing periods:
ticket 1x   3d&6h     2 firing periods: [4319-5667] [6500-6859]
```

The naive alert fired 38 times, many on baseline noise, before the real incident. The 14.4x rule paged once, at minute 1017, 17 minutes into the fast burn, and stopped about when it ended. The slow burn never paged (burn 3 is below 6) but produced a ticket. Caveats: my code reports nothing before a full 3-day window exists, so 4319 is the earliest possible; the second ticket period is the slow burn's tail plus the blip lifting the 6-hour window.

The same SLO as Prometheus rules (shown, not run; assumes a counter `http_requests_total` with a `code` label):

```yaml
- record: job:slo_errors:ratio_rate1h
  expr: sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))
- alert: ErrorBudgetFastBurn
  expr: job:slo_errors:ratio_rate1h > 14.4*0.001 and job:slo_errors:ratio_rate5m > 14.4*0.001
  labels: {severity: page}
```

## When the budget is spent

**My opinion:** an SLO nobody acts on is decoration. Agree in advance: when the budget is gone, slow feature releases and spend time on reliability until it recovers; when plenty is left, take more risk.

## Averages hide tails

Generated latencies (200,000 values, seed 3, 1.5% slow):

```text
mean=48.8 ms  p50=40.3  p99=551.9  p99.9=860.8
fraction <= 300ms = 0.9853
```

The mean looks healthy while 1 in 100 users waits over half a second. A latency SLO as "99% of requests under 300 ms" fails here; "mean under 100 ms" would pass. {{< term "percentile" "Percentiles" >}} from histogram buckets are estimates, because Prometheus-style interpolation assumes values are spread evenly inside a bucket. I reimplemented that interpolation:

```text
buckets [100 1000]: p99 estimate=386.5 exact=551.9 error=-30.0%
buckets [10 25 50 100 250 500 1000]: p99 estimate=570.4 exact=551.9 error=+3.4%
```

Put a bucket boundary at your SLO threshold, then "fraction under 300 ms" is exact.

## A few things to watch

- Measure at the edge users see (load balancer or client), not only inside the app.
- Count a timed-out request as bad; retries can multiply load, see the timeouts post.
- Low traffic makes ratios jumpy; use longer windows.
- 100% is the wrong target: it leaves no budget to change anything.

## Exercise

Add a 6x rule over 6h and 30m to the Prometheus YAML, then change the timeline so only that rule fires.

## What's next

The next post is "Blameless postmortems".
