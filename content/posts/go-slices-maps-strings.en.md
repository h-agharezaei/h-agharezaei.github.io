+++
date = '2026-11-06T10:00:00+03:30'
draft = false
title = 'Slices, maps and strings in Go'
description = 'A practical tour of Go slices, maps and strings: the shared backing array gotcha, nil maps, UTF-8 byte vs rune counts, and a word-frequency counter.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "slice", "map", "string"]
cover = { image = "/images/covers/go-slices-maps-strings.png", alt = "Slices, maps and strings in Go", hiddenInSingle = true }
+++

Say you have a list of five numbers and you cut a piece out of the middle to work on. You expect the original list to stay untouched. In Go that is often not the case: `b := a[1:3]` does not make a copy of the elements, and if you then call `append` on `b`, it may quietly overwrite an element of `a`. Another example: `len("سلام")` is 8, not 4.

**Slices**, **maps** and **strings** appear in almost every Go program, and each has a behavior that surprises newcomers. After [functions, `defer` and error handling](/posts/go-functions-defer-errors/) and [types, variables and control flow](/posts/go-types-control-flow/), we look at these three types by running code and reading real output, not by guessing.

> All code was run with Go 1.26 as a local example. The exact growth of `cap` is an implementation detail, not a language guarantee.

## Arrays and slices

First let us separate two words. An **array** is a row of boxes whose count is fixed, and the count is part of the array's type: `[3]int` means three integers, and `[4]int` is a different type. When you assign an array to another variable, it is copied.

A **slice** is something else. Think of it as a "window" onto a row of boxes: it holds no data of its own, it only says which array you start from, at which box, and how many boxes you can see. In practice a slice is a small header with three fields: a pointer to an underlying array (the **backing array**), `len` (how many elements you see) and `cap` (how many boxes there are from this point to the end of the backing array). You work with slices almost all the time, rarely with arrays.

This code shows the difference, and also how a slice grows with `append`:

```go
arr := [3]int{1, 2, 3}
b := arr // arrays are copied
b[0] = 99
fmt.Println(arr, b)

var s []int
for i := 0; i < 10; i++ {
    s = append(s, i)
    fmt.Printf("len=%d cap=%d\n", len(s), cap(s))
}
```

```
[1 2 3] [99 2 3]
len=1 cap=4
len=2 cap=4
len=3 cap=4
len=4 cap=4
len=5 cap=8
...
len=9 cap=16
len=10 cap=16
```

The first line shows `b` is an independent copy: changing `b[0]` does not touch `arr`. The rest is the slice growing (I removed a few lines in the middle). Each `append` adds one element and `len` goes up by one. `cap` stays the same until the room runs out. At `len=5` the capacity jumps from 4 to 8, and at `len=9` from 8 to 16: Go allocated a bigger array and copied the data into it. That is why you must always write `s = append(s, ...)`; the result may point at a different array. (The exact growth numbers are an implementation detail, not a language guarantee.)

## The classic trap: a shared backing array

Now to the example from the start. Slicing does not copy data; it only creates a new window onto the same array. So two slices can look at the same memory. Let us see step by step what happens:

```go
a := []int{1, 2, 3, 4, 5}
b := a[1:3]
fmt.Println(b, len(b), cap(b))
b[0] = 99
fmt.Println(a, b)
b = append(b, 77) // fits in cap: overwrites a[3]
fmt.Println(a, b)
c := append(a[:2:2], 1000) // full slice expression forces a new array
c[0] = -1
fmt.Println(a, c)
```

```
[2 3] 2 4
[1 99 3 4 5] [99 3]
[1 99 3 77 5] [99 3 77]
[1 99 3 77 5] [-1 99 1000]
```

