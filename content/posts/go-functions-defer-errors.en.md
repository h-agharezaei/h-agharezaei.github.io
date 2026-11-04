+++
date = '2026-11-04T10:00:00+03:30'
draft = false
title = 'Functions, defer and error handling in Go'
description = 'Go functions with multiple returns, variadics and closures, plus the error interface, %w wrapping, errors.Is/As, defer and why panic is not for errors.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "functions", "errors", "defer"]
cover = { image = "/images/covers/go-functions-defer-errors.png", alt = "Functions, defer and error handling in Go", hiddenInSingle = true }
+++

Imagine a function that opens a file, reads it and pulls a number out of it. Each of those three steps can fail. In languages with exceptions, the failure is thrown out of the middle of the code and a `try/catch` somewhere around it catches it. Go does it differently. It has no exceptions in that sense: functions return errors as ordinary values, the caller checks `if err != nil` right away, and cleanup, like closing that same file, is done with `defer`.

Once these two ideas click, the shape of most Go code and a lot of its style make sense. In this post we first look at functions (because errors start there), then `error`, then `defer`, and finally a short word on `panic`. The only prerequisite is [types, variables and control flow](/posts/go-types-control-flow/).

> I ran every example below with Go 1.26. The outputs are taken from those runs.

## Functions and multiple return values

In Go the type of a parameter comes after its name, and a function can return several values. The second point is the foundation of Go's whole error handling, so we start with a simple example. `divmod` returns the quotient and the remainder together:

```go
func divmod(a, b int) (int, int) { return a / b, a % b }
```

The return types go in parentheses, and at the call site we receive both values into two variables:

```go
q, r := divmod(17, 5)
fmt.Println(q, r)   // 3 2
```

17 divided by 5 is 3 with a remainder of 2. In other languages you would usually return an array or an object and unpack it. In Go the two values simply come back.

Three more things about functions:

```go
func sum(nums ...int) int {
	total := 0
	for _, n := range nums {
		total += n
	}
	return total
}

func counter() func() int {
	n := 0
	return func() int { n++; return n }
}
```

`sum` is **variadic**, which means its number of arguments is not fixed. Inside the function, `nums` is a slice of `int`. You can call it with no arguments, with several, or with a ready-made slice followed by `...`. (The `_` in the loop means we do not need the index and throw it away.)

Functions are values too. `counter` returns a function, and that returned function can reach the variable `n`, which was defined outside of it, and keeps it between calls. Such a function is called a **closure**. Every call to `counter()` creates a fresh, independent `n`.

```go
fmt.Println(sum(), sum(1, 2, 3), sum([]int{4, 5}...)) // 0 6 9
next := counter()
fmt.Println(next(), next(), next())                 // 1 2 3
```

The three `sum` calls give 0 (no arguments), 6 and 9. The three `next()` calls return 1, 2 and 3, because `n` stays alive between calls.

Return values can also be **named**, as in `func f() (n int, err error)`. These variables start at their zero value (which we saw in the previous post) and a bare `return` returns them. Naming helps with `defer`, which we see below. But a bare `return` in a long function makes the reader hunt for where the values were set. I use named results only in short functions, or when a deferred function must change the result.

## The error interface

Now to errors. Go has a type called `error`, which is really just an **interface** with one method: `Error() string`. An interface is a list of methods; any type that has those methods automatically belongs to it. (We cover interfaces fully in a later post.) For now it is enough to know that an error is nothing complicated: any value that can describe itself as a piece of text.

By convention the error is the last return value of a function, and the caller checks it immediately. If nothing went wrong, the error is `nil` ("nothing"):

```go
n, err := strconv.Atoi(s)
if err != nil {
	return 0, err
}
```

`strconv.Atoi` converts a string to a number. If it cannot, `err` is set and we pass it on to our own caller. You will write this `if err != nil` a lot, and that is deliberate: the failure path is visible in the code, and no hidden `throw` gets lost in the middle of your functions.

