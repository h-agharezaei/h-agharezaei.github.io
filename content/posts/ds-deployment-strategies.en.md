+++
date = '2027-06-09T10:00:00+03:30'
draft = false
title = 'Deployment strategies: blue-green and canary'
description = 'Deployment strategies compared with Go runs on loopback: big-bang, rolling, blue-green and canary with automatic rollback, plus safe schema changes.'
contentType = 'tutorial'
categories = ["Distributed"]
series = ["Distributed Systems"]
tags = ["distributed-systems", "deployment", "canary", "blue-green", "go"]
cover = { image = "/images/covers/ds-deployment-strategies.png", alt = "Deployment strategies: blue-green and canary", hiddenInSingle = true }
+++

Imagine it is Friday afternoon and the new version has just gone out to all servers. Five minutes later the error graph starts to climb: one request in twenty is failing. Now there are two questions. How fast can we get the old version back? And how many users have already seen the errors?

Every deploy is a small experiment on production. We cannot make sure the new version is perfect, so the thing to control is how many users a bad version can hurt before we notice. This is its {{< term "blast-radius" "blast radius" >}}. In this post the same bug, 5% of requests failing, reaches 10,000 requests when everything is replaced at once, and only 130 requests when the rollout is staged and analysed automatically.

The [previous post](/posts/ds-modular-monolith-vs-microservices/) counted deployable pieces. This one asks how a new version of one piece gets to users. If you want more context: [pipeline design](/posts/eng-ci-cd-pipeline-design/) covers how a change gets to the point of being deployed, [feature flags](/posts/eng-feature-flags-trunk-based/) separate deploying from releasing, and [load balancers](/posts/net-load-balancer-l4-l7/) explain the proxy that splits traffic in the demos.

> How the demo works: it was written for Go 1.26 originally, and I re-ran it with Go 1.27 together with its tests (`go test -race`). The numbers below are what it printed. It runs on one machine, on loopback only. The backends are real HTTP servers behind a small weighted reverse proxy I wrote (`httputil.ReverseProxy`). The "bug" in v2 is deterministic: about 5% of request ids get a 500 error. I show counts, not timings.

I will go through four strategies. For each one I describe what happens over time, then show the run. In every run, 10,000 requests go through the proxy, and v2 is the bad version unless I say otherwise.

## Big-bang and rolling

**Big-bang** is the simplest strategy: stop v1, start v2, send everything to v2. Timeline: at the first request all traffic is on v2. If v2 is bad, all users are affected from the first moment.

```
big-bang, 5% bug     requests=10000 errors=502 | v2: 10000 req 502 err
```

All 10,000 requests were served by v2, and 502 of them failed, about 5%. This is the baseline to beat: 10,000 requests exposed.

A {{< term "rolling-update" "rolling update" >}} replaces the instances one at a time. In the demo there are 4 instances of v1 behind the proxy. After every 2,000 requests, one is replaced by a v2 instance, but only if the new instance passes its {{< term "health-check" "readiness check" >}}. A readiness check is a small endpoint (`/healthz` here) that answers "are you ready to take traffic?". Timeline over the five windows of 2,000 requests: 0 instances on v2, then 1, 2, 3 and 4 of 4.

Let me try two bad versions. In the first, v2 cannot start properly and fails its readiness check. In the second, v2 has the 5% bug but starts fine:

```
rolling, v2 fails readiness           requests=10000 errors=0   | v1: 10000 req
rolling, v2 5% bug passes readiness   requests=10000 errors=244 | v1: 5000 req 0 err | v2: 5000 req 244 err
```

The demo also prints `readiness failed on instance 1, rollout halted` after the first line.

In the first run, the rollout stops at the first instance. All 10,000 requests were served by v1 and users never notice. Rolling protects well against a version that crashes.

In the second run, the bug sails through. The readiness check only asks "are you alive?", and v2 is alive. As the rollout continued, v2 took half of all requests (5,000 of 10,000) and 244 of them failed. The lesson is that rolling protects from crashes, not from wrong behaviour. Nothing in this strategy looks at errors.

## Blue-green

{{< term "blue-green-deployment" "Blue-green" >}} keeps the old fleet (blue) running and starts a complete new fleet (green) next to it. When green is ready, the proxy flips all traffic from blue to green in one step. Timeline: blue serves everything, green starts and is checked, the flip happens, and if something is wrong, the flip goes back.

The run below starts green, sends 20 requests straight at it, flips, and then watches the errors. The alarm rule I chose is "flip back after 10 errors":

