+++
date = '2026-12-10T10:00:00+03:30'
draft = false
title = 'Building a command-line tool in Go'
description = 'Build wordstat, a real Go CLI: the flag package, subcommands, reading stdin, exit codes, a testable run function, version stamping and cross-compiling.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "cli", "flag", "build"]
cover = { image = "/images/covers/go-cli-tool.png", alt = "Building a command-line tool in Go", hiddenInSingle = true }
+++

Here is a small surprise about Go programs. If you write `defer f.Close()` in `main` and later call `os.Exit(1)`, the deferred call never runs. `os.Exit` ends the process on the spot. That one detail decides how a well-behaved command-line tool in Go should be structured, and we will come back to it with a tiny program that proves it.

First, though, let us build something. After [files, `io.Reader`/`io.Writer` and JSON](/posts/go-file-io-json/), we have the pieces for a real tool. We will write `wordstat`: a program that reads a text file (or standard input), prints the number of lines, words and bytes, and lists the most frequent words. It can print the result as plain text or as JSON. Along the way we meet the `flag` package for options, subcommands, {{< term "exit-status" "exit codes" >}}, a structure that is easy to test, and how to get one binary for any operating system.

> I ran everything with Go 1.27 on an arm64 Mac. All output below is copied from real runs. The code is a local example, not a published repo.

## Arguments and the flag package

When you run `wordstat -top 5 notes.txt`, the words after the program name arrive in Go as `os.Args`, a plain `[]string` whose element 0 is the program name. You could split it by hand, deciding which items are options and which are file names. But options, default values and the `-h` help text are a solved problem, and the `flag` package solves it.

The idea: you declare each option with a name, a default and a help text, and `flag` parses the command line for you. Whatever is left after the options (the file name, here) are **positional arguments**, and you read them with `fs.Arg(0)` and `fs.NArg()`. This is how `wordstat` starts:

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

Each call such as `fs.Int("top", 3, "...")` registers an option and returns a pointer to the value (so you write `*top` later). I use my own `FlagSet` instead of the global one that `flag.Int` uses, so that the function can be tested and does not touch global state. `ContinueOnError` makes `Parse` return an error instead of exiting the whole program, and `fs.Usage` replaces the default help text. One rule to remember: flags must come before positional arguments, because parsing stops at the first argument that is not a flag.

## Reading a file or stdin

Many Unix tools read from a file when you give one, and from **standard input** (stdin) when you do not. That makes them work in a {{< term "pipe" "pipe" >}}, such as `cat x | tool`. We can do the same with almost no extra code, because the counting function takes an `io.Reader`, exactly the idea from the previous post. The caller decides what that reader is:

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

If there is a file name, open it and use it. Otherwise keep `stdin`. `count` itself reads line by line with `bufio.Reader`, counts lines, words and bytes, and fills a map of word frequencies. I will not repeat it here, because it is plain code from earlier posts. Let us use this three-line file:

```text
$ cat sample.txt
Go is fun. Go is small.
Small tools are fun to build.
The go tool builds one binary.
```

Now two runs. The first prints the default text report. The second asks for only the top word, as JSON, and `head -3` cuts the output after three lines:

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

The first line says 3 lines, 18 words and 85 bytes. Below it comes the top-3 list: `go` appears three times (the code lowercases words and strips punctuation, so "Go" and "go." count together), then `fun` and `is` twice each. Words with the same count are sorted alphabetically, which is why `fun` comes before `is`. In the second run `< sample.txt` feeds the file to stdin, so there is no file name argument at all.

The same tool also works at the end of a pipe:

```text
$ printf 'a b a\nc a b\n' | ./wordstat -top 2
lines=2 words=6 bytes=12
    3  a
    2  b
```

## Errors, stderr and exit codes

A program has two output streams. **stdout** is for results. **stderr** is for error messages. The point of keeping them apart is that `wordstat file > out.txt` redirects only stdout, so error messages do not end up inside your file.

There is a third channel: the **exit code**, a number the program returns when it ends. Scripts and CI check it to know what happened. By convention 0 means success, 1 a runtime failure, and 2 a usage error (you called it wrongly). Here are a missing file, the same with stderr thrown away, and a bad flag value:

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

`echo "exit=$?"` prints the exit code of the previous command. In the first case the message goes to stderr and the exit code is 1. In the second, `2>/dev/null` discards stderr, so nothing is printed, but the exit code is still 1. In the third, the flag parser complains about `abc`, our `Usage` function prints the help, and the code is 2 because the problem is in how the tool was called.