## Creating, wrapping and inspecting errors

A bare error such as "invalid syntax" is not very useful. After going up several layers of functions you want to know where, and while doing what, it failed. So we have three tools:

- `errors.New` creates a simple error with a message.
- `fmt.Errorf` with the `%w` verb **wraps** an error: it adds new text and context and keeps the original error inside.
- `errors.Is` checks whether a specific error appears somewhere in the chain of wraps, and `errors.As` finds an error of a given type in the chain and hands it to you.

Here is a small program I built for this. It has three pieces. The first is a **sentinel error**, an error defined once at package level so we can compare against it later. The second is a custom error type. (It uses `struct` and a method, which I cover fully in later posts; for now, a `struct` is a group of fields and a method is a function attached to a type. The `*` and `&` belong to pointers, which come in [Pointers and the memory model in Go](/posts/go-pointers-memory/).) The `Unwrap` method tells `errors.Is` and `errors.As` where the inner error is. The third is the functions that use them:

```go
var ErrDivideByZero = errors.New("divide by zero")

type ParseError struct {
	Input string
	Err   error
}

func (e *ParseError) Error() string { return fmt.Sprintf("parse %q: %v", e.Input, e.Err) }
func (e *ParseError) Unwrap() error { return e.Err }

func parse(s string) (int, error) {
	n, err := strconv.Atoi(strings.TrimSpace(s))
	if err != nil {
		return 0, &ParseError{Input: s, Err: err}
	}
	return n, nil
}

func divide(a, b string) (int, error) {
	x, err := parse(a)
	if err != nil {
		return 0, fmt.Errorf("divide: left operand: %w", err)
	}
	y, err := parse(b)
	if err != nil {
		return 0, fmt.Errorf("divide: right operand: %w", err)
	}
	if y == 0 {
		return 0, fmt.Errorf("divide %d by %d: %w", x, y, ErrDivideByZero)
	}
	return x / y, nil
}
```

`parse` turns a string (after trimming surrounding spaces) into a number. If that fails, it puts the `Atoi` error inside a `ParseError`, which also keeps the original input. `divide` takes two strings, parses both and divides. If parsing fails, it wraps the error with whether it was the "left" or "right" operand. If the divisor is zero, it wraps `ErrDivideByZero` together with the numbers.

`main` tries four inputs: `("84", "2")`, `("10", "0")`, `("abc", "2")` and `("7", " x1")`. For each error it prints the message and the results of `errors.Is` and `errors.As`. The output:

```text
result: 42
error: divide 10 by 0: divide by zero
  is ErrDivideByZero: true
  is strconv.ErrSyntax: false
  as *ParseError: no
error: divide: left operand: parse "abc": strconv.Atoi: parsing "abc": invalid syntax
  is ErrDivideByZero: false
  is strconv.ErrSyntax: true
  as *ParseError: input="abc"
error: divide: right operand: parse " x1": strconv.Atoi: parsing "x1": invalid syntax
  is ErrDivideByZero: false
  is strconv.ErrSyntax: true
  as *ParseError: input=" x1"
```

Let us read it input by input:

- **`84` and `2`:** no error, and the result 42 is printed.
- **`10` and `0`:** both numbers parse fine, but the divisor is zero. The message says `divide 10 by 0: divide by zero`. `errors.Is(err, ErrDivideByZero)` is true and `ErrSyntax` is not, and since there is no `ParseError` in the chain, `errors.As` answers "no".
- **`abc` and `2`:** read the message as a chain: each layer added context, from `divide: left operand` to `parse "abc"` to the text of `strconv`'s own error. This time `errors.Is(err, strconv.ErrSyntax)` is true even though we never mention it ourselves: the function walks down through our `ParseError` (thanks to `Unwrap`) to the error `strconv` returned. `errors.As` also found the `ParseError` and handed us the original input, `abc`.
- **`7` and ` x1`:** the same story, for the right operand. Notice that `ParseError` kept the original input with its leading space (`" x1"`), while `strconv` saw only `x1`, because `parse` trimmed the spaces before converting.

