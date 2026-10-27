+++
date = '2027-03-26T10:00:00+03:30'
draft = false
title = 'API design: versioning and pagination'
description = 'API design in Go: offset pagination skips and repeats rows, cursor pagination does not; additive versus breaking changes and Sunset headers, run.'
categories = ["Engineering"]
series = ["Software Engineering"]
tags = ["api-design", "pagination", "versioning", "software-engineering", "go"]
cover = { image = "/images/covers/eng-api-design-versioning-pagination.png", alt = "API design: versioning and pagination", hiddenInSingle = true }
+++

After [Effective code review](/posts/eng-code-review/) comes a thing reviewers can rarely fix later: the shape of a public API. Once clients depend on it, every mistake is a migration. Two decisions bite most often: how a list is {{< term "pagination" "paginated" >}} and how the API changes over time. The server is plain `net/http`, in the style of [Building an API with net/http](/posts/go-http-api-stdlib/); I wrote a small new one with 250 seeded orders in memory. Opinions are marked **in my opinion**; everything else was run with curl on `127.0.0.1`.

## Offset pagination and its trap

The obvious design is `?page=2&per_page=100` on `/v1/orders`, newest first. I fetched page 1, then created one new order, then fetched page 2:

```text
page 1: 100 ids [250, 249] ... [152, 151]
(POST /admin/orders  -> new order 251)
page 2: 100 ids [151, 150] ... [53, 52]
```

Order 151 appears on both pages: the new row pushed everything down by one. Deleting is the mirror image. On the next page 1 (ids 251 ... 152) I deleted order 200, then fetched page 2:

```text
page 2: 100 ids [150, 149] ... [52, 51]
```

Order 151 was never shown: it slid up into the first page's range after the client had already read it. A client that syncs "everything" silently misses a row. This is a property of "skip N rows", not a bug in my code, and it needs only a busy table.

## Keyset pagination

The fix is to say where to continue, not how many to skip. `/v2/orders` uses {{< term "keyset-pagination" "keyset" >}} paging and returns an opaque `next_cursor`: base64 of the last row's `(created_at, id)`. Decoded, it holds `{"t":"2027-01-01T02:31:00Z","id":151` plus the closing brace. Same scenario on a fresh server: page 1 gave ids 250 ... 151, I inserted order 251 and deleted order 200, then followed the cursor:

```text
page 2: 100 ids [150, 149] ... [52, 51]
page 3:  50 ids [50, 49] ... [2, 1]   next_cursor = null
```

No duplicate, no skip. The sort key must be unique and stable, which is why `id` breaks ties for equal timestamps; the order is `(created_at desc, id desc)`. The response also carries a `Link` header, and with `limit=2` the first page returned:

```text
Link: </v2/orders?cursor=eyJ0Ijoi...&limit=2>; rel="next"
```

Keep the cursor opaque so you can change its content later. The price is that clients cannot jump to page 7.

## Limits and bad input

An unbounded `limit` is a denial-of-service switch. Mine caps at 100 and rejects the rest with a 400 and a message:

```text
GET /v1/orders?per_page=1000  -> 400 {"error":"page must be >= 1 and per_page 1..100"}
GET /v2/orders?limit=abc      -> 400 {"error":"limit must be an integer from 1 to 100"}
GET /v2/orders?cursor=zzz     -> 400 {"error":"invalid cursor"}
```

**In my opinion** rejecting is better than silently clamping: the client learns its assumption was wrong. A `total` count is a separate trade-off. Exact counts mean a second query on every page, which on a large table is usually not cheap; I did not measure it. My demo has none.

## Versioning options

All three work; this is **my opinion**.

- URL path (`/v1/`): visible in logs, easy to route and to try with curl.
- Header (`Accept: application/vnd.example.v2+json` or a custom header): clean URLs, but harder to cache and debug.
- Query parameter (`?version=2`): simple; you need a default when it is missing.

I pick the path. More important than the mechanism is to need new versions rarely.

## Additive versus breaking

Adding a field is usually safe; removing or renaming one is not. A strict decoder versus a {{< term "tolerant-reader" "tolerant reader" >}}, on three responses for one order:

```text
same     {"customer":"c007","id":7,"status":"paid"}
  strict:   ok
  tolerant: ok
added    {"currency":"EUR","customer":"c007","id":7,"status":"paid"}
  strict:   err=json: unknown field "currency"
  tolerant: ok
removed  {"customer":"c007","id":7}
  strict:   err=missing field status
  tolerant: Status:"" err=<nil>
```

The strict decoder (`DisallowUnknownFields`) breaks on an addition. The tolerant one survives it but silently reads the removed field as `""`, which is worse. So: clients should be tolerant, servers should treat removal and renaming as breaking, and a change in meaning (same field name, new unit) is the nastiest breaking change because no decoder notices it.

## Deprecation and Sunset

The old offset endpoint now says what is coming:

```text
Deprecation: true
Link: </v2/orders>; rel="successor-version"
Sunset: Wed, 31 Dec 2031 23:59:59 GMT
```

The date is invented. According to RFC 8594 `Sunset` carries the HTTP-date after which the resource may stop responding. I believe a newer RFC defines `Deprecation` with a date value instead of `true`; I did not check it, so look before copying. Log which clients still call the old path.

## Retries and idempotency

Pagination is read-only, so it is safe to retry. For POSTs, accept a client-supplied key so a retry does not create two orders; the idea is the same as {{< term "idempotency" "idempotency" >}} in [Idempotency in JetStream](/posts/nats-jetstream-idempotency/). I did not build it here.

## A few things to watch

- Choose keyset for any list that grows or changes while being read; use offset only for small, stable lists.
- Never change the meaning of a field in place; add a new one.
- A deprecation without a date and a successor is a rumour.

## Exercise

Run the two scenarios against your own list endpoint: insert and delete a row between page 1 and page 2. Does any id repeat or vanish? If so, write down what a keyset version would sort by.

## What's next

The next post is "OpenAPI and API contracts".