- **First line:** `b := a[1:3]` shows elements number 1 and 2 of `a`, so `[2 3]` with `len` 2. `cap` is 4 because from box 1 to the end of `a` there are four boxes.
- **Second line:** we wrote `b[0] = 99`, yet `a` changed too: `a[1]` is now 99. `b[0]` and `a[1]` are the same box.
- **Third line:** it gets worse. `b` has only two elements but a capacity of 4. When we call `append(b, 77)`, there is spare room within the capacity, so Go does not allocate a new array and writes 77 into the box right after `b`. That box is `a[3]`. The result: `a[3]` silently changed from 4 to 77.
- **Last line:** the three-index form `a[:2:2]` limits the capacity too: two elements with a capacity of 2. So `append` has no spare room and has to allocate a new array. `c` lives on the new array, and `c[0] = -1` no longer touches `a`: `a` stays `[1 99 3 77 5]`.

The practical conclusion: if you want a sub-slice not to affect the original data, either `copy` (next section) or limit the capacity with `a[:n:n]`.

## copy, make and nil versus empty

Three small things worth knowing. `make([]int, 2, 5)` creates a slice with `len` 2 and `cap` 5 whose elements are all zero values. `copy(dst, src)` copies elements into another slice and returns how many it copied. And a `nil` slice differs subtly from an empty slice:

```go
var nilS []int
empty := []int{}
fmt.Println(nilS == nil, empty == nil, len(nilS), len(empty))

m := make([]int, 2, 5) // len 2, cap 5
fmt.Println(m, len(m), cap(m))

src := []int{1, 2, 3}
dst := make([]int, len(src))
n := copy(dst, src)
dst[0] = 100
fmt.Println(n, src, dst)
```

```
true false 0 0
[0 0] 2 5
3 [1 2 3] [100 2 3]
```

First line: both slices have length 0, but only the first equals `nil`. In practice both work with `append` and `range`; they differ only when compared directly with `nil`. The second line is the `make` slice: two zeros and a capacity of 5. Third line: `copy` copied three elements (the return value is 3), and because `dst` has its own array, changing `dst[0]` does not affect `src`.

## Maps

A **map** is a table from keys to values. This example shows creating, reading, deleting and copying a map:

```go
ages := map[string]int{"ali": 30, "sara": 25}
ages["reza"] = 41
v, ok := ages["nobody"]
fmt.Println(v, ok)
if age, ok := ages["sara"]; ok {
    fmt.Println("sara", age)
}
delete(ages, "ali")
delete(ages, "ghost") // no-op
fmt.Println(len(ages), ages)

alias := ages
alias["sara"] = 26
fmt.Println(ages["sara"])
```

```
0 false
sara 25
2 map[reza:41 sara:25]
26
```

When a key is not in the map, reading it returns the zero value of the value type (here `0`), not an error. So how do we tell "the key is missing" from "the value really is zero"? With the two-value form called **comma-ok**: `v, ok := ages["nobody"]`. `ok` says whether the key existed. The first output line is exactly that: `0 false`. The second line uses the same pattern in an `if`. Then you see `delete`: deleting `"ali"` removes the key, and deleting a missing key (`"ghost"`) does nothing; that is why `len` on the third line is 2.

The last line: `alias := ages` does not create a new map, it only copies the reference to the same map. So changing `alias["sara"]` makes `ages["sara"]` 26 too.

We saw in earlier posts that reading from a `nil` map is fine, but writing panics:

```go
var m map[string]int
m["a"] = 1
```

```
panic: assignment to entry in nil map
```

Always create a map with `make` or a literal (like `map[string]int{}`).

One more thing: the iteration order of a map is unspecified, and Go deliberately randomizes it so nobody relies on a particular order. I iterated an eight-key map in two runs and got `0 1 2 3 4 5 6 7` once and `6 7 0 1 2 3 4 5` the other time. When I re-ran the same program while rewriting this post, I saw other orders again, such as `1 2 3 4 5 6 7 0` and `3 4 5 6 7 0 1 2`. Never rely on the order.

## Strings

In the types post we saw that a string is an immutable sequence of bytes, usually UTF-8, and that `len` counts bytes. Now we put them side by side: `utf8.RuneCountInString` gives the number of characters (**runes**), and `range` over a string goes rune by rune. We try three words, one English, one Persian and one emoji:

```go
for _, w := range []string{"hello", "سلام", "🚀"} {
    fmt.Println(w, len(w), utf8.RuneCountInString(w))
}
for i, r := range "سلام" {
    fmt.Printf("%d:%c(%U) ", i, r, r)
}
```

