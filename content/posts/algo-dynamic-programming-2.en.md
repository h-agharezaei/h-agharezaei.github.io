+++
date = '2027-04-12T10:00:00+03:30'
draft = false
title = 'Dynamic programming 2: classic problems'
description = 'Dynamic programming in Go: LCS, edit distance, 0/1 knapsack and LIS with real tables, reconstructed answers and a Persian rune-vs-byte check.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "dynamic-programming", "lcs", "edit-distance", "knapsack", "go"]
cover = { image = "/images/covers/algo-dynamic-programming-2.png", alt = "Dynamic programming 2: classic problems", hiddenInSingle = true }
+++

When you mistype the word `kitten` in a program and it asks "did you mean `sitting`?", there is a question behind it: how many small edits does it take to turn one word into another? For these two words the answer is 3: change `k` to `s`, change `e` to `i`, and add a `g` at the end. In this post we solve that question with dynamic programming, along with three other classic problems.

In the [previous post](/posts/algo-dynamic-programming-1/) we learned a five-step recipe: state, transition, base case, order of filling and answer. There the table only gave one number (for example the fewest coins). Here we go one step further: we fill the table from the bottom up and then **read it backwards** from its corner to build the answer itself, not only its size. That means not just "the distance is 3" but "these three edits". The counting is done like in [Big-O with real measurements](/posts/algo-big-o-measured/), and [binary search](/posts/algo-binary-search-invariants/) helps in the last problem.

> I re-ran every output with Go 1.27. It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish no timings; you see counts.

## Longest common subsequence (LCS)

First a definition. A **subsequence** of a sequence is some of its elements in the same order, where skipping is allowed. `ACE` is a subsequence of `ABCDE`, but `AEC` is not (the order is broken). The {{< term "longest-common-subsequence" "longest common subsequence" >}} (LCS) is the longest sequence that appears in both inputs this way. A familiar use is comparing two versions of a file: the lines that appear in both, in the same order, are a common subsequence (tools like `diff` use an idea close to this; I did not check the details of their implementation).

Take the two sequences `ABCBDAB` and `BDCABA`. Let `t[i][j]` be the LCS length for the first i characters of the first sequence and the first j characters of the second (our state). Row and column zero are zero, because nothing is shared with an empty sequence. For every other cell there are two cases:

- If the last characters are equal, we add it to the LCS: `t[i][j] = t[i-1][j-1] + 1`.
- If not, we drop the last character of one of the two sequences and take the better of the two: `t[i][j] = max(t[i-1][j], t[i][j-1])`.

For example, `t[1][1]` compares `A` with `B`; they differ, so `max(t[0][1], t[1][0]) = 0`. `t[1][4]` compares `A` with the fourth column, which is `A`. They are equal, so `t[0][3] + 1 = 1`. The demo's output, the full table:

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

The rows are the characters of the first sequence (`ABCBDAB`) and the columns those of the second (`BDCABA`). The bottom-right cell, 4, is the LCS length.

To build the string itself we start at that corner and walk backwards. If the two current characters are equal, we put it in the output and move diagonally up-left. If not, we move toward the larger neighbor (up or left), because the value came from there. This path collects the characters `A`, `B`, `C`, `B` from last to first, and after reversing we get `BCBA`. There may be several LCSs of the same length; my code returns one of them.

## Edit distance

Now the question we opened with. The {{< term "edit-distance" "edit distance" >}} is the fewest edits needed to turn one string into another, with three kinds of edit: insert a character, delete a character, and replace a character with another. Another name for it is the Levenshtein distance.

State: `t[i][j]` = the fewest edits to turn the first i characters of the first string into the first j characters of the second. Base cases: turning i characters into the empty string takes i deletions, and building j characters from empty takes j insertions; so the first row and column are `0..n`. Every other cell is the minimum of three ways:

- delete (from above): `t[i-1][j] + 1`
- insert (from the left): `t[i][j-1] + 1`
- replace or keep (from the diagonal): `t[i-1][j-1]` plus 0 if the two characters are equal and 1 if not.

