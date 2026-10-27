+++
date = '2027-01-20T10:00:00+03:30'
draft = false
title = 'Sorting: quick, merge and heap'
description = 'Sorting algorithms in Go: quicksort, merge sort and heap sort with exact comparison counts, the O(n^2) worst case, stability and what to use in practice.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "sorting", "go", "quicksort", "merge-sort", "heap-sort"]
cover = { image = "/images/covers/algo-sorting.png", alt = "Sorting: quick, merge and heap", hiddenInSingle = true }
+++

In the previous post, [Binary search and invariants](/posts/algo-binary-search-invariants/), the data was already sorted. Now we produce that order. Three classic algorithms give O(n log n) ({{< term "big-o" "Big-O" >}}, as in [Big-O analysis with real measurements](/posts/algo-big-o-measured/)): {{< term "quicksort" "quicksort" >}}, {{< term "merge-sort" "merge sort" >}} and {{< term "heap-sort" "heap sort" >}}. The last one reuses the heap from [Heaps and priority queues](/posts/algo-heaps-priority-queues/). They differ in worst case, memory and one property that surprises people: {{< term "stable-sort" "stability" >}}.

> Go 1.26, local example. When I wanted to time things, the 1-minute load average on this machine was 10.61, far above my limit of 2.0, so I publish no nanoseconds. Everything below is deterministic: counts of calls to `less`, and allocations.

## The three implementations

All three are generic and take `less func(a, b T) bool`; thin wrappers use `cmp.Less` for `cmp.Ordered` types. Each is tested against `slices.Sort` on random, sorted, reverse-sorted and many-duplicate inputs (fixed seed, sizes 0 to 5000), plus a descending-order `less` and a stability test. They pass with `go test -race`.

Quicksort picks the median of the first, middle and last items as pivot and parks it before the end, then partitions. It recurses into the smaller side and loops on the larger, so the stack depth stays at most log2 n, and ranges of 12 items or fewer go to insertion sort:

```go
func Quick[T any](a []T, less func(x, y T) bool) {
	for len(a) > cutoff {
		p := partition(a, less)
		if p < len(a)-p-1 {
			Quick(a[:p], less)
			a = a[p+1:]
		} else {
			Quick(a[p+1:], less)
			a = a[:p]
		}
	}
	insertion(a, less)
}
```

Merge sort splits in half, sorts both halves, and merges them through one buffer of size n allocated up front. The one-character detail that makes it stable is the strict `<`: on a tie the left item goes first:

```go
if less(buf[j], buf[i]) { // strict: equal keys take the left one first
	a[k] = buf[j]; j++
} else {
	a[k] = buf[i]; i++
}
```

Heap sort builds a max-heap with heapify, then swaps the root to the end and sifts down, n-1 times. No buffer.

## Counting comparisons

I sorted the same random integers with each algorithm and counted `less` calls:

```
n         quick        merge        heap         n*log2(n)
1000      10533        8721         16884        9966
10000     144197       120483       235400       132877
100000    1792110      1536402      3019908      1660964
1000000   21623445     18674250     36795744     19931569
```

All three grow like n log n. Merge sort stays below n log2 n, quicksort lands 5 to 9% above it, and heap sort needs almost twice as many comparisons as merge sort. That matches the heap sort result of the previous post. Counts are not time, though: they ignore memory access patterns, so I make no claim about which is fastest.

Allocations, measured with `testing.AllocsPerRun` at n = 10000 (each run includes one allocation for cloning the input): quicksort 1 and heap sort 1, so zero extra; merge sort 2, the buffer.

## The quicksort worst case

Take the simplest quicksort: first element as pivot, no cutoff. On random input it is fine. On already sorted input every partition removes only one item. With n = 10,000 and a depth counter (I measured it rather than risk a stack overflow):

```
sorted  comparisons=49995000  n^2/2=50000000  max recursion depth=10000
random  comparisons=156275  n^2/2=50000000  max recursion depth=31
median-of-three quick on the same sorted input: comparisons=107963
```

Sorted input gives about n^2/2 comparisons and a recursion as deep as the input; the same code on random input needs 156,275 comparisons and depth 31. Median-of-three handles the sorted case with 107,963. It is not immune: adversarial inputs exist for any fixed pivot rule, which is one reason libraries add fallbacks.

## Stability

I sorted 200 records with 3 distinct keys and counted pairs of equal keys that ended up in a different order than they arrived:

```
my merge sort                      equal-key pairs out of original order: 0
my quicksort                       equal-key pairs out of original order: 100
my heap sort                       equal-key pairs out of original order: 126
sort.Stable                        equal-key pairs out of original order: 0
slices.SortStableFunc              equal-key pairs out of original order: 0
sort.Slice                         equal-key pairs out of original order: 102
slices.SortFunc                    equal-key pairs out of original order: 102
```

Only merge sort and the standard stable functions keep order. Note that `sort.Slice` and `slices.SortFunc` are not stable by documentation, so any order you see from them is accidental. (With only 12 records my quicksort looked stable, because ranges under the cutoff use insertion sort, which is stable. Small examples lie.)

## What the standard library does

According to the Go docs and source, `sort.Slice` and `slices.Sort` use a pattern-defeating quicksort since Go 1.19. I counted `sort.Slice` on 100,000 random numbers: 1,739,892 calls to `less`, close to my 1,792,110 for quicksort.

## A few things to watch

- Use `slices.Sort` or `slices.SortFunc` unless you have a reason; use `slices.SortStableFunc` when equal keys must keep their order, for example sorting by a second key after a first.
- Your comparison must be a consistent ordering. A `less` that is not, such as one using `<=`, can break the result.
- A fixed pivot rule has bad inputs; random pivots or fallbacks are the defense.
- Merge sort costs O(n) extra memory; quicksort and heap sort do not.
- Fewer comparisons does not mean faster. Measure on your data before choosing.

## Exercise

Make the merge sort do one thing less: skip the merge when `!less(a[m], a[m-1])`, so already sorted input costs about n comparisons. Count `less` calls on sorted input before and after, and keep the stability test green.

## What's next

Search trees and the B-tree.
