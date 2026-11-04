+++
date = '2027-03-26T10:00:00+03:30'
draft = false
title = 'API design: versioning and pagination'
contentType = 'engineering'
description = 'API design in Go: offset pagination skips and repeats rows, cursor pagination does not; additive versus breaking changes and Sunset headers, run.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["api-design", "pagination", "versioning", "software-engineering", "go"]
cover = { image = "/images/covers/eng-api-design-versioning-pagination.png", alt = "API design: versioning and pagination", hiddenInSingle = true }
+++

Here is a bug that no test in your own repository will show you. A client fetches page 1 of a newest-first list of orders. Then somebody creates one new order. The client fetches page 2, and order 151, which it already saw at the bottom of page 1, shows up again at the top of page 2. Now run the story the other way: if an order is deleted between the two requests, order 151 is never shown at all. The client syncs "everything" and silently misses a row.

Nobody can fix that with a [code review](/posts/eng-code-review/) later. It comes from the shape of the API itself, and once clients depend on that shape, every mistake in it becomes a migration. Two decisions cause this kind of pain most often: how a list is {{< term "pagination" "paginated" >}} (returned in pages instead of all at once), and how the API changes over time without breaking the people who use it.

To look at both with real behavior, I wrote a small server in plain `net/http`, in the style of [Building an API with net/http in Go](/posts/go-http-api-stdlib/). It holds 250 seeded orders in memory. I mark my opinions with **in my opinion**. Everything else was run with curl against `127.0.0.1`.

> The demo is a local example. I originally ran it with Go 1.26 and re-ran every scenario below for this edit with Go 1.27.3, on a random free port instead of the one in the code. Some outputs in the original post were abbreviated; where I found that, I replaced them with the real output.

## Offset pagination and its trap

The obvious design is `?page=2&per_page=100` on `/v1/orders`, newest first. "Offset" means the server skips the first (page-1) × per_page rows and returns the next ones. To see what goes wrong, I fetched page 1, then created one new order, then fetched page 2:

```text
page 1: 100 ids [250, 249] ... [152, 151]
(POST /admin/orders  -> new order 251)
page 2: 100 ids [151, 150] ... [53, 52]
```

Order 151 is on both pages. The new row went on top and pushed everything down by one, so the last row of page 1 became the first row of page 2.

Deletion is the mirror image. I fetched page 1 again (ids 251 down to 152), deleted order 200, and fetched page 2:

```text
page 2: 100 ids [150, 149] ... [52, 51]
```

Order 151 was never shown. Deleting 200 moved everything below it up by one, so 151 slid up into the range of page 1 after the client had already read that page. A client that syncs "everything" silently misses a row.

This is a property of "skip N rows", not a bug in my code, and all it needs is a table that is being written to. Which is almost any table that matters.

## Keyset pagination

The fix is to tell the server where to continue, not how many rows to skip. {{< term "keyset-pagination" "Keyset pagination" >}} does this: "give me the rows after this one". The endpoint `/v2/orders` uses it and returns an opaque `next_cursor`. "Opaque" means the client should treat it as a meaningless token and just send it back. Inside, it is base64 of the last row's `(created_at, id)`. Decoded, the cursor after the first 100 rows looks like this:

```text
{"t":"2027-01-01T02:31:00Z","id":151}
```

I ran the same scenario on a fresh server. Page 1 gave ids 250 down to 151. Then I inserted order 251 and deleted order 200, and followed the cursor:

```text
page 2: 100 ids [150, 149] ... [52, 51]
page 3:  50 ids [50, 49] ... [2, 1]   next_cursor = null
```

Page 2 starts exactly after 151, no matter what happened above it. Over all three pages there is no duplicate and no skipped id, which I checked by comparing the ids I received with 1..250 minus 200. `next_cursor = null` on the last page says there is nothing more.

One rule makes this work: the sort key must be unique and stable. Many orders can share a timestamp, so `id` breaks the ties, and the order is `(created_at desc, id desc)`.

The response also carries a `Link` header with the next page, which is a standard way to say it. With `limit=2` the first page returned:

```text
Link: </v2/orders?cursor=eyJ0IjoiMjAyNy0wMS0wMVQwNDowOTowMFoiLCJpZCI6MjQ5fQ&limit=2>; rel="next"
```

Keep the cursor opaque, so you can change what is inside it later without breaking clients. The price is that a client cannot jump straight to page 7.

## Limits and bad input

