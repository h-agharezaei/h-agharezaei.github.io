+++
date = '2027-02-17T10:00:00+03:30'
draft = false
title = 'Tries and union-find'
description = 'Tries and union-find in Go: prefix sharing on a real word list, autocomplete, parent-hop counts for path compression, and Kruskal on a small graph.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "trie", "union-find", "disjoint-set", "kruskal", "go"]
cover = { image = "/images/covers/algo-tries-union-find.png", alt = "Tries and union-find", hiddenInSingle = true }
+++

In the previous post, [Search trees and the B-tree](/posts/algo-trees-bst-btree/), keys were compared with each other. Two structures break that habit. A {{< term "trie" "trie" >}} walks the characters of a key, so its cost depends on the key length, not on how many keys exist. {{< term "union-find" "Union-find" >}} answers one question, "are these two things in the same group?", in almost constant time. Both are close relatives of the ideas in [A hash table from scratch](/posts/algo-hash-tables/) and [Big-O analysis with real measurements](/posts/algo-big-o-measured/).

> Go 1.26, local example, tests with `go test -race`. The load on this machine was above 4 when I ran it, so there are no timings: only counts and bytes.

## A trie

Each node has children keyed by one rune, plus an `end` flag. `Insert`, `Search` and `HasPrefix` walk one path:

```go
type tnode struct {
	next map[rune]*tnode
	end  bool
}
```

`Autocomplete(prefix, limit)` finds the prefix node, then walks everything below it in sorted order and stops at `limit`. I loaded the lowercase words of `/usr/share/dict/words` (the macOS word list) and inserted them all:

```
words=210773 chars=2039158 trie nodes=696834 (34.2% of chars)
Search(trie) false Search(tri) true HasPrefix(tri) true HasPrefix(xq) false
Autocomplete("algo", 5): [algocyan algodoncillo algodonite algoesthesiometer algogenic]
Autocomplete("trie", 10): [tried triedly trielaidin triene triennial trienniality triennially triennium triens triental]
```

The words have 2,039,158 characters in total, but the trie needs only 696,834 nodes: words share their prefixes, so about two thirds of the characters cost nothing. (`Search("trie")` is false because this list does not contain "trie" as a word, while "tri" is there.) A test compares the trie against a map and a sorted scan on random words, including Persian text, so runes work.

## Map nodes or array nodes

A node with a map is small to declare but the map allocates on its own. A node with `[26]*anode` has constant-time indexing and no map, but it carries 26 pointers even for a leaf. `unsafe.Sizeof` and the bytes allocated while building (measured here with `runtime.MemStats`, so treat them as approximate):

```
Sizeof map node: 16  array node: 216  map header pointer: 8
bytes allocated: map trie=112873376 (162/node), array trie=156090816 (224/node)
```

On this word list the array trie is bigger, about 224 bytes per node against 162, and it only handles `a-z`. It would be faster per step; I did not measure that. Maps cost less where nodes have few children, which is most of them deep in the tree.

## Union-find

Keep a `parent` array. A set is a tree and its root is the representative. `Find` follows parents to the root; `Union` links one root under the other. Two optimizations: {{< term "path-compression" "path compression" >}} (during `Find`, point the whole path at the root) and {{< term "union-by-size" "union by size" >}} (hang the smaller tree under the larger). My `UF` has flags for both and counts every parent hop. First a chain, `Union(i+1, i)` for 20,000 elements, then 20,000 calls of `Find(0)`:

```
none              hops(unions)=0      hops(20000 Find(0))=399980000
by size only      hops(unions)=19997  hops(20000 Find(0))=20000
compression only  hops(unions)=0      hops(20000 Find(0))=39998
both              hops(unions)=19997  hops(20000 Find(0))=20000
```

Without either, the tree is a 20,000-long list and every `Find` walks it. Now random unions (seed 7), then a `Find` on every element:

```
100000 random unions on 100000 elements
none                222100465  552463368
compression only       377426     164241
by size only           180584     183368
both                   134293     110884

1000000 random unions on 1000000 elements
none                (not run: too slow)
compression only      4365473    1642501
by size only          1823203    1853238
both                  1344183    1108882
```

Columns are hops during the unions and hops in the final pass. The unoptimized version needed 222 million hops for 100,000 elements, so I did not run it at 1M. With both optimizations 1M unions cost about 1.3 hops each. According to the literature the {{< term "amortized-analysis" "amortized" >}} cost is the inverse Ackermann function, which is below 5 for any practical input; I am not proving it here.

## Applications

All four use the same `UF`, and tests cover each. Components of 8 nodes with edges 0-1, 1-2, 3-4, 5-6, 6-7, 7-5 give `components: 3` with groups `[0 1 2]`, `[3 4]`, `[5 6 7]`. Adding edges `[0 1] [1 2] [2 3] [3 1] [4 5]` in order, `Union` returns false on index 3: that edge closes a cycle. For Kruskal's {{< term "minimum-spanning-tree" "minimum spanning tree" >}} I sort edges by weight and keep each one whose `Union` succeeds. On 8 nodes and 12 edges it keeps 7 edges, total weight 17:

```
1-2 w=1   6-7 w=1   1-3 w=2   3-4 w=2   0-2 w=3   5-6 w=3   4-6 w=5
```

A test checks this weight against brute force over all 4,096 edge subsets. For a grid, union each `#` with its left and top `#`; on a 4x5 grid the number of islands printed is 4 (the test first expected 3, my mistake in counting by eye, and the code was right).

## A few things to watch

- A trie trades memory for prefix queries; for exact lookups only, a map is simpler.
- Compare node layouts by bytes per node, not by guesses.
- Without optimizations union-find degrades to a list; implement both from the start.
- `Find` should be iterative, not recursive, or a deep tree can overflow the stack.
- Union-find only merges. It cannot split a group.

## Exercise

Add `Delete` to the trie (remove nodes that no longer lead to a word) and test that the node count drops back after inserting and deleting one word.

## What's next

Graphs: BFS and DFS.
