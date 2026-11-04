+++
date = '2027-02-09T10:00:00+03:30'
draft = false
title = 'Threat modeling with STRIDE'
description = 'Threat modeling with STRIDE on a Go orders API: a data-flow diagram, a STRIDE table, three real demos (tampering, error leaks, DoS) and a template.'
contentType = 'tutorial'
categories = ["Security"]
series = ["Software Security"]
tags = ["security", "threat-modeling", "stride", "appsec", "go"]
cover = { image = "/images/covers/sec-threat-modeling-stride.png", alt = "Threat modeling with STRIDE", hiddenInSingle = true }
+++

Imagine an orders endpoint that decodes the request body straight into its `Order` struct. It looks tidy: one line of code, every field filled in. But the client now decides every field, including the price and the status. A customer can send an order for a 1500-cent book that costs 1 cent and is already marked "paid". Nobody wrote a bug on purpose. Nobody asked the question "what if the client lies?"

{{< term "threat-modeling" "Threat modeling" >}} is the habit of asking that question early, on paper, before the code exists or while it is still easy to change. It finds problems like this one as a group, instead of one at a time after they hurt. This post walks one small system through it. The system is the `orders` service from [Building an API with net/http in Go](/posts/go-http-api-stdlib/), with Postgres behind it ([Postgres with pgx and sqlc in Go](/posts/go-postgres-pgx-sqlc/)) and NATS JetStream for events. It is also the first post of a series about writing safer software, so I will explain each term as it comes.

> Defensive only. Every demo here is my own tiny Go program on `127.0.0.1`, standard library only. I re-ran them all with Go 1.27 (the first run used Go 1.26) and the outputs below are the real ones. Nothing targets a third party. The "database error" in demo 2 is invented text, not a real Postgres run.

## Four questions

Threat modeling sounds heavy, but it is four plain questions:

1. What are we building?
2. What can go wrong?
3. What are we going to do about it?
4. Did we do a good enough job?

These four are a widely used framing and I do not attribute them to anyone in particular. The rest of the post is just these questions applied to one service. Question 1 needs a picture.

## Question 1: draw the system

A threat model starts with a simple drawing of what talks to what. Here is the orders service:

```
 [ Client ] --1 HTTPS--> ( Orders API ) --2 SQL--> =Postgres=
  external      |            process   \--3 publish--> =NATS JetStream=
                |                                       |
   ===== trust boundary =====          ( Worker ) <--4--/
```

There are three kinds of shapes. `[ ]` is an external entity, something outside our control (the client). `( )` is a process, code we run. `= =` is a data store. The arrows are the flows of data between them: 1 is the client calling the API, 2 is the API talking to the database, 3 is the API publishing an event, 4 is the worker consuming it.

The line of equals signs is the part that matters most. It is a {{< term "trust-boundary" "trust boundary" >}}: the place where data passes from something we do not control to something we do. Here it sits where the internet meets the API. Everything that arrives on flow 1 is untrusted, however friendly the client looks. Flows 2 to 4 are internal, but they still cross from one process to another, so they deserve a second look too.

## Question 2: STRIDE, a checklist for "what can go wrong"

"What can go wrong?" is too open a question; people either freeze or list only the problems they already know. {{< term "stride" "STRIDE" >}} is a checklist that gives the question some structure. Its name is six letters, each one a kind of threat:

