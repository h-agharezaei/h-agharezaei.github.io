+++
date = '2026-11-11T10:00:00+03:30'
draft = false
title = 'The Node.js event loop'
description = 'The Node.js event loop explained with real runs: phases, nextTick vs promises vs timers, blocking, microtask starvation and the libuv thread pool.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "event-loop", "javascript", "async", "libuv"]
cover = { image = "/images/covers/node-event-loop.png", alt = "The Node.js event loop", hiddenInSingle = true }
+++

Here is a small program. It asks for a timer to fire after 10 milliseconds, and then it runs a loop that keeps the program busy for 200 milliseconds. When does the timer callback run? After 10 ms, as requested? No. It runs after about 200 ms, and only once the loop has finished. The timer did not do anything wrong: nobody was free to run its callback.

To understand why, you need one idea, and it is the most useful mental model for anyone who writes Node.js. Your JavaScript runs on **one thread**, one thing at a time. Anything that has to wait (a timer, a socket, a file read) is handed to the operating system, and when the result is ready it comes back as a callback that waits for its turn. The thing that hands out those turns is the {{< term "event-loop" "event loop" >}}.

Think of a small shop with a single cashier. The cashier serves one customer at a time, and a customer who needs something from the back room is not allowed to block the counter: the cashier writes down the request, sends someone to fetch it, and serves the next customer. When the item arrives, it joins the queue. This works very well, as long as no single customer holds the cashier for ten minutes. That is the whole post: how the queue works, and what happens when someone holds the counter.

If you come from Go, compare this with [goroutines and channels](/posts/go-goroutines-channels/) and the [Go scheduler](/posts/go-scheduler-gc-internals/). There the runtime spreads your code over several threads. Here your JavaScript never runs in parallel with itself.

> Everything below was run with Node v20.13.1 on macOS. The scripts are local examples and the outputs are copied from real runs. Where a result can differ from run to run, I say so.

## One turn of the loop

The loop is a cycle. Each turn goes through a fixed list of **phases**, and each phase has its own queue of callbacks. The loop itself is implemented by a C library called {{< term "libuv" "libuv" >}}, which Node.js uses. The phases are:

1. **timers**: run the `setTimeout` and `setInterval` callbacks whose time has come.
2. **pending callbacks**: run a few deferred callbacks from the operating system. You will rarely think about this one.
3. **poll**: wait for I/O (sockets, files) and run its callbacks. If nothing is ready, the loop can sleep here.
4. **check**: run the `setImmediate` callbacks.
5. **close**: run `close` callbacks, for example when a socket is closed.

There are two more queues, and they are not phases. After the current script finishes, and again after every single callback, Node empties the `process.nextTick` queue first and then the promise {{< term "microtask" "microtask" >}} queue. A microtask is a tiny job that must run right after the current code, before the loop moves on. `.then(...)` callbacks of promises are microtasks; so is anything you pass to `queueMicrotask`.

Putting it together:

```text
script runs (synchronous code)
  -> nextTick queue, then microtask queue
  -> loop turn: timers -> pending -> poll -> check -> close
       (after each callback: nextTick queue, then microtask queue)
  -> next turn
```

## Who runs first?

Let's test this picture. The script below schedules one of each kind of work. The numbers in the messages are the order I expect from the picture above:

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

The output matches the numbers. Line by line:

- **1 and 2**: the script's own synchronous code always finishes first. Everything else is only *scheduled* while it runs, nothing is executed yet.
- **3, 4, 5**: when the script ends, Node empties the `nextTick` queue and then the microtask queue, in the order the callbacks were added.
- **6**: now the loop starts, and the first phase is timers. A timer of 0 ms is already due. (According to the Node.js docs, a delay of 0 is treated as 1 ms.)
- **7**: the check phase runs `setImmediate`.
- **8**: the file read was handed to a worker thread (more on that later), and its callback is only delivered when the loop polls and finds the result ready. It usually arrives after the first few steps.

One honest warning: lines 6, 7 and 8 are the order I saw, but 6 and 7 are not guaranteed at the top level of a script. The next section shows why.

## Microtasks run between callbacks

The picture says "after each callback, drain the queues". Here is a script that checks it. Two timers are due together, and the first one schedules a promise callback and a `nextTick` callback. This one is not in the original demo folder; I ran it in a scratch copy:

```js
setTimeout(() => {
  console.log('timer 1');
  Promise.resolve().then(() => console.log('  promise from timer 1'));
  process.nextTick(() => console.log('  nextTick from timer 1'));
}, 0);
setTimeout(() => console.log('timer 2'), 0);
```

```text
timer 1
  nextTick from timer 1
  promise from timer 1
timer 2
```

Both timers are due at the same time, yet `timer 2` waits until the `nextTick` and promise callbacks that `timer 1` created have run. So microtasks do not wait for the end of the phase; they run after every callback. (Node 11 introduced this behaviour; older versions drained these queues only after the whole phase.) And `nextTick` goes before promises, even though the promise was created first.

## setTimeout(0) versus setImmediate

