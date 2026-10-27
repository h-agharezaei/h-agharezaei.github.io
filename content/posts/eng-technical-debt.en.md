+++
date = '2027-04-11T10:00:00+03:30'
draft = false
title = 'Technical debt'
description = 'Technical debt in a Go repo: measure churn, complexity, TODOs, coverage and dependency age with real tools, then write a debt register and decide.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["technical-debt", "software-engineering", "go", "refactoring", "metrics"]
cover = { image = "/images/covers/eng-technical-debt.png", alt = "Technical debt", hiddenInSingle = true }
+++

The previous post, [OpenAPI and API contracts](/posts/eng-openapi-contracts/), was about a promise you make to other people. {{< term "technical-debt" "Technical debt" >}} is the promise you make to yourself: "we will clean this up later". The metaphor is useful only when you can say what the interest is and what the repayment costs. So here I measure instead of complaining. Tools I lean on: [Refactoring safely](/posts/eng-refactoring-safely/), [Testing in Go](/posts/go-testing-basics/). Opinions are marked **in my experience**; the numbers were run.

> Go 1.26. The repo is invented: 31 commits created by a script with fixed dates and a fake author. It is a small shop with `pricing`, `orders` and `notify` packages. The numbers describe this toy repo, not any real project.

## Where does the work gather?

{{< term "code-churn" "Churn" >}} is the cheapest signal: how many commits touched each file.

```text
$ git log --format= --name-only | sort | uniq -c | sort -rn | grep -v '^ *1 '
  25 pricing/pricing.go
   7 orders/orders.go
```

`notify.go` changed once. `pricing.go` changed 25 times out of 31 commits. Churn alone only says people work there. Combine it with {{< term "cyclomatic-complexity" "cyclomatic complexity" >}}. I could not run `gocyclo` in this environment, so I used a small `go/ast` counter with the same rule (1 plus each `if`, `for`, non-default `case`, `&&`, `||`):

```text
65	pricing/pricing.go	Price
2	orders/orders.go	Total
1	notify/notify.go	Message
```

A function with complexity 65 in the most-changed file is a hotspot. I also ran the counter on old versions of the file:

```text
2026-01-05 complexity=3  todos=1
2026-01-21 complexity=21 todos=5
2026-02-21 complexity=43 todos=10
2026-03-25 complexity=65 todos=15
```

(The todos column counts `TODO` and `FIXME` over the whole repo.) Debt did not appear in one bad commit; it grew by a rule at a time. **In my experience** that is the usual shape.

## Other signals

- Markers: `grep -rnE "TODO|FIXME" . --include='*.go'` found 15: 8 in `pricing.go`, 6 in `orders.go`, 1 in `notify.go`. Markers without an owner or ticket are wishes.
- Tests: `go test -race -cover ./...` gave `orders` 100.0%, `pricing` 39.4%, `notify` 0.0%. The riskiest code has the thinnest {{< term "code-coverage" "coverage" >}}. Coverage says which lines ran, not that they are asserted well.
- Vet: `go vet ./...` printed nothing here, so this signal was clean. It is worth tracking in {{< term "ci" "CI" >}} as a count.
- Dependencies: the module requires `golang.org/x/text v0.3.0`. `go list -m -u all` printed `golang.org/x/text v0.3.0 [v0.43.0]`, and the version dated 2017-12-14. Old does not mean broken, but the gap grows every month.
- Vulnerabilities: `govulncheck@v1.1.4` failed with `fetching vulnerabilities: ... vuln.go.dev/index/modules.json.gz returned unexpected status: 403 Forbidden`. So I have no vulnerability result and make no claim about this module.

## A debt register

Numbers become useful in a table the team can argue about. This one is my example, with made-up estimates:

| Item | Cost of delay (interest) | Fix cost | Verdict |
|---|---|---|---|
| `Price` is complexity 65, 39% covered | every pricing change is risky | 3-4 days | pay now |
| `x/text` is old | grows with each update | 1 day | next quarter |
| `notify` has 0% coverage, untouched | none so far | 1 day | leave |

The last row matters: debt in code that never changes costs nothing. Fowler's well-known quadrant (as I remember it, from his writing on the topic) sorts debt as deliberate or inadvertent, and prudent or reckless. I use it to ask: did we choose this knowingly, and did we write it down?

## Paying it down

- **In my opinion** the boy-scout rule (leave the file a bit cleaner than you found it) handles small debt, but it never fixes a function of complexity 65. That needs a planned, tested {{< term "refactoring" "refactor" >}}: first characterization tests, then small steps.
- With non-engineers I do not say "the code is ugly". I say "each pricing change now takes longer and breaks things more often", and only if the team's own numbers (lead time, incidents) support it.
- When not to pay: code about to be deleted, code that never changes, and a prototype whose idea is still unproven.

## A few things to watch

- Do not turn metrics into targets. A team ordered to raise coverage will write assertion-free tests.
- Churn needs history; a squashed or new repo hides it.
- A register that nobody reads is another TODO. Review it with planning.
- Mixing cleanup into a feature commit makes review and `git bisect` harder.

## Exercise

Run the churn command on a real repo and the complexity counter on its top file. Write three rows of a register with an honest "cost of delay" for each, and decide one to leave alone.

## What's next

The next post is "ADRs and documenting decisions".