For example the cell (`k`, `s`): the characters differ, so the minimum of `t[0][1]+1 = 2`, `t[1][0]+1 = 2` and `t[0][0]+1 = 1` is 1 (a replacement). The cell (`i`, `i`): the characters are equal and `t[1][1] + 0 = 1`. The demo's output for `kitten` and `sitting`:

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

The corner of the table is 3. The last line is the walk back from the corner: in each cell we ask which way its value came from and record that edit. It reads: replace `k` with `s`, keep `i`, `t` and `t`, replace `e` with `i`, keep `n`, and insert `g`. Three edits, the ones I mentioned at the start. The time and memory of this algorithm are O(n·m).

## The 0/1 knapsack

The third problem: we have a backpack with capacity 7 kg and four items with (weight, value): (1, 1), (3, 4), (4, 5) and (5, 7). Each item is either taken once or not taken (hence "0/1"). What is the greatest value? This problem is called the {{< term "knapsack" "knapsack" >}} problem.

The greedy temptation is to take first the item with the best value-to-weight ratio: item (5, 7) with ratio 1.4. Then only the item (1, 1) still fits: weight 6, value 8. But (3, 4) and (4, 5) together have weight 7 and value 9. DP solves it correctly.

State: `t[i][c]` = the greatest value using the first i items with capacity `c`. For item i there are two choices: leave it (`t[i-1][c]`, the answer without this item) or take it, if it fits (`t[i-1][c-weight] + value`). We keep the larger. To rebuild the choice, we walk back from the corner: if `t[i][c]` differs from `t[i-1][c]`, item i was taken, and we reduce the capacity by its weight. The demo's output:

```
knapsack 2-D: 9 items [1 2]
```

The greatest value is 9, using items number 1 and 2 (counting from zero), that is (3, 4) and (4, 5).

The two-dimensional table needs only the previous row for each row, so it can be turned into a single array. Here the loop direction decides which problem you solve. If you go through the capacities from high to low (descending), then when you read `d[c-w]` it still holds the previous row's value, so you count the current item once. If you go from low to high (ascending), `d[c-w]` has just been updated with this very item, and the same item is taken again. On the input above both happen to give 9. To see the difference I tried one item with weight 3, value 10 and capacity 9:

```
one item w=3 v=10 cap=9: correct 10 flipped 30
```

The correct answer is 10 (the item once). The version with the flipped loop gives 30: it took the same item three times. That actually solves another problem, the unbounded knapsack, where items can repeat. The code is nearly the same; only the loop direction differs.

## Longest increasing subsequence (LIS)

The fourth problem: in an array of numbers, find the longest subsequence that is strictly increasing. For example in `[10 9 2 5 3 7 101 18]` the answer is 4 (for instance `2 3 7 18`).

The simple DP: `d[i]` = the length of the longest increasing subsequence that ends at element i. To compute it we look at all earlier elements: if `a[j] < a[i]`, we can get `d[j] + 1`. That is O(n) work per element, so O(n²) in total.

The faster way has a clever idea: instead of keeping a length for every element, we keep a list of "the smallest possible tail for each length". `tails[k]` is the smallest number that an increasing subsequence of length k+1 can end with. When a new number x arrives, we use binary search to find the first `tails[k]` that is not smaller than x, and replace it with x (a smaller tail is better because more can follow it). If there is no such entry, x makes the list one longer. On the example above (by hand):

| number | `tails` afterwards |
|---|---|
| 10 | [10] |
| 9 | [9] |
| 2 | [2] |
| 5 | [2, 5] |
| 3 | [2, 3] |
| 7 | [2, 3, 7] |
| 101 | [2, 3, 7, 101] |
| 18 | [2, 3, 7, 18] |

The final list has length 4, the answer. (The `tails` list itself is not necessarily a real subsequence; only its length is right.) Each number costs one binary search, so O(n log n). I counted the comparisons on random arrays (seed 7):

