+++
date = '2027-04-07T10:00:00+03:30'
draft = false
title = 'Multiprocessing in Python'
description = 'Multiprocessing in Python on macOS: spawn and the main guard, Pool and ProcessPoolExecutor, pickling limits, Value, Manager, shared memory, errors.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "multiprocessing", "concurrency", "processes", "pickle"]
cover = { image = "/images/covers/py-multiprocessing.png", alt = "Multiprocessing in Python", hiddenInSingle = true }
+++

In [the previous post](/posts/py-gil-threading/) we saw that the GIL lets threads help with waiting but not with computing. For CPU work the standard answer is {{< term "process" "processes" >}}: each has its own interpreter and its own GIL. This post runs the `multiprocessing` module on macOS and shows where it bites. If you know Go ([getting started](/posts/go-getting-started/)), expect more ceremony than `go f()`.

> Python 3.14.0 on macOS, demos in a local directory. The machine was busy (load average above 6), so I publish **no speed numbers**, only counts and bytes. I did not run anything on Linux.

## Start method and the main guard

```text
start method: spawn
```

That is `multiprocessing.get_start_method()` here. On macOS the {{< term "start-method" "start method" >}} is `spawn`: the child is a fresh interpreter that imports your main module again. According to the docs (not run by me), Linux used `fork` and changed its default to `forkserver` in 3.14.

So without the `if __name__ == '__main__':` guard, the child would re-run the code that starts children. I tested a script that starts a `Process` at top level, under a 15 s timeout (a subprocess with `timeout=15`). Python stopped it:

```text
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
```

It refuses rather than looping, but always write the guard.

## Process, Pool and the executor

```python
if __name__ == '__main__':
    with mp.Pool(4) as pool:
        print(pool.map(square, range(10)))
    with ProcessPoolExecutor(max_workers=3) as ex:
        print(list(ex.map(square, range(5))))
```

```text
Pool.map: [0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
Executor.map: [0, 1, 4, 9, 16]
```

A bare `mp.Process(target=..., args=...)` with `start()` and `join()` also worked (child exit code 0). For 200 tasks, the set of worker pids had at most 4 members and did not include the parent: real separate processes. This is a {{< term "worker-pool" "worker pool" >}}, like the threaded one in the last post; `ProcessPoolExecutor` has the same API as `ThreadPoolExecutor`, so switching is a one-line change.

## Everything is pickled

Arguments and results travel between processes through {{< term "pickle" "pickle" >}}:

```text
pickled bytes for 1,000,000 ints: 4871352
pickled bytes for one int: 5
PicklingError Can't pickle <function <lambda> at 0x1076ff110>: it's not found as __main__.<lambda>
```

Two consequences. A lambda (or a local function) cannot be sent; use a top-level `def`. And a list of a million ints is about 4.9 MB each way, so sending small tasks with big data can cost more than the computing saves (pass IDs or file paths instead). I did not measure that cost.

## Sharing state

Processes do not share variables. Four processes each added 1 to a shared `Value` 20,000 times:

```text
Value no lock  : 61798 expected 80000
Value with lock: 80000 expected 80000
```

Same {{< term "race-condition" "race condition" >}} as with threads, same fix: `with v.get_lock():` (a {{< term "mutex" "mutex" >}}). The no-lock number varies per run; the lock number does not. Other tools I ran:

```text
Array: [0.0, 2.5, 0.0]
Manager dict   : 8000 expected 8000
SharedMemory   : b'hello'
after unlink: FileNotFoundError (no leak)
```

`mp.Array` is a fixed-size typed array. `Manager` runs a server process holding a `dict` or `Lock` that others reach through proxies: flexible but slower, and I used a lock for the 8,000 increments. {{< term "shared-memory" "SharedMemory" >}} is a raw block: the child attached by name and wrote `hello`, the parent read it, then `close()` and `unlink()`; attaching again raised `FileNotFoundError`, so nothing leaked. For passing messages instead, `mp.Queue` worked: four children each put `(n, n*n)` and the parent got `[(0, 0), (1, 1), (2, 4), (3, 9)]`.

## Initializers and errors

`Pool(2, initializer=init, initargs=('cfg',))` runs `init` once per worker, a place for setup such as opening a connection; `tagged` returned `['cfg:0', 'cfg:1', 'cfg:2']`.

When a worker raises, the exception is re-raised in the parent, with the worker's traceback attached as its cause:

```text
multiprocessing.pool.RemoteTraceback:
...
  File ".../errors.py", line 9, in boom
    raise ValueError('bad input 2')
ValueError: bad input 2

The above exception was the direct cause of the following exception:
...
ValueError: bad input 2
```

The executor raised `bad input 2` the same way.

## Threads, goroutines, worker_threads

Threads share memory but share one GIL; processes parallelize pure Python but cost startup time and pickling. A goroutine is cheap and shares memory ([goroutines and channels](/posts/go-goroutines-channels/)). Node's `worker_threads` are separate threads with their own event loops ([worker threads and cluster](/posts/node-worker-threads-cluster/)); a Python process is closer to a whole new interpreter.

## A few things to watch

- Always use the `if __name__ == '__main__':` guard; the default start method differs per OS.
- Functions and arguments must be picklable; keep tasks coarse.
- Shared mutable state needs a lock; prefer passing results back.
- Release shared memory: `close()` everywhere, `unlink()` once.
- Use processes for CPU work; for waiting, threads or asyncio are cheaper.

## Exercise

Write a prime counter over ranges 0 to 2,000,000 split into 8 chunks. Run it with `Pool.map`, then with `ProcessPoolExecutor`. Print the worker pids to prove more than one process worked, and time it only if `uptime` shows a quiet machine.

## What's next

The next post is "asyncio in Python", the single-threaded way to handle thousands of waiting tasks.
