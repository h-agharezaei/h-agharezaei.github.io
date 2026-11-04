+++
date = '2027-01-25T10:00:00+03:30'
draft = false
title = 'Concurrency patterns: worker pool and errgroup'
description = 'Go concurrency patterns: bounded worker pools, errgroup with first-error cancellation, SetLimit, pipelines, goroutine leaks and weighted semaphores.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "concurrency", "errgroup", "worker-pool", "semaphore"]
cover = { image = "/images/covers/go-concurrency-patterns.png", alt = "Concurrency patterns: worker pool and errgroup", hiddenInSingle = true }
+++

Picture a handler that calls a slow service. To be safe it gives up after 10 ms and answers the user without that result. The caller moves on, and everything looks fine. But the goroutine that was doing the call is still alive, and when it finally finishes, it tries to hand over its result and nobody is listening. It waits forever. Call this handler 300 times and you have 300 goroutines that will never finish. Nothing crashes, so you only notice later, when memory has been growing for days.

That is the first problem of this post. The second is the opposite one: a loop that starts one goroutine for every item. With 10,000 items you get 10,000 calls to the database or to some API at once, and the database connection pool or the API quota, unlike goroutines, is not cheap. The third is a group of goroutines where one fails, and the others carry on working for a result nobody wants.

All three have the same cure: **run work concurrently, but bounded, and make it stop when it is no longer needed.** Go has a few small, well-known patterns for this: the worker pool, `errgroup`, a pipeline with cancellation and a weighted semaphore. This post builds each one in a small program and shows what it prints. The examples are plain Go with no database, and they build on [goroutines and channels](/posts/go-goroutines-channels/) and [sync, select and context](/posts/go-sync-select-context/). Since the previous post, [transactions and the repository pattern](/posts/go-transactions-patterns/), was about concurrency between database clients, this one is about concurrency inside the Go process itself.

> Everything was re-run with Go 1.27 on macOS (arm64), with the race detector (`go run -race`) and `golang.org/x/sync` v0.24.0. I show no timings, only counts and ordering. When several goroutines run at once, the order of some lines can change from run to run; I say so where it matters. The code is a local example, not a published repo.

## Words we need

Four things from the earlier posts, in one sentence each, so that the rest reads smoothly:

- A **{{< term "goroutine" "goroutine" >}}** is a function running concurrently with the rest of the program. `go f()` starts one.
- A **{{< term "channel" "channel" >}}** is a pipe between goroutines. A send on an unbuffered channel waits until another goroutine receives, and a receive waits until someone sends. A buffered channel can hold a few values, so a send only waits when the buffer is full.
- A `sync.WaitGroup` is a counter used to wait until a group of goroutines has finished.
- A **{{< term "context" "context" >}}** carries a "stop now" signal. Code that is willing to stop watches `ctx.Done()`, a channel that is closed when the context is cancelled or its deadline passes. Cancellation in Go is cooperative: nothing is killed, the code has to look.

## The goroutine leak: the broken version first

Here is the handler from the introduction. `slow` is a simulated call that takes 30 ms. `leaky` starts it in a goroutine, and waits for the result for at most 10 ms:

```go
func leaky() (int, bool) {
	ch := make(chan int)
	go func() { ch <- slow(context.Background()) }()
	select {
	case v := <-ch:
		return v, true
	case <-time.After(10 * time.Millisecond):
		return 0, false
	}
}
```

The 10 ms timer always wins. `leaky` returns `false`, and nobody ever reads from `ch`. About twenty milliseconds later the goroutine finishes `slow` and runs `ch <- 42`. The channel is unbuffered, so the send waits for a receiver that will never come. The goroutine is stuck for the rest of the program's life. This is a {{< term "goroutine-leak" "goroutine leak" >}}.

I called `leaky` 300 times and printed `runtime.NumGoroutine()` after every hundred calls:

```
start: 1
leaky after 100 calls: 101 goroutines
leaky after 200 calls: 201 goroutines
leaky after 300 calls: 301 goroutines
```

The program starts with one goroutine (`main`). After 100 calls there are 101, then 201, then 301. Every call leaked exactly one.

The fix has two parts, and both are small:

```go
func fixed() (int, bool) {
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	ch := make(chan int, 1)
	go func() { ch <- slow(ctx) }()
	select {
	case v := <-ch:
		return v, true
	case <-ctx.Done():
		return 0, false
	}
}
```

