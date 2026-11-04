+++
date = '2027-02-05T10:00:00+03:30'
draft = false
title = 'The test pyramid and TDD'
description = 'The test pyramid and TDD in Go: red-green-refactor on a real example, over-specified mocks, test doubles, flaky tests and why coverage is not a goal.'
contentType = 'tutorial'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "tdd", "software-engineering", "go"]
cover = { image = "/images/covers/eng-testing-pyramid-tdd.png", alt = "The test pyramid and TDD", hiddenInSingle = true }
+++

Picture a test suite that has gone bad in two different ways at once. After a small internal cleanup that changed no behavior, many tests fail, and you spend the afternoon fixing tests instead of code. Meanwhile a real pricing bug goes to production, even though the report says {{< term "code-coverage" "coverage" >}} is 100%. The first problem makes changing code expensive. The second means the tests are not protecting you.

Both come from the same place: we write tests without asking what each one is for. This post opens the Software Engineering series with a way to think about that. We will look at the {{< term "test-pyramid" "test pyramid" >}}, which is a way to decide how many tests of each kind to write. Then we will look at {{< term "tdd" "TDD" >}} (test-driven development), where you write the test before the code. Finally we will look at four specific ways tests go wrong. I mark my own opinions with **my opinion**, so you can tell them apart from facts.

The mechanics of `go test` are in [Testing in Go](/posts/go-testing-basics/), and the service layout I use below comes from [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/). The same ideas exist in [node:test](/posts/node-testing-builtin/) and [Rust testing](/posts/rust-testing-docs/).

> The demos are local examples in Go. I originally ran them with Go 1.26 and `go test -race`, and I re-ran them with Go 1.27.3 for this edit.

## The pyramid is a cost model

Tests come in different sizes, and each size has a different price. A {{< term "unit-test" "unit test" >}} checks one small piece of logic, such as a function, with no network or disk. An {{< term "integration-test" "integration test" >}} checks that a few pieces work together, for example a service and its storage. An end-to-end test runs the whole system the way a user would, for example by sending a real HTTP request to a running stack.

The test pyramid says: write many unit tests, fewer integration tests, and very few end-to-end tests. The reason is cost. The higher a test sits, the slower it runs, the more setup it needs, and the more ways it can fail for reasons that have nothing to do with the code you changed (a slow network, a leftover record in a database). Here is how the three levels look in a small orders domain:

- **Unit:** `cart.Total`, a pure function. It takes items and a discount code and returns a number. No I/O.
- **Integration:** `orders.Service` working with a fake repository (we will see it later).
- **End-to-end:** a real HTTP request against a running stack. I did not build or run one here.

**My opinion:** put most of the logic in pure functions and test those heavily. Test each connection point between components once, using a fake. Keep one or two end-to-end checks for the paths that make money, such as checkout.

## TDD: red, green, refactor

TDD is a small loop with three steps. **Red:** write a test for behavior that does not exist yet, and watch it fail. **Green:** write the least code that makes it pass. **Refactor:** clean the code up while the tests stay green. Then you repeat, with the next small piece of behavior.

I grew a function `Total(items, code)` this way. Prices are in cents, and a discount code takes a percentage off. Here is how it went.

**Step 1: an empty cart.** I wrote the test first. It cannot even compile, because `Total` does not exist, and that is the first red:

```text
cart_test.go:6:14: undefined: Total
```

Making it return 0 turned it green.

**Step 2: sum the items.** The new test is a pen at 150 times 2 plus a book at 1200, so 1500. The failure is the right kind of failure, because it fails for the reason I want to fix:

```text
--- FAIL: TestTotalSumsItems (0.00s)
    cart_test.go:16: Total = 0, want 1500
```

A simple loop fixed it.

**Step 3: a `SAVE10` code.** Red again: the function ignores the code and returns the full price.

```text
Total = 1000, <nil>; want 900, nil
```

The laziest fix was a hard-coded `if code == "SAVE10"`. That is ugly, but it is green, and green is what this step asks for.

**Step 4: an unknown code must return `ErrUnknownCode`.** Red, then an `else if`.

**Step 5: refactor.** Now the `if` chain bothers me, so I replaced it with a map and added a test for a second code, `SAVE25`:

```go
var discounts = map[string]int{"SAVE10": 10, "SAVE25": 25}

percent, ok := discounts[code]
if !ok {
	return 0, ErrUnknownCode
}
return sum * (100 - percent) / 100, nil
```

Running the tests shows all five passing:

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

The refactor was safe because the tests already existed. If I had broken the discount math while rewriting it, one of these five would have told me within a second. For this post I re-ran the red steps in a scratch copy with Go 1.27.3, and the failure messages above are the ones it printed.

**My opinion:** I use TDD for logic that has clear rules, such as pricing or parsing. I do not use it when I am still exploring an API I do not understand yet, because I would be writing tests for a design I am about to throw away.

## Test doubles: stub, fake, mock

