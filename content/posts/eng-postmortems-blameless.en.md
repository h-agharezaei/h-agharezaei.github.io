+++
date = '2027-05-16T10:00:00+03:30'
draft = false
title = 'Blameless postmortems'
contentType = 'tutorial'
description = 'Blameless postmortems from a staged Go incident: timeline from logs, TTD/TTM/TTR, contributing factors, action items and a runnable document lint.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["postmortem", "incident", "blameless", "software-engineering", "go", "slog"]
cover = { image = "/images/covers/eng-postmortems-blameless.png", alt = "Blameless postmortems", hiddenInSingle = true }
+++

Picture the end of an incident review. The service was down for a while, the cause has been found, and someone asks the natural question: "so who pushed that change?" A name is said, people nod, the meeting ends. Everyone feels the problem is understood. Next month the same kind of change goes out, from a different person, and breaks the same way.

The review ended at a person, and a person is the one place where nothing can be fixed. A **blameless postmortem** asks a different question: what would have stopped this? The answer is almost always something in the system: a missing check, a rollout that hits everything at once, an alert that only fires after users are hurt. A {{< term "postmortem" "postmortem" >}} is simply a written review of an incident, built from evidence (logs and metrics), with a timeline, the factors that led to it and a list of follow-up actions.

This post connects to the previous one, [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/): an incident spends the {{< term "error-budget" "error budget" >}} that an {{< term "slo" "SLO" >}} allows, and the postmortem is where the team writes down what that cost and what to change. Related reading: [Config, structured logging and errors in Go](/posts/go-config-logging-errors/), [Connection pooling and its failure modes](/posts/db-connection-pooling/) and [Designing a CI/CD pipeline](/posts/eng-ci-cd-pipeline-design/).

**The incident in this post is staged on my machine.** There are no real users or real people, and the names and roles are invented. The logs, the numbers and the lint output come from real runs of a small Go demo.

> I re-ran the demo with Go 1.27.3 and `go test -race` passes (the original run used Go 1.26). The "service" is a model in virtual time: a seeded random generator, an injected clock, no sockets and no sleeping. That is why the timestamps are identical on every run.

## The staged incident

To have something to write about, the demo simulates a small service. It sends requests through a connection pool (a fixed number of slots, each one a connection to a database or another dependency). Here is what happens, in order:

1. At 09:00:15 a config change lowers the pool limit from 10 to 2.
2. Five seconds later, the dependency slows down from 100 ms to 400 ms per call.
3. Two slots at 400 ms each can serve about 5 requests per second, but traffic is about 10 per second. Requests start to queue for a connection, and after waiting 1 second they give up with an error (HTTP 503).

The service writes {{< term "structured-logging" "structured logs" >}}: one JSON object per line, written with Go's `slog`. It also writes a small counter file. These are one real error line and the final counters:

```text
{"level":"ERROR","msg":"request","ts":"2027-05-10T09:00:22.304Z","id":209,"status":503,"wait_ms":1000,"dur_ms":0,"err":"pool wait timeout","pool_max":2}
requests_total{status="200"} 699
requests_total{status="503"} 201
```

Each failed request says what happened (`pool wait timeout`), how long it waited (`wait_ms`: 1000) and how big the pool was at the time (`pool_max`: 2). This detail matters later, because a timeline can only be as good as the logs it is built from.

Two more rules of the model. The alert is "error rate at least 20% over the last 10 seconds, checked every 5 seconds". And the mitigation (a rollback of the config) happens 30 seconds after the alert fires. That delay is my assumption, not a measurement of anyone.

## Timeline from evidence

The first job of a postmortem is a timeline: what happened, when, in order. The reliable way is to build it from logs, not from people's memory. A second program in the demo reads only `service.jsonl` and prints the key moments. In its output, `t+0:00` is the first failed request, and the other times are relative to it:

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
bad config live before first error: 7.304s
requests=900 failed=201 (22.3%)
assumed SLO 99.5% at 10 rps for 30 days: budget = 129600 failed requests; burned 0.16%
```

The table reads from top to bottom. The config change came first (7 seconds before the first error), then the first failure, then the alert, then the rollback, then recovery. "Recovered" here means the first moment of a run of 20 healthy requests in a row after the rollback.

The three lines that follow measure how the team did, all counted from the start of the impact:

- **TTD**, time to detect: from the first error to the alert. Did we notice?
- **TTM**, time to mitigate: from the first error to the rollback. Did we stop the bleeding?
- **TTR**, time to recover: from the first error to healthy traffic again. Is it really over?

The 0.16% at the end is the share of the error budget this incident spent: 201 failed requests out of 129,600 allowed. That number assumes 10 requests per second for 30 days, which I invented for the demo. A real calculation needs your real traffic.

## Contributing factors, not "the root cause"

My opinion: a single "root cause" hides everything else. Look at what the tests say. The slow dependency alone does not fail a pool of 10: with a healthy pool size, `TestHealthyConfigHasNoErrors` sees zero failures. The bad pool size alone does not fail either: a second test with a fast dependency also shows zero failures, because 2 slots at 100 ms can serve about 20 requests per second. It took both together.

Four things lined up:

- the pool size was never validated;
- the change rolled out to everything at once;
- nothing alerted on dependency latency;
- the one alert we had watched only errors, so it fired after users were already hurt.

Each of these is a {{< term "contributing-factor" "contributing factor" >}}, and each has its own fix. A {{< term "circuit-breaker" "circuit breaker" >}} ([Circuit breakers and bulkheads](/posts/ds-circuit-breaker-bulkhead/)) would also limit the damage of a slow dependency.

You may know the technique called {{< term "five-whys" "5 whys" >}}: ask "why?" five times. It follows one chain and tends to stop where the person answering stops, often at a human ("why? someone forgot to check"). I prefer a small causal diagram that allows branches. Read it from left to right as "caused by":

```text
503s <- pool wait timeouts <- capacity (2 x 2.5/s) < traffic (10/s)
   |-- pool_max=2 accepted      <- no validation, no canary
   |-- dependency 4x slower     <- no latency alert
   '-- noticed after users hurt <- alert on errors only
