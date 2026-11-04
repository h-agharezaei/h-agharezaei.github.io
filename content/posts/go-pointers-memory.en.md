+++
date = '2026-11-12T10:00:00+03:30'
draft = false
title = 'Pointers and the memory model in Go'
description = 'How pointers, pass-by-value, nil, escape analysis and Go 1.22 loop variables really work, with runnable examples and real compiler output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "pointers", "memory"]
cover = { image = "/images/covers/go-pointers-memory.png", alt = "Pointers and the memory model in Go", hiddenInSingle = true }
+++

Imagine you write a function that adds one to a user's age. You call it, and afterwards the age is unchanged. The code looks right and the compiler says nothing. The reason is that Go hands every argument to a function **as a copy**, so the function worked on the copy. The fix is a **pointer**.

There is also a reverse question. In Go you can return the address of a local variable from a function (`return &p`), and it is perfectly safe. In a language like C the same thing is dangerous, because a local variable dies when the function returns. How does Go keep this safe? The answer to both questions comes from two ideas: Go always passes copies, and the compiler, not you, decides where each value lives.

In [structs, methods and interfaces](/posts/go-structs-methods-interfaces/) we gave methods pointer receivers and said they let you change the value, but we did not say much about what a pointer is. This post fills that gap. It also explains the `append` behavior we saw in [slices, maps and strings](/posts/go-slices-maps-strings/).

> Everything below was run with Go 1.26 on macOS (arm64). The code is a local example, and I shortened the file paths in the output.

## What is a pointer?

Every variable lives somewhere in memory, and that place has an **address**. A pointer is a variable that holds the address of another value instead of the value itself. It is like handing someone the location of the cabinet where a document is kept, instead of a photocopy: they go there and see the same document, and if they write on it, you see that too.

Go has two operators for this:

- `&x` means "the address of `x`".
- `*p` means "the thing `p` points to"; following a pointer like this is called **dereferencing**.

And one rule to keep in mind at all times: **Go always passes by value.** Whatever you pass to a function, the function gets a copy. A pointer is copied too, but both copies point to the same value, so the function can change the value behind the pointer.

The small program below has four functions. Two add one to an `int` (one using a copy, one using a pointer), and two do the same to a `User`'s age. After each call we print the value:

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

`x` started at 10 and Ali's age at 30. First line: `incValue` increased only its own copy, so `x` stayed 10. Second line: we gave `incPtr` the address of `x` (`&x`), and `*n++` changed the value behind that address, so `x` became 11. Lines three and four are the same story with a struct: a struct is copied just like an `int`, so `birthdayCopy` has no effect and `birthday` makes the age 31.

## Pointers to structs, `new` and `&T{}`

With a pointer to a struct you do not have to write `(*p).Age` every time. You write `p.Age` and Go follows the pointer for you. There are two ways to create a pointer: `new(T)` makes a zero-valued `T` and gives you its address, and `&T{...}` does the same but lets you set fields right away.

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

The first line comes from a separate `Println` in the same program (`fmt.Println(u, (*p).Name)`): after `p.Age = 40`, `u` itself is 40, because `p` points at `u`. Then `(*p).Name` gives the name, `Ali`. The second line shows that `new(User)` made a user with empty fields (empty `Name`, zero `Age`) and `&User{Name: "Sara"}` filled in only the name. Here we printed `*a` and `*b`, the values behind the pointers. In practice you will see `&T{...}` almost everywhere.

## nil pointers

A pointer that points at nothing has the value `nil`, and that is also the zero value of every pointer. Comparing it with `nil` is fine, but following it means going to an address that does not exist, and the program panics. This program shows it:

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

The first line is `true`: the comparison was safe. Then `np.Name` crashed the program. The message says "invalid memory address or nil pointer dereference", and `addr=0x0` means it tried to read address zero. (The `pc` value changes from run to run, and `...` stands for the project path.) The good news is that the file and line in the trace point at the exact dereference, so these panics are easy to find.

The fix is simple: if a pointer may legitimately be absent (say, a function that looks for a user and sometimes finds none), ask `if p != nil` before using it.

## Slices and maps: values that hold a reference inside

