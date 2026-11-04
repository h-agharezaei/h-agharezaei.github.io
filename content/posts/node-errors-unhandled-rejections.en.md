+++
date = '2026-12-11T10:00:00+03:30'
draft = false
title = 'Errors and unhandled rejections in Node.js'
description = 'Node.js errors with real runs: Error and cause chains, try/catch limits, EventEmitter errors, unhandled rejection modes and a fatal-error handler.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "errors", "unhandled-rejection", "javascript", "error-handling"]
cover = { image = "/images/covers/node-errors-unhandled-rejections.png", alt = "Errors and unhandled rejections in Node.js", hiddenInSingle = true }
+++

Here is a surprise. You wrap a `setTimeout` call in a `try/catch`, and the callback inside throws an error. The `catch` does not run, and the whole process crashes. Nothing is wrong with your `try/catch`; it just cannot see that far. Knowing where `try/catch` stops working, and what Node does with a failure that nobody caught, decides whether one bug in one request takes your whole server down.

The core idea is simple. A `try/catch` only protects the code that runs *inside* it, on the current call stack, including code after an `await`. A failure that happens later, from a timer or an event, starts a new call stack where your `try` no longer exists. Node needs a rule for such failures, and the rule is harsh: if nobody handles them, the process stops. This post goes through where errors come from, where they get lost, how Node reacts, and what a server should do in the last moment.

[Promises and async/await in Node.js](/posts/node-promises-async-await/) ended with an unhandled rejection killing the process; here we look at errors properly, building on [the event loop](/posts/node-event-loop/). If you come from Go, [errors as values](/posts/go-functions-defer-errors/) is the other model, compared at the end.

> Everything was run with Node v20.13.1. The scripts are local examples; outputs are copied from real runs, with file paths and long stack traces shortened.

## Error objects and cause chains

An `Error` is an object with a `name`, a `message` and a `stack`, which is the list of function calls that led to the error. JavaScript lets you `throw` any value, even a string, but then you lose the stack:

```js
try { throw 'just a string'; } catch (x) { console.log(typeof x, x.stack); }
```

```text
string undefined
```

The thrown string has no `.stack`, so when it shows up in a log you cannot tell where it came from. Always throw `Error` objects.

You can also extend `Error` with your own class that carries extra fields, like a `code` for programs to check and a `status` for HTTP. And when you catch an error and throw a new one, pass the original as `cause`, so the first failure is not lost:

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

The demo wraps a failing `JSON.parse` in an `AppError('bad config')`, and wraps that in another one, `AppError('cannot start')`. Then it walks the `cause` links from the outside in and prints one line per level:

```text
AppError [E_START]: cannot start
  AppError [E_CONFIG]: bad config
    SyntaxError [-]: Expected property name or '}' in JSON at position 1
```

You read it from top to bottom: the program could not start, because the config was bad, because the JSON was invalid. Each level adds context and none loses the root cause. (`[-]` means the error had no `code`.)

## Where try/catch does not reach

`try/catch` sees code that runs inside it synchronously, and code after an `await` (because the function is resumed inside the same `try`). It does not see code that runs later from the event loop. This demo has a `try` around a timer whose callback throws:

```js
try { setTimeout(() => { throw new Error('thrown in a timer'); }, 10); }
catch (e) { console.log('never printed'); }
```

The `setTimeout` call itself succeeds immediately and the `try` ends. Ten milliseconds later the loop runs the callback on a fresh stack, with no `try` around it. Nothing catches the error, the process crashes with `Error: thrown in a timer` followed by `Node.js v20.13.1`, and the exit code is 1. (An **exit code** is the number a process returns to its parent; 0 means success and anything else means failure.)

The same file shows the two cases that do work: an `await`, and the older callback style where the error is the first argument ("error-first"):

```text
caught around await: rejected promise
error-first: ENOENT undefined
```

The first line is a `try/catch` around `await` of a rejected promise, and it catches. The second is `fs.readFile` on a file that does not exist: the callback receives `err` with code `ENOENT`, and `data` is `undefined`. Check `err` first, every time.

## EventEmitter: the unlistened error

Many Node objects, such as servers and streams, are {{< term "event-emitter" "EventEmitters" >}}: they announce things by emitting named events, and you attach listeners. One event name is special. If something emits `'error'` and nobody listens, Node throws it. This script emits a normal event and then an `'error'` with no listener:

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

The `data` event was fine. The `error` event had no listener, so Node threw the error, which crashed the process (exit code 1). I cut most of the stack lines. In a second script with `em.on('error', ...)` the same emit printed `handled: with a listener`, the program printed `still running`, and the exit code was 0. Give every emitter you own an `'error'` listener.

## Unhandled rejections and the modes

We saw the promise version in the previous post. On Node 20 a rejected promise with no handler prints the error and stack, then `Node.js v20.13.1`, and exits with code 1 before a 100 ms timer can fire. That is the {{< term "unhandled-rejection" "unhandled rejection" >}} behaviour. The `--unhandled-rejections` flag changes it. I ran the same script (a rejected promise plus a timer that prints `timer fired`) in every mode:

