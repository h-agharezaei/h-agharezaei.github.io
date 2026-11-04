+++
date = '2026-11-18T10:00:00+03:30'
draft = false
title = 'Packages and modules: structuring a Go project'
description = 'Go packages and modules: exported names, internal/, init order, import cycles, go.mod and go.sum, and a sane project layout, with real compiler output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "modules", "packages"]
cover = { image = "/images/covers/go-packages-modules.png", alt = "Packages and modules: structuring a Go project", hiddenInSingle = true }
+++

So far every example in this series has fit in one file. But a program that grows will sooner or later reach a thousand lines in one file: finding anything gets hard, every change feels risky, and you cannot tell which part of the code is safe to touch. You have to split the program into pieces. Go has two concepts for this, and beginners often mix them up: **packages** and **modules**.

After [Pointers and the memory model in Go](/posts/go-pointers-memory/), this post builds a small multi-package project and looks at what the compiler enforces: who can see what, what the `internal/` directory does, in what order packages start up, why two packages cannot import each other, and how an external dependency is added.

> Everything below was run with Go 1.26 on macOS (arm64). The code is a local example.

## Package vs module

Let me give the simplest definitions first. A **package** is a directory of `.go` files that all start with the same `package name` line. It is the unit of compilation and the unit of visibility: whatever lives inside a package is either visible from outside or not (the next section shows how).

A **module** is a tree of packages versioned together. A module is identified by a `go.mod` file at its root, created with `go mod init <path>`. The name you write in `go.mod` (the module path) is the prefix of the import path of every package inside that module. In short: a package is "one directory of code", and a module is "a whole project or library wrapped around several packages".

Our demo module is `example.com/shop`, laid out like this:

```
shop/
  go.mod                  // module example.com/shop
  cmd/app/main.go         // package main
  internal/store/store.go // package store
  internal/audit/audit.go // package audit
  pkg/slug/slug.go        // package slug
```

The import path of each package is the module path plus its directory: for example `example.com/shop/internal/store`. The directory name and the package name usually match, but only the directory is part of the path. While you are just experimenting, the module path does not have to be a real URL. For a library you publish, it is the repository path.

## Exported vs unexported

How do we decide what is visible outside a package? Go has no `public` or `private` keyword. The rule is only the first letter of the name: if it is a capital letter, the name is **exported** and other packages can use it. If it is lowercase, it is visible only inside its own package.

In our `slug` package we have the function `Make` (exported) and the function `clean` (unexported). This small program, in another module, tries to call `clean`:

```go
import "example.com/shop/pkg/slug"

func main() { _ = slug.clean(" x ") }
```

```
$ go build .
# example.com/bu
./main.go:5:24: undefined: slug.clean
```

(This program is a separate module, linked to the local `shop` directory with one `replace` line in its `go.mod`. That is only for the experiment.) The message says `undefined`, not "unexported", which is confusing at first: from the compiler's point of view, a name you cannot see does not exist. If you get this error for a name you are sure is defined, check the capitalization of its first letter.

## The `internal/` rule

Sometimes you want a package to be usable everywhere in your own project, but you do not want others to import it. Go has a special directory name for this: a package under a directory named `internal` can only be imported by code rooted at the parent of that `internal` directory. In our example that parent is the root of `example.com/shop`. Now take another module (`outsider`) that tries to import `store`:

```
$ go build .
package example.com/outsider
	main.go:3:8: use of internal package example.com/shop/internal/store not allowed
```

The message is clear: using an internal package is not allowed. The Go toolchain enforces this, not a convention between people. So you can keep implementation details private while the rest of the module shares them freely.

## `init()` and initialization order

When the program starts, what code runs before `main`? Each package initializes its package-level variables first, then runs its own `init()` functions. A package may have several `init` functions, run in the order the files and declarations are presented to the compiler. A package is initialized only after all the packages it imports. `main` runs last.

In our example every package prints a line when it starts. `main` imports `store` and `slug`, and `store` imports `audit`. The output of `go run ./cmd/app`:

