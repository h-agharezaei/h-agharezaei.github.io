+++
date = '2027-03-28T10:00:00+03:30'
draft = false
title = 'Worker threads and cluster in Node.js'
description = 'Worker threads and cluster in Node.js: block the event loop on purpose, then fix it with workers, Atomics, a pool and cluster, with real runs.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "worker-threads", "cluster", "concurrency", "performance"]
cover = { image = "/images/covers/node-worker-threads-cluster.png", alt = "Worker threads and cluster in Node.js", hiddenInSingle = true }
+++

Here is a small experiment. I start a timer that should tick every 10 milliseconds, then call a deliberately slow function, `fib(38)`. While that function runs, the timer ticks 0 times. Not "a few times late". Zero. For the whole second or so of the computation, the program could not do anything else, and a web server in that state would not answer a single request.

Everything we have done in Node.js so far, up to [Input validation with Zod](/posts/node-validation-zod/), ran on one thread. As [The Node.js event loop](/posts/node-event-loop/) explained, that is fine for I/O: while the program waits for a database or the network, the loop serves other work. But a long calculation does not wait for anything. It keeps the one thread busy, and every other request queues behind it.

The fix is to run that calculation somewhere else. Node gives you two tools for this, and they are easy to mix up:

- A {{< term "worker-threads" "worker thread" >}} is another thread inside the same program. It has its own event loop and its own memory, and it talks to the main thread by sending messages. Use it to move CPU-heavy work off the main thread.
- {{< term "node-cluster" "cluster" >}} starts several copies of your whole program as separate processes (a {{< term "process" "process" >}} is a running program with its own memory) that share one listening port. Use it to serve HTTP on all CPU cores.

There is also `child_process`, which starts any program as a separate process; I do not use it in this post. I build on [An HTTP server with node:http](/posts/node-http-server/) for the cluster part.

> I ran everything with Node v20.13.1, as local example scripts on 127.0.0.1. The original demo scripts of this post were not kept, so I wrote them again for this version and ran them; the code below is what I ran. The machine was busy, so I report counts and not timings. I did not run these on Linux or Windows.

## The event loop, blocked

The first script runs the same job twice. A `setInterval` of 10 ms increments a counter, and I count the ticks that happen while the job runs. The first time the job runs on the main thread. The second time it runs in a worker:

```js
const w = new Worker(new URL('./fibworker.mjs', import.meta.url), { workerData: { n: 38 } });
w.on('message', resolve);
w.on('error', reject);
// fibworker.mjs: parentPort.postMessage(fib(workerData.n))
```

`workerData` is copied into the worker when it starts, and the worker sends its answer back with `postMessage`. The output:

```text
block:  fib(38) = 39088169 | ticks counted during the job: 0
worker: fib(38) = 39088169 | ticks counted during the job: 38
```

In the first line the timer was starved for the whole job: 0 ticks. In the second line the same function ran in a worker, and the main thread kept ticking. The exact number of ticks depends on the machine and its load (I got 35 in another run, and the original version of this post showed 52). The point is 0 versus not 0.

## Copying and transferring

The main thread and a worker do not share variables. When you call `postMessage`, the data is copied by default. For a big `ArrayBuffer` that copy is wasteful, so you can hand the buffer over instead, by listing it in the second argument (the `transferList`). The buffer is then moved, not copied:

```text
copied buffer after postMessage: byteLength = 8
before transfer: byteLength = 1024
after transfer:  byteLength = 0
worker got byteLength 1024 first byte 42
```

A small buffer I posted without the list kept its `byteLength` of 8, because the worker received a copy. The big buffer I transferred has `byteLength` 0 in the sender afterwards (it is "detached"), while the worker got all 1024 bytes, including the first byte 42 that I had written. Transfer is fast for big buffers, but you must not touch them after sending.

## Sharing memory with Atomics

Sometimes you do want one block of memory that several threads can see. A {{< term "shared-array-buffer" "SharedArrayBuffer" >}} is exactly that: no copy, visible to all threads. That also creates the classic problem of shared memory. To show it, four workers each add 1 a hundred thousand times to two counters in a shared `Int32Array`. One counter is updated with `Atomics.add`, the other with a plain `v[1]++`:

```js
for (let i = 0; i < N; i++) { Atomics.add(v, 0, 1); v[1]++; }
```

```text
expected      : 400000
Atomics.add   : 400000
plain v[1]++  : 171664 | lost updates: 228336
```

The atomic counter is exact. The plain counter lost more than half of its updates. Why? `v[1]++` is really three steps: read the value, add one, write it back. Two threads can read the same value, both add one, and both write the same result, so one update disappears. That bug is a {{< term "race-condition" "race condition" >}}, the same family as in [sync, select and context in Go](/posts/go-sync-select-context/). `Atomics.add` makes the three steps one indivisible step. The plain counter's number is different in every run: another run gave 179018, and the original version of this post saw 195040 and 154693. The atomic one is 400000 every time.

## A tiny pool

