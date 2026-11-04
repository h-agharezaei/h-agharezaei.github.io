+++
date = '2026-11-25T10:00:00+03:30'
draft = false
title = 'Big-O analysis with real measurements'
description = 'Big-O analysis in Go: exact operation counts for search and duplicate checks, then testing.B timings that show where theory fits and where it fails.'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "big-o", "go", "benchmark", "complexity"]
cover = { image = "/images/covers/algo-big-o-measured.png", alt = "Big-O analysis with real measurements", hiddenInSingle = true }
+++

Here is a result worth a pause. Looking up a key in a map is supposed to be fast, "O(1)", the best a lookup can be. Yet on this machine, scanning a plain slice from start to end beat the map lookup for up to 8 `int` keys. How can the "slow" method win?

The answer is that {{< term "big-o" "Big-O" >}} does not measure speed. It describes how the cost *grows* as the input grows. That is a very useful thing to know, but it is a different question from "which one is faster today, for my data". This post is the first of a series on algorithms and data structures, so I want to start by explaining Big-O in plain words and then check it against real numbers. First I count the operations a piece of code does (a count is exact and never changes between runs). Then I time the same code and see where the theory fits and where it does not. If you want the tools behind the timing, benchmarks are covered in [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/), and finding the places where a program really spends its time is in [Profiling Go with pprof](/posts/go-profiling-pprof/).

> The code is a local example in Go. The operation counts are exact; I re-ran them with Go 1.27 and they match the numbers below. The timings are from an earlier run on Go 1.26 and an Apple M1 (arm64): each one is the median of 5 runs, **measured on this machine**. The one-minute load average was 1.89 at the start of that run and 2.96 at the end, because other work was running. Read them as the shape of the curve, not as exact facts.

## What Big-O says

Start with a small question. You have a phone book with `n` names in no particular order, and you look for one name by reading from the first line. If the book has 1,000 names, you may read up to 1,000 lines. If it has 2,000 names, up to 2,000. The work grows in step with `n`: double the book and you double the work. We say this search is **O(n)**, read "order n" or "linear".

Now suppose the names are sorted. You open the book in the middle, see whether your name comes before or after that page, and throw away half of the book. Then you do the same to the half that is left. Doubling the book now costs you only one extra step. We say this is **O(log n)**: the cost grows like the number of times you can halve `n`. For a million names that is about 20 steps.

That is all Big-O is: a short label for "what happens to the cost when `n` doubles". To keep the label short we ignore two things:

- **Constant factors.** "Twice as slow, always" does not change how the cost grows, so it does not show in the label.
- **Smaller terms.** Take a program that does `3n² + 10n + 7` steps. For `n = 1000` that is 3,000,000 + 10,000 + 7, and the `n²` part is already over 99.6% of the total. So we just say O(n²).

The classes you will meet most often:

| Class | Name | Example | When n doubles |
|---|---|---|---|
| O(1) | constant | index into a slice | same cost |
| O(log n) | logarithmic | binary search | one more step |
| O(n) | linear | scan a slice | cost doubles |
| O(n log n) | linearithmic | sorting | a bit more than double |
| O(n²) | quadratic | compare every pair | cost multiplies by 4 |

Big-O does **not** tell you the real time in nanoseconds, which method is faster for a small `n`, or how the processor's memory behaves. It only tells you the *shape* of the growth. So the plan is simple: use Big-O to predict what should happen when `n` doubles, then measure to see if it does.

## Count first: searching

The first experiment compares two ways to find a number in a sorted slice. `LinearSearch` walks from the start. `BinarySearch` is the halving method from the phone book, called {{< term "binary-search" "binary search" >}}. Both functions return the position they found and also **how many comparisons they made**. I look for a key that is not in the slice, which is the worst case: the search has to go all the way before it can give up.

```
        n       linear   binary
     1000         1000       10
     2000         2000       11
     4000         4000       12
     8000         8000       13
    16000        16000       14
  ...
  1024000      1024000       20
```

Read it down one column at a time. Every time `n` doubles, the linear column doubles too (1000, 2000, 4000...). The binary column goes up by exactly one (10, 11, 12...). From 1,000 to about a million names, linear search went from 1,000 comparisons to 1,024,000, while binary search went from 10 to 20. That is O(n) against O(log n), in numbers rather than in words.

## Count first: finding duplicates

The second experiment is a question you meet all the time: does this slice contain the same value twice? There are three common ways to answer it:

- **Quadratic:** two nested loops compare every value with every other value.
- **Sort and scan:** sort a copy of the slice, then look at neighbours. After sorting, equal values stand next to each other, so one pass is enough.
- **Hash set:** walk through the slice and remember each value in a {{< term "hash-table" "hash set" >}}. If you meet a value that is already in the set, you found a duplicate. We look at how hash tables work later in this series.

All values in my test are different, so no method can stop early. This is again the worst case.

```
      n      quadratic    sort+scan      map
   1000         499500          999     1000   (sort comparisons: 10343)
   4000        7998000         3999     4000   (sort comparisons: 51678)
  16000      127992000        15999    16000   (sort comparisons: 238193)
```

