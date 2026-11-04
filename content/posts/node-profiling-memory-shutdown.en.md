+++
date = '2027-04-05T10:00:00+03:30'
draft = false
title = 'Profiling, memory and graceful shutdown in Node.js'
seoTitle = 'Profiling, memory and shutdown in Node.js'
description = 'Profiling Node.js: --cpu-prof, heap snapshots, a real memory leak and OOM, event loop delay, then a clean SIGTERM shutdown of an HTTP server.'
contentType = 'tutorial'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "profiling", "memory", "heap-snapshot", "graceful-shutdown"]
cover = { image = "/images/covers/node-profiling-memory-shutdown.png", alt = "Profiling, memory and graceful shutdown in Node.js", hiddenInSingle = true }
+++

Your service is slow, or its memory grows every hour until it is killed. The natural reaction is to guess: "it must be the JSON parsing", "it must be that cache". A guess costs time when it is wrong, and you only find out after the work is done. This post is about not guessing. Node.js can tell you where the time goes, what is holding the memory, and whether the event loop is being blocked. We then finish with the other half of a healthy service: stopping without dropping requests.

To make it concrete I use a test server with a cache that never evicts anything. Over 50000 requests its heap grew from 3 MB to 31 MB. Before adding more of the threads and processes from [Worker threads and cluster in Node.js](/posts/node-worker-threads-cluster/), you should know where time and memory go, and the process should be able to stop without losing requests. This is the Go story of [Profiling Go with pprof](/posts/go-profiling-pprof/) and [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/), told in Node.js terms, on top of the [event loop](/posts/node-event-loop/) and the [HTTP server](/posts/node-http-server/).

> I ran everything with Node v20.13.1, as local example scripts, and the outputs are real. The machine was busy, so I publish counts and sizes, not timings. The heap snapshots and profiles were deleted afterwards. The port of the shutdown demo is random. DevTools and `--inspect` are not shown, and I did not run them. Numbers such as sample counts vary from run to run; I say so where it matters.

## Where does the CPU go

The first question is "which function is using the time?". A profiler answers it by sampling: many times a second it looks at what the program is doing right now and writes down the function. After a while, the functions that appear most often are the ones using the time.

`node --cpu-prof script.js` does this and writes a {{< term "cpu-profile" "CPU profile" >}} when the program exits, a `.cpuprofile` JSON file. Chrome DevTools can open it as a {{< term "flame-graph" "flame graph" >}}; I did not use DevTools and read the file with a short script instead. The script counts how many samples had each function on top.

The program is CPU-heavy on purpose: a recursive `fib(34)` and 300000 calls of `JSON.stringify`, in two functions called `fib` and `render`. The output:

```text
total samples 146
    55 fib cpu.js:1
    55 render cpu.js:2
     6 (garbage collector) :0
     5 compileForInternalLoader realm:383
```

The program spent nearly all its time in `fib` and `render`, about equally, with a little in the {{< term "garbage-collector" "garbage collector" >}} (the part of the runtime that frees objects nothing can reach any more) and in Node's own start-up code. The first number is the sample count for each function. The exact counts change from run to run: the first version of this post got 70 for `render` and 50 for `fib`, and my run now got 55 for both. What does not change is the ranking idea: profile first, then optimise only the top lines.

## A leak you can watch

Now memory. A {{< term "memory-leak" "memory leak" >}} in a garbage-collected language is not memory that was forgotten, it is memory that is still *reachable*: something still points at it, so the collector must keep it, even though the program will never use it again. The classic cause is a cache or a list that only grows.

The server below keeps a module-level `Map` and, in "leak" mode, adds an entry per request and never removes it. In "ok" mode it adds nothing. I sent 50000 requests over keep-alive connections and called `global.gc()` (this needs the `--expose-gc` flag) before reading `process.memoryUsage().heapUsed`. Forcing a collection first matters: without it you would be measuring garbage that is about to be freed.

```js
const cache = new Map();            // module level: lives as long as the process
const leaky = process.argv[2] === 'leak';
const server = http.createServer((req, res) => {
  const body = { id: cache.size, payload: 'x'.repeat(1000) };
  if (leaky) cache.set(req.url + Math.random(), body);   // never evicted
  res.end('ok');
});
```

The output of the two runs, one after the other:

```text
ok before: 3 MB, cache 0
ok after 50000 requests: 4 MB, cache 0
leak before: 3 MB, cache 0
leak after 50000 requests: 31 MB, cache 50000
```

The "ok" run ends at about the same size it started. The leaking run holds 31 MB after a full collection, with 50000 entries in the cache. That is the leak: the memory is still reachable.

To see *what* holds it, take a {{< term "heap-snapshot" "heap snapshot" >}}: a dump of every live object in the heap, with sizes and references. `v8.writeHeapSnapshot()` wrote one (about 59 MB on disk). Chrome DevTools can open it and show you the objects. I did not use DevTools; I summed the sizes by type with a script:

```text
nodes 854769 edges 2455490 self size MB 31
  18.4 MB concatenated string
   4.6 MB string
   2.5 MB array
   2.1 MB code
```

The first line says the snapshot has about 855 thousand objects ("nodes") and 2.5 million references ("edges") to each other, totalling 31 MB, which matches the 31 MB we measured. The following lines are the biggest kinds of object. Strings dominate, which points straight at the cache entries (each holds a 1000-character payload). In a real service you would then look at what keeps those strings alive. In a running service you can also start the process with `--heapsnapshot-signal=SIGUSR2` to write a snapshot on demand; I did not run that flag.

