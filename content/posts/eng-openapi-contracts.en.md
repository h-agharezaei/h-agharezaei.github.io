+++
date = '2027-04-04T10:00:00+03:30'
draft = false
title = 'OpenAPI and API contracts'
contentType = 'tutorial'
description = 'OpenAPI and API contracts in Go: write a spec, lint it, check real responses against it with kin-openapi and see a breaking change fail a test.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["openapi", "api-contract", "software-engineering", "testing", "go"]
cover = { image = "/images/covers/eng-openapi-contracts.png", alt = "OpenAPI and API contracts", hiddenInSingle = true }
+++

Imagine a mobile app that has been sending `{"item":"pen","qty":3}` to your server for a year. One day the server team decides orders need a `currency` too, and makes it a required field. Nobody tells the app team, because nobody thought of it as a breaking change. The app keeps working in the test environment, where it was never re-run, and starts failing in production the moment the new server is deployed.

The cause is not a bug in either side. The two sides simply held different ideas of what the API looks like, and there was no place where the idea was written down and checked. An {{< term "api-contract" "API contract" >}} is that place: a written description of what the server accepts and returns, in a form a program can check. It is the written form of the decisions from [API design: versioning and pagination](/posts/eng-api-design-versioning-pagination/). The server in this post is a small one in the style of [Building an API with net/http in Go](/posts/go-http-api-stdlib/), and the test basics are in [Testing in Go](/posts/go-testing-basics/). I mark my opinions with **in my opinion**. Everything else was run.

> The demo is a small orders API written for this post in Go. I originally ran it with Go 1.26 and Node 20.13.1, and re-ran the Go tests with Go 1.27.3 for this edit. It is not the demo of the previous post: I did not build on that one. I could not re-run the Node linter this time (the download timed out), so the lint output below is from the original run.

## A small spec

The contract format I use is {{< term "openapi" "OpenAPI" >}}, a standard way to describe an HTTP API in a YAML or JSON file. The file lists the paths, the methods, what each request must contain and what each response looks like. I wrote version 3.1 of it for three things: `GET /orders` (which returns one page of orders, using a cursor and a limit, as in {{< term "pagination" "pagination" >}}), `POST /orders` to create an order, and an `Error` shape for failures.

The shapes of requests and responses are written in {{< term "json-schema" "JSON Schema" >}}, a small language for saying "this must be an object, with these fields, of these types". This is the schema of one page of results:

```yaml
    OrderPage:
      type: object
      required: [items]
      properties:
        items:
          type: array
          items: { $ref: "#/components/schemas/Order" }
        next_cursor: { type: string }
```

Read it like this: a page is an object. It must have `items`, a list of `Order`. It may have a `next_cursor` string. The `{ $ref: ... }` is only a reference to another schema defined in the same file.

## Lint it

A spec is a file like any other, and it can be wrong or incomplete. A linter reads it and complains about things the standard allows but a good spec should not leave out. I used Redocly's linter, with its version pinned: `npx --yes @redocly/cli@1.34.5 lint openapi.yaml`. My first draft was valid, but the linter was not happy. These are four of its findings:

```text
openapi.yaml:
  1:1   error    no-empty-servers        Servers must be present.
  7:5   error    operation-summary       Operation object should contain `summary` field.
  7:5   error    security-defined        Every operation should have security defined on it or on the root level.
  16:7  warning  operation-4xx-response  Operation must have at least one `4XX` response.
  (5 errors and 2 warnings in total)
```

In plain words: the spec did not say where the server lives, did not give the operations a summary, did not say how requests are authenticated, and described no failure response for the list. I added `servers`, summaries, a bearer security scheme, a license and a `400` response on the list. The second run said `Your API description is valid`, with two warnings left: a `localhost` server, and a license without `url` or `identifier`. I kept both. The second one matters in a moment.

## Check real responses against the spec

So far the spec is only text. It becomes a contract when something checks the real server against it. A {{< term "contract-test" "contract test" >}} does that: it calls the real handler, takes the response, and validates it against the spec. I used the Go library `github.com/getkin/kin-openapi` v0.133.0. The important call is this one:

