+++
date = '2027-04-06T10:00:00+03:30'
draft = false
title = 'Dynamic programming 1: the idea and memoization'
seoTitle = 'Dynamic programming and memoization in Go'
description = 'Dynamic programming in Go: memoization vs a table on Fibonacci, grid paths and coin change, with exact call counts and a brute-force test.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "dynamic-programming", "memoization", "recursion", "go"]
cover = { image = "/images/covers/algo-dynamic-programming-1.png", alt = "Dynamic programming 1: the idea and memoization", hiddenInSingle = true }
+++

In the previous post, [Topological sort and dependencies](/posts/algo-topological-sort/), an order on a graph let us avoid redundant work. Some problems repeat work in a different way: the recursion asks the same question again and again. {{< term "dynamic-programming" "Dynamic programming" >}} (DP) fixes that. It builds on recursion, the [hash tables](/posts/algo-hash-tables/) and [dynamic arrays](/posts/algo-dynamic-arrays/) from earlier posts, and on the [Big-O](/posts/algo-big-o-measured/) habit of counting.

> Go 1.26, local example, tests with `go test -race`. The load average was high, so I publish counts and allocations, no timings.

## Fibonacci: the same question many times

```go
func FibNaive(n int, calls *int) int {
	*calls++
	if n < 2 { return n }
	return FibNaive(n-1, calls) + FibNaive(n-2, calls)
}
```

`fib(32)` and `fib(31)` both need `fib(30)`. These are {{< term "overlapping-subproblems" "overlapping subproblems" >}}. The cost, as an exact count:

```
naive  fib(35) = 9227465 calls = 29860703
```

Almost 30 million calls for 36 distinct questions. Now {{< term "memoization" "memoize" >}}: before computing, look in a map; after computing, store.

```
map    fib(35) = 9227465 calls = 69 subproblems = 34
slice  fib(35) = 9227465 calls = 69
```

69 calls = 2n - 1: each stored value is computed once, then looked up. The map holds 34 entries (n = 2..35, the base cases are not stored). The slice version is the same idea with the index as key, so the {{< term "hash-table" "hash lookups" >}} disappear.

## Bottom-up and O(1) space

Memoization is top-down: start from the question, recurse down. Bottom-up fills a table from the base cases up:

```go
t[1] = 1
for i := 2; i <= n; i++ { t[i] = t[i-1] + t[i-2] }
```

Since `t[i]` only needs the last two values, two variables are enough. All variants return 9227465. `testing.AllocsPerRun` for fib(35), including building the memo:

```
allocs map  : 7
allocs slice: 1
allocs table: 1
allocs o1   : 0
```

The map allocation count depends on how it grows, so treat 7 as "measured here". Recursion depth is only 35 here. Go stacks grow on demand (up to a large limit, 1 GB by default on 64-bit according to the docs), so depth in the thousands is fine; Python's default recursion limit is 1000, which is a real concern for top-down DP there.

## The two properties

DP applies when a problem has overlapping subproblems and {{< term "optimal-substructure" "optimal substructure" >}}. Climbing stairs (1 or 2 steps) has ways(i) = ways(i-1) + ways(i-2):

```
stairs 0..8 : [1 1 2 3 5 8 13 21 34]
```

A cheapest path through a grid (moving right or down) extends the cheaper of two neighbours. Here is a 3x4 grid and its table of best costs:

```
grid:   1 3 1 2 / 1 5 1 9 / 4 2 1 1
table:  [1 4 5 7]
        [2 7 6 15]
        [6 8 7 8]
brute: 8
```

The bottom-right cell is the answer, and plain recursion without a cache agrees.

## The recipe

1. **State**: what do the arguments mean? (`dp[a]` = fewest coins for amount `a`.)
2. **Transition**: how does a state depend on smaller ones?
3. **Base case**: what is known without recursion?
4. **Order**: which states first, so dependencies are ready?
5. **Answer**: which state is the result?

## Worked example: coin change

Fewest coins for amount 11 with coins 1, 5, 6, 9. State `dp[a]`; transition `dp[a] = min over c of dp[a-c] + 1`; base `dp[0] = 0`; order `a = 1..11`; answer `dp[11]`. I also store the last coin used per amount to rebuild the choice:

```
table: [0 1 2 3 4 1 1 2 3 1 2 2]
used : [5 6] true
```

Two coins: 5 + 6. Greedy (largest first) would take 9 + 1 + 1, which is three. For coins 4 and 6 and amount 7 the function reports that it is impossible.

## The test

The test generates 300 random cases (seeds 0 to 299, 1-4 coins of value 1-9, amounts below 25) and compares the table with a brute-force recursion. It also checks that the reconstructed coins sum to the amount, and does the same with 300 random grids against brute force. A third test checks that all four Fibonacci versions agree for n up to 40. All pass with `-race`. This is the {{< term "property-based-testing" "property-style" >}} habit from before.

## Memoization's pitfall

A memo is correct only if the key holds everything the answer depends on. I wrote a deliberately bad version keyed by the amount only, while the answer also depends on the coin set:

```
bad memo, coins {1,5,6,9}, 11 -> 2
bad memo, coins {1,2},     11 -> 2 (correct: 6)
```

The second call returned the stale entry from the first. The same applies to functions with side effects or hidden inputs (time, globals): a cached result skips the side effect. Slices and maps cannot be Go map keys, so complex state must be encoded into a comparable key.

## A few things to watch

- Count subproblems: states x work per state is the complexity, not the call count of naive code.
- Pick top-down when few states are reachable, bottom-up when you need all of them or want less overhead.
- Put every input the answer depends on into the key.

## Exercise

Change `Coins` to count the number of distinct ways to make an amount (order does not matter). Which loop must be outer? Check it against brute force.

## What's next

Next is "Dynamic programming 2: classic problems", where the recipe meets sequences, subsets and edit distance.
