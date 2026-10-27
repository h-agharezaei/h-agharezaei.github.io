+++
date = '2027-02-09T10:00:00+03:30'
draft = false
title = 'Threat modeling with STRIDE'
description = 'Threat modeling with STRIDE on a Go orders API: a data-flow diagram, a STRIDE table, three real demos (tampering, error leaks, DoS) and a template.'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "threat-modeling", "stride", "appsec", "go"]
cover = { image = "/images/covers/sec-threat-modeling-stride.png", alt = "Threat modeling with STRIDE", hiddenInSingle = true }
+++

This opens the Software Security series. Before fixing bugs one by one, I want a way to find them early: {{< term "threat-modeling" "threat modeling" >}}. The `orders` service from this blog is our subject: the API from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), with Postgres ([pgx and sqlc](/posts/go-postgres-pgx-sqlc/)) and NATS JetStream behind it.

> Defensive only. Every demo here is my own tiny Go program on `127.0.0.1`, standard library only, run with Go 1.26. Nothing targets a third party. The "database error" in demo 2 is invented text, not a real Postgres run.

## Four questions

The process is four questions: what are we working on, what can go wrong, what are we going to do about it, did we do a good job. They are a widely used framing; I do not attribute them further.

## The model

```
 [ Client ] --1 HTTPS--> ( Orders API ) --2 SQL--> =Postgres=
  external      |            process   \--3 publish--> =NATS JetStream=
                |                                       |
   ===== trust boundary =====          ( Worker ) <--4--/
```

`[ ]` is an external entity, `( )` a process, `= =` a data store. The trust boundary sits where the internet meets the API: everything arriving on flow 1 is untrusted. Flows 2 to 4 are internal but still cross processes.

## STRIDE per element

{{< term "stride" "STRIDE" >}} asks six questions: Spoofing, Tampering, Repudiation, Information disclosure, {{< term "denial-of-service" "Denial of service" >}}, Elevation of privilege.

| Element | Threat | Mitigation |
|---|---|---|
| API, flow 1 | **S**: stolen or forged token | verify tokens, short expiry |
| API, flow 1 | **T**: client sets `price_cents` | allow-list input, server pricing (demo 1) |
| API | **R**: no record of who did what | structured logs with request ID, see [config and logging](/posts/go-config-logging-errors/) |
| API | **I**: raw errors reach the client | generic error plus log (demo 2) |
| API | **D**: huge or slow requests | body limit, timeouts (demo 3), [rate limiting](/posts/go-rate-limiting-caching/) |
| API | **E**: user reads another user's order | check ownership on every read |
| Postgres | **I**: leaked credentials | secrets out of logs, least-privilege DB user |
| NATS | **T/E**: anyone publishes events | TLS and auth, see [JetStream in production](/posts/nats-jetstream-production/) |
| NATS to worker | **T**: replayed or duplicate message | [idempotency](/posts/nats-jetstream-idempotency/) |

Three of these I reproduced.

## Demo 1: tampering

The naive endpoint decodes the body straight into its `Order` struct, so the client controls every field. This is {{< term "mass-assignment" "mass assignment" >}}:

```
$ curl -s -X POST 127.0.0.1:8101/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"id":1,"sku":"book","qty":1,"price_cents":1,"status":"paid"}
```

A 1500-cent book became 1 cent and "paid". The fixed version decodes into a two-field input (`sku`, `qty`), looks the price up in a server-side catalog and sets the status itself:

```
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"error":"bad request"}
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":2}'
{"id":1,"sku":"book","qty":2,"price_cents":1500,"status":"pending"}
```

`DisallowUnknownFields` rejects the extra fields.

## Demo 2: information disclosure

The naive handler returns `err.Error()`. My invented driver-style error leaks a column name, the SQLSTATE, a host name and the DB user:

```
{"error":"query orders: ERROR: column \"total_cents\" does not exist (SQLSTATE 42703) [host=db.internal port=5432 user=orders_app]"}
```

The fixed handler logs the details and returns a fixed message with a request ID the client can quote:

```
{"error":"internal error","request_id":"a1b2c3"}
level=ERROR msg="request failed" path=/orders/1/total error="query orders: ERROR: ..." request_id=a1b2c3
```

(The ID is a constant in this demo; real code generates it per request.)

## Demo 3: denial of service

I sent a 50 MiB body (zeros) to an endpoint that just drains it. The naive server read all of it: `{"read":"52428800"}`. With `http.MaxBytesReader` at 1 MiB the answer is `{"error":"body too large"}`.

For slow headers, a small Go probe opens a connection, sends half a header, then one byte every 200 ms (the {{< term "slowloris" "slowloris" >}} pattern). The server without timeouts: `still open after 4s, giving up`. With `ReadHeaderTimeout` of 1 s: `server closed after ~1.0s`. I did not measure memory or throughput.

## Ranking

Likelihood times impact, 1 to 3 each. This is my judgment for this service, not a measurement:

| Threat | L | I | Score |
|---|---|---|---|
| Client-set price | 3 | 3 | 9 |
| Another user's order | 2 | 3 | 6 |
| Verbose errors | 3 | 2 | 6 |
| Slow or huge requests | 2 | 2 | 4 |

Fix the highest scores first.

## A template

```markdown
# Threat model: <system>
Scope / out of scope:
Diagram: (elements, flows, trust boundaries)
| Element | S | T | R | I | D | E | Mitigation | Owner | Status |
Top risks (L x I):
Review date / trigger (new feature, new dependency):
```

## A few things to watch

- Redraw the diagram when the architecture changes; an old model is worse than none.
- Threats on flows are as real as threats on boxes.
- A mitigation without an owner is a wish.
- Tools such as OWASP Threat Dragon and the Microsoft Threat Modeling Tool exist; I only mention them and did not use them here.

## Exercise

Add an element to the diagram (a Redis cache, say) and write its six STRIDE rows. Which one scores highest?

## What's next

The next post is “The OWASP Top 10 in real code”.
