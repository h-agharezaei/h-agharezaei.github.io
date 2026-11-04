+++
date = '2026-12-01T10:00:00+03:30'
draft = false
title = 'Dynamic arrays and slices from the inside'
description = 'Dynamic arrays in Go: the slice header, real append growth, amortized O(1) with counted copies, preallocation, aliasing and your own DynArray[T].'
contentType = 'tutorial'
categories = ["Algorithms"]
series = ["Algorithms"]
tags = ["algorithms", "data-structures", "go", "slice", "dynamic-array"]
cover = { image = "/images/covers/algo-dynamic-arrays.png", alt = "Dynamic arrays and slices from the inside", hiddenInSingle = true }
+++

Every time you call `append`, Go has to find room for one more element. Usually there is room and it costs almost nothing. Sometimes there is not, and the whole slice has to move to a bigger place, copying every element on the way. So a single `append` can be very expensive. And yet, if you add a million elements one by one, the total number of copies per `append` stays around 4. How can both be true?

This post answers that by looking inside the {{< term "dynamic-array" "dynamic array" >}}, probably the most used data structure there is. In Go it hides behind the slice, which we met in [Slices, maps and strings in Go](/posts/go-slices-maps-strings/). I measure it the way we set up in [Big-O analysis with real measurements](/posts/algo-big-o-measured/): count first, and only print things that are exact. The memory side of slices is in [Pointers and the memory model in Go](/posts/go-pointers-memory/), and at the end we write our own container using [Generics in Go](/posts/go-generics/).

> Everything here was run with Go 1.27 as a local example. I print counts and sequences, no timings. The exact growth numbers are an implementation detail of the Go runtime, not a promise of the language, so they may change between versions.

## The idea: an array that can grow

An **array** is a block of memory split into equal slots, one after another. Because the slots are the same size and sit side by side, finding element number `i` is just arithmetic: start address plus `i` times the slot size. That is why indexing is instant, O(1).

```
slot:   0    1    2    3
      [ 10 ][ 20 ][ 30 ][ 40 ]
```

The price is that an array has a fixed size. If you need a fifth slot, you cannot simply extend the block, because the memory right after it may be used by something else. The fix is to ask for a bigger block somewhere else, copy the old elements into it, and use the new block from now on:

```
old:  [ 10 ][ 20 ][ 30 ][ 40 ]
new:  [ 10 ][ 20 ][ 30 ][ 40 ][ 50 ][    ][    ][    ]
                                 ^ spare room for later
```

Notice that the new block is bigger than what we needed right now. The extra room is what makes the next few additions free. That is the whole idea of a dynamic array: **keep spare room at the end, and only when it runs out, move to a bigger block.** The length (how many slots are in use) and the capacity (how many slots the block has) are two different numbers.

## The slice header

In Go, a {{< term "slice" "slice" >}} is exactly this idea. A slice value is not the elements themselves. It is a small descriptor of three words: a pointer to the first element, the length `len`, and the capacity `cap`. The pointer points into a {{< term "backing-array" "backing array" >}}, the block of memory that really holds the elements.

This small program checks the size of that descriptor, and then makes two slices over the same array to show that they share it:

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

The first line says the descriptor is 24 bytes (three 8-byte words on a 64-bit machine). `a` has length 3 and capacity 10; `b := a[:2]` is a second descriptor over the same array with length 2. We write 7 through `b[0]`, and `a` sees it too, and the last value `true` confirms that both start at the same memory address. So copying a slice copies 24 bytes and never the elements: `a` and `b` are two headers over one array.

## How append really grows

When the capacity runs out, how much bigger is the new block? To see this I appended one zero value at a time and recorded every new `cap` I saw:

```
[]int : [4 8 16 32 64 128 256 512 848 1280 1792 2560]
[]byte: [32 64 128 256 512 896 1408 2048]
3-byte struct: [10 21 42 85 170]
```

Each list is the capacities, in order, for a slice that grows from empty to about 2,000 elements (100 for the 3-byte struct). For `[]int`, the capacity starts at 4 and doubles up to 256 and 512. After that the steps become smaller than a doubling (512 to 848 is 1.66 times, 848 to 1280 is 1.5 times, and later steps get closer to 1.25 times).

According to the Go source (`growslice`), the rule is: below 256 elements, double; otherwise add `(cap + 3*256) / 4` until it is enough. Then the result is rounded up to a {{< term "size-class" "size class" >}}, one of the fixed block sizes the memory allocator hands out. I checked the numbers by hand for one step: 512 gives 512 + (512 + 768) / 4 = 832 elements, which is 6,656 bytes. The next size class is 6,784 bytes, and 6,784 / 8 = 848. The same works for 848 to 1280 and 1792 to 2560. The `[]byte` row and the 3-byte struct row (32 bytes hold 10 of them) show that the rounding happens even in the small range. I did not investigate why the first value is 4, 32 or 10, so do not rely on it.

