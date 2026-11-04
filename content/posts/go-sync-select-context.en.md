+++
date = '2026-11-26T10:00:00+03:30'
draft = false
title = 'sync, select and context in Go'
description = 'Go sync, select and context: protect shared state with Mutex, RWMutex, atomic and Once, wait on channels with select and cancel work, with race output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "context", "sync", "select"]
cover = { image = "/images/covers/go-sync-select-context.png", alt = "sync, select and context in Go", hiddenInSingle = true }
+++

In [Goroutines and channels in Go](/posts/go-goroutines-channels/) we met two problems and left them half-finished. First: when several goroutines must touch the same memory, what do we do? (Remember the counter of 1000 goroutines that gave a wrong answer.) Second: how do we tell a goroutine "drop what you are doing"? Without an answer to the first we have races, and without an answer to the second we have goroutines that never end and leak.

This post answers both with three tools: the `sync` package to protect shared memory, the `select` statement to wait on several things at once, and the `context` package for cancellation and timeouts.

> Everything below was run with Go 1.26 on macOS (arm64). I shortened file paths in the outputs.

## A race and its fix with a mutex

First, the problem again. The classic broken counter: 1000 goroutines all increasing one variable, with no protection:

```go
counter := 0
for i := 0; i < 1000; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		counter++ // unprotected
	}()
}
```

Why is it broken? Because `counter++` is made of three steps (read, add one, write), and two goroutines can both do the first step before either does the last. Ordinary runs gave numbers like `counter: 850` and `counter: 984` (in my first two runs), and when I ran it again for this text I got `counter: 972`. It was never a reliable 1000. The **race detector** (`go run -race`) names the problem. This is the shortened report:

```
WARNING: DATA RACE
Read at 0x00c000094048 by goroutine 11:
  main.main.func1()
      racy/main.go:15 +0x68

Previous write at 0x00c000094048 by goroutine 7:
  main.main.func1()
      racy/main.go:15 +0x78
...
Found 2 data race(s)
exit status 66
```

The report says one goroutine reads from an address another goroutine had written to earlier, both on line 15, which is `counter++`. (Goroutine numbers change from run to run.)

The first fix is **sync.Mutex**. A {{< term "mutex" "mutex" >}} is a lock: at any moment it lets only one goroutine into the critical section, the code between `Lock` and `Unlock`. The others wait on `Lock`.

```go
var mu sync.Mutex
mu.Lock()
counter++
mu.Unlock()
```

With the lock, `-race` is silent and we get `mutex counter: 1000`.

Sometimes data is read far more often than it is written (a map that rarely changes, say). There **sync.RWMutex** helps: it allows many readers at once (`RLock`), or a single writer (`Lock`) with no readers. In methods, release the lock with `defer` so an early `return` cannot leave it locked:

```go
type SafeCounter struct {
	mu sync.RWMutex
	n  map[string]int
}

func (c *SafeCounter) Inc(key string) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.n[key]++
}

func (c *SafeCounter) Get(key string) int {
	c.mu.RLock()
	defer c.mu.RUnlock()
	return c.n[key]
}
```

Here the lock sits inside the struct next to the data it protects, and the methods use pointer receivers because a lock must not be copied (see the last section).

## atomic and Once

For a single number, locking is overkill. The `sync/atomic` package has operations that complete in one uninterruptible step, like `hits.Add(1)`. They are usually lighter than a mutex. And **sync.Once** runs a function exactly once, however many goroutines call it at the same time; it is good for lazy initialization, meaning "build it the first time it is needed".

I put these pieces together in one program with 1000 goroutines: one counter with a mutex, one with atomic, one RWMutex-protected map, and a `once.Do`:

```go
var hits atomic.Int64
var once sync.Once

once.Do(func() { fmt.Println("init runs once") })
hits.Add(1)
```

```
init runs once
mutex counter: 1000
atomic counter: 1000
rwmutex map: 1000
```

1000 goroutines called `once.Do`, and `init runs once` was printed only once. All three counters were exactly 1000 (again under `-race`, with no warning).

## select: waiting on several channels

Now to the second question, but first we need a tool: how do we wait on several channels at once? **select** is like `switch`, for channel operations. It waits until one of the cases can proceed and runs that one. With a `default` branch it never blocks, and with `time.After` you get a timeout.

The example program has three `select`s. In the first, two goroutines send something after 50 and 200 milliseconds, and a loop does `select` twice. The second is on a channel nobody sends to, with `default`. The third is on a channel that never receives anything, with a 100 ms timeout:

```go
for i := 0; i < 2; i++ {
	select {
	case m := <-fast:
		fmt.Println("got", m)
	case m := <-slow:
		fmt.Println("got", m)
	}
}

select {
case v := <-ch:
	fmt.Println("got", v)
default:
	fmt.Println("nothing ready")
}

select {
case v := <-never:
	fmt.Println("got", v)
case <-time.After(100 * time.Millisecond):
	fmt.Println("timeout")
}
```

