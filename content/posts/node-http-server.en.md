+++
date = '2026-12-27T10:00:00+03:30'
draft = false
title = 'An HTTP server with node:http'
description = 'An HTTP server with node:http, real runs: routing by hand, JSON body limits with 413, timeouts, keep-alive, graceful shutdown and node:test.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "http", "node-http", "graceful-shutdown", "node-test"]
cover = { image = "/images/covers/node-http-server.png", alt = "An HTTP server with node:http", hiddenInSingle = true }
+++

What does a web server really do? It waits for a message from a client, reads it, decides what the client wants, and sends back a message. Everything else, such as frameworks, routers and middleware, is a convenience on top of that loop. Before using Fastify in the next post, I want to build the loop by hand with only what ships with Node.js, so that later you know what the framework is doing for you.

The server is a small orders API with the same shape as [Building an API with net/http in Go](/posts/go-http-api-stdlib/): create an order, fetch an order, a health check. Along the way we will meet the problems every real server has to solve: a client that sends a huge body, a client that sends garbage, a client that is slow on purpose, and a deploy that must not cut requests in half.

This is where the chunked data from [Streams and backpressure in Node.js](/posts/node-streams-backpressure/) starts to matter, because the request is a readable stream and the response is a writable stream. The code leans on [the event loop](/posts/node-event-loop/), [async/await](/posts/node-promises-async-await/) and [error handling](/posts/node-errors-unhandled-rejections/).

> Node v20.13.1. The code is a local example (`app.js`, `main.js` and a few demo scripts); every output below is copied from real runs on loopback (127.0.0.1) with a random free port. I show port 3000 in the commands to keep them short.

## The server and manual routing

`http.createServer` takes one function, and Node calls it once for every incoming request with two objects: `req` (the request, a readable stream) and `res` (the response, a writable stream). There is no router. To decide what to do, I read `req.url` and look at the method and the path myself.

The routes are `GET /health`, `POST /orders` and `GET /orders/:id`, and the orders live in an in-memory `Map` (so they disappear when the server restarts). To keep the handlers simple, they *throw* an `HttpError` carrying a status code when something is wrong, and one place at the top turns that into a response:

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

Why the `.catch`? Because `handle` is an `async` function, so a thrown error becomes a rejected promise. If nobody handled it, it would be an {{< term "unhandled-rejection" "unhandled rejection" >}}, and as we saw in the previous posts that kills the process, so one bad request would take every other client down. The last line of the `.catch` has one more rule: an unexpected error (status 500) is logged on the server, but the client only sees the words "internal error", never the real message.

Let us try it. The commands are `curl` against the running server (`-s` is silent, `-i` prints the response headers, and I trimmed the headers to the useful lines):

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

The first command creates an order and the server answers `201 Created`, with a `Location` header telling the client where the new order lives. The id (`c0b3df24`) is random, so you will see a different one. The other lines show what each kind of mistake looks like to the client:

- **404**: no such order (or no such route).
- **405**: the path exists but not for this method, and the `Allow` header says which method is accepted.
- **400**: the body is not valid JSON.
- **422**: the JSON is valid but the content is not (here `qty` is missing).
- **500**: a bug on our side.

`/boom` is a route I added that throws on purpose. The server log showed `internal error: unexpected bug`, the client got the generic 500, and the next request to `/health` was still answered, so one failure did not stop the server. I re-ran all of these in a scratch copy for this post and the status codes and bodies matched.

## Reading a body with a size limit

Now the first real danger. The body of a request arrives in chunks, and a client can send as many as it likes. If you collect everything, one client can fill your memory. So the code counts bytes as chunks arrive and refuses to keep more than 1024:

```js
req.on('data', (chunk) => {
  if (tooBig) return;
  size += chunk.length;
  if (size > max) { tooBig = true; reject(new HttpError(413, 'body too large')); return; }
  chunks.push(chunk);
});
```

The status for "your body is too big" is `413 Payload Too Large`. There is one catch that is easy to miss. The natural move, destroying the request as soon as the limit is exceeded (`req.destroy()`), also destroys the connection. Then the client never receives your 413. In my first version I did exactly that, and `curl` printed an empty reply (exit code 52) instead of a status. The fix is to write the 413 first, tell the client the connection will close (`Connection: close`), and destroy the request only after the response has been flushed, on the response's `finish` event:

```js
if (status === 413) {
  res.on('finish', () => req.destroy());
  return send(res, status, { error: err.message }, { Connection: 'close' });
}
```

Now a 5000-byte body gives a proper answer:

```text
HTTP/1.1 413 Payload Too Large
Connection: close

{"error":"body too large"}
```

## Defaults you should know

Node's HTTP server has a few timeouts that matter for safety. This is what a fresh server prints on Node 20.13.1 (times are in milliseconds):

```text
keepAliveTimeout  5000
headersTimeout    60000
requestTimeout    300000
timeout           0
maxHeadersCount   null
```

In plain words:

