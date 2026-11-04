+++
date = '2027-03-31T10:00:00+03:30'
draft = false
title = 'The GIL and threading'
description = 'The GIL and threading in Python: what the lock does, when threads help, a lost-update race on a free-threaded build, Lock, Queue and thread pools.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "gil", "threading", "concurrency", "free-threading"]
cover = { image = "/images/covers/py-gil-threading.png", alt = "The GIL and threading", hiddenInSingle = true }
+++

Suppose you have a function that crunches numbers for ten seconds. You split the work between four {{< term "thread" "threads" >}}, run them on a four-core laptop, and expect it to finish in about three seconds. In standard Python it does not, because the threads take turns instead of running together. The reason has a name, the {{< term "gil" "GIL" >}}, and it is the first thing that surprises people who come from Go ([goroutines and channels](/posts/go-goroutines-channels/)) or Node.js ([the event loop](/posts/node-event-loop/)).

The GIL is a single lock inside the standard Python interpreter (CPython). A thread must hold it to run Python code, and there is only one of it. So even with four threads on four cores, only one of them runs Python bytecode at any moment. You can picture it as a meeting with a single microphone: everyone can be in the room, but only the person holding the microphone speaks.

That sounds like a disaster, so it helps to see exactly what it blocks and what it does not. After [testing the code](/posts/py-testing-pytest/), this post makes it concurrent, and answers three questions: when do threads help, what can still go wrong with them, and what do you do instead when they do not help.

> I ran the demos with Python 3.14.0 (`python3 --version`), the standard build with the GIL: `sys._is_gil_enabled()` printed `True`. The comparison with a build without the GIL, in the race section, is from the original run of this post on Python 3.14.3 free-threaded (`python3.14t`, installed with `uv python install 3.14t` and deleted afterwards), where `sys._is_gil_enabled()` printed `False`; I did not install that build again, so I did not re-run it. The machine was heavily loaded (one-minute load average above 10 while I re-ran the demos), so I publish **no timings for CPU work**. The one time I show is a sleep, which does not depend on load. The demos are local scripts.

## The picture: one microphone

Here is a schematic of how two threads that both compute look under the GIL (a drawing of the idea, not a measurement). `A` and `B` are threads, and a dot means "not running Python code at that moment":

```text
CPU-bound, 2 threads, with the GIL:
  thread A:  AAAA....AAAA....AAAA
  thread B:  ....BBBB....BBBB....
  (one thread at a time; the interpreter hands the GIL over every so often)

I/O-bound, 2 threads, with the GIL:
  thread A:  A~~~~~~~~~~~~~~~~~~A     ~ = waiting (sleep, socket), GIL released
  thread B:  .B~~~~~~~~~~~~~~~~~B
  (both wait at the same time; each holds the GIL only for its short bursts of Python code)
```

Two things in this picture matter. When two threads compute, they take turns, so the total work done per second is the same as for one thread. When a thread waits, it gives the GIL away, so the others can run and the waits overlap. That one difference decides when threads are worth using.

## Threads help when they wait

While a thread blocks on I/O (a network call, a file read) or on `sleep`, the GIL is released and other threads run. To see it without a network, the demo `io.py` uses `time.sleep(0.2)` as a stand-in for a network wait. Ten tasks, first one after another, then in ten threads:

```text
sequential, 10 x 0.2s: ~2.0s
10 threads:           ~0.2s [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

Sequentially, the ten waits add up to about 2 seconds. With ten threads, all ten wait at the same time and the total is about one wait, 0.2 seconds. The elapsed time dropped tenfold, because sleeping is waiting and not computing. (These two numbers are rounded to one decimal and are dominated by the sleeps, so machine load does not change them.) The code used `ThreadPoolExecutor(max_workers=10)` and `ex.map(fetch, range(10))`. That is the simplest threading API: a {{< term "thread-pool" "thread pool" >}} that runs the function in its threads and returns the results in input order.

For CPU-bound pure Python the picture is the first one: threads take turns, so four threads do not give four times the speed. I did **not** measure it, because the machine load would make any number meaningless. According to the Python docs, use processes for CPU work; that is the next post.

## The race the GIL does not prevent

A common wrong conclusion is: "only one thread runs at a time, so my shared data is safe." It is not. A {{< term "race-condition" "race condition" >}} does not need parallelism. It only needs a thread switch between two steps of an operation. Look at how Python executes `counter += 1`. This is the bytecode of a function that does it on a global variable (printed in a scratch script with the `dis` module):

```text
LOAD_GLOBAL              0 (counter)
LOAD_SMALL_INT           1
BINARY_OP               13 (+=)
STORE_GLOBAL             0 (counter)
```

One line of Python is four steps: read the value, load 1, add, store. If thread A reads `5`, then the interpreter switches to thread B, which reads `5`, adds one and stores `6`, and then A adds one to its old `5` and stores `6` too, one increment is lost. The interpreter can switch threads between bytecodes; the default switch interval is `sys.getswitchinterval()`, which printed `0.005` seconds here.

The demo `race.py` runs 8 threads that each do `counter += 1` 200,000 times, three times without a lock. The expected total is 1,600,000. On 3.14.0 with the GIL:

```text
no lock   run 1: 1600000 expected 1600000
no lock   run 2: 1600000 expected 1600000
no lock   run 3: 1600000 expected 1600000
```

No lost updates, even in `race2.py`, where I split the statement by hand into `tmp = counter` and `counter = tmp + 1` (it printed `1600000` too). Please do not read this as "it is safe". It only means the switch did not happen at a bad moment in these runs. The code is still wrong, and the free-threaded build shows it. This is the same file on Python 3.14.3 without the GIL, from the original run (see {{< term "free-threading" "free-threaded Python" >}}):

```text
no lock   run 1: 215326 expected 1600000
no lock   run 2: 209878 expected 1600000
no lock   run 3: 252377 expected 1600000
with lock run 1: 1600000 expected 1600000
```

Here about 85% of the increments disappeared, because threads really run at the same time and constantly overwrite each other's results. The fix is the same on both builds, a {{< term "mutex" "lock" >}}:

```python
lock = threading.Lock()
for _ in range(N):
    with lock:
        counter += 1
