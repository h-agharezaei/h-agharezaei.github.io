+++
date = '2027-06-05T10:00:00+03:30'
draft = false
title = 'Estimation and planning'
contentType = 'tutorial'
description = "Estimation and planning in Go: why one number misleads, Monte Carlo ranges, merge bias, throughput forecasts, Little's law and a toy Brooks's law model."
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["estimation", "planning", "forecasting", "monte-carlo", "software-engineering", "go", "kanban"]
cover = { image = "/images/covers/eng-estimation-planning.png", alt = "Estimation and planning", hiddenInSingle = true }
+++

"How long will it take?" You add up your estimates for ten tasks, get 42 days, and say "about two months". Then the project takes longer. It happens so often that it should not surprise anyone, yet the next plan is built the same way: one number.

In a simulation I ran for this post, ten tasks whose likely durations sum to 42 days took longer than 42 days in more than half of 100,000 simulated runs. This is not bad luck or bad people. A single number answers "when will it be done?" with something that is almost always wrong, and a range is a more honest answer. This post shows why, with small simulations you can reproduce, and then what to do instead.

This is the last post of the Software Engineering series, after [Monorepo or polyrepo?](/posts/eng-monorepo-vs-polyrepo/). Related reading: [SLIs, SLOs and error budgets](/posts/eng-sli-slo-error-budgets/), [Technical debt](/posts/eng-technical-debt/), [Blameless postmortems](/posts/eng-postmortems-blameless/) and [Topological sort and dependencies](/posts/algo-topological-sort/).

> I re-ran everything with Go 1.27.3 and `go test -race` passes (the original run used Go 1.26). It is a local demo with a fixed random seed and synthetic data. The numbers are days inside a model and counts, not timings of anything real.

## One number misleads

Start with a simple fact: task durations are skewed. A task estimated at 5 days can easily take 10, but it will not take 0. Doubling is far easier than halving. So I model each task with a skewed distribution (a log-normal one). Each task has three numbers: an optimistic value (O), a likely value (M) and a pessimistic value (P). I treat "likely" as the median (half the time it takes less, half the time more) and "pessimistic" as roughly the 95th percentile. That is my assumption, not a law. The demo's ten tasks:

```text
task  O    M    P
t1    3.6  6.0 24.0
t2    1.2  2.0  4.0
t3    3.0  5.0 10.0
t4    1.8  3.0  9.0
t5    1.8  3.0  6.0
t6    1.8  3.0  9.0
t7    3.0  5.0 20.0
t8    1.2  2.0  8.0
t9    4.8  8.0 32.0
t10   3.0  5.0 10.0
```

The likely values are between 2 and 8 days. Optimistic is 0.6 of likely, and pessimistic is 2 to 4 times likely, so every task has a long tail upward and a short one downward.

Now a {{< term "monte-carlo-simulation" "Monte Carlo simulation" >}}: do the whole project 100,000 times, each time drawing a random duration for every task from its distribution, and look at the totals:

```text
sum of likely=42.0  PERT sum=54.2
simulated total: P50=50.5 P80=64.8 P95=85.5
```

Read the second line as: half of the simulated projects finished within 50.5 days ({{< term "percentile" "P50" >}}), 80% within 64.8 days (P80), and 95% within 85.5 days (P95). The sum of the likely values, 42, is below even the P50. The classic PERT mean, `(O + 4M + P) / 6` per task, gave 54.2 for the sum, which here sits between P50 and P80.

Why is the sum of "likely" too low? Because each task is more likely to run over than under, and the overruns add up while the savings are small. Hofstadter's law ("it always takes longer than you expect, even when you take Hofstadter's law into account") and the planning fallacy of Kahneman and Tversky say the same in words. The honest answer is a range: "about 50 days at even odds, 65 days at 80%".

## Dependencies and merge bias

Real tasks depend on each other. They form a {{< term "dag" "DAG" >}}, a graph of tasks where arrows say "this must finish before that can start" and there are no cycles. The demo has seven tasks:

- `a`, `b` and `c` run in parallel; then `d` needs all three.
- `e` runs, then `f` needs `e`.
- `g` needs both `d` and `f`.

With the likely values (here a, b and c take 10 days each, d 6, e 12, f 8, g 5), the longest chain decides the total: `e`, `f`, `g` is 12 + 8 + 5 = 25 days. That chain is the {{< term "critical-path" "critical path" >}}. In this DAG the pessimistic value of every task is 3 times its likely value. I simulated it with unlimited people, and then with 3 people and 2 people:

```text
critical path with likely values: 25.0 days
workers=0: P50=36.4 P80=48.9 P95=66.8
workers=3: P50=39.6 P80=52.4 P95=70.4
workers=2: P50=45.5 P80=59.3 P95=77.7
```

(`workers=0` means unlimited people.) Even with unlimited people, the median is 36.4 days, not 25. Why? Where parallel paths meet, the join has to wait for the slowest one. If `d` is on time but `f` is late, `g` is late. Several chances to be late, only one chance to be early: that is **merge bias**. Fewer people push the whole range further out, because work that could be parallel now has to queue.