Both mean "as soon as possible", so which comes first? From the main script it depends on how quickly the process reaches the loop. If about a millisecond or more has passed by then, the timer is already due and runs first; otherwise the loop goes on to the check phase first. Here is the script:

```js
setTimeout(() => console.log('timeout'), 0);
setImmediate(() => console.log('immediate'));
```

I ran it 20 times in a row for this version of the post: `immediate timeout` came 15 times and `timeout immediate` 5 times. The split changes from run to run and with the load on the machine; the only thing to take from it is that you cannot rely on either order.

Inside an I/O callback the order is fixed. The loop is in the poll phase at that moment, and the next phase after poll is check, so `setImmediate` always wins:

```js
fs.readFile(__filename, () => {
  setTimeout(() => console.log('timeout'), 0);
  setImmediate(() => console.log('immediate'));
});
```

This printed `immediate timeout` in 10 of 10 runs.

## Blocking the loop

Now back to the opening puzzle. This script sets a 10 ms timer, then spins in a loop until 200 ms have passed:

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

The timer was due after 10 ms, but the event loop cannot start a turn while our synchronous code is still running. So the callback ran only after the loop ended, and `done` was already `true` by then. That is exactly what the single cashier does: nobody else is served while he is busy. In a server, every other request waits like this timer did. I will not quote latency numbers, because the machine was busy while I tested.

## Microtask starvation

A related problem: because the microtask queue is emptied *completely* before the loop moves on, a microtask that keeps scheduling another microtask never lets the loop continue. To see it safely, this script stops after 100,000 steps:

```js
let n = 0;
setTimeout(() => console.log('timer ran, microtasks so far:', n), 0);
function spin() { if (++n < 100000) queueMicrotask(spin); }
spin();
```

```text
timer ran, microtasks so far: 100000
```

The timer was due almost at once, but it ran only after all 100,000 microtasks. If the counter had no limit, the timer would never run, and the process would look frozen even though it is working all the time. (The demo file also prints `sync end` before this line; I left it out of the listing.)

## Not everything is single-threaded

I said JavaScript runs on one thread, but Node as a whole does not. Some operations are handed to a small group of helper threads called the {{< term "thread-pool" "thread pool" >}}: `crypto.pbkdf2`, many `fs` calls, and `dns.lookup`. Your JavaScript is still single-threaded, but these jobs run in the background and report back through the loop. According to the Node.js docs, the pool has 4 threads by default, and you can change it with the `UV_THREADPOOL_SIZE` environment variable.

To see the pool, the next script starts 8 `pbkdf2` jobs at once (a deliberately slow password hash) and prints how long each took to finish, divided by the time of the first. The result in the original run:

```text
default (4):          1.0 1.0 1.0 1.0 2.1 2.1 2.1 2.1
UV_THREADPOOL_SIZE=8: 1.0 1.1 1.1 1.1 1.1 1.1 1.1 1.1
UV_THREADPOOL_SIZE=1: 1.0 2.0 3.2 4.3 5.6 6.5 7.5 8.5
```

With 4 threads, the jobs finish in two batches of four: the first four take one unit, and the second four wait for a free thread, so they finish at about two units. With 8 threads all jobs run together in one batch. With 1 thread they run one by one. These ratios are from the original run; a re-run on a busy machine gave the same shape (for example `1.0 1.0 1.0 1.1 2.0 2.0 2.0 2.1` with the default) but slightly different digits, so treat the exact decimals as approximate.

## Measuring how late the loop is

How can you tell, in a running service, that something is blocking the loop? Node has a built-in tool: `perf_hooks.monitorEventLoopDelay` checks regularly how late the loop wakes up, and keeps the results in a histogram. In this script I block the loop for 300 ms and then look at the histogram:

```text
max lag > 250ms: true
min lag < 100ms: true
```

The maximum delay was over 250 ms (that is my 300 ms block) and the minimum was small, which means that the loop was healthy except for that one stall. Actual values depend on the machine, so I only print the comparison. In production, export a high percentile (p99) of this histogram as a metric and watch it.

## What stalls the loop

- **Heavy synchronous work in a handler.** Parsing a huge JSON string, `*Sync` file calls and CPU-heavy loops hold the cashier's counter, and every other request waits behind them.
- **Endless `process.nextTick` or recursive microtasks.** These run before the loop can move on, so timers and I/O never get their turn.
- **Relying on `setTimeout(0)` versus `setImmediate` at the top level.** As we saw, the order varies. If you need an order, create the timers inside an I/O callback, or better, do not depend on one.
- **Thinking the thread pool is unlimited.** It is shared by `fs`, `crypto` and DNS, so several slow jobs can delay each other. CPU-heavy work belongs in worker threads.

## Exercise

Write a script with a `setInterval` of 50 ms and a synchronous loop of 300 ms that starts after 120 ms. Predict how many ticks will be printed, run it, and use `monitorEventLoopDelay` to confirm the gap.

## What's next

"Modules: ESM and CommonJS": now that we know how code runs, the next question is how Node finds and loads it.
