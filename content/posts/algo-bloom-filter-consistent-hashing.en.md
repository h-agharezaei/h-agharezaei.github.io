+++
date = '2027-05-06T10:00:00+03:30'
draft = false
title = 'Bloom filters and consistent hashing'
description = 'Bloom filters and consistent hashing in Go: measured false-positive rates, memory, keys remapped when a node is added, vnode balance and rendezvous.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "bloom-filter", "consistent-hashing", "hashing", "go"]
cover = { image = "/images/covers/algo-bloom-filter-consistent-hashing.png", alt = "Bloom filters and consistent hashing", hiddenInSingle = true }
+++

The last post of the series is about two ideas built on hashing, the same trick as in [A hash table from scratch](/posts/algo-hash-tables/). A {{< term "bloom-filter" "Bloom filter" >}} answers "is this key in the set?" with very little memory, at the price of sometimes saying yes wrongly. {{< term "consistent-hashing" "Consistent hashing" >}} decides which server owns a key so that adding a server moves few keys. The previous post was [String algorithms: KMP and Rabin–Karp](/posts/algo-string-algorithms/).

> Go 1.26, local example, tests with `go test -race`. Machine load was not low, so I publish counts and bytes, not timings. Hash: FNV-1a followed by a splitmix64 mixing step.

## Bloom filter

A bit array of m bits and k hash positions per key. Add sets k bits; lookup checks them. One zero bit means "definitely not present", so there are no false negatives. If all are set it means "maybe". I get the k positions from two hashes: position i = h1 + i*h2 mod m (double hashing).

The documented formulas: false-positive rate p ≈ (1 − e^(−kn/m))^k, and the best k is (m/n)·ln 2. I inserted n = 10,000 keys and probed 100,000 keys that were never inserted (fixed names, so the run is deterministic):

```
      m      k  bytes  false+  measured%  formula%  k_opt
  40000      3   5000   14595    14.595    14.689   2.77
  80000      6  10000    2100     2.100     2.158   5.55
 100000      7  12504     793     0.793     0.819   6.93
 100000      3  12504    1736     1.736     1.741   6.93
 200000     14  25000       7     0.007     0.007  13.86
```

The formula matches within a few percent. Ten bits per key with k=7 gives about 0.8% false positives. Using k=3 with the same memory doubles the error, as the formula said.

Memory: the filter above is 12,504 bytes. A `map[string]struct{}` with the same 10,000 keys grew the heap by 435,384 bytes (a `runtime.MemStats` delta; the key strings were already allocated and are not counted, so a real set costs more). The filter is far smaller, but it cannot list or return keys.

A test adds 5,000 keys and checks every one is found (no false negatives).

**Deletion is impossible**: clearing a bit could erase another key. A counting variant keeps a small counter per position; Remove decrements:

```
counting: after Remove(item-5) Has(item-5) = false  Has(item-6) = true
```

It costs 8 bits per cell here instead of 1.

Where it helps: put it in front of a slow lookup. A "no" skips the database, which blocks cache penetration (keys that never exist) in a cache like [Rate limiting and caching](/posts/go-rate-limiting-caching/). I believe LSM-tree databases such as RocksDB use Bloom filters to skip files that cannot contain a key, but I did not verify that here. I also did not check Postgres's `bloom` extension.

## Consistent hashing

With `hash(key) % N`, changing N changes almost every key. Consistent hashing puts node points on a ring of 64-bit hashes, and a key belongs to the next point clockwise. I store the points in a sorted slice and use binary search ([Binary search and invariants](/posts/algo-binary-search-invariants/)), wrapping around at the end. Each node gets many virtual nodes (vnodes) to even out the shares.

Moving from 4 to 5 nodes, with 100,000 keys:

```
mod-N        moved: 80194
ring vn=100  moved: 22588
rendezvous   moved: 20137
ring: moved keys that landed on node-4: 22588
```

Mod-N moved about 80% (ideal for a fifth node is 20%). The ring moved 22.6%, and every moved key went to the new node, which a test also checks. Removing node-4 again moved exactly the 22,588 keys that lived on it.

Balance on 5 nodes, as max load divided by mean and standard deviation as a share of the mean:

```
ring vn=1     2.378  71.5%
ring vn=10    1.574  35.5%
ring vn=100   1.129  11.6%
ring vn=1000  1.051  5.3%
rendezvous    1.010  0.7%
```

One point per node is terrible: one node held 2.4 times its fair share. More vnodes fix it at the cost of a bigger sorted slice.

Weights are easy: give a node more vnodes. With node-0 at weight 3 the counts were `49324 17256 18233 15187`, roughly 3:1:1:1.

## Rendezvous hashing

{{< term "rendezvous-hashing" "Rendezvous hashing" >}} needs no ring:

```go
func Rendezvous(nodes []string, key string) string {
	best, bs := "", uint64(0)
	for _, n := range nodes {
		if s := hash64(n + "|" + key); best == "" || s > bs {
			best, bs = n, s
		}
	}
	return best
}
```

It moved 20,137 keys (close to the ideal 20%) and balanced best (1.010). The cost is O(nodes) per lookup instead of O(log points). Fine for tens of nodes, worse for thousands.

## A few things to watch

- A Bloom filter must be sized in advance for n; past that, the error rises quickly.
- Hash quality matters: I added a mixing step because raw FNV on similar names is weak.
- Replicas, failures and rebalancing data are a separate problem from choosing the owner.
- My results come from one key set; do not treat 22.6% as a constant.

## Exercise

Make the Bloom filter grow: when the estimated count passes n, build a bigger one. What do you need to keep to rebuild it? Then measure how the ring's moved fraction changes between 10 and 11 nodes.

## What's next

The Algorithms series ends here. Sharding and consistent hashing come back in the Distributed Systems series, where owners can fail and data must follow.
