+++
date = '2027-04-07T10:00:00+03:30'
draft = false
title = 'Multiprocessing in Python'
description = 'Multiprocessing in Python on macOS: spawn and the main guard, Pool and ProcessPoolExecutor, pickling limits, Value, Manager, shared memory, errors.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "multiprocessing", "concurrency", "processes", "pickle"]
cover = { image = "/images/covers/py-multiprocessing.png", alt = "Multiprocessing in Python", hiddenInSingle = true }
+++

You have a pipeline that must chew through a big pile of CPU work: hash a million files, resize images, count primes in huge ranges. You want it to use every core of the machine. [The GIL](/posts/py-gil-threading/) says threads cannot do that in standard Python, because they take turns. The standard answer is to use {{< term "process" "processes" >}} instead.

A process is a whole running program with its own memory. If you start four processes, you get four separate Python interpreters, and each one has its own GIL, so all four really run at the same time on four cores. The picture I keep in mind: threads are several cooks sharing one kitchen with one stove; processes are several kitchens. More stoves, but now the kitchens cannot just reach into each other's fridge. Whatever they need to exchange has to be packed up and carried across. That packing is the cost of this approach, and most of this post is about where it shows.

This post runs the `multiprocessing` module on macOS. If you know Go ([getting started](/posts/go-getting-started/)), expect more ceremony than `go f()`.

> I re-ran every demo with Python 3.14.0 on macOS; they are local scripts. The machine was busy (the one-minute load average was between 11 and 14 while I re-ran them), so I publish **no speed numbers**, only counts, bytes and outputs. I did not run anything on Linux. After the runs I checked with `ps` that none of my worker processes were left.

## Start method and the main guard

How does a new process get created? The module has a setting called the {{< term "start-method" "start method" >}}. On this Mac it printed:

```text
start method: spawn
```

With `spawn`, the child is a brand new interpreter. To know what code to run, it imports your main module again from the top. According to the Python docs (I did not run this on Linux), Linux has used `fork`, which copies the parent process, and changed its default to `forkserver` in Python 3.14. So the same script can behave differently on different systems.

That re-import has a consequence. If your script starts a child at the top level, the child imports the script, which starts another child, and so on. To prevent this, everything that starts processes must sit under the guard `if __name__ == '__main__':`, which is false in the re-imported copy. I tested a script with no guard that starts a `Process` at top level, under a 15 second timeout. Python stopped it with this error:

```text
RuntimeError:
        An attempt has been made to start a new process before the
        current process has finished its bootstrapping phase.
```

(The full message goes on with a long hint about `freeze_support()`.) So Python refuses instead of looping forever. Still, always write the guard.

## Process, Pool and the executor

The lowest-level tool is `mp.Process(target=..., args=...)` with `start()` and `join()`. In the demo `basics.py` a child printed `hello from child` and its `exitcode` was `0`. Most of the time you do not want to manage processes one by one, so you use a pool, a fixed set of worker processes that take tasks from a list:

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

`pool.map` splits the list among the four workers and returns the results in the original order. To prove these were real separate processes, the demo asked 200 tasks for their process id (`os.getpid()`) and collected the set of ids: it had at most 4 members, and the parent's id was not among them. This is a {{< term "worker-pool" "worker pool" >}}, like the threaded one in the last post. `ProcessPoolExecutor` has the same API as `ThreadPoolExecutor`, so switching from threads to processes can be a one-line change.

## Everything is pickled

Processes do not share memory, so arguments and results have to be turned into bytes, sent through a pipe and rebuilt on the other side. Python does this with {{< term "pickle" "pickle" >}}. The demo `pickling.py` shows what it means in practice:

```text
pickled bytes for 1,000,000 ints: 4871352
pickled bytes for one int: 5
PicklingError Can't pickle <function <lambda> at 0x1076ff110>: it's not found as __main__.<lambda>
```

(The address in the last line changes on every run.) There are two consequences:

- A lambda or a function defined inside another function cannot be sent. Pickle sends functions by name, and these have no importable name. Use a top-level `def`.
- A list of a million ints is about 4.9 MB, and it has to travel to the worker and back. If each task is tiny and its data is big, sending the data can cost more than computing saves. Pass IDs or file paths and let the worker load the data itself. I did not measure that cost.

## Sharing state

Since processes do not share variables, how do they work on the same number? The demo has four processes that each add 1 to a shared `Value` 20,000 times, first without a lock and then with one:

```text
Value no lock  : 61798 expected 80000
Value with lock: 80000 expected 80000
```

It is the same {{< term "race-condition" "race condition" >}} as with threads, with the same fix: `with v.get_lock():`, which is a {{< term "mutex" "mutex" >}}. The no-lock number is different on every run: the line above is from the original run, and my re-run printed `20439`. The with-lock number is always 80000. The demo has three more ways to share or pass data:

```text
Array: [0.0, 2.5, 0.0]
Manager dict   : 8000 expected 8000
SharedMemory   : b'hello'
after unlink: FileNotFoundError (no leak)
```

- `mp.Array` is a fixed-size array of one type (here doubles); I set the middle item to 2.5.
- `Manager` starts a server process that holds a `dict` or a `Lock`, and the others reach it through proxy objects. It is flexible but slower, because every access is a message. I used a lock for the 8,000 increments, and the total was exact.
- {{< term "shared-memory" "SharedMemory" >}} is a raw block of memory. The child attached to it by name and wrote `hello`, and the parent read it. Then `close()` and `unlink()` released it, and attaching again raised `FileNotFoundError`, which shows nothing was leaked.

If you would rather pass messages than share state, `mp.Queue` works: four children each put `(n, n*n)` in it, and the parent got `[(0, 0), (1, 1), (2, 4), (3, 9)]`.

## Initializers and errors

A pool can run a setup function once in every worker, which is the place to open a connection or load a model. `Pool(2, initializer=init, initargs=('cfg',))` runs `init('cfg')` in each worker, and the task function `tagged` returned `['cfg:0', 'cfg:1', 'cfg:2']`, so every worker saw the setup.

What happens when a worker raises an exception? It is sent back and raised again in the parent, with the worker's own traceback attached as its cause. Here is the demo output with long paths shortened:

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

The first half is the traceback from inside the worker, showing the real line where the error happened. The second half is the parent re-raising it at `pool.map`. The demo also printed `caught: ValueError('bad input 2') | cause: RemoteTraceback`, and the executor version raised `bad input 2` in the same way.

## Threads, goroutines, worker_threads

Threads share memory but share one GIL, so they help with waiting but not with computing. Processes run pure Python in parallel, at the price of startup time and pickling. A Go goroutine is cheap and shares memory ([goroutines and channels](/posts/go-goroutines-channels/)). Node's `worker_threads` are separate threads with their own event loops ([worker threads and cluster](/posts/node-worker-threads-cluster/)); a Python process is closer to a whole new interpreter.

## Where processes get expensive

- Always use the `if __name__ == '__main__':` guard. The default start method differs between operating systems, so a script that works on one can break on another.
- Functions and arguments must be picklable. Keep tasks coarse, so the work per task is large compared with the data you send.
- Shared mutable state needs a lock; it is usually simpler to pass results back and combine them in the parent.
- Release shared memory: call `close()` in every process and `unlink()` once.
- Use processes for CPU work. For waiting, threads or asyncio are cheaper.

## Exercise

Write a prime counter over ranges 0 to 2,000,000 split into 8 chunks. Run it with `Pool.map`, then with `ProcessPoolExecutor`. Print the worker pids to prove more than one process worked, and time it only if `uptime` shows a quiet machine.

## What's next

Processes are heavy when the work is only waiting, so the next post is "asyncio in Python", the single-threaded way to handle thousands of waiting tasks.
