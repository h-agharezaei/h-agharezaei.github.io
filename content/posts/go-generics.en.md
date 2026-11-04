+++
date = '2026-11-30T10:00:00+03:30'
draft = false
title = 'Generics in Go'
description = 'Go generics explained: type parameters, constraints, generic functions and types, type inference and the slices, maps and cmp packages.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "generics", "slices", "maps"]
cover = { image = "/images/covers/go-generics.png", alt = "Generics in Go", hiddenInSingle = true }
+++

Imagine you want a function that returns the smaller of two numbers. For `int` you write `MinInt`. Then you need `float64` too, so you copy it into `MinFloat`. Then strings. The body of all three is identical, and only the type differs. The other option is to take the parameters as `any` and check the type inside the function, but then the compiler can no longer help you, and mistakes move to run time.

**Generics**, which arrived in Go 1.18, fix this: you write one function or type that works for several types, and the compiler still checks everything. After [sync, select and context in Go](/posts/go-sync-select-context/), where we dealt with concurrency, this post shows what a type parameter and a constraint are, writes a few generic functions and containers, looks at the standard packages, and ends with when to leave generics alone.

> Everything below was run with Go 1.26 on macOS (arm64).

## The problem: one logic, several types

This is the situation I described at the start. Without generics we have two functions that differ only in type:

```go
func MinInt(a, b int) int {
	if a < b {
		return a
	}
	return b
}

func MinFloat(a, b float64) float64 { /* identical body */ }
```

(I ran the full program with both; `MinInt(3, 2)` and `MinFloat(1.5, 2.5)` gave `2` and `1.5`.) You can also write one function with `any`, but `any` means "anything", and you cannot put `<` on "anything". You would have to ask for the type at run time (a type assertion), and if you get it wrong the program panics, not the compiler. The third way is a **type parameter**.

## Type parameters and constraints

The core idea is simple: just as a function has parameters for values, it can have parameters for types. The list of type parameters goes in square brackets, before the normal parameters: `Min[T ...](a, b T) T`. It reads: "a function with type parameter `T`, taking two values of type `T` and returning one of type `T`".

But the compiler needs to know what you may do with `T`. So each type parameter has a **constraint** that says which types are accepted. A few ready-made constraints:

- `any` accepts everything. In return you can only do what every type supports (holding and passing it around, but not comparing, for example).
- `comparable` means types that have `==`.
- `cmp.Ordered` from the standard library means types that can be ordered with `<` and `>` (numbers and strings). `Min` needs this one.

The function and two uses of it:

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

The first line calls `Min` for `int`, `float64` and `string`, with one function. We did not have to write `Min[int](3, 2)`, because the compiler infers the type from the arguments; this is called **type inference**. The second line gives the type explicitly (`Min[float64](1, 2.5)`), which made the untyped constant `1` a float and the answer `1`. (In a real program, Go has built-in `min` and `max` since version 1.21; `Min` here is for teaching the concept.)

## A constraint is an interface

We saw what the ready-made constraints are. What if you want to say "only numbers" yourself? A custom constraint in Go is just an interface with a list of types. The `~` sign means "any type whose underlying type is this one", so your own named types are accepted too:

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

`Sum` takes a slice of any numeric type and returns the total: `1.5 + 2.5` is `4`, and for `Cents`, a type we defined ourselves, `100 + 250` is `350`. Without `~`, `Cents` would be rejected, because its type is `Cents`, not `int`. (`var total T` creates the zero value of type `T`, which is `0`.)

## Generic helper functions

A function can have several type parameters. Look at these three classic functions and `Keys`:

```go
func Map[T, U any](s []T, f func(T) U) []U { /* ... */ }
func Filter[T any](s []T, keep func(T) bool) []T { /* ... */ }
func Reduce[T, A any](s []T, init A, f func(A, T) A) A { /* ... */ }
func Keys[K comparable, V any](m map[K]V) []K { /* ... */ }
```