Starting a new worker for every task is wasteful, because starting a thread has a cost. The usual answer is a pool of workers: start a few once, keep a queue of jobs and a list of idle workers, and hand each job to an idle worker. Here is a small one, with a promise per job so callers can simply `await` their result:

```js
class Pool {
  constructor(file, size) {
    this.queue = []; this.idle = [];
    for (let i = 1; i <= size; i++) {
      const w = new Worker(file); w.id = i;
      w.on('message', (r) => { const j = w.job; w.job = null; this.idle.push(w); j.resolve({ value: r, by: w.id }); this.next(); });
      w.on('error', (e) => { const j = w.job; w.job = null; if (j) j.reject(e); });
      this.idle.push(w);
    }
    this.all = [...this.idle];
  }
  run(data) { return new Promise((resolve, reject) => { this.queue.push({ data, resolve, reject }); this.next(); }); }
  next() {
    while (this.idle.length && this.queue.length) {
      const w = this.idle.pop(), job = this.queue.shift();
      w.job = job; w.postMessage(job.data);
    }
  }
  close() { return Promise.all(this.all.map((w) => w.terminate())); }
}
```

`run` puts a job in the queue; `next` gives queued jobs to idle workers; when a worker answers, it goes back to the idle list and the next job starts. I ran two workers on six inputs, `fib(30)` to `fib(35)`:

```text
fib(30) = 832040  (done by worker#2)
fib(31) = 1346269  (done by worker#1)
fib(32) = 2178309  (done by worker#2)
fib(33) = 3524578  (done by worker#1)
fib(34) = 5702887  (done by worker#2)
fib(35) = 9227465  (done by worker#1)
results are in input order: true
```

The results come out in input order because the script awaits all the promises in input order, not because the workers finish in order. Which worker handles which job can differ between runs.

## Errors and exit

A worker can fail in two ways. The script starts three tiny workers, one that throws, one that calls `process.exit(3)` and one that finishes normally, and listens to both events:

```text
throw -> error event: boom in worker
throw -> exit event, code 1
exit3 -> exit event, code 3
ok    -> exit event, code 0
```

An uncaught `throw` in a worker fires `error` on the parent and then `exit` (code 1). A `process.exit(3)` in the worker fires only `exit`, with that code. So always listen to both, and in a pool reject the current job on `error`. My small pool does that, but it does not start a new worker when one dies. A production pool must.

## cluster: one port, several processes

Worker threads help with CPU work inside one program. To use more cores for an HTTP server, `cluster` starts child processes that all listen on the same port. The first process, the primary, accepts connections and hands them to the workers. According to the Node.js docs, the default is round-robin on every platform except Windows: connection 1 to worker 1, connection 2 to worker 2, and so on.

The script forks two workers. Each answers every request with its own `process.pid`. The primary then sends 40 requests, one after another, each on a new connection (`connection: close`), and counts which worker answered. I replaced real pids with names:

```text
40 requests, distinct responders: 2 -> worker#1: 20, worker#2: 20
```

An even 20 and 20, as round-robin predicts. Then I killed worker#1 with `SIGKILL` and looked at what the primary saw:

```text
worker#1 exited (signal SIGKILL)
alive workers now: 1
40 requests after restart, distinct responders: 2 -> worker#2: 20, worker#3: 20
```

The primary got an `exit` event, and only one worker was left alive. Cluster does not restart workers by itself: the script forked worker#3 on its own, and then the split was even again. Keeping the workers alive is your job (or your process manager's).

One more observation. When I sent the 40 requests of the second round all at once instead of one after another, the split in my runs was 37 and 3, not 20 and 20 (the first round, sent the same way, was still 20 and 20). I did not investigate why. Do not count on an exactly even split.

## Which one to use

- **CPU-bound work inside one process:** worker threads.
- **Serving HTTP on all cores:** cluster, or a process manager or orchestrator that runs several copies of the program.
- **Mostly I/O (database, network):** neither. The event loop already handles it.

## Compared with Go

In Go a {{< term "goroutine" "goroutine" >}} is scheduled across cores by the runtime, so CPU work needs no extra API ([Goroutines and channels in Go](/posts/go-goroutines-channels/), [The Go scheduler and garbage collector](/posts/go-scheduler-gc-internals/)). In Node you choose threads or processes yourself, and each worker has its own memory.

## Where threads and processes bite

- **Workers do not share your variables.** A worker has its own event loop and heap; only shared buffers are shared, and everything else is copied by messages.
- **Too many workers.** Do not start more CPU-bound workers than cores; they just compete with each other.
- **Unhandled worker failure.** Always handle `error` and `exit`, or a dead worker leaves a job waiting forever.
- **Plain updates on shared memory.** `v[1]++` on a `SharedArrayBuffer` loses updates. Use `Atomics`.
- **State in cluster workers.** Cluster workers share nothing in memory. Keep sessions and caches outside, in a database or another service.

## Exercise

Make the pool respawn a worker after `error`, and test it with a job that throws on a chosen input.

## What's next

The next post is "Profiling, memory and graceful shutdown in Node.js". Before adding workers, you should know where the time and the memory really go, and that post shows how to find out.
