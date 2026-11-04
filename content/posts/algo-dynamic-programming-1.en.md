+++
date = '2027-04-06T10:00:00+03:30'
draft = false
title = 'Dynamic programming 1: the idea and memoization'
seoTitle = 'Dynamic programming and memoization in Go'
description = 'Dynamic programming in Go: memoization vs a table on Fibonacci, grid paths and coin change, with exact call counts and a brute-force test.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "dynamic-programming", "memoization", "recursion", "go"]
cover = { image = "/images/covers/algo-dynamic-programming-1.png", alt = "Dynamic programming 1: the idea and memoization", hiddenInSingle = true }
+++

Write the Fibonacci function in its simplest recursive form and call `fib(35)`. The function has only 36 different questions (`fib(0)` to `fib(35)`), yet to answer it, it is called 29,860,703 times. Nearly all of its work is repeating questions it has already answered. {{< term "dynamic-programming" "Dynamic programming" >}} (DP for short) is the way to remove this waste, and its main idea is very simple: write down the answer to each question the first time, and next time just read it.

So far in this series we worked with data structures and graphs. In the [previous post](/posts/algo-topological-sort/) an ordering on a graph stopped extra work. Here the extra work is inside the recursion itself and has nothing to do with graphs. DP builds on things we have already seen: recursion, the [hash table](/posts/algo-hash-tables/) (to write answers down), [dynamic arrays](/posts/algo-dynamic-arrays/) and the habit of counting from [Big-O](/posts/algo-big-o-measured/). First we learn the idea with Fibonacci, the simplest example, and then solve three real problems the same way: counting ways to climb stairs, the cheapest path through a grid, and the fewest coins.

> I re-ran every output with Go 1.27. It is a local example and its tests pass with `go test -race`. The machine was busy, so I publish no timings; you see call counts and allocation counts.

## Fibonacci: one question, many times

The Fibonacci sequence is: `fib(0) = 0`, `fib(1) = 1`, and every next number is the sum of the previous two. The code comes straight from the definition:

```go
func FibNaive(n int, calls *int) int {
	*calls++
	if n < 2 { return n }
	return FibNaive(n-1, calls) + FibNaive(n-2, calls)
}
```

(The `calls` parameter only counts how many times the function was called.) Let's see what happens for a small number, `fib(5)`. The call tree is:

```
fib(5)
├─ fib(4)
│  ├─ fib(3)
│  │  ├─ fib(2)
│  │  │  ├─ fib(1)
│  │  │  └─ fib(0)
│  │  └─ fib(1)
│  └─ fib(2)
│     ├─ fib(1)
│     └─ fib(0)
└─ fib(3)
   ├─ fib(2)
   │  ├─ fib(1)
   │  └─ fib(0)
   └─ fib(1)
```

Fifteen calls for one simple question. Look at the tree: `fib(3)` is computed twice, and `fib(2)` three times. Each time we find the same answer from scratch. These are {{< term "overlapping-subproblems" "overlapping subproblems" >}}: the big problem breaks into smaller problems, but those smaller problems are the same ones. The number of repeats grows enormously as n grows. The real count for `fib(35)`:

```
naive  fib(35) = 9227465 calls = 29860703
```

The answer is 9,227,465, and reaching it took about 30 million calls.

## First fix: write it down (memoization)

Imagine you are in an exam and you worked hard to find the answer to question 3. If question 5 needs it again, you do not solve it again; you read it from your notes. {{< term "memoization" "Memoization" >}} is exactly that: before computing, look in a map to see whether we already have the answer; if not, compute it and then store it:

```go
func FibMap(n int, calls *int, memo map[int]int) int {
	*calls++
	if n < 2 { return n }
	if v, ok := memo[n]; ok { return v }   // already computed
	v := FibMap(n-1, calls, memo) + FibMap(n-2, calls, memo)
	memo[n] = v
	return v
}
```

