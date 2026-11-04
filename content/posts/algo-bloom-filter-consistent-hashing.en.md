+++
date = '2027-05-06T10:00:00+03:30'
draft = false
title = 'Bloom filters and consistent hashing'
description = 'Bloom filters and consistent hashing in Go: measured false-positive rates, memory, keys remapped when a node is added, vnode balance and rendezvous.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "bloom-filter", "consistent-hashing", "hashing", "go"]
cover = { image = "/images/covers/algo-bloom-filter-consistent-hashing.png", alt = "Bloom filters and consistent hashing", hiddenInSingle = true }
+++

Imagine you run four cache servers and decide which one stores a key with `hash(key) % 4`. Traffic grows and you add a fifth. Now the formula is `hash(key) % 5`, and I counted what happens: of 100,000 keys, 80,194 now belong to a different server. Almost the whole cache is suddenly in the wrong place. A hash ring, the idea in the second half of this post, moved only 22,588 in the same test.

Both ideas in this post are built on hashing, the same trick as in [A hash table from scratch](/posts/algo-hash-tables/). A {{< term "bloom-filter" "Bloom filter" >}} answers "is this key in the set?" with very little memory, at the price of sometimes saying yes wrongly. {{< term "consistent-hashing" "Consistent hashing" >}} decides which server owns a key, so that adding or removing a server moves few keys. The previous post was [String algorithms: KMP and Rabin–Karp](/posts/algo-string-algorithms/).

> I re-ran every output with Go 1.27 on macOS (arm64). It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish counts and bytes, not timings. The hash is FNV-1a followed by a splitmix64 mixing step.

## Bloom filter

### The idea, with a few bits

Start with a row of 10 bits, all 0. A Bloom filter has `k` hash functions; every key is turned into `k` positions in the row. To **add** a key you set those `k` bits to 1. To **ask** whether a key is present you look at its `k` positions: if any bit is 0, the key was definitely never added. If all of them are 1, the answer is "maybe".

Here is a tiny picture with `k` = 2. The positions below are made up by me for the illustration, not real hash output. Suppose `cat` hashes to positions 1 and 4, and `dog` to positions 4 and 7. After adding both, the row looks like this:

```
position: 0 1 2 3 4 5 6 7 8 9
bits:     0 1 0 0 1 0 0 1 0 0
```

Now we ask about two keys that were never added. Suppose `fox` hashes to 2 and 4: bit 2 is 0, so the filter says "definitely not here", and it is right. Suppose `cow` hashes to 1 and 7. Both of those bits are 1, because `cat` set one and `dog` set the other. The filter says "maybe", but `cow` was never added. This is a **false positive**: bits set by different keys happen to cover a key that was not added.

Two things follow from the picture. A key that was added can never be reported missing, because its bits are 1 and nothing ever sets a bit back to 0. So there are no false negatives. And the more keys you add, the more bits are 1, so the more likely a stranger's positions are all covered.

### How wrong is it, and how much memory does it save?

Let `m` be the number of bits, `n` the number of keys added and `k` the number of positions per key. In my code the `k` positions come from two hashes, `h1` and `h2`: position `i` is `h1 + i·h2` mod `m`. This is called double hashing, and it avoids computing `k` separate hashes.

The standard approximation for the false-positive rate is p ≈ (1 − e^(−kn/m))^k, and the best `k` for given `m` and `n` is (m/n)·ln 2. These formulas assume the positions behave like independent random numbers, so I wanted to see how well they match real data. The demo inserts n = 10,000 keys and then probes 100,000 keys that were never inserted (fixed names, so the run is deterministic), counting how many the filter claims to have:

```
      m      k  bytes  false+  measured%  formula%  k_opt
  40000      3   5000   14595    14.595    14.689   2.77
  80000      6  10000    2100     2.100     2.158   5.55
 100000      7  12504     793     0.793     0.819   6.93
 100000      3  12504    1736     1.736     1.741   6.93
 200000     14  25000       7     0.007     0.007  13.86
```

Each row is one filter size. `bytes` is the memory of the bit array, `false+` is the number of wrong "maybe" answers out of 100,000, `measured%` is that as a percentage, and `formula%` is what the formula predicts. The measured rate is a little below the formula in the first four rows. The largest gap relative to the formula is in the third row, 0.793% against 0.819%, about 3% lower; in the others it is 0.3% to 2.7% lower, and in the last row both round to 0.007%. So in this run the formula describes the measurements well.

Reading the rows: with 10 bits per key and `k` = 7 (third row), about 0.8% of strangers pass. Using `k` = 3 with the same memory (fourth row) gives 1.736%, more than twice the error (the formula predicted 1.741% against 0.819%). The best `k` for this size is about 6.93, so 7 is the sensible choice. Doubling the memory and using `k` = 14 brings the rate down to 0.007%.

For memory, the filter above (third row) is 12,504 bytes. For comparison I put the same 10,000 keys in a `map[string]struct{}` and measured the heap growth with `runtime.MemStats`: 435,384 bytes in the earlier run and 435,416 in this one (such numbers shift a little from run to run). The key strings were already allocated before the measurement and are not counted, so a real set costs more than that. The filter is about 35 times smaller, but it cannot list its keys or give them back.

A test adds 5,000 keys and checks that every one is found, which is the no-false-negatives guarantee in code.

### Deleting

**You cannot delete from a plain Bloom filter.** Setting a key's bits back to 0 could also erase another key that shares one of them; in the picture above, removing `cat` by clearing bits 1 and 4 would break `dog`. A counting variant keeps a small counter per position instead of a bit. Add increments the counters, Remove decrements them, and a position counts as set while its counter is above zero:

