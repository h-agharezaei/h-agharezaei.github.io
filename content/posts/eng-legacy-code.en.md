+++
date = '2027-05-21T10:00:00+03:30'
draft = false
title = 'Working with legacy code'
description = 'Working with legacy code in Go: explore with git and coverage, pin behaviour with a golden test, add seams, fix the bug, then strangle it in shadow mode.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["legacy-code", "refactoring", "golden-master", "strangler-fig", "software-engineering", "go"]
cover = { image = "/images/covers/eng-legacy-code.png", alt = "Working with legacy code", hiddenInSingle = true }
+++

The previous post, [Blameless postmortems](/posts/eng-postmortems-blameless/), ended with action items, and many land in code nobody dares touch. My working definition: {{< term "legacy-code" "legacy code" >}} is code without tests (the idea is from Michael Feathers' book *Working Effectively with Legacy Code*). Related: [Refactoring safely](/posts/eng-refactoring-safely/), [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/), [Testing in Go](/posts/go-testing-basics/).

**The "legacy" package is my own invention**: 80 lines, global state, `time.Now`, `os.Getenv`, a hidden bug, 12 invented commits (Go 1.26, local demo). Output is from real runs; opinions are marked.

## 1. Understand before changing

It parses `country|sku:qty,...`, prices it and appends to a global `Ledger`. Read-only first:

```text
$ git blame -L '/q > 10/,+1' shop.go
3a6b62b6 (Dev C 2026-04-14 10:00:00 +0000 42) 		if q > 10 {
$ git log -L '/q > 10/,+1:shop.go' -s --format='%h %an %s'
3a6b62b Dev C tweak bulk threshold
0c05928 Dev B bulk discount
798d5ea Dev A first version of pricing
$ go vet ./...            # clean
$ go test -cover ./...
	example.com/legacy		coverage: 0.0% of statements
```

`git log -L` follows one line through history. A comment says "10 or more", yet the commit "tweak bulk threshold" changed `>=` to `>`: a lead, not a verdict. `go vet` is silent; coverage 0.0% is the real starting point. `go list -f '{{.Imports}}'` shows `time` and `os`: the hidden inputs are the clock and the environment.

## 2. Pin behaviour first

A {{< term "characterization-test" "characterization test" >}} records what the code does, bugs included. An uncontrollable clock prevents that, so the first edit is one line, `var now = time.Now`, a {{< term "seam" "seam" >}}. The test runs 120 seeded inputs in three setups (Friday, Monday, `SHOP_TAX=7`) against `testdata/golden.txt`; `go test -update` rewrites it:

```text
$ go test -update ./... && go test -race -cover ./...
ok  	example.com/legacy	1.330s	coverage: 97.6% of statements
```

My first version recorded only return values. I then added the global `discountLog`, re-recorded at the old commit, and my next refactoring step failed (`apple:7`, want `apple:9`): I had dropped counts for items before a parse error. **Globals are outputs.**

## 3. Seams, one edit at a time

One small step at a time, `go test -race` after each:

- `var getenv = os.Getenv`.
- Extract `parse` and a pure `compute(country, items, friday, taxPct)`; `Process` keeps the side effects.
- `var record = func(country string, total float64){...}` for the ledger, the "database".

```text
ok  	example.com/legacy	1.317s      # getenv
ok  	example.com/legacy	1.489s      # parse + compute
ok  	example.com/legacy	1.451s	coverage: 97.9% of statements   # record
```

This is {{< term "dependency-injection" "dependency injection" >}} with the least ceremony. **My opinion:** function variables suffice at first; interfaces can come later.

## 4. Fix the bug after it is pinned

Changing `bulk` to `q >= 10` fails the golden test, as it should:

```text
--- FAIL: TestGolden
         got  fri	XX|fig:10,melon:6	TOTAL=40.94
         want fri	XX|fig:10,melon:6	TOTAL=41.54
```

`go test -update` rewrote 40 golden lines: 37 orders, each containing a quantity of exactly 10, plus 3 summary lines. I read the diff and committed code and golden together. The test never judged what is right; I did.

## 5. Sprout and wrap

For new behaviour, avoid the knot. A **sprout** is a new tested function (`ApplyCoupon`, five table cases); a **wrap** surrounds the old one (`ProcessAudited` calls `Process`, then an `audit` hook). I did not wire the coupon into `Process`.

## 6. Strangler fig

For a bigger replacement, the {{< term "strangler-fig" "strangler fig" >}} pattern (from a description by Martin Fowler, as I remember it) puts a router in front. `ProcessV2` uses integer cents and no globals. In {{< term "shadow-mode" "shadow mode" >}} the router serves the old answer and counts differences on 10,000 seeded inputs (a Monday):

```text
inputs=10000 mismatches=3051 (one cent apart: 3040, other: 11, error-vs-total: 0)
served by new: 2141 of 10000 at SHOP_ROUTE=20
```

Errors are identical. Money differs because legacy truncates (`int(total*100)`) and v2 rounds per step; the 11 others are two cents apart. Whether a cent on 30% of orders is acceptable is a business decision. `SHOP_ROUTE` (`shadow` or 0-100) is a {{< term "feature-flag" "feature flag" >}}, and both implementations sharing one function shape is a light {{< term "branch-by-abstraction" "branch by abstraction" >}} ([Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/)). Share 20 sent 2141 calls to the new path, chosen by hash of the input.

## 7. Delete what is dead

`go tool cover -func` showed `oldTax` at 0.0%, grep found no callers, and I deleted it with the suite green. **I did not run staticcheck**, the usual tool for this.

## Rewrite or refactor? (opinion)

Joel Spolsky wrote a well-known essay against rewriting from scratch; I agree with its gist. A rewrite throws away quirks the code learned, like the cent truncation above, and in my experience big rewrites rarely finish. Small modules with a clear contract are the exception.

## Team practice (opinion)

Leave code a little better each time you pass (the boy-scout rule), write findings in an [ADR](/posts/eng-adr-documentation/), and track unfinished cleanup as [technical debt](/posts/eng-technical-debt/).

## A few things to watch

- Coverage says what ran, not what is correct.
- Record every output: return values, globals, files.
- One change per step.
- Never fix a bug in a refactoring commit.

## Exercise

Wire `ApplyCoupon` into `Process` with a third field in the line. Which golden lines change, and should any?

## What's next

The next post is "Domain-driven design basics".
