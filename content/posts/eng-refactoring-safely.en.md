+++
date = '2027-03-03T10:00:00+03:30'
draft = false
title = 'Refactoring safely'
contentType = 'tutorial'
description = 'Refactoring safely in Go: pin legacy behavior with a golden-master test, refactor in small steps, catch a one-character slip, and change a signature.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["refactoring", "testing", "legacy-code", "software-engineering", "go"]
cover = { image = "/images/covers/eng-refactoring-safely.png", alt = "Refactoring safely", hiddenInSingle = true }
+++

Imagine an 89-line function that calculates the price of an order. It is full of nested `if`/`else` blocks and magic numbers, nobody wrote down what it should do, and you have been asked to clean it up. Here is how fragile that is. Change a single `>=` to `>` in it, and a certain order's total silently moves from 111027 to 119954 cents. Nothing crashes, no error appears, and the customer is charged more.

{{< term "refactoring" "Refactoring" >}} means changing the structure of code while its behavior stays exactly the same. The hard part is the second half of that sentence. You cannot promise that behavior is unchanged unless something checks it, and in this function there is no written rule to check against, only the behavior itself. That is different from [Property-based testing](/posts/eng-property-based-testing/), where we started from a rule. Here we start from what the code does today.

So the plan is: first pin down today's behavior with a test, then change the structure in small steps and run that test after each one. The habit of small green steps is the same one from {{< term "tdd" "TDD" >}}. The basics of `go test` are in [Testing in Go](/posts/go-testing-basics/).

> The demos are local examples. I originally ran them with Go 1.26 and `go test -race`, and re-ran them with Go 1.27.3 for this edit. The legacy function is invented by me for this post.

## The legacy function

`PriceOrder(qty, unit, tier, coupon, country, express)` returns the order total in cents, or -1 for invalid input. It is 89 lines of nested `if`/`else`. Inside it you find:

- volume discounts that start at 10 items and at 50 items;
- a bonus for the customer's tier (gold, silver);
- three coupons;
- tax that depends on the country;
- shipping, with a surcharge for one country;
- and a final rule that adds one cent to any total that ends in 9.

I also planted two oddities, the kind that real legacy code has: the gold bonus disappears at 50 items and above, and only Germany rounds tax half up. They matter later, because a safe refactoring must keep them.

## Step 0: characterize the behavior first

Before touching the code I wrote a {{< term "characterization-test" "characterization test" >}}. The idea is simple. Run the function on a large set of inputs, save every output to a file, and later fail if any output is different. This is also called a golden-master test. It does not say the behavior is right. It only says the behavior has not changed.

My test uses 3000 inputs from a random generator with a fixed seed (`rand.NewSource(42)`), so the same 3000 inputs come out every time. About a third of them are invalid (1032 of the 3000 results are -1), so the error paths are covered too. The test writes one line per case to `testdata/golden.txt`. This is one line:

```text
50 2143 "basic" "HALF" "DE" true => 111027
```

Read it as: 50 items at 2143 cents, tier "basic", coupon "HALF", country "DE", express shipping, gives 111027 cents.

The test regenerates all the lines from the current code and compares them with the file. To record the file in the first place I run `go test -run Golden -update .`, which rewrites it from whatever the code does now. I recorded it on the untouched code. (Looking at the git history of the demo, I actually recorded it twice before touching anything: the first inputs did not mix tiers, coupons and countries well enough, so I widened them and recorded again. The numbers in this post are from the second recording.) Then I ran the test with `-race -cover`:

```text
$ go test -race -cover .
ok  	example.com/pricing	1.351s	coverage: 100.0% of statements
```

It passes, which is expected because the file was just made from this code, and the test covers every statement. The time differs from run to run.

The file also records the oddities, on purpose. **My opinion:** a golden file is a photograph, not a specification. It shows what the code does. Whether a quirk is a bug is a separate decision, and we make it later, in its own commit.

## Steps 1 to 3: small moves, test after each

Each step was its own commit. After each commit I ran `go vet` and the golden test. If the test had gone red, I would know the last small step was the cause.

1. **A mechanical rewrite with `gofmt -r`.** `gofmt` can rewrite code by a pattern: `gofmt -r 'a * b / 100 -> percentOf(a, b)' -w price.go` replaced four expressions of the form `x * y / 100` with a call to a helper (6 insertions and 4 deletions, including the helper). Because the tool does the change, there is no chance of a typo. One limit: the pattern must be an expression. `a = a + b` is a statement, and `gofmt` refused it with `expected '=='`.
2. **Early returns and `switch`.** The pyramid of `else { if ... }` became guard clauses (check the bad case, return early) and `switch` statements (60 insertions, 78 deletions).
3. **Extract and name.** I pulled out `discountPercent`, `couponOff`, `taxFor` and `shipping`, and gave the magic numbers names, such as `wholesaleQty = 50` and `halfCouponCap = 2000` (73 insertions, 35 deletions).

