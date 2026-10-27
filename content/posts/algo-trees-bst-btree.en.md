+++
date = '2027-02-01T10:00:00+03:30'
draft = false
title = 'Search trees and the B-tree'
description = 'Search trees in Go: a binary search tree, why sorted input makes it a list, AVL rotations, and why B-trees are wide, with real heights and counts.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "trees", "bst", "avl", "b-tree", "go"]
cover = { image = "/images/covers/algo-trees-bst-btree.png", alt = "Search trees and the B-tree", hiddenInSingle = true }
+++

In the previous post, [Sorting: quick, merge and heap](/posts/algo-sorting/), we produced order once. A search tree keeps data ordered while it changes, so insert, search and delete stay cheap. It is the idea behind [Binary search and invariants](/posts/algo-binary-search-invariants/) made dynamic, and its wide cousin is the index from [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/).

> Go 1.26, local example, tests with `go test -race`. The load on this machine was too high for timings (3.97 at the last check), so everything is deterministic: heights and comparison counts.

## A binary search tree

A {{< term "binary-search-tree" "binary search tree" >}} puts smaller keys in the left subtree and larger in the right. My generic version takes a compare function; search and insert walk one path. `Delete` has the three classic cases:

```go
switch {
case x.left == nil:  *pp = x.right // no child, or only a right child
case x.right == nil: *pp = x.left  // only a left child
default: // two children: swap in the in-order successor
	sp := &x.right
	for (*sp).left != nil { sp = &(*sp).left }
	s := *sp
	*sp = s.right
	s.left, s.right = x.left, x.right
	*pp = s
}
```

It also has pre-order, post-order, level-order (a queue) and in-order {{< term "tree-traversal" "traversals" >}}; in-order returns sorted keys. `Range(lo, hi)` skips subtrees that cannot match. A test runs 20,000 random inserts and deletes against a sorted-slice oracle and compares contents, searches and ranges. It passes.

## Sorted input kills it

Height is the cost of every operation. I inserted keys 0..n-1 in order, then the same keys shuffled (seed 42), counting height with an iterative loop so the degenerate tree cannot overflow the stack:

```
n=1000   sorted   BST=1000  AVL=10  min=ceil(log2(n+1))=10  max<1.44*log2(n+2)=14.4
n=1000   shuffled BST=20    AVL=12  min=ceil(log2(n+1))=10  max<1.44*log2(n+2)=14.4
n=10000  sorted   BST=10000 AVL=14  min=ceil(log2(n+1))=14  max<1.44*log2(n+2)=19.1
n=10000  shuffled BST=35    AVL=16  min=ceil(log2(n+1))=14  max<1.44*log2(n+2)=19.1
```

Sorted input gives height n: a linked list. Shuffled input gives 20 and 35, close to the log2 n scale. Same data, same code, only the order differs.

## AVL: repair with rotations

An {{< term "avl-tree" "AVL tree" >}} stores each node's height and, after every insert or delete, fixes any node whose subtrees differ by more than 1 using a {{< term "tree-rotation" "rotation" >}}:

```go
func rotR[K any](y *node[K]) *node[K] { // y.left becomes the root
	x := y.left
	y.left, x.right = x.right, y
	upd(y); upd(x)
	return x
}
```

Four cases exist. LL and RR need one rotation, LR and RL two (rotate the child first). In every case three keys end up balanced:

```
LL (3,2,1)   RR (1,2,3)   LR (3,1,2)   RL (1,3,2)
    3            1            3            1
   /              \          /              \
  2                2        1                3
 /                  \        \              /
1                    3        2            2
          all become:   2
                       / \
                      1   3
```

The demo prints level order for each: all four give `[2 1 3]`, while the plain BST keeps the chain. A test checks order, stored heights and the balance rule after every one of 20,000 random operations, and after 10,000 sorted inserts. In the table above, the AVL height is 10 and 14 for sorted input (the minimum possible) and 12 and 16 for shuffled input, always below the 1.44 log2 bound.

Comparisons for 100,000 random searches in a 10,000-key tree:

```
BST, shuffled input    total=1903183    per search=19.0
BST, sorted input      total=499193738  per search=4991.9
AVL, sorted input      total=1236443    per search=12.4
```

The degenerate tree needs about 4,992 comparisons per search, 400 times the AVL's 12.4.

## Why databases use wide trees

Binary trees are shallow in comparisons but each node is a separate read. Disks and databases read whole pages, so a {{< term "b-tree" "B-tree" >}} packs hundreds of keys in a node. Height is about log base {{< term "fan-out" "fan-out" >}} of n, computed by code:

```
fanout   n=1e6      n=1e9
2        20         30
16       5          8
128      3          5
512      3          4
```

In [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/), the index on `orders.customer_id` (200k rows) has 232 pages (1856 KB) and `bt_metap` reports level 1: a root and leaves. The primary key index has level 2, so `WHERE id = 123` cost only 7 buffers. I did not implement a B-tree here, and I did not try `github.com/google/btree`.

## A few things to watch

- Plain BSTs are fine for random keys, dangerous for ordered keys such as timestamps or IDs.
- AVL guarantees O(log n) but pays with extra height bookkeeping on every write.
- Pointer-chasing trees in memory have poor {{< term "cache-locality" "cache locality" >}}; wide nodes help there too.
- In Go, a sorted slice with `slices.BinarySearch` is often enough when reads dominate.
- Test trees against a trivial oracle, and check invariants after every operation.

## Exercise

Add `Min`, `Max` and `Floor(k)` (the largest key at most k) to the BST, and test `Floor` against the sorted-slice oracle with `slices.BinarySearch`.

## What's next

Tries and union-find.
