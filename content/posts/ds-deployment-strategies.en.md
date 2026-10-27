+++
date = '2027-06-09T10:00:00+03:30'
draft = false
title = 'Deployment strategies: blue-green and canary'
description = 'Deployment strategies compared with Go runs on loopback: big-bang, rolling, blue-green and canary with automatic rollback, plus safe schema changes.'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "deployment", "canary", "blue-green", "go"]
cover = { image = "/images/covers/ds-deployment-strategies.png", alt = "Deployment strategies: blue-green and canary", hiddenInSingle = true }
+++

[The previous post](/posts/ds-modular-monolith-vs-microservices/) was about how many deployable pieces you have. This one is about how a piece reaches users. Every deploy is an experiment on production; the question is how many users the bad version can hurt before you notice: its {{< term "blast-radius" "blast radius" >}}. Related: [pipeline design](/posts/eng-ci-cd-pipeline-design/), [load balancers](/posts/net-load-balancer-l4-l7/).

> Honest labelling: this is Go 1.26 on one machine, loopback only. Backends are real HTTP servers behind a small weighted reverse proxy I wrote (`httputil.ReverseProxy`). The "bug" in v2 is deterministic: about 5% of request ids get a 500. I show counts, not timings.

## Big-bang and rolling

Big-bang replaces everything at once. 10,000 requests, all served by v2:

```
big-bang, 5% bug     requests=10000 errors=502 | v2: 10000 req 502 err
```

A {{< term "rolling-update" "rolling update" >}} replaces 4 instances one by one, after every 2,000 requests, if the new one passes its {{< term "health-check" "readiness check" >}}. Two bad versions:

```
rolling, v2 fails readiness           requests=10000 errors=0   | v1: 10000 req
rolling, v2 5% bug passes readiness   requests=10000 errors=244 | v1: 5000 req 0 err | v2: 5000 req 244 err
```

If v2 cannot start, the rollout halts and users never notice. But a readiness check only asks "are you alive?". The subtle bug sailed through, and half of all requests hit v2. Rolling protects from crashes, not wrong behaviour.

## Blue-green

{{< term "blue-green-deployment" "Blue-green" >}} keeps the old fleet (blue) and starts a full new one (green); the proxy flips 100% at once.

```
servers running during the switch: 4 (normal: 2)
smoke test on green: 20 requests, 1 errors -> flip
alarm rule: 10 errors seen -> after 152 requests (10 errors); flip back
after rollback (next 1000)   requests=1000 errors=0 | v1: 1000 req 0 err
```

The cost is double capacity, here 4 servers instead of 2. The {{< term "smoke-test" "smoke test" >}} saw 1 error in 20 and let it pass, because 20 requests are too few for a 5% bug. The benefit: rollback is one atomic pointer swap, instant and without redeploying.

In-flight requests need care. I started 5 slow requests on blue, flipped, then shut blue down gracefully ({{< term "graceful-shutdown" "graceful shutdown" >}}, as in [this post](/posts/go-graceful-shutdown-workers/)):

```
during drain: in-flight on blue=5, new request -> v2 status 200
in-flight results (200 = finished, 0 = lost): [200 200 200 200 200], Shutdown error: <nil>
```

New traffic went to green and all 5 old requests finished.

## Canary with automatic analysis

A {{< term "canary-release" "canary" >}} grows 1%, 5%, 25%, 50%, 100%. After each step of 2,000 requests the code compares canary and baseline with a one-sided {{< term "fisher-exact-test" "Fisher exact test" >}}; I chose to roll back when p < 0.005. I used Fisher rather than a z-test because the normal approximation is poor with a handful of errors.

```
bad v2
step 1: weight=  1% canary n=  28 err= 0 | baseline n=1972 err=0 | p=1.0000 power(5% bug)=0.41 -> continue
step 2: weight=  5% canary n= 102 err= 5 | baseline n=1898 err=0 | p=0.0000 power(5% bug)=0.97 -> ROLLBACK
blast radius: 130 requests served by v2 (big-bang: 10000)
good v2
... step 4: weight= 50% canary n=1008 err=0 ... -> continue
step 5: weight=100% canary n=2000 err=0 -> PROMOTED
```

The bad version is stopped at step 2 with a blast radius of 130 requests instead of 10,000. Step 1 shows the catch: the test said "fine" with 28 canary requests. That is not evidence of health, it is low {{< term "statistical-power" "statistical power" >}}. The code computes it: with 20 canary requests out of 2,000, the chance of detecting a true 5% error rate is 0.26, and one error in 20 gives p = 0.01, not enough. About 59 canary requests give 80% power. (Routing is by hash, so step 1 got 28, not 20.) Assumptions: the baseline never fails; no correction for repeated looks; I built only an error-rate check, not a latency one.

## Shadow traffic and feature flags

{{< term "shadow-mode" "Shadow mode" >}} sends a copy of each request to v2 and only compares answers. 2,000 mirrored requests: 0 user-visible errors, 102 differing responses (first at request 12). A {{< term "feature-flag" "feature flag" >}} then separates deploy from release: ship the code dark, enable it per user group, switch it off without a deploy (a {{< term "kill-switch" "kill switch" >}}).

## Database changes

Old and new versions overlap in every strategy above, so the schema must work for both. This is a map-based simulation, not Postgres; the SQL steps are the usual ones and I did not run them.

```
WRONG: rename in one step while v1 is still running
  first error: column "name" does not exist
  v1 reads name      ok=0 errors=100
RIGHT: expand, dual-write, backfill, switch reads, contract
  1 expand (v1 live)                    name: ok=100
  2 v1 and v2 both live, v2 dual-writes name: ok=110 | full_name: ok=5 empty=105
  3 backfill done (105 rows)            name: ok=110 | full_name: ok=110
  4 reads switched to full_name         full_name: ok=110
  5 contract (drop name, later release) full_name: ok=110
```

This is {{< term "expand-contract" "expand/contract" >}}: add the column, {{< term "dual-write" "dual-write" >}}, {{< term "backfill" "backfill" >}}, switch reads, drop later. Consumers should be {{< term "tolerant-reader" "tolerant readers" >}}. See [zero-downtime migrations](/posts/db-zero-downtime-migrations/).

## Rollback or roll forward?

In my experience rollback is the right first move while it is cheap and safe, and {{< term "roll-forward" "roll forward" >}} wins once v2 has written data v1 cannot read or a migration dropped something. Watch the {{< term "sli" "SLIs" >}} of your [SLO](/posts/eng-sli-slo-error-budgets/) split by version, or a 1% canary hides in the noise. Argo Rollouts, Flagger, Spinnaker and Kubernetes Deployment strategies automate this; I know them only from documentation.

## A few things to watch

- Readiness is not correctness; a rollout needs real metrics.
- Small canaries are blind: compute the sample size you need.
- Make every migration backward compatible before shipping code that needs it.
- Mirrored writes must not have side effects.

## Exercise

Add a latency check with a counted clock to the canary analysis, then try a bug that only affects 0.5% of requests and see how many requests you need.

## What's next

The next post is “Capacity estimation”.
