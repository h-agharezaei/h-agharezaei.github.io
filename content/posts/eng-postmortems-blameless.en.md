+++
date = '2027-05-16T10:00:00+03:30'
draft = false
title = 'Blameless postmortems'
description = 'Blameless postmortems from a staged Go incident: timeline from logs, TTD/TTM/TTR, contributing factors, action items and a runnable document lint.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["postmortem", "incident", "blameless", "software-engineering", "go", "slog"]
cover = { image = "/images/covers/eng-postmortems-blameless.png", alt = "Blameless postmortems", hiddenInSingle = true }
+++

The previous post, [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/), said how much failure an {{< term "slo" "SLO" >}} accepts. This one is about what to do after an incident spends some of the {{< term "error-budget" "error budget" >}}. **This incident is staged on my machine**: no real users, no real people, invented names and roles. The logs, numbers and lint output are real runs of a small Go demo. Judgments are marked as my opinion.

A {{< term "postmortem" "postmortem" >}} is a written review made from evidence. Related: [Config, structured logging and errors in Go](/posts/go-config-logging-errors/), [Connection pooling and its failure modes](/posts/db-connection-pooling/), [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).

> Go 1.26, `go test -race` passed. The "service" is a virtual-time model (a seeded generator, an injected clock, no sockets, no sleeping), so timestamps are identical on every run.

## The staged incident

A config change drops the pool limit from 10 to 2 at 09:00:15. Five seconds later the dependency slows from 100 ms to 400 ms. Two slots at 400 ms handle about 5 requests per second; traffic is about 10. Requests wait for a connection and give up after 1 s. The service writes {{< term "structured-logging" "structured logs" >}} with `slog` JSON plus a counter file:

```text
{"level":"ERROR","msg":"request","ts":"...","id":...,"status":503,"wait_ms":1000,"err":"pool wait timeout","pool_max":2}
requests_total{status="200"} 699
requests_total{status="503"} 201
```

The alert rule is "error rate at least 20% over 10 s, checked every 5 s". The mitigation (a rollback) happens 30 s after the alert; that delay is my assumption, not a measurement of anyone.

## Timeline from evidence

A second program reads only `service.jsonl`. `t+0:00` is the first failed request:

```text
clock     t       event
09:00:15  t-0:07  deploy-pipeline applied cfg-1042 (pool_max=2)
09:00:22  t+0:00  first failed request (503, pool wait timeout)
09:00:30  t+0:07  alert fired: error rate >= 20% over 10s
09:01:00  t+0:37  oncall-engineer applied rollback-cfg-1042 (pool_max=10)
09:01:01  t+0:38  recovered: 20 healthy requests in a row

TTD (first error -> alert):      7.696s
TTM (first error -> mitigation): 37.696s
TTR (first error -> recovered):  38.957s
requests=900 failed=201 (22.3%)
assumed SLO 99.5% at 10 rps for 30 days: budget = 129600 failed requests; burned 0.16%
```

TTD is time to detect, TTM time to mitigate, TTR time to recover, all from the start of impact. They separate three questions: did we notice, did we stop the bleeding, is it really over? The 0.16% assumes 10 rps for 30 days, which I invented; real budget math needs your real traffic.

## Contributing factors, not "the root cause"

**My opinion:** a single "root cause" hides the rest. Here, the slow dependency alone would not fail a pool of 10 (the model says so: with a healthy pool size the test `TestHealthyConfigHasNoErrors` sees zero failures), and the bad pool size alone would not fail either (a second test with a fast dependency shows zero failures: 2 slots at 100 ms is about 20 per second). Four things lined up: no validation of the pool size, a rollout to everything at once, no alert on dependency latency, and an alert that only watches errors. A {{< term "circuit-breaker" "circuit breaker" >}} ([Circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/)) limits the damage of a slow dependency. Each is a {{< term "contributing-factor" "contributing factor" >}} with its own fix.

The {{< term "five-whys" "5 whys" >}} follows one chain and stops where the answerer stops, often at a person ("why? someone forgot to check"). I prefer a small causal diagram that allows branches:

```text
503s <- pool wait timeouts <- capacity (2 x 2.5/s) < traffic (10/s)
   |-- pool_max=2 accepted      <- no validation, no canary
   |-- dependency 4x slower     <- no latency alert
   '-- noticed after users hurt <- alert on errors only
```

## Blameless language

Blameless does not mean nobody is accountable; it means we ask what the system allowed. Rewrites:

- "Bob pushed a bad config" becomes "the config change had no validation and no staged rollout".
- "The on-call was slow to react" becomes "the runbook did not say that a rollback was the first move".
- "Human error" becomes nothing: if a person could do it, the system made it possible.

## Lint the document

`postmortem.md` has the standard sections: Summary, Impact, Timeline, Contributing factors, What went well, What went badly, Where we got lucky, Action items. Action items are rows with an owner **role**, a due date and a priority. `pmlint` checks that, and flags first names and phrases like "human error". Run on the good draft and on a deliberately blamey one:

```text
postmortem.md
  ok (3 action items)
blamey.md
  FAIL missing section "Where we got lucky"
  FAIL line 4: first name "Bob" (use a role)
  FAIL line 13: blamey phrase "human error"
  FAIL line 13: blamey phrase "should have known"
  FAIL line 29: owner "Bob" is not a role
  FAIL line 30: due date "soon" is not YYYY-MM-DD
```

(Output shortened by three similar lines.) A regex finds only the names I list, so it is a nudge, not a judge.

## Practice (my opinion)

Write it within days. Review it in a meeting where the question is "what would have stopped this", and publish it where every team can read it. Track action items like any other work, or the postmortem is theater; unfinished ones are {{< term "technical-debt" "technical debt" >}} with a date on it ([Technical debt](/posts/eng-technical-debt/)).

## A few things to watch

- Timeline from logs, not memory; keep clocks in one timezone.
- Count what went well and where you were lucky: luck is a risk.
- Action items need an owner role, a date and a priority, or they rot.
- Do not publish names; do not list "be more careful" as an action.

## Exercise

Add a "dependency latency above 250 ms" alert to the model and recompute TTD. Does it fire before the first error?

## What's next

The next post is "Working with legacy code".