```
hello 5 5
سلام 8 4
🚀 4 1
0:س(U+0633) 2:ل(U+0644) 4:ا(U+0627) 6:م(U+0645)
```

For each word there are two numbers: the byte count and the rune count. For `hello` both are 5, since each English letter is one byte. The Persian word has 4 runes but 8 bytes, and the rocket has 1 rune but 4 bytes. The last line shows the index and Unicode code of each letter of `سلام` (`%c` is the letter itself and `%U` its code). The indexes advance by two (0, 2, 4, 6), because each letter takes two bytes.

The consequence: `s[0]` gives a byte, not a character. For `"سلام"` that expression gave 216, which is the first byte of the letter "س".

Now building strings. Because strings are immutable, gluing text onto one repeatedly in a loop creates a new string every time. To build text in a loop use `strings.Builder`. Also know three common functions: `Split` cuts a text on a separator, `Join` does the reverse, and `Fields` splits on whitespace:

```go
var sb strings.Builder
for i := 0; i < 3; i++ {
    fmt.Fprintf(&sb, "item%d,", i)
}
sb.WriteString("end")
fmt.Println(sb.String())

parts := strings.Split("a,b,,c", ",")
fmt.Printf("%q\n", parts)
fmt.Println(strings.Join(parts, "-"))
fmt.Printf("%q\n", strings.Fields("  go   is \t fun\n"))
```

```
item0,item1,item2,end
["a" "b" "" "c"]
a-b--c
["go" "is" "fun"]
```

The `Builder` appends `item…,` three times and then `end`, and hands out the string once at the end. `Split` on `"a,b,,c"` gives four pieces and keeps the empty piece between the two commas; that is why `Join` with `-` produces `a-b--c`. `Fields` splits on any run of spaces, tabs and newlines and drops empty pieces, so that messy text ends up as just three words.

## A small program: counting word frequency

Now let us use all three types together. We want to see how many times each word appears in a sentence. A map takes a word to its count. But since map order is unspecified, to print in a stable order we put the keys in a slice and sort it:

```go
text := "the quick brown fox jumps over the lazy dog the fox"
counts := map[string]int{}
for _, w := range strings.Fields(strings.ToLower(text)) {
    counts[w]++
}
keys := make([]string, 0, len(counts))
for k := range counts {
    keys = append(keys, k)
}
sort.Slice(keys, func(i, j int) bool {
    if counts[keys[i]] != counts[keys[j]] {
        return counts[keys[i]] > counts[keys[j]]
    }
    return keys[i] < keys[j]
})
for _, k := range keys {
    fmt.Printf("%-6s %d\n", k, counts[k])
}
```

```
the    3
fox    2
brown  1
dog    1
jumps  1
lazy   1
over   1
quick  1
```

`counts[w]++` relies on the zero value of a missing key: the first time a word appears its value is 0 and it becomes 1. After counting, we put the keys into `keys` and sort them with `sort.Slice` and a comparison function: first by count (high to low), and by alphabet when the counts are equal. The output shows exactly that: `the` three times, `fox` twice, and the rest once in alphabetical order. And since we fixed the order ourselves with the sort, the output is the same on every run.

## Where slices and maps surprise you

- **Always assign the result of `append`** (`s = append(s, x)`), and remember that the result may or may not share memory with the original slice, depending on whether there was room.
- **Sub-slices share the backing array.** For independence use `copy` or `a[:n:n]`.
- **Writing to a nil map panics; reading does not.**
- **Do not rely on map iteration order.** For stable output, sort the keys.
- **`len(s)` is bytes, not characters.** For text use `utf8.RuneCountInString` or `range`.

## Exercise

1. Write `func removeAt(s []int, i int) []int` and see what happens to the contents of the original slice.
2. Extend the word counter so that it reads a Persian sentence and also prints the rune count of each word.

## What's next

"Structs, methods and interfaces in Go": so far we have only seen the language's built-in types, and that post introduces the building blocks for making our own.
