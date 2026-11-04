+++
date = '2027-02-19T10:00:00+03:30'
draft = false
title = 'Property-based testing'
contentType = 'tutorial'
description = 'Property-based testing in Go with testing/quick and rapid: shrinking to a minimal counterexample, model-based tests, a real Dedupe bug and Go fuzzing.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["testing", "property-based-testing", "software-engineering", "go"]
cover = { image = "/images/covers/eng-property-based-testing.png", alt = "Property-based testing", hiddenInSingle = true }
+++

Suppose you write a function `Dedupe` that removes duplicates from a list and keeps the first occurrences in order. You add four tests: an empty list, one element, `[1,1,2]` and `[1,2,3]`. All four pass. You move on. Later you discover that `Dedupe([0 1 0])` still returns `[0 1 0]`. The duplicate is still there, and no test you wrote could have seen it, because no test you wrote contained a duplicate that was not next to its twin.

That is the limit of example tests like the ones in [The test pyramid and TDD](/posts/eng-testing-pyramid-tdd/): they are easy to read, but they only check the cases I thought of. {{< term "property-based-testing" "Property-based testing" >}} turns this around. Instead of writing inputs and expected outputs, I write a rule that must hold for every input, and I let the machine invent the inputs. If it finds an input that breaks the rule, it shows me that input.

The basics of `go test` are in [Testing in Go](/posts/go-testing-basics/). The hash table I test later in the post comes from [A hash table from scratch](/posts/algo-hash-tables/).

> The demos are local examples. I originally ran them with Go 1.26, `go test -race` and `pgregory.net/rapid` v1.3.0. For this edit I re-ran them with Go 1.27.3 and the same rapid version. Anything random (counterexamples, seeds, timings) differs from run to run, and I say so where it matters.

## A property versus an example

An example says: `Reverse([1,2,3])` is `[3,2,1]`. A property says: for any slice `s`, reversing it twice gives back `s`, and the length never changes. The standard library has a small package for this, `testing/quick`:

```go
f := func(s []int) bool { return slices.Equal(Reverse(Reverse(s)), s) }
if err := quick.Check(f, nil); err != nil { t.Error(err) }
```

`quick.Check` calls `f` with many random slices and fails if `f` ever returns false. It passes here. But `testing/quick` has two weaknesses: when a property fails, it does not make the failing input smaller, and you control little about what it generates. So for the rest of the post I use a library called `rapid`. This is a property for a sort function:

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

`Draw` asks rapid for a random slice of ints. Then the test checks three things, and these are the three classic properties of sorting:

- **Ordered:** the result is in order.
- **Same elements:** the result has exactly the elements of the input. I check this by comparing with the standard library's `slices.Sort`.
- **Idempotent:** sorting an already sorted list changes nothing. (Idempotent means that doing it a second time has no further effect.)

Another workhorse is the round trip: encode a value, decode it, and you must get the same value back. I wrote a small encoder for variable-length integers (a "varint" stores small numbers in fewer bytes), and the property is `Decode(Encode(v)) == v` for any `uint64`. Both properties pass. For the sort property rapid reports:

```text
props_test.go:66: [rapid] OK, passed 100 tests (1.389959ms)
```

"Passed 100 tests" means rapid generated 100 random inputs and the property held for each of them. The time in brackets and the line number depend on the run and on the file.

## A bug the examples missed

Back to `Dedupe`. My first version compared each value only with the last one it had kept. That removes `[1,1,2]` correctly, so all four example tests pass, but it does not see a duplicate that is farther away, as in `[0 1 0]`.

The property that catches this has two parts: the output has no duplicates, and nothing was lost from the input. I run it over small ints, so repeats are common. The code in the demo directory is the fixed version of `Dedupe`, so to see the failure I made a scratch copy with the first version (I did not change the demo itself). This is what a run prints:

```text
--- FAIL: TestDedupeProps (0.03s)
    props_test.go:94: [rapid] failed after 0 tests: duplicate 0 in [0 1 0]
        To reproduce, specify -run="TestDedupeProps" -rapid.failfile="testdata/rapid/TestDedupeProps/TestDedupeProps-20261027092037-19116.fail" (or -rapid.seed=11724099063003310201)
    props_test.go:95: [rapid] draw s: []int{0, 1, 0}
```

Line by line: the first line says the property failed, and that the output `[0 1 0]` contains the duplicate `0`. The second line tells me how to replay exactly this failure: a failure file, or a seed. The last line shows the input rapid drew, `[0, 1, 0]`.

