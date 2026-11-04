+++
date = '2026-12-04T10:00:00+03:30'
draft = false
title = 'Testing in Go: table-driven tests and benchmarks'
description = 'Go testing basics: go test flags, table-driven tests with subtests, helpers, coverage, benchmarks with b.Loop and a short look at fuzzing.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "testing", "benchmark"]
cover = { image = "/images/covers/go-testing-basics.png", alt = "Testing in Go: table-driven tests and benchmarks", hiddenInSingle = true }
+++

You change a function, and you want to know whether it still works. The slow way is to run the program, click around, and hope. The better way is to keep a few small programs that call your function with known inputs and complain loudly when the answer is wrong. Those small programs are **tests**, and you can run them after every change in a second or two.

Go makes this easy because the tools are part of the language. The `testing` package and the `go test` command ship with Go, so there is nothing to install and no framework to choose. After [generics](/posts/go-generics/), this post shows how to write a test, how to read a failure, how to test many cases without repeating yourself (the **table-driven** style), how to measure test coverage, and how to write a **benchmark**, which is a test that measures speed instead of correctness.

> Everything below was run on macOS (arm64) with Go 1.27, and the outputs are copied from those runs. The code is a local example, not a published repo.

## Your first test

Go finds tests by a naming rule, not by configuration. A file whose name ends in `_test.go` is a test file, and it normally sits next to the code it tests. Inside it, every function named `TestSomething` that takes one `*testing.T` parameter is a test. The `t` is your handle to the test: you use it to report failures.

We need something to test. Here is a tiny package with one function that divides two integers and returns an error when the divisor is zero:

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

And two tests for it. The first checks the normal case. The second checks that dividing by zero gives the right error:

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

Notice there is no special `assert` function. A Go test is ordinary code: you compare the result with what you expect, and if they differ you call `t.Errorf` or `t.Fatalf` with a message.

Those two calls differ in one way. Both mark the test as failed, but `t.Errorf` lets the test keep running, while `t.Fatalf` stops it right there. Use `Fatalf` when going on makes no sense. In `TestDivide`, if `err` is not `nil`, the value `got` is meaningless, so there is no point checking it.

The second test uses `errors.Is`, which we met in [functions, defer and errors](/posts/go-functions-defer-errors/). `Divide` wraps the error with `%w`, so comparing with `==` would fail, but `errors.Is` looks inside the wrapping.

You run tests with `go test`. I almost always add two flags:

- `-v` prints every test and its result, not only the final summary.
- `-count=1` turns off the test cache. Go remembers the result of a package whose code and tests did not change, and prints `(cached)` instead of running it again. That is good for speed, but confusing when you want to see a test actually run.

There is also `-run`, which takes a regular expression and runs only the tests whose names match it. Note that it matches anywhere in the name, so `-run TestDivide` runs both of our tests, `TestDivide` and `TestDivideByZero`.

## What a failure looks like

A green test teaches little, so let me break one on purpose. This `add` has a bug: it subtracts. It lives in a separate folder of the demo project:

```go
func add(a, b int) int { return a - b } // bug

func TestAdd(t *testing.T) {
	if got := add(2, 3); got != 5 {
		t.Errorf("add(2, 3) = %d, want 5", got)
	}
}
```

Running `go test` there prints:

```text
--- FAIL: TestAdd (0.00s)
    b_test.go:9: add(2, 3) = -1, want 5
FAIL
FAIL	example.com/brokentest	0.973s
FAIL
```

The second line is the useful one: the file and line of the failed check, followed by our own message. That is why the message has the shape `got ..., want ...`. Without opening the code you can see what was called, what came back and what should have. The `0.973s` is the run time and changes from run to run. Also, `go test` exits with a non-zero code when something fails, and that is what a CI system looks at to turn a build red.

## Table-driven tests

Now suppose we are testing a function with many interesting inputs. Here is `Slug`, which turns a title into a URL-friendly word chain:

```go
func Slug(s string) string {
	return strings.Join(strings.Fields(strings.ToLower(s)), "-")
}
```

We could write one test function per input, but each would repeat the same five lines. The usual Go answer is a **table-driven test**: put the cases in a slice of structs (the "table"), where each row has a name, an input and the expected output, and loop over it. Adding a case is then one line.

For each row we call `t.Run(name, func...)`, which starts a **subtest**: a named test inside a test. Each subtest passes or fails on its own and shows up in the report with its name.

I also moved the comparison into a small helper. The helper calls `t.Helper()`, which tells Go "do not report failures at my line, report them at the line of whoever called me". Without it, every failure would point inside `assertSlug` instead of at the test case.

