+++
date = '2027-01-06T10:00:00+03:30'
draft = false
title = 'Building an API with Fastify'
description = 'Building an API with Fastify, with real runs: JSON-schema validation, hooks, plugins, one error handler, pino logs, inject() tests, graceful shutdown.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "fastify", "api", "json-schema", "pino"]
cover = { image = "/images/covers/node-fastify-api.png", alt = "Building an API with Fastify", hiddenInSingle = true }
+++

In the previous post, [An HTTP server with node:http](/posts/node-http-server/), I wrote routing, body limits and error mapping by hand. Here I rebuild the same tiny orders API (`GET /health`, `GET /orders/:id`, `POST /orders`, in-memory store) with Fastify, and compare it with [Building an API with net/http in Go](/posts/go-http-api-stdlib/).

> Node v20.13.1, Fastify 5.12.7 (pino 10.4.0). The code is a local example (`app.js`, `main.js`, `app.test.js`); all outputs are copied from real runs on loopback. Fastify's `inject()` crashed at first with `ERR_REQUIRE_ESM`: the newest `light-my-request` pulls in an ES-module-only `cookie` that Node 20.13 cannot `require()`. I pinned `light-my-request` to 6.6.0 with an npm `overrides` entry; everything below ran with that pin.

## Routes and schemas

A route is a method, a path and an async function. Whatever you `return` is serialized to JSON. The `schema` option attaches a {{< term "json-schema" "JSON Schema" >}} to the params, body and response:

```js
app.post('/orders', {
  schema: {
    body: { type: 'object', required: ['item', 'qty'], additionalProperties: false,
      properties: { item: { type: 'string', minLength: 1 }, qty: { type: 'integer', minimum: 1 } } },
    response: { 201: orderSchema },
  },
}, async (request, reply) => { /* request.body is already valid here */ });
```

I ran a Fastify app with no custom error handling and sent bad payloads. This is Fastify's own error body:

```text
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body/qty must be integer"}
400 {"statusCode":400,"code":"FST_ERR_VALIDATION","error":"Bad Request","message":"body must have required property 'qty'"}
200 {"item":"book","qty":1}
```

The third request had an extra field `"extra": true` and `additionalProperties: false`, yet it got 200 and the field was silently removed. By default Fastify's validator strips unknown properties instead of rejecting them.

The response schema works the other way: the handler returned an object with a `secretNote` field, but `GET /orders/:id` sent only `{"id":"c298b17c","item":"pen","qty":3}`. Serialization keeps only what the schema lists.

## Hooks and the request id

{{< term "lifecycle-hook" "Hooks" >}} run at fixed stages. I printed the order for one POST: `onRequest -> preValidation -> preHandler -> onSend`. Mine add a {{< term "request-id" "request id" >}} on the way in and a header on the way out:

```js
genReqId: (req) => req.headers['x-request-id'] || randomUUID().slice(0, 8),
// ...
app.addHook('onRequest', async (request, reply) => { reply.header('x-request-id', request.id); });
app.addHook('onSend', async (request, reply, payload) => { reply.header('x-served-by', 'fastify-demo'); return payload; });
```

With `-H 'x-request-id: req-42'` the response carried `x-request-id: req-42`; without it, a generated one such as `53faa9e5`.

## Plugins and encapsulation

`app.register(plugin)` creates a child scope. The orders routes and their `orders` decorator live in `ordersPlugin`. A tiny check shows the boundary: a decorator added inside a plugin is visible inside it and not outside.

```text
{"inside":42} {"outside":"undefined"}
```

Hooks and decorators added in a plugin stay there.

## One place for errors

Handlers throw a `DomainError('not_found' | 'conflict' | 'invalid', ...)`. `setErrorHandler` maps all of them in one place, the same idea as `statusOf` in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/). Fastify's own 4xx errors (validation, bad JSON, 413) are mapped there too, and anything else becomes a generic 500. `setNotFoundHandler` covers unknown routes.

```text
GET  /orders/nope1                  -> 404 {"error":"order not found"}
GET  /orders/ab                     -> 400 {"error":"params/id must NOT have fewer than 3 characters"}
POST /orders {"item":"dup","qty":1} (twice) -> 409 {"error":"order already exists"}
POST /orders {"item":"forbidden"..} -> 422 {"error":"this item cannot be ordered"}
POST /orders (2000-byte item)       -> 413 {"error":"Request body is too large"}
GET  /nothing                       -> 404 {"error":"not found"}
GET  /boom                          -> 500 {"error":"internal error"}
```

`bodyLimit: 1024` gave the 413 with no stream code, and the 500 hides the real message from the client while the log keeps it.

## Logging with pino

Logging is built in: `Fastify({ logger: { level: process.env.LOG_LEVEL || 'info' } })`. Every line is {{< term "structured-logging" "structured JSON" >}} with the request id (I set `base: null` to drop the machine's pid and hostname):

```text
{"level":30,"time":1793078445637,"reqId":"32474994","req":{"method":"GET","url":"/health","host":"127.0.0.1:3000","remoteAddress":"127.0.0.1","remotePort":49603},"msg":"incoming request"}
{"level":50,"time":1793078445676,"reqId":"1c813ba7","err":{"type":"Error","message":"unexpected bug","stack":"Error: unexpected bug\n ...
```

With `LOG_LEVEL=warn` the same two requests (`/boom` and an unknown path) produced exactly one line, the level 50 error. Use `request.log` in handlers to keep the id.

## Tests without a port

`app.inject()` runs a request through the whole pipeline without opening a socket:

```js
const app = build({ logger: false });
const created = await app.inject({ method: 'POST', url: '/orders', payload: { item: 'book', qty: 2 } });
assert.equal(created.statusCode, 201);
```

One `node:test` test covers health, create, get, 404, 400, 422, and 409 (`# pass 1`, `# fail 0`).

## Graceful shutdown

```js
process.on('SIGTERM', async () => { app.log.info({ sig: 'SIGTERM' }, 'shutting down'); await app.close(); process.exit(0); });
```

I started a 1.5 s `/slow` request, then sent a real `kill -TERM`. A request sent during shutdown got curl exit code 7 (refused), the slow one finished, and the server exited with 0:

```text
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

This is the {{< term "graceful-shutdown" "graceful shutdown" >}} from the last post, now a single `close()` call. I added no forced-exit timer here; you should.

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

I made no performance claim and measured none.

## A few things to watch

- Unknown body fields are stripped, not rejected, by default.
- A schema is a contract: write response schemas so internal fields cannot leak.
- Throw domain errors in handlers and map them in one `setErrorHandler`.
- Check that the Fastify version and its dependencies support your Node version; here `inject()` needed a pin.

## Exercise

Add `DELETE /orders/:id` (204, or 404 through your domain error) and a `preHandler` hook that rejects a request without an `x-api-key` header with 401. Test both with `inject()`.

## What's next

The next post is "Testing in Node.js with node:test".
