+++
date = '2027-02-19T10:00:00+03:30'
draft = false
title = 'Property-based testing'
description = 'Property-based testing in Go with testing/quick and rapid: shrinking to a minimal counterexample, model-based tests, a real Dedupe bug and Go fuzzing.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "property-based-testing", "software-engineering", "go"]
cover = { image = "/images/covers/eng-property-based-testing.png", alt = "Property-based testing", hiddenInSingle = true }
+++

In [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/) every test was an example: one input, one expected output. Examples are easy to read, but they only check the cases I thought of. {{< term "property-based-testing" "Property-based testing" >}} states a rule that must hold for all inputs and lets the machine invent the inputs. The basics of `go test` are in [Testing in Go](/posts/go-testing-basics/), and the table I test below is from [A hash table from scratch](/posts/algo-hash-tables/).

> Demos ran on Go 1.26 with `go test -race` and `pgregory.net/rapid` v1.3.0, as local examples.

## A property versus an example

Example: `Reverse([1,2,3]) == [3,2,1]`. Property: for any slice `s`, `Reverse(Reverse(s))` equals `s` and the length is unchanged. The stdlib has `testing/quick`:

```go
f := func(s []int) bool { return slices.Equal(Reverse(Reverse(s)), s) }
if err := quick.Check(f, nil); err != nil { t.Error(err) }
```

It passes, but `testing/quick` cannot shrink a failure and you control little. I use `rapid` for the rest:

```go
rapid.Check(t, func(t *rapid.T) {
	s := rapid.SliceOf(rapid.Int()).Draw(t, "s")
	got := InsertionSort(s)
	if !slices.IsSorted(got) { t.Fatal("not ordered") }
	want := slices.Clone(s); slices.Sort(want)
	if !slices.Equal(got, want) { t.Fatal("different elements") }
	if !slices.Equal(InsertionSort(got), got) { t.Fatal("not idempotent") }
})
```

Those are the three classic sort properties: ordered, same elements, idempotent. A round trip is the other workhorse: `Decode(Encode(v)) == v` for any `uint64` against my hand-written varint. Both pass:

```text
props_test.go:57: [rapid] OK, passed 100 tests
```

## A bug the examples missed

`Dedupe` should remove duplicates and keep the first occurrences in order. My first version compared each value only with the previous kept one. The example tests (`nil`, `[1]`, `[1,1,2]`, `[1,2,3]`) all pass. The property "no duplicates in the output, and nothing lost" over small ints finds it:

```text
--- FAIL: TestDedupeProps (0.03s)
    props_test.go:94: [rapid] failed after 0 tests: duplicate 0 in [0 1 0]
        To reproduce, specify -run="TestDedupeProps" -rapid.failfile="testdata/rapid/TestDedupeProps/TestDedupeProps-20261027092037-19116.fail" (or -rapid.seed=11724099063003310201)
    props_test.go:95: [rapid] draw s: []int{0, 1, 0}
```

That is the {{< term "shrinking" "shrinking" >}}: rapid reduced a random failing slice to `[0 1 0]`, the smallest input that still fails. Passing the printed `-rapid.seed` or `-rapid.failfile` reruns exactly that case (I ran both and got the same failure). Commit the `testdata/rapid` file as a regression test.

Notice that `testing/quick` with 10,000 random `[]int` **passed** the buggy function: random 64-bit ints almost never repeat, so it never built a duplicate. The generator matters; I restricted rapid to `IntRange(0, 5)` so collisions are common. After switching to a `seen` map, the property passes.

## Model-based testing

For stateful code, run random sequences of operations on the real thing and on a trivial model. My open-addressing table against a `map[int]int`, with `put`, `get`, `delete` and a check that `Len` matches:

```go
t.Repeat(map[string]func(*rapid.T){
	"put":    func(t *rapid.T) { /* m.Put(k,v); model[k]=v */ },
	"delete": func(t *rapid.T) { /* compare return value, then delete(model,k) */ },
	"get":    func(t *rapid.T) { /* compare value and ok */ },
	"":       func(t *rapid.T) { /* m.Len() == len(model) */ },
})
```

The table's `Delete` (tombstones) passes 100 sequences. The `DeleteNaive` from that post, which I had shown as the wrong way, fails and shrinks to four steps:

```text
[rapid] failed after 8 tests: Len 2 != model 1
  put k=1; put k=17; delete k=1; put k=17
```

Keys 1 and 17 collide, deleting 1 breaks the probe chain, and the second `put 17` inserts a duplicate. I would not have written that example by hand.

## Cases, seeds and fuzzing

The default is 100 cases per property; `-rapid.checks=10000` ran `TestSort` 10,000 times. As far as I know rapid picks a fresh random seed each run, so a bug can show up only on some runs. That looks like a {{< term "flaky-test" "flaky test" >}} but is a real bug: keep the printed seed or failfile to reproduce it. Pin `-rapid.seed` in CI if you want fully deterministic runs.

Go's own {{< term "fuzzing" "fuzzing" >}} is related but different: coverage-guided and runs until stopped. `go test -fuzz FuzzEncodeDecode -fuzztime 5s` on the varint round trip did 512,551 executions and found nothing. It shines on parsers; the security angle comes in a later post, “Fuzzing to find security bugs”. Python's Hypothesis is the same idea; I did not run it.

## A few things to watch

- Writing the property is the hard part. If it just re-implements the code, it proves nothing; prefer round trips, invariants and a simple model.
- Check what your generator produces (empty, duplicates, huge values, unicode via `rapid.String()`), not only that it runs.
- Keep properties fast and deterministic inside; no clock, no network.
- **My opinion:** not worth it for glue code, UI or simple CRUD; a few examples are clearer. Use it for parsers, encoders, data structures and money math.

## Exercise

Write a property for `slices.Compact` and one for a `Max` function, then plant a bug and see which fails first.

## What's next

Next: “Refactoring safely”, where these tests become the safety net.
