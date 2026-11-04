+++
date = '2026-10-31T10:00:00+03:30'
draft = false
title = 'Types, variables and control flow in Go'
description = "Variables, zero values, basic types, constants with iota, explicit conversion, and Go's if, for and switch, all with real runnable examples."
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "types", "control-flow"]
cover = { image = "/images/covers/go-types-control-flow.png", alt = "Types, variables and control flow in Go", hiddenInSingle = true }
+++

Say you have 3 items at 2.5 each and you want the total. In most languages you write `count * price` and get 7.5. In Go that single line does not compile. Go will not guess whether you mean integer or floating-point arithmetic. It wants you to write that decision down.

The same strictness runs through the rest of the basics. Every variable has a defined starting value, an unused variable is a compile error, and there is only one loop, `for`. Go has fewer of these building blocks than most languages, and that is on purpose: when there is one way to do each thing, other people's code is easier to read. If you have not installed Go yet, start with [Getting started with Go](/posts/go-getting-started/).

> Everything below was run with Go 1.26.0 on macOS, and the outputs are taken from those runs.

## var and :=

There are two ways to declare a variable:

```go
var count int = 3   // explicit
var name = "Roham"  // type inferred from the value
price := 2.5        // short form, only inside functions
```

The first line states the type explicitly. In the second, Go works out the type from the value (this is called **type inference**): `"Roham"` is a string, so `name` is a `string`. The third is the short form: `:=` declares the variable and gives it a value in one step. Inside functions you will write this almost every time. Outside functions, at package level, only `var` works.

Remember one rule from the start: an unused local variable is a compile error, not a warning.

## Zero values

In some languages (C, for example) a variable that was never given a value may hold random leftovers from memory. Go has nothing like that. A variable declared without a value gets the **zero value** of its type: zero for numbers, the empty string for `string`, `false` for `bool`, and `nil` (meaning "nothing") for pointers, slices and maps.

To see it, we declare one variable of each kind and print them without ever assigning anything:

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

In `Printf`, `%v` means "print the value in its default form", `%q` means "print the string in quotes" (that is why the empty string shows as `""` and we can tell it is really empty), and `%t` is for `bool`. The output shows that each type has its own zero value. The last two lines are the interesting ones: an unassigned slice and map are `nil`, yet their length is zero and they print like empty values.

This removes a whole class of bugs, because no variable is ever "undefined". One practical point: a `nil` slice is already usable (`len` and `append` both work on it), so you rarely need to initialize it by hand. A map is different, and we come back to it in the traps section.

## Basic types

Let us go through the types you will see most often:

- **Integers:** `int` and `uint` (unsigned) match the size of your platform, 64 bits on mine. There are also sized types such as `int8`, `int32` and `int64`. Use plain `int` unless you have a reason not to.
- **Floats:** `float64` is the default. `float32` exists but you will rarely need it.
- **`string`:** an immutable sequence of bytes, usually UTF-8 encoded. Two aliases matter: `byte` is another name for `uint8`, and `rune` is another name for `int32`, which holds one Unicode code point, that is, one "character".

The difference between bytes and runes stays invisible while you write only English. It matters as soon as you leave ASCII. Look at this:

```go
s := "سلام"
fmt.Println(len(s), len([]rune(s)))   // 8 4

for i, r := range "hé" {
    fmt.Println(i, r, string(r))
}
// 0 104 h
// 1 233 é

fmt.Println([]byte("hé"))
// [104 195 169]
```

On the first line `len(s)` counts bytes and gives 8, yet `"سلام"` has four letters. Each Persian letter takes two bytes in UTF-8. If we convert the string to `[]rune`, each element is one character, and `len` gives 4.

A `range` loop over a string walks it rune by rune. On each round it gives two things: the position where that rune starts in the string (in bytes) and the rune itself. In `"hé"`, `h` is one byte and starts at position 0, and `é` starts at position 1. The Unicode value of `h` is 104 and of `é` is 233. The last line shows why: `[]byte("hé")` has three bytes, one for `h` and two for `é`. So `len("hé")` is 3, not 2.

## Constants and iota

Constants are declared with `const` and do not change after that. When you have several related values, such as the days of the week, typing the numbers by hand is tedious and easy to get wrong. For this Go has **iota**: a counter that starts at 0 in each `const` block and increases by one on every line. If you write nothing on the following lines, Go repeats the expression from the line above:

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

In the first block `Sunday` is 0, `Monday` is 1 and `Tuesday` is 2. In the second block, the first line throws away the 0 with `_`. Then `KB` is `1 << (10 * 1)`, that is 1 shifted left by 10 bits (1024). `MB` repeats the same expression with iota equal to 2 (`1 << 20`) and `GB` with 3 (`1 << 30`). Printing `Sunday, Monday, Tuesday` gives `0 1 2`, and `KB, MB, GB` gives `1024 1048576 1073741824`.

## No implicit conversion

