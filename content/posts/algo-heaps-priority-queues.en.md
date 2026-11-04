+++
date = '2026-12-31T10:00:00+03:30'
draft = false
title = 'Heaps and priority queues'
description = 'Binary heap and priority queue in Go: a generic Heap[T], heapify vs n pushes, top-K of a stream, container/heap with Fix, and a stable scheduler.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "heap", "priority-queue"]
cover = { image = "/images/covers/algo-heaps-priority-queues.png", alt = "Heaps and priority queues", hiddenInSingle = true }
+++

Imagine you run a hospital emergency room. Patients arrive in some order, but arrival order does not decide who is seen next; how sick they are does. Whenever a doctor becomes free, you must be able to find the most urgent patient among everyone waiting, and new patients keep arriving. The same pattern shows up in programs all the time: the most urgent job, the shortest distance, the highest score. A queue whose order is decided by importance and not by arrival time is called a {{< term "priority-queue" "priority queue" >}}.

[Stacks, queues and deques](/posts/algo-stacks-queues-deques/) only knew arrival order. For a priority queue there are two simple approaches, and both are slow: keep the items unsorted and scan the whole list for the smallest every time (n steps), or keep the list sorted and insert each new item in its place (again up to n moves). The structure that does both jobs in about log n steps is the {{< term "binary-heap" "binary heap" >}}, and almost every priority queue is built on one. A heap lives in a plain slice, the kind we met in [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/). The container uses [Generics in Go](/posts/go-generics/), and costs are stated in {{< term "big-o" "Big-O" >}} like in [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> Go 1.27, local example, re-run for this post. The numbers below are operation counts (calls to the `less` comparison function), so they are deterministic and do not depend on how busy the machine is. I publish no wall-clock times.

## One simple rule: a parent is never larger than its children

A heap is a tree in which every node has at most two children, and it obeys exactly one rule: **every parent is smaller than or equal to both of its children.** Think of this as an {{< term "invariant" "invariant" >}}, something that must stay true at all times. The consequence is that the smallest element is always at the top, because any path from the root downwards can only get larger.

Notice what this does not say. A heap is not sorted. There is no rule between two different branches; only the root is guaranteed. This modest promise is exactly what makes it cheap to maintain.

An example with six numbers:

```
        2
      /   \
     5     3
    / \   /
   9   6 8
```

The nice part is that we need no pointers to store this tree. We write it into an array level by level, left to right:

```
index:  0  1  2  3  4  5
value: [2, 5, 3, 9, 6, 8]
```

The children of slot `i` are at `2i+1` and `2i+2`, and its parent is at `(i-1)/2` (integer division). For example, the children of slot 1 (value 5) are slots 3 and 4 (9 and 6), and the parent of slot 5 (value 8) is slot 2 (value 3). The tree is always "complete": levels fill from the top and the last level fills from the left, so the array never has holes.

One important consequence: a tree with n nodes has about log₂ n levels, around 20 for a million nodes. Anything that walks a single path from the root to a leaf takes about 20 steps at most.

## Adding: sift up

Let us add the number 1 to the heap above. We put it in the first free slot, the end of the array. That may break the rule, but only in one place: between the new number and its parent. So we compare with the parent, swap if the new number is smaller, and keep going up as long as needed:

```
[2, 5, 3, 9, 6, 8, 1]     1 sits in slot 6; parent is slot 2 (value 3): 1 < 3, swap
[2, 5, 1, 9, 6, 8, 3]     now 1 is in slot 2; parent is slot 0 (value 2): 1 < 2, swap
[1, 5, 2, 9, 6, 8, 3]     1 reached the root; done
```

Why is it correct? When the new number swaps with its parent, the parent (which was larger) moves down into the new number's old place. It was already smaller than everything below it, so it still is. The rule stays true at that spot, and at most one level above might be broken again.

## Removing the smallest: sift down

Removing the smallest, the root, leaves a hole at the top. We fill it with the last element of the array, which keeps the shape intact, but now a probably large number sits at the top. It has to sink. Each time it is compared with the **smaller of its two children**, and swapped if it is bigger than that child. Example: remove the root (1) from the heap we just built:

```
[1, 5, 2, 9, 6, 8, 3]     remove 1, move the last element (3) to the root
[3, 5, 2, 9, 6, 8]        children of 3 are 5 and 2; the smaller is 2 and 3 > 2, swap
[2, 5, 3, 9, 6, 8]        now 3 has only the child 8; 3 < 8, done
```

Why the smaller child and not either one? Because that child becomes the parent after the swap, and it must be smaller than its sibling too, or the rule would break.

Both operations walk one root-to-leaf path, so they are O(log n). Looking at the smallest (`Peek`) just reads slot 0 and is O(1).

## The same in Go

The same two moves as code. We take `less` from the caller, so the same heap works as a min-heap, a max-heap or any order you like:

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

`up` swaps while the item is smaller than its parent and stops when it is not (or when it reaches the root). `down` first computes the left child; if there is none, the item is a leaf and nothing is left to do. Then `m` becomes the smaller of the two children (the right child may not exist), and if `m` is not smaller than the item, we stop; otherwise we swap and continue from there. `Push` appends to the slice and calls `up`; `Pop` writes the last element onto the root, shortens the slice by one and calls `down(0)`.

The tests include a property test: 500 random inputs (with many duplicates) are pushed in, popped out and compared with `slices.Sort`. After every step they also check that the parent-child rule holds, and independent heaps are exercised in separate goroutines. All of it passes with `go test -race`.

## Against container/heap

The standard library has a heap too. It asks you to write five methods on your own type, `Len`, `Less`, `Swap`, `Push(any)` and `Pop() any`, and then call `heap.Push`, `heap.Pop`, `heap.Fix` and `heap.Remove`. A small program gave the same 20 random numbers to my heap and to `container/heap` and popped both until empty. The output shows the same order from both:

```
mine: [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
std:  [1 4 5 15 23 28 28 29 35 43 45 50 52 52 53 57 67 68 76 87]
equal: true
```

Both come out sorted, since we always took the smallest. The difference is in use: the standard one boxes values in `any`; mine is typed, but it cannot change the priority of an item already inside the heap. That is where `container/heap` shines (a few sections down).

## Building a heap from an array: heapify

Suppose you have all the data from the start. The simplest approach is n calls to `Push`, which costs O(n log n) in the worst case. There is a better way: {{< term "heapify" "heapify" >}}. Treat the array as a tree as it is, start at the last parent and go backwards, and `down` each one. Because we come from the end, by the time we reach a node its two subtrees are already heaps, so `down` only has to place that one node. The whole job is O(n). The intuition: half of the nodes are leaves and need nothing, a quarter sink at most one level, and so on; very few nodes have a long way to go.

The demo program ran both ways on random numbers and counted calls to `less`:

```
n         heapify      n pushes     ratio
1000      1856         2248         1.21
10000     18778        22509        1.20
100000    188354       228196       1.21
1000000   1882279      2284797      1.21
```

The last column is the ratio of the two before it. Both ways are linear here and the gap is only about 21%, because a random number does not usually rise far after a `Push`. (These numbers come from random data with a fixed seed; other data gives slightly different counts.) The worst case for pushes is descending input: every new number is smaller than all the earlier ones and climbs to the root:

```
1000      heapify 1982      pushes 7987
100000    heapify 199978    pushes 1468946
1000000   heapify 1999974   pushes 17951445
```

Here the difference shows. Heapify stays near 2n (about two million comparisons for a million items), while pushes reach about 18 comparisons per item, close to log n. If you already have all the data, heapify.

## Use one: top-K of a stream

Say a million numbers arrive from a stream and you want only the 10 largest, without keeping them all. The trick is a **min-heap of size K** holding the 10 largest so far. Its root is the smallest of those 10, in other words "the lowest score that still belongs among the biggest". A new number matters only if it is bigger than the root; then the root is dropped and the new number takes its place (one `down`):

```go
func (h *Heap[T]) ReplaceTop(v T) {
	h.data[0] = v
	h.down(0)
}
```

The point is that it is a min-heap even though we want the largest, because we need to find and throw out the weakest member of the group quickly. The demo did this on a million random numbers with K = 10 and compared it with a full sort (`sort.Slice`):

```
N = 1000000 K = 10
max heap size: 10 | heap replaced top 134 times
less calls: heap 654 | full sort 20985383
same top-K: true
```

The second line says the heap never held more than 10 items and the root was replaced only 134 times (most numbers were smaller than the root from the start and were dropped). The third line gives the comparisons: 654 for the heap and about 21 million for sorting everything. The last line says the results are identical. I did not time it; I only counted comparisons.

## Use two: a scheduler, and the problem of equals

Now a simple scheduler: each job has a priority (lower runs first). Eight jobs `a` to `h` were added in that order; `a c e g` have priority 0 and the rest 1. The output is shown for two runs: first by priority only, then with an arrival number added to break ties:

```
tie-break = false [a(p0) e(p0) g(p0) c(p0) b(p1) d(p1) f(p1) h(p1)]
tie-break = true  [a(p0) c(p0) e(p0) g(p0) b(p1) d(p1) f(p1) h(p1)]
```

In the first line the priorities are respected (all the p0s before the p1s), but among equals the order got shuffled: `c` came after `e` and `g` even though it arrived earlier. The reason is that a heap is not {{< term "stable-sort" "stable" >}}: it does not care about equal items, so they may be reordered. The fix is to give every job an arrival number and write `Less` so that, when priorities are equal, the smaller number goes first (`x.Seq < y.Seq`). The second line is the result: among equals, arrival order (FIFO) is back.

## Changing a priority while the item is inside

Sometimes the priority of an item that is already in the heap changes. `container/heap` lets you keep each item's index yourself (updated in `Swap`) and call `heap.Fix(h, i)` after changing its key; `heap.Remove(h, i)` deletes from the middle. Both are O(log n). In the demo, five jobs `a` to `e` were created with priorities 10 to 14, and then the priority of `d` was changed to 1:

```
top before: a
after d.Prio=1 and Fix: d
after Remove(d), rest: [a b c e]
```

Before the change the root was `a` (priority 10). After lowering `d`'s priority to 1 and calling `Fix`, `d` rose to the root. Then we removed `d` from the middle, and the rest came out in the order `a b c e`.

## Heap sort

The same tool gives a sort: heapify, then `Pop` n times. It is O(n log n) and needs no extra structure. But in my count it did more comparisons than `sort.Slice`: 3,019,536 against 1,754,793 for 100,000 numbers (and 16,874 against 10,237 for 1,000). I will look at this properly in the later post "Sorting: quick, merge and heap". And Dijkstra's algorithm, in a later post, will use this same heap.

## What a heap does not promise

- **A heap is not sorted.** Only the root is guaranteed. If you print the whole heap, the slots are not in order; you have to `Pop` one at a time.
- **Searching for an arbitrary value is O(n).** A heap finds only the smallest quickly. For "is 42 in there?" you must scan everything.
- **Equal priorities come out in no promised order.** If arrival order matters, add a sequence number, as in the scheduler section.
- **For the top K largest, use a min-heap of size K,** not a max-heap; the top-K section explains why.
- **A heap is not safe for concurrent use without a lock.** Several goroutines must not `Push` and `Pop` on one heap at the same time.

## Exercise

Add `Fix(i int)` to `Heap[T]` and a map from key to index so you can update an item by its key. Test it against `container/heap` with a property test.

## What's next

"Binary search and invariants". The habit that kept this heap correct, writing down what must always stay true, pays off most there.
