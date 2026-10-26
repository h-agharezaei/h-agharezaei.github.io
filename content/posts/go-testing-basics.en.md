+++
date = '2026-12-04T10:00:00+03:30'
draft = false
title = 'Testing in Go: table-driven tests and benchmarks'
description = 'Go testing basics: go test flags, table-driven tests with subtests, helpers, coverage, benchmarks with b.Loop and a short look at fuzzing.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "testing", "benchmark"]
cover = { image = "/images/covers/go-testing-basics.png", alt = "Testing in Go: table-driven tests and benchmarks", hiddenInSingle = true }
+++

In the [previous post](/posts/go-generics/) we looked at generics. This time we cover something you will use every day: testing. Go ships a test runner and a benchmark tool in the standard library, so there is nothing to install and no framework to pick. By the end you will know how to write table-driven tests, run a single subtest, measure coverage, and compare two implementations with a benchmark.

> I ran everything below with Go 1.26 on an arm64 Mac (Apple M1). The outputs are copied from those runs.

## The basics

Tests live in files ending in `_test.go`, usually next to the code. A test is a function named `TestXxx` that takes a `*testing.T`. Here is a small package to test:

```go
package calc

var ErrDivideByZero = errors.New("divide by zero")

func Divide(a, b int) (int, error) {
	if b == 0 {
		return 0, fmt.Errorf("divide %d by %d: %w", a, b, ErrDivideByZero)
	}
	return a / b, nil
}
```

And its tests:

```go
func TestDivide(t *testing.T) {
	got, err := Divide(10, 2)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got != 5 {
		t.Errorf("Divide(10, 2) = %d, want 5", got)
	}
}

func TestDivideByZero(t *testing.T) {
	_, err := Divide(1, 0)
	if !errors.Is(err, ErrDivideByZero) {
		t.Fatalf("err = %v, want ErrDivideByZero", err)
	}
}
```

The difference between `t.Error` and `t.Fatal`: both mark the test as failed, but `Fatal` stops the test immediately, while `Error` lets it continue. Use `Fatal` when continuing makes no sense (for example, the `err` check above: if there is an error, `got` is meaningless). The second test also reuses `errors.Is` from the [errors post](/posts/go-functions-defer-errors/): since `Divide` wraps with `%w`, comparing with `==` would fail.

Run the tests with `go test`. I use `-v` for verbose output and `-count=1` to bypass the test cache, which otherwise skips tests whose code has not changed. `-run` takes a regular expression to select tests by name.

## A failing test

A passing test teaches little, so here is a deliberately broken one (in its own folder in my demo):

```go
func add(a, b int) int { return a - b } // bug

func TestAdd(t *testing.T) {
	if got := add(2, 3); got != 5 {
		t.Errorf("add(2, 3) = %d, want 5", got)
	}
}
```

```text
--- FAIL: TestAdd (0.00s)
    b_test.go:9: add(2, 3) = -1, want 5
FAIL
FAIL	example.com/brokentest	0.298s
FAIL
```

The convention `got ..., want ...` makes the message readable without opening the code. Note that the exit code is non-zero, which is what CI relies on.

## Table-driven tests and subtests

When you have many cases for the same function, repeating the test body is noisy. Go's idiom is a slice of cases and a loop, with `t.Run` creating a named **subtest** for each one. I also pulled the comparison into a helper that calls `t.Helper()`, so a failure is reported at the caller's line instead of inside the helper:

```go
func Slug(s string) string {
	return strings.Join(strings.Fields(strings.ToLower(s)), "-")
}

func assertSlug(t *testing.T, in, want string) {
	t.Helper()
	if got := Slug(in); got != want {
		t.Errorf("Slug(%q) = %q, want %q", in, got, want)
	}
}

func TestSlug(t *testing.T) {
	tests := []struct {
		name string
		in   string
		want string
	}{
		{"simple", "Hello World", "hello-world"},
		{"extra spaces", "  Go   is fun ", "go-is-fun"},
		{"empty", "", ""},
		{"single", "Go", "go"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			t.Parallel()
			assertSlug(t, tt.in, tt.want)
		})
	}
}
```

