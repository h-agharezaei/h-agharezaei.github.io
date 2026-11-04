+++
date = '2027-05-28T10:00:00+03:30'
draft = false
title = 'Domain-driven design basics'
contentType = 'tutorial'
description = 'Domain-driven design in Go: value objects, an aggregate that guards its invariants, domain events, bounded contexts and an import-checking test.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ddd", "domain-driven-design", "software-engineering", "go", "architecture"]
cover = { image = "/images/covers/eng-ddd-basics.png", alt = "Domain-driven design basics", hiddenInSingle = true }
+++

Imagine a shop with two teams. The sales team talks about a customer as someone with an email address and a credit limit. The shipping team talks about a customer as a name and an address where a parcel goes. Both say "customer". If the code has one `Customer` type that tries to serve both, it grows fields for everybody, and every change for one team risks the other. Worse, the code starts to use words nobody speaks: a developer writes `status = 2`, while everyone else says "the order was placed".

This is the problem {{< term "domain-driven-design" "domain-driven design" >}} (DDD) tries to solve. The "domain" is the business area the software is about (selling, shipping, billing). DDD says: shape the code around that domain, using the words the business uses, and draw explicit borders where those words change meaning. The border between two models is the same kind of border we met between old and new code in the previous post, [Working with legacy code](/posts/eng-legacy-code/), and it is largely what this post is about.

The ideas come from Eric Evans' book *Domain-Driven Design*; Vaughn Vernon's *Implementing Domain-Driven Design* is the practical follow-up. Related reading: [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/) and [Testing in Go](/posts/go-testing-basics/). Opinions are marked; the rest was run.

> I re-ran the demo with Go 1.27.3 and `go test -race` passes (the original run used Go 1.26). The demo is a local example I invented: orders in a Sales context, recipients in a Shipping context.

I will go through four ideas, from small to large: language and value objects, aggregates, events with use cases, and bounded contexts. For each I show a small piece of code and a test that proves the point.

## Language and value objects

The first idea is the {{< term "ubiquitous-language" "ubiquitous language" >}}: the names in the code are the names people use in conversation. If the team says "place an order", the method is called `Place`, not `SetStatus(2)`. The demo's words are order, line, place, pay, ship and cancel. When a business person reads the method names, they should recognise their own sentences.

The next idea is the {{< term "value-object" "value object" >}}. Think of a banknote: you do not care which particular note you hold, only its value. A value object is the same. It has no identity, it never changes after it is created, and two of them with the same contents are equal. `Money` in the demo is one: an amount in cents and a currency. Its fields are unexported and the only way to make one is a constructor that checks the input, so `Money == Money` works in Go and you cannot construct, for example, negative money through the constructor. `Add` refuses to mix currencies. The test also tries bad values; the one that logs something prints:

```text
domain_test.go:36: rejected: email: invalid "not-an-email"
```

That line comes from the email value object refusing the string `not-an-email`. Zero quantity and negative money are rejected in the same way (those tests print nothing, they just pass). The point is that once you hold an `Email` or a `Money`, you know it is valid, and no later code has to check again.

An **entity** is the opposite: it has an identity that stays the same while its state changes. An `Order` is the same order whether it is a draft or shipped.

## An aggregate guards its rules

Now picture an order with its lines. "Add a line" and "place the order" are not two separate operations on two separate things; the rules involve both. For instance: no line may be added after the order is placed. If any code could append to the list of lines directly, that rule would depend on everybody remembering it.

An {{< term "aggregate" "aggregate" >}} solves that. It is a cluster of objects that is always changed as one unit, through one entry point, the **root**, and the root enforces the rules. In the demo, `Order` is the root, and the lines are reachable only through it. Its rules: no line changes after it is placed, at most 50 lines, the total can never be negative, and the order can only move through legal states. The customer is referenced by `CustomerID`, never by a pointer to another object, so the aggregate stays small and self-contained.

An illegal move returns a typed error, `*IllegalTransition`. To check the state rules completely, a table-driven test tries every action from every state and prints the result (`ok` means the move was allowed):

```text
          place   pay     ship    cancel  
draft     ok      ERR     ERR     ERR     
placed    ERR     ok      ERR     ok      
paid      ERR     ERR     ok      ok      
shipped   ERR     ERR     ERR     ERR     
cancelled ERR     ERR     ERR     ERR     
```

Read it row by row. A draft can only be placed. A placed order can be paid or cancelled. A paid order can be shipped or cancelled. Shipped and cancelled orders are finished: nothing is allowed. Anything you do not see as `ok` is refused by the root, and the test checks every one of the 20 cells against the expected table.

A rule of thumb: one {{< term "transaction" "transaction" >}} changes one aggregate ([Transactions and ACID](/posts/db-transactions-acid/)). If a use case seems to need two aggregates changed together, the boundary is probably in the wrong place, or the second change should happen later, triggered by an event.

### The bad design, run

To see why this matters, the demo also contains the opposite design, an *anemic* model. Its `Order` has exported fields (`Status`, `Items`) and no behaviour. The rules live in a separate service: `AddItem` checks that the status is `draft`. That works, until someone adds `CopyItems` for an import job and forgets the check.

