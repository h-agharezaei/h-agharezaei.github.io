+++
date = '2026-10-27T10:00:00+03:30'
draft = false
title = 'Getting started with Go: install, modules, tooling'
description = 'Install Go, create your first module with go mod init, and learn the everyday commands: run, build, fmt, vet, test and mod tidy.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "tooling", "modules"]
cover = { image = "/images/covers/go-getting-started.png", alt = "Getting started with Go: install, modules, tooling", hiddenInSingle = true }
+++

This is the first post of a beginner series, **Go Fundamentals**. The plan is to cover the language basics here, and then move on to a second, backend-oriented series: HTTP services, databases, concurrency in real systems. I already used Go in an earlier post on [NATS JetStream](/posts/nats-jetstream-go/), but that one assumed you could read Go. This series starts from zero.

Today we install Go, create a module, and learn the handful of commands you will type every day. Everything below was run with Go 1.26.0 on macOS (arm64).

## Why Go for backend

Go is a statically typed, compiled language with a small spec. A few reasons people pick it for backend work:

- `go build` produces a single binary, which makes deployment and Docker images simple.
- Concurrency (goroutines and channels) is built into the language.
- The standard library covers HTTP, JSON, testing and more.
- The toolchain (formatter, test runner, dependency management) ships with the language, so teams argue less about setup.

## Installing

Follow the official guide at [go.dev/doc/install](https://go.dev/doc/install). On macOS, `brew install go` is also an option if you already use Homebrew. Then verify:

```bash
go version
```

```
go version go1.26.0 darwin/arm64
```

## Your first module

Go code lives in **modules**. A module is a directory with a `go.mod` file. Create one:

```bash
mkdir hello && cd hello
go mod init example.com/hello
```

The module path (`example.com/hello`) is the name other code would use to import you. For a local experiment any name works; for something you publish it is usually the repository path. Now `main.go`:

```go
package main

import "fmt"

func main() {
	fmt.Println("Hello, Go!")
}
```

`package main` with a `main` function marks an executable program. Run it:

```bash
go run .
```

```
Hello, Go!
```

`go run` compiles to a temporary location and runs it. To keep the binary, use `go build`:

```bash
go build -o hello .
./hello
```

```
Hello, Go!
```

## What is in go.mod

```
module example.com/hello

go 1.25.0
```

It has the module path and a `go` line with the Go version the module expects. When you add dependencies, `require` lines appear here too. Interestingly, my toolchain is 1.26.0 but `go mod init` wrote `go 1.25.0`; the file records a language version, not necessarily the exact toolchain you have installed.

## A slightly bigger program

Let us read an optional name from the command line, with a default:

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

`os.Args[0]` is the program itself, so the first real argument is at index 1. We cover variables and `if` properly in the next post.

```bash
go run .
go run . Roham
```

```
Hello, world!
Hello, Roham!
```

## The everyday commands

- `go fmt ./...` rewrites files into the standard format and prints the names of files it changed. In Go nobody debates style; the formatter decides.
- `go vet ./...` reports suspicious code that compiles fine. It prints nothing when all is well.
- `go test ./...` runs tests. A test is a function `TestXxx(t *testing.T)` in a `_test.go` file:

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

- `go mod tidy` adds missing and removes unused dependencies in `go.mod`. With no dependencies, as here, it changes nothing.

I checked `go fmt` by feeding it a badly spaced file: it printed `bad.go` and rewrote `func  x( ){ }` into `func x() {}`.

## Where Go keeps things

```bash
go env GOPATH GOMODCACHE
```

```
/Users/hossein/go
/Users/hossein/go/pkg/mod
```

`GOMODCACHE` is where downloaded dependencies are stored, shared by all your projects. By default it lives under `GOPATH`. You do not need to put your own code there.

## A few things to watch

- `go run main.go` compiles only that file. Prefer `go run .` so the whole package is built once you have more than one file.
- Run commands from inside the module (where `go.mod` is), or you get a "no go.mod" error.
- Unused imports and unused local variables are compile errors, not warnings.
- `go build` writes the binary in the current directory; do not commit it.
- `go vet` passing does not mean the code is correct, only that it avoids a set of common mistakes.

## Exercise

1. Create a new module and make the greeting program accept two arguments, a first and last name, and print `Hello, First Last!`.
2. Add a second test case for the default name `world` by extracting that logic into a function.
3. Run `go fmt`, `go vet` and `go test` before you consider it done.

## What's next

In the next post, `go-types-control-flow`, we look at types, variables and control flow: the building blocks you need to write real programs.
