+++
date = '2026-12-23T10:00:00+03:30'
draft = false
title = 'Stacks, queues and deques'
description = 'Stack, queue and deque in Go: generic slice and ring-buffer implementations, the q = q[1:] pitfall, allocation counts, and four real uses with output.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "stack", "queue", "deque"]
cover = { image = "/images/covers/algo-stacks-queues-deques.png", alt = "Stacks, queues and deques", hiddenInSingle = true }
+++

In the previous post, [A hash table from scratch](/posts/algo-hash-tables/), we built a structure that finds things by key. Stacks and queues do the opposite: they restrict access on purpose, and that restriction is exactly what makes them fast and easy to reason about. They sit on top of the arrays from [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/), and the node-based alternative was covered in [Linked lists and why they are rarely the answer](/posts/algo-linked-lists/). The code uses [Generics in Go](/posts/go-generics/).

> Go 1.26, macOS arm64, local example. All numbers below are counts or sizes, not timings, so they do not depend on machine load. Tests pass with `go test -race`.

## Three small types

A {{< term "stack" "stack" >}} is last-in, first-out. A slice does it perfectly: push is `append`, pop takes the last element.

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

A {{< term "queue" "queue" >}} is first-in, first-out, and a {{< term "deque" "deque" >}} allows push and pop at both ends. Both fit one {{< term "ring-buffer" "ring buffer" >}}: a fixed array plus a `head` index and a count, where positions wrap around with `%`. When the array is full it doubles.

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

`Queue[T]` is a thin wrapper that exposes only `Enqueue` and `Dequeue`. The tests compare the deque against a plain slice model over 5000 random operations, and check FIFO order across growth.

## The `q = q[1:]` pitfall

The tempting queue is a slice: `append` to enqueue, `q = q[1:]` to dequeue.

```
start      len 8 cap 8
5 dequeues len 3 cap 3
5 enqueues len 8 cap 8 (reallocated)
```

Reslicing moves the start forward and the capacity shrinks with it, so the front space is gone. Worse, the old elements are still referenced by the {{< term "backing-array" "backing array" >}}. I queued 1000 pointers to 1 KB values, dequeued 990, forced a garbage collection and read `HeapAlloc`:

```
990 of 1000 items popped with q = q[1:]: ~1000 KB still live
same, but q[0] = nil before reslicing:   ~0 KB still live
```

The popped items stayed alive until the array is replaced. Clearing the slot first fixes the leak (my `Pop` does this). Then I ran 100000 enqueue/dequeue pairs with never more than 5 items waiting:

```
slice queue: new arrays allocated = 25000
ring queue: cap = 8 copies = 4
```

The slice queue allocates a fresh array about every 4 operations; the ring buffer stays at capacity 8 and copied 4 elements once.

## Allocations and amortized growth

`testing.AllocsPerRun` for 1000 pushes and 1000 pops:

```
slice stack 12, presized 1, container/list 1745
```

The slice stack grows geometrically (12 allocations), a presized one needs 1. `container/list` allocates a node per element, and the 745 extra are the list itself plus 744 boxed ints: pushing a small constant or a pointer gives 1001 allocations, and the 744 matches the values 256 to 999 that the runtime does not cache.

Growth by doubling is {{< term "amortized-analysis" "amortized" >}} O(1). I counted the elements `grow` copied:

```
n=10       cap=16       copies=12       copies/n=1.20
n=1000     cap=1024     copies=1020     copies/n=1.02
n=1000000  cap=1048576  copies=1048572  copies/n=1.05
```

Roughly one copy per push, whatever n is.

## Four real uses

**Balanced brackets** with a stack, remembering the position of each opener:

```
"{[()]}"           balanced=true  pos=-1
"f(a[1], {x: 2})"  balanced=true  pos=-1
"(]"               balanced=false pos=1
"((a)"             balanced=false pos=0
"a)"               balanced=false pos=1
```

**Undo/redo** with two stacks. A new edit must clear the redo stack:

```
"hello world" undo "hello" undo "" redo "hello" type ! then redo "hello!"
```

**Level-order walk** of a small tree with the queue (the idea behind {{< term "bfs" "breadth-first search" >}}). `size := q.Len()` at the start of each round is exactly one level:

```
levels: [[1] [2 3] [4 5 6] [7]]
```

**Next greater element** with a monotonic stack. For each value, pop smaller indexes from the stack and answer them:

```
input: [2 1 5 3 4 9 4] next greater: [5 5 9 4 9 -1 -1] pushes 7 pops 7
n=100000 increasing: pushes 100000 pops 100000
n=100000 decreasing: pushes 100000 pops 100000
```

The inner loop looks quadratic, but every index is pushed once and popped at most once, so the total is at most 2n operations. The counts show it for the two extreme inputs.

## Channels and other languages

A buffered Go channel is already a thread-safe FIFO queue ([Goroutines and channels in Go](/posts/go-goroutines-channels/)); use it between goroutines, and the types here when only one goroutine touches the data. These types are not safe for concurrent use. According to the docs, Rust's `std::collections::VecDeque` is a growable ring buffer; I did not run it here.

## A few things to watch

- Clear the slot when you pop, or the garbage collector cannot free the value.
- `q = q[1:]` is fine for short-lived queues, not for long-running ones.
- Pop on an empty structure must return `ok == false`, not panic.
- The modulo in a ring buffer is the classic place for off-by-one bugs; test with a slice model.
- Presize with `make([]T, 0, n)` when you know the size.

## Exercise

Add `Peek` to `Queue`, then make `Deque` shrink when it is a quarter full. Check with the copy counter that a push/pop pattern at the shrink boundary does not copy on every step.

## What's next

Heaps and priority queues.
