+++
date = '2026-12-27T10:00:00+03:30'
draft = false
title = 'An HTTP server with node:http'
description = 'An HTTP server with node:http, real runs: routing by hand, JSON body limits with 413, timeouts, keep-alive, graceful shutdown and node:test.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "http", "node-http", "graceful-shutdown", "node-test"]
cover = { image = "/images/covers/node-http-server.png", alt = "An HTTP server with node:http", hiddenInSingle = true }
+++

In the previous post, [Streams and backpressure in Node.js](/posts/node-streams-backpressure/), we saw that data moves in chunks. An HTTP server is the first place that matters: the request and the response are streams. Here we build a small orders API with only the standard library, the same shape as [Building an API with net/http in Go](/posts/go-http-api-stdlib/). It leans on [the event loop](/posts/node-event-loop/), [async/await](/posts/node-promises-async-await/) and [error handling](/posts/node-errors-unhandled-rejections/).

> Node v20.13.1. The code is a local example (`app.js`, `main.js`, a few demo scripts); all outputs are copied from real runs on loopback.

## The server and manual routing

`http.createServer` gives you `req` (a readable stream) and `res` (a writable stream). There is no router, so I parse `req.url` and branch on method and path. Routes: `GET /health`, `POST /orders`, `GET /orders/:id`, with an in-memory `Map`. Handlers throw an `HttpError`; one `.catch` turns it into a response:

```js
const server = http.createServer((req, res) => {
  handle(req, res).catch((err) => {
    if (res.headersSent || res.destroyed) { res.destroy(); return; }
    const status = err instanceof HttpError ? err.status : 500;
    if (status === 500) console.error('internal error:', err.message);
    send(res, status, { error: status === 500 ? 'internal error' : err.message });
  });
});
```

Because `handle` is `async`, a thrown error is a rejected promise. Without that `.catch` it would be an {{< term "unhandled-rejection" "unhandled rejection" >}} and, as we saw, kill the process.

Real runs with curl (headers trimmed to the useful lines):

```text
$ curl -si -X POST -d '{"item":"book","qty":2}' 127.0.0.1:3000/orders
HTTP/1.1 201 Created
Location: /orders/c0b3df24
Connection: keep-alive
Keep-Alive: timeout=5

{"id":"c0b3df24","item":"book","qty":2}

$ curl -si 127.0.0.1:3000/orders/nope      ->  404 {"error":"order not found"}
$ curl -si -X DELETE .../orders/<id>       ->  405 with "Allow: GET"
$ curl -si -X POST -d '{bad' .../orders    ->  400 {"error":"invalid JSON"}
$ curl -si -X POST -d '{"item":"x"}' ...   ->  422 (qty missing)
$ curl -si 127.0.0.1:3000/boom             ->  500 {"error":"internal error"}
```

`/boom` throws on purpose; the log shows `internal error: unexpected bug`, the client gets a generic 500, and the next `/health` still answered. The global `fetch` saw the same 404 (`application/json; charset=utf-8`, `{ error: 'order not found' }`) and the 413 below.

## Reading a body with a size limit

A body arrives as chunks, so I count bytes and refuse to buffer more than 1024:

```js
req.on('data', (chunk) => {
  if (tooBig) return;
  size += chunk.length;
  if (size > max) { tooBig = true; reject(new HttpError(413, 'body too large')); return; }
  chunks.push(chunk);
});
```

My first version called `req.destroy()` immediately. That kills the socket, and curl got an empty reply (exit code 52), so no 413 was ever seen. The fix: write the 413 with `Connection: close`, and destroy the request on the response's `finish` event. Now a 5000-byte body gives:

```text
HTTP/1.1 413 Payload Too Large
Connection: close

{"error":"body too large"}
```

## Defaults you should know

Printed from a fresh server on Node 20.13.1:

```text
keepAliveTimeout  5000
headersTimeout    60000
requestTimeout    300000
timeout           0
maxHeadersCount   null
```

A {{< term "keep-alive" "keep-alive" >}} agent sending five requests used 1 TCP connection; with keep-alive off it used 5.

## A slow client

The classic {{< term "slowloris" "slowloris" >}} attack opens connections and never finishes the request. I wrote a raw `node:net` client that sends one header line every 300 ms against a server with `headersTimeout = 500`, `requestTimeout = 1000` and `connectionsCheckingInterval = 100` (all shortened for the demo):

```text
header chunks sent: 2 of 6 (one every 300 ms, headersTimeout 500 ms)
server replied: "HTTP/1.1 408 Request Timeout"
```

Four runs gave the same result. The machine was busy (load average above 2.5), so I report no durations. The request timeout was set too, but the headers timeout fired first; I did not test the body case separately.

## Graceful shutdown

On SIGTERM: stop accepting, close idle connections, let running requests finish, then exit. I added a `/slow` route that takes 1.5 s, started it with curl, then sent a real `kill -TERM`:

```js
process.on('SIGTERM', () => {
  server.close(() => process.exit(0));
  server.closeIdleConnections();
  setTimeout(() => process.exit(1), 5000).unref(); // safety net
});
```

```text
new request during shutdown: curl exit code 7   (connection refused)
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

The in-flight request finished, new ones were refused, and the exit code was 0. According to the docs, `close()` also closes idle connections since Node 19; calling `closeIdleConnections()` is explicit. This is the {{< term "graceful-shutdown" "graceful shutdown" >}} idea.

## Testing with node:test

`server.listen(0)` picks a free port, so tests never collide:

```js
before(async () => {
  server = createApp();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => { server.closeAllConnections(); server.close(); });
```

Three tests (health, create-then-get, and the 404/405/400/413 cases) with `fetch` and `node:assert`: `# pass 3`, `# fail 0`.

## Compared with Go

Go's `ServeMux` (since Go 1.22) gives you patterns like `GET /orders/{id}`, `PathValue`, and automatic 405 with an `Allow` header; here I wrote all of that by hand. Go has `http.MaxBytesReader` for the body limit and `Server.Shutdown` for the drain. Go runs each request in its own goroutine; Node handles all requests on one thread, so a blocking handler stalls every client.

## A few things to watch

- Always `.catch` an async handler; a rejection must become a 500, not a crash.
- Cap the body size, and answer before you destroy the socket.
- Keep `headersTimeout` and `requestTimeout` on; set your own `keepAliveTimeout` behind a load balancer.
- Handle SIGTERM and add a forced-exit timer.

## Exercise

Add `DELETE /orders/:id` (204, or 404) and a test that deletes an order and then expects 404 on `GET`. Then reject any `Content-Type` other than `application/json` with 415.

## What's next

The next post is "Building an API with Fastify".
