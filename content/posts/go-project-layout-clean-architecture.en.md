+++
date = '2026-12-18T10:00:00+03:30'
draft = false
title = 'Project layout and clean architecture in Go'
description = 'A small orders API in a layered Go layout: domain, service, store and transport, wired by hand, with real import checks, a fake-store test and curl runs.'
contentType = 'engineering'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "architecture", "clean-architecture", "backend"]
cover = { image = "/images/covers/go-project-layout-clean-architecture.png", alt = "Project layout and clean architecture in Go", hiddenInSingle = true }
+++

Think about the first version of almost any small service. One handler reads the JSON body, checks that the amount is positive, runs an `INSERT`, and writes the response. It is thirty lines, it works, and nobody complains. Then a rule changes, and you want a test for it. But to test "the amount must be positive" you now have to start a database, because the rule lives in the same function as the SQL. A little later someone asks to run the same rule from a queue consumer instead of HTTP, and you find that the rule is welded to `http.ResponseWriter`.

Nothing here is a bug. The code simply mixes three different jobs: business rules, storage, and talking HTTP. When they live in one place, you cannot change or test one without dragging the other two along.

This post builds one small `orders` service in which each job has its own place, and it gives the rule for who is allowed to import whom. The interesting part is that we will not check this rule by eye: the Go toolchain can print it for us. In [packages and modules](/posts/go-packages-modules/) and the [URL shortener mini project](/posts/go-mini-project-url-shortener/) everything fitted in a handful of files, so this is the first time the question "where does this code go?" really matters.

> Everything below was re-run with Go 1.27 on macOS (arm64); the module declares `go 1.26`. The module is `example.com/orders` and uses only the standard library. The code is a local example, not a published repo.

## The core idea: arrows point inward

Picture the service as rings. In the centre are the **business rules**: what an order is and which orders are valid. Around it are the **use cases**: "create an order", "look up an order". On the outside are the details that can change: the database and the HTTP layer.

The rule is one sentence: **dependencies point inward**. A package in an inner ring must not import a package from an outer ring. The inner code does not know the outer code exists. The outer code is free to know the inner code.

The reason is practical. The database and the web framework are the things you are most likely to swap or upgrade. If the rules do not import them, the rules never have to change when they do. And a package that imports nothing heavy can be tested without anything heavy.

In Go this becomes four packages and one `main`:

```
orders/
  cmd/api/main.go                  // composition root
  internal/domain/order.go         // entities and rules
  internal/service/service.go      // use cases
  internal/store/memory/store.go   // one implementation of storage
  internal/transport/http/handler.go // thin HTTP handlers
```

- `domain` knows nobody. It holds the order itself and the rules.
- `service` knows only `domain`. It holds the use cases.
- `store` and `transport` are the outer ring. They know the inner packages.
- `main` is the only place that knows everybody; it creates the parts and connects them.

One Go detail: the `internal/` directory is special. The compiler refuses to let code outside this module import packages under it, so nobody else can start depending on our internals by accident.

## Domain: no infrastructure

The innermost package holds the `Order` type, the sentinel errors (`ErrNotFound`, `ErrInvalidOrder`) and a constructor. The constructor is where the business rule lives:

```go
func NewOrder(id, customer string, cents int64) (Order, error) {
	if customer == "" || cents <= 0 {
		return Order{}, fmt.Errorf("%w: customer and positive amount required", ErrInvalidOrder)
	}
	return Order{ID: id, Customer: customer, Cents: cents, Status: "new"}, nil
}
```

The rule "a customer and a positive amount are required" is an **invariant**: something that must be true for every order that exists. Because the only way to make a valid order is this constructor, the rule is written once and cannot be skipped by accident.

Look at what is missing. There are no JSON tags, no SQL, and no `net/http` import. This package can be compiled and tested with nothing else around it.

## Service: the interface belongs to the one who uses it

The service implements the use cases. To create an order it must save it somewhere, but it should not know where. So it declares what it needs as an **interface**, a list of methods, and asks for "anything that has these methods":

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

Read `Create` as a story: ask the repository for a new ID, build a valid order (the domain rule runs here), then save it. If the rule fails, we return early and nothing is saved.

Notice where the interface is declared: in `service`, next to the code that uses it, not in the package that implements it. In Go, a type satisfies an interface just by having the right methods; it never says "I implement this". So the store does not need to import the service's interface at all in order to fit it. This is the Go saying "accept interfaces, return structs" applied between packages: the consumer describes the small thing it needs, and any type that fits is welcome.

The in-memory store (a map guarded by a mutex) satisfies `Repository`. A real database store would satisfy it too. The HTTP package does the same trick in the other direction: it declares a two-method `Orders` interface for what it needs from the service. Its handlers do four small things: decode the request, call the service, translate an error into a status code, encode the response. No rules live there.

## A compile-time guard

Because interfaces are satisfied implicitly, a typo in a method signature has a nasty side effect. The compiler says nothing until the first place where the store is actually used as a `Repository`, which may be far from the store. A one-line guard moves the error next to the implementation:

```go
var _ service.Repository = (*Store)(nil)
```

It reads: "assign a nil `*Store` to a variable of type `service.Repository` and throw it away". It does nothing at runtime. It only forces the compiler to check that `*Store` has all the methods.