- `keepAliveTimeout`: how long an idle connection is kept open for the next request, 5 seconds.
- `headersTimeout`: how long the client has to finish sending the request headers, 60 seconds.
- `requestTimeout`: how long the client has to send the whole request, 300 seconds.
- `timeout`: the old socket inactivity timeout; 0 means disabled.
- `maxHeadersCount`: no limit on the number of headers (`null`).

The first one deserves a picture. Opening a TCP connection costs a round trip, so HTTP lets the client reuse one connection for several requests. That is {{< term "keep-alive" "keep-alive" >}}. In the demo, a client using a keep-alive agent sent five requests over 1 TCP connection; with keep-alive off, the same five requests used 5 connections.

## A slow client

Timeouts exist because of clients that are slow on purpose. The classic example is the {{< term "slowloris" "slowloris" >}} attack: open many connections and send each request very slowly, so the server keeps all those connections occupied and has no room for real users.

To test the defence, I wrote a raw client with `node:net` that sends the request one header line at a time, one line every 300 ms. The server it talks to has shortened timeouts so the demo is fast: `headersTimeout = 500`, `requestTimeout = 1000` and `connectionsCheckingInterval = 100` (how often Node looks for expired requests). The client prints how many pieces it managed to send and the first line of the server's reply:

```text
header chunks sent: 2 of 6 (one every 300 ms, headersTimeout 500 ms)
server replied: "HTTP/1.1 408 Request Timeout"
```

The server gave up before the headers were complete and answered `408 Request Timeout`. The machine was busy while I re-ran this (the 1-minute load average was above 20), and the number of chunks sent changed between runs: 2 in one run, 3 in another. The 408 was the same both times. That is why the demo prints the count but I do not claim a duration. Both timeouts were set, but the headers timeout is the one that fired first, and I did not test the body case separately.

## Graceful shutdown

When you deploy a new version, the old process receives `SIGTERM` ("please stop"). If it exits at once, every request in progress is cut. The polite way is {{< term "graceful-shutdown" "graceful shutdown" >}}: stop accepting new connections, close the idle ones, let the running requests finish, then exit.

To test it I added a `/slow` route that takes 1.5 seconds, started a `curl` against it, and 0.5 seconds later sent a real `kill -TERM` to the server. The handler in `main.js` is:

```js
let shuttingDown = false;
process.on('SIGTERM', () => {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log('SIGTERM: closing');
  server.close(() => { console.log('server closed, exiting 0'); process.exit(0); });
  server.closeIdleConnections();
  setTimeout(() => { console.log('forced exit'); process.exit(1); }, 5000).unref(); // safety net
});
```

`server.close` stops accepting new connections and calls back when all existing ones have finished. The timer is a safety net: if something hangs for 5 seconds, exit anyway (`unref()` means the timer alone does not keep the process alive). The script then tried a new request while the server was shutting down:

```text
new request during shutdown: curl exit code 7   (connection refused)
{"status":"slow done"} (HTTP 200)
server exit code: 0
```

The three lines say: a new request was refused (curl's exit code 7 means it could not connect), the request already in flight still finished with its answer, and the server exited with code 0. According to the Node docs, `close()` also closes idle connections since Node 19; calling `closeIdleConnections()` makes it explicit.

## Testing with node:test

Last, a server without tests is a hope. The trick for testing an HTTP server is `server.listen(0)`: port 0 asks the operating system for a free port, so tests never collide with each other or with another running server. We will look at `node:test` itself in a later post; here is just how it is used:

```js
before(async () => {
  server = createApp();
  await new Promise((r) => server.listen(0, '127.0.0.1', r));
  base = `http://127.0.0.1:${server.address().port}`;
});
after(() => { server.closeAllConnections(); server.close(); });
```

`before` starts the server and remembers its address, and `after` closes it. Three tests (health, create-then-get, and the 404/405/400/413 cases) use the built-in `fetch` and `node:assert`. When I ran them, the summary was `# tests 3`, `# pass 3`, `# fail 0`.

## Compared with Go

Go's `ServeMux` (since Go 1.22) understands patterns like `GET /orders/{id}`, gives you `PathValue`, and answers 405 with an `Allow` header by itself; here I wrote all of that by hand. Go has `http.MaxBytesReader` for the body limit and `Server.Shutdown` for the drain. Another difference is the concurrency model: Go runs each request in its own goroutine, while Node handles all requests on one thread, so a handler that blocks stalls every client.

## Before it goes to production

- **Always `.catch` an async handler.** A rejected promise must become a 500 for that request, not a crash of the whole process.
- **Cap the body size, and answer before you destroy the socket.** Otherwise a client either exhausts your memory or gets an empty reply instead of an error.
- **Keep `headersTimeout` and `requestTimeout` on.** They are your defence against slow clients. Behind a load balancer, also set `keepAliveTimeout` yourself to match it.
- **Handle SIGTERM and add a forced-exit timer.** Without the timer, one stuck connection can keep the old process alive forever.

## Exercise

Add `DELETE /orders/:id` (204, or 404) and a test that deletes an order and then expects 404 on `GET`. Then reject any `Content-Type` other than `application/json` with 415.

## What's next

"Building an API with Fastify" is the next post. Everything written by hand here, from routing to validation and shutdown, is handed to a framework there.
