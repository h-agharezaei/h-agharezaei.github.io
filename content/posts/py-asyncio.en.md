+++
date = '2027-04-14T10:00:00+03:30'
draft = false
title = 'asyncio in Python'
description = 'asyncio in Python: coroutines vs tasks, TaskGroup, cancellation and timeouts, a blocking call that freezes it, Queue, Semaphore and a TCP echo server.'
contentType = 'tutorial'
categories = ["Python"]
series = ["Python"]
tags = ["python", "asyncio", "concurrency", "async", "taskgroup"]
cover = { image = "/images/covers/py-asyncio.png", alt = "asyncio in Python", hiddenInSingle = true }
+++

Here is a puzzle. A small task is supposed to tick every 10 milliseconds. Another task, running next to it, calls `time.sleep(0.5)`. How many ticks does the first task get during that half second? Not fifty. Zero. One blocking call stopped everything, and understanding why is the key to `asyncio`.

Imagine you have a thousand network calls to make, and each one spends almost all its time waiting for a reply. You could start a thousand threads, but that is heavy. `asyncio` takes another approach: **one thread, and tasks that politely step aside whenever they have to wait**. While one task waits for its reply, the thread runs another task. Everything shares one thread and switches only at the keyword `await`.

That is the third option for concurrency in Python, next to threads (see [the GIL and threading](/posts/py-gil-threading/)) and the processes we used for CPU work in [the previous post](/posts/py-multiprocessing/). It is meant for waiting on sockets, not for computing. If you know Node.js ([the event loop](/posts/node-event-loop/), [promises and async/await](/posts/node-promises-async-await/)), most of it will feel familiar. The differences are where it gets interesting.

> I re-ran all the demos with Python 3.14.0, standard library only. The machine was heavily loaded (the one-minute load average was between 11 and 14), so I publish counts, orderings and booleans, **no timings**. The demo scripts are local examples.

## The idea in one picture

An `async def` function is a function that can pause. It pauses at `await`, and that is the only place it can. The program that decides who runs next is the {{< term "event-loop" "event loop" >}}. Here is a trace of two tasks that each do some work, wait, and finish:

```text
time ->
task A:  [run A] await sleep ........................ [run A: finish]
task B:           [run B] await sleep ............................ [run B: finish]
loop:    A runs until its await, then B runs until its await,
         then the loop has nothing to do and waits for a timer to fire.
```

Notice that nobody interrupts a task. A task runs until it reaches `await`, and only then does the loop move on. This is called cooperative multitasking. It is simple and predictable, but it also explains the puzzle above: a task that never reaches an `await` never lets anyone else run.

## Coroutines and tasks

When you call an `async def` function, the body does not run. You get back a {{< term "coroutine" "coroutine" >}}, an object that represents "this call, not started yet". It runs only when you `await` it or hand it to the event loop to schedule. A coroutine that the loop is running on its own is called a *task*.

In the demo `d1.py` each job logs `start`, sleeps 0.1 seconds, logs `end` and returns its number. First, three jobs awaited one by one, then the same three through `asyncio.gather`:

```text
sequential: ['start 0', 'end 0', 'start 1', 'end 1', 'start 2', 'end 2']
gather    : ['start 0', 'start 1', 'start 2', 'end 0', 'end 1', 'end 2'] [0, 1, 2]
```

`await job()` runs the job to the end before the next line, so the log is strictly start, end, start, end. `gather` wraps each coroutine in a task, so all three start before any of them finishes: the log shows three starts, and only then the three ends. The list at the end holds the results in order. The demo then used ten tasks in an `asyncio.TaskGroup` (more on it below):

```text
taskgroup: started before first end: 10 results: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
```

The number is the position of `end 0` in the log, so all 10 `start` events came first, and the results come back in creation order.

All of this ran on one thread. The demo collected `threading.get_ident()` from ten tasks and put the values in a set:

```text
one thread for all tasks: True same as main: True
```

The set had one element, equal to the main thread's id. Since tasks switch only at `await`, you rarely need locks for plain in-memory data between two awaits: nobody can jump in between.

## A blocking call freezes the loop

Now the puzzle. The demo `d2.py` starts a ticker task that adds 1 to a counter every 10 ms (`await asyncio.sleep(0.01)` between increments). Then it measures how much the counter grew while another coroutine blocked for half a second, in two ways:

```text
ticks during blocking time.sleep(0.5): 0
ticks during to_thread(time.sleep, 0.5): True
```

With plain `time.sleep(0.5)` the answer is 0: the sleep never hands control back, so the ticker could not run once. With `await asyncio.to_thread(time.sleep, 0.5)` the blocking call runs in a separate thread, and the event loop stays free, so the ticker kept going. For this second case I print only whether the counter grew by at least 20, not the exact count, because the exact count depends on the machine. `loop.run_in_executor` does the same with an executor you choose.