The `orders.Service` does not talk to a real database. It talks to a `Repository` interface, and in tests we hand it something else. Anything that takes the place of a real dependency in a test is called a {{< term "test-double" "test double" >}}. (Handing the dependency in from outside, instead of creating it inside the service, is called {{< term "dependency-injection" "dependency injection" >}}.)

There are three common kinds, and I wrote one of each for the `Repository` interface:

- **Stub:** returns canned answers and has no logic. `failingRepo{err}` always returns an error from `Save`. The test checks that the service passes that error up to its caller.
- **Fake:** a simplified implementation that really works. Mine is a map in memory. The test places an order, then reads it back from the fake and checks the stored total.
- **Mock:** records which calls were made, so the test can verify them afterwards. A mock is useful when the call itself is the outcome you care about, such as "an email was sent". It is risky otherwise, and the next section shows why.

## An over-specified test

Next to the fake-based test I wrote a mock test. It checks that `Place` calls the repository in exactly this order: `[Count Save]`. At that point `Place` asked the repository to count existing orders, to make a new id. Both tests passed.

Then I refactored `Place` so it makes ids from a counter inside the service and no longer asks the repository to count. This stands in for a harmless internal change. I would not ship that design, but it shows the problem well. From the outside, nothing changed: the same order is stored with the same total. Here is the run:

```text
--- PASS: TestPlaceStoresOrder (0.00s)
--- PASS: TestPlaceReturnsSaveError (0.00s)
    service_test.go:42: calls = [Save], want [Count Save]
--- FAIL: TestPlaceCallSequence (0.00s)
```

The two tests that check results still pass. The mock test fails, because it did not check what the code does for the caller. It checked how the code does it. That is what over-specified means: the test is glued to today's implementation, so any cleanup breaks it, even a correct one. After a few of these, people stop refactoring or stop trusting the red.

**My opinion:** assert what the caller can observe, not the path the code takes to get there.

## A flaky test

A {{< term "flaky-test" "flaky test" >}} is a test that sometimes passes and sometimes fails with the same code. Here is a small one. A `Session` expires after a time limit (the ttl), and the test assumes that 1ms of work never takes longer than 1.25ms, against a session that really reads the clock with `time.Now`:

```go
s := New(1250 * time.Microsecond)
time.Sleep(time.Millisecond) // the "work"
if s.Expired() { t.Fatal("session expired too early") }
```

On an idle machine this almost always passes. But `time.Sleep(time.Millisecond)` only promises to sleep at least 1ms. If the machine is busy, it can wake up later than 1.25ms, and the test fails for a reason that has nothing to do with the code.

In the original run I executed `go test -count=50` (which runs the test 50 times) four times on a loaded laptop, with a load average around 5. The failures were 0, 8, 1 and 0. For this edit I ran it three times again and got 1, 0 and 0. The exact numbers change every time, and that is the point: same code, different results.

The fix is to stop depending on real time. We pass the clock in as a parameter, `New(ttl, now func() time.Time)`. Production code passes `time.Now`, and the test passes a fake clock that it moves forward by hand. In the original run, three runs of `-race -count=50` all passed. This time the fixed version passed too (`ok`, 50 runs), because nothing depends on the real time anymore.

## Coverage is a signal

Code coverage reports which lines were executed while the tests ran. It sounds like a measure of quality, but it only measures execution. Here is a function with a bug in it:

```go
func BulkPrice(unit, qty int) int {
	if qty >= 10 {
		return unit * qty * 10 / 100 // bug: should be * 90 / 100
	}
	return unit * qty
}
```

The discount should leave the customer paying 90%, but the code multiplies by 10%. Now take a test that only calls `BulkPrice(100, 1)` and `BulkPrice(100, 10)` and never checks the result. It runs every line, so `go test -cover` prints `coverage: 100.0% of statements`, and the test passes. The bug survives. Now add one assertion and run it again:

```text
price_test.go:12: BulkPrice(100, 10) = 100, want 900
```

The assertion catches it: 10 units at 100 should cost 900, and the function returns 100. So coverage tells you what was never executed, which is useful for finding untested code. It cannot tell you what was actually verified.

## Testing traps

- **Reaching for a mock first.** Prefer fakes and stubs. Use a mock only when the interaction itself is the requirement, because a mock ties the test to the implementation.
- **Ignoring a flaky test.** Treat it as a bug, not as noise. If people learn to re-run until it is green, a real failure will be re-run away too.
- **Chasing a coverage number.** It is fine as a hint to find code nobody tests. As a target it rewards tests that run code without checking anything.
- **Treating TDD as a religion.** It is a tool. If I dropped everything else, I would still keep refactoring under green tests.

## Exercise

Add a `FREESHIP` code that is valid only for totals above 5000 cents, using red-green-refactor. Then write a mock test and a fake test for it. Rename an internal helper and see which of the two breaks.

## What's next

The next post is "Property-based testing". Every input in this post was chosen by hand, which means we only found the bugs we thought of. There the computer invents the inputs.