```go
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

Every subtest also calls `t.Parallel()`. That tells Go the subtest may run at the same time as its siblings. Since Go 1.22 each loop iteration has its own copy of `tt`, so the closure is safe. Only use `t.Parallel()` for tests that do not share mutable state.

To run a single subtest, put a slash in the `-run` pattern: the part before the slash matches the test, the part after matches the subtest. Spaces in a name become underscores. Running the "extra spaces" case:

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

The `RUN` lines mark the start of the test and its subtest. `PAUSE` and `CONT` (continue) come from `t.Parallel()`: a parallel subtest pauses until the parent test function has finished its own code (here, the loop that starts the subtests), then continues alongside its siblings. With several subtests, the order of the `CONT` lines and of the results can differ from run to run. The last two `PASS` lines are the result, the subtest indented under its parent.

## Coverage

After writing tests you may wonder whether they actually reach all of your code. Go can measure that. **Coverage** is the percentage of statements that ran at least once during the tests:

```text
$ go test -count=1 -cover .
ok  	example.com/testing-basics	0.290s	coverage: 100.0% of statements
```

For this small package every statement ran, so we got 100%. Be careful with what the number says. It tells you which lines were never executed, and that is useful for finding code with no tests. It does not tell you whether your checks are any good: a test that calls a function and checks nothing also gives coverage. Use it as a way to find gaps, not as a goal.

## Benchmarks

So far the question was "is the answer right?". The other question is "how fast is it?". A benchmark answers it. It is a function named `BenchmarkSomething` that takes a `*testing.B`, and Go runs its body again and again until it has a stable measurement. Since Go 1.24 the loop is written with `b.Loop()`.

To have something to measure, let us compare two ways of joining many short strings. The first uses `+=`. The second uses `strings.Builder`, which collects the pieces in a buffer:

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

`BenchmarkConcatBuilder` is identical except that it calls the other function. `parts` is a package-level slice of 1001 short strings, and an ordinary test checks that both functions return the same result, so we know we are comparing like with like.

Now the command. Benchmarks do not run with plain `go test`, so `-bench .` selects all of them. `-run xxx` skips the ordinary tests (no test is called xxx), and `-benchmem` adds memory numbers:

```text
$ go test -count=1 -run xxx -bench . -benchmem .
goos: darwin
goarch: arm64
pkg: example.com/testing-basics
cpu: Apple M1
BenchmarkConcatPlus-8      	   10000	    110425 ns/op	 1063869 B/op	     999 allocs/op
BenchmarkConcatBuilder-8   	  296140	      3936 ns/op	    5368 B/op	      10 allocs/op
```

Let us read one row. `BenchmarkConcatPlus-8` is the name, and the `-8` is the value of `GOMAXPROCS`, the number of threads Go may use. The next number is how many times the loop ran. Then come the interesting three: nanoseconds per call (`ns/op`), bytes allocated per call (`B/op`) and number of separate memory allocations per call (`allocs/op`).

The two rows tell a clear story. In the original run the `+=` version was about 28 times slower, and it made about 1000 allocations per call against 10. The reason is that a Go string cannot be changed, so every `+=` builds a new string and copies everything collected so far. Joining 1001 pieces that way copies again and again. `strings.Builder` appends into a buffer that grows only now and then.

Timings depend on the machine and on what else is running, so yours will differ. I took the `ns/op` numbers from my original run. When I ran it again for this post the machine was busy, and the ratio was similar (the allocation counts, 999 and 10, are the same every time).

## Fuzzing in one paragraph

Go also has built-in {{< term "fuzzing" "fuzzing" >}}. You write a `FuzzSomething(f *testing.F)` function, give it a few starting inputs with `f.Add`, and Go generates thousands of variations looking for one that breaks your rule. You run it with `go test -fuzz FuzzReverse -fuzztime 5s`. I tried it on a function that reverses the runes of a string, with the rule "reversing twice must give back the input" (inputs that are not valid UTF-8 are skipped). In my original run it made about 300,000 attempts in 5 seconds and found nothing; the count changes from run to run. If it had found a failing input, Go would save it under `testdata/` and plain `go test` would replay it from then on.

## Common traps

- **A test that "does not run".** If you forget `-count=1` and see `(cached)`, Go is reusing the last result because nothing changed. This is normal, but it can look like the test is stuck.
- **`Fatal` versus `Error`.** Use `t.Fatal` when the following lines depend on the check that just failed. Use `t.Error` when you want to see all failures in one run.
- **Unnamed table rows.** Give every case a clear name. That name is how you find a failing case in the output and how you run it alone with `-run`.
- **Benchmarking code the compiler can remove.** If the result of the measured code is never used, the compiler may delete the work, and the benchmark measures nothing. Using the result helps. According to the Go documentation, `b.Loop()` also keeps calls inside the loop from being optimized away.
- **Shared state in parallel subtests.** If parallel subtests write the same variable, you have a data race. Keep them independent.

## Exercise

1. Write a table-driven test for `Divide` with an ordinary case, a negative number and division by zero (check the error with `errors.Is`).
2. Write `ConcatJoin` using `strings.Join` and add a third benchmark. Guess where it will rank before you run it.
3. Run `go test -cover` and find a branch you have not tested.

## What's next

Next is "Files, io.Reader/Writer and JSON in Go": after tests, the first real code worth testing is code that reads and writes files and speaks JSON.