| mode | behaviour | exit code |
|---|---|---|
| default | prints error, exits | 1 |
| `strict` | raises it as an uncaught exception | 1 |
| `throw` | throws, unless a handler exists | 1 |
| `warn` | prints `UnhandledPromiseRejectionWarning`, continues | 0 |
| `none` | silent, continues (`timer fired`) | 0 |

According to the Node.js docs, the default mode is `throw`, which is why the first and third rows behave the same. In `warn` and `none` the program keeps running (the timer fired in both), and in `none` there is not even a message. These two modes hide real bugs, so keep the default.

`Promise.any` is related: when all its inputs fail it rejects with an {{< term "aggregate-error" "AggregateError" >}} that holds every reason. The demo prints its name, whether it really is an `AggregateError`, its message and the list of reasons:

```text
AggregateError true All promises were rejected
[ 'x', 'y' ]
```

## Handlers are for logging and exiting

Node lets you listen for failures that nobody caught: `process.on('unhandledRejection', ...)` for promises, and `process.on('uncaughtException', ...)` for thrown errors. This script sets both and then causes one of each:

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

Both handlers ran, and the process carried on and exited with code 0. That is the trap. It feels friendly, but after an unexpected error your program may be half-updated: a counter changed, a file half written, a connection in a strange state. Continuing as if nothing happened can corrupt data. So these handlers should do three things: log the error, stop accepting new work, and exit with a non-zero code. Here is a minimal version for an HTTP server:

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

What it does: the flag makes sure it runs once. It logs the failure. The timer is a hard deadline: if closing takes more than 5 seconds, exit anyway (`unref()` means this timer alone does not keep the process alive). `server.close` stops accepting new connections and exits when the old ones are done, and `closeAllConnections` closes the remaining ones instead of waiting for them.

In the demo server, a background job fires a forgotten rejection after 600 ms. It printed `FATAL unhandledRejection: background job failed` and the server process exited with code 1. In production a supervisor (systemd, Kubernetes) notices and starts a fresh process.

## One place that maps errors to HTTP

Back in the request handler there is another question: what does the client see when something fails? Keep that decision in one place. This `errors.js` has a base `AppError` plus `NotFoundError` and `ValidationError`, and a function that maps any error to a status and a body. It is the Node analogue of `statusOf` in [Config, structured logging and errors in Go](/posts/go-config-logging-errors/):

```js
function statusOf(err) {
  if (err instanceof AppError) return [err.status, { error: err.expose ? err.message : 'internal error', code: err.code }];
  return [500, { error: 'internal error', code: 'E_INTERNAL' }];
}
```

`expose` is true only for statuses below 500, so details of server-side failures never reach the client. I sent real requests to the demo server on `127.0.0.1` (random port) with `curl`, and the status code is in brackets:

```text
GET /          -> {"error":"id is required","code":"E_VALIDATION"} [422]
GET /?id=1     -> {"user":"alice"} [200]
GET /?id=9     -> {"error":"user not found","code":"E_NOT_FOUND"} [404]
GET /?id=boom  -> {"error":"internal error","code":"E_INTERNAL"} [500]
GET /?id=bug   -> {"error":"internal error","code":"E_INTERNAL"} [500]
```

The last two are different kinds of failure. `boom` is an {{< term "operational-error" "operational error" >}}: an expected failure, here a database that refuses the connection, wrapped in an `AppError`. `bug` is a `TypeError` caused by a programmer mistake (`null.x`). In the demo both are logged on the server (`request failed: db password wrong` and `request failed: Cannot read properties of null (reading 'x')`) and both give the client the same hidden 500, and the server stayed up. The difference is in what you do about them: an operational error is something your code planned for, while a bug means your assumptions were wrong, so the state of the process is suspect and a restart is the safest reaction.

## Compared with Go

In Go, a function returns an `error` as an ordinary value and the `if err != nil` at the call site makes you deal with it there. `panic` is for bugs. JavaScript throws, so a missing handler is invisible until the failure happens at runtime. Wrapping exists in both languages: `cause` here, `%w` there.

## Errors that slip through

- **Throwing strings or plain objects.** They have no stack. Throw `Error` objects or subclasses.
- **Trusting `try/catch` around callbacks and timers.** It does not cover them. It does cover `await`.
- **An emitter without an `'error'` listener.** One emitted error crashes the process.
- **Using global handlers to recover.** They are for logging and exiting non-zero, not for carrying on.
- **Scattering error to HTTP decisions across handlers.** Map in one place and hide 5xx messages.

## Exercise

Add a `TimeoutError` to `errors.js` that maps to 504, and prove with `curl` that a handler awaiting a slow call returns it.

## What's next

"Streams and backpressure in Node.js": errors inside streams and `pipeline` are covered there.
