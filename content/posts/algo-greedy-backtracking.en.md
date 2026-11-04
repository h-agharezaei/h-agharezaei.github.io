+++
date = '2027-04-21T10:00:00+03:30'
draft = false
title = 'Greedy algorithms and backtracking'
description = 'Greedy algorithms and backtracking in Go: interval scheduling, coin change, Huffman, N-Queens and Sudoku with real node counts and tests.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "greedy", "backtracking", "huffman", "n-queens", "go"]
cover = { image = "/images/covers/algo-greedy-backtracking.png", alt = "Greedy algorithms and backtracking", hiddenInSingle = true }
+++

You owe someone 6 units of money and you have coins worth 1, 3 and 4. The obvious move is to hand over the biggest coin that fits, then the next, and so on. That gives 4+1+1, three coins. But 3+3 does it with two. A choice that looks best right now can be the wrong choice for the whole problem.

That is the question behind this post: when can you simply take the best-looking option and never think about it again, and when do you have to try things and take them back? The [previous post](/posts/algo-dynamic-programming-2/) avoided the question by filling a table that checked every option. Here we look at two other strategies. In a {{< term "greedy-algorithm" "greedy algorithm" >}} you make one local choice at each step and never look back. In {{< term "backtracking" "backtracking" >}} you make a choice, follow it as far as it goes, and if it leads nowhere you undo it and try the next one. Costs are counted as in [Big-O with real measurements](/posts/algo-big-o-measured/).

> I re-ran every output with Go 1.27 on macOS (arm64). It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish counts, not timings.

## Greedy: choosing meetings

Here is a problem where greedy works. You have one meeting room and a list of requests, each with a start and an end time. Two meetings cannot overlap (one may start exactly when another ends). You want to fit in as many meetings as possible.

There are several greedy rules you could try. Sort by earliest start, by shortest length, or by earliest finish, and then walk through the list taking every meeting that does not clash with the last one you took. Two of these rules look just as sensible as the third. Let's see what each does on two small inputs. Each interval is written `{start end}`. The demo prints the best possible count, found by brute force over all subsets, and then what each rule picks:

```
A [{0 10} {1 2} {3 4} {5 6}] best=3
  earliest end   -> 3 [{1 2} {3 4} {5 6}]
  earliest start -> 1 [{0 10}]
  shortest       -> 3 [{1 2} {3 4} {5 6}]
B [{0 5} {4 6} {5 10}] best=2
  earliest end   -> 2 [{0 5} {5 10}]
  earliest start -> 2 [{0 5} {5 10}]
  shortest       -> 1 [{4 6}]
```

(The demo also prints a third, larger input, `C`, which I left out here. On it "earliest end" again finds the best count, 4, while "earliest start" finds only 3.)

Read it like this. In input A there is one long meeting `{0 10}` that starts first. "Earliest start" takes it, and now nothing else fits, so it ends with 1 meeting instead of 3. In input B the shortest meeting is `{4 6}`, but it overlaps both of the others, so "shortest" ends with 1 instead of 2. Only "earliest end" got the best count in all three inputs, A, B and C.

Why does earliest finish work? Think about the first meeting in any best schedule. The meeting that ends earliest overall ends no later than that one. So we can swap it in at the front: it finishes at least as early, so it cannot clash with the second meeting, and the schedule is just as big. After that swap we are left with the same problem on the remaining time, and we repeat the argument. This way of proving a greedy rule correct is called an **exchange argument**: you show that any best answer can be changed, step by step, into the greedy one without getting worse.

I did not rely on the argument alone. A test compares the greedy answer with brute force on 500 random inputs (seed 42, up to 10 intervals each), and all of them agree.

## When greedy breaks: coins

Now back to the opening. Greedy for coins takes the biggest coin that fits, again and again. For the coins {1, 5, 10, 25}, the greedy answer matches the one from {{< term "dynamic-programming" "dynamic programming" >}} (see [part 1](/posts/algo-dynamic-programming-1/)) for every amount from 1 to 100 in the demo, and up to 200 in the tests. For 41 it takes 25+10+5+1, four coins, and no better answer exists.

But for the coins {1, 3, 4} greedy fails. The demo compares greedy and DP on amounts 1 to 100 and then shows the one from the opening:

```
coins [1 3 4]: greedy!=dp for 24 of 100 amounts, first 6
coins {1,3,4} amount 6: greedy 3 dp 2
```

For 24 of the 100 amounts greedy uses more coins than necessary, and the first such amount is 6: greedy gives 4+1+1 (3 coins), DP gives 3+3 (2 coins). Whether greedy works depends on the coin set, not on the idea of "take the biggest". That is the most important thing to remember about greedy: it is only correct when the problem has the right structure, and you have to show that, not assume it.

The {{< term "knapsack" "knapsack" >}} problem shows the same thing from another side. You have a bag with capacity 50 and three items with (weight, value): (10, 60), (20, 100), (30, 120). The greedy rule is to take items in order of value per weight (6, 5 and 4 here). If you may cut items into pieces, as with sand or flour, this rule is optimal. If each item is all-or-nothing, it is not:

```
knapsack cap 50: fractional 240, greedy 0/1 160, optimal 0/1 220
```

With pieces allowed you take items 1 and 2 whole and two thirds of item 3: 60 + 100 + 80 = 240. All-or-nothing, greedy takes items 1 and 2 (weight 30) and then item 3 no longer fits, so it stops at 160. The real best is items 2 and 3 together: 100 + 120 = 220. The 0/1 optimum comes from the same one-array table as in the previous post.

## Greedy at work: Huffman coding

Greedy is not only a trap. Some of the most useful algorithms are greedy. One is {{< term "huffman-coding" "Huffman coding" >}}, used in compression. The idea: instead of spending the same number of bits on every letter, give frequent letters short codes and rare letters long ones.

The algorithm builds a tree. Keep a pool of symbols, each with its count. Take the two rarest, merge them into one node whose count is their sum, and put that back in the pool. Repeat until one node is left. The code of a letter is the path from the root to it (0 for left, 1 for right). To always find "the two rarest" quickly we use a {{< term "priority-queue" "priority queue" >}}, Go's `container/heap` (see [Heaps and priority queues](/posts/algo-heaps-priority-queues/)). Ties are broken by insertion order, so the output is the same on every run.

For the word "abracadabra" (a appears 5 times, b and r twice each, c and d once) the demo prints the code of each letter, shortest first, and then the total size:

```
a 0   c 100   d 101   b 110   r 111
huffman "abracadabra": 23 bits, fixed 3-bit: 33 bits
```

(In the real output the codes are printed one per line; I put them on one line to save space.) The frequent `a` gets a single bit; the rare ones get three. The whole word takes 5×1 + 2×3 + 2×3 + 1×3 + 1×3 = 23 bits, against 33 bits if each of the 11 letters used a fixed 3 bits (five different letters need at least 3 bits when all codes have the same length). A test also checks that no code is the start of another code. That matters: without it, a stream of bits could be read in two ways.

The same greedy flavour appears in Kruskal's algorithm for the {{< term "minimum-spanning-tree" "minimum spanning tree" >}}: take the cheapest edge that does not close a cycle. The cycle check is done with {{< term "union-find" "union-find" >}} (see [Tries and union-find](/posts/algo-tries-union-find/)).

## Backtracking: choose, explore, unchoose

Greedy never goes back. Backtracking is the opposite: it is built around going back. Picture a maze. At each fork you pick a path and walk. At a dead end you walk back to the last fork and try the next path. In code, "walk back" is the third line of this pattern:

```go
cur = append(cur, v)      // choose
rec(...)                  // explore
cur = cur[:len(cur)-1]    // unchoose
```

Choose adds one decision to the current partial answer. Explore calls the same function to continue from there. Unchoose removes the decision so the next option starts from a clean state. This is {{< term "dfs" "depth-first search" >}} over a tree where every node is a partial answer and every branch is a choice (see [Graphs: BFS and DFS](/posts/algo-graphs-bfs-dfs/)).

The simplest uses visit the whole tree. All subsets of 10 items: for each item you either include it or not, so 2^10 = 1024 subsets. All orderings of 6 items: 6! = 720. A little more interesting is combination sum: given numbers that may be reused, find every way to add up to a target. The demo prints:

```
combination sum [2 3 6 7] -> 7: [[2 2 3] [7]]
combination sum [2 3 5] -> 8: [[2 2 2 2] [2 3 3] [3 5]]
```

