+++
date = '2026-12-15T10:00:00+03:30'
draft = false
title = 'A hash table from scratch'
description = 'Hash table in Go from scratch: linear probing, load factor and rehash, tombstone deletes, probe counts for a good and a terrible hash, tested against map.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "hash-table", "hashing"]
cover = { image = "/images/covers/algo-hash-tables.png", alt = "A hash table from scratch", hiddenInSingle = true }
+++

How does a program find the value for a key without looking at every key? In a slice you have to scan. In a sorted slice you can halve the search. A {{< term "hash-table" "hash table" >}} does better: it computes where the key must be, goes straight there, and usually finds it on the first try. In my test with 100,000 keys, a lookup looked at about 1.3 slots on average with a good hash function. With a bad hash function that always returns 7, the same table looked at 50,000 slots, which is a plain linear scan. The whole difference is one function.

A hash table is the structure behind Go's `map` ([Slices, maps and strings in Go](/posts/go-slices-maps-strings/)). It is also the half of the LRU cache in [Linked lists and why they are rarely the answer](/posts/algo-linked-lists/) that found keys without scanning. This time we build one ourselves. When the table is full it has to grow, and that part borrows from [Dynamic arrays and slices from the inside](/posts/algo-dynamic-arrays/).

> Go 1.27, macOS arm64, local example. The numbers are counts of slots examined, so they are deterministic and I re-ran them for this post. No timings.

## The idea: turn the key into a position

Suppose we have an array of 8 empty slots, numbered 0 to 7, and we want to store the pair `"cat" -> 3`. We need a rule that turns the key into a slot number. That rule is a **hash function**: it takes a key and returns a big number. We then keep only the lower part of that number to get a valid slot. For a table of 8 slots we keep the last 3 bits, which is the same as "remainder after dividing by 8".

```
hash("cat") = ...0101 (binary)  -> keep last 3 bits -> 5

slot:  0     1     2     3     4     5          6     7
     [    ][    ][    ][    ][    ][ cat -> 3 ][    ][    ]
```

(The hash value above is made up to show the idea; the real hash of "cat" depends on the function.) To find `"cat"` later, we compute the same hash, jump to slot 5 and look. The same key always gives the same slot, so we never scan.

The catch is that two different keys can land on the same slot. That is called a {{< term "hash-collision" "collision" >}}. Collisions are not a bug; with 8 slots and more than 8 keys they are certain. A hash table is really a rule for what to do when they happen.

## The design

There are two classic answers. With **chaining**, each slot holds a small list of all the entries that landed there. With **open addressing**, there is only one flat array, and if a slot is taken, you look at another one. I chose open addressing with {{< term "linear-probing" "linear probing" >}}: if the slot is taken, try the next one, then the next, and wrap around at the end. Chaining deletes more simply, but every entry is a separate node, which we saw is costly. I did not implement it.

A generic `Map[K comparable, V any]` takes the hash function from the caller. Each slot stores a key, a value and a state: `empty`, `full` or `tomb` (we will meet that last one in a moment). The heart is `find`:

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

It starts at the slot the hash points to. Then it loops: an empty slot means the key is not in the table, a full slot with the same key means found, and anything else means "keep going to the next slot". Each look at a slot is called a **probe**, and the `Probes` counter counts them, so we can measure the work without a clock.

The number of slots is always a power of two, so `hash & mask` (keep the low bits) does the job of a remainder, which is the "keep the last 3 bits" from the picture. The API is `Get`, `Put`, `Delete`, `Len` and `Range`.

## Growth and the load factor

A table that is too full gets slow, because probing walks longer and longer runs of taken slots. The share of slots in use is called the {{< term "load-factor" "load factor" >}}. My table keeps it under 75%: if live entries plus deleted markers would pass 75% of the slots, `rehash` allocates a new array and re-inserts every live entry. It re-inserts rather than copies because the slot depends on the array size, so every key may land somewhere new.

`rehash` doubles the array only when real entries fill more than half of the load limit (37.5% of the slots). Otherwise most of the load is deleted markers, and a rebuild at the same size just clears them out. A rehash is O(n), but it happens rarely, so inserts are {{< term "amortized-analysis" "amortized" >}} O(1), exactly like the dynamic array in the previous posts.

## Deleting: the naive way fails

Deleting looks easy: empty the slot. But think about what `find` does. It stops at the first empty slot. Suppose keys 1 and 2 collide, so 1 is in slot 7 and 2 was pushed into slot 8. If we empty slot 7, a lookup for key 2 starts at slot 7, sees "empty", and decides that key 2 does not exist. We just lost it.