```

The top line is the mechanism: requests fail because they wait too long for a connection, because the pool (2 slots, each serving 2.5 requests per second at 400 ms) is smaller than the traffic (10 per second). The three branches are the reasons the system allowed it. Each branch ends in something a team can change.

## Blameless language

Blameless does not mean nobody is accountable. It means we ask what the system allowed, not who to punish. A few rewrites show the difference:

- "Bob pushed a bad config" becomes "the config change had no validation and no staged rollout".
- "The on-call was slow to react" becomes "the runbook did not say that a rollback was the first move".
- "Human error" becomes nothing. If one person could do it, the system made it possible, and that is the sentence to write.

## What a postmortem looks like

Here is the good version of the document from the demo, `postmortem.md`. It has the standard sections, and each one answers a question:

```markdown
# Postmortem: 503 spike after a pool-size config change (STAGED INCIDENT)

## Summary
A config rollout lowered the DB pool limit from 10 to 2. Five seconds later the dependency slowed from 100 ms to 400 ms. Capacity fell below traffic and requests timed out waiting for a connection.

## Impact
201 of 900 requests failed (22.3%) over about 38 seconds. 0.16% of the assumed 30-day error budget.

## Timeline
See the table produced by cmd/timeline (t+0:00 = first failed request).

## Contributing factors
- The config change had no validation of a minimum pool size.
- The rollout went to 100% at once, with no canary.
- The dependency latency rose with no alert of its own.
- The alert watched only the error rate, so it fired after users were hurt.

## What went well
- The alert fired 7.7 s after the first error.
- The rollback was one config change, not a deploy.

## What went badly
- The new config reached all instances at once.
- Nobody could see pool saturation on a dashboard.

## Where we got lucky
- The dependency slowdown came after the change; had it come first the cause would have been unclear.

## Action items
| ID | Action | Owner | Due | Priority |
|----|--------|-------|-----|----------|
| AI-1 | Reject pool_max below 4 in config validation | backend team | 2027-06-01 | P1 |
| AI-2 | Roll config out to 10% of instances first | release engineer | 2027-06-15 | P1 |
| AI-3 | Alert on pool wait time p95 | SRE on-call | 2027-06-08 | P2 |
```

(In the file I linted, the Summary said "Seven seconds later". That is wrong: the slowdown is five seconds after the change, as the timeline shows. I corrected it above. The lint result does not depend on that sentence.)

How to read it: Summary is what happened in three sentences. Impact is the size of the damage in numbers. Contributing factors is the list from the previous section. "What went well" is as important as the failures: it tells the team what to keep. "Where we got lucky" is the section people skip, and it matters, because luck is a risk that has not happened yet. Action items are the point of the whole document. Each one has an owner **role** (not a person's name), a due date and a priority.

## Lint the document

A document like this can drift back to blame without anyone noticing. So the demo includes a small checker, `pmlint`. It checks that all eight sections exist, that each action item has an owner role, a date in `YYYY-MM-DD` form and a priority of P0, P1 or P2, and it flags first names and phrases like "human error". Here it is on the good draft and on a deliberately blamey one (the second run exits with an error, which is the point):

```text
postmortem.md
  ok (3 action items)
blamey.md
  FAIL missing section "Where we got lucky"
  FAIL line 4: first name "Bob" (use a role)
  FAIL line 13: blamey phrase "human error"
  FAIL line 13: blamey phrase "careless"
  FAIL line 13: blamey phrase "should have known"
  FAIL line 13: first name "Bob" (use a role)
  FAIL line 29: first name "Bob" (use a role)
  FAIL line 29: owner "Bob" is not a role
  FAIL line 30: due date "soon" is not YYYY-MM-DD
```

The good draft passes with its three action items. The blamey one fails nine checks: a missing section, the name "Bob" in the summary, the contributing factors and the action table, three blamey phrases in one line, and an action item with the due date "soon". A regex can only catch the names I put in its list, so this is a nudge, not a judge.

## How I would run it (my opinion)

Write it within a few days, while people still remember. Review it in a meeting where the question is "what would have stopped this?", and publish it where every team can read it. Track the action items like any other work. Otherwise the postmortem is theater: unfinished action items are {{< term "technical-debt" "technical debt" >}} with a date on it ([Technical debt](/posts/eng-technical-debt/)).

## Habits that keep it blameless

- **Build the timeline from logs, not memory.** Keep every clock in one timezone, or the order of events will be argued about.
- **Write down what went well and where you were lucky.** Luck is a risk, and it is invisible until it runs out.
- **Give every action item an owner role, a date and a priority.** Without them it quietly rots.
- **Do not publish names, and do not write "be more careful" as an action item.** The first blames a person, and the second cannot be checked or finished.

## Exercise

Add a "dependency latency above 250 ms" alert to the model and recompute TTD. Does it fire before the first error?

## What's next

The next post is "Working with legacy code". Action items help only if the code they touch can be changed safely, and that is often exactly what old code does not allow.