## Forecast from throughput

Estimating every item is slow and, as we saw, inaccurate. A different idea: do not estimate items, count the finished ones. For a team that has worked for a while, "how many items did we finish each week?" is a fact. The demo uses a synthetic history of 20 weeks (some weeks are zero, like a holiday or an incident) and asks: when will 40 items be done?

```text
history: [8 8 4 2 3 7 8 8 0 0 4 2 2 8 3 5 5 6 2 4]
velocity average=4.45 items/week -> 40 items in 9.0 weeks
bootstrap weeks: P50=9 P85=11 P95=13
```

The average is 4.45 items per week, so 40 items take 40 / 4.45 = 9.0 weeks. That is the one-number answer. The third line is the range. It comes from a bootstrap: draw a random week from the history, add its items, repeat until 40 items are done, count the weeks, and do it 100,000 times. The result: 9 weeks at even odds, 11 weeks at 85%, 13 weeks at 95%.

This is the idea behind probabilistic forecasting and the #NoEstimates movement. It assumes two things: the future looks like the past, and the items are of similar size. When those fail, so does the forecast.

## Little's law

Another planning tool is {{< term "littles-law" "Little's law" >}}: in a stable system, average work in progress (WIP) = throughput × average cycle time. Cycle time is how long one item takes from start to finish. Put it into words: if you keep 10 items in progress and finish 0.6 items a day, each item takes about 16 days from start to finish.

To see it, I simulated a Kanban-like board. There are 3 people and an endless backlog. Items need 1 to 9 days of work, and each person works on one item per day. The board limits how many items may be in progress, and the simulation runs for 2000 days for each limit:

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

Each row is one WIP limit. The last column, throughput × cycle time, matches the average WIP, which is Little's law (the last rows are a bit below the limit because items still in progress at day 2000 are not counted as done). Now look at the throughput column. From a limit of 3 to a limit of 40, throughput stays flat at about 0.6 items a day, because there are only 3 people. But cycle time grows from 5.0 to 65.4 days, about 13 times. Starting more work did not finish more work; it made every item wait longer. Below 3 (limits 1 and 2), people are idle, so throughput drops.

My opinion: a {{< term "wip-limit" "WIP limit" >}} near the team size is the cheapest planning tool there is.

## Brooks's law, as a toy

{{< term "brooks-law" "Brooks's law" >}} comes from *The Mythical Man-Month*: adding people to a late project makes it later. One reason is communication. Channels between n people grow as `n(n-1)/2`:

```text
n  channels
 3    3
 5   10
10   45
20  190
```

Five people have 10 channels, twenty people have 190. I built a toy model of the effect. It is not evidence, only an illustration: every channel eats 0.05 person-days of work per day, each newcomer costs 10 person-days of ramp-up, 200 person-days of work remain, and 5 people are on the team now.

```text
added  days to finish 200 person-days (5 people)
    0  44.4
    2  37.0
    5  32.3
   10  30.8
   25  54.5
```

Read the days column from top to bottom. Each addition helps less than the one before. Two new people save 7.4 days (44.4 to 37.0); going from 2 to 5 saves 4.7 more; going from 5 to 10 saves only 1.5 more; and 25 new people make the project later than doing nothing (54.5 days). Returns diminish, then reverse. The constants are made up; only the shape matters.

## Techniques and communication

Here are common techniques, with my notes:

| Technique | Use | My note |
|---|---|---|
| Planning poker | surface disagreement | the discussion is the value |
| T-shirt sizing | rough early ordering | do not add shirts up |
| {{< term "reference-class-forecasting" "Reference class" >}} | compare with similar past projects | strongest against optimism |
| Story points | relative size | easy to turn into a target; I prefer counting items |

It also helps to keep three words apart. A **forecast** is what we expect. A **target** is what we want. A **commitment** is what we promise. Mixing them is how forecasts turn into broken promises. Say "80% by this date", and name what would move it.

Two more ideas I did not run. Critical chain (buffers shared at the end of the project instead of per task) is worth reading about. The cone of uncertainty (Boehm) says estimates narrow as work progresses; its support is debated.

## The planning loop

Put together, planning is a loop, not a single act. Slice the work thin and vertical, so that each slice can ship. Measure cycle time and weekly throughput. Re-forecast every week with the bootstrap. And reserve capacity for the work that otherwise gets squeezed out: error-budget work (see the SLO post), technical debt and fixes from postmortems.

## How forecasts get misused

- **A range handed to a boss becomes a single number.** Write the percentile next to it ("65 days, 80% confidence").
- **Do not use throughput history from before a team change.** The model assumes the future looks like the past.
- **Splitting items helps more than re-estimating them.** This is my opinion.
- **Do not judge people by estimate accuracy.** Estimates are about uncertainty in the work, not a score for the person.

## Exercise

Add a fourth parallel branch before task `d` and watch the median.

## What's next

The Software Engineering series ends here. If you want to continue with Distributed Systems, that series starts with [Why distributed systems are hard](/posts/ds-why-distributed-is-hard/).
