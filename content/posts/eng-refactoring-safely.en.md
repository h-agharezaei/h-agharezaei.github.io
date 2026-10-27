+++
date = '2027-03-03T10:00:00+03:30'
draft = false
title = 'Refactoring safely'
description = 'Refactoring safely in Go: pin legacy behavior with a golden-master test, refactor in small steps, catch a one-character slip, and change a signature.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["refactoring", "testing", "legacy-code", "software-engineering", "go"]
cover = { image = "/images/covers/eng-refactoring-safely.png", alt = "Refactoring safely", hiddenInSingle = true }
+++

Last time, in [Property-based testing](/posts/eng-property-based-testing/), we described code by its rules. Today the code has no rules written down, only behavior. {{< term "refactoring" "Refactoring" >}} means changing structure while behavior stays identical, and you cannot promise that without a test that pins the behavior first. The {{< term "tdd" "TDD" >}} habit of small green steps applies; test basics are in [Testing in Go](/posts/go-testing-basics/). Judgment calls are marked **my opinion**; everything else was run.

> Go 1.26, `go test -race`, local example; the legacy function is invented.

## The legacy function

`PriceOrder(qty, unit, tier, coupon, country, express)` returns a total in cents, or -1 for invalid input. It is 89 lines of nested `if`/`else` with magic numbers: volume discounts at 10 and 50 items, tier bonuses, three coupons, tax by country, shipping, and a final rule that bumps any total ending in 9. Planted oddities: the gold bonus vanishes at 50+ items and only Germany rounds tax half up.

## Step 0: characterization first

Before touching it I wrote a {{< term "characterization-test" "characterization test" >}}: 3000 inputs from `rand.NewSource(42)` (a third invalid), each output written to `testdata/golden.txt`, one line per case:

```text
50 2143 "basic" "HALF" "DE" true => 111027
```

The test regenerates the lines and compares. Recording is `go test -run Golden -update .`, which I ran once, on the untouched code:

```text
$ go test -race -cover .
ok  	example.com/pricing	1.351s	coverage: 100.0% of statements
```

The file records the oddities too, on purpose. **My opinion:** a golden file is a photograph, not a spec; whether a quirk is a bug is decided later.

## Steps 1 to 3: small moves, test after each

Each step was a commit; `go vet` and the golden test ran after each.

1. **Mechanical rewrite with `gofmt -r`**: `gofmt -r 'a * b / 100 -> percentOf(a, b)' -w price.go` replaced four expressions (6 insertions, 4 deletions with the helper). Patterns must be expressions: `a = a + b` failed with `expected '=='`.
2. **Early returns and `switch`**: the `else { if ... }` pyramid became guard clauses and switches (60 insertions, 78 deletions).
3. **Extract and name**: `discountPercent`, `couponOff`, `taxFor`, `shipping`, plus constants such as `wholesaleQty = 50` and `halfCouponCap = 2000` (73 insertions, 35 deletions).

All green. The quirks stayed, with a comment saying so.

## Did it get simpler?

I could not run `gocyclo` here: fetching and running it was blocked in this environment, so I did not get its output. I wrote a small `go/ast` counter with the same rule ({{< term "cyclomatic-complexity" "cyclomatic complexity" >}} is 1 plus each `if`, `for`, non-default `case`, `&&` and `||`). These numbers come from that rule, not from gocyclo:

```text
before: PriceOrder 26
after:  Price 7, discountPercent 7, couponOff 6, taxFor 5, shipping 5, percentOf 1
```

The worst function dropped from 26 to 7; the logic is the same, split into readable pieces.

## The safety net catches a slip

I changed one character, `>=` to `>` in the wholesale check, and ran the golden test:

```text
--- FAIL: TestGolden (0.00s)
    golden_test.go:49: case 76 differs:
          want 50 2143 "basic" "HALF" "DE" true => 111027
          got  50 2143 "basic" "HALF" "DE" true => 119954
```

It names the first differing input, exactly the boundary I broke. A second slip, `+ 50` to `+ 49` in the German rounding, failed at case 59 (`5081` vs `5080`). Both were reverted with `git checkout`.

## Parallel change for a signature

Six positional parameters were a smell, so I wanted `Price(Order)`. With many callers you cannot change all of them at once. {{< term "expand-contract" "Parallel change (expand/contract)" >}} does it in four safe commits, each green; the database version is in [Zero-downtime migrations](/posts/db-zero-downtime-migrations/):

```go
// Expand: add the new API, make the old one a thin wrapper.
// Deprecated: use Price.
func PriceOrder(qty, unit int, tier, coupon, country string, express bool) int {
	return Price(Order{qty, unit, tier, coupon, country, express})
}
```

Then migrate callers one at a time (`CartTotal`, then the other two), and finally contract: delete `PriceOrder` and update the test. The golden file did not change after its creation (empty `git diff --stat`). Limit: my three demo callers are not covered by the golden test; real ones would need tests first.

## Refactor or rewrite?

**My opinion:** prefer refactoring. The evidence is the golden file: its 3000 lines are the old code's exact behavior, including quirks someone may depend on. A rewrite starts from the spec in people's heads and loses all of that.

## A few things to watch

- Keep refactor commits and behavior-change commits separate (**my advice**). A reviewer can then check "nothing changed" mechanically.
- A golden file is only as good as its inputs. 100% statement coverage says little about boundaries; {{< term "mutation-testing" "mutation testing" >}} checks that better (I did not run it here).
- Fix the seed and sort map output, or the golden file flaps.
- Do not "fix" a quirk inside a refactor; change it in its own commit.
- A {{< term "regression" "regression" >}} test guards one known bug; a characterization test guards everything.

## Exercise

Take a function from your own codebase that nobody wants to touch. Record 500 seeded inputs to a golden file, extract one function, run the test, then break one operator and read the failure.

## What's next

The next post is "Effective code review".