All steps stayed green. Each oddity stayed too, now with a comment saying that it is a known quirk kept on purpose.

## Did it get simpler?

It is easy to feel that code got simpler. A number is better. {{< term "cyclomatic-complexity" "Cyclomatic complexity" >}} is a rough count of how many different paths run through a function: 1, plus one for each `if`, `for`, non-default `case`, `&&` and `||`. The more paths, the harder the function is to hold in your head.

The usual tool, `gocyclo`, was blocked in my environment, so I wrote a small counter with `go/ast` that uses the same rule. These numbers come from that rule, not from `gocyclo`. For this edit I rebuilt a counter with the same rule and got the same numbers:

```text
before: PriceOrder 26
after:  Price 7, discountPercent 7, couponOff 6, taxFor 5, shipping 5, percentOf 1
```

The worst function dropped from 26 to 7. The logic is the same, but it now sits in pieces small enough to read one at a time.

## The safety net catches a slip

Now the reason for all this setup. I changed one character on purpose, `>=` to `>` in the wholesale check (the 50-item discount), and ran the golden test:

```text
--- FAIL: TestGolden (0.00s)
    golden_test.go:49: case 76 differs:
          want 50 2143 "basic" "HALF" "DE" true => 111027
          got  50 2143 "basic" "HALF" "DE" true => 119954
```

The test names the first input that differs. It is the order with exactly 50 items, which is exactly the boundary I broke: with `>` those 50 items no longer get the 12% discount, so the total goes up to 119954. This is the 111027 to 119954 from the beginning of the post. A second slip, `+ 50` to `+ 49` in the German rounding, failed at case 59 (`5081` against `5080`). I reverted both with `git checkout`. I re-ran both slips on a scratch copy for this edit and got the same two failures.

## Parallel change for a signature

The function takes six positional parameters, and that is a smell: it is easy to swap two strings by mistake. I wanted a single `Price(Order)` instead. The trouble is that a real function like this may have many callers (in the demo I made three, standing in for a larger number), and you cannot change all of them in one go.

{{< term "expand-contract" "Parallel change (also called expand/contract)" >}} solves this in four safe commits, each of them green. The database version of the same idea is in [Zero-downtime migrations](/posts/db-zero-downtime-migrations/). The first step, expand, adds the new API and turns the old one into a thin wrapper around it:

```go
// Expand: add the new API, make the old one a thin wrapper.
// Deprecated: use Price.
func PriceOrder(qty, unit int, tier, coupon, country string, express bool) int {
	return Price(Order{qty, unit, tier, coupon, country, express})
}
```

Nothing breaks, because old callers still work. Then I moved the callers over one at a time (`CartTotal`, then the other two). The last step is contract: delete `PriceOrder` and update the test to call `Price`. The golden file did not change at all after it was created, and `git diff --stat` on it is empty. That is the proof that the behavior stayed the same.

One limit to be honest about: my three demo callers are not covered by the golden test (the coverage dropped to 94.3% at the end for this reason). Real callers would need tests of their own before you migrate them.

## Refactor or rewrite?

**My opinion:** prefer refactoring. The evidence is the golden file. Its 3000 lines are the exact behavior of the old code, including quirks that somebody may depend on. A rewrite starts from the specification that people keep in their heads, and it loses all of that.

## Where refactors go wrong

- **Mixing refactoring and behavior changes.** Keep them in separate commits (**my advice**). Then a reviewer can check "nothing changed" mechanically, because the golden test says so.
- **Trusting the golden file blindly.** It is only as good as its inputs. 100% statement coverage says little about boundaries, such as exactly 50 items. {{< term "mutation-testing" "Mutation testing" >}}, which makes small changes to the code and checks that a test notices, measures this better. I did not run it here.
- **A flapping golden file.** Fix the random seed and sort any map output, or the file will change between runs for no reason.
- **"Fixing" a quirk in the middle of a refactor.** Change it in its own commit, so a failure can only mean one thing.
- **Confusing two kinds of tests.** A {{< term "regression" "regression" >}} test guards one known bug. A characterization test guards everything the code does today.

## Exercise

Take a function from your own codebase that nobody wants to touch. Record 500 inputs with a fixed seed into a golden file. Extract one function, run the test, then break one operator and read the failure.

## What's next

The next post is "Effective code review". Keeping refactoring commits separate from behavior changes only pays off if the reviewer knows how to use that separation, so we look at the reviewer's side.
