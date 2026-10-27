+++
date = '2027-02-05T10:00:00+03:30'
draft = false
title = 'The test pyramid and TDD'
description = 'The test pyramid and TDD in Go: red-green-refactor on a real example, over-specified mocks, test doubles, flaky tests and why coverage is not a goal.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "tdd", "software-engineering", "go"]
cover = { image = "/images/covers/eng-testing-pyramid-tdd.png", alt = "The test pyramid and TDD", hiddenInSingle = true }
+++

This post opens the Software Engineering series. Much of this series is judgment rather than syntax, so I will mark opinions as **my opinion** and back every claim about behavior with a real run. Today: how to think about the {{< term "test-pyramid" "test pyramid" >}}, how {{< term "tdd" "TDD" >}} feels in practice, and four ways tests go wrong.

The mechanics of `go test` are in [Testing in Go](/posts/go-testing-basics/), and the service layout I use below is from [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/). Same ideas in [node:test](/posts/node-testing-builtin/) and [Rust testing](/posts/rust-testing-docs/).

> All demos ran on Go 1.26 with `go test -race`, as local examples.

## The pyramid is a cost model

Many unit tests, fewer {{< term "integration-test" "integration tests" >}}, very few end-to-end tests. The reason is cost: the higher a test sits, the slower it runs, the more it needs set up, and the more ways it can fail for unrelated reasons. In the orders domain that means three levels:

- unit: `cart.Total`, a pure function, no I/O;
- integration: `orders.Service` with a fake repository (shown later);
- end-to-end: a real HTTP request against a running stack. I did not run one here.

**My opinion:** put most logic in pure functions and test those heavily, test each seam once with a fake, and keep one or two end-to-end checks for the paths that earn money.

## TDD: red, green, refactor

I grew `Total(items, code)` (prices in cents, discount codes) in small steps. Step 1, a test for an empty cart. Red is a compile error:

```text
cart_test.go:6:14: undefined: Total
```

Returning 0 made it green. Step 2, sum the items; the failure is the right one:

```text
--- FAIL: TestTotalSumsItems (0.00s)
    cart_test.go:16: Total = 0, want 1500
```

A loop fixed it. Step 3, a `SAVE10` code; red (`Total = 1000, <nil>; want 900, nil`), then a hard-coded `if code == "SAVE10"`: green. Step 4, an unknown code must return `ErrUnknownCode`; red, then an `else if`. Step 5, refactor: the `if` chain became a map, plus a `SAVE25` test:

```go
var discounts = map[string]int{"SAVE10": 10, "SAVE25": 25}

percent, ok := discounts[code]
if !ok {
	return 0, ErrUnknownCode
}
return sum * (100 - percent) / 100, nil
```

```text
=== RUN   TestTotalEmpty
--- PASS: TestTotalEmpty (0.00s)
=== RUN   TestTotalSumsItems
--- PASS: TestTotalSumsItems (0.00s)
=== RUN   TestTotalWithDiscountCode
--- PASS: TestTotalWithDiscountCode (0.00s)
=== RUN   TestTotalUnknownCode
--- PASS: TestTotalUnknownCode (0.00s)
=== RUN   TestTotalSecondCode
--- PASS: TestTotalSecondCode (0.00s)
PASS
```

The refactor was safe because the tests existed. **My opinion:** I use TDD for logic with clear rules (pricing, parsing) and not for exploring an unknown API.

## Test doubles: stub, fake, mock

A {{< term "test-double" "test double" >}} replaces a dependency. I wrote one of each for the `Repository` interface (see {{< term "dependency-injection" "dependency injection" >}}):

- **Stub**: canned answers. `failingRepo{err}` returns an error from `Save`; the test checks the service passes it up.
- **Fake**: a working shortcut, here a map. The test places an order and reads it back.
- **Mock**: records calls so the test can verify them. Useful when the call itself is the outcome (an email was sent), risky otherwise.

## An over-specified test

Next to the fake-based test I wrote a mock test that pins the call sequence `[Count Save]`. Both passed. Then I refactored `Place` to generate ids from an in-service counter instead of asking the repository to count (a stand-in for a harmless internal change; I would not ship that design). Behavior did not change:

```text
--- PASS: TestPlaceStoresOrder (0.00s)
--- PASS: TestPlaceReturnsSaveError (0.00s)
    service_test.go:42: calls = [Save], want [Count Save]
--- FAIL: TestPlaceCallSequence (0.00s)
```

The mock test broke, the behavior tests did not. **My opinion:** assert what the caller can observe, not how the code gets there.

## A flaky test

This test assumes 1ms of work never takes more than 1.25ms against a session that really uses `time.Now`:

```go
s := New(1250 * time.Microsecond)
time.Sleep(time.Millisecond) // the "work"
if s.Expired() { t.Fatal("session expired too early") }
```

I ran `go test -count=50` four times on a loaded laptop (load average about 5): 0, 8, 1 and 0 failures. Same code, different results, which is the definition of a {{< term "flaky-test" "flaky test" >}}. The fix is to inject the clock (`New(ttl, now func() time.Time)`) and advance a fake one by hand. Three runs of `-race -count=50` all passed, because nothing depends on the real time anymore.

## Coverage is a signal

```go
func BulkPrice(unit, qty int) int {
	if qty >= 10 {
		return unit * qty * 10 / 100 // bug: should be * 90 / 100
	}
	return unit * qty
}
```

A test that only calls `BulkPrice(100, 1)` and `BulkPrice(100, 10)` without asserting gives `coverage: 100.0% of statements`, and the bug survives. Add one assertion and:

```text
price_test.go:12: BulkPrice(100, 10) = 100, want 900
```

{{< term "code-coverage" "Coverage" >}} tells you what was never executed. It cannot tell you what was verified.

## A few things to watch

- Prefer fakes and stubs; use mocks only when the interaction is the requirement.
- Treat a flaky test as a bug, not as noise. Remove time and randomness through injection.
- Never chase a coverage percentage as a target.
- TDD is a tool; refactoring under green tests is the part I would keep even if I dropped the rest.

## Exercise

Add a `FREESHIP` code that is valid only for totals above 5000 cents, using red-green-refactor. Then write a mock test and a fake test for it, rename an internal helper, and see which one breaks.

## What's next

The next post is “Property-based testing”, where the computer invents the test inputs for us.
