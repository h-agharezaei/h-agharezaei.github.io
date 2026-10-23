+++
date = '2026-11-10T10:00:00+03:30'
draft = false
title = 'Structs, methods and interfaces in Go'
description = 'How Go models data and behavior: structs, embedding, value vs pointer receivers, implicit interfaces, type switches, and the nil-interface gotcha.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "struct", "interface", "methods"]
cover = { image = "/images/covers/go-structs-methods-interfaces.png", alt = "Structs, methods and interfaces in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-slices-maps-strings/) we looked at slices, maps and strings. Now we need a way to group data and attach behavior to it. Go has no classes and no inheritance. It has **structs** for data, **methods** for behavior, and **interfaces** for abstraction, and these three small pieces cover most of what you would use classes for.

> I ran every example in this post with Go 1.26. The outputs are copied from the real run.

## Structs, literals and zero values

A **struct** is a collection of named fields. Prefer literals with named fields: they survive field reordering and make the code readable.

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

Every field you do not set gets its **zero value**. A struct is usable the moment it is declared, which is why Go code rarely needs constructors for simple types.

## Embedding: composition instead of inheritance

Look at the `Address` line in `User`: a type with no field name is **embedded**. Its fields and methods are **promoted** to the outer type.

```go
func (a Address) Describe() string { return "city=" + a.City }

u.Address = Address{City: "Tehran"}
fmt.Println(u.City, u.Describe())
```

```
Tehran city=Tehran
```

`User` is not a subtype of `Address`. It just contains one and forwards to it. This is composition: you reuse behavior without building a type hierarchy.

## Methods: value vs pointer receivers

A method is a function with a receiver. The receiver can be a value or a pointer, and the difference matters:

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

A value receiver works on a copy, so the change is lost. Use a pointer receiver when the method must mutate the struct, or when the struct is large. For consistency, if one method needs a pointer receiver, give them all pointer receivers. We will see why pointers behave this way in the next post.

## Interfaces are satisfied implicitly

An **interface** is a set of method signatures. There is no `implements` keyword: any type that has the methods satisfies the interface.

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

`Rect` and `Circle` never mention `Shape`. The consumer defines the interface it needs, and any type that fits is accepted.

`fmt.Stringer` is the most common standard interface: `String() string`. If you add it, `fmt` uses it when printing.

```go
func (r Rect) String() string { return fmt.Sprintf("Rect(%gx%g)", r.W, r.H) }

fmt.Println(shapes[0]) // Rect(3x4)
fmt.Println(Circle{R: 2}) // {2}, no String method
```

```
Rect(3x4)
{2}
```

## `any`, type assertions and type switches

`any` is an alias for the empty interface `interface{}`: every type satisfies it. To get the concrete value back, use a **type assertion** or a **type switch**.

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
```

```
is Rect: 2 5
is Circle: false
int 42
string hi
shape with area 3.1
unknown float64
```

Always use the two-value form (`v, ok := ...`) unless you want a panic on mismatch.

## The nil interface gotcha

An interface value holds a (type, value) pair. It is `nil` only when both are empty. Returning a nil pointer through an interface gives you a non-nil interface:

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

So `if err != nil` is true for `bad()` even though the pointer inside is nil. The fix: return a literal `nil` on the success path.

## Accept interfaces, return structs

A common guideline: functions should accept interfaces and return concrete types. Accepting an interface keeps the function flexible and easy to test, since callers can pass any type with the needed methods, including a fake. Returning a concrete struct gives callers the full type with all its fields and methods, and lets them decide which interface to treat it as. Define small interfaces (one or two methods) in the package that uses them, not the package that implements them.

## Exported vs unexported

Capitalization is visibility. `User`, `Name` and `Describe` start with an uppercase letter, so other packages can use them. `user`, `name` or `describe` are visible only inside the same package. There is no `public` or `private` keyword.

## A few things to watch

- A value type does not get the pointer-receiver methods in an interface. I tried `var i Incer = C{}` where `Inc` has a pointer receiver, and the compiler said: `C does not implement Incer (method Inc has pointer receiver)`. Use `&C{}`.
- Never return a typed nil pointer as an `error` or other interface. Return `nil` directly.
- Do not reach for `any` out of habit. It throws away type checking; prefer a small interface.
- Embedding promotes methods, but it is not inheritance: the outer type does not become an `Address`.
- Mixing value and pointer receivers on one type is confusing. Pick one.

## Exercise

1. Add a `Perimeter() float64` method to `Rect` and `Circle`, extend `Shape`, and print the total perimeter.
2. Make a `Notifier` interface with `Send(msg string) error`, and write `EmailNotifier` and `SMSNotifier` structs. Write one function that accepts a `Notifier`.
3. Write your own version of the nil-interface gotcha, then fix it.

## What's next

So far I kept saying "copy" and "pointer" without explaining them properly. In the next post, pointers and the memory model in Go, we will look at what really happens.
