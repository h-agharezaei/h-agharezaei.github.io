+++
date = '2026-11-22T10:00:00+03:30'
draft = false
title = 'Goroutines and channels in Go'
description = 'Go goroutines and channels: WaitGroup, buffered and unbuffered channels, deadlocks, a worker pipeline and the race detector, with real program output.'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "goroutines", "channels"]
cover = { image = "/images/covers/go-goroutines-channels.png", alt = "Goroutines and channels in Go", hiddenInSingle = true, hiddenInList = true }
+++

In the [previous post](/posts/go-packages-modules/) we organised code into packages and modules. Now we get to the feature Go is most known for: concurrency. This post covers goroutines, `sync.WaitGroup`, channels, the deadlock error everyone meets once, a small producer/worker pipeline, and the race detector. Next time we add `sync`, `select` and `context`.

> Everything below was run with Go 1.26 on macOS (arm64). Outputs that depend on scheduling are marked as such.

## Concurrency is not parallelism

**Concurrency** is about structuring a program as independent tasks that make progress in overlapping time. **Parallelism** is about actually running them at the same instant on several CPU cores. Go gives you the first by making tasks cheap; the runtime then spreads them over cores when it can. You write concurrent code and the scheduler decides how parallel it is.

## `go f()` and the main exit

Putting `go` before a function call starts it as a **goroutine**, a lightweight task managed by the Go runtime. The call returns immediately.

```go
func main() {
	go func() {
		time.Sleep(100 * time.Millisecond)
		fmt.Println("hello from goroutine")
	}()
	fmt.Println("main is done")
}
```

```
main is done
```

The goroutine never printed. When `main` returns, the program exits and every other goroutine is killed, finished or not. We need a way to wait.

## `sync.WaitGroup`

A **WaitGroup** is a counter: `Add` before starting, `Done` when finished, `Wait` blocks until it is zero.

```go
var wg sync.WaitGroup
for i := 1; i <= 3; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		time.Sleep(time.Duration(i) * 50 * time.Millisecond)
		fmt.Println("worker", i, "done")
	}()
}
wg.Wait()
fmt.Println("all done")
```

```
worker 1 done
worker 2 done
worker 3 done
all done
```

The sleeps make the order deterministic here. Without them it would vary between runs. Call `Add` in the starting goroutine, not inside the new one, otherwise `Wait` might run first.

## Unbuffered channels

A **channel** is a typed pipe between goroutines: `ch <- v` sends, `<-ch` receives. An unbuffered channel (`make(chan int)`) has no storage, so a send and a receive must meet. Whoever arrives first blocks. I printed timestamps (rounded to 100 ms) to see it:

```go
ch := make(chan int)
go func() {
	time.Sleep(300 * time.Millisecond)
	fmt.Println(ts(), "receiver: ready to receive")
	fmt.Println(ts(), "receiver: got", <-ch)
}()
fmt.Println(ts(), "sender: sending")
ch <- 42
fmt.Println(ts(), "sender: send finished")
```

```
   0ms sender: sending
 300ms receiver: ready to receive
 300ms receiver: got 42
 300ms sender: send finished
```

The sender was stuck for 300 ms until the receiver showed up. The order of the last two lines can swap between runs, since both happen right after the hand-off.

## Buffered channels

`make(chan string, 2)` adds room for two values. Sends only block when the buffer is full.

```go
ch := make(chan string, 2)
ch <- "a"
ch <- "b"
select {
case ch <- "c":
	fmt.Println("sent c")
default:
	fmt.Println("a third send would block")
}
```

```
sent a, len 1 cap 2
sent b, len 2 cap 2
a third send would block
a b
```

(The `select` with `default` is just a way to test without blocking; we cover `select` properly next time.)

## Closing, `range` and comma-ok

The sender calls `close(ch)` to say "no more values". A `for v := range ch` loop reads until the channel is closed and drained. Receiving from a closed channel never blocks: it returns the zero value, and the second result tells you whether the value was real.

```go
for v := range ch {
	fmt.Println("got", v)
}
v, ok := <-ch
fmt.Println("after close:", v, ok)
```

```
got 10
got 20
got 30
after close: 0 false
```

Only the sender should close, and only once; sending on a closed channel panics.

## The deadlock

An unbuffered send with nobody to receive:

```go
ch := make(chan int)
ch <- 1
fmt.Println(<-ch)
```

```
fatal error: all goroutines are asleep - deadlock!

goroutine 1 [chan send]:
main.main()
	.../deadlock/main.go:7 +0x38
exit status 2
```

The runtime noticed that no goroutine could ever proceed and gave up. It shows where each goroutine is stuck (`chan send`). Note this detection only works when *every* goroutine is blocked; in a bigger program a stuck goroutine can hide silently.

## A small worker pipeline

Producer, three workers, one collector. Workers read from `jobs` and write to `results`; a helper goroutine closes `results` after all workers finish. Result order depends on scheduling, so I sort before printing.

```go
for w := 0; w < 3; w++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		for n := range jobs {
			results <- result{n, n * n}
		}
	}()
}
go func() { for n := 1; n <= 9; n++ { jobs <- n }; close(jobs) }()
go func() { wg.Wait(); close(results) }()
```

```
1^2 = 1
2^2 = 4
...
9^2 = 81
```

(Lines 3 to 8 omitted; they follow the same pattern.) Ownership is the idea to remember: the producer closes `jobs`, and whoever knows all workers are done closes `results`.

## Loop variables and the race detector

Before Go 1.22, goroutines started in a `for i` loop all shared one `i`, and the classic bug was seeing the final value everywhere. With Go 1.22 or newer (the `go` line in `go.mod` is 1.25 here), each iteration has its own `i`, and my test printed `[0 1 2]`. I did not run the old behaviour.

Now a deliberately broken counter: 1000 goroutines doing `count++` without protection, run with `go run -race`:

```
WARNING: DATA RACE
Read at 0x00c000094048 by goroutine 10:
  main.main.func1()
      .../racy/main.go:15 +0x68

Previous write at 0x00c000094048 by goroutine 7:
  main.main.func1()
      .../racy/main.go:15 +0x78
...
count: 853
Found 2 data race(s)
exit status 66
```

The detector found it, and the final count was wrong (853 here, different on each run; plain runs gave 965 and 970). Guarding the increment with a `sync.Mutex` printed `count: 1000` and a clean `-race` run. The pipeline and the other demos were also clean under `-race`.

## A few things to watch

- Always know how a goroutine ends; otherwise it leaks.
- `wg.Add` before `go`, and `defer wg.Done()` inside.
- Close channels from the sending side, never from the receiver.
- A nil channel blocks forever on send and receive.
- Run tests and demos with `-race` regularly; a correct-looking output proves nothing.

## Exercise

1. Change the worker count to 1 and then 5. Does the sorted output change? Does the unsorted one?
2. Make `jobs` buffered with capacity 9 and remove the producer goroutine (fill it in `main`, then close it). Why does that work?
3. Write a counter that uses a channel instead of a mutex: goroutines send `+1`, and one goroutine owns the total.

## What's next

Next we cover `sync`, `select` and `context` in Go: mutexes, timeouts, cancellation and how to stop goroutines cleanly.
