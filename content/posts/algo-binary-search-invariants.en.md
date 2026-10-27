+++
date = '2027-01-10T10:00:00+03:30'
draft = false
title = 'Binary search and invariants'
description = 'Binary search in Go with invariants: LowerBound and UpperBound, real midpoint overflow and off-by-one bugs, exhaustive tests and searching on the answer.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "binary-search", "go", "invariants", "testing"]
cover = { image = "/images/covers/algo-binary-search-invariants.png", alt = "Binary search and invariants", hiddenInSingle = true }
+++

In the previous post, [Heaps and priority queues](/posts/algo-heaps-priority-queues/), I leaned on an invariant to keep the heap correct. {{< term "binary-search" "Binary search" >}} is the algorithm where this habit pays off most: the idea fits in one sentence, yet the code is famous for being written wrong. It works on a sorted slice like in [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), uses [Generics in Go](/posts/go-generics/), and its cost is the logarithm from [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> Go 1.26, local example. The machine was busy, so I publish counts (deterministic) and no timings.

## State the invariant first

An {{< term "invariant" "invariant" >}} is a sentence that stays true on every iteration. I search the half-open interval `[lo, hi)` and write the sentence in the code:

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

At the start nothing is known, so it holds. Each branch moves a boundary past an element it just classified, so it still holds. The interval shrinks, so the loop ends, and then `lo == hi` is exactly the {{< term "lower-bound" "lower bound" >}}. `UpperBound` is the same with `<=`. From the two: first occurrence, last occurrence and `Count = UpperBound - LowerBound`.

```
a = [1 3 3 3 5 8 8 13]
x=3  lower=1 upper=4 first=1 last=3 count=3
x=4  lower=4 upper=4 first=-1 last=-1 count=0
x=8  lower=5 upper=7 first=5 last=6 count=2
```

I can also assert the invariant: a variant checks `a[lo-1] < x` and `a[hi] >= x` before each iteration. Over the cases below it ran 5344 checks and never panicked.

## The standard library

`slices.BinarySearch` returns `(index, found)`, where the index is the lower bound. `sort.Search(n, f)` returns the smallest index where `f` is true, so it is the same idea with your own predicate:

```
x=3  slices.BinarySearch=(1,true)  sort.Search=1
x=4  slices.BinarySearch=(4,false) sort.Search=4
```

## Classic bugs, for real

**Midpoint overflow.** `(lo+hi)/2` adds before it halves. With `int8` and indices 100 and 120, and with `int32`:

```
(lo+hi)/2     = -18 (lo+hi wrapped to -36)
lo+(hi-lo)/2  = 110
int32 (lo+hi)/2    = -97483648
int32 lo+(hi-lo)/2 = 2050000000
```

Go's `int` is 64 bits, so you rarely meet this, but the {{< term "integer-overflow" "overflow" >}} is silent when you do.

**An off-by-one that never ends.** Writing `lo = mid` instead of `lo = mid + 1` can stall. I capped it with a step counter of 1000:

```
x=1 finished=true  steps=3
x=5 finished=false steps=1001
x=6 finished=false steps=1001
```

**A closed interval that misses.** With `[lo, hi]`, the loop must be `lo <= hi`. With `lo < hi` it stops one element early: searching `5` in `[1 3 5]` returned `-1`; the correct version returned `2`.

## Exhaustive testing

Random tests can miss these bugs. Here the input space is small enough to check everything: all sorted arrays of length 0 to 7 over values 0 to 3, and every target from -1 to 4:

```
arrays=330 cases=1980 | LowerBound/Count failures=0 | closedOK failures=0 | broken closed failures=217
first failing case of the broken version: a=[0] target=0
```

The broken version fails on a one-element array. `go test -race` passes too.

## Search on the answer

You can search anything that is monotone: `false false ... true true`. The smallest `n` where `ok(n)` is true, with the invariant "`ok` is false below `lo`, true from `hi`":

```go
func MinTrue(lo, hi int, ok func(int) bool) int {
	for lo < hi {
		mid := lo + (hi-lo)/2
		if ok(mid) { hi = mid } else { lo = mid + 1 }
	}
	return lo
}
```

Ship capacity: packages are shipped in order, one capacity per day. A capacity is feasible if greedy loading needs at most `D` days, and a bigger ship is never worse, so feasibility is monotone. Weights 1 to 10:

```
days=1 -> capacity 55    days=2 -> capacity 28
days=5 -> capacity 15    days=10 -> capacity 10
```

Integer square root: the smallest `k` with `k*k > n`, minus one. My first predicate `k*k > n` overflowed for large `n`; the fix `k > n/k` does not:

```
isqrt(1099511627776)=1048576 naive=546710704328
```

## How many comparisons?

On a sorted slice of n elements, searching for an absent value, I counted evaluations of `a[mid] < x`:

```
n=1000    9    n=10000   13
n=100000  16   n=1000000 19
```

Growing n by 1000 adds about 10 steps: the doubling table from the Big-O post, in reverse.

## A few things to watch

- Write the invariant as a comment before the code.
- Choose `[lo, hi)` or `[lo, hi]` and never mix their conditions.
- Use `lo+(hi-lo)/2`.
- Search with a predicate, then derive "find x" from it.
- The input must really be sorted; I did not test what happens otherwise.

## Exercise

Write `Floor` and `Ceil` for a sorted slice of floats, and the exhaustive test against a linear scan. Then break your code on purpose and read the failing case.

## What's next

Sorting: quick, merge and heap.
