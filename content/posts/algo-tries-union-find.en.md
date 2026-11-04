+++
date = '2027-02-17T10:00:00+03:30'
draft = false
title = 'Tries and union-find'
description = 'Tries and union-find in Go: prefix sharing on a real word list, autocomplete, parent-hop counts for path compression, and Kruskal on a small graph.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "trie", "union-find", "disjoint-set", "kruskal", "go"]
cover = { image = "/images/covers/algo-tries-union-find.png", alt = "Tries and union-find", hiddenInSingle = true }
+++

When you type "tri" into a search box and a list of words starting with it appears, how does the program find them? The hash table from [A hash table from scratch](/posts/algo-hash-tables/) finds an exact key quickly, but not "all keys that start with tri". A sorted array with binary search could do it, but there is a structure made for exactly this: the {{< term "trie" "trie" >}} (said "try"), a tree in which every path spells a prefix. The macOS word list has 2,039,158 characters, yet a trie of all its words needs only 696,834 nodes, because prefixes are shared.

The second half of this post is about a different question: "are these two things in the same group?" For example, are two people in a friendship network connected, or are two cells on the same island? A structure called {{< term "union-find" "union-find" >}} answers this in almost constant time. Both structures are trees, but unlike the [search trees and B-tree](/posts/algo-trees-bst-btree/) of the previous post, a trie never compares whole keys; it walks characters, so its cost depends on the key length, not the key count. And union-find sees the tree upside down: each child points to its parent. [A hash table from scratch](/posts/algo-hash-tables/) and [Big-O analysis with real measurements](/posts/algo-big-o-measured/) are good background.

> Go 1.27, local example, re-run for this post, tests with `go test -race`. The machine was busy, so I publish no timings: only counts and bytes. (The allocated bytes move by a few thousand from run to run; the numbers below are from one of the runs.)

## A trie

The idea is simple: each node stands for one character (a rune), and the path from the root to a node spells a prefix. An `end` flag on a node says "a complete word ends right here". Take the words `car`, `cart`, `cat` and `dog` (a star means the `end` flag):

```
(root)
 ├─ c ─ a ─ r* ─ t*
 │       └─ t*
 └─ d ─ o ─ g*
```

`car`, `cart` and `cat` share their first two characters: `c` and `a` are stored only once. For `Search("ca")` the path `c-a` exists but the `a` node has no `end` flag, so the answer is false (not a word), while `HasPrefix("ca")` is true (it is a prefix). For a prefix with no path at all, such as `xq`, both are false. `Insert` walks the same path and creates the missing nodes. All three take only as many steps as the word is long, no matter how many words the trie holds.

```go
type tnode struct {
	next map[rune]*tnode
	end  bool
}
```

Each node has a map from character to child. `Autocomplete(prefix, limit)` first finds the prefix node (say the `a` node in `ca`), then walks everything below it visiting children in sorted order, so the result comes out alphabetically (`car`, `cart`, `cat`), and stops as soon as it reaches `limit`.

For real sizes I loaded the words from `/usr/share/dict/words` (the macOS word list), keeping only those made entirely of lowercase `a-z` letters (the code drops the rest), and inserted them all:

```
words=210773 chars=2039158 trie nodes=696834 (34.2% of chars)
Search(trie) false Search(tri) true HasPrefix(tri) true HasPrefix(xq) false
Autocomplete("algo", 5): [algocyan algodoncillo algodonite algoesthesiometer algogenic]
Autocomplete("trie", 10): [tried triedly trielaidin triene triennial trienniality triennially triennium triens triental]
```

Line one: 210,773 words with 2,039,158 characters in total, yet the trie has only 696,834 nodes, which is 34.2% of the character count; about two thirds of the characters cost nothing because the prefixes are shared. Line two: `Search("trie")` is false because this list does not contain "trie" as a word, but `Search("tri")` is true because "tri" is in the list. `HasPrefix("tri")` is true and `HasPrefix("xq")` is false. The last two lines are autocompletes: the first five words with the prefix `algo` and the first ten with `trie`, in alphabetical order (the list lacks the word `trie` itself, but has words that start with it).

The tests compare a trie against a map and a sorted traversal on random words, and a separate test with the Persian words "سلام" and "سلامت" shows that runes work correctly.

## Map nodes or array nodes

There is a design choice: children in a map or in an array? A map node is small to declare, but the map itself takes separate memory. A `[26]*anode` node (one pointer for each letter a to z) has fixed indexing and no map, but it holds 26 pointers even for a leaf. Struct sizes with `unsafe.Sizeof` and bytes allocated while building (via `runtime.MemStats`, so treat them as approximate):

```
Sizeof map node: 16  array node: 216  map header pointer: 8
bytes allocated: map trie=112873376 (162/node), array trie=156090816 (224/node)
```

On this list the array trie is bigger: about 224 bytes per node against 162, and it covers only `a-z`. Each step may be faster; I did not measure that. Where nodes have few children, which is true of most nodes deeper in the tree, the map is cheaper.

## Union-find

Now the second question: grouping. Suppose we have 6 people numbered 0 to 5, and messages arrive: "0 and 1 became friends", "2 and 3 became friends", "1 and 3 became friends". After each message we want to ask "are 0 and 3 in the same group?"

The idea: each group is a tree and the root of the tree represents the group. We keep just one array, `parent`; `parent[i]` is the parent of i, and a root is its own parent. Our invariant: **two elements are in the same group if and only if they have the same root.** `Find(x)` follows parents up to the root, and `Union(a, b)` hangs one root under the other. With an example, at the start `parent = [0 1 2 3 4 5]` (everyone is a root):

