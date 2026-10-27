+++
date = '2027-04-14T10:00:00+03:30'
draft = false
title = 'asyncio in Python'
description = 'asyncio in Python: coroutines vs tasks, TaskGroup, cancellation and timeouts, a blocking call that freezes it, Queue, Semaphore and a TCP echo server.'
categories = ["Python"]
series = ["Python"]
tags = ["python", "asyncio", "concurrency", "async", "taskgroup"]
cover = { image = "/images/covers/py-asyncio.png", alt = "asyncio in Python", hiddenInSingle = true }
+++

In the [previous post](/posts/py-multiprocessing/) we used processes for CPU work. For waiting on sockets, `asyncio` is the third option next to threads (see [the GIL and threading](/posts/py-gil-threading/)). If you know Node.js ([the event loop](/posts/node-event-loop/), [promises and async/await](/posts/node-promises-async-await/)) most of it will feel familiar; the differences are where it gets interesting.

> Python 3.14.0, standard library only. The machine was heavily loaded, so I publish counts, orderings and booleans, **no timings**. Demo scripts are local examples.

## Coroutines and tasks

An `async def` function returns a {{< term "coroutine" "coroutine" >}} when called; it runs only when awaited or scheduled on the {{< term "event-loop" "event loop" >}}. Each job logs start, sleeps 0.1 s, logs end. Three jobs, awaited one by one, then with `asyncio.gather`:

```text
sequential: ['start 0', 'end 0', 'start 1', 'end 1', 'start 2', 'end 2']
gather    : ['start 0', 'start 1', 'start 2', 'end 0', 'end 1', 'end 2'] [0, 1, 2]
```

`await job()` runs the job to the end before moving on. `gather` wraps each coroutine in a task, so all start before any finishes. With ten tasks in an `asyncio.TaskGroup`, 10 events were logged before the first "end 0", and the results were `[0, ..., 9]` in creation order.

All of them ran on one thread: I collected `threading.get_ident()` from ten tasks and `len(ids) == 1` was `True`, equal to the main thread's id. Tasks switch only at `await`, so you rarely need locks for plain in-memory state between awaits.

## A blocking call freezes the loop

A ticker task increments a counter every 10 ms. While a coroutine calls `time.sleep(0.5)`, the ticker count changed by:

```text
ticks during blocking time.sleep(0.5): 0
ticks during to_thread(time.sleep, 0.5): True
```

Zero ticks: nobody else ran. With `await asyncio.to_thread(time.sleep, 0.5)` the call goes to a thread and the ticker kept going (I print only whether it got at least 20 ticks, not the exact count). `loop.run_in_executor` does the same with an explicit executor. This is the same lesson as a long synchronous task in Node. Go differs here: goroutines are scheduled by the runtime over several OS threads, so one goroutine's blocking call does not stop the others ([goroutines and channels](/posts/go-goroutines-channels/)).

## Forgetting await

```python
async def forgot():
    asyncio.sleep(0.1)   # no await
asyncio.run(forgot())
```

```text
<string>:4: RuntimeWarning: coroutine 'sleep' was never awaited
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

The call created a coroutine and threw it away. Unlike a JavaScript promise, it never even starts. Run with `python3 -X dev` for a longer traceback of where it was created.

## Cancellation and timeouts

`task.cancel()` raises `CancelledError` inside the task at its current `await`. Output:

```text
slow: cleanup, got CancelledError
cancelled: True
timeout() -> TimeoutError
wait_for -> TimeoutError
```

The task ran its `except` block, re-raised, and `t.cancelled()` was `True`. Always re-raise `CancelledError` after cleanup. `async with asyncio.timeout(0.1)` and `await asyncio.wait_for(coro, 0.1)` both turned a 5 s sleep into `TimeoutError` (builtin in 3.11+).

## TaskGroup: structured concurrency

A `TaskGroup` is {{< term "structured-concurrency" "structured concurrency" >}}: no task escapes the `async with` block, and when one fails the others are cancelled. I started a long sleeper plus two tasks raising `ValueError` and `KeyError` at 10 ms and 20 ms:

```text
sibling cancelled by TaskGroup
ValueError group: ['bad value']
```

Failures arrive as an {{< term "exception-group" "ExceptionGroup" >}}, handled with `except*` (see [errors and context managers](/posts/py-errors-context-managers/)). My `KeyError` branch never printed: the group cancelled that task before it raised. So you do not always see every error, only those that happened before cancellation.

## Queue and Semaphore

An `asyncio.Queue(maxsize=2)` between one producer and one consumer gives {{< term "backpressure" "backpressure" >}}: `put` waits when the queue is full. The consumer squared six numbers: `[0, 1, 4, 9, 16, 25]`.

To cap concurrency, use a {{< term "semaphore" "semaphore" >}}. Twenty tasks, `asyncio.Semaphore(3)`, a counter of tasks inside the block:

```text
semaphore limit 3, peak concurrent: 3
```

The peak was exactly the limit, which makes it a deterministic check.

## A TCP echo server

```python
async def handle(r, w):
    while data := await r.readline():
        w.write(data.upper()); await w.drain()
    w.close(); await w.wait_closed()

srv = await asyncio.start_server(handle, "127.0.0.1", 0)
```

Port 0 lets the OS pick a free port. Five clients connected at once with `gather` and each got its line back uppercased:

```text
['HELLO 0', 'HELLO 1', 'HELLO 2', 'HELLO 3', 'HELLO 4']
```

One thread served all five connections. Compare it with [a TCP server from scratch](/posts/net-sockets-tcp-from-scratch/).

## A few things to watch

- Never call blocking code (`time.sleep`, `requests`, heavy CPU) in a coroutine; use `to_thread` or a process pool.
- Always `await` coroutines; read the `never awaited` warning.
- Prefer `TaskGroup` over bare `create_task`; keep a reference to tasks you create.
- Re-raise `CancelledError`; do not swallow it.
- Put a timeout on every network call.

## Exercise

Write a script that fetches 30 URLs from a local `http.server` through `open_connection`, with a semaphore of 5, and prints the peak concurrency. Then add `asyncio.timeout(0.5)` and make one URL slow.

## What's next

The next post is "Building an API with FastAPI and Pydantic", where `async def` handlers run on this event loop.