```
servers running during the switch: 4 (normal: 2)
smoke test on green: 20 requests, 1 errors -> flip
alarm rule: 10 errors seen -> after 152 requests (10 errors); flip back
after rollback (next 1000)   requests=1000 errors=0 | v1: 1000 req 0 err
```

Line by line:

- **4 servers instead of 2.** This is the cost of blue-green: double capacity while both fleets exist.
- **The smoke test.** A {{< term "smoke-test" "smoke test" >}} is a handful of quick requests that check the new version basically works. It saw 1 error in 20 and let the flip happen, because 20 requests are far too few to see a 5% bug reliably. We will return to this point in the canary section.
- **The alarm.** After the flip, 10 errors showed up within 152 requests, so the rule flipped traffic back.
- **After the rollback.** The next 1,000 requests all went to v1 with no errors.

The benefit of blue-green is that rollback is one atomic switch of a pointer: instant, with no redeploy. In this run, about 142 of the first 152 requests succeeded on v2, and the damage was limited to the time it took to notice.

There is one more detail: requests that were already running on blue when we flip. If we simply kill blue they are lost. In the demo I started 5 slow requests on blue, flipped to green, and then shut blue down with a {{< term "graceful-shutdown" "graceful shutdown" >}}, which stops accepting new requests but waits for the running ones to finish (more in [this post](/posts/go-graceful-shutdown-workers/)):

```
during drain: in-flight on blue=5, new request -> v2 status 200
in-flight results (200 = finished, 0 = lost): [200 200 200 200 200], Shutdown error: <nil>
```

While blue was draining, 5 requests were still in flight on it, and a new request went to v2 and got status 200. When the slow requests were released, all 5 finished with 200, and shutdown returned no error. Nobody lost a request.

## Canary with automatic analysis

The smoke test above missed a 5% bug because 20 requests are too few. A {{< term "canary-release" "canary" >}} fixes this by sending a small share of real traffic to the new version first, and growing it only while the numbers look fine. The name comes from the canary in a coal mine: the small thing that gets hurt first, to warn the rest.

Timeline in the demo: the canary gets 1%, then 5%, 25%, 50% and finally 100% of traffic. After each step of 2,000 requests, the code compares the error rate of the canary to the error rate of the baseline (v1). How do we decide whether a difference is real or just chance? I use a one-sided {{< term "fisher-exact-test" "Fisher exact test" >}}, which gives a p-value: the probability of seeing at least this many canary errors if canary and baseline were equally good. If p is below 0.005, the code rolls back. I chose Fisher over a z-test because the usual normal approximation is poor when there are only a handful of errors.

First the bad v2, then a good one (the good run is shown in full):

```
bad v2
step 1: weight=  1% canary n=  28 err= 0 | baseline n=1972 err=0 | p=1.0000 power(5% bug)=0.41 -> continue
step 2: weight=  5% canary n= 102 err= 5 | baseline n=1898 err=0 | p=0.0000 power(5% bug)=0.97 -> ROLLBACK
blast radius: 130 requests served by v2 (big-bang: 10000), after 4000 total requests
good v2
step 1: weight=  1% canary n=  28 err= 0 | baseline n=1972 err=0 | p=1.0000 power(5% bug)=0.41 -> continue
step 2: weight=  5% canary n= 102 err= 0 | baseline n=1898 err=0 | p=1.0000 power(5% bug)=0.97 -> continue
step 3: weight= 25% canary n= 494 err= 0 | baseline n=1506 err=0 | p=1.0000 power(5% bug)=1.00 -> continue
step 4: weight= 50% canary n=1008 err= 0 | baseline n= 992 err=0 | p=1.0000 power(5% bug)=1.00 -> continue
step 5: weight=100% canary n=2000 err=0 -> no baseline left, PROMOTED
```

How to read a step: `n` is how many requests each side got, `err` how many failed, and `p` the p-value. `power` I explain in a moment.

For the bad v2, step 1 sent 28 requests to the canary, saw no errors and continued. At step 2 the canary got 102 requests and 5 of them failed, against 0 errors in the baseline. The p-value is practically 0, so the code rolled back. In total v2 served 28 + 102 = 130 requests, compared with 10,000 for big-bang. The good v2 passed every step and was promoted at 100%.

Step 1 holds the catch. With 28 canary requests the test said "fine", and that is not evidence that v2 is healthy. It is low {{< term "statistical-power" "statistical power" >}}: the probability that the test would notice the bug if it were there. The `power(5% bug)` column shows it is only 0.41 at step 1 and 0.97 at step 2. The demo also computes this directly: with 20 canary requests out of 2,000, the chance of detecting a true 5% error rate is 0.26, and a single error in 20 gives p = 0.01, which is not below 0.005. About 59 canary requests are needed for 80% power. (Routing is by a hash of the request id, so step 1 got 28 requests, not exactly 1% of 2,000.)