First, the channel has a buffer of 1, so the goroutine's send always succeeds, even if nobody reads. Second, the work receives a context with the same timeout, so `slow` stops early instead of finishing a result nobody wants. I then ran `fixed` 300 times on top of the leaked ones:

```
fixed after 300 calls: 301 goroutines (added 0)
```

The 301 is the old leaked goroutines (and `main`); the important part is "added 0". The rule to take away: **every goroutine you start needs a guaranteed way to finish.** Ask yourself, for each one, "what makes this goroutine return?"

## A bounded worker pool

Now the second problem: many jobs, limited capacity. A **{{< term "worker-pool" "worker pool" >}}** starts a fixed number of goroutines, the workers. They all read jobs from one channel, so the jobs are shared among them. Each worker writes its results to a second channel. Sharing the jobs out is called fan-out, and gathering the results into one channel is fan-in ({{< term "fan-out-fan-in" "fan-out and fan-in" >}}).

The tricky part is who closes which channel. The producer closes `jobs` when it has no more work, which ends the workers' `range` loops. A separate goroutine waits for all the workers through the `WaitGroup`, and only then closes `results`, so the reader's `range` over `results` also ends:

```go
for w := 1; w <= workers; w++ {
	wg.Add(1)
	go func() {
		defer wg.Done()
		for j := range jobs {
			fetch(j) // simulated I/O
			results <- result{job: j, worker: w}
		}
	}()
}
go func() { for j := 1; j <= 9; j++ { jobs <- j }; close(jobs) }()
go func() { wg.Wait(); close(results) }()
```

(Since Go 1.22 each loop iteration has its own `w`, so every goroutine sees its own worker number.) With 3 workers and 9 jobs, `go run -race` printed:

```
jobs done: [1 2 3 4 5 6 7 8 9]
workers used: 3 total: 9
```

All nine jobs finished, and all three workers took part. Results come back in the order jobs complete, which changes from run to run, so the program sorts them before printing. Below we see how to keep the input order instead.

## errgroup: the first error stops the rest

The pool above is a lot of plumbing: two channels, a `WaitGroup`, and the closing rules. Most of the time we want something simpler: run these functions, wait for all of them, and tell me the first error. That is what **{{< term "errgroup" "errgroup" >}}** (from `golang.org/x/sync`) does. `errgroup.WithContext` also returns a context that is cancelled as soon as any function returns an error (or when `Wait` returns), so the other functions can notice and stop.

To see it, five jobs would finish at 40, 80, 120, 160 and 200 ms, and job 3 fails when its turn comes. The jobs wait with a `select`: either their time is up, or the context is cancelled. The demo also records a line for each event in a mutex-protected slice and prints them at the end, so that output from different goroutines does not mix:

```go
g, ctx := errgroup.WithContext(context.Background())
for i := 1; i <= 5; i++ {
	g.Go(func() error {
		d := time.Duration(i) * 40 * time.Millisecond
		select {
		case <-time.After(d):
			if i == 3 {
				note("job 3 failed")
				return errors.New("job 3: upstream returned 500")
			}
			note(fmt.Sprintf("job %d finished", i))
			return nil
		case <-ctx.Done():
			note(fmt.Sprintf("job %d cancelled: %v", i, context.Cause(ctx)))
			return ctx.Err()
		}
	})
}
err := g.Wait()
```

```
job 1 finished
job 2 finished
job 3 failed
job 5 cancelled: job 3: upstream returned 500
job 4 cancelled: job 3: upstream returned 500
Wait returned: job 3: upstream returned 500
```

Jobs 1 and 2 finished before the failure. Job 3 failed at 120 ms. That cancelled the context, and jobs 4 and 5, which were still waiting, saw `ctx.Done()` and stopped. (The order of the two "cancelled" lines can swap between runs, because they happen at almost the same moment.) `context.Cause(ctx)` returns the error that caused the cancellation, which is why their messages carry job 3's error; `ctx.Err()` alone would only say "context canceled". Finally `Wait` returns the first error. Jobs 4 and 5 stopped early only because they watch `ctx`: nothing forced them to. Again, cancellation is cooperative.

## SetLimit: proving the bound

`errgroup` can also be the pool. `g.SetLimit(n)` makes `g.Go` block when `n` functions are already running, until one finishes. Instead of trusting this, the demo counts how many functions are running at the same moment with an `atomic.Int32`, and remembers the maximum. The 40 jobs each sleep 20 ms:

```go
g.SetLimit(4)
for i := 0; i < 40; i++ {
	g.Go(func() error {
		n := inflight.Add(1)
		// update max with a CompareAndSwap loop
		time.Sleep(20 * time.Millisecond)
		inflight.Add(-1)
		return nil
	})
}
```