An unbounded `limit` is a denial-of-service switch: one request can ask for everything. My server caps it at 100 and rejects anything outside the range with a 400 and a message:

```text
GET /v1/orders?per_page=1000  -> 400 {"error":"page must be >= 1 and per_page 1..100"}
GET /v2/orders?limit=abc      -> 400 {"error":"limit must be an integer from 1 to 100"}
GET /v2/orders?cursor=zzz     -> 400 {"error":"invalid cursor"}
```

(On the wire, Go's JSON encoder writes the `>` in the first message as `\u003e`, which is the same string for any JSON decoder. I show it the way a decoder reads it.)

**In my opinion** rejecting is better than silently clamping the value to 100: the client learns that its assumption was wrong, instead of quietly receiving less data than it asked for.

A `total` count is a separate trade-off. An exact count means a second query on every page, which on a large table is usually not cheap. I did not measure it. My demo has no `total`.

## Versioning options

Once an API has to change, there has to be a way for clients to say which version they speak. There are three common places to put it. All three work. This is **my opinion** on them:

- **URL path (`/v1/`):** visible in logs, easy to route, and easy to try with curl.
- **Header (`Accept: application/vnd.example.v2+json` or a custom header):** keeps URLs clean, but is harder to cache and to debug.
- **Query parameter (`?version=2`):** simple, but you need a default for requests that leave it out.

I pick the path. More important than the mechanism is not needing new versions often.

## Additive versus breaking

That leads to the real question: what changes need a new version at all? Adding a field is usually safe. Removing or renaming one is not, because that is a {{< term "breaking-change" "breaking change" >}}. How a client reads the response decides how much damage a change does.

I wrote two clients and ran them against three versions of one order response. The strict client uses Go's `DisallowUnknownFields`, which rejects any field it does not know, and it also checks by hand that `status` is present. The other is a {{< term "tolerant-reader" "tolerant reader" >}}: plain `json.Unmarshal`, which ignores unknown fields. This is the real output of the test:

```text
same     body={"customer":"c007","id":7,"status":"paid"}
  strict:   {ID:7 Customer:c007 Status:paid} err=<nil>
  tolerant: {ID:7 Customer:c007 Status:paid} err=<nil>
added    body={"currency":"EUR","customer":"c007","id":7,"status":"paid"}
  strict:   {ID:7 Customer:c007 Status:paid} err=json: unknown field "currency"
  tolerant: {ID:7 Customer:c007 Status:paid} err=<nil>
removed  body={"customer":"c007","id":7}
  strict:   {ID:7 Customer:c007 Status:} err=missing field status
  tolerant: {ID:7 Customer:c007 Status:} err=<nil>
```

Read the three cases in turn:

- **same:** both clients are happy.
- **added:** a new field `currency` appears. The strict client fails with an error, even though nothing it needs changed. The tolerant client ignores it and carries on.
- **removed:** the `status` field is gone. The strict client reports a clear error. The tolerant client survives, but it silently reads the missing field as an empty string (`Status:` with `err=<nil>`), which is worse, because nothing tells it something is wrong.

So there are three rules. Clients should be tolerant of additions. Servers should treat removing or renaming a field as breaking. And a change in meaning, the same field name with a new unit, is the nastiest breaking change of all, because no decoder notices it.

## Deprecation and Sunset

When you do have to retire something, say so in the response itself. The old offset endpoint now announces what is coming:

```text
Deprecation: true
Link: </v2/orders>; rel="successor-version"
Sunset: Wed, 31 Dec 2031 23:59:59 GMT
```

The date is invented. According to RFC 8594, the `Sunset` header carries the HTTP-date after which the resource may stop responding. I believe a newer RFC defines `Deprecation` with a date value instead of `true`; I did not check it, so look before copying. Whatever you send, log which clients still call the old path, because that tells you when it is safe to turn it off.

## Retries and idempotency

Pagination only reads, so a client can safely retry it. For POST requests that create things, accept a key chosen by the client, so a retry does not create two orders. The idea is the same as {{< term "idempotency" "idempotency" >}} in [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/). I did not build it here.

## Mistakes that turn into migrations

- **Offset on a list that changes.** Choose keyset for any list that grows or changes while being read. Use offset only for small, stable lists.
- **Changing what a field means.** Never change the meaning of a field in place. Add a new field.
- **Announcing a deprecation vaguely.** A deprecation without a date and a successor is a rumour.

## What's next

The next post is "OpenAPI and API contracts". These decisions only hold if the contract is written down and checked against real responses.