Adding a case is one line. Spaces in subtest names become underscores. To run only one subtest, use a slash in `-run`:

```text
$ go test -v -count=1 -run 'TestSlug/extra' .
=== RUN   TestSlug
=== RUN   TestSlug/extra_spaces
=== PAUSE TestSlug/extra_spaces
=== CONT  TestSlug/extra_spaces
--- PASS: TestSlug (0.00s)
    --- PASS: TestSlug/extra_spaces (0.00s)
PASS
```

`t.Parallel()` is what produced the `PAUSE` and `CONT` lines: it lets the subtests run concurrently with each other. Since Go 1.22 each loop iteration has its own `tt`, so the closure is safe. Use it only for tests that do not share mutable state.

## Coverage

```text
$ go test -count=1 -cover .
ok  	example.com/testing-basics	0.249s	coverage: 100.0% of statements
```

That is 100% for this tiny package. Coverage tells you which lines never ran, not whether your assertions are good, so treat it as a way to find untested code and not as a goal.

## Benchmarks

A benchmark is a function named `BenchmarkXxx` that takes a `*testing.B`. Since Go 1.24 you write the loop with `b.Loop()`; I confirmed it compiles and runs on 1.26. Let us compare two ways to join strings:

```go
func ConcatPlus(parts []string) string {
	s := ""
	for _, p := range parts {
		s += p
	}
	return s
}

func ConcatBuilder(parts []string) string {
	var sb strings.Builder
	for _, p := range parts {
		sb.WriteString(p)
	}
	return sb.String()
}

func BenchmarkConcatPlus(b *testing.B) {
	for b.Loop() {
		ConcatPlus(parts)
	}
}
```

(`BenchmarkConcatBuilder` is identical with the other function, and `parts` is a package-level slice of 1001 short strings. A normal test checks that both functions return the same result.) Run with `-run xxx` to skip the regular tests, `-bench .` for all benchmarks, and `-benchmem` for allocations:

```text
$ go test -count=1 -run xxx -bench . -benchmem .
goos: darwin
goarch: arm64
cpu: Apple M1
BenchmarkConcatPlus-8      	   10000	    110425 ns/op	 1063869 B/op	     999 allocs/op
BenchmarkConcatBuilder-8   	  296140	      3936 ns/op	    5368 B/op	      10 allocs/op
```

These numbers are from one run on my machine (arm64 macOS, Go 1.26) and will differ on yours. On this run, the `+=` version was about 28 times slower and allocated about a thousand times per call versus ten, because every `+=` copies the string built so far. The `-8` suffix is `GOMAXPROCS`.

## Fuzzing in one paragraph

Go also has built-in fuzzing: a `FuzzXxx(f *testing.F)` function with `f.Add` seeds and `f.Fuzz`, run with `go test -fuzz FuzzReverse -fuzztime 5s`. I tried it on a rune-reversing function with the property "reversing twice returns the input" (skipping invalid UTF-8). It ran about 300,000 executions in 5 seconds and found nothing. A failure would be saved under `testdata/` and replayed by plain `go test`.

## A few things to watch

- Forgetting `-count=1` and wondering why nothing reruns: results of unchanged packages are cached.
- Use `t.Fatal` when later lines depend on an earlier check, `t.Error` when you want to see all failures.
- Name table cases well, because the name is how you find and run a failing one.
- Do not benchmark code the compiler can delete: use the result or rely on `b.Loop()`, which is designed to avoid that for the call inside the loop.
- Parallel subtests must not share mutable state.

## Exercise

1. Add a table-driven test for `Divide` with cases for a normal result, a negative number and division by zero (check the error with `errors.Is`).
2. Write `ConcatJoin` using `strings.Join` and add a third benchmark. Predict where it lands before running it.
3. Run `go test -cover` and find a branch you have not tested.

## What's next

Next we will read and write files, meet `io.Reader` and `io.Writer`, and encode and decode JSON in Go.