`Map` turns each element into something else (maybe of another type) using a function: input `T`, output `U`. `Filter` keeps only the elements for which `keep` returns `true`. `Reduce` folds everything into one value (a sum, say). `Keys` returns the keys of a map. The bodies are simple and are in the full program. Usage:

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

The first line turned numbers into strings (`T` is `int`, `U` is `string`). The second kept the even ones. The third added everything up: 15. A map key must be `comparable`, which is why `Keys` asks for that constraint on `K`. Map iteration order is random, so if you print keys, sort them first; in the full program I did that with `slices.Sort` and it printed `[ali reza sara]`.

## Generic types

Types can have parameters too, not only functions. Two examples: a `Stack` for any type, and a `Set` whose elements must be `comparable` because they become map keys. Methods repeat the type parameter but cannot add new ones:

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

In `main` we did three things. First line: `Pop` on a `Stack[string]` where we pushed `"a"` and `"b"`; the last element, `b`, came back, and `true` means the stack was not empty. Second line: `Pop` on an empty `Stack[int]`, which gave the zero value (`0`) and `false`. Third line: `Has("go")` and `Has("rust")` on a set that contains only `"go"`. About `var zero T`: when you do not know the type, this is how you make its zero value. And you cannot use a generic type without giving its parameter: you must write `Stack[string]`.

## The standard library already has the common ones

Before you write your own helper, look at the `slices`, `maps` and `cmp` packages. Many of these are ready-made:

```go
fmt.Println(slices.Contains(nums, 3), slices.Index(nums, 4), slices.Max(nums))
fmt.Println(slices.Sorted(maps.Keys(ages)))
keys := slices.Collect(maps.Keys(ages))
slices.Sort(keys)
fmt.Println(keys)
fmt.Println(cmp.Compare(2, 5))
```

```
true 3 5
[ali reza sara]
[ali reza sara]
-1
```

First line: is `3` in the slice (`true`), at what index is `4` (`3`), and what is the largest element (`5`). The second and third lines both give the sorted keys of the map, in two ways. `cmp.Compare(2, 5)` is `-1`, meaning the first is smaller. In Go 1.23 and later `maps.Keys` returns an iterator, not a slice. Turn it into a slice with `slices.Collect`, or collect and sort in one step with `slices.Sorted`.

## When the constraint is not met

The biggest advantage of generics over `any` is that the mistake is found at compile time. If a type does not meet the constraint, the compiler reports an error at the place where you call the function. We called `Min(User{"a"}, User{"b"})`, where `User` is a struct and has no `<`:

```
badconstraint/main.go:18:17: User does not satisfy cmp.Ordered (User missing in ~int | ~int8 | ~int16 | ~int32 | ~int64 | ~uint | ~uint8 | ~uint16 | ~uint32 | ~uint64 | ~uintptr | ~float32 | ~float64 | ~string)
```

The message says `User` does not meet `cmp.Ordered`, and lists the types that do. This error is at compile time, which is the whole point of generics. (The `go run` output also has a line `# example.com/generics/badconstraint` above this, which I left out.)

## When not to use generics

- **Start from concrete code.** Write the function for one type first. When a second use really arrives, make it generic.
- **If only behavior matters, an interface is usually simpler.** `io.Reader` needs no type parameter, because all we want is to read, and we do not care from where.
- **Don't make something generic just to remove a few repeated lines.** Read the generic version and see whether it became harder to understand.
- **A method cannot have type parameters of its own**; only the type can. If you need that, write a plain function instead of a method.
- **When type inference fails, the compiler says it cannot infer the type.** Then give the type arguments explicitly.

## Exercise

1. Write `Max[T cmp.Ordered](s []T) (T, bool)` that returns `false` for an empty slice.
2. Add the methods `Len() int` and `Peek() (T, bool)` to `Stack[T]`.
3. Write `Uniq[T comparable](s []T) []T` using `Set[T]`, removing duplicates and keeping the order.

## What's next

"Testing in Go: table-driven tests and benchmarks". The generic and helper functions we wrote need tests, and that post shows table-driven tests, subtests and benchmarks with the `testing` package.
