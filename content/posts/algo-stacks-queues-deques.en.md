+++
date = '2026-12-23T10:00:00+03:30'
draft = false
title = 'Stacks, queues and deques'
description = 'Stack, queue and deque in Go: generic slice and ring-buffer implementations, the q = q[1:] pitfall, allocation counts, and four real uses with output.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "stack", "queue", "deque"]
cover = { image = "/images/covers/algo-stacks-queues-deques.png", alt = "Stacks, queues and deques", hiddenInSingle = true }
+++

Picture a queue of 1,000 pointers to 1 KB values, kept in a slice. You take 990 of them off the front with `q = q[1:]`, force a garbage collection, and look at the memory: the 990 popped items are still alive. The tempting {{< term "queue" "queue" >}} is a leak.

This post is about two of the simplest data structures there are, and about why getting their storage right matters. {{< term "stack" "Stacks" >}} and queues restrict access on purpose. A hash table, which we built in [A hash table from scratch](/posts/algo-hash-tables/), lets you ask for any key. A stack or a queue lets you touch only one end, or two. That restriction is exactly what makes them fast and easy to reason about, as long as the storage underneath is right. They sit on top of the arrays from [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), and the node-based alternative was covered in [Linked lists and why they are rarely the answer](/posts/algo-linked-lists/). The code uses [Generics in Go](/posts/go-generics/).

> Go 1.27, macOS arm64, local example, re-run for this post. All numbers below are counts or sizes, not timings, so they do not depend on machine load. Tests pass with `go test -race`.

## The three shapes

A **stack** is last-in, first-out (LIFO), like a pile of plates: you put a plate on top and you take the top one. A **queue** is first-in, first-out (FIFO), like people in a line: the one who arrived first is served first. A {{< term "deque" "deque" >}} (said "deck", short for double-ended queue) allows adding and removing at both ends.

```
stack:   push -> [ a b c ] <- pop            (one end)
queue:   enqueue -> [ a b c ] -> dequeue     (two ends, different roles)
deque:   push/pop <-> [ a b c ] <-> push/pop (both ends, both operations)
```

## Three small types

A slice does the stack perfectly: push is `append`, and pop takes the last element. The one detail is that `Pop` also clears the slot it frees, so the slice does not keep a pointer alive by accident.

```go
func (s *Stack[T]) Pop() (T, bool) {
	var zero T
	n := len(s.items)
	if n == 0 {
		return zero, false
	}
	v := s.items[n-1]
	s.items[n-1] = zero // do not keep a reference alive
	s.items = s.items[:n-1]
	return v, true
}
```

Pop returns a value and a bool, `false` when the stack is empty, so an empty stack is a normal answer and not a panic.

For the queue and the deque we need something smarter than a slice, because both remove from the front. A good fit is a {{< term "ring-buffer" "ring buffer" >}}: a fixed array, a `head` index that says where the first element is, and a count. The array is treated as a circle: when an index runs past the end, it wraps around to 0 with `%`. For example, with an array of 4 slots, after some dequeues and enqueues the elements can sit like this:

```
index:    0    1    2    3
        [ e ][ . ][ c ][ d ]      head = 2, count = 3
                       ^ first    (c, d, then wraps around to e)
```

Nothing ever has to shift. Removing from the front just moves `head` forward by one. When the array is full it doubles, like the dynamic array before.

```go
func (d *Deque[T]) PushBack(v T) {
	if d.n == len(d.buf) {
		d.grow()
	}
	d.buf[(d.head+d.n)%len(d.buf)] = v
	d.n++
}

func (d *Deque[T]) PopFront() (T, bool) {
	var zero T
	if d.n == 0 {
		return zero, false
	}
	v := d.buf[d.head]
	d.buf[d.head] = zero
	d.head = (d.head + 1) % len(d.buf)
	d.n--
	return v, true
}
```

`PushBack` writes at position `head + count` (wrapped), and `PopFront` reads at `head`, clears the slot and moves `head` on. `Queue[T]` is a thin wrapper around the deque that exposes only `Enqueue` and `Dequeue`. The tests compare the deque against a plain slice model over 5,000 random operations, and check FIFO order across growth.

## The `q = q[1:]` pitfall

Now back to the opening. The tempting queue is a slice: `append` to enqueue and `q = q[1:]` to dequeue. It looks right and it is short. The first experiment shows what happens to the length and capacity:

```
start      len 8 cap 8
5 dequeues len 3 cap 3
5 enqueues len 8 cap 8 (reallocated)
```

We start with 8 items. After 5 dequeues by reslicing, `len` is 3 and `cap` is 3 too: reslicing moved the start forward, so the space at the front is gone and cannot be reused. When we then enqueue 5 more, the slice is full and `append` has to allocate a new array.

Worse, the old elements are still referenced by the {{< term "backing-array" "backing array" >}}. To see it, I made 1,000 pointers to 1 KB values, popped 990, forced a garbage collection and read `HeapAlloc`, the live heap size, in kilobytes:

```
990 of 1000 items popped with q = q[1:]: ~1000 KB still live
same, but q[0] = nil before reslicing:   ~0 KB still live
```

(Rounded to the nearest 100 KB in the program.) Without clearing, all 1,000 values are still alive, about 1,000 KB, even though we only have 10 left in the queue. The garbage collector sees the whole backing array as in use, so everything it points to stays. If we set `q[0] = nil` before reslicing, the popped values can be freed and almost nothing stays. My `Pop` does this, which is why it contains that `zero` line.

