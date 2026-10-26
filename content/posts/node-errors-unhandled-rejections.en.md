+++
date = '2026-12-11T10:00:00+03:30'
draft = false
title = 'Errors and unhandled rejections in Node.js'
description = 'Node.js errors with real runs: Error and cause chains, try/catch limits, EventEmitter errors, unhandled rejection modes and a fatal-error handler.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "errors", "unhandled-rejection", "javascript", "error-handling"]
cover = { image = "/images/covers/node-errors-unhandled-rejections.png", alt = "Errors and unhandled rejections in Node.js", hiddenInSingle = true }
+++

The previous post, [Promises and async/await in Node.js](/posts/node-promises-async-await/), ended with a rejection nobody handled. Here we look at errors properly: what an error is, where `try/catch` stops working, and what Node does with failures nobody caught. It builds on [the event loop](/posts/node-event-loop/). If you come from Go, [errors as values](/posts/go-functions-defer-errors/) is the other model, compared at the end.

> Everything was run with Node v20.13.1. The scripts are local examples; outputs are copied from real runs, with file paths and long stack traces shortened.

## Error objects and cause chains

An `Error` has `name`, `message` and `stack`. JavaScript lets you `throw` anything, but a thrown string has no stack:

```js
try { throw 'just a string'; } catch (x) { console.log(typeof x, x.stack); }
```

```text
string undefined
```

So always throw `Error` objects. A custom class can carry a `code`, and `new Error(msg, { cause })` keeps the original failure:

```js
class AppError extends Error {
  constructor(message, { code, status, cause } = {}) {
    super(message, { cause });
    this.name = 'AppError';
    this.code = code;
    this.status = status;
  }
}
```

Wrapping a `JSON.parse` failure twice and walking `err.cause`:

```text
AppError [E_START]: cannot start
  AppError [E_CONFIG]: bad config
    SyntaxError [-]: Expected property name or '}' in JSON at position 1
```

## Where try/catch does not reach

`try/catch` only sees code that runs inside it, synchronously, or after an `await`:

```js
try { setTimeout(() => { throw new Error('thrown in a timer'); }, 10); }
catch (e) { console.log('never printed'); }
```

The timer callback runs later, from the event loop, when the `try` is long gone. The process crashed with `Error: thrown in a timer`, then `Node.js v20.13.1`, exit code 1. Around `await` it works, and callback APIs use the error-first convention:

```text
caught around await: rejected promise
error-first: ENOENT undefined
```

(`fs.readFile` on a missing file: `err` is set, `data` is `undefined`.) Check `err` first, every time.

## EventEmitter: the unlistened error

Many Node objects are {{< term "event-emitter" "EventEmitters" >}}. Emitting `'error'` with no listener throws:

```js
em.on('data', (x) => console.log('data', x));
em.emit('data', 1);
em.emit('error', new Error('no listener for me'));
```

```text
data 1
node:events:497
      throw er; // Unhandled 'error' event
Error: no listener for me
Emitted 'error' event at: ...
Node.js v20.13.1
```

Exit code 1. With `em.on('error', ...)` the same emit printed `handled: with a listener` and the program kept running (exit 0). Servers and streams are emitters, so give them an `'error'` listener.

## Unhandled rejections and the modes

On Node 20 a rejected promise without a handler prints the error and stack, then `Node.js v20.13.1`, and exits with 1 before a 100 ms timer can fire. The `--unhandled-rejections` flag changes this. Same script, each mode:

| mode | behaviour | exit code |
|---|---|---|
| default | prints error, exits | 1 |
| `strict` | raises it as an uncaught exception | 1 |
| `throw` | throws, unless a handler exists | 1 |
| `warn` | prints `UnhandledPromiseRejectionWarning`, continues | 0 |
| `none` | silent, continues (`timer fired`) | 0 |

`warn` and `none` hide real bugs; keep the default.

`Promise.any` is related: when all inputs fail it rejects with an {{< term "aggregate-error" "AggregateError" >}} holding every reason:

```text
AggregateError true All promises were rejected
[ 'x', 'y' ]
```

## Handlers are for logging and exiting

You can listen for what nobody caught:

```js
process.on('unhandledRejection', (reason) => console.log('unhandledRejection:', reason.message));
process.on('uncaughtException', (err, origin) => console.log('uncaughtException:', err.message, origin));
Promise.reject(new Error('r1'));
setTimeout(() => { throw new Error('t1'); }, 10);
setTimeout(() => console.log('carried on (this is the danger)'), 50);
```

```text
unhandledRejection: r1
uncaughtException: t1 uncaughtException
carried on (this is the danger)
```

Exit code 0: the process survived. That is the trap. After an unexpected error your state may be half-updated, so these handlers should log, stop accepting work, and exit non-zero. A minimal version for an HTTP server:

```js
let shuttingDown = false;
function fatal(kind, err) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.error(`FATAL ${kind}:`, err && err.message);
  const t = setTimeout(() => process.exit(1), 5000); t.unref(); // hard deadline
  server.close(() => process.exit(1));
  server.closeAllConnections();
}
process.on('uncaughtException', (err) => fatal('uncaughtException', err));
process.on('unhandledRejection', (reason) => fatal('unhandledRejection', reason));
```

A forgotten rejection fired by a background job produced `FATAL unhandledRejection: background job failed` and the server process exited with 1. A supervisor (systemd, Kubernetes) restarts it.

## One place that maps errors to HTTP

Keep the decision in a single `errors.js`, the Node analogue of `statusOf` in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/):

```js
function statusOf(err) {
  if (err instanceof AppError) return [err.status, { error: err.expose ? err.message : 'internal error', code: err.code }];
  return [500, { error: 'internal error', code: 'E_INTERNAL' }];
}
```

`expose` is true only for statuses below 500, so 5xx details never reach the client. Real requests against the server on `127.0.0.1`:

```text
GET /          -> 422 {"error":"id is required","code":"E_VALIDATION"}
GET /?id=1     -> 200 {"user":"alice"}
GET /?id=9     -> 404 {"error":"user not found","code":"E_NOT_FOUND"}
GET /?id=boom  -> 500 {"error":"internal error","code":"E_INTERNAL"}
GET /?id=bug   -> 500 {"error":"internal error","code":"E_INTERNAL"}
```

`boom` is an {{< term "operational-error" "operational error" >}} (an `AppError` for a failing dependency); `bug` is a `TypeError` from a programmer mistake. Both are hidden from the client and logged; the difference is in how you treat them in review.

## Compared with Go

In Go, a function returns `error` as an ordinary value and the compiler-visible `if err != nil` makes you handle it at the call site; `panic` is for exceptional bugs. JavaScript throws, so a missing handler is invisible until runtime. Wrapping exists in both: `cause` here, `%w` there.

## A few things to watch

- Throw `Error` objects (or subclasses), never strings.
- `try/catch` does not cover callbacks and timers; it does cover `await`.
- Give every emitter an `'error'` listener.
- Global handlers log and exit non-zero; they do not recover.
- Map errors to HTTP in one place and hide 5xx messages.

Errors inside streams and `pipeline` are covered in the next post.

## Exercise

Add a `TimeoutError` to `errors.js` that maps to 504, and prove with `curl` that a handler awaiting a slow call returns it.

## What's next

The next post is "Streams and backpressure in Node.js".