These are the limits of my analysis: the baseline is assumed never to fail; I did not correct for looking at the data several times; and I built only an error-rate check, not a latency one.

## Shadow traffic and feature flags

Two more techniques reduce the blast radius even further.

{{< term "shadow-mode" "Shadow mode" >}} sends a copy of each real request to v2 and only compares the answers. The user always gets v1's answer. I mirrored 2,000 requests: 0 user-visible errors, but 102 responses differed (the first at request 12, where v1 answered 200 and v2 answered 500). So the bug was found without any user ever seeing it.

A {{< term "feature-flag" "feature flag" >}} separates deploying from releasing. You ship the new code switched off ("dark"), turn it on for one group of users, and if something goes wrong you turn it off again without a deploy. That last switch is called a {{< term "kill-switch" "kill switch" >}}.

## Database changes

All of the strategies above have a period in which the old and the new version run at the same time. That means the database schema has to work for both. This part is a simulation on a map, not Postgres. The SQL steps behind it are the usual ones, and I did not run them.

The task: rename the column `name` to `full_name`. First the wrong way, in one step while v1 is still running. Then the right way, in five steps:

```
WRONG: rename in one step while v1 is still running
  first error: column "name" does not exist
  v1 reads name      ok=0 errors=100 empty=0
  v2 reads full_name ok=100 errors=0 empty=0
RIGHT: expand, dual-write, backfill, switch reads, contract
  1 expand (v1 live)                 name: ok=100 err=0 empty=0 |
  2 v1 and v2 both live, v2 dual-writes name: ok=110 err=0 empty=0 | full_name: ok=5 err=0 empty=105 |
  backfilled 105 rows after v1 retired
  3 backfill done                    name: ok=110 err=0 empty=0 | full_name: ok=110 err=0 empty=0 |
  4 reads switched to full_name      full_name: ok=110 err=0 empty=0 |
  5 contract (drop name, later release) full_name: ok=110 err=0 empty=0 |
```

In the wrong way, v2 works but all 100 reads from v1 fail, because its column is gone. In the right way, there are no errors at any step. Step 1 adds the new column while v1 is live. In step 2 both versions run: 5 new rows come from v1 (only `name` filled) and 5 from v2, which writes both columns. So `full_name` has 5 good values and 105 empty ones. Once v1 is retired, a backfill copies the missing 105 values. Then reads switch to `full_name`, and only at the end, in a later release, is `name` dropped.

This pattern is called {{< term "expand-contract" "expand/contract" >}}: add the column, {{< term "dual-write" "dual-write" >}} to both, {{< term "backfill" "backfill" >}} old rows, switch reads, and drop the old column later. Consumers should be {{< term "tolerant-reader" "tolerant readers" >}} so an added column does not break them. For the real database side, see [zero-downtime migrations](/posts/db-zero-downtime-migrations/).

## Rollback or roll forward?

When the new version is bad you have two choices: go back to the old version (rollback) or fix quickly and ship a new version ({{< term "roll-forward" "roll forward" >}}). In my experience rollback is the right first move while it is cheap and safe, and roll forward wins once v2 has written data that v1 cannot read, or a migration dropped something.

Whichever you choose, you need to see the problem. Watch the {{< term "sli" "SLIs" >}} of your [SLO](/posts/eng-sli-slo-error-budgets/) split by version. Otherwise a 1% canary's errors hide in the noise of the other 99%. Argo Rollouts, Flagger, Spinnaker and the Kubernetes Deployment strategies automate much of this. I know them only from their documentation and did not run them here.

## Where automated rollouts go blind

- **Readiness is not correctness.** A rolling update that only checks "is it alive?" will happily roll out a version that is alive and wrong. A rollout needs real metrics.
- **Small canaries are blind.** With few requests the analysis cannot see a small bug, as the 28-request step showed. Compute the sample size you need, as the demo does.
- **Make every migration backward compatible** before shipping the code that needs it, since old and new versions always overlap.
- **Mirrored writes must not have side effects.** Shadow mode is safe for reads; if a mirrored request charges a card or sends an email, it does it for real.

## Exercise

Add a latency check to the canary analysis, using a counted clock so the result is reproducible. Then try a bug that affects only 0.5% of requests and see how many requests you need before the analysis can see it.

## What's next

The next post is "Capacity estimation". We now know how to ship a change safely, so the next question is how many machines it needs.