```go
err = openapi3filter.ValidateResponse(ctx, &openapi3filter.ResponseValidationInput{
	RequestValidationInput: in, Status: rec.Code, Header: rec.Header(),
	Body: nopCloser{bytes.NewReader(rec.Body.Bytes())},
})
```

It takes the status, the headers and the body that the handler produced, finds the matching response in the spec, and returns an error if they disagree. Three tests (list, create, and create with `qty: 0`) pass under `go test -race`. The invalid one passes too, which can look odd. It sends `qty: 0`, the server answers `400`, and that `400` body has the shape of `Error`. The spec allows it, so the contract is kept.

A test that passes proves little until I have seen it fail. So I broke the handler on purpose. First I renamed the JSON tag `qty` to `quantity`, which is exactly what a careless rename does:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": property "qty" is missing
```

The message says which request failed, which schema it was checked against, and which field is the problem. Then I changed the type of `Qty` from a number to a string:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": value must be an integer
POST /orders -> 201 violates the contract: response body doesn't match schema #/components/schemas/Order: Error at "/qty": value must be an integer
```

Here two endpoints fail at once, because both return an `Order`. I restored the handler afterwards. **In my opinion** this is the cheapest valuable test in an API codebase: one helper function, and every endpoint is covered.

One honest detail. My first spec used two 3.1 features, and kin-openapi rejected them. `type: [string, "null"]` gave `unsupported 'type' value "null"`, and a license `identifier` gave `extra sibling fields: [identifier]` (this is the warning I kept earlier). So I dropped both and simply leave out `next_cursor` on the last page. Before you trust a validator, check how much of the spec version you use it really supports.

## Breaking changes

Now back to the opening story. A {{< term "breaking-change" "breaking change" >}} is a change that breaks a client that was written correctly against the old contract. To see one, I made a second spec in which `currency` is a required field of the request. Then I validated the old request, `{"item":"pen","qty":3}`, against both specs:

```text
openapi.yaml: err=<nil>
openapi.v2.yaml: err=request body has an error: doesn't match schema #/components/schemas/NewOrder: Error at "/currency": property "currency" is missing
```

The old spec accepts the request (`err=<nil>` means no error). The new one rejects it, and says exactly why. This is what a diff tool should report in {{< term "ci" "CI" >}}, before the change is merged. I tried to run `oasdiff`, a tool made for this, pinned to a version, with `go run`, but my environment refused the command, so it **was not run**. The check above is my small manual substitute.

By the same logic: removing a field, adding a new required field, or narrowing a type are breaking. A new optional field in a response usually is not, although a very strict client can still choke on a field it does not know.

## Spec-first or code-first

There are two ways to get a spec. In spec-first you write the spec, and the code follows. In code-first you write the code and generate the spec from it. **In my opinion**, spec-first suits APIs with several consumers, because the spec can be reviewed before any code exists. Code-first suits one team that owns both sides, as long as the spec is generated and a test like the one above keeps it honest. Either way, a spec is only trustworthy if a test ties it to the running code.

## Concepts I did not run

- Generating server stubs or clients from the spec (for example with `oapi-codegen`): I did not run it.
- {{< term "consumer-driven-contract" "Consumer-driven contracts" >}} with Pact: here the clients write down what they actually use, and the server verifies that it still provides it. I only mention it.

## How a contract drifts

- A spec that no test checks is documentation, and documentation drifts away from the code. Tie it to the code with a test.
- Run the linter in {{< term "ci" "CI" >}} and pin its version, so a new release of the linter does not suddenly turn your pipeline red.
- Test the error responses too, not only the happy path. Clients depend on error bodies as much as on success bodies.
- "The spec is valid" and "my validator supports every 3.1 feature" are two different claims. A validator can accept a spec and still ignore parts of it.

## Exercise

Take one endpoint of yours, write its schema, and add a contract test. Then rename one response field and read the failure message.

## What's next

The next post is "Technical debt". Keeping one contract honest is a small, checkable job. Technical debt asks the bigger question: where does the cost of a whole repo pile up, and how do you measure it?