For the first line, the search tries 2, then 2, then 2 again. That adds up to 6 and leaves 1, which no number can fill, so it goes back one step. 2+2+3 hits 7 exactly, so it records that; later 7 on its own works too. Numbers are only tried in non-decreasing order, so `[2 2 3]` is found once and `[3 2 2]` is never produced.

## N-Queens and pruning

The famous example is N-Queens: place N queens on an N×N board so that no two attack each other (same row, column or diagonal). Let's do 4×4 by hand, placing one queen per row, top to bottom, trying columns 0 to 3 in order.

- Row 0: put a queen at column 0.
- Row 1: column 0 is the same column, column 1 is a diagonal neighbour. Column 2 is safe. Put it there.
- Row 2: column 0 and 2 are taken by columns, and columns 1 and 3 are diagonal neighbours of the queen in row 1. No place at all. Dead end, so we undo row 1's queen and try its next column.
- Row 1, column 3 is safe. Row 2: only column 1 is safe. Row 3: columns 0, 1 and 3 are already used, and column 2 is a diagonal neighbour of the row-2 queen. Dead end again. We go back through row 2 and row 1, which have nothing left, and finally row 0 moves its queen to column 1.
- With the first queen at column 1 the search finds a full board: columns 1, 3, 0, 2.

Notice what happened at the dead ends. We did not fill the whole board and then check it; we gave up on a partial board the moment it could not be completed. That is called **pruning**: cutting off a whole branch of the tree early. To see how much it matters, I also ran a version without it. It only avoids repeating a column and checks the diagonals at the very end, once all N queens are down. "Nodes" is the number of queen placements tried:

```
n  solutions  pruned   no pruning
4  2          16       64
6  4          152      1956
8  92         2056     109600
10 724        35538    9864100
```

(The real output has more rows, n = 4 to 10, and slightly different column titles; I kept four rows.) Both versions find the same number of solutions, so the pruning loses nothing. The tests check the known counts for n = 4 to 10, among them 92 for n = 8. At n = 10 the pruned version places about 278 times fewer queens (9,864,100 / 35,538). The no-pruning column is not the worst case either; it already avoids repeating columns, which is smarter than trying every cell.

## Sudoku: the order of choices matters

A Sudoku solver is the same pattern. Find an empty cell, try each digit that does not break a rule, go deeper, and if you get stuck undo the digit. I took the well-known puzzle that has exactly one solution (counting solutions up to a limit of 2 returned 1) and solved it two ways. The first fills the first empty cell it finds, in reading order. The second, as a change of only one rule, picks the empty cell that has the fewest legal digits. "Nodes" counts every digit placed:

```
same answer: true  nodes first-empty: 4208  fewest-candidates: 51
```

Both give the same finished grid (the demo prints it too). But the first needed 4,208 placements, while the second needed 51. The puzzle has 51 empty cells, so the second never had to undo anything: every digit it placed stayed. The idea is that a cell with only one legal digit is a forced move, and taking forced moves first avoids guessing. This is the point of "order the choices so that failure comes early". For hard puzzles that will not be so clean; I did not run any.

## Exponential, and sometimes unavoidable

Pruning and a good order shrink the tree but not its worst case. N-Queens, Sudoku and subset problems stay exponential in general. A rule of thumb for choosing between the tools: if the subproblems repeat (the same partial situation can be reached in many ways), a DP table remembers them and is much cheaper. If they do not repeat, backtracking is the honest tool.

## Before you trust a greedy rule

- **A plausible rule is not a proof.** "Take the biggest coin" sounds right and fails for {1, 3, 4}. Either prove the rule (an exchange argument) or at least test it.
- **Compare against brute force on small random inputs.** The brute force is slow but obviously correct, and small inputs are where counterexamples show up first.
- **Unchoose must undo exactly what choose did.** If you save a result, copy the current slice before storing it (`append([]int{}, cur...)`). If you store the slice itself, later changes to it silently change what you saved.
- **Order the choices so that failure comes early**, as the Sudoku numbers showed.

## Exercise

Rewrite N-Queens with bitmasks (an integer whose bits mark used columns and diagonals) instead of three boolean arrays, and check that the node counts match the table. Then find another coin set, besides {1, 3, 4}, where greedy fails, and write a test that proves it.

## What's next

Everything so far searched structures of numbers and choices. "String algorithms: KMP and Rabin–Karp" turns to searching text.
