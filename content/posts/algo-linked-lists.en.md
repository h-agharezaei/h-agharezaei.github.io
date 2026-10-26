+++
date = '2026-12-07T10:00:00+03:30'
draft = false
title = 'Linked lists and why they are rarely the answer'
description = 'Linked list in Go: a generic List[T], node memory overhead, allocation counts, cache locality measured against a slice, and where an LRU cache fits.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "linked-list", "cache"]
cover = { image = "/images/covers/algo-linked-lists.png", alt = "Linked lists and why they are rarely the answer", hiddenInSingle = true }
+++

In the previous post, [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), the array won on almost every count. The textbook rival is the {{< term "linked-list" "linked list" >}}: constant-time insertion, no copying on growth. So why do people reach for it so rarely? This time I measured. We use [Generics in Go](/posts/go-generics/) for the container, the memory side is in [Pointers and the memory model in Go](/posts/go-pointers-memory/), and the one place a list really fits shows up in [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/).

> Go 1.26, macOS arm64, local example. Counts and sizes are deterministic. Timings are labelled with the load they were measured under.

## A generic singly linked list

A node holds a value and a pointer to the next node. `List[T]` has `PushFront`, `PushBack` (O(1) thanks to a tail pointer), `Find`, `Remove` and `Reverse`:

```go
type Node[T any] struct {
	Val  T
	Next *Node[T]
}

func (l *List[T]) PushFront(v T) {
	nd := &Node[T]{Val: v, Next: l.head}
	l.head = nd
	if l.tail == nil {
		l.tail = nd
	}
	l.n++
}

func (l *List[T]) Reverse() {
	var prev *Node[T]
	l.tail = l.head
	for c := l.head; c != nil; {
		next := c.Next
		c.Next = prev
		prev, c = c, next
	}
	l.head = prev
}
```

The tests cover push, find, remove, reverse (including that `PushBack` still works afterwards, since `Reverse` must fix the tail), the empty list, and independent lists in goroutines. They pass with `go test -race`.

| Operation | Linked list | Dynamic array |
|---|---|---|
| Insert at head | O(1) | O(n) |
| Append | O(1) with tail | O(1) amortized |
| i-th element | O(n) | O(1) |
| Remove a node you hold | O(1) doubly; singly needs the previous node | O(n) shift |

Counting nodes visited by `Find` in a list of 1000: first element 1 step, middle 501, last 1000. The O(n) is literally that.

## What a node costs

```
sizeof Node[int]: 16  elem int: 8
sizeof Node[byte]: 16 elem byte: 1
sizeof Node[big]: 136 elem big: 128
```

Every node carries an 8-byte pointer, and alignment pads it. For small elements the overhead dominates. These are struct sizes; the allocator may round up further (I did not measure that).

Allocations for 1000 elements, with `testing.AllocsPerRun`:

```
list 1000, presized slice 1, append-grown slice 9
```

The list needs one allocation per element, the presized slice one in total.

## Where the nodes live

I printed the address difference between consecutive nodes. Built back-to-back:

```
[16 16 16 16 16 16 16 16 16 16 16 16]
```

Then I allocated the same 1000 nodes, shuffled them and relinked:

```
[-304 1648 -8736 5408 -27696 23536 6720 -1040 1744 -16 -27136 -2432]
```

In this run, fresh nodes were adjacent; after shuffling, walking the list jumps around. That is the difference between good and poor {{< term "cache-locality" "cache locality" >}}. A real program that adds and removes over time looks more like the second case, but I did not prove that here.

## The timed benchmark

Sum of all elements: slice, list built in order, list shuffled in memory. Median of 7 `testing.Benchmark` runs, binary built beforehand, run alone under a lock. **Measured on this machine, load 1.9 at start and 2.3 at the end** (higher than I wanted, so treat it as indicative):

```
n         slice ns   list(ordered) ns   list(shuffled) ns
1000           323             1261               1260
100000       40997           128347             546201
1000000     418855          1318309           27327167
```

The ordered list is about 3x slower than the slice at every size. The shuffled one is 3.9x at 1000 elements (where everything fits in cache) but 13x at 100k and 65x at 1M. What I can support: the gap grows exactly when the data gets large and the order is scrambled. A reasonable explanation is cache misses, but I did not read hardware counters, so that is a hypothesis. Numbers will differ on your machine.

## Where lists do fit

A doubly linked list lets you remove a node you already hold in O(1), without searching. The standard `container/list` does that:

```
0 1 3 4 (removed known element 2 in O(1))
```

The classic use is an {{< term "lru-cache" "LRU cache" >}}: a map from key to list element, and a list ordered by recency.

```go
func (c *LRU) Get(k string) (int, bool) {
	e, ok := c.items[k]
	if !ok {
		return 0, false
	}
	c.ll.MoveToFront(e)
	return e.Value.(*entry).val, true
}

func (c *LRU) Put(k string, v int) {
	if e, ok := c.items[k]; ok {
		e.Value.(*entry).val = v
		c.ll.MoveToFront(e)
		return
	}
	c.items[k] = c.ll.PushFront(&entry{k, v})
	if c.ll.Len() > c.cap {
		last := c.ll.Back()
		c.ll.Remove(last)
		delete(c.items, last.Value.(*entry).key)
	}
}
```

With capacity 3, puts `a b c`, a read of `a`, then a put of `d` gave keys `[d a c]`: `b` was evicted. The test passes too. The map finds the element in O(1), the list moves and evicts in O(1). Neither alone can do both.

## A few things to watch

- Default to a slice. Reach for a list only when you hold nodes and splice often.
- Each node is a separate allocation, which means more garbage collector work too.
- Insert at the head is O(1), but finding the position is O(n).
- `container/list` stores `any`, so you pay type assertions; my generic `List[T]` does not.
- Do not trust these ratios on other hardware or other element sizes.

## Exercise

Make `List[T]` doubly linked and add `Remove(node)` that takes the node itself. Then test removing every second node of a 1M list and compare with `slices.DeleteFunc` on a slice. Predict the winner first.

## What's next

A hash table from scratch.