## os.Exit skips deferred calls

Now the surprise from the beginning. `os.Exit` ends the process immediately, so deferred calls do not run. A small program shows it. It defers a print, and exits early only if you ask it to:

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

In the normal run `main` returns, and the deferred line prints last. In the second run `os.Exit(3)` happens first, and "deferred: cleanup" never appears. In a real tool the deferred call might close a file, flush a buffer or remove a temporary file, so skipping it is a real bug. (Run this from a built binary. `go run` hides the real exit code and prints its own `exit status 3` message.)

The fix is to keep `os.Exit` in exactly one place, and make that place so small that nothing needs deferring. All the logic goes into a function `run` that returns the exit code as an `int`, and `main` is one line:

```go
func run(args []string, stdin io.Reader, stdout, stderr io.Writer) int { /* ... */ }

func main() {
	os.Exit(run(os.Args[1:], os.Stdin, os.Stdout, os.Stderr))
}
```

Since `run` returns normally, its `defer f.Close()` runs before `os.Exit` ever sees the code.

## Testing run

This structure has a second benefit. `run` receives its arguments, input and output as parameters instead of reading globals, so a test needs no files and no real processes. We pass a string reader as stdin and two buffers as stdout and stderr:

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
ok  	example.com/wordstat	0.355s
```

There are two tests: the one above, and `TestRunMissingFile`, which checks that a missing file gives exit code 1 and an error message that contains the file name. Both pass. The run time at the end changes from run to run.

## Subcommands

Tools like `git` have subcommands: `git commit`, `git push`. Each one has its own flags. The standard `flag` package supports this with a simple pattern: give every subcommand its own `FlagSet` and choose by looking at `os.Args[1]`:

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

The word after the program name picks the branch, and the remaining arguments (`os.Args[2:]`) go to that subcommand's own flag set. Here `ExitOnError` is fine because this tiny example has nothing to clean up.

## One binary, any platform

`go build` produces a single self-contained binary, so installing your tool means copying one file. A common need is to stamp a release with its version. The linker can set a string variable for you: `-ldflags "-X main.version=..."`. The variable must be a package-level `string` (here `var version = "dev"`):

```text
$ go build -ldflags "-X main.version=1.2.0" -o wordstat . && ./wordstat -version
wordstat 1.2.0
$ go build -o wordstat . && ./wordstat -version
wordstat dev
```

Cross-compiling, building for a different operating system or CPU, needs just two environment variables:

```text
$ GOOS=linux GOARCH=amd64 go build -o wordstat-linux .
$ file wordstat-linux wordstat
wordstat-linux: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, ...
wordstat:       Mach-O 64-bit executable arm64
```

The `file` command reports what each file is: `wordstat-linux` is a Linux executable for 64-bit x86, and `wordstat` is a native macOS one. I could not run the Linux binary on this Mac, only build it and inspect it (I did the same for `windows/amd64`, and `file` reported a Windows executable). With Go 1.27 the native binary was about 3.9 MB, and adding `-ldflags "-s -w"` (which strips the symbol table and debug information) made it about 2.6 MB. Sizes depend on the Go version and platform.

## flag and exit code traps

- **`flag` stops at the first positional argument.** In `wordstat sample.txt -json`, the tool prints the plain text report: `-json` is after the file name, so it is not parsed as a flag, and `wordstat` silently ignores it. Put flags first.
- **Do not call `os.Exit` deep inside helper functions.** Return errors, and decide the exit code in one place. That keeps deferred cleanup working and keeps the helpers testable.
- **Errors go to stderr, data goes to stdout.** Then pipes and redirects behave as users expect.
- **`-X` is easy to get wrong silently.** It only sets `string` variables, and the package path must match exactly. I tried a typo (`main.versoin`) and the build succeeded; the binary just kept printing `dev`. According to the linker documentation, it also has no effect when the variable is initialized by a function call.
- **`go run` does not pass through the exact exit code.** Test exit codes with a built binary.

## Exercise

1. Add a `-min` flag that ignores words shorter than N characters, and extend the test to cover it.
2. Make `wordstat` accept several files and print one summary per file. Which part of `run` has to change?
3. Build for `windows/amd64` and check the result with `file`.

## What's next

"Mini project: a URL shortener in Go": it puts files and JSON, tests, concurrency and a clean shutdown together in one small HTTP service.
