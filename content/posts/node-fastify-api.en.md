+++
date = '2027-01-06T10:00:00+03:30'
draft = false
title = 'Building an API with Fastify'
description = 'Building an API with Fastify, with real runs: JSON-schema validation, hooks, plugins, one error handler, pino logs, inject() tests, graceful shutdown.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "fastify", "api", "json-schema", "pino"]
cover = { image = "/images/covers/node-fastify-api.png", alt = "Building an API with Fastify", hiddenInSingle = true }
+++

Look back at the orders API from [An HTTP server with node:http](/posts/node-http-server/). The business logic was tiny: store an order, fetch an order. But around it there was a lot of plumbing that I wrote by hand: splitting the URL, branching on the method, reading the body with a size counter, checking the types of the fields, turning errors into status codes, and closing the server politely. In a bigger API that plumbing is repeated for every route, and every copy is a chance for a mistake.

This is the problem a framework solves. **Fastify** is a Node.js web framework whose main idea is that you *describe* what a route accepts and returns, as data, and the framework does the checking, the parsing and the serializing for you. In this post I rebuild the same API (`GET /health`, `GET /orders/:id`, `POST /orders`, in-memory store) with Fastify, and at each step I point at the hand-written code it replaces. The Go version of the same exercise is [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Node v20.13.1, Fastify 5.12.7 (pino 10.4.0), taken from the demo's lockfile. The code is a local example (`app.js`, `main.js`, `app.test.js`); outputs are copied from real runs on loopback. One thing went wrong at first: Fastify's `inject()` (we use it for tests below) crashed with `ERR_REQUIRE_ESM`. The reason is that a recent `light-my-request` depends on an ES-module-only `cookie` package that Node 20.13 cannot `require()`. I pinned `light-my-request` to 6.6.0 with an npm `overrides` entry, and everything below ran with that pin. I checked again while writing this: a fresh unpinned install today (Fastify 5.12.8, light-my-request 6.8.0) still fails the same way on Node 20.13.1.

## Routes and schemas

A route in Fastify is a method, a path and an async function. Whatever the function returns is turned into JSON. The interesting part is the `schema` option. It attaches a {{< term "json-schema" "JSON Schema" >}} to the route: a small JSON document that describes what the params, the body and the response must look like. Fastify validates the incoming data against it before your function runs, so the function can trust its input:

```js
app.post('/orders', {
  schema: {
    body: { type: 'object', required: ['item', 'qty'], additionalProperties: false,
      properties: { item: { type: 'string', minLength: 1 }, qty: { type: 'integer', minimum: 1 } } },
    response: { 201: orderSchema },
  },
}, async (request, reply) => { /* request.body is already valid here */ });
```

This replaces the `if (typeof body.item !== 'string' ...)` lines from the hand-written server. To see what it does, I ran a small Fastify app with no custom error handling and sent three payloads: `qty` of the wrong type, `qty` missing, and a valid one with an extra field `"extra": true`. This is Fastify's own error body:

```text
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body/qty must be integer"}
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body must have required property 'qty'"}
200 {"item":"book","qty":1}
```

The first two are rejected with 400 and a message that names the field. The third one is the surprise. The schema says `additionalProperties: false`, yet the request was accepted with 200, and `extra` is gone from the result. By default Fastify's validator *removes* unknown properties instead of rejecting them. That is convenient, but you should know it: a client that mistypes a field name will not get an error, the field will simply disappear.

The response schema works in the other direction, and it is a safety feature. In my demo the handler returns an object with an extra `secretNote` field, but `GET /orders/:id` sent only `{"id":"c298b17c","item":"pen","qty":3}`. Serialization keeps only what the schema lists, so an internal field cannot leak by accident. (The id is random; you will see another.)

## Hooks and the request id

Every request goes through a fixed series of stages, and Fastify lets you run your own function at any of them. These are {{< term "lifecycle-hook" "hooks" >}}. To see the order I registered a hook on every stage in a scratch script and sent one `POST /orders`. This is not in the demo directory; I ran it in a scratch copy. The stages ran in this order:

```text
onRequest -> preParsing -> preValidation -> preHandler -> preSerialization -> onSend -> onResponse
```

Roughly: the request has arrived, the body is being read, the body is being validated, your handler is about to run, the response is about to be serialized, it is about to be sent, and it has been sent. My demo app uses two of them: one adds a {{< term "request-id" "request id" >}} to the response on the way in, and one adds a header on the way out:

```js
genReqId: (req) => req.headers['x-request-id'] || randomUUID().slice(0, 8),
// ...
app.addHook('onRequest', async (request, reply) => { reply.header('x-request-id', request.id); });
app.addHook('onSend', async (request, reply, payload) => { reply.header('x-served-by', 'fastify-demo'); return payload; });
```

A request id is a short unique label attached to one request, so that every log line about it can be found later. `genReqId` decides how it is made: take the client's `x-request-id` header if there is one, otherwise generate one. With `-H 'x-request-id: req-42'` the response carried `x-request-id: req-42`; without it, a generated one such as `53faa9e5`.

## Plugins and encapsulation

When an app grows, you want to split it into parts that do not step on each other. In Fastify the unit is a **plugin**: an async function that receives the app and adds routes, hooks and decorators (extra properties on the app). `app.register(plugin)` runs it in a new child scope. In the demo, the orders routes and the `orders` store live in `ordersPlugin`.

The point of the child scope is the boundary: what you add inside a plugin is visible inside it and not outside. A small check shows that: a decorator added inside a plugin is visible to the plugin's own route and not to a route outside:

```text
{"inside":42} {"outside":"undefined"}
```

The first route, inside the plugin, sees the decorator (`42`). The second, outside, finds its type is `"undefined"`. This is why plugins are safe to compose: one part cannot accidentally depend on, or overwrite, another part's internals.

## One place for errors

In the hand-written server there was one big `.catch`. Fastify has a proper place for it. Handlers throw a `DomainError('not_found' | 'conflict' | 'invalid', ...)`, which is just a small error class of our own that carries a code. `setErrorHandler` maps all of them to status codes in one place, the same idea as `statusOf` in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). Fastify's own 4xx errors (validation, bad JSON, body too large) are mapped there too, and anything else becomes a generic 500. `setNotFoundHandler` covers unknown routes. I sent one request for each case:

```text
GET  /orders/nope1                  -> 404 {"error":"order not found"}
GET  /orders/ab                     -> 400 {"error":"params/id must NOT have fewer than 3 characters"}
POST /orders {"item":"dup","qty":1} (twice) -> 409 {"error":"order already exists"}
POST /orders {"item":"forbidden"..} -> 422 {"error":"this item cannot be ordered"}
POST /orders (2000-byte item)       -> 413 {"error":"Request body is too large"}
GET  /nothing                       -> 404 {"error":"not found"}
GET  /boom                          -> 500 {"error":"internal error"}
```

Each line is one request and the response it got. `/orders/ab` fails the `minLength: 3` in the params schema, so that is a validation error. The `dup` item always gets the same id, so the second time it conflicts (409). `forbidden` is a business rule (422). Setting `bodyLimit: 1024` on the app gave the 413 with no stream code of my own, compare it with the byte-counting `readJson` from the last post. And the 500 hides the real message from the client while the log keeps it.

## Logging with pino

Fastify comes with a logger called pino. You turn it on with `Fastify({ logger: { level: process.env.LOG_LEVEL || 'info' } })`. Every log line is {{< term "structured-logging" "structured" >}}: one JSON object with named fields, so a log tool can filter by field instead of searching text. Each line carries the request id. (I set `base: null` to drop the process id and the host name from every line.) Here are two lines from the demo, shortened:

```text
{"level":30,"time":1793078445637,"reqId":"32474994","req":{"method":"GET","url":"/health","host":"127.0.0.1:3000","remoteAddress":"127.0.0.1","remotePort":49603},"msg":"incoming request"}
{"level":50,"time":1793078445676,"reqId":"1c813ba7","err":{"type":"Error","message":"unexpected bug","stack":"Error: unexpected bug\n ...
```

`level` is a number: 30 is info and 50 is error. `time` is a Unix time in milliseconds, and `reqId` is what ties all the lines of one request together. The second line is the `/boom` failure with its stack, which the client never saw. With `LOG_LEVEL=warn`, the same two requests (`/boom` and an unknown path) produced exactly one line, the level 50 error. Inside handlers, use `request.log` rather than a global logger, so the request id comes along automatically.

## Tests without a port

In the last post, tests started a real server on a free port. Fastify can skip even that: `app.inject()` pushes a fake request through the whole pipeline, hooks and validation included, without opening a socket:

```js
const app = build({ logger: false });
const created = await app.inject({ method: 'POST', url: '/orders', payload: { item: 'book', qty: 2 } });
assert.equal(created.statusCode, 201);
```

One `node:test` test covers health, create, get, 404, 400, 422 and 409; its summary was `# pass 1`, `# fail 0`. Because nothing is listening, these tests are fast and cannot collide on a port.

## Graceful shutdown

Shutting down is also shorter. `app.close()` stops accepting connections and waits for the running requests:

```js
process.on('SIGTERM', async () => { app.log.info({ sig: 'SIGTERM' }, 'shutting down'); await app.close(); process.exit(0); });
```

As before, I started a request to a `/slow` route that takes 1.5 seconds, then sent a real `kill -TERM`. A request sent during shutdown got curl exit code 7 (connection refused), the slow one finished, and the server exited with code 0:

```text
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

This is the {{< term "graceful-shutdown" "graceful shutdown" >}} from the last post, now one `close()` call. I added no forced-exit timer here; in production you should, as we did there.

## What Fastify replaced

| By hand in node:http | In Fastify |
|---|---|
| split `req.url`, branch on method | `app.get('/orders/:id')`, `request.params` |
| `readJson` with size counting | `request.body`, `bodyLimit` |
| `if (typeof ...)` checks | `schema.body` |
| `send()` helper, `JSON.stringify` | `return obj`, `schema.response` |
| one big `.catch` | `setErrorHandler` |
| `console.error` | `request.log`, pino |
| 5 s `server.close` dance | `app.close()` |

I made no performance claim and measured none; I chose Fastify here for the structure, not for speed.

## Framework defaults that bite

- **Unknown body fields are stripped, not rejected, by default.** As the `extra` field showed, a typo in a field name can disappear silently. Check the validator options if you need strict rejection.
- **A schema is a contract.** Write response schemas so internal fields cannot leak, as `secretNote` did not.
- **Throw domain errors in handlers and map them in one `setErrorHandler`.** Scattering `reply.code(...)` through the handlers makes the API inconsistent.
- **Check that the framework's dependencies support your Node version.** Here `inject()` needed a pin to work on Node 20.13.

## Exercise

Add `DELETE /orders/:id` (204, or 404 through your domain error) and a `preHandler` hook that rejects a request without an `x-api-key` header with 401. Test both with `inject()`.

## What's next

"Testing in Node.js with node:test" is the next post. `inject()` made tests cheap, so the test runner itself is what we look at next.
