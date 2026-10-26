+++
date = '2026-12-01T10:00:00+03:30'
draft = false
title = 'Dynamic arrays and slices from the inside'
description = 'Dynamic arrays in Go: the slice header, real append growth, amortized O(1) with counted copies, preallocation, aliasing and your own DynArray[T].'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "slice", "dynamic-array"]
cover = { image = "/images/covers/algo-dynamic-arrays.png", alt = "Dynamic arrays and slices from the inside", hiddenInSingle = true }
+++

The previous topic in this series was [Big-O analysis with real measurements](/posts/algo-big-o-measured/). Now we apply it to the most used data structure there is, the {{< term "dynamic-array" "dynamic array" >}}. In Go it hides behind the slice, which we met in [Slices, maps and strings in Go](/posts/go-slices-maps-strings/); the memory side is in [Pointers and the memory model in Go](/posts/go-pointers-memory/), and we will write our own container with [Generics in Go](/posts/go-generics/).

> Everything here was run with Go 1.26 as a local example. I print counts and sequences, no timings. Exact growth values are an implementation detail, not a language guarantee.

## The slice header

A {{< term "slice" "slice" >}} is three words: pointer, `len`, `cap`. The pointer points into a {{< term "backing-array" "backing array" >}}.

```go
var s []int
fmt.Println(unsafe.Sizeof(s), "bytes")
a := make([]int, 3, 10)
b := a[:2]
b[0] = 7
fmt.Println(a, b, &a[0] == &b[0])
```

```
24 bytes
[7 0 0] [7 0] true
```

Copying a slice copies 24 bytes, never the elements. `a` and `b` are two headers over one array.

## How append really grows

I appended one zero value at a time and recorded every new `cap`:

```
[]int : [4 8 16 32 64 128 256 512 848 1280 1792 2560]
[]byte: [32 64 128 256 512 896 1408 2048]
3-byte struct: [10 21 42 85 170]
```

Two things show up. Up to 256 the capacity doubles. After that it grows by roughly 1.25x plus a constant. According to the Go source (`growslice`), the rule is: below 256 elements double, otherwise add `(cap + 3*256) / 4` until it is enough. The result is then rounded up to a {{< term "size-class" "size class" >}} of the allocator. I checked the numbers by hand: 512 gives 512 + (512+768)/4 = 832 elements, which is 6656 bytes; the next size class is 6784 bytes, and 6784 / 8 = 848. Same for 848 to 1280 and 1792 to 2560. The `[]byte` row and the 3-byte struct (32 bytes holds 10 of them) show the rounding even in the small range. I did not investigate why the first value is 4, 32 or 10, so do not rely on it.

## Why append is O(1) amortized

A single append can copy everything, so the worst case is O(n). {{< term "amortized-analysis" "Amortized analysis" >}} looks at the whole sequence. I detected every cap change and counted the elements that had to be copied:

```
n=1000    copies=1868     copies/n=1.87
n=10000   copies=32415    copies/n=3.24
n=100000  copies=402079   copies/n=4.02
n=1000000 copies=4154015  copies/n=4.15
```

The copies per append do not grow with n; they level off near 4. That is exactly what a 1.25x growth factor predicts: copies sum to a geometric series, about n / 0.25 = 4n. Pure doubling gives about 2n at most. Either way the total is `c·n`, so each append costs O(1) on average. The price of a smaller factor is more copying; the price of a bigger one is more unused memory.

## Preallocation

If you know the size, say so. With `testing.AllocsPerRun` over 1000 appends:

```
without prealloc: 9   with make([]int, 0, N): 1
```

Nine allocations became one (in this run, values are allocation counts, not time).

## Insert, delete and the aliasing trap

Insert in the middle shifts the tail, so it is O(n); so is delete.

```go
x = slices.Insert(x, 1, 99)   // [1 99 2 3 4 5]
z := slices.Delete(y, 1, 3)   // result [1 4 5], y is now [1 4 5 0 0]
```

`slices.Delete` shifts the elements and, since Go 1.22, zeroes the obsolete tail, which I confirmed above: the original `y` ends in two zeros. Never keep using the old slice after `Delete`.

Aliasing after `append` has two outcomes:

```
fits:  [42 0 0] [42 0 0 1] shared: true
grows: [42 0 0 1] [-1 0 0 1 2] shared: false
```

With spare capacity `append` writes into the same array, so a write through `q` was visible in `p`. When full, it allocates a new array and the two diverge. That is why you always write `s = append(s, x)`, and why you should not guess which case you are in.

## Our own DynArray[T]

The container has `Push`, `Pop`, `At`, `Insert`, doubling growth, and a `Copies` counter. The core is:

```go
func (d *DynArray[T]) grow(min int) {
	newCap := max(1, 2*len(d.data))
	for newCap < min {
		newCap *= 2
	}
	nd := make([]T, newCap)
	d.Copies += copy(nd, d.data[:d.n])
	d.data = nd
}

func (d *DynArray[T]) Push(v T) {
	if d.n == len(d.data) {
		d.grow(d.n + 1)
	}
	d.data[d.n] = v
	d.n++
}
```

`Pop` zeroes the freed slot so it does not keep a pointer alive. After 1000 pushes: `len 1000 cap 1024 copies 1023`, below 2n as expected. The tests (push, pop, insert, empty pop, copies below 2n, and independent instances in goroutines) pass with `go test -race`. The instance is not safe for concurrent use; the race test only checks that separate instances do not interfere.

For comparison I ran Rust: `Vec<u32>` capacities were `[4, 8, 16, ... 2048]` and `Vec<u8>` started at 8. Also doubling, with a different start.

## A few things to watch

- Always assign the result of `append`.
- Slicing shares memory; use `slices.Clone` or `a[:2:2]` when you need isolation.
- A small slice of a huge array keeps the whole array alive.
- `make([]T, 0, n)` when `n` is known.
- Insert and delete in the middle are O(n); if you do them a lot, the structure may be wrong.

## Exercise

Change `DynArray` to grow by 1.25x (at least 1 more) and print `Copies/n` for n = 1000000. Predict the value first, then compare with the ~4 above. Then add `Delete(i)` and make it zero the slot that becomes unused.

## What's next

Linked lists and why they are rarely the answer.
