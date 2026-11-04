+++
date = '2027-01-20T10:00:00+03:30'
draft = false
title = 'Sorting: quick, merge and heap'
description = 'Sorting algorithms in Go: quicksort, merge sort and heap sort with exact comparison counts, the O(n^2) worst case, stability and what to use in practice.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "sorting", "go", "quicksort", "merge-sort", "heap-sort"]
cover = { image = "/images/covers/algo-sorting.png", alt = "Sorting: quick, merge and heap", hiddenInSingle = true }
+++

Sorting is something every programmer does every week, usually with a single line, `slices.Sort`. But if you want to know what happens under that line, or understand why some sorts shuffle the order of equal records, you have to look at three classic algorithms up close. A warning to start: give the simplest {{< term "quicksort" "quicksort" >}} (first element as the pivot) 10,000 items that are already sorted and it does about n²/2 comparisons, recursing as deep as the input itself. The same code on random input needs only 156,275 comparisons and depth 31. What changed? Only the order of the input.

In [Binary search and invariants](/posts/algo-binary-search-invariants/) the data was already sorted; here we produce that order ourselves. Three algorithms reach O(n log n) ({{< term "big-o" "Big-O" >}}, as in [Big-O analysis with real measurements](/posts/algo-big-o-measured/)): quicksort, {{< term "merge-sort" "merge sort" >}} and {{< term "heap-sort" "heap sort" >}}. The last one reuses the heap from [Heaps and priority queues](/posts/algo-heaps-priority-queues/). They differ in the worst case, in memory, and in one property that surprises many people: {{< term "stable-sort" "stability" >}}.

> Go 1.27, local example, re-run for this post. I publish no timings. Everything below is deterministic: counts of calls to the `less` comparison function, and allocations. (When I tried to time things in the first run, the 1-minute load average on this machine was 10.61, far above the limit I use for publishing times.)

## Why O(n log n)? A picture

Before the three algorithms, one question: why do they all land on n log n, and not something smaller or larger? The simplest sort, moving each element backwards until it sits in the right place (insertion sort), makes about n²/2 moves in the worst case. The faster algorithms use one trick: **cut the problem in half**. Halve 8 elements once and you have 4 and 4, twice and you have pairs, three times and single elements. So for n elements there are about log₂ n levels; and if each level does linear work over all n elements, the total is n × log₂ n. For a million elements, n log₂ n is about 20 million, while n²/2 would be 500 billion.

Each of the three algorithms implements this idea in its own way. Let us see each on a few small numbers first.

## Quicksort: put one element in its place, split the rest in two

The idea of quicksort: pick one element, the **pivot**. Divide the rest into two groups: smaller than the pivot on the left, larger on the right. Now the pivot sits exactly in its final place. Repeat the same thing on both groups. For example, with pivot 5:

```
[5 8 2 9 1 7 3]
        |
[2 1 3]  5  [8 9 7]      <- 5 is in its final place
```

(In the real implementation the partitioning happens in place and the order inside each group may change; this is only a picture of the idea.) The left and right groups are sorted the same way until we reach single-element groups. If the pivot lands near the middle every time, each level halves the problem and there are log n levels. If the pivot is bad (say, always the smallest), one group stays empty and the work shrinks by only one element; we will get to that.

My version adds a few things. It takes the median of the first, middle and last elements as the pivot (median-of-three), parks it near the end and then partitions. It recurses into the smaller side and loops on the larger one, so the recursion depth is at most log₂ n (each recursive call covers at most half of the range). And ranges of 12 elements or fewer go to insertion sort, which is cheap on small ranges:

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

`partition` returns one index: the final place of the pivot. Then the code recurses into the smaller of the two sides, and for the larger side it just shrinks `a` and lets the loop continue.

## Merge sort: halve, sort, merge

The idea of merge sort: cut the array in half, sort each half, and **merge** the two sorted halves. Merging is easy because both halves are already sorted: look at the front of each, take the smaller one, repeat:

```
left:  [2 5 8]      right: [1 3 9]
compare 2 and 1  -> 1      [2 5 8]  [3 9]
compare 2 and 3  -> 2      [5 8]    [3 9]
compare 5 and 3  -> 3      [5 8]    [9]
compare 5 and 9  -> 5      [8]      [9]
compare 8 and 9  -> 8      []       [9]
leftover         -> 9
result: [1 2 3 5 8 9]
```

Merging needs a helper buffer of size n; in the code it is allocated once at the start and reused at every level. The detail that makes merge sort stable is the strict `<`: when two elements are equal, the left one goes first:

```go
if less(buf[j], buf[i]) { // strict: equal keys take the left one first
	a[k] = buf[j]; j++
} else {
	a[k] = buf[i]; i++
}
```

That is, the right side moves ahead only when it is **strictly** smaller. We will see what "stable" means in the stability section.

## Heap sort: build a heap, bring the largest to the end

The idea of heap sort: turn the array into a **max-heap** (heapify, as in the heap post, but this time the parent is larger than its children), so the largest element is in slot 0. Swap it with the last slot; now the largest is in its final place at the end. Shrink the heap by one and sift the new root down. Repeat. The sorted part grows from the end of the array while the heap shrinks from the front. With five numbers `[4 10 3 5 1]`:

```
heapify:                  [10 5 3 4 1]
swap root with last:      [1 5 3 4 | 10]   sift down -> [5 4 3 1 | 10]
swap root with last:      [1 4 3 | 5 10]   sift down -> [4 1 3 | 5 10]
swap root with last:      [3 1 | 4 5 10]   sift down -> [3 1 | 4 5 10]
swap root with last:      [1 | 3 4 5 10]
```

