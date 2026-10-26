+++
date = '2026-11-04T10:00:00+03:30'
draft = false
title = 'Functions, defer and error handling in Go'
description = 'Go functions with multiple returns, variadics and closures, plus the error interface, %w wrapping, errors.Is/As, defer and why panic is not for errors.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "functions", "errors", "defer"]
cover = { image = "/images/covers/go-functions-defer-errors.png", alt = "Functions, defer and error handling in Go", hiddenInSingle = true }
+++

In the [previous post](/posts/go-types-control-flow/) we covered types, variables and control flow. Now we get to the part that shapes most Go code you will ever read: functions and error handling. Go has no exceptions. Functions return errors as ordinary values, and `defer` takes care of cleanup. Once this clicks, a lot of Go's style makes sense.

> I ran every example below with Go 1.26. The outputs are copied from those runs.

## Functions and multiple return values

A function declares its parameter types after the names, and it can return more than one value:

```go
func divmod(a, b int) (int, int) { return a / b, a % b }

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

`sum` is **variadic**: inside, `nums` is a `[]int`. You can call it with no arguments, with several, or pass an existing slice with `...`. Functions are also values. `counter` returns a **closure** that keeps its own `n` alive between calls.

```go
q, r := divmod(17, 5)
fmt.Println(q, r)                                   // 3 2
fmt.Println(sum(), sum(1, 2, 3), sum([]int{4, 5}...)) // 0 6 9
next := counter()
fmt.Println(next(), next(), next())                 // 1 2 3
```

Return values can be **named** (`func f() (n int, err error)`). They start as zero values and a bare `return` returns them. That is handy with `defer` (see below), but a bare `return` in a long function makes readers hunt for where the values were set. I only use named returns for short functions or when a deferred function needs to change the result.

## The error interface

`error` is just an interface with one method, `Error() string`. By convention the error is the last return value, and the caller checks it right away:

```go
n, err := strconv.Atoi(s)
if err != nil {
	return 0, err
}
```

You will write `if err != nil` a lot. That is intentional: the failure path is visible in the code.

## Creating, wrapping and inspecting errors

`errors.New` creates a simple error. `fmt.Errorf` with the `%w` verb **wraps** another error, adding context while keeping the original reachable. Then `errors.Is` checks whether a specific error is anywhere in the chain, and `errors.As` finds an error of a specific type and gives it to you.

Here is the small program I ran. It has a **sentinel error** (a package-level value you compare against) and a custom error type with `Unwrap`:

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

`main` runs four inputs and, for each error, prints the message and the results of `errors.Is` and `errors.As`:

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

Notice that the printed message reads like a chain, each layer adding context. And `errors.Is(err, strconv.ErrSyntax)` is true even though we never mentioned it: it walks through our `ParseError` (thanks to `Unwrap`) down to what `strconv` returned.

## defer

`defer` schedules a call to run when the surrounding function returns. It is the idiomatic way to release resources right next to where you acquire them:

```go
f, err := os.Open(path)
if err != nil {
	return err
}
defer f.Close()
```

Two rules matter. Deferred calls run in **LIFO** order, and the arguments are evaluated at the `defer` statement, not when the call finally runs:

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

## panic and recover, briefly

`panic` stops normal execution, runs deferred calls, and crashes the program unless something calls `recover` inside a deferred function. For example, writing to a nil map panics, and a named result lets us turn that into an error:

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

Do not use panic for expected failures like bad input or a missing file. Return an error instead. Panic is for bugs and impossible states, and `recover` is mostly for boundaries such as an HTTP server protecting itself from one bad request.

## A few things to watch

- Never ignore an error with `_` unless you can say why it is safe.
- Wrap with `%w`, not `%v`, if callers may need `errors.Is` or `errors.As`. `%v` only keeps the text.
- Compare errors with `errors.Is`, not `==`, once wrapping is involved.
- `defer` inside a loop runs at the end of the function, not each iteration. Move the body into its own function if you open many files.
- Arguments of a deferred call are evaluated immediately. Use a closure (`defer func() { ... }()`) if you need the latest value.

## Exercise

1. Add a `ErrNegative` sentinel to `divide` and return it (wrapped) when either operand is negative. Check it with `errors.Is`.
2. Write `func average(nums ...float64) (float64, error)` that returns an error for empty input.
3. Write a function that defers three prints and predict the output before running it.

## What's next

In the next post we look at slices, maps and strings in Go: how they actually work and the traps that catch beginners.
