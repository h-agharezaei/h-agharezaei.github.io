+++
date = '2026-11-10T10:00:00+03:30'
draft = false
title = 'Structs, methods and interfaces in Go'
description = 'How Go models data and behavior: structs, embedding, value vs pointer receivers, implicit interfaces, type switches, and the nil-interface gotcha.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "struct", "interface", "methods"]
cover = { image = "/images/covers/go-structs-methods-interfaces.png", alt = "Structs, methods and interfaces in Go", hiddenInSingle = true }
+++

Say you want to represent a "user" in your program: a name, an age, a few other things, and some actions you can take on a user. In a language with classes you would write a `class` and put both inside. Go has no classes, no inheritance and no `implements` keyword. Instead it has three simple pieces: **structs** for data, **methods** for behavior and **interfaces** for abstraction. Together they cover most of what classes do, and an interface is satisfied without any type naming it.

After [slices, maps and strings](/posts/go-slices-maps-strings/), which were the language's built-in types, it is time for our own types. We first look at structs and methods, then interfaces, and finally a famous trap that nearly everyone who learns Go falls into once.

> I ran every example in this post with Go 1.26, and the outputs are taken from the real runs.

## Structs, literals and zero values

A **struct** is a group of named fields, like a record or an object without behavior. You create an instance with a **literal**, and it is better to write the fields by name: it is more readable and your code does not break if the field order changes.

```go
type Address struct {
	City string
}

type User struct {
	Name  string
	Age   int
	Admin bool
	Address // embedded
}

u := User{Name: "Roham", Age: 30}
fmt.Printf("%+v\n", u)
var z User
fmt.Printf("zero: %+v\n", z)
```

```
{Name:Roham Age:30 Admin:false Address:{City:}}
zero: {Name: Age:0 Admin:false Address:{City:}}
```

(`%+v` in `Printf` means "print the struct with its field names".) In the first line we gave two fields a value and left the rest. The output shows that unset fields are not empty holes: `Admin` is `false` and `City` is an empty string. This is the **zero value** we saw in the types post, applied field by field to a struct. The second line shows that `var z User`, with no initialization at all, produces a complete, usable `User`. That is why Go types that are simple usually need no constructor.

## Embedding: composition instead of inheritance

Look at the `Address` line inside `User`: a type written without a field name is **embedded**. The fields and methods of that type are **promoted** to the outer type, as if they were its own. Here is how:

```go
func (a Address) Describe() string { return "city=" + a.City }

u.Address = Address{City: "Tehran"}
fmt.Println(u.City, u.Describe())
```

```
Tehran city=Tehran
```

(The first line defines a method; I explain its shape in the next section.) Although `City` and `Describe` are defined on `Address`, we called them directly on `u`. `User` is not a subtype of `Address`; it merely holds one and passes the call on to it. This is **composition**: you reuse behavior without building a hierarchy of types.

## Methods: value or pointer receivers

A **method** is a function attached to a type. Between the `func` keyword and the method name there is an extra parameter called the **receiver**, which says what the method works on. A receiver comes in two forms: **value** (a copy of the value) or **pointer** (the address of the value itself; the next post is entirely about pointers, and here we only need this much). The difference matters. We write two methods that do the same thing and differ only in the receiver type:

```go
type Counter struct{ N int }

func (c Counter) IncValue()    { c.N++ }
func (c *Counter) IncPointer() { c.N++ }

c := Counter{}
c.IncValue()
fmt.Println("after IncValue:", c.N)
c.IncPointer()
fmt.Println("after IncPointer:", c.N)
```

```
after IncValue: 0
after IncPointer: 1
```

Both methods add one to `N`. Yet after `IncValue`, `N` is still 0, and after `IncPointer` it is 1. The reason is that a value receiver works on a **copy** of the struct, so its change disappears when the method returns. A pointer receiver reaches the struct itself. The conclusion: use a pointer receiver when the method must change the struct, or when the struct is big and you do not want it copied on every call. For consistency, if one method of a type needs a pointer receiver, make the others pointer receivers too.

## Interfaces are satisfied implicitly

Now to the most important idea. An **interface** is a set of method signatures, in other words "anything that can do these things". And in Go you never write "this type implements that interface". Any type that has the required methods satisfies the interface automatically.

The example is geometric shapes. We want the total area of several shapes without the function knowing what types they are:

```go
type Shape interface {
	Area() float64
}

type Rect struct{ W, H float64 }
type Circle struct{ R float64 }

func (r Rect) Area() float64   { return r.W * r.H }
func (c Circle) Area() float64 { return math.Pi * c.R * c.R }

func TotalArea(shapes []Shape) float64 {
	var t float64
	for _, s := range shapes {
		t += s.Area()
	}
	return t
}

shapes := []Shape{Rect{W: 3, H: 4}, Circle{R: 1}}
fmt.Printf("total: %.2f\n", TotalArea(shapes))
```

```
total: 15.14
```

`Shape` has a single requirement: a method named `Area` that returns a `float64`. `Rect` and `Circle` never mention `Shape`, but both have `Area()`, so both are `Shape`s and we can put them side by side in a slice of `Shape`. `TotalArea` just calls `Area()`. The answer is right: the area of a 3 by 4 rectangle is 12 and a circle with radius 1 has area π, about 3.14; together 15.14. The design point is that the consumer defines the interface it needs, and any type that fits is accepted, without the types depending on it.

