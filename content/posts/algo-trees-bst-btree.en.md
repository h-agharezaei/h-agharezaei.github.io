+++
date = '2027-02-01T10:00:00+03:30'
draft = false
title = 'Search trees and the B-tree'
description = 'Search trees in Go: a binary search tree, why sorted input makes it a list, AVL rotations, and why B-trees are wide, with real heights and counts.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "trees", "bst", "avl", "b-tree", "go"]
cover = { image = "/images/covers/algo-trees-bst-btree.png", alt = "Search trees and the B-tree", hiddenInSingle = true }
+++

Imagine a phone book that keeps getting new contacts. If you keep it in a sorted array, search is fast with [binary search](/posts/algo-binary-search-invariants/), but every new contact means shifting half the array to make room. If you keep it in a linked list, adding is cheap but search must look at everything. A {{< term "binary-search-tree" "binary search tree" >}} promises to do both in about log n steps. [Sorting: quick, merge and heap](/posts/algo-sorting/) produced order once; a search tree keeps data ordered while it changes, as long as it stays **balanced**.

And that condition can be lost: insert 10,000 keys in sorted order into a plain search tree and you get a linked list. The height is 10,000 and a search takes about 4,992 comparisons, instead of 12.4 in a balanced tree. This post is about that gap, the trick that closes it (AVL), and a wider form of the same idea that databases use (the B-tree, which we saw from the outside in [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/)). The idea is binary search, made dynamic.

> Go 1.27, local example, re-run for this post, tests with `go test -race`. What I measure is height and comparison counts, which are deterministic, so they do not depend on how busy the machine is, and I publish no timings.

## A binary search tree

Each node holds a key and at most two children: left and right. One rule determines everything, and it is our invariant:

> For every node, all keys in the left subtree are smaller than its key and all keys in the right subtree are larger.

Inserting 50, 30, 70, 20, 40, 60, 80 in that order builds this tree:

```
        50
       /  \
     30    70
    /  \   /  \
   20  40 60  80
```

**Search** is binary search, on a tree: to find 60 we compare with the root (50). 60 is larger, so we look only in the right subtree. Then compare with 70: smaller, so go left. Then 60 is found. Three comparisons for seven keys, and every step throws half the tree away. **Insert** walks the same path and, when it reaches an empty spot, attaches the new node there: 65 goes right from 50, left from 70, right from 60, and becomes the right child of 60.

**Delete** has three cases. If the node has no children, you just cut it off. If it has one child, that child takes its place. If it has two children (like deleting the root, 50), you cannot just remove it. The smallest key of the right subtree, the **in-order successor** (60: go right once, then left as far as possible), takes its place, because it is larger than everything on the left and smaller than everything else on the right, so the invariant survives:

```
        60
       /  \
     30    70
    /  \   /  \
   20  40 65  80
```

