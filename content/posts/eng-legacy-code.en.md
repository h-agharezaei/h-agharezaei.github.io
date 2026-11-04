+++
date = '2027-05-21T10:00:00+03:30'
draft = false
title = 'Working with legacy code'
contentType = 'tutorial'
description = 'Working with legacy code in Go: explore with git and coverage, pin behaviour with a golden test, add seams, fix the bug, then strangle it in shadow mode.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["legacy-code", "refactoring", "golden-master", "strangler-fig", "software-engineering", "go"]
cover = { image = "/images/covers/eng-legacy-code.png", alt = "Working with legacy code", hiddenInSingle = true }
+++

Every team has a module nobody wants to open. It has no tests, it keeps its state in a global variable, and above one `>` check there is a comment that says "10 or more". Nobody is sure the comment is right, and nobody dares to find out. Many of the action items from [Blameless postmortems](/posts/eng-postmortems-blameless/) end up exactly there: in code that is too scary to change.

My working definition of {{< term "legacy-code" "legacy code" >}} is simple: code without tests. The idea comes from Michael Feathers' book *Working Effectively with Legacy Code*. Age has nothing to do with it. Code with no tests is code you cannot change with confidence, because you have no way to learn quickly whether your change broke something. So the whole job is: first build a safety net, then change the code, in small steps.

This post walks through that on a small example, step by step. Related reading: [Refactoring safely](/posts/eng-refactoring-safely/), [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/) and [Testing in Go](/posts/go-testing-basics/).

**The "legacy" package is my own invention.** It is about 80 lines with global state, `time.Now`, `os.Getenv` and a hidden bug, plus 12 invented commits by "Dev A", "Dev B" and "Dev C" to give it a history. The demo is local, and its output is from real runs; opinions are marked as such. I re-ran everything with Go 1.27.3 (the original run used Go 1.26), using a scratch clone of the demo repository to check out each commit.

## 1. Understand before changing

The package prices an order. It parses a line like `DE|apple:4,pear:2` (country, then `sku:quantity` pairs), computes a total with discounts and tax, and appends a line to a global `Ledger`. Before touching anything, I only read. Git remembers why code looks the way it does:

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

`git blame` says who last changed the line and in which commit. `git log -L` follows one line of code through the whole history, so we see three commits touched it. Now compare that with the comment above the line, which says "10 or more of one item: 8% off". The code says `q > 10`, which means 11 or more. The commit "tweak bulk threshold" changed `>=` to `>`. That is a lead, not a verdict: maybe the comment is stale, maybe the commit was the mistake. We do not know yet.

`go vet` prints nothing, so it sees no obvious problem. The coverage line confirms the definition: 0.0% of statements are tested. Finally, `go list -f '{{.Imports}}'` prints `[fmt os strconv strings time]`. Two of those matter: `time` and `os` mean the function secretly depends on the clock and the environment. These are hidden inputs, and they are why a test of this code would give different answers on different days.

## 2. Pin behaviour first

Before any change, I want a test that records what the code does today, bugs included. This is called a {{< term "characterization-test" "characterization test" >}} (some people say golden master). It does not say what the code should do. It only says what it does, so that when it changes you notice.

There is an obstacle: the code reads the clock directly, and Friday has a promotion. A test cannot control that. So the first edit is one line, `var now = time.Now`, and the code calls `now()` instead. That is a {{< term "seam" "seam" >}}: a place where a test can replace behaviour without editing the code around it.

The test generates 120 inputs with a fixed random seed (a few of them malformed on purpose), runs each in three setups (a Friday, a Monday and a Monday with `SHOP_TAX=7`), and compares all the outputs with a stored file, `testdata/golden.txt`. The first time, `go test -update` writes that file from the current behaviour:

```text
$ go test -update ./... && go test -race -cover ./...
ok  	example.com/legacy	1.565s	coverage: 97.6% of statements
```

Coverage went from 0.0% to 97.6% with one seam and one test. (The time on the `ok` line varies from run to run.) Remember that coverage tells you which lines ran, not whether they are correct. The golden file is what makes it useful here.

There is a lesson in how I got this test right. My first version recorded only return values. Then I also recorded the global `discountLog` (it counts discounted items per product), re-recorded the golden file at the old commit, and tried the next refactoring step. It failed:

```text
--- FAIL: TestGolden
    golden_test.go:72: line 121:
         got  fri	ledger=76 report=76 orders, last=17.77 bulk=map[apple:7 fig:4 kiwi:5 melon:6 pear:10]
         want fri	ledger=76 report=76 orders, last=17.77 bulk=map[apple:9 fig:4 kiwi:5 melon:6 pear:11]
    ...
```