The most used standard interface is `fmt.Stringer`, with the method `String() string`. If a type has it, `fmt` uses it when printing:

```go
func (r Rect) String() string { return fmt.Sprintf("Rect(%gx%g)", r.W, r.H) }

fmt.Println(shapes[0]) // Rect(3x4)
fmt.Println(Circle{R: 2}) // {2}, no String method
```

```
Rect(3x4)
{2}
```

`Rect` has a `String` method, so it prints as `Rect(3x4)`. `Circle` has none, and `fmt` falls back to the default and prints just its field: `{2}`.

## `any`, type assertions and type switches

Sometimes a function must accept a value of any type. For that we have `any`, another name for the empty interface (`interface{}`). It demands no methods, so every type satisfies it. The catch is that once you have a value inside an interface, you no longer know its real type. Two tools get the original type back: a **type assertion** (you ask "is this an X?") and a **type switch** (you try several types in a row).

```go
var s Shape = Rect{2, 5}
if r, ok := s.(Rect); ok {
	fmt.Println("is Rect:", r.W, r.H)
}
_, ok := s.(Circle)
fmt.Println("is Circle:", ok)

func describe(v any) string {
	switch x := v.(type) {
	case int:
		return fmt.Sprintf("int %d", x)
	case string:
		return "string " + x
	case Shape:
		return fmt.Sprintf("shape with area %.1f", x.Area())
	default:
		return fmt.Sprintf("unknown %T", x)
	}
}

fmt.Println(describe(42))
fmt.Println(describe("hi"))
fmt.Println(describe(Circle{R: 1}))
fmt.Println(describe(3.5))
```

```
is Rect: 2 5
is Circle: false
int 42
string hi
shape with area 3.1
unknown float64
```

The first two lines: `s` is really a `Rect`, so `s.(Rect)` succeeds and `r` is the original rectangle with its fields. `s.(Circle)` fails and `ok` is `false`. The last four lines are the four `describe` calls in order: the number 42 reaches the `int` case, `"hi"` the `string` case, a circle of radius 1 reaches `Shape` because it has an `Area` method (its area is 3.1 with one decimal), and 3.5 matches none and goes to `default`, which prints its type with `%T`: `float64`.

Always use the two-value form (`v, ok := ...`) unless you really want a panic when the type does not match.

## The nil trap in interfaces

Now the trap I promised at the start. An interface value actually holds two things: a type and a value. Picture a box with a type label and a content. An interface is `nil` only when both are empty, the label and the content. Now if you return a pointer that is `nil` through an interface, the type label gets filled in and the box no longer counts as empty, even though its content is `nil`:

```go
type MyErr struct{}

func (*MyErr) Error() string { return "my error" }

func bad() error {
	var p *MyErr = nil
	return p
}

func good() error { return nil }

fmt.Println("bad() == nil:", bad() == nil)
fmt.Println("good() == nil:", good() == nil)
```

```
bad() == nil: false
good() == nil: true
```

`bad()` returns a `*MyErr` pointer whose value is `nil` as an `error`. The output shows the result is not equal to `nil`. So `if err != nil` in the caller of `bad()` is true and the program thinks an error happened, while nobody had an error. `good()` returns `nil` directly and everything is right. The fix is simple: on the success path return `nil` directly.

## Accept interfaces, return structs

A common rule in Go is that functions take interfaces and return concrete types (structs). Taking an interface keeps a function flexible and easy to test, because the caller can pass any type with the needed methods, even a fake made for testing. Returning a concrete struct gives the caller all its fields and methods and leaves it to choose which interface to view it through. Keep interfaces small (one or two methods) and define them in the package that uses them, not the package that implements them.

## Exported and unexported

In Go, capitalization is the access control. `User`, `Name` and `Describe` start with an uppercase letter, so other packages can use them (these are called exported). `user`, `name` and `describe` start with lowercase and are visible only inside their own package. There is no `public` or `private` keyword.

## Common mistakes with receivers and interfaces

- **A plain value does not have the pointer-receiver methods.** If `Inc` has a pointer receiver, `var i Incer = C{}` does not compile. I tried exactly this and the compiler said: `C does not implement Incer (method Inc has pointer receiver)`. Use `&C{}` instead.
- **Never return a typed-nil pointer as an `error` or another interface.** It is the trap above. Return `nil` directly.
- **Do not reach for `any` out of habit.** `any` gives up compile-time type checking; a small interface is better.
- **Embedding promotes methods but is not inheritance.** The outer type does not become an `Address`, and it is not accepted where an `Address` is expected.
- **Mixing value and pointer receivers on one type is confusing.** Pick one.

## Exercise

1. Add a method `Perimeter() float64` to `Rect` and `Circle`, extend `Shape`, and print the total perimeter.
2. Define an interface `Notifier` with a method `Send(msg string) error`, write two structs `EmailNotifier` and `SMSNotifier`, and write a function that takes a `Notifier`.
3. Write your own version of the interface nil trap, then fix it.

## What's next

"Pointers and the memory model in Go": here I talked about "copies" and "pointers" only as far as needed; that post shows what really happens.