## Why append is O(1) amortized

A single append that has to grow copies every element, so the worst case for one call is O(n). But the worst case is rare, and {{< term "amortized-analysis" "amortized analysis" >}} looks at the whole sequence of calls instead of one call. The question becomes: if I do `n` appends in a row, how many element copies happen in total, divided by `n`?

To measure it, I detected every `cap` change during the appends and added up the number of elements that had to be copied each time:

```
n=1000    copies=1868     copies/n=1.87
n=10000   copies=32415    copies/n=3.24
n=100000  copies=402079   copies/n=4.02
n=1000000 copies=4154015  copies/n=4.15
```

The last column is the number of copies per append. It does not keep growing with `n`; it levels off near 4. A growth factor explains why. Each grow copies everything the slice holds at that moment, and each block is 1.25 times bigger than the one before. Those copy sizes add up like a geometric series to about `n / 0.25 = 4n`. With pure doubling the total would be about `n`. Either way the total is `c·n` for some constant `c`, so on average each append costs O(1). The factor is a trade-off: a smaller factor means more copying, a bigger one means more unused memory.

## Preallocation

If you already know how many elements are coming, tell Go. Then it can allocate the right block once and never grow. I measured with `testing.AllocsPerRun` over 1,000 appends, without and with `make([]int, 0, N)`:

```
without prealloc: 9   with make([]int, 0, N): 1
```

Nine memory allocations became one. These are allocation counts, not time.

## Insert, delete and the aliasing trap

Inserting in the middle has to shift every element after the position one slot to the right, so it is O(n). Delete shifts them left, also O(n).

```go
x = slices.Insert(x, 1, 99)   // [1 99 2 3 4 5]
z := slices.Delete(y, 1, 3)   // result [1 4 5], y is now [1 4 5 0 0]
```

`slices.Delete` shifts the elements and, since Go 1.22, zeroes the obsolete tail. The demo confirms it: the original `y` ends in two zeros. So never use the old slice after `Delete`; use the returned one.

The most surprising behaviour of slices is **aliasing**: two slices that share one array. What `append` does depends on whether there is spare capacity:

```
fits:  [42 0 0] [42 0 0 1] shared: true
grows: [42 0 0 1] [-1 0 0 1 2] shared: false
```

In the first line, `p` had length 3 and capacity 4, so `append` wrote into the same array. Then a write through `q` (`q[0] = 42`) was visible in `p` as well. In the second line, `q` was full, so `append` allocated a new array. After that the two are independent: the write `r[0] = -1` changed only `r`. This is why you always write `s = append(s, x)`, and why you should never guess which of the two cases you are in.

## Our own DynArray[T]

To check that we understand all this, let us write the container ourselves. It has `Push`, `Pop`, `At`, `Insert`, doubling growth, and a `Copies` counter so that we can count the work. The core is:

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

`Push` checks whether the block is full. If it is, `grow` makes a block twice as big and copies the used part, adding the number of copied elements to `Copies`. Then the value goes into the next free slot. `Pop` zeroes the slot it frees, so that the container does not keep a pointer alive by accident. After 1,000 pushes the demo prints `len 1000 cap 1024 copies 1023`: the copies are 1,023, close to `n` and below `2n`, as doubling predicts.

The tests cover push, pop, insert, popping an empty array, copies below `2n`, and independent instances in goroutines. They pass with `go test -race`. The container itself is not safe for concurrent use; the race test only checks that separate instances do not interfere.

For comparison I also ran the same experiment in Rust: the capacities of a `Vec<u32>` were `[4, 8, 16, ... 2048]` and a `Vec<u8>` started at 8. It also doubles, only with a different start.

## Common traps with slices

- **Always assign the result of `append`.** It may return a different slice (a new array), and if you throw the result away you may keep using the old one.
- **Slicing shares memory.** When you need isolation, use `slices.Clone`, or `a[:2:2]` which limits the capacity so the next `append` must copy.
- **A small slice of a huge array keeps the whole array alive.** The garbage collector cannot free the array while any slice points into it.
- **Use `make([]T, 0, n)` when `n` is known.** It removes the growth copies completely.
- **Insert and delete in the middle are O(n).** If you do them a lot, the structure may be wrong for the job.

## Exercise

Change `DynArray` to grow by 1.25 times (at least 1 more) and print `Copies/n` for `n = 1000000`. Predict the value first, then compare it with the roughly 4 above. After that, add `Delete(i)` and make it zero the slot that becomes unused.

## What's next

The next post is "Linked lists and why they are rarely the answer". It looks at the textbook rival of the array, a list where each element points to the next, and measures it the same way.
