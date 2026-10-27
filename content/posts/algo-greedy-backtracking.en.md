+++
date = '2027-04-21T10:00:00+03:30'
draft = false
title = 'Greedy algorithms and backtracking'
description = 'Greedy algorithms and backtracking in Go: interval scheduling, coin change, Huffman, N-Queens and Sudoku with real node counts and tests.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "greedy", "backtracking", "huffman", "n-queens", "go"]
cover = { image = "/images/covers/algo-greedy-backtracking.png", alt = "Greedy algorithms and backtracking", hiddenInSingle = true }
+++

In [Dynamic programming 2: classic problems](/posts/algo-dynamic-programming-2/) we checked every option through a table. Two other strategies exist: take one local choice and never look back, or try choices and undo them. The first is a {{< term "greedy-algorithm" "greedy algorithm" >}}, the second is {{< term "backtracking" "backtracking" >}}. Costs are counted as in [Big-O measured](/posts/algo-big-o-measured/).

> Go 1.26, local example, tests with `go test -race`. Machine load was not low, so I publish counts, not timings.

## Greedy: interval scheduling

Pick the most non-overlapping intervals. Sorting by earliest finish and taking whatever fits is correct. Sorting by earliest start or by shortest length looks plausible but fails. Output (best = brute force over all subsets):

```
A [{0 10} {1 2} {3 4} {5 6}] best=3
  earliest end   -> 3
  earliest start -> 1 [{0 10}]
B [{0 5} {4 6} {5 10}] best=2
  earliest end   -> 2
  shortest       -> 1 [{4 6}]
```

Why does earliest finish win? The exchange argument: take any optimal answer; its first interval ends no earlier than ours, so swapping ours in cannot create an overlap and loses nothing. Repeat for each step. A test compares it with brute force on 500 random inputs (seed 42) and all agree.

## When greedy breaks: coins

Greedy takes the biggest coin. For {1,5,10,25} it matched the {{< term "dynamic-programming" "dynamic programming" >}} answer ([part 1](/posts/algo-dynamic-programming-1/)) for amounts 1 to 100 and (in the test) up to 200. For {1,3,4}:

```
coins [1 3 4]: greedy!=dp for 24 of 100 amounts, first 6
coins {1,3,4} amount 6: greedy 3 dp 2
```

Greedy gives 4+1+1, DP gives 3+3. The same happens with the {{< term "knapsack" "knapsack" >}}: when items can be split, taking the best value per weight is optimal; when not, it is not (capacity 50, items weight/value 10/60, 20/100, 30/120):

```
fractional 240, greedy 0/1 160, optimal 0/1 220
```

The 0/1 optimum comes from the DP table of the previous post.

## Huffman coding

{{< term "huffman-coding" "Huffman coding" >}} repeatedly merges the two rarest symbols, using Go's `container/heap` as the {{< term "priority-queue" "priority queue" >}} (see [Heaps](/posts/algo-heaps-priority-queues/)). Ties are broken by insertion order so the output is stable. For "abracadabra":

```
a 0   c 100   d 101   b 110   r 111
huffman "abracadabra": 23 bits, fixed 3-bit: 33 bits
```

Frequent letters get short codes. The test checks that no code is a prefix of another. The same greedy flavour appears in Kruskal's {{< term "minimum-spanning-tree" "minimum spanning tree" >}}: take the cheapest edge that makes no cycle, checked with {{< term "union-find" "union-find" >}} ([Tries and union-find](/posts/algo-tries-union-find/)).

## Backtracking: choose, explore, unchoose

```go
cur = append(cur, v)      // choose
rec(...)                  // explore
cur = cur[:len(cur)-1]    // unchoose
```

This is {{< term "dfs" "depth-first search" >}} over a tree of choices ([Graphs](/posts/algo-graphs-bfs-dfs/)). Subsets of 10 items: 1024 (2^10). Permutations of 6: 720 (6!). Combination sum, where numbers may repeat:

```
[2 3 6 7] -> 7: [[2 2 3] [7]]
[2 3 5] -> 8: [[2 2 2 2] [2 3 3] [3 5]]
```

## N-Queens and pruning

Pruning means rejecting a partial board as soon as a queen attacks another. For comparison I also ran a version that only avoids repeating columns and checks diagonals at the end. "Nodes" is the number of queen placements tried:

```
n  solutions  pruned   no pruning
4  2          16       64
6  4          152      1956
8  92         2056     109600
10 724        35538    9864100
```

n=8 gives 92, and the tests check the known counts for n=4..10. At n=10 pruning explores about 277 times fewer placements. The no-pruning column is not the worst case; it is already smarter than trying every cell.

## Sudoku

I took a classic puzzle with a single solution (a count up to 2 solutions returned 1). The solver fills the first empty cell with any digit that fits and backtracks. Then I changed one rule: pick the empty cell with the fewest candidates.

```
nodes first-empty: 4208   fewest-candidates: 51
```

Both give the same grid. 51 is exactly the number of empty cells here, so this puzzle needed no backtracking after the reordering. That will not hold for hard puzzles; I did not run any.

## Exponential, sometimes unavoidable

Pruning and ordering shrink the tree but not its worst case: N-Queens, Sudoku and subset problems stay exponential in general. If the sub-problems overlap, use DP; if not, backtracking is the honest tool.

## A few things to watch

- Greedy needs a proof or a brute-force test; a plausible rule is not enough.
- Always compare against brute force on small random inputs.
- Unchoose must undo exactly what choose did, including shared slices (copy before saving).
- Order the choices so that failure comes early.

## Exercise

Rewrite N-Queens with bitmasks instead of three boolean arrays and check that the node counts match the table. Then find another coin set, besides {1,3,4}, where greedy fails, and a test that proves it.

## What's next

Everything so far searched structures of numbers and choices. Next up: "String algorithms: KMP and Rabin–Karp".