```
LIS n=100   quad=16  ops=4950     fast=16  ops=331
LIS n=1000  quad=57  ops=499500   fast=57  ops=5121
LIS n=10000 quad=185 ops=49995000 fast=185 ops=68997
```

For each size the two methods give the same length (16, 57 and 185). But for n = 10,000 the simple version made 49,995,000 comparisons (n(n−1)/2) and the fast one made 68,997 probes in its binary searches. Note that my fast version returns only the length, not the subsequence itself.

## Persian text: runes, not bytes

A practical note about LCS and edit distance on Persian text. My functions are generic and take `[]T`. If you convert a string straight to `[]byte`, every byte counts as a "character", but in UTF-8 every Persian letter is two bytes. "سلام" and "کلام" differ in just one letter:

```
sub 0xd8->0xda, sub 0xb3->0xa9, keep 0xd9, keep 0x84, keep 0xd8, keep 0xa7, keep 0xd9, keep 0x85
bytes : 8 8 distance 2
runes : 4 4 distance 1 [sub س->ک keep ل keep ا keep م]
```

With bytes: each string is 8 bytes and the distance comes out as 2, because both bytes of the first letter differ. With {{< term "rune" "runes" >}}, that is `[]rune(s)` where each letter is one element: 4 characters and the correct distance of 1 (`س` to `ک`). More dangerous is that for some pairs bytes happen to give the right answer: `س` and `ع` have the same first byte (`0xd8`) and differ only in the second, so the byte distance is also 1. That means the bug shows up only for some inputs and is hard to find. The simple fix: pass `[]rune(s)` to the function. I did not check combining characters and normalization.

## The tests

The tests run with a fixed seed of 42 and 300 random inputs for each problem: strings of up to 10 characters from the three-letter alphabet `a` to `c`; knapsack with up to 10 items, weights 1 to 8, values 1 to 20 and capacity below 25; and for LIS, arrays of up to 12 elements with values 0 to 9. Each algorithm's answer is compared with a brute force: trying every subset for LCS, knapsack and LIS, and a simple recursion for edit distance. The tests also check that the cost of the edit script (the number of non-`keep` edits) equals the distance, that the knapsack items fit and their values sum to the best value, and that the two LIS versions agree. All passed.

## How do you recognize a DP problem?

With these four questions:

1. Can you state the answer for a prefix, a suffix or a capacity? (state)
2. Is a bigger state built from smaller states? (recurrence)
3. Do the states repeat? (overlapping subproblems)
4. Is the best answer built from the best answers of smaller problems? (optimal substructure)

The costs:

| problem | time | memory |
|---|---|---|
| LCS and edit distance | O(n·m) | O(n·m), or O(min(n,m)) if you only want the length |
| 0/1 knapsack | O(n·C) | O(n·C), or O(C) without rebuilding the items |
| LIS | O(n²) or O(n log n) | O(n) |

The knapsack is "pseudo-polynomial": C is the capacity, which is itself a number and not the size of the input; if the capacity is huge, the table is huge too. And the order of filling the table, "dependencies first", is the [topological order](/posts/algo-topological-sort/) of the graph of subproblems: each cell is a vertex and each dependency an edge.

## DP table traps

- **Rebuilding the answer needs the full table.** The low-memory versions (two rows or one array) give only the number and lose the path.
- **The loop direction in a one-dimensional table decides which problem you solve**, as we saw in the knapsack: 10 versus 30.
- **Do not index a Unicode string by bytes.** Use `[]rune`.
- **Test against brute force on small inputs.** An off-by-one cell in the table usually shows up only for some inputs.

## Exercise

Rebuild the LIS itself in O(n log n): for each element also keep the index of the previous element in the subsequence, and at the end walk back from the last tail. Then write LCS with only two rows and check that the length comes out the same.

## What's next

"Greedy algorithms and backtracking". DP weighs all the options; but sometimes one local choice is enough (and as we saw in the knapsack, sometimes it is not), and sometimes we have to take choices back.
