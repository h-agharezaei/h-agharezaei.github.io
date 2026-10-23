+++
date = '2026-10-31T10:00:00+03:30'
draft = false
title = 'Types, variables and control flow in Go'
description = "Variables, zero values, basic types, constants with iota, explicit conversion, and Go's if, for and switch, all with real runnable examples."
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/go-types-control-flow.png", alt = "Types, variables and control flow in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-getting-started/) we installed Go, created a module and ran our first program. Now we need the building blocks every program uses: variables, types and control flow. Go has far fewer of them than most languages, and that is on purpose.

> Everything below was run with Go 1.26.0 on macOS, and the outputs are copied from those runs.

## var and :=

There are two ways to declare a variable:

```go
var count int = 3   // explicit
var name = "Roham"  // type inferred
price := 2.5        // short form, only inside functions
```

`:=` declares and assigns in one step, and it is what you will write 90% of the time inside functions. At package level you must use `var`. An unused local variable is a compile error, not a warning.

## Zero values

A variable you declare without a value is never "uninitialized". It gets the **zero value** of its type:

```go
var i int
var s string
var b bool
var f float64
var p *int
var sl []int
var m map[string]int

fmt.Printf("int:     %v\n", i)
fmt.Printf("string:  %q\n", s)
fmt.Printf("bool:    %v\n", b)
fmt.Printf("float64: %v\n", f)
fmt.Printf("pointer: %v\n", p)
fmt.Printf("slice:   %v (nil: %t, len: %d)\n", sl, sl == nil, len(sl))
fmt.Printf("map:     %v (nil: %t, len: %d)\n", m, m == nil, len(m))
```

```text
int:     0
string:  ""
bool:    false
float64: 0
pointer: <nil>
slice:   [] (nil: true, len: 0)
map:     map[] (nil: true, len: 0)
```

This removes a whole class of bugs. A nil slice is already usable (`len` works, and `append` works too), so you rarely need to initialize it.

## Basic types

- Integers: `int` and `uint` (the size of your platform, 64 bits on mine), plus sized ones like `int8`, `int32`, `int64`. Use plain `int` unless you have a reason not to.
- Floats: `float64` is the default; `float32` exists but you will rarely need it.
- `string` is an immutable sequence of bytes, usually UTF-8. `byte` is an alias for `uint8`, and `rune` is an alias for `int32` that holds one Unicode code point.

The difference between bytes and runes matters as soon as you leave ASCII:

```go
s := "سلام"
fmt.Println(len(s), len([]rune(s)))   // 8 4

for i, r := range "hé" {
    fmt.Println(i, r, string(r))
}
// 0 104 h
// 1 233 é
```

`len` counts bytes (8 here), while converting to `[]rune` counts characters (4). Ranging over a string walks runes, and the index jumps by the byte width.

## Constants and iota

Constants use `const`. For related values, **iota** is a counter that starts at 0 in each `const` block and increments per line:

```go
type Weekday int

const (
    Sunday Weekday = iota
    Monday
    Tuesday
)

const (
    _  = iota
    KB = 1 << (10 * iota)
    MB
    GB
)
```

Printing `Sunday, Monday, Tuesday` gives `0 1 2`, and `KB, MB, GB` gives `1024 1048576 1073741824`.

## No implicit conversion

Go never converts between numeric types for you. You write the conversion yourself:

```go
count := 3
price := 2.5
fmt.Println(float64(count) * price)  // 7.5
fmt.Println(count * price)
```

The last line does not compile. This is the exact error from `go run`:

```text
./main.go:9:14: invalid operation: count * price (mismatched types int and float64)
```

It feels strict at first, but it stops silent precision bugs.

## if, for and switch

`if` can have an init statement, and the variable lives only inside the `if`/`else` chain:

```go
if n, err := strconv.Atoi("42x"); err != nil {
    fmt.Println("error:", err)
} else {
    fmt.Println(n)
}
// error: strconv.Atoi: parsing "42x": invalid syntax
```

`for` is the only loop, in a few forms:

```go
for i := 0; i < 3; i++ { }          // classic
for n < 3 { n++ }                    // like while
for { if done { break } }            // infinite
for i, v := range []string{"a", "b"} { }  // range
for i := range 3 { }                 // 0 1 2 (Go 1.22+)
```

`switch` does not fall through: only the matching case runs, with no `break` needed. Use `fallthrough` explicitly if you really want it, and use a tagless `switch` (the same as `switch true`) instead of long `if/else if` chains. A case can list several values, like `case 1, 2:`.

`break` and `continue` work as usual. For nested loops, put a label in front of the outer loop and name it: `continue outer` or `break outer`.

## Putting it together

A small temperature table that uses a loop, conversion and a tagless switch:

```go
for c := -10; c <= 40; c += 10 {
    f := float64(c)*9/5 + 32

    var label string
    switch {
    case c < 0:
        label = "freezing"
    case c < 20:
        label = "cool"
    case c < 30:
        label = "warm"
    default:
        label = "hot"
    }
    fmt.Printf("%4d C = %6.1f F  %s\n", c, f, label)
}
```

```text
 -10 C =   14.0 F  freezing
   0 C =   32.0 F  cool
  10 C =   50.0 F  cool
  20 C =   68.0 F  warm
  30 C =   86.0 F  hot
  40 C =  104.0 F  hot
```

## A few things to watch

- `:=` inside an inner block creates a new variable and shadows the outer one. This is a classic source of "why is my value unchanged" bugs.
- A nil map can be read but writing to it panics; create it with `make(map[string]int)` first.
- `len(s)` on a string is bytes, not characters.
- Unused variables and imports are compile errors.
- `fallthrough` jumps into the next case without checking its condition.

## Exercise

1. Write a program that prints 1 to 30, but "Fizz" for multiples of 3, "Buzz" for 5 and "FizzBuzz" for both, using a tagless `switch`.
2. Define `Celsius` and `Fahrenheit` as separate types based on `float64` and try adding them together. Read the compiler error.
3. Declare a `Level` type with `iota` constants `Debug`, `Info`, `Warn`, and print each one.

## What's next

In the next post we cover functions, `defer` and error handling in Go, which is where Go's most recognizable style shows up.