(I show three rows of the output; the program also prints 2000 and 8000.) The "quadratic" column counts inner-loop steps. When the input grows 4 times, from 1000 to 4000, the count grows 16 times, from 499,500 to 7,998,000. That is the signature of O(n²): multiply `n` by 4 and the cost is multiplied by 4².

The "sort+scan" and "map" columns count only the final pass over the slice, so they are about `n` each. For sort+scan that hides the real cost, which is the sorting itself. That is why I counted the comparisons made by `sort.Slice` separately (the last number on each line). They grow by a little more than 2 times per doubling of `n` (10,343, 22,521, 51,678...), which is what `n log n` looks like: slightly worse than linear, far better than quadratic.

## Now time it

Counts tell us about the algorithm. Time tells us about this code on this machine. The benchmarks use `b.Loop()` from Go's `testing` package, which runs the function over and over and reports the average time of one call in nanoseconds (**ns**, a billionth of a second). I built the test binary first so that compilation is not part of the timing.

Searching a slice that does not contain the key, in nanoseconds per call:

| n | linear | binary |
|---|---|---|
| 1,024 | 331 ns | 8.5 ns |
| 16,384 | 5,159 ns | 11.0 ns |
| 262,144 | 82,111 ns | 13.6 ns |
| 1,048,576 | 341,816 ns | 15.3 ns |

The theory says linear search should double its time when `n` doubles. Going from 1,024 to 2,048 elements (a row not in the table above), the scan went from 331 ns to 652 ns, which is 1.97 times. Binary search barely moves: each doubling of `n` adds about 0.7 ns. Between 1,024 and 1,048,576 elements, binary search got about 1.8 times slower while the data got 1,024 times bigger. Here theory and measurement agree.

Now the duplicate check, in microseconds per call (a microsecond is a millionth of a second):

| n | quadratic | sort+scan | map |
|---|---|---|---|
| 1,024 | 179 | 10.8 | 14.4 |
| 4,096 | 2,681 | 128 | 58 |
| 16,384 | 42,411 | 735 | 255 |

Per doubling of `n`, the quadratic method became 3.8 to 4.0 times slower, as the theory says (about 4). The map became 2.0 to 2.2 times slower, which is O(n). Sort+scan was noisy: between 2.1 and 4.5 times per doubling, so I do not claim a clean slope for it. One more detail: at 1,024 elements, sort+scan was actually faster than the map, and at 16,384 the map was about 3 times faster. The ranking changes with `n`.

## The surprise at small n

Back to the question at the top. I looked up the **last** element of an `[]int` (the worst case for a scan) and compared it to a lookup in a `map[int]struct{}` of the same size.

| n | slice scan | map |
|---|---|---|
| 4 | 2.5 ns | 3.8 ns |
| 8 | 3.8 ns | 5.1 ns |
| 16 | 6.3 ns | 5.1 ns |
| 64 | 21.4 ns | 5.1 ns |

The map stays near 5 ns whatever `n` is, which is what O(1) promises. The slice scan keeps growing. But a map lookup has fixed work to do (computing a hash of the key and finding the right place), while a scan over a few neighbouring numbers is very cheap. So the slice wins up to 8 elements and loses from 16. The crossover is somewhere between 8 and 16 **on this machine, for `int` keys, with the key at the end**. I tested nothing else, so please do not copy that number into your own decisions. The lesson is only that constant factors matter when `n` is small.

## A note on cache

Modern processors read memory in chunks and keep recently used chunks in a small fast memory called the {{< term "cpu-cache" "CPU cache" >}}. A scan that walks through neighbouring numbers is the kind of access that suits it. I looked for an effect in the data:

The linear scan cost about 0.32 to 0.33 ns per element at 1,024 elements and also at 1,048,576 elements (8 MB of ints). So I saw no cliff for sequential access. The map's cost per element in the duplicate check rose from about 14 ns to 15.5 ns between 1,024 and 16,384 elements, a small change. I ran no experiment that isolates the CPU cache, so I draw no conclusion beyond this.

## Where measurements mislead

- **Big-O compares growth, not speed.** Constants decide the winner for small inputs, as the previous section showed.
- **Input shape matters.** My cases were worst cases (absent key, no duplicates). With a key near the front or an early duplicate, the results would look different.
- **One machine, one Go version, a busy load.** Repeat the run with `-count` and expect different numbers on your computer.
- **Counts for algorithms, timings for code.** Use exact counts to talk about the algorithm, and timings only to talk about this specific code on this specific machine.
- **The compiler may delete your work.** If a benchmark's result is never used, the compiler is allowed to remove the code you wanted to time. That is why the benchmark file stores results in a package-level variable called `sink`.

## Exercise

Write a `DupSortInPlace` that sorts the slice without making a copy, and compare the allocations (memory requests) against `DupSort` with `b.ReportAllocs()`. Then find the slice-versus-map crossover for `string` keys on your own machine. Is it also between 8 and 16?

## What's next

The next post is "Dynamic arrays and slices from the inside". We start with the data structure we used here without looking inside, Go's slice, and apply the same counting to it.