```
got fast
got slow
nothing ready
timeout
```

The first two lines belong to the loop: the first `select` proceeded on whichever was ready first (`fast`) and the second time on the other (`slow`). Third line: since `ch` has nothing, `default` ran and nothing blocked. Last line: `never` never sends, so after 100 ms the `time.After` case proceeded. If several cases are ready at the same time, Go picks one at random.

## context: cancellation and deadlines

Now the second question: how do we tell a goroutine to stop? A **{{< term "context" "context" >}}.Context** carries a cancellation signal between goroutines. From it you get a channel, `ctx.Done()`, which is closed when the context ends, and `ctx.Err()` tells you why. A goroutine only has to listen to `ctx.Done()` in a `select`. Contexts form a tree: cancelling a parent context cancels its children too.

A worker that runs under a context looks like this. Every 20 ms it prints a tick, and when the context is cancelled it prints the reason and returns. It also has an `atomic.Bool` so that we can ask from outside whether it really stopped:

```go
func worker(ctx context.Context, stopped *atomic.Bool) {
	defer stopped.Store(true)
	t := time.NewTicker(20 * time.Millisecond)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			fmt.Println("worker: stopping:", ctx.Err())
			return
		case <-t.C:
			fmt.Println("worker: tick")
		}
	}
}
```

`main` starts this worker, waits 70 ms, asks for the status, calls `cancel()`, waits another 50 ms and asks again. Then it prints `Err` after `WithCancel`, `WithTimeout` and `WithDeadline`:

```
worker: tick
worker: tick
worker: tick
stopped before cancel: false
worker: stopping: context canceled
stopped after cancel: true
Err after cancel: context canceled true
timeout Err: context deadline exceeded true
deadline Err: context deadline exceeded
```

Three ticks in 70 ms (the exact count depends on scheduling), and `stopped before cancel: false`: the worker is still alive. After `cancel()` the message `worker: stopping: context canceled` appeared and `stopped after cancel: true`: it really stopped. The last three lines show the reasons: `WithCancel` gives `context.Canceled`, and `WithTimeout` and `WithDeadline` both give `context.DeadlineExceeded` (the `true` at the end of a line means it equals that value). After creating any of them, always `defer cancel()` so its resources are released.

## fetch with a timeout

Now a more realistic example: a function that does slow work (say, a network request) and must finish in a given time. I simulated the slow work with `time.Sleep`, so no network is needed. By convention, `ctx` is the **first parameter** of the function. The work runs in a goroutine, and the function uses `select` to wait for either the result or the cancellation:

```go
func fetch(ctx context.Context, id int) (string, error) {
	result := make(chan string, 1)
	go func() {
		time.Sleep(300 * time.Millisecond)
		result <- fmt.Sprintf("user-%d", id)
	}()
	select {
	case r := <-result:
		return r, nil
	case <-ctx.Done():
		return "", ctx.Err()
	}
}
```

We call it once with a 100 ms timeout, which the work (300 ms) cannot meet, and once with 1 second:

```
error: context deadline exceeded
is deadline exceeded: true
result: user-2 err: <nil>
```

The first time the timeout arrived before the result: `context deadline exceeded`. And `errors.Is(err, context.DeadlineExceeded)` is `true`, so you can tell the kind of error. The second time there was a whole second, and `user-2` arrived. Why does the channel have a buffer of 1? Suppose it had none and the function had returned because of the timeout. After 300 ms the worker goroutine would try to send the result with nobody listening, and it would be stuck forever (a leak). With a buffer of 1, the send completes even without a receiver and the goroutine goes away.

## Misusing locks and context

- **Don't copy a `sync.Mutex` after first use.** According to the `sync` docs it must not be copied. A copy of a lock has its own separate state, so two goroutines that each lock a different copy do not exclude each other. Pass the struct by pointer.
- **Keep the critical section short.** Don't hold a lock during slow I/O (network, disk), because every other goroutine waits.
- **Don't store a context in a struct.** According to the `context` docs, pass it as the first parameter of a function, named `ctx`.
- **`context.WithValue` is for request-scoped data**, like a request ID. It is not for optional parameters, config or a database connection, because it hides the dependency from the reader.
- **`time.After` in a busy loop** creates a fresh timer on every iteration. There, use `time.NewTimer`, which can be reused, or use a context.

## Exercise

1. Replace the counter's mutex with `atomic.Int64` and make sure `-race` stays silent.
2. Make `fetch` answer in 50 ms and see that the 100 ms timeout no longer fires.
3. Write a worker that prints a tick every 100 ms and stops after 350 ms using `context.WithTimeout`.

## What's next

"Generics in Go". After concurrency comes writing one piece of code for several types: type parameters and constraints, and when they are really worth using.
