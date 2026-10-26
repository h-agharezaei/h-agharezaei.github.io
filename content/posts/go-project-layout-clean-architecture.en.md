+++
date = '2026-12-18T10:00:00+03:30'
draft = false
title = 'Project layout and clean architecture in Go'
description = 'A small orders API in a layered Go layout: domain, service, store and transport, wired by hand, with real import checks, a fake-store test and curl runs.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "architecture", "clean-architecture", "backend"]
cover = { image = "/images/covers/go-project-layout-clean-architecture.png", alt = "Project layout and clean architecture in Go", hiddenInSingle = true }
+++

This post starts the Go Backend series. The Go Fundamentals series ended with [packages and modules](/posts/go-packages-modules/) and the [URL shortener mini project](/posts/go-mini-project-url-shortener/), where everything fit in a handful of files. Once a service has a database, an HTTP layer and real business rules, the question becomes where things live and who is allowed to import whom. Here we build one small `orders` service in a layered layout and check the dependency rules with the toolchain instead of by eye.

> Everything below was run with Go 1.26 on macOS (arm64). The module is `example.com/orders`, standard library only.

## The layout

```
orders/
  cmd/api/main.go                  // composition root
  internal/domain/order.go         // entities and rules
  internal/service/service.go      // use cases
  internal/store/memory/store.go   // one implementation of storage
  internal/transport/http/handler.go // thin HTTP handlers
```

The rule is one sentence: dependencies point inward. `domain` knows nothing about anyone, `service` knows `domain`, and the outer packages (`store`, `transport`) know the inner ones. Only `main` knows everybody.

## Domain: no infrastructure

```go
func NewOrder(id, customer string, cents int64) (Order, error) {
	if customer == "" || cents <= 0 {
		return Order{}, fmt.Errorf("%w: customer and positive amount required", ErrInvalidOrder)
	}
	return Order{ID: id, Customer: customer, Cents: cents, Status: "new"}, nil
}
```

The `Order` struct, the constructor that enforces its invariants and the sentinel errors (`ErrNotFound`, `ErrInvalidOrder`) live here. No JSON tags, no SQL, no `net/http`.

## Service: interfaces on the consumer side

The service needs somewhere to save orders, so it declares the interface itself, as small as its use cases require:

```go
type Repository interface {
	Save(ctx context.Context, o domain.Order) error
	Get(ctx context.Context, id string) (domain.Order, error)
	NextID(ctx context.Context) string
}

func (s *Service) Create(ctx context.Context, customer string, cents int64) (domain.Order, error) {
	o, err := domain.NewOrder(s.repo.NextID(ctx), customer, cents)
	if err != nil {
		return domain.Order{}, err
	}
	if err := s.repo.Save(ctx, o); err != nil {
		return domain.Order{}, err
	}
	return o, nil
}
```

This is the Go proverb "accept interfaces, return structs" applied at package boundaries: the interface belongs to the code that uses it, not to the code that implements it. The in-memory store (a mutex-guarded map) satisfies it, and so does anything else with those three methods. The HTTP package does the same: it declares a two-method `Orders` interface and its handlers only decode, call the service, map the error to a status and encode.

## The compile-time guard

Go interfaces are satisfied implicitly, so a typo in a method signature would only show up where the store is first used. A one-line guard moves that failure next to the implementation:

```go
var _ service.Repository = (*Store)(nil)
```

I removed `NextID` from a copy of the store (kept in a `_broken` folder in the demo) and built it:

```
$ go build ./_broken/
_broken/store.go:10:28: cannot use (*Store)(nil) (value of type *Store) as service.Repository value in variable declaration: *Store does not implement service.Repository (missing method NextID)
```

One trade-off: the guard makes `store/memory` import `service`. That arrow still points inward, but if you prefer the store not to know the service, put the guard in `main.go` or in the store's test instead.

## Composition root

```go
func main() {
	repo := memory.New()
	svc := service.New(repo)
	handler := transport.NewHandler(svc)

	log.Fatal(http.ListenAndServe(":8080", handler))
}
```

Wiring by hand is three lines here and will be thirty in a bigger service. That is still readable, greppable and checked by the compiler; I have not needed a DI framework in Go so far.

## Proving the direction

`go list` prints each package's imports. I filtered to this module:

```
$ for p in domain service store/memory transport/http; do
>   echo "== $p"; go list -f '{{join .Imports "\n"}}' ./internal/$p | grep example.com
> done
== domain
== service
example.com/orders/internal/domain
== store/memory
example.com/orders/internal/domain
example.com/orders/internal/service
== transport/http
example.com/orders/internal/domain
```

`domain` imports nothing from the module, `service` imports only `domain`, and neither imports `store` or `transport`. `go list -deps ./internal/service` agrees, even transitively. Put this in CI and the architecture is enforced rather than hoped for.

## The payoff: testing without infrastructure

The fake lives in the test file and has the same three methods:

```go
type fakeRepo struct{ saved map[string]domain.Order }

func (f *fakeRepo) Save(_ context.Context, o domain.Order) error { f.saved[o.ID] = o; return nil }
func (f *fakeRepo) NextID(context.Context) string                { return "42" }
// Get omitted here; it looks the id up in f.saved
```

```go
func TestCreateInvalidDoesNotSave(t *testing.T) {
	repo := &fakeRepo{saved: map[string]domain.Order{}}
	_, err := service.New(repo).Create(context.Background(), "", 0)
	if !errors.Is(err, domain.ErrInvalidOrder) {
		t.Fatalf("err = %v", err)
	}
	if len(repo.saved) != 0 {
		t.Fatal("saved an invalid order")
	}
}
```

```
$ go test -v ./internal/service
=== RUN   TestCreate
--- PASS: TestCreate (0.00s)
=== RUN   TestCreateInvalidDoesNotSave
--- PASS: TestCreateInvalidDoesNotSave (0.00s)
PASS
ok  	example.com/orders/internal/service	0.250s
```

No server, no database, no mocking library.

## Running it

Responses below are trimmed to the status line and body.

```
$ curl -si -X POST localhost:8080/orders -d '{"customer":"ali","cents":1500}'
HTTP/1.1 201 Created
{"id":"1","customer":"ali","cents":1500,"status":"new"}

$ curl -si localhost:8080/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}
```

An invalid body returned `422` with `{"error":"invalid order: customer and positive amount required"}`: the domain error travelled up through the service and the handler mapped it to a status code.

## Is this clean architecture?

Roughly. The famous circles map onto Go like this: entities are `domain`, use cases are `service`, interface adapters are `transport` and `store`, and frameworks and drivers are `main` plus third-party libraries. The Go-specific part is that interfaces are implicit and small, so you rarely need a dedicated "ports" package.

## A few things to watch

- This is over-engineering for a 300-line tool or a CRUD service with no real rules. Start flat (`main.go`, `store.go`), and extract a package when a second implementation or a hard-to-test piece shows up.
- Layers do not need an interface each. Add one where you want a seam: storage, clocks, external APIs. A service with a single implementation and no tests does not need it.
- Do not copy this folder tree as ritual. It is one reasonable shape, not the way; many good Go projects are flatter.
- Keep the domain honest. If handlers or SQL tags creep into `Order`, the arrows you proved above become decoration.
- Avoid package names like `utils` or `models`; they invite import cycles.

## What's next

Next: config, structured logging and errors in Go, where we replace the hard-coded `:8080` and `log.Println` in this service.
