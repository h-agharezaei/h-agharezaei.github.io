+++
date = '2026-12-15T10:00:00+03:30'
draft = false
title = 'A hash table from scratch'
description = 'Hash table in Go from scratch: linear probing, load factor and rehash, tombstone deletes, probe counts for a good and a terrible hash, tested against map.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "hash-table", "hashing"]
cover = { image = "/images/covers/algo-hash-tables.png", alt = "A hash table from scratch", hiddenInSingle = true }
+++

In the previous post, [Linked lists and why they are rarely the answer](/posts/algo-linked-lists/), a map and a list made an LRU cache. The map found keys without scanning. This time we build that part. A {{< term "hash-table" "hash table" >}} is the structure behind Go's `map`, which we used in [Slices, maps and strings in Go](/posts/go-slices-maps-strings/). The growth idea comes from [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/).

> Go 1.26, macOS arm64, local example. Numbers are counts of slots examined, so they are deterministic; no timings.

## The design

A generic `Map[K comparable, V any]` takes a hash function from the caller. I picked **open addressing** with {{< term "linear-probing" "linear probing" >}}: one flat array of slots, and a key goes to `hash & (len-1)` or, if that is taken, to the next free slot. The alternative is **chaining**: each slot holds a list of entries. Chaining deletes more simply, but every entry is a separate node. I did not implement it, so I measured nothing about it.

```go
type slot[K comparable, V any] struct {
	key K
	val V
	st  state // empty, full or tomb
}

func (m *Map[K, V]) find(k K) int {
	mask := uint64(len(m.slots) - 1)
	i := m.hash(k) & mask
	for {
		m.Probes++
		s := &m.slots[i]
		switch {
		case s.st == empty:
			return -1
		case s.st == full && s.key == k:
			return int(i)
		}
		i = (i + 1) & mask
	}
}
```

The length is a power of two, so a mask replaces a modulo. `Probes` counts every slot looked at. The API is `Get`, `Put`, `Delete`, `Len` and `Range`.

## Growth and the load factor

If live entries plus tombstones would pass 75% of the slots, `rehash` allocates a new array and reinserts every live entry. It doubles only when real entries fill over a third of the slots; otherwise it just drops tombstones. A rehash is O(n) but rare, so inserts are {{< term "amortized-analysis" "amortized" >}} O(1).

## Deleting: the naive way fails

If `Delete` just empties the slot, a key that was pushed past it by a collision can no longer be found, because `find` stops at the first empty slot. I wrote that as `DeleteNaive` and a test with a hash that sends everything to one slot:

```
--- FAIL: TestNaiveDeleteBreaksChain (0.00s)
    table_test.go:43: key 2 lost after deleting key 1 (Get returned "", false)
```

The fix is a {{< term "tombstone" "tombstone" >}}: mark the slot as deleted, keep probing past it, let a later `Put` reuse it. The same test with the real `Delete` passes. That failing test runs only with `SHOW_BUG=1`.

## Testing against the built-in map

A property-style test applies 300,000 random `Put`, `Delete` and `Get` calls from a fixed seed (42) to my table and to a Go `map`, comparing every result and `Len` after each step, then compares the full contents through `Range`. It runs with FNV-1a (`hash/fnv`) and with the terrible hash, and passes under `go test -race`.

## A good hash against a terrible one

100,000 random keys (fixed seed), FNV-1a against a hash that returns 7 for every key. Put counts the lookup plus the insert:

```
fnv-1a       put probes 733778 (7.3/op) get probes 130719 (1.3/op) slots 262144
all-collide  put probes 10000100000 (100001.0/op) get probes 5000050000 (50000.5/op)
```

With a decent hash a lookup touches about 1.3 slots. With every key colliding, the table becomes one long run: the average successful `Get` examines 50,000 slots, half of n, exactly a linear scan. The table is only as good as its {{< term "hash-collision" "collisions" >}} are rare.

## Load factor against probe length

A fixed table of 131,072 slots, growth disabled, filled to different {{< term "load-factor" "load factors" >}} with random keys:

| Load | Probes per hit | Probes per miss |
|---|---|---|
| 25% | 1.17 | 1.39 |
| 50% | 1.50 | 2.50 |
| 75% | 2.54 | 8.83 |
| 90% | 5.65 | 57.71 |
| 95% | 9.84 | 177.22 |

Misses degrade fastest, because they must walk to an empty slot. This fits the textbook estimates for linear probing (about 1.5 and 2.5 at half full), and it is why I grow at 75%.

## Iteration order

My `Range` walks the slots, so the order is fixed by the hash and the insertion history. Inserting 0 to 7, two runs gave the same order for mine, different ones for Go's map:

```
mine: [5 4 7 6 1 0 3 2] builtin: [7 0 1 2 3 4 5 6]
mine: [5 4 7 6 1 0 3 2] builtin: [2 3 4 5 6 7 0 1]
```

Go randomizes on purpose so nobody depends on an order. On the hasher choice, [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/) swapped Rust's default DoS-resistant hasher for a simple FNV one and a word-count benchmark got faster.

## A few things to watch

- Keys must be comparable and hashable. If a key's hash depends on something you later mutate, the entry sits in the wrong slot and is lost. I did not demonstrate this; treat keys as immutable.
- Tombstones count towards the load, otherwise a delete-heavy table fills with them.
- A predictable hash lets someone craft colliding keys; avoid toy hashes on untrusted input.
- My table is not safe for concurrent writes.

## Exercise

Implement the chaining version with the same API and run the same property test. Then compare average chain length with probe length at 75% load. Predict the winner first.

## What's next

Stacks, queues and deques.
