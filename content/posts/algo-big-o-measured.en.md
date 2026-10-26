+++
date = '2026-11-25T10:00:00+03:30'
draft = false
title = 'Big-O analysis with real measurements'
description = 'Big-O analysis in Go: exact operation counts for search and duplicate checks, then testing.B timings that show where theory fits and where it fails.'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "big-o", "go", "benchmark", "complexity"]
cover = { image = "/images/covers/algo-big-o-measured.png", alt = "Big-O analysis with real measurements", hiddenInSingle = true }
+++

This opens the Algorithms series. Explanations of {{< term "big-o" "Big-O" >}} usually stay on the whiteboard. Here I count operations first, because counts are exact, then time the same code with `testing.B`. Benchmarks: [Testing in Go: table-driven tests and benchmarks](/posts/go-testing-basics/); finding real hot spots: [Profiling Go with pprof](/posts/go-profiling-pprof/).

> Everything ran as a local example on Go 1.26, Apple M-series arm64. Counts are exact. Timings are medians of 5 runs, **measured on this machine**, 1-minute load average 1.89 at the start of the run and 2.96 at the end (other work was running): shapes, not facts.

## What Big-O says, and what it does not

Big-O is an upper bound on cost growth with input size `n`. Drop constants and lower terms: `3n² + 10n + 7` is O(n²).

| Class | Name | Example |
|---|---|---|
| O(1) | constant | index into a slice |
| O(log n) | logarithmic | binary search |
| O(n) | linear | scan a slice |
| O(n log n) | linearithmic | sorting |
| O(n²) | quadratic | compare every pair |

It does **not** tell you actual time, which is faster at small `n`, or how the cache behaves. It tells you what happens when `n` doubles, and that is what we measure.

## Count first: search

`LinearSearch` and `BinarySearch` return their comparison count; the key is absent (worst case) in a sorted slice:

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

Doubling `n` doubles the linear count and adds one to the {{< term "binary-search" "binary search" >}} count: O(n) against O(log n), no timing involved.

## Count first: duplicates

Does a slice of distinct values contain a duplicate? Three ways: nested loops, sort a copy and scan neighbours, or a {{< term "hash-table" "hash set" >}}:

```
      n      quadratic    sort+scan      map
   1000         499500          999     1000   (sort comparisons: 10343)
   4000        7998000         3999     4000   (sort comparisons: 51678)
  16000      127992000        15999    16000   (sort comparisons: 238193)
```

Quadratic grows 16x for 4x the input. The sort's comparison count (measured with `sort.Slice`) grows a little over 2x per doubling, which is n log n; the scan itself is linear, the sort is the cost.

## Now time it

Benchmarks use `b.Loop()`; I built the test binary first, so compilation is not timed.

| n | linear | binary |
|---|---|---|
| 1,024 | 331 ns | 8.5 ns |
| 16,384 | 5,159 ns | 11.0 ns |
| 262,144 | 82,111 ns | 13.6 ns |
| 1,048,576 | 341,816 ns | 15.3 ns |

Doubling 1,024 to 2,048 took the linear scan from 331 to 652 ns (1.97x); binary search grows about 0.7 ns per doubling. Theory and measurement agree.

For duplicates (time per call, microseconds):

| n | quadratic | sort+scan | map |
|---|---|---|---|
| 1,024 | 179 | 10.8 | 14.4 |
| 4,096 | 2,681 | 128 | 58 |
| 16,384 | 42,411 | 735 | 255 |

Per doubling, quadratic grew 3.8x to 4.0x and the map 2.0x to 2.2x. Sort+scan was noisy (2.1x to 4.5x), so I claim no clean slope from it. At 1,024 the sort beat the map; at 16,384 the map won about 3x.

## The small-n surprise

A map lookup is O(1) and a scan is O(n), so the map should win. I looked up the last element of an `[]int` and a `map[int]struct{}`:

| n | slice scan | map |
|---|---|---|
| 4 | 2.5 ns | 3.8 ns |
| 8 | 3.8 ns | 5.1 ns |
| 16 | 6.3 ns | 5.1 ns |
| 64 | 21.4 ns | 5.1 ns |

The map stays near 5 ns for any `n`. The slice wins up to 8 elements and loses from 16: a crossover between 8 and 16 **on this machine, for int keys, key last**. I tested nothing else, so do not copy the number.

## Cache effects

The linear scan cost 0.32 to 0.33 ns per element at 1,024 elements and at 1,048,576 (8 MB of ints): no visible cliff for sequential access. The map's cost per element in the duplicate check rose from about 14 ns to 15.5 ns between 1,024 and 16,384. I ran no experiment isolating the {{< term "cpu-cache" "CPU cache" >}}, so I conclude nothing more.

## A few things to watch

- Big-O compares growth, not speed; constants decide small inputs.
- Input shape matters: my cases were worst cases.
- One machine, one Go version, a busy load: repeat with `-count`.
- Use exact counts to talk about algorithms, timings to talk about this code.
- Without a `sink` variable the compiler may remove the work you time.

## Exercise

Add a `DupSortInPlace` that sorts without copying and compare allocations with `b.ReportAllocs()`. Then find the slice-versus-map crossover for `string` keys on your machine.

## What's next

Dynamic arrays and slices from the inside.