The lesson is the same as with a long synchronous task in Node: **never run blocking code directly in a coroutine**. Go behaves differently here: goroutines are scheduled by the runtime over several OS threads, so one goroutine's blocking call does not stop the others ([goroutines and channels](/posts/go-goroutines-channels/)).

## Forgetting await

The most common beginner mistake is calling a coroutine function without `await`:

```python
async def forgot():
    asyncio.sleep(0.1)   # no await
asyncio.run(forgot())
```

```text
<demo>/d1.py:36: RuntimeWarning: coroutine 'sleep' was never awaited
  asyncio.sleep(0.1)   # no await
RuntimeWarning: Enable tracemalloc to get the object allocation traceback
```

The call created a coroutine object and threw it away, so the sleep never happened. Unlike a JavaScript promise, a coroutine does not even start until it is awaited. Python warns you when the object is deleted. If you run with `python3 -X dev`, the warning also prints where the coroutine was created.

## Cancellation and timeouts

Waiting forever is a bug, so tasks must be cancellable. `task.cancel()` raises `CancelledError` inside the task, at the `await` where it is currently paused. In `d3.py` a task sleeps for 10 seconds, catches the error to clean up, and re-raises it. Then two ways to put a time limit on a 5-second sleep:

```text
slow: cleanup, got CancelledError
cancelled: True
timeout() -> TimeoutError
wait_for -> TimeoutError
```

The first line is the task's own `except` block running. `t.cancelled()` was `True` afterwards. Always re-raise `CancelledError` after cleanup, because the cancellation has to finish. `async with asyncio.timeout(0.1)` and `await asyncio.wait_for(coro, 0.1)` both turned the long sleep into a `TimeoutError`. That is the built-in `TimeoutError` in Python 3.11 and later.

## TaskGroup: structured concurrency

A `TaskGroup` is a way to start several tasks and be sure none of them is forgotten. It is {{< term "structured-concurrency" "structured concurrency" >}}: no task escapes the `async with` block, the block waits for all of them, and when one fails the others are cancelled. In the demo I started a long sleeper plus two tasks that raise `ValueError` at 10 ms and `KeyError` at 20 ms:

```text
sibling cancelled by TaskGroup
ValueError group: ['bad value']
```

The `ValueError` came first, so the group cancelled the sleeper, which printed its message. Failures arrive together as an {{< term "exception-group" "ExceptionGroup" >}}, and `except*` handles them by type (see [errors and context managers](/posts/py-errors-context-managers/)). Notice what is missing: my `KeyError` branch never printed. That task was cancelled at 10 ms, before its 20 ms wait finished, so it never got to raise. A group tells you about the errors that happened before cancellation, not about every error that could have happened.

## Queue and Semaphore

Two tools help when tasks have to share work. An `asyncio.Queue(maxsize=2)` between one producer and one consumer gives {{< term "backpressure" "backpressure" >}}: when the queue holds two items, `put` waits until the consumer takes one, so a fast producer cannot flood a slow consumer. The demo's consumer squared six numbers and collected `[0, 1, 4, 9, 16, 25]`.

To cap how many tasks do something at once, use a {{< term "semaphore" "semaphore" >}}, a counter that allows only N tasks inside a block. The demo starts twenty tasks with `asyncio.Semaphore(3)` and counts how many are inside at the same time:

```text
semaphore limit 3, peak concurrent: 3
```

The peak was exactly the limit. It does not depend on timing, which makes it a reliable check.

## A TCP echo server

Finally, the use case `asyncio` is made for: many connections on one thread. This server reads a line from each client and sends it back in upper case:

```python
async def handle(r, w):
    while data := await r.readline():
        w.write(data.upper()); await w.drain()
    w.close(); await w.wait_closed()

srv = await asyncio.start_server(handle, "127.0.0.1", 0)
```

Port 0 lets the operating system pick a free port. The demo's five clients connect at the same time through `gather`, each sends `hello <i>` and reads one line back:

```text
['HELLO 0', 'HELLO 1', 'HELLO 2', 'HELLO 3', 'HELLO 4']
```

One thread served all five connections, switching at each `await`. If you want to see the same thing without `asyncio`, compare it with [a TCP server from scratch](/posts/net-sockets-tcp-from-scratch/).

## asyncio traps

- Never call blocking code (`time.sleep`, `requests`, heavy CPU work) inside a coroutine. Use `to_thread` or a process pool.
- Always `await` coroutines, and read the `never awaited` warning when you see it.
- Prefer `TaskGroup` over a bare `create_task`, and keep a reference to any task you create, so it is not lost.
- Re-raise `CancelledError`; do not swallow it.
- Put a timeout on every network call. Without one, a silent peer can make a task wait forever.

## Exercise

Write a script that fetches 30 URLs from a local `http.server` through `open_connection`, with a semaphore of 5, and prints the peak concurrency. Then add `asyncio.timeout(0.5)` and make one URL slow.

## What's next

An `async def` function is only useful if something runs it, so the next post is "Building an API with FastAPI and Pydantic", where `async def` handlers run on this event loop.