The leak is only one half. The other is allocation churn. I ran 100,000 enqueue/dequeue pairs with never more than 5 items waiting at once:

```
slice queue: new arrays allocated = 25000
ring queue: cap = 8 copies = 4
```

The slice queue allocates a fresh array about every 4 operations, because each reslice eats capacity from the front. The ring buffer stays at capacity 8 and copied 4 elements once, when it grew from 4 to 8, and never again. It reuses the same slots forever.

## Allocations and amortized growth

`testing.AllocsPerRun` for 1,000 pushes and 1,000 pops, three ways:

```
slice stack 12, presized 1, container/list 1745
```

The slice stack grows by doubling and so needs 12 allocations. A slice created with the right capacity needs 1. `container/list`, the doubly linked list from the standard library, allocates a node per element, and the 745 extra are the list itself plus 744 boxed ints: when I pushed a small constant instead, the count was 1,001. The 744 matches the values from 256 to 999. As far as I know the runtime keeps preallocated boxes for small values below 256, but I only checked the counts, not the runtime source.

Growth by doubling is {{< term "amortized-analysis" "amortized" >}} O(1), as we saw with the dynamic array. I counted the elements that `grow` copied:

```
n=10       cap=16       copies=12       copies/n=1.20
n=1000     cap=1024     copies=1020     copies/n=1.02
n=1000000  cap=1048576  copies=1048572  copies/n=1.05
```

Roughly one copy per push, whatever `n` is. (The first grow goes from 0 to 4, then 4 to 8 and so on, so the counts come out a little above `n`.)

## Four real uses

A stack and a queue are small, but a surprising amount of work reduces to one of them. Here are four, each with real output.

**Balanced brackets** with a stack. Walk through the text: push every opening bracket together with its position, and for every closing bracket pop one and check that it matches. If a closer finds an empty stack or the wrong opener, or openers are left over at the end, the text is not balanced, and the position tells us where:

```
"{[()]}"           balanced=true  pos=-1
"f(a[1], {x: 2})"  balanced=true  pos=-1
"(]"               balanced=false pos=1
"((a)"             balanced=false pos=0
"a)"               balanced=false pos=1
```

`pos=-1` means no problem. In `"(]"` the `]` at position 1 meets a `(`, so the report is position 1. In `"((a)"` the `)` closes the second `(`, and the first `(` at position 0 is never closed, so the report is 0. In `"a)"` the `)` at position 1 finds an empty stack.

**Undo/redo** with two stacks. Every edit pushes the old text on the undo stack. Undo moves the current text to the redo stack and restores from undo. A new edit must clear the redo stack, because after a new edit the old "future" no longer makes sense:

```
"hello world" undo "hello" undo "" redo "hello" type ! then redo "hello!"
```

Read it left to right: we typed "hello" and " world", undid twice to get back to the empty text, redid once to get "hello", then typed "!" and tried to redo. The redo gave nothing new, we stay at "hello!", because typing cleared the redo stack.

**Level-order walk** of a small tree with a queue. This is the idea behind {{< term "bfs" "breadth-first search" >}}: visit the root, then its children, then their children. Take a node from the front, put its children at the back. At the start of each round, `size := q.Len()` is exactly the number of nodes on the current level, so we can group them:

```
levels: [[1] [2 3] [4 5 6] [7]]
```

**Next greater element** with a monotonic stack. For each value in a list we want the next larger value to its right. We keep a stack of indexes whose answer we do not know yet. For each new value, we pop every smaller index from the stack and answer it with this value, and then push the new index:

```
input: [2 1 5 3 4 9 4] next greater: [5 5 9 4 9 -1 -1] pushes 7 pops 7
n=100000 increasing: pushes 100000 pops 100000
n=100000 decreasing: pushes 100000 pops 100000
```

For the 2 the next greater is 5, for the 1 it is 5, for the 5 it is 9, and so on; `-1` means none (the 9 and the last 4). The inner loop looks quadratic, but every index is pushed once and popped at most once, so the total is at most 2n operations. The last two lines show it for two extreme inputs, an increasing and a decreasing list of 100,000 numbers: exactly 100,000 pushes and 100,000 pops in both.

## Channels and other languages

A buffered Go channel is already a thread-safe FIFO queue ([Goroutines and channels in Go](/posts/go-goroutines-channels/)). Use it between goroutines, and the types in this post when only one goroutine touches the data. These types are not safe for concurrent use. According to the docs, Rust's `std::collections::VecDeque` is a growable ring buffer; I did not run it here.

## Bugs that hide in queues

- **Clear the slot when you pop,** or the garbage collector cannot free the value.
- **`q = q[1:]` is fine for short-lived queues,** not for long-running ones.
- **Pop on an empty structure must return `ok == false`,** not panic.
- **The modulo in a ring buffer is the classic place for off-by-one bugs.** Test it against a slice model, as I did.
- **Presize with `make([]T, 0, n)`** when you know the size.

## Exercise

Add `Peek` to `Queue`, then make `Deque` shrink when it is a quarter full. Use the copy counter to check that a push/pop pattern at the shrink boundary does not copy on every step.

## What's next

The next post is "Heaps and priority queues". It is for the case where items should leave by urgency and not by arrival order.