```
$ go run ./cmd/app
var: audit.Prefix
init: audit
init: store (first)
init: store (second)
init: slug
init: main
main starts
[audit] added Blue Mug
1 blue-mug
```

The first line comes from the variable `audit.Prefix`: package-level variables are set before any `init`. Then the `init` of `audit` ran, before `store`, because `store` depends on it. `store` has two `init` functions and both ran in the order written. Then `slug` came, and finally `main`. Only after all of that did `main starts` appear. The relative order of packages that do not depend on each other (here `store` and `slug`) is something I would not rely on, and I don't think you should either.

Even so, do not put clever logic in `init()`: it runs implicitly, it cannot return an error and it is hard to test. An explicit constructor like `store.New()` is better.

## Import cycles are errors

Now suppose package `a` imports package `b` and `b` imports `a`. Neither can be compiled without the other, and Go simply refuses:

```
$ go build ./...
package example.com/cyc/a
	imports example.com/cyc/b from a.go
	imports example.com/cyc/a from b.go: import cycle not allowed
```

The message shows the chain of imports: `a` reaches `b`, and `b` comes back to `a`. The usual fix is one of two things. Either move the shared type into a third package that both import, or define an interface in the package that needs the behavior, instead of importing the package that implements it. A cycle is often a sign that the package boundaries are in the wrong place.

## Adding an external dependency

So far we only had our own code. To use someone else's library, I imported `github.com/google/uuid` in `main.go` and ran `go mod tidy`. That command adds missing requirements to `go.mod` and removes unused ones.

One honest note: when I ran this, my configured module proxy timed out with a TLS handshake error, so I worked with `GOPROXY=off` and `GOSUMDB=off` against `v1.6.0`, which was already in my local module cache. On a normal connection `go mod tidy` alone does it, and you should leave checksum verification on. The result:

```
$ cat go.mod
module example.com/shop

go 1.26

require github.com/google/uuid v1.6.0

$ cat go.sum
github.com/google/uuid v1.6.0 h1:NIvaJDMOsjHA8n1jAhLSgzrAzy1Hgr+hNrb57e+94F0=
github.com/google/uuid v1.6.0/go.mod h1:TIyPZe4MgqvfeYDBFedMoGGpEw/LqOeaOT+nhxU+yHo=

$ go list -m all
example.com/shop
github.com/google/uuid v1.6.0
```

`go.mod` records what you need: a `require` line with a name and a version. `go.sum` records the cryptographic hashes of those versions, so that if the downloaded content ever changes, a build can notice; commit both files. `go list -m all` lists every module in the build: our own and `uuid`. If `uuid` itself depended on something else, those (indirect dependencies) would appear here too; in this case there are none.

## A sane layout, without dogma

- Start with `main.go` and `go.mod`. I mean it: a small tool needs nothing more.
- Add `cmd/<name>/main.go` when the module has more than one binary, or you want `main` to stay thin.
- Put code you do not want others to import under `internal/`.
- Create a package when it has a clear purpose and a name you can say in one word, not because the diagram looks nicer.
- `pkg/` is optional. Some projects use it for importable libraries, and many skip it. Do not treat any layout as sacred.

## Project structure traps

- **Over-structuring is the most common beginner trap.** Ten packages with one function each lead to cycles and ugly imports like `utils` and `common`.
- **Package names are short, lowercase and singular, and are not repeated in names.** `store.Store` is fine, `store.StoreItem` stutters.
- **Changing the first letter of a name changes your public API.** An exported name is a promise to everyone who uses it.
- **Do not edit `go.sum` by hand.** That is `go mod tidy`'s job.
- **Avoid heavy work in `init()`.** We saw why above: it is implicit, it cannot return an error and it is hard to test.

## Exercise

1. Add an `internal/config` package that exports `Load() Config`, and use it from `main`. See in what order the `init` lines print.
2. Create an import cycle on purpose and read the error.
3. Add another dependency, run `go mod tidy`, and compare `go.mod` and `go list -m all` before and after.

## What's next

"Goroutines and channels in Go". With the project structure in place, we get to what Go is best known for: running work concurrently without tangling it up.
