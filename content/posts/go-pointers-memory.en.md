+++
date = '2026-11-12T10:00:00+03:30'
draft = false
title = 'Pointers and the memory model in Go'
description = 'How pointers, pass-by-value, nil, escape analysis and Go 1.22 loop variables really work, with runnable examples and real compiler output.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "pointers", "memory"]
cover = { image = "/images/covers/go-pointers-memory.png", alt = "Pointers and the memory model in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-structs-methods-interfaces/) we gave methods pointer receivers without asking much about what a pointer actually is. This post fills that gap: how `&` and `*` work, why Go copies everything, what a nil pointer does to your program, and how the compiler decides where a value lives.

> Everything below was run with Go 1.26 on macOS (arm64).

## `&`, `*` and pass-by-value

`&x` gives the address of `x`; `*p` follows a pointer to the value behind it. The most important rule is that **Go always passes by value**: a function receives a copy of every argument. A pointer is also copied, but both copies point to the same value.

```go
func incValue(n int) { n++ }
func incPtr(n *int)  { *n++ }

func birthdayCopy(u User) { u.Age++ }
func birthday(u *User)    { u.Age++ }
```

```
after incValue: 10
after incPtr:   11
after copy:     {Ali 30}
after pointer:  {Ali 31}
```

`incValue` changed only its own copy. Structs behave exactly like ints here.

## Pointers to structs, `new` and `&T{}`

With a pointer to a struct you write `p.Age`; Go dereferences automatically, so `(*p).Age` is not needed. `new(T)` and `&T{}` both give a `*T`; `new` always gives the zero value, while `&T{...}` lets you set fields.

```go
p := &u
p.Age = 40 // same as (*p).Age = 40
a := new(User)
b := &User{Name: "Sara"}
fmt.Printf("%+v %+v\n", *a, *b)
```

```
{Ali 40} Ali
{Name: Age:0} {Name:Sara Age:0}
```

In practice `&T{...}` is what you will see almost everywhere.

## nil pointers

The zero value of a pointer is `nil`. Comparing with nil is fine; dereferencing it panics:

```go
var np *User
fmt.Println(np == nil)
fmt.Println(np.Name)
```

```
true
panic: runtime error: invalid memory address or nil pointer dereference
[signal SIGSEGV: segmentation violation code=0x2 addr=0x0 pc=0x102868f48]
goroutine 1 [running]:
main.main()
	.../go-pointers-memory/main.go:58 +0x5a8
```

The file and line in the trace point at the exact dereference, so these panics are easy to locate. The fix is to check for nil before using a pointer that may legitimately be absent.

## Slices and maps: values that hold references

A slice is a small struct (pointer to an array, length, capacity), and a map or channel is itself a reference to runtime data. Passing them copies that small header, not the data:

```go
grow := func(s []int) { s[0] = 99; s = append(s, 4) }
grow(s) // s := []int{1, 2, 3}
func(m map[string]int) { m["a"] = 1 }(m)
```

```
[99 2 3] 3
map[a:1]
```

The element write is visible to the caller, but the `append` is not: the function's copy of the header got the new length, ours did not. That is the same behavior we saw in the slices post, now with an explanation.

## Stack, heap and escape analysis

Go decides where a value lives, not you. Roughly: values that nobody can reach after the function returns stay on the cheap **stack**; values that outlive the call go to the **heap**, which the garbage collector manages. The compiler's **escape analysis** makes that decision, and `-gcflags=-m` shows it:

```go
func sumLocal() int {
	p := Point{1, 2}
	q := &p // pointer, but it never leaves the function
	return q.X + q.Y
}

func newPoint() *Point {
	p := Point{1, 2}
	return &p // caller will use it after we return
}
```

```
$ go build -gcflags=-m esc.go
./esc.go:5:6: can inline sumLocal
./esc.go:11:6: can inline newPoint
./esc.go:12:2: moved to heap: p
```

Only the `p` in `newPoint` is moved to the heap. Returning `&p` is perfectly safe in Go. You rarely need to care, but it explains why "pointers are slow because of the heap" is too simple.

## Loop variables since Go 1.22

Before Go 1.22 all iterations of a `for` loop shared one variable, so closures captured the same `i`. Since 1.22 each iteration gets its own copy (when your `go.mod` says `go 1.22` or newer):

```go
var fs []func() int
for i := 0; i < 3; i++ {
	fs = append(fs, func() int { return i })
}
```

```
0 1 2
```

The old behavior would have printed `3 3 3`. I did not run the old version, so take that from the Go 1.22 release notes.

## Pointer or value?

- Use a pointer when the function or method must modify the receiver.
- Use a pointer for large structs you do not want to copy on each call.
- Use a pointer when "absent" is meaningful (`*string` can be nil, `string` cannot).
- Otherwise prefer plain values: they are simpler and need no nil checks.

## A few things to watch

- Don't mix value and pointer receivers on one type; pick one.
- Check pointers for nil before dereferencing when they can be absent.
- Copying a slice header does not copy elements, so two slices may share data.
- A pointer to a loop variable is safe on Go 1.22+, but older `go.mod` versions keep the old behavior.
- Don't optimize with pointers before measuring; escape analysis is smarter than guesses.

## Exercise

1. Write `swap(a, b *int)` and call it.
2. Write a function that returns `*User` or `nil` when a name is not found, and handle both cases in the caller.
3. Run `go build -gcflags=-m` on a function of your own and find a `moved to heap` line.

## What's next

Next we look at packages and modules: how to structure a Go project into packages and manage dependencies with `go.mod`.
