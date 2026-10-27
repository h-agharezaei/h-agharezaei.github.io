+++
date = '2027-03-31T10:00:00+03:30'
draft = false
title = 'The GIL and threading'
description = 'The GIL and threading in Python: what the lock does, when threads help, a lost-update race on a free-threaded build, Lock, Queue and thread pools.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "gil", "threading", "concurrency", "free-threading"]
cover = { image = "/images/covers/py-gil-threading.png", alt = "The GIL and threading", hiddenInSingle = true }
+++

In the [previous post](/posts/py-testing-pytest/) we tested our code; now we make it concurrent. Coming from Go ([goroutines and channels](/posts/go-goroutines-channels/)) or Node.js ([the event loop](/posts/node-event-loop/)), the first surprise in Python is the {{< term "gil" "GIL" >}}: in standard CPython only one {{< term "thread" "thread" >}} runs Python bytecode at a time. This post shows what that means with real runs.

> Python 3.14.0 (`python3 --version`) with the GIL for most demos, and Python 3.14.3 free-threaded (`python3.14t`, installed with `uv python install 3.14t`, deleted afterwards) for one comparison. `sys._is_gil_enabled()` printed `True` and `False` respectively. The machine was heavily loaded, so I publish **no timings for CPU work**; the one time I show is a sleep.

## Threads help when they wait

While a thread blocks on I/O or `sleep`, the GIL is released and others run. Ten tasks of `time.sleep(0.2)`:

```text
sequential, 10 x 0.2s: ~2.0s
10 threads:           ~0.2s [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

The rounded elapsed time dropped tenfold, because sleeping is waiting, not computing. The code used `ThreadPoolExecutor(max_workers=10)` and `ex.map(fetch, range(10))`, which is the simplest API: it is a {{< term "thread-pool" "thread pool" >}} that returns results in input order.

For CPU-bound pure Python the GIL means threads take turns, so four threads do not give four times the speed. I did **not** measure this, because the load made any number meaningless. According to the docs, use processes for CPU work; that is the next post.

## The race the GIL does not prevent

A {{< term "race-condition" "race condition" >}} needs no parallelism, only a thread switch between two steps. I ran 8 threads, each doing `counter += 1` 200,000 times, three runs:

```text
no lock   run 1: 1600000 expected 1600000
no lock   run 2: 1600000 expected 1600000
no lock   run 3: 1600000 expected 1600000
```

No lost updates on 3.14.0, and also none when I split the statement into `tmp = counter; counter = tmp + 1`. Do not conclude it is safe: `+=` is several bytecodes and the interpreter may switch threads between them (the default switch interval is `sys.getswitchinterval()`, 0.005 s here). It just did not happen in my runs. The same file on the free-threaded 3.14.3:

```text
no lock   run 1: 215326 expected 1600000
no lock   run 2: 209878 expected 1600000
no lock   run 3: 252377 expected 1600000
with lock run 1: 1600000 expected 1600000
```

Now about 85% of the increments vanished, because threads truly run in parallel (see {{< term "free-threading" "free-threaded Python" >}}). The fix is the same on both builds, a {{< term "mutex" "lock" >}}:

```python
lock = threading.Lock()
for _ in range(N):
    with lock:
        counter += 1
```

All three "with lock" runs gave exactly 1,600,000 on both builds. Lesson: the GIL protects the interpreter, not your data.

## A worker pool with queue.Queue

{{< term "queue" "queue.Queue" >}} is already thread-safe, so it is the clean way to hand work between threads. Three workers, ten jobs, one `None` sentinel per worker to say "stop":

```python
def worker():
    while True:
        item = q.get()
        if item is None:
            q.task_done(); break
        out.put(item * item); q.task_done()
```

`q.join()` waits until every item was marked done; the sorted output was `[0, 1, 4, 9, ..., 81]`. This is the {{< term "worker-pool" "worker pool" >}} pattern from [concurrency patterns in Go](/posts/go-concurrency-patterns/).

## Stopping threads and daemon pitfalls

There is no way to kill a thread from outside. Use a `threading.Event`: the worker loops on `while not stop.wait(0.05)` (a sleep that wakes at once when the event is set), and main calls `stop.set()` then `join()`. My demo worker printed that it saw the stop after some ticks.

A {{< term "daemon-thread" "daemon thread" >}} (`daemon=True`) is different: when the main thread ends the process exits and the daemon is dropped, with its cleanup unrun. My daemon was in `sleep(60)` and the script finished in 0.3 s total.

## asyncio, Go and Node in short

`asyncio` is the third option: one thread, an {{< term "event-loop" "event loop" >}} and `await`, very good for many sockets, like Node. A Go goroutine is scheduled by the Go runtime over several OS threads, so CPU work in goroutines runs in parallel. Node's `worker_threads` run JavaScript in separate threads with their own event loops; see [Worker threads and cluster in Node.js](/posts/node-worker-threads-cluster/).

## A few things to watch

- Threads for waiting (network, disk, `sleep`); processes for computing.
- A passing run proves nothing about races. Lock shared mutable state, or pass data through a `Queue`.
- Always `join()` or use `with ThreadPoolExecutor(...)`, so exceptions in workers are not lost.
- Do not put important cleanup in daemon threads.
- Free-threaded builds are an option, not the default; I only tried it on this tiny example, and libraries may not support it yet.

## Exercise

Write a script that fetches 20 pages from a local `http.server` with a thread pool of 5, counting how many started before the first finished. Then make the counter shared and remove the lock on the free-threaded build to see the loss.

## What's next

The next post is "Multiprocessing in Python", where CPU-bound work finally uses all cores.