Look at `fib(5)` again. `fib(5)` goes to `fib(4)`, which goes to `fib(3)` and then `fib(2)`, which reaches `fib(1)` and `fib(0)` whose answers are known. When `fib(3)` returns and `fib(4)` goes for `fib(2)`, the answer is ready and comes back in one step. The same goes for `fib(3)` in the right branch of `fib(5)`. I counted by hand: 9 calls instead of 15. For `fib(35)`:

```
map    fib(35) = 9227465 calls = 69 subproblems = 34
slice  fib(35) = 9227465 calls = 69
```

From about 30 million calls down to 69. 69 is 2n − 1 (for n=5 that is 9, as we saw): every value is computed once and afterwards only read. The map has 34 entries: n from 2 to 35 (the base cases `fib(0)` and `fib(1)` are not stored). The slice version does the same with an index instead of a key, so the {{< term "hash-table" "hash lookup" >}} goes away.

## Second fix: fill the table from the bottom

In memoization we start from the big question and go down (this is called **top-down**). The other way is the opposite: start with the simplest questions and build larger answers from them (**bottom-up**). For Fibonacci we make a table and fill it in order:

```go
t[1] = 1
for i := 2; i <= n; i++ { t[i] = t[i-1] + t[i-2] }
```

There is no recursion and each cell is filled once. And since `t[i]` needs only the last two values, we do not have to keep the whole table: two variables are enough (the `O1` version). All five versions give 9,227,465 for `fib(35)`. I also counted allocations per version with `testing.AllocsPerRun`, including building the memo:

```
allocs map  : 7
allocs slice: 1
allocs table: 1
allocs o1   : 0
```

The map version makes seven allocations (probably because the map grows as entries are added; the number also depends on the Go version, and I did not investigate the cause), the slice and the table one, and the two-variable version none. None of them needs much memory, but the idea matters: once you know every cell needs only a few previous cells, you can throw the table away.

A note on recursion depth: here it is only 35. Go's stack grows on demand (according to the docs, by default up to about 1 GB on 64-bit), so a depth of a few thousand is no problem. In Python the default recursion limit is 1000, and there top-down DP for large n is a real problem, so you have to write it bottom-up.

## What problems can DP solve?

Fibonacci you could guess. For problems that are less obvious, DP works when two properties hold:

- **Overlapping subproblems**: what we saw in the tree.
- {{< term "optimal-substructure" "Optimal substructure" >}}: the best answer to the problem is built from the best answers to its subproblems.

The first example is **stairs**: you start at step 0 and each time climb 1 or 2 steps. In how many ways can you reach step n? With n=3 you can count: `1+1+1`, `1+2` and `2+1`, so 3 ways. The idea: you reach step i either from i−1 or from i−2, and these two groups are separate. So `ways(i) = ways(i-1) + ways(i-2)`, exactly Fibonacci:

```
stairs 0..8 : [1 1 2 3 5 8 13 21 34]
```

(There is one way to reach step 0: do nothing. For step 3 you see 3, the same as we counted.)

The second example is the **cheapest path through a grid**: each cell has a cost, you start at the top left and move only right or down to reach the bottom right. What is the smallest total cost? You reach a cell either from above or from the left, so the cheapest cost of a cell is its own cost plus the smaller of those two neighbors. The cost grid (3 rows, 4 columns):

```
1 3 1 2
1 5 1 9
4 2 1 1
```

We fill the answer table cell by cell. The first row can only come from the left (1, 1+3=4, 4+1=5, 5+2=7). The first column only from above (1, 1+1=2, 2+4=6). Take the cell (row 1, column 1): from above comes 4 and from the left 2, the smaller is 2, so 2 + 5 = 7. The rest follows the same way:

```
table:  [1 4 5 7]
        [2 7 6 15]
        [6 8 7 8]
brute: 8
```

The bottom-right cell is the answer: 8. The `brute: 8` line means a plain recursion that tries all paths gives the same. An optimal path: `1 → 3 → 1 → 1 → 1 → 1` (right, right, down, down, right).

## A recipe

From these examples we can build a pattern that works for any DP problem. Ask five questions:

