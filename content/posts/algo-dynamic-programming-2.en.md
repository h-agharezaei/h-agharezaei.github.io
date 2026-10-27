+++
date = '2027-04-12T10:00:00+03:30'
draft = false
title = 'Dynamic programming 2: classic problems'
description = 'Dynamic programming in Go: LCS, edit distance, 0/1 knapsack and LIS with real tables, reconstructed answers and a Persian rune-vs-byte check.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "dynamic-programming", "lcs", "edit-distance", "knapsack", "go"]
cover = { image = "/images/covers/algo-dynamic-programming-2.png", alt = "Dynamic programming 2: classic problems", hiddenInSingle = true }
+++

In [Dynamic programming 1: the idea and memoization](/posts/algo-dynamic-programming-1/) we cached subproblems top-down. Here we fill tables bottom-up for four classics and, more importantly, walk the table backwards to recover the actual answer, not just its size. Counting follows [Big-O measured](/posts/algo-big-o-measured/); [binary search](/posts/algo-binary-search-invariants/) shows up in the last problem.

> Go 1.26, local example, tests with `go test -race`. Machine load was high, so I publish counts, not timings.

## LCS

For two sequences, the longest common subsequence {{< term "longest-common-subsequence" "(LCS)" >}} keeps order but may skip items. Let `t[i][j]` be the LCS length of the first i and j items: if the items match it is `t[i-1][j-1]+1`, otherwise the larger of `t[i-1][j]` and `t[i][j-1]`. This is a {{< term "dynamic-programming" "dynamic programming" >}} table:

```
      B D C A B A
    0 0 0 0 0 0 0
 A  0 0 0 0 1 1 1
 B  0 1 1 1 1 2 2
 C  0 1 1 2 2 2 2
 B  0 1 1 2 2 3 3
 D  0 1 2 2 2 3 3
 A  0 1 2 2 3 3 4
 B  0 1 2 2 3 4 4
LCS: BCBA len 4
```

The corner holds 4. To get the string, start at the corner and go back: on a match output the item and move diagonally, otherwise move towards the larger neighbour. Ties are possible; mine returns one answer.

## Edit distance

The {{< term "edit-distance" "edit distance" >}} counts insertions, deletions and substitutions. The first row and column are `0..n`, and each cell is the minimum of three moves:

```
       s i t t i n g
    0 1 2 3 4 5 6 7
 k  1 1 2 3 4 5 6 7
 i  2 2 1 2 3 4 5 6
 t  3 3 2 1 2 3 4 5
 t  4 4 3 2 1 2 3 4
 e  5 5 4 3 2 2 3 4
 n  6 6 5 4 3 3 2 3
distance: 3
sub k->s, keep i, keep t, keep t, sub e->i, keep n, ins g
```

Walking back from the corner gives the edit script. Cost: time and memory O(n*m).

## 0/1 knapsack

Each item is taken once. With weights `[1 3 4 5]`, values `[1 4 5 7]` and capacity 7, the {{< term "knapsack" "knapsack" >}} table gives:

```
knapsack 2-D: 9 items [1 2]
```

Items 1 and 2 (weights 3 and 4, values 4 and 5). The 2-D table only needs the previous row, so it collapses to one array. The loop direction matters: going downwards the cell `d[c-w]` is still the old row (each item once). Going upwards it is already updated, so the item can be reused. On this input both give 9 by luck, so here is a case where they differ, one item of weight 3 and value 10, capacity 9:

```
one item w=3 v=10 cap=9: correct 10 flipped 30
```

The flipped loop solves the unbounded version, where an item may repeat: same code shape, different problem.

## Longest increasing subsequence

The O(n^2) DP checks every earlier element. The O(n log n) version keeps the smallest tail of each length and uses binary search to place each element. I counted inner comparisons and probes on random arrays (seed 7):

```
LIS n=100   quad=16  ops=4950     fast=16  ops=331
LIS n=1000  quad=57  ops=499500   fast=57  ops=5121
LIS n=10000 quad=185 ops=49995000 fast=185 ops=68997
```

Same lengths, but 49,995,000 against 68,997 operations at n = 10,000. The fast version gives the length only.

## Persian text: runes, not bytes

A Go string is bytes, and a Persian letter takes two in UTF-8. Comparing "سلام" and "کلام" (one letter differs):

```
sub 0xd8->0xda, sub 0xb3->0xa9, keep 0xd9, keep 0x84, keep 0xd8, keep 0xa7, keep 0xd9, keep 0x85
bytes : 8 8 distance 2
runes : 4 4 distance 1 [sub س->ک keep ل keep ا keep م]
```

By bytes the distance is 2; by {{< term "rune" "runes" >}} it is 1. Note that with some letter pairs (س and ع share their first byte) bytes would accidentally give the right answer, which makes this bug easy to miss. The generic functions take `[]T`, so `[]rune(s)` fixes it. I did not handle combining marks or normalisation.

## Tests

A `go test -race` test uses fixed seed 42 and 300 random cases per problem (length up to 10 items, small alphabet). Brute force checks LCS over all subsets, edit distance with plain recursion, knapsack over all subsets and LIS over all subsets. It also checks that the script's cost equals the distance, that the chosen knapsack items fit and sum to the best value, and that both LIS versions agree. All pass.

## How to recognise a DP problem

1. You can state the answer for a prefix, a suffix or a capacity (the state).
2. A bigger state follows from smaller ones (the recurrence).
3. The same states recur (overlapping subproblems).
4. The optimum contains optimal sub-answers.

| Problem | Time | Memory |
|---|---|---|
| LCS, edit distance | O(n*m) | O(n*m), or O(min(n,m)) for the length only |
| 0/1 knapsack | O(n*C) | O(n*C), or O(C) without items |
| LIS | O(n^2) or O(n log n) | O(n) |

Knapsack is pseudo-polynomial: C is a number, not an input size. Filling a table in dependency order is a [topological order](/posts/algo-topological-sort/) of the subproblem DAG.

## A few things to watch

- Reconstruction needs the table; the memory-saving versions lose it.
- Loop direction in 1-D tables decides the problem you solve.
- Never index Unicode strings by byte.
- Test against brute force on tiny inputs.

## Exercise

Reconstruct the LIS itself in O(n log n) by storing predecessor indices. Then do LCS with two rows only and check it gives the same length.

## What's next

DP checks every option. Sometimes one local choice is enough, and sometimes you must undo choices. The next post is "Greedy algorithms and backtracking".