(65, the right child of the old 60, took 60's place in the subtree of 70.) My generic version takes a compare function. The delete code works on `pp`, a pointer to "the link that points to the node", so changing it needs no separate parent variable:

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

The first case covers both "no child" and "only a right child". In the two-children case, `sp` walks down to the leftmost node of the right subtree (`s`, the successor), `s` is pulled out of its old place (its right child takes over), and it is put where `x` was.

There are also pre-order, post-order, level-order (with a queue) and in-order {{< term "tree-traversal" "traversals" >}}. In-order means "left first, then the node, then right", and because of the invariant it returns the keys sorted. For the tree above: 20, 30, 40, 50, 60, 70, 80. `Range(lo, hi)` skips subtrees that cannot match. A test runs 20,000 random inserts and deletes against an oracle (a sorted slice, the simple and trustworthy way) and compares contents, searches and ranges. It passes.

## Sorted input kills it

Now back to the promise at the start. The cost of every operation is the height of the tree (the number of nodes on the longest path). See what happens when we insert 1, 2, 3, 4 in order: 1 is the root; 2 is larger, so it is the right child; 3 is the right child of 2; 4 the right child of 3. A chain, that is, a linked list, and every search goes to the end of it.

I measured this with code: keys 0 to n-1 inserted once in order and once shuffled (seed 42). I counted the height with an iterative loop so the degenerate tree cannot overflow the stack. I explain the AVL column in the next section; for now compare the BST with the last two columns: `min` is the smallest possible height for n keys and `max` is the height limit that AVL guarantees:

```
n=1000   sorted   BST=1000  AVL=10  min=ceil(log2(n+1))=10  max<1.44*log2(n+2)=14.4
n=1000   shuffled BST=20    AVL=12  min=ceil(log2(n+1))=10  max<1.44*log2(n+2)=14.4
n=10000  sorted   BST=10000 AVL=14  min=ceil(log2(n+1))=14  max<1.44*log2(n+2)=19.1
n=10000  shuffled BST=35    AVL=16  min=ceil(log2(n+1))=14  max<1.44*log2(n+2)=19.1
```

Sorted input gives the BST a height of n: a linked list. Shuffled input gives 20 and 35, close to the log₂ n scale. Same data, same code, only the order differs. So a plain tree is fine for random keys, but keys that usually arrive in order, such as timestamps or increasing IDs, are exactly what breaks it.

## AVL: repair with rotations

The fix is for the tree to rebalance itself after every insert and delete. An {{< term "avl-tree" "AVL tree" >}} adds a second invariant: for every node, the heights of the left and right subtrees differ by at most 1. Because of this, the height never exceeds about 1.44 log₂ n (the `max` bound in the table). AVL stores each node's height and, after every insert or delete, fixes any node that broke the rule with a {{< term "tree-rotation" "rotation" >}}.

A rotation is a small rearrangement of links that does not disturb the key order but reduces the height. Say 3, 2, 1 were inserted and we built a left-left chain. We lift node 2 up and make 3 its right child:

```go
func rotR[K any](y *node[K]) *node[K] { // y.left becomes the root
	x := y.left
	y.left, x.right = x.right, y
	upd(y); upd(x)
	return x
}
```

`x` is the left child of `y`. The right subtree of `x` (keys between `x` and `y`) moves to be the left child of `y`, `y` becomes the right child of `x`, the heights are updated (`y` first, because it is lower now) and `x` is returned as the new root of this subtree. There are four cases. LL and RR (a straight chain) need one rotation, and LR and RL (a zigzag) need two: first rotate the child so the chain becomes straight. In every case three keys end up balanced:

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

After inserting each of these four orders, the demo printed the tree in level order, the root first and then its children:

```
LL insert [3 2 1]: BST [3 2 1] -> AVL [2 1 3]
RR insert [1 2 3]: BST [1 2 3] -> AVL [2 1 3]
LR insert [3 1 2]: BST [3 1 2] -> AVL [2 1 3]
RL insert [1 3 2]: BST [1 3 2] -> AVL [2 1 3]
```

The plain BST keeps the chain as inserted (root 3 or 1), while AVL turned all four into `[2 1 3]`: root 2 with children 1 and 3. A test checks order, stored heights and the balance rule after every one of 20,000 random operations, and after 10,000 sorted inserts. In the table above, the AVL height is 10 and 14 for sorted input (the minimum possible) and 12 and 16 for shuffled input, always below the 1.44 log₂ bound.

Now the real cost: 100,000 random searches in a tree of 10,000 keys, counting how many times the compare function was called:

```
BST, shuffled input    total=1903183    per search=19.0
BST, sorted input      total=499193738  per search=4991.9
AVL, sorted input      total=1236443    per search=12.4
```

The plain tree with shuffled input needs about 19 comparisons per search (the program also printed `log2(10000)=13.3`). The same tree with sorted input needs about 4,992, roughly 400 times the AVL's 12.4. More notably: AVL fed the same bad sorted input, at 12.4 comparisons, even beats the plain tree fed random input.

## Why databases use wide trees

A binary tree is shallow in comparisons, but each node is a separate read. Disks and databases read whole **pages**, several kilobytes at a time, so if a node holds only one key most of the page is wasted. The {{< term "b-tree" "B-tree" >}} fixes this: each node keeps hundreds of sorted keys and points to children between the keys. For example, a node with two keys has three children:

```
            [ 40 | 80 ]
           /     |     \
   [10 20 30] [50 60 70] [90 100 110]
```

To find 60: at the root we see it is between 40 and 80, so we take the middle child. There we scan the keys (a binary search inside the node itself) and find 60. We read two nodes, for nine keys. The number of children per node is called the {{< term "fan-out" "fan-out" >}}. When a node is full and a new key arrives, the node is split in two and the middle key goes up to the parent; this makes the tree grow taller from the top, so all leaves always stay at the same depth and the tree never degenerates.

The height of a B-tree is about the logarithm of n in base fan-out. This table was computed by a simple loop (the smallest h with fanout^h ≥ n), not from a real B-tree:

```
fanout   n=1e6      n=1e9
2        20         30
16       5          8
128      3          5
512      3          4
```

With fan-out 2, a binary tree, a billion keys need 30 levels. With fan-out 512 only 4. This is what we saw in [B-tree indexes and EXPLAIN ANALYZE](/posts/db-indexes-btree-explain/): the index on `orders.customer_id` (200k rows) had 232 pages (1856 KB) and two levels, a root and leaves, and the primary key index had three levels, which is why `WHERE id = 123` cost only 7 buffers. I did not implement a B-tree here, and I did not try `github.com/google/btree`.

## Trade-offs of search trees

- **Plain BSTs are fine for random keys,** dangerous for ordered keys such as timestamps or IDs (see the height table).
- **AVL guarantees O(log n)** but pays with height bookkeeping and rotations on every write.
- **Pointer-chasing trees in memory have poor {{< term "cache-locality" "cache locality" >}},** because every node lives somewhere else; wide nodes help there too.
- **In Go, a sorted slice with `slices.BinarySearch` is often enough** when reads dominate.
- **Test trees against a trivial oracle,** and check the invariant after every operation.

## Exercise

Add `Min`, `Max` and `Floor(k)` (the largest key at most k) to the BST, and test `Floor` against the sorted-slice oracle with `slices.BinarySearch`.

## What's next

"Tries and union-find". Two more tree shapes, one for string prefixes and one for grouping connected items.