```
counting: after Remove(item-5) Has(item-5) = false  Has(item-6) = true
```

After removing `item-5`, the filter no longer reports it, and its neighbour `item-6` is still found. The price is memory: 8 bits per position in my version instead of 1. (My counters stop at 255, which is a limit of this simple version.)

### Where it helps

Put a Bloom filter in front of a slow lookup. A "no" answer is certain, so you skip the database entirely; a "maybe" goes on to the real lookup, which also catches the false positives. This blocks what is called cache penetration: requests for keys that never exist, which miss the cache every time and hit the database (see [Rate limiting and caching](/posts/go-rate-limiting-caching/) for the cache side). I believe LSM-tree databases such as RocksDB use Bloom filters to skip files that cannot contain a key, but I did not verify that here. I also did not check Postgres's `bloom` extension.

## Consistent hashing

### Why `% N` fails, and the ring

Back to the opening. With `hash(key) % N`, changing N changes the answer for almost every key. A small example shows why. Pretend the hash of a key is the key itself, and look at keys 0 to 11 when N goes from 3 to 4. Key 3 was on server 0 and now it is on server 3; key 4 moves from 1 to 0, and so on. Only keys 0, 1 and 2 stay put; the other 9 of the 12 move. In the real test, going from four servers to five moved 80% of the keys, where the ideal is 20%: the new server should take only its fair share, a fifth.

Consistent hashing fixes this by changing the question. Imagine a ring of positions, here 0 to 99 for the example (in the code they are 64-bit hash values). Each server is placed on the ring at a point given by hashing its name. A key is hashed to a point too, and it belongs to the first server point you meet going clockwise. Say server A is at 10, B at 40 and C at 70. Key 25 goes to B, key 55 goes to C, and key 85 goes past 99, wraps around, and lands on A.

Now add server D at 60. Which keys change owner? Only those between 40 and 60, which used to belong to C (their next point clockwise was 70) and now belong to D. Everything else still finds the same point first. Keys never move between the old servers, only onto the new one. And removing D again would hand those keys back to C.

In code, I keep the points in a sorted slice and find a key's owner with binary search, wrapping around at the end ([Binary search and invariants](/posts/algo-binary-search-invariants/)).

### Virtual nodes

With one point per server the arcs between points are uneven, so some servers own much more than others. The fix is to give each server many points, called virtual nodes or vnodes: `node-0#0`, `node-0#1` and so on, each hashed separately. The many small arcs average out.

The demo moves from 4 to 5 nodes with 100,000 keys and compares three methods, mod-N, the ring with 100 vnodes per node, and rendezvous hashing (explained in a moment):

```
mod-N        moved: 80194
ring vn=100  moved: 22588
rendezvous   moved: 20137
ring: moved keys that landed on node-4: 22588
```

`moved` is how many keys have a different owner after adding the fifth node. Mod-N moved about 80%. The ring moved 22.6%, close to the ideal 20%, and the last line shows that all 22,588 moved keys landed on the new node, which a test also checks. Going back from 5 nodes to 4 by removing `node-4` moved exactly 22,588 keys, the ones that lived on it. The ring's 22.6% is a bit above 20% because the new node's share by chance is a little more than a fifth.

How even is the split? The next output shows, for 5 nodes and 100,000 keys, the busiest node's load divided by the mean load, and then the standard deviation of the loads as a percentage of the mean:

```
ring vn=1     2.378  71.5%
ring vn=10    1.574  35.5%
ring vn=100   1.129  11.6%
ring vn=1000  1.051  5.3%
rendezvous    1.010  0.7%
```

A perfect split would be 1.000 and 0%. With one point per node the busiest node held 2.4 times its fair share, which is terrible. More vnodes fix it, at the cost of a bigger sorted slice.

Weights are easy to add: give a node more vnodes. With `node-0` at weight 3 and the others at 1, the four nodes held `49324 17256 18233 15187` keys, roughly 3:1:1:1.

## Rendezvous hashing

{{< term "rendezvous-hashing" "Rendezvous hashing" >}} gets the same "few keys move" property without any ring. For a given key, compute a score for every node by hashing the node name together with the key, and give the key to the node with the highest score:

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

Adding a node only changes the winner for keys where the new node's score is the highest, so only those move. In the run above it moved 20,137 keys (close to the ideal 20%) and balanced best (1.010). The cost is that every lookup scores all the nodes: O(nodes), instead of O(log points) for the ring. That is fine for tens of nodes and worse for thousands.

## Limits of both

- **A Bloom filter must be sized in advance for `n`.** Past that number the error rises quickly, because more and more bits are 1.
- **Hash quality matters.** I added the mixing step after FNV because, as a comment in my code says, FNV's low bits are weak; I did not measure the version without it.
- **Choosing the owner is only part of the problem.** Replicas, failures and moving the data itself are separate. I come back to them in [Sharding and consistent hashing](/posts/ds-sharding-consistent-hashing/), which starts from the ring code here.
- **My results come from one set of keys.** Do not treat 22.6% as a constant; with other names or other vnode counts it will be a little different.

## Exercise

Make the Bloom filter grow: when the estimated count passes `n`, build a bigger one. What do you need to keep in order to rebuild it? Then measure how the ring's moved fraction changes when you go from 10 to 11 nodes.

## What's next

The Algorithms series ends here. Sharding and consistent hashing come back in the Distributed Systems series, where owners can fail and data must follow.