Back to the example we started with. Go never converts between numeric types for you. If you want to mix an `int` and a `float64`, you write the conversion yourself:

```go
count := 3
price := 2.5
fmt.Println(float64(count) * price)  // 7.5
fmt.Println(count * price)
```

The first line converts `count` to `float64` first, then multiplies, and 7.5 is printed. The second line does not compile. This is the exact error `go run` gave:

```text
./main.go:9:14: invalid operation: count * price (mismatched types int and float64)
```

The message is clear: "mismatched types `int` and `float64`". It feels strict at first, but it stops silent precision bugs, because every place where a type changes is visible in the code.

The same rule applies to types you define yourself. If you declare `Celsius` and `Fahrenheit`, both based on `float64`, adding them is a compile error too (the real error: `invalid operation: c + f (mismatched types Celsius and Fahrenheit)`). That is exactly what you want: it does not let you add Celsius to Fahrenheit by accident.

## if, for and switch

After declaring data comes deciding and repeating. Start with `if`. One thing is different in Go: `if` can run a small statement before the condition (an **init statement**), and the variable you create there lives only inside that `if`/`else` chain:

```go
if n, err := strconv.Atoi("42x"); err != nil {
    fmt.Println("error:", err)
} else {
    fmt.Println(n)
}
// error: strconv.Atoi: parsing "42x": invalid syntax
```

`strconv.Atoi` converts a string to a number and returns two things: the number and an `err`. If the conversion fails, `err` is filled in and not `nil`. (I explain returning several values and `error` in the next post.) Since `"42x"` is not a valid number, the `err != nil` branch runs and the error message is printed. The point is that `n` and `err` do not exist after the `if`, so they do not clutter your scope.

Now loops. `for` is Go's only loop, but it has a few forms:

```go
for i := 0; i < 3; i++ { }          // classic
for n < 3 { n++ }                    // like while
for { if done { break } }            // infinite
for i, v := range []string{"a", "b"} { }  // range
for i := range 3 { }                 // 0 1 2 (Go 1.22+)
```

The first is the three-part `for` you know from other languages. With only a condition, `for` does the job of `while`. With nothing at all, it is an infinite loop that ends with `break`. `range` over a slice gives the index and value of each element, and `range` over a number, from Go 1.22 on, counts from zero up to one less than that number.

A `switch` in Go does not fall through to the next case. Only the matching case runs, and no `break` is needed. If you really want execution to continue into the next case, you write `fallthrough` explicitly. A case can list several values, like `case 1, 2:`. Instead of a long `if/else if` chain you can write a tagless `switch` (the same as `switch true`) where each case is a condition; the next section has an example.

`break` and `continue` work as usual. For nested loops, put a **label** in front of the outer loop and refer to it by name: `continue outer` or `break outer`.

## Putting it together

Now a few things at once: a temperature table with a loop, a conversion and a tagless `switch`. It converts each temperature from Celsius to Fahrenheit and puts a label next to it:

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

The loop starts at -10 and moves 10 degrees at a time until it reaches 40. For the Fahrenheit formula we first convert `c` to `float64`, the "no implicit conversion" rule again. The tagless `switch` tries the conditions from top to bottom and runs the first true one; that is why 10 gets the label `cool` (`c < 0` is false and `c < 20` is true). In `Printf`, `%4d` means an integer in a width of 4 characters and `%6.1f` means a float in a width of 6 with one decimal place; that is why the columns line up.

## Common traps

- **`:=` inside an inner block creates a new variable** and hides the outer one (this is called shadowing). For example, if there is a `total` outside an `if` and you write `total := 99` inside it, you see 99 inside the `if`, but outside it the old value (10) is still there. This is the classic source of bugs that start with "why is my value unchanged". I ran this example separately, and the output was `inside: 99` and `outside: 10`.
- **A nil map can be read, but writing to it panics.** Reading a missing key from a nil map returns `0`, but writing stops the program with the message `assignment to entry in nil map`. Create the map first with `make(map[string]int)`.
- **`len(s)` on a string counts bytes, not characters.** For non-English text use `[]rune` or `range`.
- **Unused variables and imports are compile errors.** If you are not using a variable yet while experimenting, you have to delete it or use it.
- **`fallthrough` jumps into the next case without checking its condition.** After `fallthrough` the body of the next case runs even if its condition does not hold.

## Exercise

1. Write a program that prints 1 to 30, but "Fizz" for multiples of 3, "Buzz" for 5 and "FizzBuzz" for both, using a tagless `switch`.
2. Define `Celsius` and `Fahrenheit` as separate types based on `float64` and try adding them together. Read the compiler error.
3. Declare a `Level` type with `iota` constants `Debug`, `Info`, `Warn`, and print each one.

## What's next

Functions, `defer` and error handling: in this post we saw `strconv.Atoi` return a number and an `err` together. That post shows how this pattern, returning errors instead of throwing exceptions, shapes the whole Go style.
