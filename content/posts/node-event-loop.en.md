+++
date = '2026-11-11T10:00:00+03:30'
draft = false
title = 'The Node.js event loop'
description = 'The Node.js event loop explained with real runs: phases, nextTick vs promises vs timers, blocking, microtask starvation and the libuv thread pool.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "event-loop", "javascript", "async", "libuv"]
cover = { image = "/images/covers/node-event-loop.png", alt = "The Node.js event loop", hiddenInSingle = true }
+++

This post opens the Node.js series. If you write Node.js code in production, the most useful mental model is the {{< term "event-loop" "event loop" >}}: your JavaScript runs on one thread, and everything that waits (timers, sockets, files) is handed to the system and comes back as a callback. If you come from Go, compare it with [goroutines and channels](/posts/go-goroutines-channels/) and the [Go scheduler](/posts/go-scheduler-gc-internals/): there the runtime spreads your code over many threads, here your JavaScript does not run in parallel.

> Everything below was run with Node v20.13.1. Scripts are local examples; outputs are copied from real runs.

## The phases, in plain words

Each turn of the loop (which {{< term "libuv" "libuv" >}} implements) goes through these phases:

1. **timers**: run expired `setTimeout`/`setInterval` callbacks.
2. **pending callbacks**: a few deferred system callbacks.
3. **poll**: wait for I/O (sockets, files) and run its callbacks.
4. **check**: run `setImmediate` callbacks.
5. **close**: run `close` callbacks, such as a socket closing.

Between callbacks, Node drains `process.nextTick` first and then the promise {{< term "microtask" "microtask" >}} queue.

## Who runs first?

```js
const fs = require('fs');
console.log('1 sync start');
setTimeout(() => console.log('6 setTimeout 0'), 0);
setImmediate(() => console.log('7 setImmediate'));
fs.readFile(__filename, () => console.log('8 readFile callback'));
process.nextTick(() => console.log('3 nextTick'));
Promise.resolve().then(() => console.log('4 promise then'));
queueMicrotask(() => console.log('5 queueMicrotask'));
console.log('2 sync end');
```

Output:

```text
1 sync start
2 sync end
3 nextTick
4 promise then
5 queueMicrotask
6 setTimeout 0
7 setImmediate
8 readFile callback
```

Synchronous code first, then `nextTick`, then microtasks, then the loop phases. The order of 6, 7 and 8 is what I saw in this run, and the timeout/immediate pair is not guaranteed at top level, as the next section shows.

## setTimeout(0) vs setImmediate

At the top level of a script the order depends on how fast the process reaches the loop. I ran this 12 times:

```js
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
```

Result: 10 times `immediate timeout`, 2 times `timeout immediate`. Do not rely on either. Inside an I/O callback the order is fixed, because after poll comes check:

```js
fs.readFile(__filename, () => {
  setTimeout(() => console.log('timeout'), 0);
  setImmediate(() => console.log('immediate'));
});
```

In 6 of 6 runs: `immediate timeout`.

## Blocking the loop

```js
const t0 = Date.now();
setTimeout(() => console.log('timer callback ran, after the loop finished:', done), 10);
let done = false;
console.log('busy loop starts');
while (Date.now() - t0 < 200) {}
done = true;
console.log('busy loop ends');
```

```text
busy loop starts
busy loop ends
timer callback ran, after the loop finished: true
```

A 10 ms timer waited for a 200 ms synchronous loop. In a server, that is every other request waiting. I will not quote latency numbers here, because the machine was busy while I tested.

## Microtask starvation

Microtasks are drained completely before the loop moves on, so a chain of microtasks can block timers. With a bounded counter:

```js
let n = 0;
setTimeout(() => console.log('timer ran, microtasks so far:', n), 0);
function spin() { if (++n < 100000) queueMicrotask(spin); }
spin();
```

```text
timer ran, microtasks so far: 100000
```

The timer only ran after all 100000 microtasks. With an unbounded version the timer would never run.

## The libuv thread pool

Not everything is single-threaded: some work (`crypto.pbkdf2`, many `fs` calls, DNS lookups via `dns.lookup`) goes to a {{< term "thread-pool" "thread pool" >}} whose default size is 4, according to the Node docs (`UV_THREADPOOL_SIZE`). I started 8 `pbkdf2` jobs and printed each completion time divided by the first one:

```text
default (4):        1.0 1.0 1.0 1.0 2.1 2.1 2.1 2.1
UV_THREADPOOL_SIZE=8: 1.0 1.1 1.1 1.1 1.1 1.1 1.1 1.1
UV_THREADPOOL_SIZE=1: 1.0 2.0 3.2 4.3 5.6 6.5 7.5 8.5
```

With 4 threads the jobs finish in two batches of four. With 8 there is one batch, with 1 they run one by one. The ratios are approximate and depend on the machine.

## Measuring lag

`perf_hooks.monitorEventLoopDelay` samples how late the loop wakes up. I blocked it for 300 ms and checked the histogram:

```text
max lag > 250ms: true
min lag < 100ms: true
```

Absolute values are machine-dependent, so I only show the comparison. In production, export the p99 of this histogram as a metric.

## A few things to watch

- Never run heavy synchronous work (big JSON parsing, `*Sync` fs calls, CPU loops) in a request handler.
- `process.nextTick` and recursive microtasks can starve I/O and timers.
- Do not depend on `setTimeout(0)` vs `setImmediate` order at top level.
- The thread pool is shared by `fs`, `crypto` and DNS, so slow jobs can delay each other. CPU work belongs in worker threads.

## Exercise

Write a script with a `setInterval` of 50 ms and a synchronous loop of 300 ms started after 120 ms. Predict how many ticks are printed, then run it and use `monitorEventLoopDelay` to confirm the gap.

## What's next

The next post is "Modules: ESM and CommonJS".
