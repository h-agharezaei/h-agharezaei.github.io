+++
date = '2027-05-28T10:00:00+03:30'
draft = false
title = 'Domain-driven design basics'
description = 'Domain-driven design in Go: value objects, an aggregate that guards its invariants, domain events, bounded contexts and an import-checking test.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["ddd", "domain-driven-design", "software-engineering", "go", "architecture"]
cover = { image = "/images/covers/eng-ddd-basics.png", alt = "Domain-driven design basics", hiddenInSingle = true }
+++

The previous post, [Working with legacy code](/posts/eng-legacy-code/), ended at the border between old and new models. {{< term "domain-driven-design" "Domain-driven design" >}} (DDD) is largely about that border. The ideas come from Eric Evans' book "Domain-Driven Design"; Vaughn Vernon's "Implementing Domain-Driven Design" is the practical follow-up. Related: [Project layout and clean architecture in Go](/posts/go-project-layout-clean-architecture/), [Testing in Go](/posts/go-testing-basics/). Opinions are marked; the rest was run.

> Go 1.26, `go test -race`. The demo is a local example I invented: orders in Sales, recipients in Shipping.

## Language and value objects

The {{< term "ubiquitous-language" "ubiquitous language" >}} rule: names in code are names in conversation. If the team says "place an order", the method is `Place`. My demo's words are order, line, place, pay, ship, cancel.

A {{< term "value-object" "value object" >}} is immutable and compared by value. `Money` has unexported fields and a validating constructor, so `Money == Money` works and an invalid one cannot be built. `Add` rejects mixing currencies. The test also builds bad values:

```text
domain_test.go:36: rejected: email: invalid "not-an-email"
```

Zero quantity and negative money are rejected the same way. An entity, by contrast, has identity: `Order` is the same order as its state changes.

## An aggregate guards its rules

An {{< term "aggregate" "aggregate" >}} is a cluster changed as one unit; its root enforces the rules. My `Order` has: no line changes after it is placed, at most 50 lines, total never negative, and a state machine. `Customer` is referenced by `CustomerID`, never by pointer. Illegal moves return a typed `*IllegalTransition`. The table-driven test tries every action from every state (`ok` = allowed):

```text
          place   pay     ship    cancel  
draft     ok      ERR     ERR     ERR     
placed    ERR     ok      ERR     ok      
paid      ERR     ERR     ok      ok      
shipped   ERR     ERR     ERR     ERR     
cancelled ERR     ERR     ERR     ERR     
```

The rule of thumb is one {{< term "transaction" "transaction" >}} per aggregate ([Transactions and ACID](/posts/db-transactions-acid/)). If a use case must change two, the boundary is probably wrong, or the second change should be an event.

### The bad design, run

The anemic version has exported fields, and the rule lives in a service: `AddItem` checks the status. Later someone adds `CopyItems` for an import job and forgets the check. One test asserts that a placed order never gains items. I put it behind a build tag so the normal run stays green, and ran `go test -tags anemic`:

```text
--- FAIL: TestNoItemsAfterPlaced (0.00s)
    anemic_test.go:16: placed order gained 1 item(s) through CopyItems
FAIL
```

On the rich `Order` the same promise holds because `lines` is unexported and `AddLine` is the only door. Its test passes. **In my opinion** this is the most useful tactical idea: put the rule where no code path can skip it.

## Events, repositories and use cases

`Place` records an {{< term "domain-event" "OrderPlaced" >}} event inside the aggregate. The `Repository` interface lives in the domain package, and `MemRepo` in `infra` implements it. The application service only orchestrates: load, `Place`, save, then publish. Two tests, using a recording publisher and a repo that fails on demand:

```text
--- PASS: TestPublishAfterSave
--- PASS: TestNoEventWhenSaveFails
```

When the save fails, nothing is published. This is an in-memory fake, not a real database. Doing "save and publish" atomically against a real database is the [outbox pattern](/posts/go-outbox-pattern-nats/); I did not rerun it here.

## Bounded contexts

In Sales, `Customer` has an email and a credit limit. In Shipping, `Customer` has a name and an address. These are two types in two packages, and a translator connects them:

```go
func FromSales(c sales.Customer, name, address string) shipping.Customer
```

That is the {{< term "bounded-context" "bounded context" >}} idea: one model per language, with explicit translation between them. The same shape protects you from an old system, as in the [legacy code](/posts/eng-legacy-code/) post: `FromLegacy` takes an invented row with `CustNm`, `Addr1`, `Addr2` and returns a clean Shipping customer. That is an {{< term "anti-corruption-layer" "anti-corruption layer" >}}; the test logs `{ID:c2 Name:Bob Address:2 Side Rd}`.

**In my opinion** the strategic part (contexts, language, who owns what) is the valuable part of DDD. The tactical patterns are optional. **Event storming**, a workshop where people stick events on a wall to find contexts, is the technique I know for the strategic work; I have not run one for this post.

## Keeping the layers honest

Layout: `internal/sales/{domain,app,infra}` and `internal/shipping/{domain,acl}`. A test runs `go list -deps` for both domain packages and fails if they depend on `net/http`, `database/sql`, `/infra` or `/app`. It passes. Then I added a `net/http` import to the domain on purpose:

```text
--- FAIL: TestDomainPurity (0.15s)
    arch_test.go:22: ./internal/sales/domain depends on net/http
```

The real output also listed `net/http/...` sub-packages; I cut them. After reverting, it passes again.

## A few things to watch

- DDD is overkill for CRUD. A table with a form needs no aggregates.
- Large aggregates cause contention; keep them small.
- I did not run event sourcing or CQRS here.

## Exercise

Take one entity in your service. List its rules, move each into a method of the root, make the fields unexported, and write one test that fails if a rule is skipped.

## What's next

The next post is "Monorepo or polyrepo?".
