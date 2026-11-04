+++
date = '2027-04-11T10:00:00+03:30'
draft = false
title = 'Technical debt'
contentType = 'engineering'
description = 'Technical debt in a Go repo: measure churn, complexity, TODOs, coverage and dependency age with real tools, then write a debt register and decide.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["technical-debt", "software-engineering", "go", "refactoring", "metrics"]
cover = { image = "/images/covers/eng-technical-debt.png", alt = "Technical debt", hiddenInSingle = true }
+++

Ask a team what its technical debt costs and you usually get a feeling instead of an answer: "the pricing code is a mess", "nobody wants to touch it". The feeling may be right. But a feeling cannot be compared with a feature on a planning board, and it cannot tell you which mess to clean first.

So in this post I measure instead of complaining. I use a small repo and a handful of cheap tools. In this repo, `pricing.go` changed in 25 of 31 commits, and the {{< term "cyclomatic-complexity" "cyclomatic complexity" >}} of its `Price` function grew from 3 to 65, one small rule at a time. Cyclomatic complexity is a count of the independent paths through a function: one, plus one for every `if`, loop, `case` and `&&` / `||`. A function with a count of 65 has 65 paths that, in principle, each need a test.

That is {{< term "technical-debt" "technical debt" >}}: a promise you make to yourself, "we will clean this up later". It is the inner counterpart of the promise in [OpenAPI and API contracts](/posts/eng-openapi-contracts/), which was a promise to other people. The metaphor of debt is useful only if you can say what the interest is and what repaying costs. The tools I lean on are from [Refactoring safely](/posts/eng-refactoring-safely/) and [Testing in Go](/posts/go-testing-basics/). I mark my opinions with **in my experience** (or **in my opinion**). The numbers were run.

> The original run used Go 1.26, and I re-ran what I could with Go 1.27.3: the churn, complexity, TODO and coverage numbers for `orders` and `pricing`. The repo is invented: 31 commits created by a script with fixed dates and a fake author. It is a small shop with `pricing`, `orders` and `notify` packages. The numbers describe this toy repo, not any real project. Checks that need a module download (`notify` coverage, `go list -m -u`, `govulncheck`) could not be re-run because the Go proxy was too slow here, so those results are from the original run.

## Where does the work gather?

The first question is where the team spends its time. {{< term "code-churn" "Churn" >}} is the cheapest answer: how many commits touched each file. Git already knows:

```text
$ git log --format= --name-only | sort | uniq -c | sort -rn | grep -v '^ *1 '
  25 pricing/pricing.go
   7 orders/orders.go
```

`git log --format= --name-only` prints only the names of the changed files, one per commit. `sort | uniq -c` counts them, and `grep -v '^ *1 '` hides files that were changed just once. So `notify.go` changed once, `orders.go` seven times, and `pricing.go` 25 times out of 31 commits.

Churn alone says only that people work in a file. A file can change often and be perfectly healthy. So I combined it with complexity. I could not run `gocyclo` in this environment, so I used a small counter built on Go's `go/ast` package with the same rule (1 plus each `if`, `for`, non-default `case`, `&&`, `||`):

```text
65	pricing/pricing.go	Price
2	orders/orders.go	Total
1	notify/notify.go	Message
1	notify/notify.go	Default
```

Each line is the complexity, the file and the function. A function with complexity 65 in the most-changed file is a **hotspot**: code that is hard to understand and that people keep having to change. This is where the interest on the debt is paid, again and again.

I also ran the counter on old versions of the file, to see how the hotspot grew:

```text
2026-01-05 complexity=3  todos=1
2026-01-21 complexity=21 todos=5
2026-02-21 complexity=43 todos=10
2026-03-25 complexity=65 todos=15
```

(The `todos` column counts `TODO` and `FIXME` over the whole repo.) Debt did not appear in one bad commit. It grew one rule at a time, and every single step looked reasonable. **In my experience** that is the usual shape.

## Other signals

Churn and complexity are the two I trust most. A few more signals are cheap to collect:

- **Markers.** `grep -rnE "TODO|FIXME" . --include='*.go'` found 15: 8 in `pricing.go`, 6 in `orders.go` and 1 in `notify.go`. A marker with no owner and no ticket is a wish, not a plan.
- **Tests.** `go test -race -cover ./...` gave `orders` 100.0%, `pricing` 39.4% and `notify` 0.0%. (I re-ran the first two; `notify` is from the original run.) The riskiest code has the thinnest {{< term "code-coverage" "coverage" >}}. Keep in mind that coverage says which lines ran, not that they are well asserted.
- **Vet.** `go vet ./...` printed nothing in the original run, so this signal was clean. It is worth tracking in {{< term "ci" "CI" >}} as a count.
- **Dependencies.** The module requires `golang.org/x/text v0.3.0`. In the original run `go list -m -u all` printed `golang.org/x/text v0.3.0 [v0.43.0]`, and the old version dates from 2017-12-14. Old does not mean broken, but the gap grows every month.
- **Vulnerabilities.** In the original run `govulncheck@v1.1.4` failed with `fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`. So I have no vulnerability result and make no claim about this module.

## A debt register

Numbers become useful when they are in a table the team can argue about. A debt register lists each item with the cost of leaving it (the interest), the cost of fixing it, and a decision. This one is my example, and the estimates are made up:

| Item | Cost of delay (interest) | Fix cost | Verdict |
|---|---|---|---|
| `Price` is complexity 65, 39% covered | every pricing change is risky | 3-4 days | pay now |
| `x/text` is old | grows with each update | 1 day | next quarter |
| `notify` has 0% coverage, untouched | none so far | 1 day | leave |

The last row matters most for the idea of debt. Debt in code that never changes costs nothing, because there is no interest to pay. It only looks bad in a report.

There is also a well-known way to sort debt, Martin Fowler's quadrant (as I remember it, from his writing on the topic). It divides debt into deliberate or inadvertent, and prudent or reckless. I use it for two questions: did we choose this knowingly, and did we write it down?

## Paying it down

- **In my opinion** the boy-scout rule (leave the file a bit cleaner than you found it) handles small debt. It will never fix a function with complexity 65. That needs a planned and tested {{< term "refactoring" "refactor" >}}: first characterization tests that pin the current behavior, then small steps.
- With non-engineers I do not say "the code is ugly". I say "each pricing change now takes longer and breaks things more often", and only if the team's own numbers (lead time, incidents) support it.
- Sometimes you should not pay at all: code that is about to be deleted, code that never changes, and a prototype whose idea is still unproven.

## How debt tracking goes wrong

- **Metrics become targets.** A team told to raise coverage will write tests with no assertions, and the number will go up while the safety goes down.
- **Churn needs history.** A squashed or brand-new repo hides it.
- **A register nobody reads.** It becomes just another TODO. Review it together with planning.
- **Cleanup mixed into a feature commit.** It makes review harder, and it makes `git bisect` less useful when something breaks.

## What's next

The next post is "ADRs and documenting decisions". In the register above, the last question was "did we write it down?". An ADR is the place where that answer lives.