- **S**poofing: pretending to be someone else (a forged or stolen login token).
- **T**ampering: changing data you should not be able to change (the price in an order).
- **R**epudiation: doing something and later denying it, because nobody recorded who did it.
- **I**nformation disclosure: showing data to someone who should not see it (a raw database error).
- **D**enial of service: making the service unavailable for others, see {{< term "denial-of-service" "denial of service" >}} (a huge or very slow request).
- **E**levation of privilege: getting more rights than you were given (reading another user's order).

You go through the elements of your drawing, boxes and arrows, and ask the six questions of each. For the orders service I ended up with this table:

| Element | Threat | Mitigation |
|---|---|---|
| API, flow 1 | **S**: stolen or forged token | verify tokens, short expiry |
| API, flow 1 | **T**: client sets `price_cents` | allow-list input, server pricing (demo 1) |
| API | **R**: no record of who did what | structured logs with a request ID, see [Config, structured logging and errors in Go](/posts/go-config-logging-errors/) |
| API | **I**: raw errors reach the client | generic error plus log (demo 2) |
| API | **D**: huge or slow requests | body limit, timeouts (demo 3), [Rate limiting and caching in Go](/posts/go-rate-limiting-caching/) |
| API | **E**: user reads another user's order | check ownership on every read |
| Postgres | **I**: leaked credentials | secrets out of logs, least-privilege DB user |
| NATS | **T/E**: anyone can publish events | TLS and auth, see [JetStream in production: clustering, retention and security](/posts/nats-jetstream-production/) |
| NATS to worker | **T**: replayed or duplicate message | [Idempotency and the meaning of exactly-once in JetStream](/posts/nats-jetstream-idempotency/) |

A table like this is a list of questions with first answers, not a proof that the system is safe. I only reproduced and fixed three of these rows (T on the API, I on the API, D on the API), because they fit in a small local demo. The others are listed so the reader sees the whole shape; I did not run them here.

## Question 3: what we do about it, three demos

Each demo has the same shape: a naive server, then a fixed one, the same request sent to both. Both run from the same program in a scratch copy: `api naive <addr>` and `api fixed <addr>`, each on its own random loopback port (I write `127.0.0.1:8101` and `8102` below to keep the commands readable).

### Demo 1: tampering

The weakness is called {{< term "mass-assignment" "mass assignment" >}}: the server copies every field of the request into an internal object, so the client can set fields it should never control. The naive endpoint decodes the body straight into `Order`, so I send an order that sets its own price and status:

```
$ curl -s -X POST 127.0.0.1:8101/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"id":1,"sku":"book","qty":1,"price_cents":1,"status":"paid"}
```

The server accepted it as it was: price 1, status paid. The shop just sold a book for one cent.

The fixed version does three things differently. It decodes into a small input type with only two fields, `sku` and `qty` (an {{< term "allow-list" "allow-list" >}}: only these are accepted, and everything else is rejected). It looks the price up in a catalog on the server. And it sets the status itself. The same hostile request, then a normal one:

```
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":1,"price_cents":1,"status":"paid"}'
{"error":"bad request"}
$ curl -s -X POST 127.0.0.1:8102/orders -d '{"sku":"book","qty":2}'
{"id":1,"sku":"book","qty":2,"price_cents":1500,"status":"pending"}
```

The first request is refused, because `DisallowUnknownFields` makes the decoder fail when it sees `price_cents` or `status`. The second request has only the two allowed fields; the price 1500 comes from the server's catalog and the status is `pending`, set by the server. The principle is the same as in any trust boundary: the client says what it wants (`sku`, `qty`); the server decides everything else.

### Demo 2: information disclosure

When something fails inside the server, the quickest way to handle it is to send the error text back. The naive handler does exactly that with `err.Error()`. The error here is one I invented, in the style of a database driver error. Look at what it tells the client:

```
{"error":"query orders: ERROR: column \"total_cents\" does not exist (SQLSTATE 42703) [host=db.internal port=5432 user=orders_app]"}
```

That one line gives away a column name, the kind of database error (the SQLSTATE code), an internal host name and port, and the database user. None of it is a vulnerability by itself, but it is a free map of the inside of the system for someone who is looking.

The fixed handler writes the full details to the server's own log, and gives the client a fixed message plus a request ID the client can quote when asking for support:

```
{"error":"internal error","request_id":"a1b2c3"}
level=ERROR msg="request failed" path=/orders/1/total error="query orders: ERROR: ..." request_id=a1b2c3
```

The first line is what the client gets. The second line is the server log: the real error, tied to the same `request_id`, so the developer can find it. (The log line above is shortened with `...`; the real one is the full error text.) The ID is a constant in this demo; real code generates a new one per request.

### Demo 3: denial of service

Two ways to make a server unavailable cost the attacker almost nothing, so I tested both.

**A huge body.** I sent a 50 MiB body (all zeros) to an endpoint that just reads and discards its input. The naive server read all of it: `{"read":"52428800"}` (that is 50 times 1,048,576 bytes). With `http.MaxBytesReader` set to 1 MiB the same request is refused with `{"error":"body too large"}`.

**A very slow client.** Here the client is not big, just slow. A small Go probe opens a connection, sends half of an HTTP header, and then one more byte every 200 ms, never finishing. This is the {{< term "slowloris" "slowloris" >}} pattern: many such connections can hold all of a server's capacity while using almost none of the attacker's. The server without timeouts: `still open after 4s, giving up`, meaning the probe stopped waiting after 4 seconds. The server with `ReadHeaderTimeout` set to 1 second: `server closed after ~1.0s`. It stops waiting for a header that never completes. I did not measure memory or throughput, only whether the connection stayed open.

## Question 4: did we do a good job? Rank and revisit

You rarely have time to fix everything at once, so I rank threats by likelihood times impact, each from 1 to 3. This is my own judgment for this service, not a measurement:

| Threat | Likelihood | Impact | Score |
|---|---|---|---|
| Client-set price | 3 | 3 | 9 |
| Another user's order | 2 | 3 | 6 |
| Verbose errors | 3 | 2 | 6 |
| Slow or huge requests | 2 | 2 | 4 |

Fix the highest scores first. Then write the answer to question 4 down as a review date or trigger, so it actually happens. A plain template is enough:

```markdown
# Threat model: <system>
Scope / out of scope:
Diagram: (elements, flows, trust boundaries)
| Element | S | T | R | I | D | E | Mitigation | Owner | Status |
Top risks (L x I):
Review date / trigger (new feature, new dependency):
```

## Keeping the model alive

- **Redraw the diagram when the architecture changes.** An old model is worse than none, because it gives a feeling of safety about a system that no longer exists.
- **Threats on arrows are as real as threats on boxes.** The message between the API and the worker can be replayed or forged just as much as the API can be called with a bad body.
- **A mitigation without an owner is a wish.** Put a name and a status next to every row.
- **Tools exist.** OWASP Threat Dragon and the Microsoft Threat Modeling Tool are two I know of. I only mention them; I did not use them here.

## Exercise

Add an element to the diagram, for example a Redis cache between the API and Postgres, and write its six STRIDE rows. Which one scores highest?

## What's next

The next post is "The OWASP Top 10 in real code". STRIDE gave us six kinds of threat; the OWASP Top 10 is the industry's common list of names for them, and there we see each one as real Go code.