## The limit, and the GC log

What happens if a leak goes on? V8 has a limit on the heap, and past it the process dies. I lowered the limit with `--max-old-space-size=20` (megabytes) and ran a script that keeps allocating objects and never lets go of them:

```text
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
exit code 134
```

The process is killed with exit code 134 here. This is what an out-of-memory crash looks like from the outside, and it is why a slow leak turns into a restart loop in production.

The `--trace-gc` flag prints one line per garbage collection, so you can watch the collector work. I cut the process id and timing columns from these lines. The first lines of a small allocating script:

```text
Scavenge 3.7 (4.0) -> 3.5 (5.0) MB
```

and, from the doomed one, the later full collections:

```text
Mark-Compact 20.4 (29.7) -> 16.4 (50.5) MB
Mark-Compact (reduce) 21.1 (50.5) -> 19.7 (21.5) MB
```

A "Scavenge" is a quick cleanup of young objects. A "Mark-Compact" is a full collection. The numbers are the used heap before and after (and the total size in brackets). In the doomed run the full collections barely shrink the heap (20.4 to 16.4, then 21.1 to 19.7 MB), because almost everything is still reachable. When you see that in a log, you are looking at a leak.

## Event loop delay

A different problem: the memory is fine but requests are slow because something blocks the event loop, as in the previous post. `perf_hooks.monitorEventLoopDelay` measures how late timers fire, which is a direct measure of how long the loop was busy. I enabled it, blocked the loop with a busy `while` for 200 ms, and read the result:

```text
samples > 0: true
max delay >= 150 ms: true  | median < 50 ms: true
```

I print booleans, not milliseconds, because the machine was loaded and I do not want to publish timings. The meaning: the monitor collected samples, the worst delay was at least 150 ms (the 200 ms block showed up), and the median delay was still small. One blocking call produces a huge maximum while the median stays low, so in a real service watch the maximum and a high percentile, not the average.

## Shutting down the HTTP server

Now the other half. When a deploy or an orchestrator wants your service to stop, it sends {{< term "sigterm" "SIGTERM" >}}. If the process just dies, requests that were half done are lost. A good shutdown stops accepting new work, finishes what is in flight, and exits.

For an HTTP server, `server.close()` stops accepting new connections and calls back when all existing connections have ended. The catch is {{< term "keep-alive" "keep-alive" >}}: a client may keep its connection open after a response to reuse it, and an open idle connection keeps `close` waiting. On 20.13.1 both `closeIdleConnections` and `closeAllConnections` exist (the script printed `function` for both).

The demo server has a `/slow` route that takes 1 second. The client uses a keep-alive connection, makes one warm-up request and then a slow request, and I send `SIGTERM` to the server while the slow request is running. The server's handler is:

```js
process.once('SIGTERM', () => {
  console.log('SIGTERM: server.close()');
  const hard = setTimeout(() => { console.log('timeout: closeAllConnections()'); server.closeAllConnections(); }, 3000);
  hard.unref();
  server.close((err) => { console.log('close callback, err =', err ?? null); process.exit(0); });
  if (mode === 'idle') { server.closeIdleConnections(); setInterval(() => server.closeIdleConnections(), 100).unref(); }
});
```

In the plain mode it only calls `server.close()` and has a 3 second hard timeout. The server output was:

```text
SIGTERM: server.close()
timeout: closeAllConnections()
close callback, err = null
```

and the client printed `client: in-flight -> slow done`. So the in-flight request did finish. But its keep-alive socket stayed open afterwards, and the close callback only came when my 3 second hard timeout fired and cut the connection.

Is it the warm-up connection that was idle when `SIGTERM` came? No. I checked with a client that only does the warm-up request: in this version `close()` already drops connections that are idle at that moment, and the server exited at once. The problem is the connection that *becomes* idle afterwards, when the slow request finishes.

The fix is the `idle` mode in the handler above: call `closeIdleConnections()` right away and then every 100 ms. With it the output was:

```text
SIGTERM: server.close()
close callback, err = null
```

The process exited right after the response, without waiting for the timeout, with exit code 0.

One more client: it sent half a request (`GET /slow HTTP/1.1` with no blank line to end it) and then went silent. It is neither idle nor finished, so `closeIdleConnections()` does not touch it. Only the 3 second timeout's `closeAllConnections()` removed it: the server printed the `timeout:` line before closing, and the client reported `stuck client: connection closed by server`.

That is the {{< term "graceful-shutdown" "graceful shutdown" >}} recipe: stop accepting, let in-flight work finish, close idle sockets, and keep a hard timeout so one stuck client cannot block a deploy forever. Go's `http.Server.Shutdown` does the first three for you; a `context` deadline plays the role of the timeout.

## Measuring the wrong thing

- **Profiling an unrealistic run.** Profile under realistic load, and change one thing at a time.
- **Reading memory before a collection.** Read the heap after a forced GC; before it, you are measuring garbage.
- **Caches without a bound.** Bound every cache (by size or by time), or it becomes a leak.
- **Leaving snapshots around.** A heap snapshot can be as large as the heap and can contain secrets such as tokens. Delete it.
- **Exiting too early.** `process.exit()` right in the SIGTERM handler skips the graceful path; exit when `close` calls back.

## Exercise

Add a `/leak` route to your server from the HTTP post, load it with a script, take two heap snapshots and compare the string sizes. Then give the cache a size limit and repeat.

## What's next

The last post of the series is "Node.js or Go? When to use which". It closes the series by comparing the two on the same kind of service.
