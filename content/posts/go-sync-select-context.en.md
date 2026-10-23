+++
date = '2026-11-26T10:00:00+03:30'
draft = false
title = 'sync, select and context in Go'
description = 'Go sync, select and context: protect shared state with Mutex, RWMutex, atomic and Once, wait on channels with select and cancel work, with race output.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "context", "sync", "select"]
cover = { image = "/images/covers/go-sync-select-context.png", alt = "sync, select and context in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-goroutines-channels/) we started goroutines and talked to them over channels. Two questions were left open: what do we do when goroutines must share memory, and how do we tell a goroutine to stop? This post answers both with the `sync` package, `select` and `context`.

> Everything below was run with Go 1.26 on macOS (arm64).

## A race, and the fix with a mutex

Here is the classic broken counter: 1000 goroutines incrementing one variable.

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

Plain runs print `counter: 850` and `counter: 984` on two different attempts, never reliably 1000. The **race detector** (`go run -race`) names the problem; this is the trimmed report:

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

A **sync.Mutex** lets one goroutine at a time into a critical section:

```go
var mu sync.Mutex
mu.Lock()
counter++
mu.Unlock()
```

With the lock, `-race` is silent and we get `mutex counter: 1000`. When reads vastly outnumber writes, **sync.RWMutex** allows many readers (`RLock`) or one writer (`Lock`). Always pair the lock with `defer` in a method so an early return can't leave it locked:

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

## atomic and Once

For a single number, `sync/atomic` is lighter than a mutex. **sync.Once** runs a function exactly once, no matter how many goroutines call it, which suits lazy initialization:

```go
var hits atomic.Int64
var once sync.Once

once.Do(func() { fmt.Println("init runs once") })
hits.Add(1)
```

Running all three together with 1000 goroutines (also under `-race`):

```
init runs once
mutex counter: 1000
atomic counter: 1000
rwmutex map: 1000
```

## select: waiting on several channels

**select** is like `switch` for channel operations: it waits until one case can proceed. With a `default` it never blocks, and with `time.After` it gives a timeout.

```go
select {
case m := <-fast:
	fmt.Println("got", m)
case m := <-slow:
	fmt.Println("got", m)
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

If several cases are ready at once, Go picks one at random.

## context: cancellation and deadlines

A **context.Context** carries a cancellation signal across goroutines. `ctx.Done()` is a channel that closes when the context ends, and `ctx.Err()` tells you why. A worker that stops when cancelled, and a check that it really stopped:

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

The last three lines come from `WithCancel` (`context.Canceled`), `WithTimeout` and `WithDeadline` (both `context.DeadlineExceeded`). Always `defer cancel()` after creating one, so its resources are released.

## A fetch with a timeout

The slow work is simulated with `time.Sleep`, so no network is needed. By convention `ctx` is the **first parameter**:

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

With a 100 ms timeout, then a 1 s timeout:

```
error: context deadline exceeded
is deadline exceeded: true
result: user-2 err: <nil>
```

The channel has buffer 1 so the abandoned goroutine can still finish its send instead of leaking.

## A few things to watch

- Never copy a `sync.Mutex` after first use; pass the struct by pointer.
- Keep critical sections short, and don't hold a lock while doing slow I/O.
- Don't store a context inside a struct; pass it as the first argument, named `ctx`.
- `context.WithValue` is for request-scoped data like a request ID, not for optional parameters, config or database handles.
- `time.After` in a hot loop creates a timer on every iteration; use `time.NewTimer` or a context there.

## Exercise

1. Replace the mutex in the counter with `atomic.Int64` and confirm `-race` stays quiet.
2. Make `fetch` return the result in 50 ms and see that a 100 ms timeout no longer fires.
3. Write a worker that prints a tick every 100 ms and stops after 350 ms using `context.WithTimeout`.

## What's next

Next up is generics in Go: type parameters, constraints, and when they are worth using.