```
Union(0,1): hang the root of 1 under 0      parent = [0 0 2 3 4 5]
Union(2,3): hang the root of 3 under 2      parent = [0 0 2 2 4 5]
Union(1,3): root of 1 (=0) and root of 3 (=2); hang 2 under 0   parent = [0 0 0 2 4 5]
Find(3): 3 -> 2 -> 0   the root is 0; so 0 and 3 are in the same group
```

Since `Find` has to walk the path, it gets slow if the trees get tall. There are two optimizations. {{< term "path-compression" "Path compression" >}}: after `Find` locates the root, connect every node on the path directly to the root. In the example, after `Find(3)` we get `parent[3] = 0`, and next time one step is enough. And {{< term "union-by-size" "union by size" >}}: when merging two trees, hang the smaller under the bigger so the trees do not get tall. My `Find`:

```go
func (u *UF) Find(x int) int {
	r := int32(x)
	for u.parent[r] != r {
		r = u.parent[r]
		u.Hops++
	}
	if u.compress { // second pass: point everything on the path at the root
		c := int32(x)
		for u.parent[c] != r {
			next := u.parent[c]
			u.parent[c] = r
			c = next
		}
	}
	return int(r)
}
```

The first loop finds the root and counts each parent step in `Hops` (only this pass is counted). If path compression is on, the second pass connects the whole path to the root. `Find` is deliberately iterative, not recursive, so a deep tree cannot overflow the stack. My `UF` has a flag for each optimization so we can count every combination.

The worst case first: a chain. `Union(i+1, i)` for 20,000 elements (each time a singleton is added to the big group), then 20,000 calls of `Find(0)`:

```
none              hops(unions)=0      hops(20000 Find(0))=399980000
by size only      hops(unions)=19997  hops(20000 Find(0))=20000
compression only  hops(unions)=0      hops(20000 Find(0))=39998
both              hops(unions)=19997  hops(20000 Find(0))=20000
```

With neither, the tree is a 20,000-long list and every `Find(0)` walks to the end: 20,000 times 19,999 steps, close to 400 million. With union by size, the big root stays the root and `0` is always one step from it: 20,000 steps. With path compression alone, the first `Find(0)` shortens the path (19,999 steps) and every later one takes a single step: 39,998 in total.

Now 100,000 random unions (seed 7) on 100,000 elements, then `Find` on every element. The columns are steps during the unions, steps in the final pass, and the number of groups left:

```
100000 random unions on 100000 elements
none                222100465  552463368     16208
compression only       377426     164241     16208
by size only           180584     183368     16208
both                   134293     110884     16208
```

All four reach the same answer (16,208 groups); only the cost differs. The unoptimized version needed 222 million steps; with both optimizations, 134 thousand. I repeated this on a million elements, without the unoptimized version, which is far too slow:

```
1000000 random unions on 1000000 elements
none                (not run: too slow)
compression only      4365473    1642501    162289
by size only          1823203    1853238    162289
both                  1344183    1108882    162289
```

With both optimizations, a million unions (each has two `Find`s) take 1.3 million steps in total, about 1.3 steps per union. According to the sources I have read, the {{< term "amortized-analysis" "amortized" >}} cost with both optimizations is the inverse Ackermann function, which is below 5 for any practical input; I do not prove it here and have not verified it myself.

## Applications

All four use the same `UF`, and each has a test.

**Connected components.** Eight nodes with edges 0-1, 1-2, 3-4, 5-6, 6-7 and 7-5. The output:

```
components: 3
  [0 1 2]
  [3 4]
  [5 6 7]
```

**Cycle detection.** If we add the edges `[0 1] [1 2] [2 3] [3 1] [4 5]` in order, `Union` returns false at the edge with index 3 (`[3 1]`), because 3 and 1 were already connected (through 2): that edge closes a cycle. The output: `first cycle-closing edge index: 3`.

**Minimum spanning tree.** For a {{< term "minimum-spanning-tree" "minimum spanning tree" >}} with Kruskal's algorithm I sort the edges by weight and keep each edge whose `Union` succeeds (that is, one that does not close a cycle). On 8 nodes and 12 edges, 7 edges remain with a total weight of 17:

```
1-2 w=1   6-7 w=1   1-3 w=2   3-4 w=2   0-2 w=3   5-6 w=3   4-6 w=5
```

A test confirms this weight by brute force over all 4,096 subsets of the edges.

**Counting islands.** In a grid, union every `#` with the `#` to its left and above, and the islands are the groups of `#`:

```
##..#
#...#
..#..
...##
islands: 4
```

Four islands: top-left (three cells), the top-right column (two cells), the lone middle cell, and the two cells at the bottom right. (The test first expected 3, because I had counted by eye and got it wrong; the code was right.)

## Where they fall short

- **A trie spends memory to get prefix queries.** If you only need exact lookup, a map is simpler.
- **Compare node layouts by bytes per node,** not by guessing; here the array turned out bigger than the map.
- **Union-find without the optimizations turns into a list,** so implement both from the start.
- **Write `Find` iteratively, not recursively,** or a deep tree fills the stack.
- **Union-find only merges;** it cannot split a group again.

## Exercise

Add a `Delete` to the trie (it should remove nodes that no longer lead to any word), and test that after inserting and deleting a word the node count returns to its earlier value.

## What's next

"Graphs: BFS and DFS". Union-find only says whether two things are connected; walking a graph also gives you the path and its length.
