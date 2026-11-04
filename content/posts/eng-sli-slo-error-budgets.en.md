+++
date = '2027-05-10T10:00:00+03:30'
draft = false
title = 'SLIs, SLOs and error budgets'
contentType = 'tutorial'
description = 'SLI, SLO and error budget in Go: availability and latency SLIs, 99.9% budget maths, burn-rate alerts on a seeded incident, and why p99 beats the mean.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["sli", "slo", "error-budget", "sre", "software-engineering", "go", "alerting"]
cover = { image = "/images/covers/eng-sli-slo-error-budgets.png", alt = "SLIs, SLOs and error budgets", hiddenInSingle = true }
+++

A team argues in a meeting. One engineer says the service must be "99.9% available". Another says that is too strict, and a third asks what 99.9% even means: of what, over how long, measured where? Nobody has an answer, so the number stays a slogan.

The fix is to turn "fast and up" into something you can measure and then agree on. That takes three terms. An {{< term "sli" "SLI" >}} (service level indicator) is the measurement: for example, "the share of requests that did not fail". An {{< term "slo" "SLO" >}} (service level objective) is the target for that measurement over a period: "at least 99.9% over 30 days". And the {{< term "error-budget" "error budget" >}} is the amount of failure the target still lets you have. Once you can see the budget, "can we ship this risky change?" becomes a question with an answer.

In this post I build these ideas in a small Go demo and look at the part that surprised me most: how to alert on the budget without being paged all night for noise. The previous post, [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/), was about shipping changes quickly and safely. This one is about how to tell whether the service is still healthy afterwards. Related reading: [Observability for JetStream](/posts/nats-jetstream-observability/), [Profiling Go with pprof](/posts/go-profiling-pprof/), [Case study: finding and fixing a slow query](/posts/db-slow-query-case-study/) and [Timeouts, retries and backoff](/posts/ds-timeouts-retries-backoff/).

> I re-ran everything below with Go 1.27.3 and `go test -race` passes (the original run used Go 1.26). The demo is a local example: a handler on loopback with seeded failures and an injected clock, so the numbers are repeatable. The Prometheus rules near the end are **not run**, because I do not have `promtool` here.

## SLI, SLO and SLA

Here are the three terms side by side, with one example each:

| Term | Meaning | Example |
|---|---|---|
| SLI | a measured ratio: good events divided by all events | 99.37% of requests were not 5xx |
| SLO | an internal target for an SLI over a window of time | 99.9% over 30 days |
| SLA | a contract with consequences if you miss it | refund if below 99.5% |

The SLI is a fact (what happened). The SLO is a goal you set for yourself. The SLA is a promise to a customer, usually looser than the SLO so that you notice trouble before you owe anybody money. This post is about the first two and the budget they create.

## Recording the SLIs

An SLI needs raw counts. In the demo, a small middleware (code that wraps the handler) sees every request and adds it to a window of one minute. For each minute it keeps three numbers: the total, the "good" requests (status below 500) and the "fast" requests (finished within 300 ms).

To test it, the demo starts a handler on loopback and sends 3000 requests. The handler fails 0.5% of the time and has a slow tail: 3% of requests take 400 to 900 ms. The clock is fake. The handler "works" by moving the clock forward, so the run finishes instantly but the middleware measures the simulated time.

```text
simulated minutes: 103
total=3000 good=2981 fast(<=300ms)=2897
availability SLI = 0.9937
latency SLI      = 0.9657
```

The 3000 requests spread over 103 simulated minutes. 2981 of them were good, so the availability SLI is 2981 / 3000 = 0.9937. 2897 were fast, so the latency SLI is 0.9657. They are two different questions about the same traffic: "did it work?" and "was it quick enough?".

Which SLIs to pick depends on what the service does. This is my opinion: a request/response service needs availability and latency; a data pipeline needs freshness ("the data is less than 5 minutes old"); a storage system needs durability.

## The budget

Now suppose the SLO is 99.9% over 30 days. The remaining 0.1% is the error budget. Thirty days is 30 × 24 × 60 = 43,200 minutes, and 0.1% of that is 43.2 minutes. So a 99.9% SLO allows about 43 minutes of complete outage per month, and not a minute more. The demo computes this table with `(1 - SLO) * 43200`:

```text
99.00   %   432.00 min
99.90   %    43.20 min
99.95   %    21.60 min
99.99   %     4.32 min
```

Look at how fast it shrinks. Each extra "9" divides the budget by ten. Going from 99.9% to 99.99% takes you from 43 minutes to a bit over 4, and every minute of a bad deploy counts against it.

You can also count the budget in requests instead of minutes. I assumed 100 requests per minute, so 4,320,000 requests in 30 days. At 99.9%, the budget is 4,320 bad requests. If 1,500 have already failed, 2,820 remain, which is 65.3% of the budget.

The last idea is the **burn rate**. It tells you how fast you are spending the budget. Divide the error rate you see by the error rate the SLO allows:

- A steady 0.1% error rate is exactly what a 99.9% SLO allows. That is burn rate 1: the budget lasts exactly the 30 days.
- A 1.44% error rate is 14.4 times the allowed rate. That is burn rate 14.4: the 30-day budget is gone in 30 days / 14.4, which is 50 hours.

Burn rate is useful because it answers "how bad is this right now?" in a way that does not depend on how long the window is.

## Alerting on burn rate

The simplest alert is "page me when the error rate over the last 5 minutes is above 0.1%". It sounds reasonable, and it is a bad alert. To see why, I built a seeded timeline of 5 days at 1000 requests per minute, with a baseline error rate of 0.03%, and three events:

- a **fast burn**: 5% errors for 30 minutes, starting at minute 1000;
- a **slow burn**: 0.3% errors from minute 3000 to 5399 (about 40 hours);
- a **blip**: 30% errors for one single minute, at minute 6500.

The simple 5-minute alert needs 5 errors in 5000 requests to fire. With the baseline, about 1.5 errors are expected in that window, so 5 happens by chance every now and then. That is noise, and it will wake somebody up.

The better approach comes from the Google SRE Workbook chapter on alerting on SLOs (I read it on sre.google). It recommends paging when 2% of the monthly budget burns in one hour (burn rate 14.4) or 5% in six hours (burn rate 6), and opening a ticket, not a page, for 10% in three days (burn rate 1). Each rule uses two windows, a long one and a short one that is one twelfth of it, and both must be over the limit. The long window says "this is serious"; the short window says "and it is still happening", so the alert also stops soon after the errors stop.

The demo runs all four rules on the timeline and prints the minutes at which each rule was firing:

```text
naive 5m >= 0.1%     38 firing periods: [453-455] [459-459] [700-700] [759-761] [1000-1033] [1077-1077] ...
page  14.4x 1h&5m     1 firing periods: [1017-1032]
page  6x    6h&30m    0 firing periods:
ticket 1x   3d&6h     2 firing periods: [4319-5667] [6500-6859]
```

Here is how to read it:

- **The naive alert** fired in 38 separate periods. Look at the first ones, `[453-455]`, `[459-459]` and `[700-700]`: they are all before the first real incident at minute 1000. They are baseline noise.
- **The 14.4x page** fired once, at minute 1017, and kept firing until minute 1032. To pass, the 1-hour window needs 1.44% errors, which is 864 errors out of 60,000 requests. The burn adds about 50 errors per minute, so the rule needs about 17 minutes to cross that line, which matches. It stopped three minutes after the burn ended at 1029, because the 5-minute window still held two bad minutes until then.
- **The 6x page** never fired. The slow burn is 0.3%, which is burn rate 3, and that is below 6. This is right: it is not an emergency.
- **The 1x ticket** fired twice. The slow burn does use the budget, just not urgently, so a ticket is the correct response. Two caveats: my code reports nothing until a full 3-day window exists, so minute 4319 is the earliest possible start. And the second period, starting at 6500, is the tail of the slow burn plus the blip lifting the 6-hour window.

The same idea, written as Prometheus rules (shown, **not run**). It assumes a counter named `http_requests_total` with a `code` label. The first two rules record the error ratio over 1 hour and over 5 minutes; the third is the page. I added the 5-minute rule to this snippet because the alert refers to it:

```yaml
- record: job:slo_errors:ratio_rate1h
  expr: sum(rate(http_requests_total{code=~"5.."}[1h])) / sum(rate(http_requests_total[1h]))
- record: job:slo_errors:ratio_rate5m
  expr: sum(rate(http_requests_total{code=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
- alert: ErrorBudgetFastBurn
  expr: job:slo_errors:ratio_rate1h > 14.4*0.001 and job:slo_errors:ratio_rate5m > 14.4*0.001
  labels: {severity: page}
```

## When the budget is spent

My opinion: an SLO that nobody acts on is decoration. Agree in advance what happens when the budget runs out. A reasonable agreement is: slow down feature releases and spend the time on reliability until the budget recovers. And when plenty of budget is left, take more risk and ship faster. That is the whole point of having a budget: it turns the old argument between "ship" and "be careful" into a number both sides accepted beforehand.

## Averages hide tails

So far the latency SLI was "the share of requests under 300 ms". Why not just track the average latency? The demo generates 200,000 latencies with a 1.5% slow tail and shows what the average says:

```text
mean=48.8 ms  p50=40.3  p99=551.9  p99.9=860.8
fraction <= 300ms = 0.9853
```

`p50` is the median: half the requests are faster. `p99` is the value 99% of requests beat. A {{< term "percentile" "percentile" >}} like this looks at the slow end directly. Here the mean is 48.8 ms and looks healthy, while `p99` is 551.9 ms: one user in a hundred waits more than half a second. An SLO of "99% of requests under 300 ms" fails on this data (only 98.53% are under 300 ms). An SLO of "mean under 100 ms" would pass and hide the problem.

There is one more subtlety. Prometheus does not keep every latency; it keeps counts per bucket (for example "how many requests took under 100 ms") and estimates the percentile by assuming values are spread evenly inside a bucket. I reimplemented that interpolation in the demo and compared it to the exact answer, with two bucket layouts:

```text
buckets [100 1000]: p99 estimate=386.5 exact=551.9 error=-30.0%
buckets [10 25 50 100 250 500 1000]: p99 estimate=570.4 exact=551.9 error=+3.4%
```

With two coarse buckets the estimate is 30% too low. With seven buckets it is within 3.4%. The practical rule: put a bucket boundary exactly at your SLO threshold (here 300 ms). Then "what fraction is under 300 ms" is an exact count and needs no estimation at all.

## Where SLOs mislead

- **Measure where users are.** Use the load balancer or the client, not only the app. If the app is down, it cannot report that it is down.
- **Count a timed-out request as bad.** And remember that retries can multiply the load on a struggling service; see the post on timeouts and retries.
- **Low traffic makes ratios jumpy.** If a service gets ten requests an hour, one failure is 10%. Use longer windows.
- **100% is the wrong target.** It leaves no budget, so every deploy would break the promise.

## Exercise

Add a 6x rule over 6 hours and 30 minutes to the Prometheus YAML. Then change the timeline in the demo so that only that rule fires. Hint: burn rate 6 against a 99.9% SLO means an error rate of 0.6%.

## What's next

The next post is "Blameless postmortems". When the budget burns, the incident still needs a write-up that teaches the team something.
