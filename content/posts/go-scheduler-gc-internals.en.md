+++
date = '2027-03-02T10:00:00+03:30'
draft = false
title = 'The Go scheduler and garbage collector'
description = 'Go scheduler and garbage collector internals: the G-M-P model, schedtrace, preemption, gctrace, GOGC, GOMEMLIMIT and sync.Pool, shown with real runs.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "runtime", "scheduler", "gc", "performance"]
cover = { image = "/images/covers/go-scheduler-gc-internals.png", alt = "The Go scheduler and garbage collector", hiddenInSingle = true }
+++

In the [previous post](/posts/go-docker-ci-deploy/) we shipped our service as a container. Now we look inside the runtime of that process: how goroutines get onto CPUs, and how memory gets cleaned up. It builds on [goroutines and channels](/posts/go-goroutines-channels/), on [profiling with pprof](/posts/go-profiling-pprof/) and on [escape analysis and the heap](/posts/go-pointers-memory/).

> Go 1.26, macOS arm64, 8 CPUs. Load average was about 1.6, but I show **no timings**: only counts and approximate sizes.

## The G-M-P model in plain words

The docs and talks describe three things. A **G** is a goroutine. An **M** is an OS thread. A **P** is a "processor", a token that a thread must hold to run Go code; there are `GOMAXPROCS` of them. Each P has a local run queue of runnable goroutines, there is a global queue too, and an idle P can steal work from others (work stealing).

```go
fmt.Println("NumCPU       =", runtime.NumCPU())
fmt.Println("GOMAXPROCS   =", runtime.GOMAXPROCS(0)) // 0 = query only
fmt.Println("NumGoroutine =", runtime.NumGoroutine())
```

```
NumCPU       = 8
GOMAXPROCS   = 8
NumGoroutine = 1
NumGoroutine = 51 after starting 50
GOMAXPROCS   = 2 (was 8 )
```

## Watching it: schedtrace

`GODEBUG=schedtrace=1000` prints one line per second. My program starts 200 goroutines that each spin on the CPU for a while. Two lines (I cut the `schedticks` tail):

```
SCHED 0ms: gomaxprocs=8 idleprocs=6 threads=3 spinningthreads=1 ... runqueue=0 [ 0 0 0 0 0 0 0 0 ]
SCHED 1010ms: gomaxprocs=8 idleprocs=0 threads=9 spinningthreads=0 ... runqueue=82 [ 12 1 11 14 10 1 0 61 ]
```

`gomaxprocs` is the number of Ps. `idleprocs=0` means every P is busy. `threads=9` is how many Ms exist. `runqueue=82` is the global queue; the bracket lists the local queue of each of the 8 Ps. When the work ended, the trace showed `idleprocs=8`, `threads=9`: threads stay around.

## Threads: blocking syscall versus blocking in Go

Does a blocked goroutine cost a thread? It depends on how it blocks. I start 100 goroutines and count threads created so far with `pprof.Lookup("threadcreate").Count()`.

```go
case "syscall":
	r, _, _ := os.Pipe() // nothing is ever written
	go func() { buf := make([]byte, 1); syscall.Read(int(r.Fd()), buf) }()
case "sleep":
	go time.Sleep(time.Minute)
case "chan":
	c := make(chan int)
	go func() { <-c }()
```

```
syscall  threadcreate before=5 after=103
sleep    threadcreate before=5 after=6
chan     threadcreate before=5 after=5
```

A goroutine stuck in a raw blocking syscall keeps its thread: about 98 more were created. Goroutines waiting on a channel or a timer are parked by the scheduler and cost no thread.

## Preemption

With `GOMAXPROCS(1)` one goroutine runs `for {}` while the main goroutine waits on a 100 ms ticker:

```
tick 1
tick 2
tick 3
tick 4
tick 5
```

The ticker is not starved: since Go 1.14 the runtime uses **asynchronous preemption** to interrupt such a loop. Before that it was only **cooperative**, at function calls, so a call-free loop could block others. I did not run old versions (documented history).

## The garbage collector

According to the docs, Go's GC is a concurrent, non-generational, **tri-color mark-and-sweep** collector. It marks reachable objects while your code keeps running, with only very short stop-the-world phases, then sweeps unreachable memory. `GODEBUG=gctrace=1` prints one line per cycle:

```
gc 3 @0.006s 2%: 0.020+0.25+0.023 ms clock, 0.16+0.054/0.21/0.021+0.18 ms cpu, 15->16->8 MB, 16 MB goal, 0 MB stacks, 0 MB globals, 8 P
```

Field by field: cycle 3, 0.006 s after start, 2% of CPU spent in GC so far; the three clock numbers are the sweep-termination pause, concurrent mark and mark-termination pause; the cpu numbers split the same work by role; `15->16->8 MB` is heap at start, at end and live afterwards; `16 MB goal` is the next target; `8 P` is GOMAXPROCS. I draw no conclusions from the times.

`runtime.ReadMemStats` gives `NumGC` and `HeapAlloc` in code.

## GOGC and GOMEMLIMIT

My workload allocates 200,000 slices of 4 KiB and keeps a rolling window of about 8 MiB alive. Only `GOGC` changes between runs (counts vary between runs, so ranges):

| GOGC | GC cycles | peak HeapAlloc (sampled) |
|---|---|---|
| 50 | ~170-180 | ~16-20 MiB |
| 100 | ~90 | ~20-24 MiB |
| 400 | ~21 | ~48-54 MiB |
| off | 0 | ~777 MiB |

A higher `GOGC` means fewer cycles and more memory; that is the trade. **GOMEMLIMIT** is a soft memory limit: the GC works harder to stay under it. With `GOGC=off GOMEMLIMIT=24MiB` I got about 100 cycles and a peak near 19 MiB, instead of 777 MiB. A limit close to the live heap is dangerous: with `GOMEMLIMIT=12MiB` the same program ran roughly 1100-1800 cycles (about 8 MiB is live). The limit is soft, not a guarantee.

## sync.Pool

A **sync.Pool** reuses temporary objects. Benchmark that renders into a `bytes.Buffer` (`-benchmem`, 20,000 iterations):

```
BenchmarkNoPool-8   20000   1984 B/op   5 allocs/op
BenchmarkPool-8     20000      0 B/op   0 allocs/op
```

Fewer allocations means fewer GC cycles. The runtime may drop pooled items at any GC, so a pool is a cache, not storage.

## A few things to watch

- `NumGoroutine` and the thread count answer different questions; watch both in production.
- Don't tune `GOGC` before profiling; first reduce allocations.
- Avoid `runtime.SetFinalizer`: it runs at an unpredictable time, or never.
- Reset a pooled object before reuse; never use it after `Put`.

## Exercise

1. Run the threads program with 1,000 goroutines in `syscall` mode and compare the count.
2. Run `gcdemo` with `GOGC=200` and place it in the table.

## What's next

This is the last post of the Go Backend series. Next on the calendar: observability in Rust with tracing. A year-end recap of the Go series comes later in March.
