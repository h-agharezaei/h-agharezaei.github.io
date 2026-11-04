+++
date = '2027-01-10T10:00:00+03:30'
draft = false
title = 'Binary search and invariants'
description = 'Binary search in Go with invariants: LowerBound and UpperBound, real midpoint overflow and off-by-one bugs, exhaustive tests and searching on the answer.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "binary-search", "go", "invariants", "testing"]
cover = { image = "/images/covers/algo-binary-search-invariants.png", alt = "Binary search and invariants", hiddenInSingle = true }
+++

A simple game: I think of a number between 1 and 100 and you have to guess it. After each guess I only say "higher" or "lower". If you start at 1 and go one by one, it might take 100 guesses. But if you always guess the middle of what is left, every answer crosses out half of the possibilities and at most 7 guesses are enough. That is {{< term "binary-search" "binary search" >}}: on sorted data, look at the middle and throw away the half that cannot hold the answer.

The idea fits in one sentence, yet the code is famous for being written wrong. For example, search for `5` in `[1 3 5]` with a "closed interval" and the loop condition `lo < hi`, and you get `-1`, even though `5` is right there. The cure is the habit that kept the heap correct in [Heaps and priority queues](/posts/algo-heaps-priority-queues/): before writing code, write the {{< term "invariant" "invariant" >}}, a sentence that must stay true on every iteration of the loop. The search works on a sorted slice like in [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), uses [Generics in Go](/posts/go-generics/), and its cost is the logarithm from [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> Go 1.27, local example, re-run for this post. The machine was busy, so I publish counts (deterministic) and no timings.

## State the invariant first

The trouble with binary search is not the idea, it is the boundaries. What does the interval include? After a comparison, do I move the boundary to `mid` or to `mid + 1`? The answers do not come from guessing; they come from one sentence written before the code.

I search the half-open interval `[lo, hi)`, which means `lo` is inside the interval and `hi` is not. What we want to find is the {{< term "lower-bound" "lower bound" >}}: the index of the first element that is **greater than or equal to** `x` (the length of the array if there is none). The sentence we keep true, the invariant, is:

> Every slot before `lo` is smaller than `x`. Every slot from `hi` onwards is greater than or equal to `x`. Only `[lo, hi)` is still unknown.

And the code, with the same sentence as a comment:

```go
// Invariant: a[i] < x for every i < lo; a[i] >= x for every i >= hi.
// The unknown part is [lo, hi).
func LowerBound[T cmp.Ordered](a []T, x T) int {
	lo, hi := 0, len(a)
	for lo < hi {
		mid := lo + (hi-lo)/2
		if a[mid] < x {
			lo = mid + 1
		} else {
			hi = mid
		}
	}
	return lo // lo == hi: nothing unknown is left
}
```

First a hand trace. In `a = [1 3 3 3 5 8 8 13]` we look for `x = 5`:

```
lo=0 hi=8  mid=4  a[4]=5  is 5 < 5? no  -> hi = 4   (from slot 4 on, everything is >= 5)
lo=0 hi=4  mid=2  a[2]=3  is 3 < 5? yes -> lo = 3   (slots 0 to 2 are < 5)
lo=3 hi=4  mid=3  a[3]=3  is 3 < 5? yes -> lo = 4
lo=4 hi=4  the loop ends; the answer is 4
```

Why is it correct? We check three things:

- **Start:** `lo = 0` and `hi = len(a)`. There are no slots before `lo` and none from `hi` on, so the sentence is true, trivially.
- **Each iteration:** if `a[mid] < x`, then because the array is sorted every slot up to `mid` is also smaller, so `lo = mid + 1` keeps the sentence true. Otherwise `a[mid] >= x` and every slot after it is too, so `hi = mid` keeps it true. In both cases the unknown interval gets smaller.
- **End:** the interval shrinks, so the loop stops, and at that moment `lo == hi`. The sentence says every slot before `lo` is smaller and every slot from `lo` on is greater or equal. So `lo` is exactly the first element `>= x`.

No clever proof is needed; you just have to have written the sentence down. `UpperBound` is the same code with `<=` instead of `<`; it gives the index of the first element **greater** than `x`. From the two we get the first occurrence, the last occurrence and the number of repeats (`Count = UpperBound - LowerBound`). The demo ran them on the array above:

```
a = [1 3 3 3 5 8 8 13]
x=3  lower=1 upper=4 first=1 last=3 count=3
x=4  lower=4 upper=4 first=-1 last=-1 count=0
x=8  lower=5 upper=7 first=5 last=6 count=2
```

For `x=3` there are three 3s in slots 1 to 3: `lower=1` is the first, `upper=4` is the slot after the last, and `count = 4 - 1 = 3`. For `x=4`, which is not in the array, `lower` and `upper` are both 4, meaning "if you inserted 4, it would go to slot 4", and the count is zero. `first` and `last` return `-1` for an absent value.

The invariant can also be checked while running. A variant of `LowerBound` verifies before every iteration that `a[lo-1] < x` and `a[hi] >= x`, and panics otherwise. Over all the cases in the "Exhaustive testing" section below it ran 5,344 checks and never panicked.

## The standard library

You do not always have to write it yourself. `slices.BinarySearch` returns `(index, found)`, where the index is the lower bound and `found` says whether `x` itself is there. `sort.Search(n, f)` returns the smallest index where `f` is true, so it is the same idea with your own condition:

```
x=3  slices.BinarySearch=(1,true)  sort.Search=1
x=4  slices.BinarySearch=(4,false) sort.Search=4
```

Both gave index 1 for `x=3` and index 4 for `x=4`, which is absent; only `BinarySearch` also says `false` explicitly.

## Classic bugs, for real

For each one I ran code that really contains the mistake.

**Midpoint overflow.** `(lo+hi)/2` adds first and halves afterwards. If `lo + hi` exceeds the largest value of the type, the sum wraps around to a negative number. With `int8` and indices 100 and 120, and with `int32` and indices two billion and 2.1 billion:

```
(lo+hi)/2     = -18 (lo+hi wrapped to -36)
lo+(hi-lo)/2  = 110
int32 (lo+hi)/2    = -97483648
int32 lo+(hi-lo)/2 = 2050000000
```

100 + 120 wraps to -36 in `int8`, and half of that is -18, an index that does not exist. The form `lo+(hi-lo)/2` never exceeds `hi`, so it cannot overflow, and it returns the right answer, 110. On 64-bit platforms Go's `int` is 64 bits, so you rarely reach this limit, but when you do the {{< term "integer-overflow" "overflow" >}} is silent, so write the safe form from the start.

**An off-by-one that never ends.** Writing `lo = mid` instead of `lo = mid + 1` can stall the loop forever. Let us see why, on `[1 3 5 7 9]` with `x = 5` and the bound `hi = len-1`: `lo=0, hi=4` -> `mid=2`, `a[2]=5` is not smaller -> `hi=2`. Then `lo=0, hi=2` -> `mid=1`, `3 < 5` -> `lo=1`. Then `lo=1, hi=2` -> `mid=1`, again `3 < 5` -> `lo=mid=1`: nothing changed, so it spins here forever. I capped the program with a step counter of 1000 so it would not hang:

```
x=1 finished=true  steps=3
x=5 finished=false steps=1001
x=9 finished=false steps=1001
x=6 finished=false steps=1001
```

`x=1` finishes by luck, because `lo` never needs to move forward. The others hit the 1001-step cap, which means they never finish.

**A closed interval that skips an element.** When the interval is `[lo, hi]` and `hi` is included, the loop condition must be `lo <= hi`. With `lo < hi`, when a single element is left, the loop stops right there and never looks at it. That is the example from the start of the post: searching `5` in `[1 3 5]` returned `-1` with the broken version and `2` with the correct one.

## Exhaustive testing

A random test might miss these bugs. Here the input space is small enough to check everything: all sorted arrays of length 0 to 7 with values from 0 to 3, and every target from -1 to 4. Each result is compared with a linear search:

```
arrays=330 cases=1980 | LowerBound/Count failures=0 | closedOK failures=0 | broken closed failures=217
first failing case of the broken version: a=[0] target=0
```

330 arrays and 1,980 cases, and the correct code never failed once. The broken closed version failed in 217 cases, and its first failure was already on the one-element array `[0]` with target `0` (the loop is never entered). `go test -race` passes too. This kind of test means you no longer have to wonder whether some small special case slipped through.

## Search on the answer

The idea of binary search is not limited to arrays. You can search anything that is **monotone**, a sequence of the form `false false ... false true true ... true`. If you can write a condition that is false for small values and true from some point on, the same loop finds the smallest value that makes it true. The invariant: "`ok` is false below `lo` and true from `hi` on":

```go
func MinTrue(lo, hi int, ok func(int) bool) int {
	for lo < hi {
		mid := lo + (hi-lo)/2
		if ok(mid) { hi = mid } else { lo = mid + 1 }
	}
	return lo
}
```

It is `LowerBound` again, with `a[mid] < x` replaced by `!ok(mid)`.

**First example: ship capacity.** Packages with given weights must be shipped **in order** by one ship. Each day the ship carries up to some capacity. We want the smallest capacity that gets everything delivered in at most `D` days. A specific capacity is "feasible" if greedy loading (each day, load as much as fits) needs at most `D` days. A bigger ship is never worse, so feasibility is monotone and binary search on the capacity works. The answer lies between the heaviest package (anything smaller cannot carry it at all) and the sum of all weights (one day). With weights 1 to 10:

```
days=1 -> capacity 55    days=2 -> capacity 28
days=5 -> capacity 15    days=10 -> capacity 10
```

One day means everything in a single load: 1+2+...+10 = 55. Ten days means one package per day, so the heaviest package (10) is enough. Two and five days fall between the two.

**Second example: integer square root.** The floor of the square root of `n` is "the smallest `k` with `k*k > n`, minus one". For `n=16`, the smallest `k` with `k*k > 16` is 5, so the answer is 4. But my first version, the predicate `k*k > n`, overflowed for a large `n`, because `k*k` exceeds the largest `int`. The fix is `k > n/k` (equivalent for `k >= 1` with integer division), which cannot overflow. For `n = 2^40`:

```
isqrt(1099511627776)=1048576 naive=546710704328
```

The right answer is 1,048,576 (2 to the power 20). The naive version returned the unrelated 546,710,704,328, because its comparisons ran on overflowed numbers. For small inputs (0, 1, 15, 16, 17, 99, 100) both were correct, so small tests alone would not have shown this bug.

## How many comparisons?

On a sorted slice of n elements, searching for a value that is absent (larger than everything), I counted evaluations of `a[mid] < x`. The program also printed `ceil(log2(n+1))`, the upper limit on the number of iterations:

```
n=1000    9    n=10000   13
n=100000  16   n=1000000 19
```

The limits for these four n are 10, 14, 17 and 20; the counts are one below. Growing n by a factor of 1000 adds about 10 steps: the doubling table from the Big-O post, in reverse. For a million elements, nineteen comparisons were enough.

## Rules that prevent off-by-one bugs

- **Write the invariant as a comment before the code.** Every `+ 1` and every `<=` should be explainable from that sentence.
- **Choose `[lo, hi)` or `[lo, hi]` and never mix their conditions.** Half-open: `lo < hi`, `hi = mid`. Closed: `lo <= hi`, `hi = mid - 1`.
- **Use `lo+(hi-lo)/2`** so overflow cannot reach you.
- **Search with a predicate** and derive "find x" from it, instead of writing several similar loops.
- **The input must really be sorted.** I did not test what happens otherwise.

## Exercise

Write `Floor` and `Ceil` for a sorted slice of floats (the largest element less than or equal, and the smallest element greater than or equal), and an exhaustive test against a linear scan. Then break your code on purpose and read the failing case.

## What's next

"Sorting: quick, merge and heap". In this post the data was already sorted; next we produce that order ourselves.