One test asserts that a placed order never gains items: it expects `AddItem` to refuse, then calls `CopyItems` and expects the placed order to stay empty. I put it behind a build tag (`anemic`) so the normal test run stays green, and ran it with `go test -tags anemic`:

```text
--- FAIL: TestNoItemsAfterPlaced (0.00s)
    anemic_test.go:16: placed order gained 1 item(s) through CopyItems
FAIL
```

The rule was in the service, so the new code path walked around it. On the rich `Order` the same promise holds, because `lines` is unexported and `AddLine` is the only door in; its test passes. In my opinion this is the most useful tactical idea in DDD: put the rule where no code path can skip it.

## Events, repositories and use cases

Three more pieces complete the picture.

When something important happens in the domain, the aggregate records it as a {{< term "domain-event" "domain event" >}}, a fact in the past tense. `Place` records `OrderPlaced` inside the aggregate. The caller later collects it with `PullEvents`.

A **repository** is how the domain asks for aggregates to be loaded and saved without knowing about the database. The `Repository` interface lives in the domain package, and `MemRepo` in the `infra` package implements it.

An **application service** runs one use case: it only orchestrates and holds no business rules. `PlaceOrder` loads the order, calls `Place`, saves it, and only then publishes the events. Two tests check the ordering, using a publisher that records what it gets and a repository that can be told to fail:

```text
--- PASS: TestPublishAfterSave
--- PASS: TestNoEventWhenSaveFails
```

The first checks that after a successful save the event is published. The second makes the save fail and checks that nothing was published, so nobody hears about an order that was not stored. Keep in mind that the repository here is an in-memory fake, not a real database. Doing "save and publish" atomically against a real database is the [outbox pattern](/posts/go-outbox-pattern-nats/); I did not rerun it here.

## Bounded contexts

Back to the two customers. In the demo, each has its own package: `sales.Customer` has an email and a credit limit; `shipping.Customer` has a name and an address. A small translator connects them:

```go
func FromSales(c sales.Customer, name, address string) shipping.Customer
```

That is a {{< term "bounded-context" "bounded context" >}}: a boundary inside which one model and one language apply consistently. Each context keeps its own model, and the only way across is explicit translation. Neither team is forced to accept the other's idea of a customer.

The same shape protects you from an old system (see [legacy code](/posts/eng-legacy-code/)). `FromLegacy` takes a row in the old system's shape, with the invented field names `CustNm`, `Addr1` and `Addr2`, and returns a clean Shipping customer. This is an {{< term "anti-corruption-layer" "anti-corruption layer" >}}: the old names stop at this function and never leak into the new model. The test logs the result:

```text
{ID:c2 Name:Bob Address:2 Side Rd}
```

The test fed in a row with spaces around the name (`" Bob "`) and got a trimmed `Bob` and a clean address back.

In my opinion the strategic part of DDD (contexts, shared language, who owns what) is the valuable part. The tactical patterns above are optional tools. **Event storming**, a workshop where people stick events on a wall to find the contexts, is the technique I know for the strategic work. I have not run one for this post.

## Keeping the layers honest

Borders only help if they hold. The demo's layout is `internal/sales/{domain,app,infra}` and `internal/shipping/{domain,acl}`. The domain must not depend on infrastructure. Instead of trusting everyone to remember, a test enforces it. It runs `go list -deps` on both domain packages and fails if they depend on `net/http`, `database/sql`, `/infra` or `/app`. It passes.

To see that the test can fail, I added a `net/http` import to the sales domain on purpose, in a scratch copy:

```text
--- FAIL: TestDomainPurity (0.05s)
    arch_test.go:22: ./internal/sales/domain depends on vendor/golang.org/x/net/http/httpguts
    arch_test.go:22: ./internal/sales/domain depends on vendor/golang.org/x/net/http/httpproxy
    arch_test.go:22: ./internal/sales/domain depends on net/http/httptrace
    arch_test.go:22: ./internal/sales/domain depends on net/http/internal
    arch_test.go:22: ./internal/sales/domain depends on net/http/internal/ascii
    arch_test.go:22: ./internal/sales/domain depends on vendor/golang.org/x/net/http2/hpack
    arch_test.go:22: ./internal/sales/domain depends on net/http/internal/httpcommon
    arch_test.go:22: ./internal/sales/domain depends on net/http/internal/httpsfv
    arch_test.go:22: ./internal/sales/domain depends on net/http/internal/http2
    arch_test.go:22: ./internal/sales/domain depends on net/http
FAIL
```

One import line produced ten lines of failure, because `go list -deps` also lists everything `net/http` pulls in; the last line is the one you did it with. (The order of the lines can differ between runs.) After I removed the import, the test passed again.

## Where DDD stops paying off

- **DDD is overkill for CRUD.** A table with a form needs no aggregates.
- **Large aggregates cause contention.** Since one aggregate is saved as one unit, many people changing the same big aggregate conflict with each other. Keep aggregates small.
- **I did not run event sourcing or CQRS here.** They are often mentioned together with DDD, but you can use DDD without them.

## Exercise

Take one entity in your service. List its rules, move each one into a method of the root, make the fields unexported, and write one test that fails if a rule is skipped.

## What's next

The next post is "Monorepo or polyrepo?". Once the contexts have clear borders, the next question is where their packages should live.