```
jobs: 40, limit: 4, max in flight: 4
```

Forty jobs were submitted, and at no moment were more than four running. Notice that `g.Go` blocks the submitting loop, so the loop itself slows down to match the workers. A producer that is slowed down by a slow consumer is called **backpressure**, and here you get it for free.

## A pipeline with cancellation

A **pipeline** is a chain of stages connected by channels: one stage produces values, the next transforms them, the last consumes them. It is the same fan-in/fan-out idea, arranged in a line. The danger is the same as in the leak at the start: if the last stage stops reading, the earlier stages are stuck on their sends. The rule that prevents it is that **every send is a `select` against `ctx.Done()`**:

```go
select {
case out <- n * n:
case <-ctx.Done():
	return ctx.Err()
}
```

In the demo a generator produces 1, 2, 3, ... forever, a second stage squares them, and the sink (the last stage) cancels the context after receiving five values:

```
got 1
got 4
got 9
got 16
got 25
Wait: context canceled | all stages exited: true
```

The sink printed five squares and cancelled. The two earlier stages, which would have run forever, saw `ctx.Done()` and returned, so `Wait` came back. `all stages exited: true` is the check that `Wait` returned within a second, not hanging. `Wait` returns `context canceled` because the stages returned `ctx.Err()`. If a deliberate stop should not look like a failure to the caller, treat that one error as success where you call `Wait`.

## Keeping the input order

Workers finish in any order, yet often you want the results in the order of the inputs. The simple trick: make a slice with one slot per input before starting, and let each goroutine write only its own slot:

```go
out := make([]string, len(inputs))
for i, s := range inputs {
	g.Go(func() error {
		out[i] = strings.ToUpper(s)
		return nil
	})
}
```

In the demo, later inputs sleep less so they finish first, but the output is `[A B C D E F G H]`, in input order. No mutex is needed, because the goroutines write to different elements, which are different memory locations, and `Wait` makes everything they wrote visible to the code that reads the slice afterwards. I ran it with `-race` and the detector stayed silent. It would not be safe to `append` to a shared slice from several goroutines, or to write to a shared map.

## Weighted limits with a semaphore

`SetLimit` counts jobs, treating them as equal. Sometimes they are not: one job holds 1 MB in memory and another 8 MB. A **{{< term "semaphore" "semaphore" >}}** is a counter of "permits" that goroutines must take before working and give back afterwards, and `semaphore.Weighted` lets a job take several permits at once. Here I used a budget of 10 and these weights: `5 5 3 3 3 2 8 1 1 4`. The loop acquires the weight before starting each goroutine, and the goroutine releases it when it ends:

```go
sem := semaphore.NewWeighted(10)
if err := sem.Acquire(ctx, w); err != nil { return err }
g.Go(func() error { defer sem.Release(w); /* work */ return nil })
```

```
budget: 10 peak weight in use: 10
Acquire(11): context deadline exceeded
TryAcquire(11): false
```

The program tracked the total weight in use at each moment, and its peak was exactly 10, never more. The last two lines show what happens with a request heavier than the whole budget: it can never succeed. `Acquire(11)` waits until its context ends (here a 50 ms timeout), and `TryAcquire(11)` does not wait and returns `false` at once.

## Common mistakes in concurrent code

- **A goroutine without a way out.** If the code in a goroutine never looks at `ctx.Done()` in its loops and blocking calls, cancellation changes nothing.
- **Closing channels from the wrong place.** Closing is the sender's job. With several senders, close from one goroutine that first waits for all of them, as the `WaitGroup` goroutine did above.
- **A limit on goroutines is not a limit on the resource.** `SetLimit(n)` bounds goroutines, not what they use downstream. Size the limit against the database pool or the API quota.
- **Surprises in `errgroup`.** Do not call `SetLimit` while goroutines are running (the docs say it must not be modified while any are active), and remember that `errgroup` keeps only the first error.
- **Not running the race detector.** Run `go test -race` on every path that is concurrent.

## Exercise

Write a function `MapOrdered(ctx, inputs, n, fn)` that applies `fn` to every input with at most `n` goroutines, returns the results in input order, and stops on the first error. Test it with `-race`.

## What's next

The next post is "The outbox pattern with Postgres and NATS in Go". It needs a background loop that keeps a database and a message broker in step, and the goroutine discipline from this post is what keeps that loop from leaking or hanging.