1. **state**: what do the function's arguments mean? For coins: `dp[a]` = the fewest coins for amount `a`.
2. **transition**: how is each state built from smaller states?
3. **base case**: what is known without recursion?
4. **order**: which states must be filled first so their dependencies are ready?
5. **answer**: which state is what we asked for?

## A full example: coin change

The problem: with coins of value 1, 5, 6 and 9, make the amount 11 using the fewest coins. First comes the temptation of the greedy method: always take the largest coin that fits. For 11 it takes 9, then 1 and 1, three coins. But 5 + 6 is just two coins. Greedy misses the best answer here. With DP:

1. state: `dp[a]` = the fewest coins to make amount `a`.
2. transition: for each coin `c` not larger than `a`, one way is to first make `a-c` and add one coin `c`; so `dp[a] = min(dp[a-c] + 1)` over all coins.
3. base: `dp[0] = 0` (amount zero needs no coins).
4. order: `a = 1..11`, small to large.
5. answer: `dp[11]`.

Let's fill the first cells by hand. `dp[1] = 1` (coin 1), `dp[5] = 1`, `dp[6] = 1`, `dp[7] = dp[6] + 1 = 2`. And for 11: with coin 1 we get `dp[10]+1 = 3`, with coin 5 we get `dp[6]+1 = 2`, with coin 6 we get `dp[5]+1 = 2`, with coin 9 we get `dp[2]+1 = 3`. The smallest is 2. The code of this loop (with a `from` array that keeps the last coin used at each amount so we can rebuild the choice later):

```go
for a := 1; a <= amount; a++ {
	table[a] = Inf
	for _, c := range coins {
		if c <= a && table[a-c]+1 < table[a] {
			table[a] = table[a-c] + 1
			from[a] = c
		}
	}
}
```

We try every coin for every amount, so the cost is O(amount × number of coins). The output:

```
table: [0 1 2 3 4 1 1 2 3 1 2 2]
used : [5 6] true
```

`table` is `dp[0]` to `dp[11]`, and the last number is `dp[11] = 2`. `used` shows the chosen coins: 5 and 6. For coins 4 and 6 and amount 7 no combination exists, and the function reports "impossible" (`coins [4 6] amount 7 possible: false`).

## How do we know it is right?

A test builds 300 random inputs (1 to 4 coins of value 1 to 9, amount below 25) and compares the table with a brute-force recursion (trying every possibility). It also checks that the rebuilt coins add up to the amount. It does the same for 300 random cheapest-path grids. A third test says that the four Fibonacci versions (all except the naive one) agree up to n = 40. All pass with `-race`. This is the same {{< term "property-based-testing" "property-based" >}} habit as before: compare a fast method with a slow but obvious one.

## The memoization trap

A memo is correct only if its key contains every input that affects the answer. I deliberately wrote a bad version that keys the memo by the amount only, while the answer also depends on the set of coins (and the memo is kept between calls):

```
bad memo, coins {1,5,6,9}, 11 -> 2
bad memo, coins {1,2},     11 -> 2 (correct: 6)
```

The first call is right. The second call, with different coins, returns the stale answer for amount 11 from the first call: 2, when with coins 1 and 2 the correct answer is 6 (five coins of 2 and one coin of 1). The same applies to functions with side effects or hidden inputs (like the time or a global variable): a cached result skips the side effect. And in Go, slices and maps cannot be map keys, so if the state is complex you have to turn it into a comparable key (such as a struct or a string).

## Before you memoize

- **Count the subproblems.** The cost of DP is the number of states times the work per state, not the number of calls of the naive code.
- **Top-down or bottom-up?** If only a few states are actually needed, top-down does less work. If all of them are needed, or you want to avoid the overhead of recursion and a map, go bottom-up.
- **Put every input that affects the answer into the key**, as in the example above.

## Exercise

Change `Coins` so that it counts the number of different ways to make an amount (the order of coins does not matter, so `1+5` and `5+1` are the same). Which loop must be the outer one: amount or coins? Test your answer against brute force.

## What's next

"Dynamic programming 2: classic problems". We apply the same recipe to the famous problems: sequences, subsets and edit distance.
