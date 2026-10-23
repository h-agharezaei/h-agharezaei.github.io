+++
date = '2026-12-10T10:00:00+03:30'
draft = false
title = 'Building a command-line tool in Go'
description = 'Build wordstat, a real Go CLI: the flag package, subcommands, reading stdin, exit codes, a testable run function, version stamping and cross-compiling.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "cli", "flag", "build"]
cover = { image = "/images/covers/go-cli-tool.png", alt = "Building a command-line tool in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-file-io-json/) we read files and wrote JSON through `io.Reader` and `io.Writer`. Now we put that to work in something you can actually install: a command-line tool. We build `wordstat`, which reads a file (or stdin) and prints line, word and byte counts plus the top-N words, as text or as JSON. Along the way: the `flag` package, subcommands, exit codes, a structure that is easy to test, and getting one binary for any platform.

> I ran everything with Go 1.26 on an arm64 Mac. All output below is copied from real runs.

## os.Args versus flag

`os.Args` is just a `[]string`; element 0 is the program name. You can parse it by hand, but flags, defaults and `-h` are already solved in the **flag** package. Positional arguments stay available through `fs.Arg(0)` and `fs.NArg()`. Here is the shape of `wordstat`:

```go
fs := flag.NewFlagSet("wordstat", flag.ContinueOnError)
fs.SetOutput(stderr)
top := fs.Int("top", 3, "number of top words to show")
asJSON := fs.Bool("json", false, "print JSON instead of text")
showVersion := fs.Bool("version", false, "print version and exit")
fs.Usage = func() {
	fmt.Fprintln(stderr, "usage: wordstat [flags] [file]")
	fmt.Fprintln(stderr, "reads stdin when no file is given")
	fs.PrintDefaults()
}
if err := fs.Parse(args); err != nil {
	if err == flag.ErrHelp {
		return 0
	}
	return 2
}
```

I use my own `FlagSet` instead of the global one so the function can be tested. `ContinueOnError` makes `Parse` return an error instead of exiting, and `fs.Usage` replaces the default help text. Flags must come before positional arguments; parsing stops at the first non-flag.

## Reading a file or stdin

The counting function takes an `io.Reader`, exactly the idea from the previous post. The caller decides what that reader is:

```go
in := stdin
if fs.NArg() > 0 {
	f, err := os.Open(fs.Arg(0))
	if err != nil {
		fmt.Fprintln(stderr, "wordstat:", err)
		return 1
	}
	defer f.Close()
	in = f
}
st, err := count(in, *top)
```

`count` itself reads line by line with `bufio.Reader`, counts lines, words and bytes, and fills a frequency map. I will not repeat it here because it is plain code from earlier posts. With this file:

```text
$ cat sample.txt
Go is fun. Go is small.
Small tools are fun to build.
The go tool builds one binary.
```

```text
$ ./wordstat sample.txt
lines=3 words=18 bytes=85
    3  go
    2  fun
    2  is
$ ./wordstat -top 1 -json < sample.txt | head -3
{
  "lines": 3,
  "words": 18,
  "bytes": 85,
```

The same tool also works in a pipe:

```text
$ printf 'a b a\nc a b\n' | ./wordstat -top 2
lines=2 words=6 bytes=12
    3  a
    2  b
```

## Errors, stderr and exit codes

Results go to stdout; error messages go to stderr, so `wordstat file > out.txt` does not put errors in your file. The exit code tells scripts what happened. By convention 0 is success, 1 is a runtime failure and 2 is a usage error:

```text
$ ./wordstat missing.txt; echo "exit=$?"
wordstat: open missing.txt: no such file or directory
exit=1
$ ./wordstat missing.txt 2>/dev/null; echo "exit=$?"
exit=1
$ ./wordstat -top abc sample.txt; echo "exit=$?"
invalid value "abc" for flag -top: parse error
usage: wordstat [flags] [file]
reads stdin when no file is given
  -json
    	print JSON instead of text
  -top int
    	number of top words to show (default 3)
  -version
    	print version and exit
exit=2
```

## os.Exit skips deferred calls

This is the reason `main` should be tiny. `os.Exit` ends the process immediately, so pending `defer`s never run. A small program shows it:

```go
func main() {
	defer fmt.Println("deferred: cleanup")
	if len(os.Args) > 1 && os.Args[1] == "exit" {
		os.Exit(3)
	}
	fmt.Println("main returns normally")
}
```

```text
$ ./exitdefer
main returns normally
deferred: cleanup
$ ./exitdefer exit; echo "exit=$?"
exit=3
```

(Run it from a built binary. `go run` hides the real exit code and prints `exit status 3` itself.) The fix is the structure used above: all logic lives in `run`, which returns an int, and `main` is one line:

```go
func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int { /* ... */ }

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
```

Since `run` returns normally, its `defer f.Close()` does run before `os.Exit` sees the code.

## Testing run

Because `run` receives its input and output as parameters, a test needs no files or real processes:

```go
func TestRunStdin(t *testing.T) {
	var out, errb bytes.Buffer
	in := strings.NewReader("go is fun\nGo is small\n")
	code := run([]string{"-top", "2"}, in, &out, &errb)
	if code != 0 {
		t.Fatalf("exit code = %d, stderr = %q", code, errb.String())
	}
	want := "lines=2 words=6 bytes=22\n    2  go\n    2  is\n"
	if out.String() != want {
		t.Errorf("stdout = %q, want %q", out.String(), want)
	}
}
```

```text
$ go test -count=1 -v .
=== RUN   TestRunStdin
--- PASS: TestRunStdin (0.00s)
=== RUN   TestRunMissingFile
--- PASS: TestRunMissingFile (0.00s)
PASS
ok  	example.com/wordstat	0.263s
```

## Subcommands

For tools like `git` you want `tool hello -name X`. Give each subcommand its own `FlagSet` and switch on `os.Args[1]`:

```go
switch os.Args[1] {
case "hello":
	fs := flag.NewFlagSet("hello", flag.ExitOnError)
	name := fs.String("name", "world", "who to greet")
	fs.Parse(os.Args[2:])
	fmt.Println("hello,", *name)
case "bye":
	fmt.Println("bye")
default:
	fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
	os.Exit(2)
}
```

```text
$ go run ./sub hello -name Roham
hello, Roham
$ go run ./sub hello
hello, world
```

## One binary, any platform

`go build` produces a single self-contained binary. `-ldflags "-X main.version=..."` sets a string variable at link time, which is how releases get stamped. The variable must be a package-level `string` (here `var version = "dev"`):

```text
$ go build -ldflags "-X main.version=1.2.0" -o wordstat . && ./wordstat -version
wordstat 1.2.0
$ go build -o wordstat . && ./wordstat -version
wordstat dev
```

Cross-compiling needs only two environment variables:

```text
$ GOOS=linux GOARCH=amd64 go build -o wordstat-linux .
$ file wordstat-linux wordstat
wordstat-linux: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, ...
wordstat:       Mach-O 64-bit executable arm64
```

I could not run the Linux binary on this Mac, only build it and inspect it. The native binary was about 3.0 MB; adding `-ldflags "-s -w"` (strip symbols) made it about 2.0 MB.

## A few things to watch

- `flag` stops at the first positional argument, so `wordstat file -json` treats `-json` as a file name.
- Never call `os.Exit` deep inside helpers; return errors and decide the exit code in one place.
- Print errors to stderr and data to stdout, so pipes and redirects behave.
- `-X` only works on uninitialized or constant-string `string` variables in the named package; a typo in the path silently does nothing.
- `go run` does not pass through the exact exit code; test exit codes with a built binary.

## Exercise

1. Add a `-min` flag that ignores words shorter than N characters, and extend the test to cover it.
2. Make `wordstat` accept several files and print one summary per file. Which part of `run` has to change?
3. Build for `windows/amd64` and check the result with `file`.

## What's next

In the next post we use all of this in the series mini project: a URL shortener in Go.
