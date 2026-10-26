+++
date = '2026-11-18T10:00:00+03:30'
draft = false
title = 'Packages and modules: structuring a Go project'
description = 'Go packages and modules: exported names, internal/, init order, import cycles, go.mod and go.sum, and a sane project layout, with real compiler output.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "modules", "packages"]
cover = { image = "/images/covers/go-packages-modules.png", alt = "Packages and modules: structuring a Go project", hiddenInSingle = true }
+++

So far every example fit in one file. Real projects don't, and Go has two concepts for splitting them up that people often mix together. After [pointers and memory](/posts/go-pointers-memory/), this post builds a small multi-package project and looks at what the compiler enforces: visibility, `internal/`, initialization order, import cycles, and external dependencies.

> Everything below was run with Go 1.26 on macOS (arm64).

## Package vs module

A **package** is a directory of `.go` files that share the same `package name` line; it is the unit of compilation and of visibility. A **module** is a tree of packages versioned together, described by a `go.mod` file at its root. The module path in `go.mod` is the prefix of every import path inside it.

Our demo module is `example.com/shop`:

```
shop/
  go.mod                  // module example.com/shop
  cmd/app/main.go         // package main
  internal/store/store.go // package store
  internal/audit/audit.go // package audit
  pkg/slug/slug.go        // package slug
```

The import path is the module path plus the directory: `example.com/shop/internal/store`. The directory name and the package name usually match, but only the directory is part of the path. The module path doesn't have to be a real URL while you experiment; for libraries you publish, it is the repository path.

## Exported vs unexported

A name that starts with a capital letter is exported; anything else is visible only inside its own package. There is no `public` or `private` keyword. In `slug` we have `Make` (exported) and `clean` (unexported). Using the latter from another module:

```go
import "example.com/shop/pkg/slug"

func main() { _ = slug.clean(" x ") }
```

```
$ go build .
./main.go:5:24: undefined: slug.clean
```

The message says `undefined`, not "unexported", which can be confusing at first. If you see it, check the capitalization.

## The `internal/` rule

A package under a directory named `internal` can only be imported by code rooted at the parent of that `internal` directory. Here that parent is the root of `example.com/shop`. A different module trying to import `store`:

```
$ go build .
package example.com/outsider
	main.go:3:8: use of internal package example.com/shop/internal/store not allowed
```

This is enforced by the toolchain, not by convention. It lets you keep implementation details private while the rest of the module shares them freely.

## `init()` and initialization order

Each package initializes its package-level variables first, then runs its `init()` functions (a package may have several, in the order the files and declarations are presented to the compiler). A package is initialized only after all packages it imports. `main` runs last. Our `main` imports `store` and `slug`; `store` imports `audit`:

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

`audit` ran before `store` because `store` depends on it, and everything finished before `main` started. The relative order of independent packages (`store` and `slug` here) is something I would not rely on. In general, avoid clever `init()` logic: it runs implicitly, can't return an error and is hard to test. Prefer an explicit constructor like `store.New()`.

## Import cycles are errors

If `a` imports `b` and `b` imports `a`, Go refuses to build:

```
$ go build ./...
package example.com/cyc/a
	imports example.com/cyc/b from a.go
	imports example.com/cyc/a from b.go: import cycle not allowed
```

The usual fix is to move the shared type into a third package, or to define an interface in the package that needs the behavior instead of importing the one that implements it. Cycles are often a sign that package boundaries are in the wrong place.

## Adding an external dependency

I imported `github.com/google/uuid` in `main.go` and ran `go mod tidy`, which adds missing requirements and removes unused ones. One honest note: my configured module proxy timed out with a TLS handshake error, so I ran with `GOPROXY=off` and `GOSUMDB=off` against `v1.6.0` already in my local module cache. On a normal connection `go mod tidy` alone does it, and you should leave checksum verification on. The result:

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

`go.mod` records what you need. `go.sum` records cryptographic hashes of those module versions so a later build can detect a changed download; commit both files. `go list -m all` shows the full dependency set, including indirect ones (here there are none).

## A sane layout

- Start with `main.go` and `go.mod`. Really: a small tool needs nothing more.
- Add `cmd/<name>/main.go` when the module has more than one binary, or you want `main` to stay thin.
- Put code you don't want others to import under `internal/`.
- Create a package when it has a clear purpose and a name you can say in one word, not because a diagram looks neat.
- `pkg/` is optional. Some projects use it for importable libraries; many skip it. Don't treat any layout as dogma.

## A few things to watch

- Over-structuring is the most common beginner trap: ten packages with one function each leads to cycles and ugly imports like `utils` and `common`.
- Package names are short, lowercase and singular; avoid repeating them in names (`store.Store` is fine, `store.StoreItem` stutters).
- Changing a capitalization changes your public API; exported names are a promise.
- Do not edit `go.sum` by hand; let `go mod tidy` manage it.
- Avoid heavy work in `init()`.

## Exercise

1. Add a `internal/config` package that exports `Load() Config`, and use it from `main`. Print the order of `init` calls to see where it falls.
2. Create an import cycle on purpose and read the error.
3. Add another dependency, run `go mod tidy`, and compare `go.mod` and `go list -m all` before and after.

## What's next

Next we get to what Go is best known for: goroutines and channels, and how to run work concurrently without tangling it.