(`...` marks two more lines of the same kind, for the other two setups.) My refactoring had stopped counting discounts for items that were parsed before an error in the same line. The old code counted them; mine did not. Return values were identical, so only the global exposed it. **Globals are outputs.** Record every output the code has: return values, global state, files. (I reproduced this failure from the demo repository's history for this post, with the golden file recorded at the old commit and the refactored `shop.go`.)

## 3. Seams, one edit at a time

Now the code can be made testable, in small steps, with `go test -race` after each one:

- `var getenv = os.Getenv`: a seam for the environment.
- Extract `parse` and a pure function `compute(country, items, friday, taxPct)`. "Pure" means no clock, no environment, no globals: the same inputs always give the same output. `Process` keeps the side effects.
- `var record = func(country string, total float64){...}`: a seam for the ledger, which plays the role of the database.

```text
ok  	example.com/legacy	1.395s	coverage: 97.6% of statements   # getenv
ok  	example.com/legacy	1.559s	coverage: 97.9% of statements   # parse + compute
ok  	example.com/legacy	1.382s	coverage: 97.9% of statements   # record
```

Each line is the full suite, including the golden test, passing after one step. If one had failed, I would know exactly which step to undo, because each step is small.

What I did here is {{< term "dependency-injection" "dependency injection" >}} with the least ceremony: instead of creating the clock, the environment and the storage inside the function, the function gets them from variables that a test can replace. My opinion: function variables are enough at first. Interfaces can come later if the code needs them.

## 4. Fix the bug after it is pinned

Now the real question from step 1. I change `bulk` to `q >= 10`, as the comment says. The golden test fails, which is exactly right:

```text
--- FAIL: TestGolden
    golden_test.go:72: line 3:
         got  fri	XX|fig:10,melon:6	TOTAL=40.94
         want fri	XX|fig:10,melon:6	TOTAL=41.54
    ...
    golden_test.go:77: 39 lines differ
```

(`...` marks the next two mismatches the test prints.)

The order with exactly 10 figs now gets the discount, so it is cheaper (40.94 instead of 41.54). The test shows me everything this one-character fix changes. `go test -update` then rewrote 39 lines of the golden file: 36 orders that contain a quantity of exactly 10, plus 3 summary lines (one for each setup). I read that diff and committed the code and the golden file together. The test never decided what is right. I did, and the diff made it easy to see what I was deciding.

## 5. Sprout and wrap

Sometimes you must add a feature in the middle of legacy code. Two techniques avoid tangling the new code with the old. A **sprout** is a new function, tested on its own, that the old code calls. A **wrap** surrounds the old function with a new one that adds behaviour.

In the demo, `ApplyCoupon` is a sprout: new logic in a new function, tested by a table of five cases. `ProcessAudited` is a wrap: it calls `Process`, then calls an `audit` hook with the line and the result. A test checks that it returns exactly what `Process` returns. I did not wire the coupon into `Process` (that is the exercise).

## 6. Strangler fig

What if the old code needs replacing, not fixing? The {{< term "strangler-fig" "strangler fig" >}} pattern, as I remember Martin Fowler describing it, replaces the old thing gradually: put a router in front, build the new implementation next to the old one, and move traffic over little by little. The name comes from a vine that grows around a tree.

In the demo, `ProcessV2` is the new version. It uses integer cents and no globals. First I run it in {{< term "shadow-mode" "shadow mode" >}}: the router serves the old answer, also runs the new one, and counts how often they differ. The run uses 10,000 seeded inputs (a Monday):

```text
inputs=10000 mismatches=3051 (one cent apart: 3040, other: 11, error-vs-total: 0)
served by new: 2141 of 10000 at SHOP_ROUTE=20
```

The first line says that in 3051 of 10,000 cases the two versions disagree. Error handling is identical: the `error-vs-total` count is 0, so both versions reject the same bad inputs. Money is where they differ. Legacy truncates (`int(total*100)`), while v2 rounds at each step. In 3040 cases the results are one cent apart; the other 11 are two cents apart (I checked that, v2 being higher in each). Is a cent on about 30% of orders acceptable? That is a business decision, not a coding one, and shadow mode gives you the data to ask it.

The second line shows the next phase. `SHOP_ROUTE` is a setting: `shadow`, or a number from 0 to 100. At 20, the router sent 2141 of 10,000 calls to the new path, picked by a hash of the input, so the same input always goes the same way. That setting is a {{< term "feature-flag" "feature flag" >}} ([Feature flags and trunk-based development](/posts/eng-feature-flags-trunk-based/)). And the fact that both implementations have the same function shape is a light version of {{< term "branch-by-abstraction" "branch by abstraction" >}}: old and new hide behind one signature, so you can switch between them.

## 7. Delete what is dead

At the end, `go tool cover -func` showed that `oldTax` was at 0.0%, a grep found no callers, and I deleted it with the suite green:

```text
example.com/legacy/shop.go:112:		oldTax		0.0%
```

I did **not** run staticcheck, which is the usual tool for finding unused code.

## Rewrite or refactor? (opinion)

Joel Spolsky wrote a well-known essay against rewriting software from scratch, and I agree with its gist. A rewrite throws away what the old code has learned, quirks like the cent truncation above that someone may depend on. In my experience, big rewrites rarely finish. Small modules with a clear contract are the exception.

## Team practice (opinion)

Leave code a little better every time you pass through it (the boy-scout rule). Write what you found in an [ADR](/posts/eng-adr-documentation/), and track unfinished cleanup as [technical debt](/posts/eng-technical-debt/).

## Where legacy work goes wrong

- **Coverage says what ran, not what is correct.** The 97.6% above is only useful because the golden file checks the outputs.
- **Record every output.** Return values, globals, files. Step 2 showed what happens when you forget one.
- **Make one change per step.** When a test fails you should know which change did it.
- **Never fix a bug inside a refactoring commit.** A refactoring should leave the golden file untouched. A bug fix changes it, so the two must be separate commits you can review separately.

## Exercise

Wire `ApplyCoupon` into `Process` with a third field in the line. Which golden lines change, and should any?

## What's next

The next post is "Domain-driven design basics". The border between old and new models that a strangler creates is largely what DDD is about.
