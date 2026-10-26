+++
date = '2026-12-31T10:00:00+03:30'
draft = false
title = 'Heaps and priority queues'
description = 'Binary heap and priority queue in Go: a generic Heap[T], heapify vs n pushes, top-K of a stream, container/heap with Fix, and a stable scheduler.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "heap", "priority-queue"]
cover = { image = "/images/covers/algo-heaps-priority-queues.png", alt = "Heaps and priority queues", hiddenInSingle = true }
+++

In the previous post, [Stacks, queues and deques](/posts/algo-stacks-queues-deques/), items left in the order they arrived. Often that is wrong: you want the most urgent job, the smallest distance, the biggest score. That is a {{< term "priority-queue" "priority queue" >}}, and almost always it is built on a {{< term "binary-heap" "binary heap" >}}. The heap lives in a plain slice, as in [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), the container uses [Generics in Go](/posts/go-generics/), and costs are stated in {{< term "big-o" "Big-O" >}} like in [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> Go 1.26, local example. I publish operation counts (calls to `less`), which are deterministic, and no wall-clock times.

## A heap in a slice

A heap is a complete binary tree where no parent is larger than its children (a min-heap). No pointers are needed: the children of index `i` are `2i+1` and `2i+2`, the parent is `(i-1)/2`. The smallest item is always at index 0. `Push` appends and sifts up; `Pop` moves the last item to the root and sifts down:

```go
func (h *Heap[T]) up(i int) {
	for i > 0 {
		p := (i - 1) / 2
		if !h.less(h.data[i], h.data[p]) {
			break
		}
		h.data[i], h.data[p] = h.data[p], h.data[i]
		i = p
	}
}

func (h *Heap[T]) down(i int) {
	n := len(h.data)
	for {
		l := 2*i + 1
		if l >= n {
			return
		}
		m := l
		if r := l + 1; r < n && h.less(h.data[r], h.data[l]) {
			m = r
		}
		if !h.less(h.data[m], h.data[i]) {
			return
		}
		h.data[i], h.data[m] = h.data[m], h.data[i]
		i = m
	}
}
```

`Heap[T]` takes a `less func(a, b T) bool`. Both operations walk one root-to-leaf path, so they are O(log n); `Peek` is O(1). The tests include a property test: 500 random inputs (with many duplicates) pushed in, popped out, and compared with `slices.Sort`, plus an invariant check after every step and independent heaps in goroutines. They pass with `go test -race`.

## Against container/heap

The standard library wants you to implement `Len`, `Less`, `Swap`, `Push(any)` and `Pop() any` on your own type, then call `heap.Push`, `heap.Pop`, `heap.Fix` and `heap.Remove`. I fed 20 random numbers to both:

```
mine: [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
std:  [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
equal: true
```

Same order. The standard one boxes values in `any`; mine is typed but cannot update an item in place, which is where `container/heap` shines (below).

## Heapify beats n pushes

Building a heap from n items with n pushes costs O(n log n) in the worst case. {{< term "heapify" "Heapify" >}} sifts down from the last parent and is O(n). Counting `less` calls on random data:

```
n         heapify      n pushes     ratio
1000      1856         2248         1.21
10000     18778        22509        1.20
100000    188354       228196       1.21
1000000   1882279      2284797      1.21
```

Both are linear here: pushes of random data rarely sift far, so the gap is only 21%. The worst case for a min-heap is descending input:

```
1000      heapify 1982      pushes 7987
100000    heapify 199978    pushes 1468946
1000000   heapify 1999974   pushes 17951445
```

Heapify stays near 2n; pushes reach about 18 per item at a million. If you have all the data, heapify.

## Top-K of a stream

Keep the 10 largest of a million numbers without storing them: a min-heap of size K whose root is the smallest of the current top K. A new value replaces the root only if it is bigger:

```
N = 1000000 K = 10
max heap size: 10 | heap replaced top 134 times
less calls: heap 654 | full sort 20985383
same top-K: true
```

The heap never held more than 10 items and used 654 comparisons; sorting everything took about 21 million (`sort.Slice`). The result is identical. I did not time it.

## A scheduler and the tie-break

Jobs have a priority (lower runs first). Eight jobs `a..h`, with priority 0 for `a c e g` and 1 for the rest, pushed in that order:

```
tie-break = false [a(p0) e(p0) g(p0) c(p0) b(p1) d(p1) f(p1) h(p1)]
tie-break = true  [a(p0) c(p0) e(p0) g(p0) b(p1) d(p1) f(p1) h(p1)]
```

Without a tie-break, `c` ran after `g`: a heap is not stable. Adding a sequence number (`x.Seq < y.Seq` when priorities are equal) restores FIFO among equals.

## Changing a priority

`container/heap` lets you keep each item's index and call `heap.Fix(h, i)` after changing its key; `heap.Remove(h, i)` deletes from the middle. Both are O(log n):

```
top before: a
after d.Prio=1 and Fix: d
after Remove(d), rest: [a b c e]
```

## Heap sort

Heapify, then pop n times. It is O(n log n) with no extra structure, but in my count it did more comparisons than `sort.Slice`: 3,019,536 against 1,754,793 for 100,000 numbers. I'll cover this properly in the later post "Sorting: quick, merge and heap". And Dijkstra's algorithm, in a later post, will use this heap.

## A few things to watch

- A heap is not sorted; only the root is guaranteed.
- Searching for an arbitrary value is O(n).
- Equal priorities come out in no promised order: add a sequence number.
- For top-K of the largest, use a min-heap of size K.
- Heaps are not safe for concurrent use without a lock.

## Exercise

Add `Fix(i int)` to `Heap[T]` and an index map so you can update an item by key. Test it against `container/heap` with a property test.

## What's next

Binary search and invariants.
