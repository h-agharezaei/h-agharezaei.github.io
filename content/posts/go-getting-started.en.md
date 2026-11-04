+++
date = '2026-10-27T10:00:00+03:30'
draft = false
title = 'Getting started with Go: install, modules, tooling'
description = 'Install Go, create your first module with go mod init, and learn the everyday commands: run, build, fmt, vet, test and mod tidy.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "tooling", "modules"]
cover = { image = "/images/covers/go-getting-started.png", alt = "Getting started with Go: install, modules, tooling", hiddenInSingle = true }
+++

Imagine you write a program that declares a variable and never uses it. In many languages the worst you get is a warning. In Go the program does not build at all. Go is this strict from the very first program: an unused import or local variable is a compile error, not a warning, and a tool called `go fmt`, not team taste, decides how code looks.

This is the first post of the **Go Fundamentals** series, and it starts from zero. We go through the language basics first, and then a second, backend-oriented series follows: HTTP services, databases and concurrency in real systems. I already used Go in an earlier post on [NATS JetStream](/posts/nats-jetstream-go/), but that one assumed you could read Go. Here I drop that assumption.

The goal today is simple: install Go, create a module, write a small program, and learn the handful of commands you will type every day. I ran the examples with Go 1.26.0 on macOS (arm64).

## Why Go for backend

Go is **compiled** (your code is turned into a machine program before it runs) and **statically typed** (the type of every variable is known at compile time, so type mistakes are caught there). Its specification is also small enough to learn completely. A few reasons people pick it for backend work:

- `go build` produces a single binary. Deployment and Docker images get simple: you move one file.
- Concurrency, meaning doing several things at once, is built into the language (goroutines and channels, which we meet in later posts).
- The standard library covers HTTP, JSON, testing and much more.
- The toolchain (formatter, test runner, dependency management) ships with the language, so teams argue less about setup.

## Installing

The official guide is at [go.dev/doc/install](https://go.dev/doc/install). On macOS, `brew install go` is also an option if you already use Homebrew. After installing, check that everything is in place:

```bash
go version
```

```
go version go1.26.0 darwin/arm64
```

The output shows the Go version, the operating system and the CPU architecture. On your machine you will probably see different values.

## Your first module

Go code always lives inside a **module**. A module is a directory that contains a file named `go.mod`. That file tells Go that this directory is a project, what it is called and what it depends on. Let us create one:

```bash
mkdir hello && cd hello
go mod init example.com/hello
```

`example.com/hello` is the **module path**, the name other code would use to import you. For a local experiment any name works. For something you publish it is usually the address of the repository.

Now we write `main.go`:

```go
package main

import "fmt"

func main() {
	fmt.Println("Hello, Go!")
}
```

It has three parts. `package main` says this file is an executable program (not a library). `import "fmt"` brings in the `fmt` package from the standard library, which handles printing and text formatting. And the `main` function is where the program starts. Run it:

```bash
go run .
```

```
Hello, Go!
```

The dot after `go run` means "the package in this directory". `go run` compiles the program to a temporary location and runs it right away, leaving nothing behind in your folder. If you want to keep the binary itself, use `go build`:

```bash
go build -o hello .
./hello
```

```
Hello, Go!
```

The `-o hello` flag names the output file. `hello` is a standalone program and does not need Go to be installed in order to run.

## What is in go.mod

The file that `go mod init` created looks like this:

```
module example.com/hello

go 1.25.0
```

It holds just two things: the module path, and a `go` line with the Go version the module expects. When you add dependencies, `require` lines appear here too.

One curious detail: my toolchain was 1.26.0, but `go mod init` wrote `go 1.25.0`. So this line records the language version the module expects, not necessarily the exact toolchain you have installed.

## A slightly bigger program

Now let the program do some work: read an optional name from the command line, and use `world` when none is given.

```go
package main

import (
	"fmt"
	"os"
)

// greeting builds the message for a given name.
func greeting(name string) string {
	return fmt.Sprintf("Hello, %s!", name)
}

func main() {
	name := "world"
	if len(os.Args) > 1 {
		name = os.Args[1]
	}
	fmt.Println(greeting(name))
}
```

Let us read it slowly. The function `greeting` takes a `string` and returns the greeting as a `string`; `fmt.Sprintf` is like `Println`, except that it returns the text instead of printing it. In `main`, we first set `name` to `"world"`. `os.Args` is the list of command-line arguments, and its element number zero is the program itself, so the first real argument is at index 1. If an argument was given (`len(os.Args) > 1`), we replace `name` with it. I explain declaring variables with `:=` and the `if` statement properly in the next post; for now it is enough that they work the way you expect.

We run the program once without an argument and once with one:

```bash
go run .
go run . Roham
```

```
Hello, world!
Hello, Roham!
```

The first run has no arguments, so the default name is used. In the second run `Roham` is the first argument and takes the place of `world`.

## The everyday commands

Working with Go revolves around a few fixed commands. These are worth knowing by heart:

- `go fmt ./...` rewrites files into the standard format and prints the names of the files it changed. In the Go world nobody debates style, because the formatter decides. (`./...` means "this directory and all subdirectories".)
- `go vet ./...` reports code that compiles but looks suspicious. It prints nothing when all is well.
- `go test ./...` runs tests. A test in Go is a function of the form `TestXxx(t *testing.T)` in a file ending in `_test.go`. For the `greeting` function above:

```go
package main

import "testing"

func TestGreeting(t *testing.T) {
	got := greeting("Roham")
	want := "Hello, Roham!"
	if got != want {
		t.Fatalf("got %q, want %q", got, want)
	}
}
```

```
$ go test ./...
ok  	example.com/greet	0.273s
```

The test compares the actual result with the expected one and fails through `t.Fatalf` if they differ. The `ok` line means every test in that package passed; the last number is the run time and changes from run to run. The name `example.com/greet` appears because I ran this test in a module with that name.

- `go mod tidy` adds missing dependencies to `go.mod` and removes unused ones. With no dependencies, as here, it changes nothing.

I also tried `go fmt` on a file that was badly spaced on purpose: it printed `bad.go` and rewrote `func  x( ){ }` into `func x() {}`.

## Where Go keeps things

The first time you download a dependency you wonder where it went. This command answers:

```bash
go env GOPATH GOMODCACHE
```

```
/home/user/go
/home/user/go/pkg/mod
```

The paths depend on your operating system and username (on macOS it is something like `/Users/you/go`), so I put a made-up example here. `GOMODCACHE` is where downloaded dependencies are stored, shared by all your projects. By default it lives under `GOPATH`. You do not need to put your own code there; projects can live anywhere you like.

## First-day mistakes

- `go run main.go` compiles only that one file. Once you have more than one file, a function defined in another file is not found. Use `go run .` instead so the whole package is built.
- Run commands from inside the module, next to `go.mod`. Otherwise you get an error saying `go.mod` was not found.
- An unused import or unused local variable is a compile error. If you are not using a variable yet while experimenting, you have to delete it or use it later.
- `go build` writes the binary in the current directory. Do not commit it.
- A passing `go vet` means the code avoids a few common mistakes, not that it works correctly. Tests are what show correctness.

## Exercise

1. Create a new module and make the greeting program accept two arguments, a first and last name, and print `Hello, First Last!`.
2. Move the default-name `world` logic into a separate function and write a second test for it.
3. Run `go fmt`, `go vet` and `go test` before you consider it done.

## What's next

"Types, variables and control flow in Go": this post used variables and `if` without explaining them, and that one covers them properly.
