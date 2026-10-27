+++
date = '2027-04-04T10:00:00+03:30'
draft = false
title = 'OpenAPI and API contracts'
description = 'OpenAPI and API contracts in Go: write a spec, lint it, check real responses against it with kin-openapi and see a breaking change fail a test.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["openapi", "api-contract", "software-engineering", "testing", "go"]
cover = { image = "/images/covers/eng-openapi-contracts.png", alt = "OpenAPI and API contracts", hiddenInSingle = true }
+++

In [API design: versioning and pagination](/posts/eng-api-design-versioning-pagination/) we decided what an API should look like. An {{< term "api-contract" "API contract" >}} is the written, checkable form of that decision. Without it, renaming one field breaks a client and nobody notices until production. The server itself comes from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), and test basics from [Testing in Go](/posts/go-testing-basics/). Opinions are marked **in my opinion**; everything else was run.

> Go 1.26, Node 20.13.1, a local demo of my own. It is a small orders API, not the previous post's demo: I did not build on that one.

## A small spec

I wrote an {{< term "openapi" "OpenAPI" >}} 3.1 document with `GET /orders` (cursor and limit, {{< term "pagination" "pagination" >}}), `POST /orders`, and an `Error` schema. Request and response shapes are {{< term "json-schema" "JSON Schema" >}}:

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

## Lint it

I pinned the linter: `npx --yes @redocly/cli@1.34.5 lint openapi.yaml`. My first draft was valid but the linter was unhappy:

```text
openapi.yaml:
  1:1   error    no-empty-servers        Servers must be present.
  7:5   error    operation-summary       Operation object should contain `summary` field.
  7:5   error    security-defined        Every operation should have security defined on it or on the root level.
  16:7  warning  operation-4xx-response  Operation must have at least one `4XX` response.
  (5 errors and 2 warnings in total)
```

I added `servers`, summaries, a bearer security scheme, a license and a `400` response on the list. The second run said `Your API description is valid` with two warnings left: a `localhost` server and a license without `url`/`identifier`. I kept them. The second one matters later.

## Check real responses against the spec

A {{< term "contract-test" "contract test" >}} calls the real handler and validates the response with the spec. I used `github.com/getkin/kin-openapi` v0.133.0:

```go
err = openapi3filter.ValidateResponse(ctx, &openapi3filter.ResponseValidationInput{
	RequestValidationInput: in, Status: rec.Code, Header: rec.Header(),
	Body: nopCloser{bytes.NewReader(rec.Body.Bytes())},
})
```

Three tests (list, create, create with `qty: 0`) pass under `go test -race`. They pass for the `400` too, because the error body matches `Error`.

Now break the handler on purpose. Renaming the JSON tag `qty` to `quantity`:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": property "qty" is missing
```

Changing `Qty` to a string:

```text
GET /orders -> 200 violates the contract: response body doesn't match schema #/components/schemas/OrderPage: Error at "/items/0/qty": value must be an integer
POST /orders -> 201 violates the contract: response body doesn't match schema #/components/schemas/Order: Error at "/qty": value must be an integer
```

I restored the handler afterwards. **In my opinion** this is the cheapest valuable test in an API codebase: one helper, every endpoint.

One honest detail. My first spec used 3.1 features and kin-openapi rejected them: `type: [string, "null"]` gave `unsupported 'type' value "null"`, and a license `identifier` gave `extra sibling fields: [identifier]`. So I dropped both and omit `next_cursor` on the last page. Check your validator's 3.1 support before trusting it.

## Breaking changes

A {{< term "breaking-change" "breaking change" >}} is one that breaks a correct client. I made a second spec where `currency` became a required request field, then validated the old request `{"item":"pen","qty":3}` against both:

```text
openapi.yaml: err=<nil>
openapi.v2.yaml: err=request body has an error: ... Error at "/currency": property "currency" is missing
```

That is what a diff tool should report in CI. I tried to run `oasdiff` (pinned) with `go run`, but the environment refused the command, so it **was not run**; the check above is my small manual substitute. Removing a field, a new required field, a narrower type: breaking. A new optional response field usually is not, though a strict client can still choke.

## Spec-first or code-first

**In my opinion**, spec-first suits APIs with several consumers: the spec is reviewed before code exists. Code-first suits one team that owns both sides, as long as the spec is generated and a test like the one above keeps it honest. Either way the spec is only trustworthy if a test ties it to the running code.

## Concepts I did not run

- Generating server stubs or clients (for example `oapi-codegen`): I did not run it.
- {{< term "consumer-driven-contract" "Consumer-driven contracts" >}} with Pact: the clients write what they use and the server verifies it. I only mention it.

## A few things to watch

- A spec that no test checks is documentation that will drift.
- Lint in {{< term "ci" "CI" >}}, and pin the linter version.
- Test error responses too, not only the happy path.
- Treat "valid spec" and "validator supports every 3.1 feature" as different claims.

## Exercise

Take one endpoint of yours, write its schema, and add a contract test. Then rename one response field and read the failure message.

## What's next

The next post is "Technical debt".