```

Only one thread at a time can be inside `with lock:`, so the read, add and store of one thread finish before another thread starts. All three "with lock" runs gave exactly 1,600,000 on 3.14.0 (and on the free-threaded build in the original run). The lesson: the GIL protects the interpreter's own data, not yours.

## A worker pool with queue.Queue

Locks are easy to forget. A calmer way to share work between threads is to pass it through a {{< term "queue" "queue.Queue" >}}, which is already thread-safe: one thread puts an item in, another takes it out, and nobody touches the same variable. The demo `pool.py` starts three workers, puts ten jobs in the queue, and then puts one `None` per worker as a sentinel, a marker that means "no more work, stop":

```python
def worker():
    while True:
        item = q.get()
        if item is None:
            q.task_done(); break
        out.put(item * item); q.task_done()
```

Each worker takes an item, squares it and puts the result in a second queue. `task_done()` tells the queue that an item was handled, and `q.join()` in the main thread waits until every item was marked done. The sorted output was:

```text
[0, 1, 4, 9, 16, 25, 36, 49, 64, 81]
```

(I sort it because the workers finish in no fixed order.) This is the {{< term "worker-pool" "worker pool" >}} pattern from [concurrency patterns in Go](/posts/go-concurrency-patterns/), written with threads and a queue.

## Stopping threads, and daemon threads

There is no way to kill a thread from outside. You ask it to stop, and it has to agree. The usual tool is a `threading.Event`. In the demo `event.py`, the worker loops on `while not stop.wait(0.05)`, which is a 50 ms sleep that wakes up at once when the event is set. After 0.3 seconds main calls `stop.set()` and then `join()`. The output was:

```text
worker saw stop after some ticks
```

A {{< term "daemon-thread" "daemon thread" >}} (`daemon=True`) is different. When the main thread ends, the process exits and daemon threads are dropped on the spot, with their cleanup code never running. In the same demo a daemon thread sat in `sleep(60)`, and the script still finished at once, printing:

```text
main exits; daemon thread is killed, its cleanup never runs
```

## asyncio, Go and Node in short

`asyncio` is the third option next to threads and processes: one thread, an {{< term "event-loop" "event loop" >}} and `await`. It is very good for many sockets waiting at once, in the same spirit as Node; the post after next covers it. A Go goroutine is scheduled by the Go runtime over several OS threads, so CPU work in goroutines runs in parallel, which is exactly what Python threads cannot do. Node's `worker_threads` run JavaScript in separate threads, each with its own event loop; see [Worker threads and cluster in Node.js](/posts/node-worker-threads-cluster/).

## Where threads fall short

- Use threads for waiting (network, disk, `sleep`) and processes for computing.
- A passing run proves nothing about races, as the three clean runs above showed. Lock shared mutable data, or pass it through a `Queue`.
- Always `join()` your threads or use `with ThreadPoolExecutor(...)`, so that exceptions inside workers are not lost.
- Do not put important cleanup in daemon threads: it will not run when the program exits.
- Free-threaded builds are an option, not the default. I only tried one on this tiny example, and libraries may not support it yet.

## Exercise

Write a script that fetches 20 pages from a local `http.server` with a thread pool of 5, counting how many started before the first finished. Then make the counter shared and remove the lock on the free-threaded build to see the loss.

## What's next

Since threads cannot make pure Python code compute in parallel, the next post is "Multiprocessing in Python", where CPU-bound work finally uses all the cores.