To see it work, I deleted `NextID` from a copy of the store (kept in a `_broken` folder in the demo) and built it:

```
$ go build ./_broken/
# example.com/orders/_broken
_broken/store.go:10:28: cannot use (*Store)(nil) (value of type *Store) as service.Repository value in variable declaration: *Store does not implement service.Repository (missing method NextID)
```

The message points at the guard line and names the missing method.

There is one trade-off. To write the guard, `store/memory` has to import `service`. That arrow still points inward, so the rule is intact. But if you prefer that the store not know about the service at all, put the guard in `main.go` or in the store's test instead.

## The composition root

Somebody has to create the concrete store, give it to the service, and give the service to the HTTP handler. That place is called the {{< term "composition-root" "composition root" >}}, and in Go it is simply `main`. Passing the dependencies in from outside like this is {{< term "dependency-injection" "dependency injection" >}} without any framework:

```go
func main() {
	repo := memory.New()
	svc := service.New(repo)
	handler := transport.NewHandler(svc)

	log.Fatal(http.ListenAndServe(":8080", handler))
}
```

The wiring is three lines here and might be thirty in a bigger service. It is still easy to read, easy to find with `grep`, and checked by the compiler. I have not needed a dependency-injection framework in Go so far.

## Proving the direction

"Dependencies point inward" is a claim, and claims should be checked. `go list` can print the imports of each package. I filtered the output to this module's own packages:

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

Read it package by package. `domain` imports nothing from the module: the list is empty. `service` imports only `domain`. The store imports `domain` and `service` (the guard from the previous section). `transport/http` imports `domain` because its handlers translate domain errors. Nobody in the inner ring imports `store` or `transport`. `go list -deps ./internal/service` agrees even for indirect imports; its only module package is `domain`. Put a check like this in CI and the architecture is enforced instead of merely hoped for.

## The payoff: testing without infrastructure

Now the reason for all this. The service needs a `Repository`, so in the test we hand it a fake: a few lines in the test file that keep orders in a map.

```go
type fakeRepo struct{ saved map[string]domain.Order }

func (f *fakeRepo) Save(_ context.Context, o domain.Order) error { f.saved[o.ID] = o; return nil }
func (f *fakeRepo) NextID(context.Context) string                { return "42" }
// Get omitted here; it looks the id up in f.saved
```

Such a stand-in is called a {{< term "test-double" "test double" >}}. With it we can check the rule "an invalid order is never saved":

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

The test asks for an order with no customer and zero cents. It expects the error to be `ErrInvalidOrder` and the fake to be still empty. Running it (the elapsed time differs between runs):

```
$ go test -v ./internal/service
=== RUN   TestCreate
--- PASS: TestCreate (0.00s)
=== RUN   TestCreateInvalidDoesNotSave
--- PASS: TestCreateInvalidDoesNotSave (0.00s)
PASS
ok  	example.com/orders/internal/service	2.358s
```

Both tests pass: the first creates a valid order through the fake and finds it saved with ID `42`. No server, no database, no mocking library was needed. That is the problem from the beginning of the post, solved.

## Running it

The demo hard-codes `:8080`. Since that port could be taken on a shared machine, I ran a throwaway copy on another local port and wrote the commands below with `localhost:8080` for readability. The responses are trimmed to the status line and body.

```
$ curl -si -X POST localhost:8080/orders -d '{"customer":"ali","cents":1500}'
HTTP/1.1 201 Created
{"id":"1","customer":"ali","cents":1500,"status":"new"}

$ curl -si localhost:8080/orders/99
HTTP/1.1 404 Not Found
{"error":"order not found"}
```

The first request creates order `1` and gets `201`. The second asks for an order that does not exist: the store returns `domain.ErrNotFound`, and the handler maps it to `404`. I also sent an order with an empty customer and `0` cents. The response was `422` with `{"error":"invalid order: customer and positive amount required"}`, and a request body that was not JSON got `400` with `{"error":"bad json"}`. In the `422` case the domain error travelled up through the service, and the handler translated it into a status code, which is exactly the handler's only job.

## Is this "clean architecture"?

Roughly, yes. In Robert Martin's well-known "Clean Architecture" diagram of concentric circles, entities are our `domain`, use cases are `service`, interface adapters are `transport` and `store`, and frameworks and drivers are `main` plus third-party libraries. The Go-specific part is that interfaces are implicit and small, so you rarely need a separate package full of "ports".

## When this layout is too much

- For a 300-line tool, or a CRUD service with no real rules, this is over-engineering. Start flat (`main.go`, `store.go`). Extract a package when a second implementation appears, or when one piece is hard to test.
- Not every layer needs an interface. Add one where you want a seam, a place where you can swap the real thing for a fake: storage, clocks, external APIs. A service with one implementation and no tests does not need it.
- Do not copy this folder tree as a ritual. It is one reasonable shape, not the only one. Many good Go projects are flatter.
- Keep the domain honest. If HTTP types or SQL tags creep into `Order`, the arrows we checked above become decoration.
- Avoid package names such as `utils` or `models`. They collect unrelated code and invite import cycles, where two packages need each other and Go refuses to compile.

## What's next

Next is "Config, structured logging and errors in Go". It starts with two things in `main` that we skipped here: the hard-coded `:8080` and the bare `log` call.
