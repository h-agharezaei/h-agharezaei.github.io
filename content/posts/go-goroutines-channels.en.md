+++
date = '2026-11-22T10:00:00+03:30'
draft = false
title = 'Goroutines and channels in Go'
description = 'Go goroutines and channels: WaitGroup, buffered and unbuffered channels, deadlocks, a worker pipeline and the race detector, with real program output.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Fundamentals"]
tags = ["go", "beginner", "concurrency", "goroutines", "channels"]
cover = { image = "/images/covers/go-goroutines-channels.png", alt = "Goroutines and channels in Go", hiddenInSingle = true }
+++

Picture a thousand {{< term "goroutine" "goroutines" >}}, each adding one to a counter. You expect 1000. But the program sometimes prints 965, sometimes 970, sometimes another number, and it never prints an error. Output that looks right proves nothing in a concurrent program. That is what this post is about: why this happens and which tools Go gives you to fix it.

Concurrency is the feature Go is most known for. After [Packages and modules: structuring a Go project](/posts/go-packages-modules/), we start with the simplest thing, launching a goroutine, and go step by step to `sync.WaitGroup`, to the core problem (two goroutines touching one variable), to {{< term "channel" "channels" >}}, to deadlocks and a small pipeline. At the end we meet the race detector, which finds these bugs for you.

> Everything below was run with Go 1.26 on macOS (arm64). Outputs that depend on scheduling are marked as such. I shortened file paths in the outputs.

## Concurrency is not parallelism

Let me separate two words first. **Concurrency** means splitting a program into independent tasks that make progress in overlapping periods of time. Think of one cook who stirs the soup and keeps an eye on the rice: one person, several things moving at once. **Parallelism** means tasks really running at the same instant on several CPU cores, like two cooks working side by side.

Go gives you the first. It makes tasks cheap, and the runtime spreads them over cores where it can. We write concurrent code, and the scheduler decides how much of it runs in parallel.

## `go f()` and `main` exiting

If you put the word `go` before a function call, that function starts as a **goroutine**: a lightweight task managed by the runtime. The call itself returns immediately, and your program carries on without waiting.

In this program a goroutine prints something after 100 milliseconds, while `main` immediately writes its own message:

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

The goroutine's message was never printed. When `main` returns, the whole program ends, and the other goroutines, finished or not, are killed on the spot. So we need a way for `main` to wait.

## `sync.WaitGroup`

The simplest way is a **WaitGroup**. It is a counter with three operations: `Add` raises it before each task starts, `Done` lowers it when a task finishes, and `Wait` blocks (stands still right there) until the counter is zero.

The program below starts three workers that each sleep for a time proportional to their number and then report. `main` waits for all three with `wg.Wait()`:

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

This time `all done` was printed after all three workers. The `Sleep`s also fixed the order: worker 1 sleeps least and finishes first. Without them, the order of the first three lines would change from run to run. One more important point: call `Add` in the goroutine that starts the work (before `go`), not inside the new goroutine. Otherwise `Wait` might run before `Add` and conclude there is nothing left to wait for.

## The core problem: two goroutines, one variable

Now back to the counter from the start. `count++` is not one operation. It has three steps: read the value, add one, write it back. Suppose two goroutines run at the same time. Both read `count` and see 5. Both compute 6. Both write 6. We incremented twice but the counter went up by one. This is called a **data race**: two goroutines touch the same variable at the same time, at least one of them writing, with no coordination. The result is a {{< term "race-condition" "race condition" >}}: the answer depends on timing.

This program starts 1000 goroutines that each do `count++` once, and waits for them all:

```go
var wg sync.WaitGroup
count := 0
for i := 0; i < 1000; i++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		count++
	}()
}
wg.Wait()
fmt.Println("count:", count)
```

In a normal run the output differs every time. In my runs I saw numbers like 965 and 970, and when I ran it again while writing this text I got `count: 956`. It never guarantees 1000, and it never complains. Fortunately Go has a tool that finds this kind of bug: the **race detector**. Just add `-race` to the command (`go run -race`):

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

The report says one goroutine reads from address `0x00c000094048` (Read) while another goroutine had written to the same address before (Previous write), and both were on line 15 of the program, which is the `count++`. (Goroutine numbers and the final count, 853 here, change from run to run, and `...` marks parts of the report I left out.) The program exited with code 66, and the final count was wrong.

The first fix is to let only one goroutine at a time touch the variable. The tool for that is a {{< term "mutex" "mutex" >}}, which we cover properly in the next post. Here I only show how it is used: take the lock before `count++` and release it after.

```go
mu.Lock()
count++
mu.Unlock()
```

With this lock the output was `count: 1000`, and the `-race` run printed no warning.

But Go has another way, summed up in a slogan: instead of sharing memory between goroutines and protecting it with locks, **send values to each other**. The tool for that is the channel.

## Unbuffered channels

A **channel** is a typed pipe between goroutines: `ch <- v` puts a value into the pipe and `<-ch` takes it out. Because only one side owns the value at any moment, no data race happens. (According to the Go memory model, a send on a channel is synchronized before the completion of the matching receive, which means whatever the sender wrote before sending is visible to the receiver after receiving.)

