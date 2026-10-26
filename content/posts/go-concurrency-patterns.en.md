+++
date = '2027-01-25T10:00:00+03:30'
draft = false
title = 'Concurrency patterns: worker pool and errgroup'
description = 'Go concurrency patterns: bounded worker pools, errgroup with first-error cancellation, SetLimit, pipelines, goroutine leaks and weighted semaphores.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "concurrency", "errgroup", "worker-pool", "semaphore"]
cover = { image = "/images/covers/go-concurrency-patterns.png", alt = "Concurrency patterns: worker pool and errgroup", hiddenInSingle = true }
+++

The [previous post](/posts/go-transactions-patterns/) was about transactions and the repository pattern. The examples here are plain Go and need no database. Backend code often has many independent pieces of work (HTTP calls, queries, files) that should run concurrently, but not unboundedly, and should stop when one fails. This post builds on [goroutines and channels](/posts/go-goroutines-channels/) and [sync, select and context](/posts/go-sync-select-context/) and shows the patterns I reach for most.

> Everything was run with Go 1.26 on macOS (arm64), `golang.org/x/sync` v0.24.0, load average about 1.4. I show no timings, only counts and ordering.

## A bounded worker pool

A **{{< term "worker-pool" "worker pool" >}}** starts a fixed number of goroutines that read from a jobs channel and write to a results channel. The trick is who closes what: the producer closes `jobs`, and a separate goroutine waits on the `WaitGroup` and closes `results`.

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

With 3 workers and 9 jobs, `go run -race` printed:

```
jobs done: [1 2 3 4 5 6 7 8 9]
workers used: 3 total: 9
```

Results arrive in completion order, so I sorted them; ordering is fixed below.

## errgroup: first error cancels the rest

The pool above is a lot of plumbing. **{{< term "errgroup" "errgroup" >}}** packages the common case: run functions, wait for all, return the first error. `errgroup.WithContext` also gives a context that is cancelled when any function returns an error or when `Wait` returns. Five jobs finish at 40, 80, 120... ms and job 3 fails:

```go
g, ctx := errgroup.WithContext(context.Background())
for i := 1; i <= 5; i++ {
	g.Go(func() error {
		select {
		case <-time.After(time.Duration(i) * 40 * time.Millisecond):
			if i == 3 { return errors.New("job 3: upstream returned 500") }
			return nil
		case <-ctx.Done():
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
job 4 cancelled: job 3: upstream returned 500
job 5 cancelled: job 3: upstream returned 500
Wait returned: job 3: upstream returned 500
```

Jobs 4 and 5 only stop early because they watch `ctx`. Cancellation in Go is cooperative.

## SetLimit: proving the bound

`g.SetLimit(n)` makes `g.Go` block when `n` functions are already running. To prove it, I count in-flight work with an `atomic.Int32` and record the maximum:

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

`Go` blocks the caller, so a submitting loop gets back-pressure for free.

## Fan-out/fan-in and a pipeline with cancellation

The worker pool is fan-out (many workers read one channel) plus fan-in (one results channel). A **pipeline** chains stages with channels. The rule that keeps it leak-free: every send is a `select` against `ctx.Done()`. Here a generator feeds a squaring stage, and the sink cancels after five values:

```go
select {
case out <- n * n:
case <-ctx.Done():
	return ctx.Err()
}
```

```
got 1
got 4
got 9
got 16
got 25
Wait: context canceled | all stages exited: true
```

`Wait` returns `context canceled` because the stages returned `ctx.Err()`. If a deliberate stop should not look like a failure, treat that specific error as success where you call `Wait`.

## The goroutine leak

A classic bug: a call gives up after a timeout, but the goroutine doing the work later blocks forever sending on an unbuffered channel nobody reads. I called this version 300 times and printed `runtime.NumGoroutine()`:

```
start: 1
leaky after 100 calls: 101 goroutines
leaky after 200 calls: 201 goroutines
leaky after 300 calls: 301 goroutines
```

Every call leaked one goroutine. The fixed version makes the channel buffered with capacity 1, so the send never blocks, and passes a timeout context into the work. After 300 more calls: `fixed after 300 calls: 301 goroutines (added 0)`.

## Keeping the input order

Workers finish in any order, but often you want results in input order. Give every input a slot in a pre-sized slice and let each goroutine write only its own index:

```go
out := make([]string, len(inputs))
for i, s := range inputs {
	g.Go(func() error {
		out[i] = strings.ToUpper(s)
		return nil
	})
}
```

Later inputs sleep less, so they finish first, yet the output is `[A B C D E F G H]`. This needs no mutex because the goroutines write to different elements, which are different memory locations, and `Wait` creates a happens-before edge, so reading `out` afterwards is safe. The run was with `-race` and the detector stayed silent. It would not be safe if you `append` from several goroutines or write to a map.

## Weighted limits with semaphore

Sometimes jobs are not equal: one holds 1 MB, another 8 MB. `semaphore.Weighted` limits the total weight. I used a budget of 10 and weights `5 5 3 3 3 2 8 1 1 4`, acquiring before starting each goroutine:

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

The peak never exceeded 10. A request bigger than the whole budget can never succeed: `Acquire` waits until its context ends, while `TryAcquire` returns false at once.

## A few things to watch

- Always give `Go` functions a way out: watch `ctx.Done()` in loops and blocking calls, or cancellation does nothing.
- Closing channels is the sender's job; with several senders, close from a goroutine that waits for all of them.
- A `SetLimit` of `n` bounds goroutines, not the downstream resource. Size the limit against the database pool or the API quota.
- Do not call `SetLimit` while goroutines are running, and remember `errgroup` keeps only the first error.
- Run `go test -race` on every concurrent code path.

## Exercise

Write a function `MapOrdered(ctx, inputs, n, fn)` that applies `fn` to every input with at most `n` goroutines, returns results in input order, and stops on the first error. Test it with `-race`.

## What's next

Concurrency gets harder when work crosses the database and a message broker. The next post is the outbox pattern with Postgres and NATS in Go.
