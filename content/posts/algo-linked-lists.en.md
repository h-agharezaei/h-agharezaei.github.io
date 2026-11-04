+++
date = '2026-12-07T10:00:00+03:30'
draft = false
title = 'Linked lists and why they are rarely the answer'
description = 'Linked list in Go: a generic List[T], node memory overhead, allocation counts, cache locality measured against a slice, and where an LRU cache fits.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "linked-list", "cache"]
cover = { image = "/images/covers/algo-linked-lists.png", alt = "Linked lists and why they are rarely the answer", hiddenInSingle = true }
+++

In the textbook, the linked list is the great rival of the array. Insert at the front in constant time. Never copy anything when the list grows. It sounds like it should win often. Yet when I sum a million numbers, a {{< term "linked-list" "linked list" >}} is about 3 times slower than a slice if its nodes sit in memory in order, and 65 times slower if they are scattered. So why do people reach for it so rarely?

To answer, we first need to see what a linked list is and what it costs. The array it competes with was the subject of [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), where it won on almost every count. Here we build a list with [Generics in Go](/posts/go-generics/), and the memory side of pointers is in [Pointers and the memory model in Go](/posts/go-pointers-memory/). At the end I show the one place where a list really belongs, which also appears in [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/).

> This is a local example on Go 1.27, macOS arm64. Counts and sizes are deterministic and were re-run for this post. The timings in the benchmark section are from an earlier run on Go 1.26 and are labelled with the load they were measured under. Memory addresses vary from run to run.

## The idea: a chain of nodes

An array keeps its elements in one block of memory, side by side. A linked list does the opposite: every element lives in its own small box, called a **node**, and each node holds two things: the value, and a pointer to the next node.

```
head
 |
 v
[ 10 | * ]--->[ 20 | * ]--->[ 30 | * ]---> nil
```

To reach the third element you cannot calculate where it is. You have to start at the head and follow the pointers: first node, second node, third node. That is the main weakness. The main strength is that the boxes can be anywhere in memory, so adding or removing one only means changing a pointer or two. Nothing else moves.

A list in which each node knows only the next one is called **singly linked**. If each node also keeps a pointer to the previous one, it is **doubly linked**. We start with the singly linked kind.

## A generic singly linked list

The `List[T]` below has `PushFront`, `PushBack`, `Find`, `Remove` and `Reverse`. It keeps both a `head` and a `tail` pointer, which is what makes `PushBack` O(1): we do not have to walk to the end first.

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

`PushFront` makes a node that points at the old head, and then makes it the new head. `Reverse` walks the list once and flips every `Next` pointer to point backwards; the old head becomes the tail, which is why `l.tail = l.head` comes first.

The tests cover push, find, remove, reverse (including that `PushBack` still works afterwards, since `Reverse` must fix the tail), the empty list, and independent lists in goroutines. They pass with `go test -race`.

How does it compare with a dynamic array?

| Operation | Linked list | Dynamic array |
|---|---|---|
| Insert at head | O(1) | O(n) |
| Append | O(1) with tail | O(1) amortized |
| i-th element | O(n) | O(1) |
| Remove a node you hold | O(1) if doubly linked; singly linked needs the previous node | O(n) shift |

The last row is easy to misread. "A node you hold" means you already have a reference to that node. Finding it in the first place is still a walk.

To see the O(n) of "i-th element" as a number, the demo counts how many nodes `Find` visits in a list of 1,000:

```
find steps in 1000 nodes: first 1 middle 501 last 1000
```

The first element takes 1 step, the middle 501, the last 1,000. That is what O(n) means in practice: the further the element is, the more steps.

## What a node costs

Every node carries an extra pointer next to the value, and that costs memory. The demo prints the size of a node for three element types:

```
sizeof Node[int]: 16  elem int: 8
sizeof Node[byte]: 16 elem byte: 1
sizeof Node[big]: 136 elem big: 128
```

For an `int`, the node is 16 bytes and the element only 8: the other half is the pointer. For a single `byte` it is worse: the node is 16 bytes for 1 byte of data, because the 8-byte pointer must be aligned and padding fills the rest. Only when the element is big (`big` is 128 bytes) does the pointer become a small part. So for small elements the overhead dominates. These are struct sizes; the allocator may round them up further, and I did not measure that.

There is a second cost: allocations. Each node is a separate request to the memory allocator. I counted them with `testing.AllocsPerRun`, for building 1,000 elements three ways:

```
allocs for 1000 elements: list 1000, presized slice 1, append-grown slice 9
```

The list needs one allocation per element. A slice whose capacity was set in advance needs one in total, and one that grows by `append` needs 9 (we saw why in the previous post). Many small allocations also mean more work for the garbage collector later.