An unbuffered channel (`make(chan int)`) has no room to hold a value. So the send and the receive must meet: whoever arrives first blocks and waits for the other. To see that, the program below prints the time of each line (rounded to 100 ms). The receiver sleeps 300 ms before it is ready to receive, but the sender starts sending right away:

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

The sender started sending at time zero, but `ch <- 42` did not complete. It was stuck for 300 ms until the receiver woke up and was ready to receive. Only then did the send complete and the sender print its last line. The order of the last two lines may swap between runs, because both happen right after the handoff.

## Buffered channels

Sometimes you do not want the sender to wait for every value. `make(chan string, 2)` adds room for two values (this is called the buffer). A send blocks only when the buffer is full. The program below sends two values and then tries a third. For the try, instead of actually blocking, I used a `select` with `default`: if the send cannot happen, the `default` branch runs. (We cover `select` properly in the next post.) `len` gives the number of values in the buffer and `cap` its capacity:

```go
ch := make(chan string, 2)
ch <- "a"
fmt.Println("sent a, len", len(ch), "cap", cap(ch))
ch <- "b"
fmt.Println("sent b, len", len(ch), "cap", cap(ch))
select {
case ch <- "c":
	fmt.Println("sent c")
default:
	fmt.Println("a third send would block")
}
fmt.Println(<-ch, <-ch)
```

```
sent a, len 1 cap 2
sent b, len 2 cap 2
a third send would block
a b
```

The first two sends did not block, and `len` reached 2, equal to `cap`. So a third send would have blocked, and `default` ran. At the end the two values came out in the order they went in, `a` then `b`: a channel is a queue.

## Closing, `range` and comma-ok

How does a receiver know no more values are coming? The sender closes the channel with `close(ch)`. The loop `for v := range ch` reads values until the channel is closed and empty, and then ends. Receiving from a closed channel never blocks: it returns the zero value of the type, and the second value (`ok`) says whether the value was real.

In this program a goroutine sends three numbers and closes the channel, and `main` reads them all and then reads once more from the closed channel:

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

Three values were read and `range` ended. Reading again from the closed channel returned `0` (the zero value of `int`) and `false`: "this is not a real value, the channel is closed". The important rule: only the sender should close, and only once. Sending on a closed channel panics.

## Deadlock

Now the worst case: sending on an unbuffered channel when nobody can receive. The program below both sends and wants to receive in the main goroutine, but the send never finishes, so we never reach the receive:

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

The runtime noticed that no goroutine could make progress and stopped the program. That is useful: the report shows where each goroutine is stuck (`chan send` means waiting to send). But this detection only works when *all* goroutines are blocked. In a bigger program, one stuck goroutine can hide silently, because the others are still alive.

## A simple pipeline with workers

Now let's put all the tools together. A **producer** puts the numbers 1 to 9 into a `jobs` channel. Three **workers** read from `jobs`, compute the square of each number and put the result into `results`. This pattern is called a {{< term "worker-pool" "worker pool" >}}. A helper goroutine closes `results` after all workers finish (using `wg.Wait`), so the reading loop knows the work is done. Finally `main` collects all the results.

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
go func() { // producer
	for n := 1; n <= 9; n++ {
		jobs <- n
	}
	close(jobs)
}()

go func() { // close results once all workers finish
	wg.Wait()
	close(results)
}()
```

```
1^2 = 1
2^2 = 4
...
9^2 = 81
```

(Lines 3 to 8 are left out; they follow the same pattern.) The order in which results arrive depends on scheduling, so I sorted them before printing. The point to remember is **ownership**: the producer owns `jobs` and closes it, and whoever knows all workers are finished (the helper goroutine with `wg.Wait`) closes `results`. This program also ran clean under `-race`.

## The loop variable

One more small but important case. Before Go 1.22, goroutines started inside a `for i` loop all shared one `i`, and the classic bug was that every one of them saw the last value. From Go 1.22 on (the `go` line in this `go.mod` is 1.25), each iteration has its own `i`. A small program that puts `i` into a slice in each iteration (with a mutex, then sorted) printed `[0 1 2]`. I did not run the old behavior.

## Leaks, deadlocks and races

- **Always know how a goroutine ends.** Otherwise it leaks: it holds memory for the life of the program and never goes away.
- **`wg.Add` before `go`, and `defer wg.Done()` inside the goroutine.** This order makes sure `Wait` misses nothing, and `Done` is called however the function exits (even with an early `return`).
- **Close a channel from the sender's side, not the receiver's.** If the receiver closes it, the sender may send on a closed channel and panic.
- **Sending or receiving on a nil channel blocks forever.** If you never gave the channel a value, know that you will get stuck.
- **Run tests and demos with `-race` regularly.** Output that looks right proves nothing, as the 956 counter showed.

## Exercise

1. Change the number of workers to one, then five. Does the sorted output change? And the unsorted output?
2. Make `jobs` buffered with capacity 9 and remove the producer goroutine (fill it in `main` and close it). Why does it work?
3. Write a counter that uses a channel instead of a mutex: goroutines send `+1`, and one goroutine owns the total.

## What's next

"sync, select and context in Go". We only glanced at mutexes and `select` here. That post, with timeouts and cancellation, shows how to stop goroutines cleanly.
