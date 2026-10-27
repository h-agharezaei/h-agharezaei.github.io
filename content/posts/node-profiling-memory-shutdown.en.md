+++
date = '2027-04-05T10:00:00+03:30'
draft = false
title = 'Profiling, memory and graceful shutdown in Node.js'
seoTitle = 'Profiling, memory and shutdown in Node.js'
description = 'Profiling Node.js: --cpu-prof, heap snapshots, a real memory leak and OOM, event loop delay, then a clean SIGTERM shutdown of an HTTP server.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "profiling", "memory", "heap-snapshot", "graceful-shutdown"]
cover = { image = "/images/covers/node-profiling-memory-shutdown.png", alt = "Profiling, memory and graceful shutdown in Node.js", hiddenInSingle = true }
+++

In the previous post, [Worker threads and cluster in Node.js](/posts/node-worker-threads-cluster/), we spread work over several threads and processes. Before you add more of them, find out where the time and the memory actually go, and make sure the process can stop without dropping requests. This is the Go story of [Profiling Go with pprof](/posts/go-profiling-pprof/) and [Graceful shutdown for Go workers](/posts/go-graceful-shutdown-workers/), told in Node.js terms, on top of the [event loop](/posts/node-event-loop/) and the [HTTP server](/posts/node-http-server/).

> Node v20.13.1. Local example scripts, real outputs. The machine was busy, so I publish counts and sizes, not timings. Heap snapshots and profiles were deleted afterwards. DevTools and `--inspect` are not shown; I did not run them.

## Where does the CPU go

`node --cpu-prof script.js` writes a {{< term "cpu-profile" "CPU profile" >}}, a `.cpuprofile` JSON file. Chrome DevTools can open it as a flame graph; I read it with a short script instead. The profiled program is CPU-heavy on purpose: a recursive `fib(34)` and 300000 `JSON.stringify` calls. The script counts samples per top frame:

```text
total samples 145
    70 render cpu.js:2
    50 fib cpu.js:1
    12 (garbage collector) :0
     2 compileForInternalLoader realm:383
```

The ranking (`render`, `fib`, then the {{< term "garbage-collector" "garbage collector" >}}) is the point; the exact counts change from run to run. Profile first, then optimise the top line only.

## A leak you can watch

The server below keeps a module-level `Map` and, in leak mode, adds an entry per request and never removes it. I sent 50000 requests over keep-alive connections and called `global.gc()` (needs `--expose-gc`) before reading `process.memoryUsage().heapUsed`:

```text
ok before: 3 MB, cache 0
ok after 50000 requests: 4 MB, cache 0
leak before: 3 MB, cache 0
leak after 50000 requests: 31 MB, cache 50000
```

Even after a full GC the leaking run holds 31 MB: a {{< term "memory-leak" "memory leak" >}} is memory that is still reachable. `v8.writeHeapSnapshot()` then wrote a {{< term "heap-snapshot" "heap snapshot" >}} (about 59 MB on disk). DevTools could open it; I read the JSON instead:

```text
nodes 854741 edges 2455453 self size MB 31
  18.3 MB concatenated string
   4.6 MB string
   2.5 MB array
   2.1 MB code
```

The strings dominate, which points at the cache entries. In a real service you can start the process with `--heapsnapshot-signal=SIGUSR2` to dump one on demand; I did not run that flag.

## The limit, and the GC log

With `--max-old-space-size=20` and a loop that keeps allocating, the process dies:

```text
FATAL ERROR: Reached heap limit Allocation failed - JavaScript heap out of memory
exit 134
```

The exit code was 134 here. `--trace-gc` prints one line per collection; the first lines of a small allocating script and of the doomed one:

```text
Scavenge 3.7 (4.0) -> 3.5 (5.0) MB
Mark-Compact 18.8 (50.3) -> 18.0 (51.0) MB
```

A scavenge cleans young objects; a mark-compact barely shrank the heap, because everything was still reachable.

## Event loop delay

`perf_hooks.monitorEventLoopDelay` samples how late timers fire. I blocked the loop with a busy `while` for 200 ms:

```text
samples > 0: true
max delay >= 150 ms: true  | median < 50 ms: true
```

I print booleans, not milliseconds, because the load was high. One blocking call shows up as a huge max while the median stays small, so watch the max and a high percentile.

## Shutting down the HTTP server

On {{< term "sigterm" "SIGTERM" >}}, `server.close()` stops accepting new connections and calls back when all connections end. On 20.13.1 both `closeIdleConnections` and `closeAllConnections` exist (the script printed `function` for both). I sent a request that takes 1 second to the server, from a client on a {{< term "keep-alive" "keep-alive" >}} connection:

```text
SIGTERM: server.close()
timeout: closeAllConnections()
close callback, err = null
client: in-flight -> slow done
```

The in-flight request finished, but its keep-alive socket stayed open afterwards, so the close callback waited for my 3 second hard timeout. A warm-up connection that was idle at SIGTERM did not cause this: in this version `close()` already dropped it and exited at once. Calling `closeIdleConnections()` every 100 ms after `close()` fixed the waiting: the process exited right after the response, the timeout never fired, exit code 0. A client that sent half a request and went silent was only removed by the timeout's `closeAllConnections()`.

That is the {{< term "graceful-shutdown" "graceful shutdown" >}} recipe: stop accepting, let in-flight work end, close idle sockets, and keep a hard timeout so a stuck client cannot block a deploy. Go's `http.Server.Shutdown` does the first three for you; a `context` deadline plays the role of the timeout.

## A few things to watch

- Profile under realistic load, and change one thing at a time.
- Read the heap after a forced GC; before it, you measure garbage.
- Bound every cache (size or TTL), or it becomes a leak.
- Heap snapshots can be as large as the heap and hold secrets: delete them.
- `process.exit()` in the SIGTERM handler skips the graceful path; exit when `close` calls back.

## Exercise

Add `/leak` to your server from the HTTP post, load it with a script, take two heap snapshots and compare the string sizes. Then give the cache a size limit and repeat.

## What's next

The next post is "Node.js or Go? When to use which", the last of the Node.js series.