## Where the nodes live

Now to the big timing gap from the introduction. A list does not need its nodes to sit next to each other, but it matters a lot for speed whether they do. To see where nodes really are, I printed the difference in memory address between consecutive nodes. First for a list built by pushing 1,000 nodes back to back:

```
address deltas, built in order: [16 16 16 16 16 16 16 16 16 16 16 16]
```

(I show the first 12.) Each node is exactly 16 bytes after the previous one, so the list is laid out like an array. Then I took the same 1,000 nodes, shuffled them and linked them again in the shuffled order:

```
address deltas, shuffled      : [-304 1648 -8736 5408 -19504 15344 6720 -1040 1744 -16 -18944 -2432]
```

Now the next node is thousands of bytes ahead or behind, in no pattern. The exact numbers change from run to run, because they are real addresses; the point is only that they are not 16 any more. This is the difference between good and poor {{< term "cache-locality" "cache locality" >}}: a processor loads memory in chunks and keeps recent chunks in a small, fast {{< term "cpu-cache" "cache" >}}. When the next node is right beside the current one, it is probably already loaded. When it is far away, the processor has to wait for main memory. A real program that adds and removes nodes over time looks more like the second case than the first, but I did not prove that here.

## The timed benchmark

The test is simple: add up all elements of a slice, of a list built in order, and of a list shuffled in memory. Each number is the median of 7 `testing.Benchmark` runs, with the binary built beforehand and the benchmark run alone under a lock. **Measured on this machine in the earlier run, load 1.9 at the start and 2.3 at the end.** That is higher than I wanted, so treat the numbers as indicative. I did not repeat the timing this time because the machine was busy, so these are the original numbers.

```
n         slice ns   list(ordered) ns   list(shuffled) ns
1000           323             1261               1260
100000       40997           128347             546201
1000000     418855          1318309           27327167
```

Read each row from left to right. For 1,000,000 elements the slice takes about 0.42 ms, the ordered list about 1.3 ms and the shuffled list about 27 ms. So:

- The ordered list is about 3 to 4 times slower than the slice at every size. It has to follow a pointer for each element and read 16 bytes where the slice reads 8.
- The shuffled list is 3.9 times slower at 1,000 elements, where everything fits in the cache anyway. But it is 13 times slower at 100,000 elements and 65 times slower at 1,000,000.

What I can support is this: the gap grows exactly when the data gets large and its order is scrambled. A reasonable explanation is cache misses, but I did not read hardware counters, so that is a hypothesis. The numbers will differ on your machine.

## Where lists do fit

There is one thing a doubly linked list does very well: it can remove a node you already hold in O(1), without searching for it. The standard library has one, `container/list`:

```
0 1 3 4 (removed known element 2 in O(1))
```

The demo builds the list 0 to 4, keeps hold of the element with value 2, and removes it directly. The rest closes up with no shifting.

The classic use of this is an {{< term "lru-cache" "LRU cache" >}}. LRU means "least recently used": when the cache is full, the entry nobody has touched for the longest time is thrown out. We need two things at once. We must find an entry by key fast (a map does that), and we must keep entries in order of recent use, moving one to the front every time it is read (a doubly linked list does that, because we can pull out a node we hold and put it at the front in O(1)).

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

`items` maps a key to its list element. `Get` finds the element through the map and moves it to the front. `Put` either updates an existing entry and moves it to the front, or adds a new one at the front, and if the cache is now over capacity it removes the node at the back, which is the least recently used one, and deletes its key from the map.

With capacity 3, I put `a`, `b` and `c`, read `a`, and then put `d`:

```
LRU keys (most recent first): [d a c]
```

`b` is gone. It was the oldest untouched entry, because reading `a` made `a` newer. The test for this passes too. The map finds the element in O(1) and the list moves and evicts in O(1); neither alone can do both. And the map from the cache is the next thing we build by hand, in the next post.

## When a list is worth it

- **Default to a slice.** Reach for a list only when you hold on to nodes and splice often.
- **Each node is a separate allocation,** which also means more work for the garbage collector.
- **Inserting at the head is O(1), but finding the position is O(n).** The fast insert only helps if you are already standing in the right place.
- **`container/list` stores `any`,** so you pay for type assertions on every read; my generic `List[T]` does not.
- **Do not trust these ratios** on other hardware or with other element sizes.

## Exercise

Make `List[T]` doubly linked and add a `Remove(node)` that takes the node itself. Then test removing every second node of a list of 1,000,000 elements and compare it with `slices.DeleteFunc` on a slice. Predict the winner first, then check.

## What's next

The next post is "A hash table from scratch". It builds the map half of the LRU cache above by hand.
