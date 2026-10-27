+++
date = '2027-03-28T10:00:00+03:30'
draft = false
title = 'Worker threads and cluster in Node.js'
description = 'Worker threads and cluster in Node.js: block the event loop on purpose, then fix it with workers, Atomics, a pool and cluster, with real runs.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "worker-threads", "cluster", "concurrency", "performance"]
cover = { image = "/images/covers/node-worker-threads-cluster.png", alt = "Worker threads and cluster in Node.js", hiddenInSingle = true }
+++

In the previous post, [Input validation with Zod](/posts/node-validation-zod/), everything ran on one thread. That is fine for I/O, as I showed in [The Node.js event loop](/posts/node-event-loop/), but one slow synchronous function stops every request. This post shows that on purpose, then fixes it with {{< term "worker-threads" "worker threads" >}}, and finally spreads an HTTP server over processes with {{< term "node-cluster" "cluster" >}}. It builds on [An HTTP server with node:http](/posts/node-http-server/).

> Node v20.13.1, local example scripts on 127.0.0.1. The machine was busy, so I report only counts, no timings. I did not run these on Linux or Windows.

## The event loop, blocked

A `setInterval` of 10 ms increments a counter. I run `fib(38)` (a deliberately slow recursive function) and count ticks that happen during it:

```text
block:  fib(38) = 39088169 | ticks counted during the job: 0 (the timer could not run)
worker: fib(38) = 39088169 | ticks counted during the job: 52 (>0 means main stayed responsive)
```

In the first run the timer was starved for the whole job. In the second, the same function ran in a worker and the main thread kept ticking. The tick count varies with machine load; the point is 0 versus not 0.

```js
const w = new Worker(new URL('./fibworker.mjs', import.meta.url), { workerData: { n: 38 } });
w.on('message', (r) => console.log(r));
// fibworker.mjs: parentPort.postMessage(fib(workerData.n))
```

`workerData` is copied into the worker at start; results come back with `postMessage`.

## Copying and transferring

`postMessage` copies by default. With a `transferList` an `ArrayBuffer` is moved instead, with no copy:

```text
before transfer: byteLength = 1024
after transfer:  byteLength = 0
worker got byteLength 1024 first byte 42
```

The sender's buffer is now empty (detached). A buffer I posted without the list kept its `byteLength` of 8, because it was copied. Transfer is fast for big buffers, but you must not touch them afterwards.

## Sharing memory with Atomics

A {{< term "shared-array-buffer" "SharedArrayBuffer" >}} is visible to every thread without copying. Four workers each add 1 a hundred thousand times to two counters in a shared `Int32Array`: one with `Atomics.add`, one with plain `v[1]++`:

```text
expected      : 400000
Atomics.add   : 400000
plain v[1]++  : 195040 | lost updates: 204960
```

A second run gave `154693` for the plain counter. The atomic one is exact every time; the plain one loses updates because read, add and write are separate steps and two threads overwrite each other. That is a {{< term "race-condition" "race condition" >}}, the same bug family as in [sync, select and context in Go](/posts/go-sync-select-context/). The `Atomics` functions make each step indivisible.

## A tiny pool

Starting a worker per task is wasteful, so I wrote a {{< term "worker-pool" "pool" >}}: a queue of jobs, a list of idle workers, and a promise per job. Two workers, six fixed inputs:

```text
fib(30) = 832040  (done by worker#1)
fib(31) = 1346269  (done by worker#2)
fib(32) = 2178309  (done by worker#1)
...
fib(35) = 9227465  (done by worker#2)
results are in input order: true
```

Results are in order because I `await` all promises in input order, not because workers finish in order. Which worker gets which job can differ between runs.

## Errors and exit

```text
throw -> error event: boom in worker
throw -> exit event, code 1
exit3 -> exit event, code 3
ok -> exit event, code 0
```

An uncaught throw in a worker fires `error` on the parent and then `exit`; `process.exit(3)` in the worker only fires `exit` with that code. Always listen to both, and in a pool reject the current job on `error`. My simple pool does that, but it does not respawn a dead worker. A production pool must.

## cluster: one port, several processes

Worker threads help with CPU work. To use more cores for an HTTP server, `cluster` forks child processes that share one listening port. Two workers, 40 requests, each response being the worker's `process.pid` (I replaced real pids with names):

```text
40 requests, distinct responders: 2 -> worker#1: 20, worker#2: 20
```

The 20/20 split matches the docs: on Linux and macOS the primary distributes connections round-robin. I sent `connection: close` so each request is a new connection.

Then I killed a worker with `SIGKILL`. The `exit` event fired in the primary, and I forked a new one myself. Cluster does not restart workers on its own:

```text
worker#1 exited (signal SIGKILL)
alive workers now: 2 | killed was worker#1
40 requests after restart, distinct responders: 2 -> worker#2: 20, worker#3: 20
```

(Output shortened by dropping some trailing text from one line.)

## Which one to use

- CPU-bound work inside one process: worker threads.
- Serve HTTP on all cores: cluster, or a process manager or orchestrator that runs several copies.
- Mostly I/O (database, network): neither; the event loop already handles it.

## Compared with Go

In Go a {{< term "goroutine" "goroutine" >}} is scheduled across cores by the runtime, so CPU work needs no extra API ([Goroutines and channels in Go](/posts/go-goroutines-channels/), [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/)). In Node you choose threads or processes yourself, and each worker has its own heap.

## A few things to watch

- A worker has its own event loop and memory; only shared buffers are shared.
- Do not start more CPU-bound workers than cores.
- Always handle `error` and `exit`.
- Plain integer updates on shared memory are not safe; use `Atomics`.
- Cluster workers share nothing in memory: keep sessions and caches outside.

## Exercise

Make the pool respawn a worker after `error`, and test it with a job that throws on a chosen input.

## What's next

The next post is "Profiling, memory and graceful shutdown in Node.js".