That small input is not luck. It is {{< term "shrinking" "shrinking" >}}: when rapid finds a random failing input, it tries smaller variants of it and keeps the smallest that still fails. You get to debug `[0 1 0]` instead of a long random slice. The counterexample itself is random. When I re-ran this with Go 1.27.3 rapid printed `[3 0 3]`, which is the same shape. The numbers change, the shape does not.

Passing the printed `-rapid.seed`, or the `-rapid.failfile`, replays that case. In the original run I tried both and got the same failure; for this edit I replayed the seed twice and again got the same input both times. Commit the `testdata/rapid` file and it becomes a regression test.

One more observation, because it surprised me. With `testing/quick`, 10,000 random `[]int` **passed** the buggy function. Random 64-bit integers almost never repeat, so it never built a list with a duplicate in it. The generator matters as much as the property. I restricted rapid to `IntRange(0, 5)`, so collisions happen all the time. After I switched `Dedupe` to a map of values already seen, the property passed.

## Model-based testing

The same idea works for code that has state, such as a data structure. You run a random sequence of operations on the real thing and on a trivially simple model, and after each step you check that they agree. This is called model-based testing.

My real thing is the open-addressing hash table from the earlier post. The model is Go's built-in `map[int]int`. The operations are `put`, `get` and `delete`, and one more check that `Len` equals the model's length:

```go
t.Repeat(map[string]func(*rapid.T){
	"put":    func(t *rapid.T) { /* m.Put(k,v); model[k]=v */ },
	"delete": func(t *rapid.T) { /* compare return value, then delete(model,k) */ },
	"get":    func(t *rapid.T) { /* compare value and ok */ },
	"":       func(t *rapid.T) { /* m.Len() == len(model) */ },
})
```

(The comments stand for code I left out here; it is in the demo.) rapid picks a random operation, runs it on both, compares, and repeats. The table's real `Delete`, which uses tombstones (a marker that means "something was deleted here"), passes 100 such sequences.

Now the interesting one. That earlier post showed a wrong way to delete, `DeleteNaive`, which simply empties the slot. The model test catches it and shrinks the failure to four steps:

```text
[rapid] failed after 8 tests: Len 2 != model 1
  put k=1; put k=17; delete k=1; put k=17
```

Read it as a story. Keys 1 and 17 land in the same slot, so 17 gets pushed to the next one. Deleting 1 empties the first slot and breaks the chain that leads to 17. The second `put 17` then cannot find the first 17, so it inserts another one. The table now holds two copies, and `Len` says 2 where the model says 1. I would not have written that example by hand.

The shape of the failure varies with the random seed. When I re-ran the naive delete eight times for this edit I got several different small failures, for example "put 7, put 15, delete 7, get 15" where `get 15` returns "not found" even though 15 is in the model. They are all the same bug seen from different sides. I kept the original output above.

## Cases, seeds and fuzzing

By default rapid runs 100 cases per property. `-rapid.checks=10000` ran `TestSort` 10,000 times.

As far as I know, rapid picks a new random seed on every run, so a bug can appear on one run and not on the next. That looks like a {{< term "flaky-test" "flaky test" >}}, but it is not noise: it is a real bug that was found by luck. When it appears, keep the printed seed or the failfile so you can reproduce it. If you want fully deterministic runs, for example in CI, pin `-rapid.seed`.

Go also has its own {{< term "fuzzing" "fuzzing" >}}, which is related but not the same. A fuzzer is guided by code coverage (it keeps inputs that reach new code) and runs until you stop it. `go test -fuzz FuzzEncodeDecode -fuzztime 5s` on the varint round trip did 512,551 executions in the original run and found nothing. In my re-run it did 456,106 executions, also finding nothing; the count depends on the machine and its load. Fuzzing shines on parsers. Its security side comes in a later post, "Fuzzing to find security bugs". Python's Hypothesis is the same idea as rapid; I did not run it here.

## Writing properties that catch bugs

- **The property is the hard part.** If a property just re-implements the code under test, it proves nothing. Prefer round trips, invariants (things that must always be true) and a simple model.
- **Look at what the generator produces.** Does it produce empty inputs, duplicates, huge values, Unicode (`rapid.String()`)? Our `testing/quick` run passed a buggy function because its inputs never repeated.
- **Keep the property fast and deterministic inside.** No clock and no network. The randomness should come only from the generator.
- **My opinion:** it is not worth it for glue code, UI or simple CRUD. A few examples are clearer there. I use it for parsers, encoders, data structures and money math.

## Exercise

Write a property for `slices.Compact` and one for a `Max` function. Then plant a bug in each and see which property fails first.

## What's next

The next post is "Refactoring safely". The tests we wrote here are the kind that make it possible to change code without being afraid of it.