Now we can solve the `append` puzzle. In the slices post we said a slice is a small header with three fields: a pointer to the backing array, a length and a capacity. When you pass a slice to a function, the "copy" is a copy of that small header. The array of elements is not copied. Maps and channels also hold a pointer to data inside the runtime, so they behave the same way.

Let's see what that means. The function `grow` both changes an element of a slice and calls `append`, and the second function adds a key to a map:

```go
grow := func(s []int) { s[0] = 99; s = append(s, 4) }
grow(s) // s := []int{1, 2, 3}
func(m map[string]int) { m["a"] = 1 }(m)
```

```
[99 2 3] 3
map[a:1]
```

First line: the caller sees `s[0] = 99`, because the copied header points to the same array. But the `append` is invisible, and the length is still 3: the new length (4) was recorded in the function's copy of the header, and our own header stayed as it was. Second line: the map follows the same logic, and its change is visible to the caller. If you want the caller to see an `append`, the function must return the new slice (`s = f(s)`) or take a pointer to the slice.

## Stack, heap and escape analysis

Back to the first question: why is `return &p` safe? We need to know where values live. There are two main places. The **stack** is the cheap, temporary space of each function call, and it is emptied when the function returns. The **heap** is where a value can outlive the function, and the {{< term "garbage-collector" "garbage collector" >}} frees it once nothing can reach it any more.

In Go you do not choose which one. The compiler runs an analysis called **escape analysis** that asks whether a value's address "escapes" the function. If not, the value stays on the stack. If so, it goes to the heap. You can see the decisions with `-gcflags=-m`. Compare the two functions below. In the first, a pointer `q` exists but never leaves the function. In the second, the address is returned:

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

(The real output has a few more lines about `main` being inlined, which I left out because they do not matter here.) The line that counts is the last one: `esc.go:12:2: moved to heap: p`. Line 12 is inside `newPoint`, so that function's `p` was moved to the heap, because its address is still needed after the function returns. There is no message about `p` in `sumLocal`, so it stayed on the stack even though a pointer to it existed. (The first two lines only say that the compiler is able to inline these small functions into their callers.)

So `return &p` is safe in Go: the compiler moves the value to the heap by itself. It also means "pointer means heap, and heap means slow" is too simple. Usually you do not need to worry about this decision.

## Loop variables since Go 1.22

An old Go trap is related to pointers and copies. Before Go 1.22 all iterations of a `for` loop shared one variable `i`. If you created a closure in each iteration that read `i`, all closures saw that same variable. Since Go 1.22 every iteration gets its own copy (as long as `go.mod` says `go 1.22` or newer).

This code builds three functions that each return `i`, and then calls them all:

```go
var fs []func() int
for i := 0; i < 3; i++ {
	fs = append(fs, func() int { return i })
}
```

```
0 1 2
```

Each function saw the `i` of its own iteration. With the old behavior the output would have been `3 3 3`, because all of them shared one `i` that the loop had pushed to 3. I did not run the old version; I take that from the Go 1.22 release notes.

## Pointer or value?

After all this, the practical decision is simple:

- Use a pointer when the function or method must change the receiver itself.
- Use a pointer for a large struct you do not want to copy on every call.
- Use a pointer when "no value" is meaningful: `*string` can be `nil`, `string` cannot.
- Otherwise prefer plain values. They are simpler and need no `nil` check.

## Where pointers bite

- **Don't mix value and pointer receivers on one type.** Pick one. Mixing makes it hard to tell which method works on a copy and which on the object itself.
- **If a pointer may be absent, check it for `nil` before dereferencing.** Otherwise you get a panic like the one above.
- **Copying a slice header does not copy the elements.** Two slices may share data, and a change through one shows up in the other.
- **A pointer to a loop variable is safe from Go 1.22**, but if the project's `go.mod` names an older version, the old behavior comes back.
- **Don't "optimize" with pointers.** Do not assume a pointer is faster before you measure. Escape analysis usually decides better than our guesses.

## Exercise

1. Write `swap(a, b *int)` that exchanges the values of two variables, and call it.
2. Write a function that returns a `*User`, or `nil` if the name is not found, and handle both cases in the caller.
3. Run `go build -gcflags=-m` on a function of your own and find a `moved to heap` line.

## What's next

"Packages and modules: structuring a Go project". So far every example fit in one file. That post shows how to split a Go project into packages and manage dependencies with `go.mod`.
