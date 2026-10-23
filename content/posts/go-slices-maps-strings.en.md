+++
date = '2026-11-06T10:00:00+03:30'
draft = false
title = 'Slices, maps and strings in Go'
description = 'A practical tour of Go slices, maps and strings: the shared backing array gotcha, nil maps, UTF-8 byte vs rune counts, and a word-frequency counter.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "slice", "map", "string"]
cover = { image = "/images/covers/go-slices-maps-strings.png", alt = "Slices, maps and strings in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-functions-defer-errors/) we covered functions, `defer` and error handling. Now the three types you will use in almost every Go program: **slices**, **maps** and **strings**. Each has one behavior that surprises newcomers, so we will run code and look at the output instead of trusting intuition.

> Everything below was run with Go 1.26 as a local example. Note that exact `cap` growth values are an implementation detail, not a language guarantee.

## Arrays and slices

An **array** has its length in its type (`[3]int`) and is copied on assignment. A **slice** is a small header with three fields: a pointer to a backing array, a `len` and a `cap`. You will almost always use slices.

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

When `append` runs out of capacity it allocates a bigger array and copies. That is why you must write `s = append(s, ...)`: the result may point to a different array.

## The classic gotcha: shared backing array

Slicing does not copy. Two slices can look at the same memory.

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

Changing `b[0]` changed `a`. Worse, appending to `b` silently overwrote `a[3]` because `b` still had spare capacity. The three-index form `a[:2:2]` caps the capacity so `append` must allocate, and `a` stays untouched.

## copy, make, nil vs empty

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

A nil slice and an empty slice both have length 0 and work with `append` and `range`; they differ only in `== nil`. `copy` gives you an independent slice.

## Maps

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

A missing key returns the zero value, so use the **comma-ok** form to tell "missing" from "zero". Deleting a missing key is a no-op. Assigning a map copies only a reference, so `alias` and `ages` are the same map.

Reading from a nil map is fine, but writing panics:

```go
var m map[string]int
m["a"] = 1
```

```
panic: assignment to entry in nil map
```

Create maps with `make` or a literal. Also, iteration order is unspecified. I ranged over the same 8-key map in two runs and got `0 1 2 3 4 5 6 7` once and `6 7 0 1 2 3 4 5` the other time. Never depend on order.

## Strings

A string is an immutable sequence of bytes, usually UTF-8. `len` counts bytes; `utf8.RuneCountInString` counts characters (**runes**); `range` yields runes.

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

The Persian word has 4 runes but 8 bytes, and the rocket is 1 rune but 4 bytes. Note the byte indexes jump by 2. Indexing `s[0]` gives a single byte (216 for `سلام`), not a character.

For building strings in a loop use `strings.Builder`, and learn `Split`, `Join` and `Fields`:

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

`Split` keeps empty pieces; `Fields` splits on any whitespace run and drops them.

## Small program: word frequency

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

Because map order is unspecified, we copy the keys into a slice and sort them: by count descending, then alphabetically.

## A few things to watch

- Always assign the result of `append`, and remember it may or may not share memory with the original.
- Sub-slices share the backing array; use `copy` or `a[:n:n]` when you need independence.
- Writing to a nil map panics; reading from one does not.
- Never rely on map iteration order; sort the keys when you need a stable output.
- `len(s)` is bytes, not characters. Use `utf8.RuneCountInString` or `range` for text.

## Exercise

1. Write `func removeAt(s []int, i int) []int` and check what happens to the original slice's contents.
2. Extend the word counter to read a sentence in Persian and print the rune count of each word.

## What's next

Next we look at structs, methods and interfaces in Go, the building blocks for modeling your own types.