## defer

Now cleanup. Suppose a function opens a file and then has five different places where it can return early. In each of those five places you must remember to close the file. `defer` solves that: it schedules a call for the moment the function returns, however the function ends. The usual pattern is to write the release right next to where you acquired the resource:

```go
f, err := os.Open(path)
if err != nil {
	return err
}
defer f.Close()
```

You need to know two rules. First, deferred calls run in **LIFO** order: last registered, first run, like plates stacked on top of each other and taken from the top. Second, the arguments of a `defer` are evaluated at the moment of the `defer` statement itself, not when the call finally runs. This example shows both:

```go
func demoDefer() {
	for i := 1; i <= 3; i++ {
		defer fmt.Println("deferred", i)
	}
	x := 10
	defer fmt.Println("x at defer time:", x)
	x = 20
	fmt.Println("x now:", x)
}
```

```text
x now: 20
x at defer time: 10
deferred 3
deferred 2
deferred 1
```

Read the output from the top. The first line is `x now: 20`, because that is the only print that is not deferred and it runs immediately. After that, when the function ends, the deferred prints start, from the last registered to the first. The last `defer` is the one that prints `x`, and its value is `10`, not `20`: the argument `x` was copied at the moment the `defer` line ran, not when the print actually happened. After it come the three loop defers in reverse order: 3, 2, 1.

## A short word on panic and recover

Go has another kind of failure too: `panic`. A `panic` stops normal execution, runs the deferred functions and crashes the program, unless someone calls `recover` inside one of those deferred functions. For example, writing to a `nil` map causes a panic. In this example we use a named result to turn the panic into an ordinary error:

```go
func safeName() (name string, err error) {
	defer func() {
		if r := recover(); r != nil {
			err = fmt.Errorf("recovered: %v", r)
		}
	}()
	var m map[string]int
	m["a"] = 1
	return "ok", nil
}
// prints:  recovered: assignment to entry in nil map
```

The line `m["a"] = 1` writes to an empty map and panics. Before the program dies, the deferred function runs, `recover()` catches the panic message and stores it in `err`. Because `err` is a named result, the function returns exactly that. The real output of `fmt.Println(safeName())` was an empty string for `name` followed by the error message, which is the line above (the blank before "recovered" is the empty `name`).

For expected failures, such as bad input or a missing file, do not use panic; return an error. A panic is for bugs and impossible states. `recover` is mostly useful at boundaries, for example an HTTP server that does not want one broken request to bring down the whole program.

## Common traps with errors and defer

- **Do not ignore an error with `_`** unless you can say why it is safe. Writing `n, _ := strconv.Atoi(s)` means "if it fails I do not want to know", and you go on working with `0`.
- **If the caller might need `errors.Is` or `errors.As`, wrap with `%w`, not `%v`.** `%v` only puts the text of the error into the new message and drops the original error from the chain.
- **When wrapping is involved, compare errors with `errors.Is`, not `==`.** `==` sees only the value itself, not what is inside the wrap.
- **`defer` inside a loop runs at the end of the function, not at the end of each iteration.** If you open many files in a loop, they all stay open until the function ends. Move the loop body into a separate function.
- **The arguments of a deferred call are evaluated immediately**, as the `x` example showed. If you want the latest value, use a closure: `defer func() { ... }()`.

## Exercise

1. Add a sentinel `ErrNegative` to `divide` and return it (wrapped) when either operand is negative. Check it with `errors.Is`.
2. Write `func average(nums ...float64) (float64, error)` that returns an error for empty input.
3. Write a function with three `defer` statements that print; guess the output before you run it.

## What's next

"Slices, maps and strings in Go": the most used types in the language behave in ways that you cannot see from their appearance. That post shows how they really work and where beginners get surprised.
