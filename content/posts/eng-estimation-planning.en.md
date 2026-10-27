+++
date = '2027-06-05T10:00:00+03:30'
draft = false
title = 'Estimation and planning'
description = "Estimation and planning in Go: why one number misleads, Monte Carlo ranges, merge bias, throughput forecasts, Little's law and a toy Brooks's law model."
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["estimation", "planning", "forecasting", "monte-carlo", "software-engineering", "go", "kanban"]
cover = { image = "/images/covers/eng-estimation-planning.png", alt = "Estimation and planning", hiddenInSingle = true }
+++

The previous post, [Monorepo or polyrepo?](/posts/eng-monorepo-vs-polyrepo/), was about structure. This last post is about "when will it be done?" A single number is almost always wrong, for mathematical reasons. Related: [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/), [Technical debt](/posts/eng-technical-debt/), [Blameless postmortems](/posts/eng-postmortems-blameless/), [Topological sort and dependencies](/posts/algo-topological-sort/). Opinions are marked.

> Go 1.26, `go test -race` passes. A local, seeded demo with synthetic data; numbers are model days and counts, no timings.

## One number misleads

Task durations are skewed: doubling is far easier than halving. I model each task as log-normal, treat "likely" as the median and "pessimistic" as roughly the 95th percentile (my assumption). Ten tasks, likely values 2 to 8 days, then {{< term "monte-carlo-simulation" "Monte Carlo" >}} with 100,000 runs:

```text
sum of likely=42.0  PERT sum=54.2
simulated total: P50=50.5 P80=64.8 P95=85.5
```

The sum of the likely values (42) is below even the {{< term "percentile" "P50" >}} of the total. The PERT mean, `(O + 4M + P) / 6`, gave 54.2, which here sits between P50 and P80. The long tails add up; Hofstadter's law and the planning fallacy (Kahneman and Tversky) describe this in words. The honest answer is a range: "50 days at even odds, 65 at 80%".

## Dependencies and merge bias

Tasks form a {{< term "dag" "DAG" >}}. Seven tasks: a, b and c in parallel, then d; e then f in parallel; then g needs d and f. The {{< term "critical-path" "critical path" >}} with likely values is 25 days. Simulated, with unlimited people and then limited:

```text
critical path with likely values: 25.0 days
workers=0: P50=36.4 P80=48.9 P95=66.8
workers=3: P50=39.6 P80=52.4 P95=70.4
workers=2: P50=45.5 P80=59.3 P95=77.7
```

Even with unlimited people, the median is 36 days, not 25. When parallel paths merge, the join waits for the slowest one: that is merge bias. Fewer people push it further out.

## Forecast from throughput

Instead of estimating items, count what was finished. A synthetic 20-week history:

```text
history: [8 8 4 2 3 7 8 8 0 0 4 2 2 8 3 5 5 6 2 4]
velocity average=4.45 items/week -> 40 items in 9.0 weeks
bootstrap weeks: P50=9 P85=11 P95=13
```

Bootstrap: draw random weeks from the history until 40 items are done, 100,000 times. The average says 9 weeks; the distribution says "9 at even odds, 11 at 85%". This is the idea behind probabilistic forecasting and #NoEstimates. It assumes the future looks like the past and items are similar in size.

## Little's law

{{< term "littles-law" "Little's law" >}}: average WIP = throughput × average cycle time. I simulated a Kanban-like board: 3 people, an endless backlog, items needing 1 to 9 days of work, each person on one item per day, 2000 days:

```text
limit  done  avgWIP  throughput/day  avgCycle(days)  throughput*cycle
    1   395    1.00           0.198             5.1              1.00
    2   811    2.00           0.406             4.9              2.00
    3  1207    3.00           0.604             5.0              3.00
    5  1207    5.00           0.604             8.3              4.99
   10  1204   10.00           0.602            16.5              9.95
   20  1201   20.00           0.601            33.0             19.82
   40  1191   40.00           0.596            65.4             38.95
```

From a limit of 3 to 40, throughput stays flat while cycle time grows 13 times. Below 3 people are idle (starvation). In this model, more things in progress buys nothing but waiting. **My opinion:** a {{< term "wip-limit" "WIP limit" >}} near the team size is the cheapest planning tool there is.

## Brooks's law, as a toy

{{< term "brooks-law" "Brooks's law" >}} (The Mythical Man-Month): adding people to a late project makes it later. Communication channels grow as `n(n-1)/2`: 5 people have 10, 20 people have 190. My toy model (not evidence): each person loses 0.05 days per channel, each newcomer costs 10 person-days of ramp-up, 200 person-days remain, 5 people now.

```text
added  days to finish
    0  44.4
    2  37.0
    5  32.3
   10  30.8
   25  54.5
```

Returns diminish, then reverse. The constants are made up; only the shape matters.

## Techniques and communication

| Technique | Use | My note |
|---|---|---|
| Planning poker | surface disagreement | the discussion is the value |
| T-shirt sizing | rough early ordering | do not add shirts up |
| {{< term "reference-class-forecasting" "Reference class" >}} | compare with similar past projects | strongest against optimism |
| Story points | relative size | easy to turn into a target; I prefer counting items |

Keep three words apart: a **forecast** is what we expect, a **target** is what we want, a **commitment** is what we promise. Say "80% by this date", and name what would move it. Critical chain (buffers shared at the end, not per task) is worth reading; I did not run it. The cone of uncertainty (Boehm) says estimates narrow as work progresses; its support is debated.

## The planning loop

Slice work thin and vertical so each slice ships; measure cycle time and weekly throughput; re-forecast every week with the bootstrap; reserve capacity for error budget work (see the SLO post), debt, and fixes from postmortems.

## A few things to watch

- A range given to a boss becomes a single number; write the percentile next to it.
- Do not use throughput history from before a team change.
- Splitting items helps more than re-estimating them (my opinion).
- Do not judge people by estimate accuracy.

## Exercise

Add a fourth parallel branch before task d and watch the median.

## What's next

The Software Engineering series ends here. Next is the Distributed Systems series, which is still being written.