To prove this, I wrote `DeleteNaive` and a test with a hash that sends every key to the same slot. The test only runs with `SHOW_BUG=1`, and it fails like this:

```
--- FAIL: TestNaiveDeleteBreaksChain (0.00s)
    table_test.go:43: key 2 lost after deleting key 1 (Get returned "", false)
```

The fix is a {{< term "tombstone" "tombstone" >}}: instead of emptying the slot, mark it as deleted. `find` keeps probing past a tombstone, so the chain stays unbroken, and a later `Put` may reuse the slot. The same test written against the real `Delete` passes.

## Testing against the built-in map

A hash table has many corner cases, so I did not trust a few hand-written examples. A property-style test applies 300,000 random `Put`, `Delete` and `Get` calls, from a fixed seed (42), to my table and to a Go `map` at the same time. At every step it compares the results and `Len`, and at the end it compares the full contents through `Range`. It runs with FNV-1a (`hash/fnv`, a simple and well-known hash function) and with the terrible constant hash, and passes under `go test -race`.

## A good hash against a terrible one

Back to the opening numbers. I inserted 100,000 random keys (fixed seed) and then looked up each of them, once with FNV-1a and once with the constant-7 hash. For `put`, the count includes the lookup that checks whether the key exists plus the insert itself:

```
fnv-1a       put probes 733778 (7.3/op) get probes 130719 (1.3/op) slots 262144
all-collide  put probes 10000100000 (100001.0/op) get probes 5000050000 (50000.5/op)
```

(The program also prints the number of growths, 15 for both; I left it out.) With FNV-1a, a successful `Get` needs 1.3 probes on average, and the table ended with 262,144 slots for 100,000 keys. The 7.3 for `Put` is higher because `Put` first does a lookup that misses (it must walk to an empty slot) and then walks again to find a place for the new key.

With the constant hash, every key collides. The table becomes one long run: the average successful `Get` examines half of `n`, 50,000 slots, which is a linear scan. A table is only as good as its collisions are rare.

## Load factor against probe length

How much does a fuller table cost? For this test I fixed the table at 131,072 slots with growth disabled, and filled it to different load factors with random keys. A "hit" is looking up a key that is there; a "miss" is looking up one that is not.

| Load | Probes per hit | Probes per miss |
|---|---|---|
| 25% | 1.17 | 1.39 |
| 50% | 1.50 | 2.50 |
| 75% | 2.54 | 8.83 |
| 90% | 5.65 | 57.71 |
| 95% | 9.84 | 177.22 |

Misses get worse much faster than hits, because a miss must walk until it finds an empty slot, and when the table is nearly full empty slots are far apart. At 95% a miss takes 177 probes. These numbers match the textbook estimates for linear probing (about 1.5 and 2.5 at half full), and that is why I grow the table at 75%, where a miss is still about 9 probes.

## Iteration order

My `Range` walks the slots from first to last, so the order is decided by the hash and by the history of inserts. I inserted 0 to 7 and printed the keys in iteration order, twice:

```
mine: [5 4 7 6 1 0 3 2] builtin: [7 0 1 2 3 4 5 6]
mine: [5 4 7 6 1 0 3 2] builtin: [2 3 4 5 6 7 0 1]
```

Mine gave the same order both times. Go's built-in map gave a different order each time, and the order you see on your machine will differ too. Go randomizes iteration order on purpose, so that nobody builds a program that depends on it.

On the choice of hash function: in [Go or Rust? When to use which](/posts/go-vs-rust-when-to-use/), swapping Rust's default hasher (which is designed to resist attacks) for a simple FNV hasher made a word-count benchmark faster. The hash function is a real choice, not a detail.

## Where a hash table breaks

- **Keys must be comparable and hashable.** If a key's hash depends on something you change later, the entry sits in the wrong slot and is lost. I did not demonstrate this; treat keys as immutable.
- **Tombstones count towards the load.** Otherwise a table with many deletes fills up with them and every lookup gets slow.
- **A predictable hash is a weakness.** Someone can craft keys that all collide and push your table into the slow case from the "all-collide" row. Avoid toy hashes on untrusted input.
- **My table is not safe for concurrent writes.** It has no locking.

## Exercise

Implement the chaining version with the same API and run the same property test against it. Then compare the average chain length with the probe length at 75% load. Predict the winner first.

## What's next

The next post is "Stacks, queues and deques". After keys and hashes, it goes to the opposite extreme: no keys at all, just access restricted on purpose.
