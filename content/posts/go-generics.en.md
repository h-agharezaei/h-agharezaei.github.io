+++
date = '2026-11-30T10:00:00+03:30'
draft = false
title = 'Generics in Go'
description = 'Go generics explained: type parameters, constraints, generic functions and types, type inference and the slices, maps and cmp packages.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "generics", "slices", "maps"]
cover = { image = "/images/covers/go-generics.png", alt = "Generics in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-sync-select-context/) we worked with goroutines, channels and context. This post is about **generics**, which arrived in Go 1.18. They let you write one function or type that works for many types while the compiler still checks everything. We will look at the problem they solve, the constraint syntax, a few generic helpers and containers, the standard library packages built on them, and when you should not reach for them.

> Everything below was run with Go 1.26 on macOS (arm64).

## The problem: same code, different types

Without generics, a `Min` for ints and one for floats are two copies of the same logic:

```go
func MinInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func MinFloat(a, b float64) float64 { /* identical body */ }
```

Using `any` and type assertions throws away type safety. A **type parameter** fixes this.

## Type parameters and constraints

A type parameter list goes in square brackets before the normal parameters. Each parameter has a **constraint** saying which types are allowed. `any` allows everything, but then you can only do what every type supports. `comparable` allows types that support `==`. For `<` we need `cmp.Ordered` from the standard library:

```go
func Min[T cmp.Ordered](a, b T) T {
	if a < b {
		return a
	}
	return b
}

fmt.Println(Min(3, 2), Min(1.5, 2.5), Min("b", "a"))
fmt.Println(Min[float64](1, 2.5))
```

```
2 1.5 a
1
```

**Type inference** let us write `Min(3, 2)` without `[int]`. You can still give the type explicitly, as in `Min[float64](1, 2.5)`, which turns the untyped `1` into a float.

## A constraint is an interface

A custom constraint is an interface that lists types. The `~` means "any type whose underlying type is this", so your own named types qualify:

```go
type Number interface {
	~int | ~int64 | ~float64
}

func Sum[T Number](s []T) T {
	var total T
	for _, v := range s {
		total += v
	}
	return total
}

type Cents int

fmt.Println(Sum([]float64{1.5, 2.5}), Sum([]Cents{100, 250}))
```

```
4 350
```

Without the `~`, `Cents` would be rejected, because its type is `Cents`, not `int`.

## Generic helpers

Functions can have several type parameters. These are the classic three, plus `Keys`:

```go
func Map[T, U any](s []T, f func(T) U) []U { /* ... */ }
func Filter[T any](s []T, keep func(T) bool) []T { /* ... */ }
func Reduce[T, A any](s []T, init A, f func(A, T) A) A { /* ... */ }
func Keys[K comparable, V any](m map[K]V) []K { /* ... */ }
```

```go
nums := []int{1, 2, 3, 4, 5}
fmt.Println(Map(nums, func(n int) string { return "#" + strconv.Itoa(n) }))
fmt.Println(Filter(nums, func(n int) bool { return n%2 == 0 }))
fmt.Println(Reduce(nums, 0, func(a, n int) int { return a + n }))
```

```
[#1 #2 #3 #4 #5]
[2 4]
15
```

Map keys must be `comparable`, so `Keys` needs that constraint on `K`. Map iteration order is random, so sort the result if you print it.

## Generic types

Types can have parameters too. Methods repeat the parameter but cannot add new ones:

```go
type Stack[T any] struct{ items []T }

func (s *Stack[T]) Push(v T) { s.items = append(s.items, v) }

func (s *Stack[T]) Pop() (T, bool) {
	var zero T
	if len(s.items) == 0 {
		return zero, false
	}
	v := s.items[len(s.items)-1]
	s.items = s.items[:len(s.items)-1]
	return v, true
}

type Set[T comparable] map[T]struct{}

func (s Set[T]) Add(v T)      { s[v] = struct{}{} }
func (s Set[T]) Has(v T) bool { _, ok := s[v]; return ok }
```

```
b true
0 false
true false
```

The first line is `Pop` on a `Stack[string]` holding "a" and "b"; the second is `Pop` on an empty `Stack[int]`. The third is `Has("go")` and `Has("rust")` on a set containing only "go". `var zero T` is how you return a zero value when you do not know the type. There is no way to write a type without instantiating it: you must write `Stack[string]`.

## The standard library already has the common ones

Before writing your own helpers, check `slices`, `maps` and `cmp`:

```go
fmt.Println(slices.Contains(nums, 3), slices.Index(nums, 4), slices.Max(nums))
fmt.Println(slices.Sorted(maps.Keys(ages)))
keys := slices.Collect(maps.Keys(ages))
slices.Sort(keys)
fmt.Println(cmp.Compare(2, 5))
```

```
true 3 5
[ali reza sara]
-1
```

In Go 1.23 and later `maps.Keys` returns an iterator, not a slice. Turn it into a slice with `slices.Collect`, or collect and sort in one step with `slices.Sorted`.

## When the constraint is not met

If the type does not satisfy the constraint, the compiler tells you at the call site. We called `Min(User{"a"}, User{"b"})`:

```
badconstraint/main.go:18:17: User does not satisfy cmp.Ordered (User missing in ~int | ~int8 | ~int16 | ~int32 | ~int64 | ~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 | ~uintptr | ~float32 | ~float64 | ~string)
```

The error is at compile time, which is the whole point.

## A few things to watch

- Start with concrete code. Write the function for one type first; make it generic when a second real use appears.
- If all you need is behavior, an interface is usually simpler. `io.Reader` does not need a type parameter.
- Do not make something generic just to avoid a few lines of duplication; read the generic version aloud and ask whether it got harder to understand.
- Methods cannot have their own type parameters, only the type can.
- When inference fails you get an error like `cannot infer S`; give the type arguments explicitly.

## Exercise

1. Write `Max[T cmp.Ordered](s []T) (T, bool)` that returns false for an empty slice.
2. Add a `Len() int` method to `Stack[T]` and a `Peek() (T, bool)` method.
3. Write `Uniq[T comparable](s []T) []T` that removes duplicates while keeping the order, using `Set[T]`.

## What's next

In the next post we cover testing in Go: table-driven tests with the `testing` package, subtests and benchmarks.