The `|` marks the border between the heap (left) and the sorted part (right). Heap sort needs no helper buffer: everything happens inside the same array.

## How I tested the implementations

All three are generic and take a `less func(a, b T) bool`; thin wrappers for `cmp.Ordered` types use `cmp.Less`. Each is tested against `slices.Sort` on random, sorted, reversed and duplicate-heavy input (fixed seed, sizes 0 to 5000), plus a descending `less` and a stability test. All pass with `go test -race`.

## Counting comparisons

I sorted the same random numbers with each algorithm and counted calls to `less`. The last column is n × log₂ n itself, for comparison:

```
n         quick        merge        heap         n*log2(n)
1000      10533        8721         16884        9966
10000     144197       120483       235400       132877
100000    1792110      1536402      3019908      1660964
1000000   21623445     18674250     36795744     19931569
```

All three grow like n log n: each time n grows tenfold, the counts grow about 12 to 14 times. Merge sort stays below n log₂ n, quicksort is about 6 to 9 percent above it, and heap sort needs almost twice as many comparisons as merge sort. The reason is visible in the code: each level the root sinks costs two comparisons, one to find the larger child and one to compare it with the element itself. This agrees with the result in the heap post. But a comparison count is not time: it cannot see memory access patterns, so I make no claim about which is fastest.

I also counted allocations with `testing.AllocsPerRun` for n = 10000 (every run includes one allocation for cloning the input):

- quicksort: 1 and heap sort: 1, so they need nothing extra.
- merge sort: 2, which is the helper buffer.

## Quicksort's worst case

Take the simplest quicksort: first element as the pivot and no cutoff. It is fine on random input. On sorted input the pivot is always the smallest element, so the left group stays empty and each partition removes only one element from the work. Instead of log n levels we get n levels. With n = 10,000 and a depth counter (I only counted the depth so that it would not overflow the stack):

```
sorted  comparisons=49995000  n^2/2=50000000  max recursion depth=10000
random  comparisons=156275  n^2/2=50000000  max recursion depth=31
median-of-three quick on the same sorted input: comparisons=107963
```

Line one: on sorted input, almost exactly n²/2 comparisons (49,995,000) and depth 10,000, as deep as the input. Line two: the same code on random input needs 156,275 comparisons and depth 31. Line three: my quicksort with median-of-three on that same sorted input needs only 107,963 comparisons, because the median of three elements of a sorted array is the middle one. But median-of-three is not immune: for any fixed pivot rule, a bad input can be built. That is why libraries usually have a fallback, or a random pivot.

## Stability

A **stable** sort keeps records with equal keys in their input order. Say you sorted a list of emails by time and now sort by sender; with a stable sort, each sender's emails stay ordered by time. I saw this on 12 small records (each record is a numeric key and a letter showing arrival order):

```
input:                   2a 1b 3c 2d 1e 3f 1g 2h 3i 1j 2k 3l 
my merge sort:           1b 1e 1g 1j 2a 2d 2h 2k 3c 3f 3i 3l 
my quicksort (cutoff 12): 1b 1e 1g 1j 2a 2d 2h 2k 3c 3f 3i 3l 
```

In both outputs the records with key 1 stayed in the order `b e g j`, their input order. But an important caveat: my quicksort only looks stable here because 12 elements fall under the cutoff and are sorted by insertion sort, which is stable. A small example lies. So I sorted 200 records with 3 distinct keys and counted the equal-key pairs whose order differed from the input order:

```
my merge sort                      equal-key pairs out of original order: 0
my quicksort                       equal-key pairs out of original order: 100
my heap sort                       equal-key pairs out of original order: 126
sort.Stable                        equal-key pairs out of original order: 0
slices.SortStableFunc              equal-key pairs out of original order: 0
sort.Slice                         equal-key pairs out of original order: 102
slices.SortFunc                    equal-key pairs out of original order: 102
```

Zero means stable. Only my merge sort and the stable functions of the standard library (`sort.Stable` and `slices.SortStableFunc`) keep the order. According to the docs, `sort.Slice` and `slices.SortFunc` are not stable, so whatever order you see from them is accidental and should not be relied on.

## What the standard library does

As far as I know, the `sort` package has used a pattern-defeating quicksort since Go 1.19, a quicksort with defences against bad inputs. I only looked at comparison counts: `sort.Slice` on 100,000 random numbers made 1,739,892 calls to `less`, close to the 1,792,110 comparisons of my quicksort. I did not read the library's source for this post.

## Choosing a sort without surprises

- **Unless you have a reason, call `slices.Sort` or `slices.SortFunc`.** When equal keys must keep their order, for instance sorting by a second key after the first, use `slices.SortStableFunc`.
- **Your comparison function must give a consistent order.** A `less` that is not consistent, for example one written with `<=`, can corrupt the result.
- **A fixed pivot rule has bad inputs.** A random pivot or a fallback is the defence.
- **Merge sort needs O(n) extra memory;** quicksort and heap sort do not.
- **Fewer comparisons does not mean faster.** Measure on your own data before choosing.

## Exercise

Make merge sort do less work: if `!less(a[m], a[m-1])` (the last element of the left half is not greater than the first of the right half, so the two halves are already in order), skip the merge so that sorted input needs about n comparisons. Count the calls to `less` on sorted input before and after, and keep the stability test green.

## What's next

"Search trees and the B-tree". Here we sorted data once; there we see how to keep data ordered while items are being added and removed.
