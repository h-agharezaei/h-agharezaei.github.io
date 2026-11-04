+++
date = '2027-03-02T10:00:00+03:30'
draft = false
title = 'The Go scheduler and garbage collector'
description = 'Go scheduler and garbage collector internals: the G-M-P model, schedtrace, preemption, gctrace, GOGC, GOMEMLIMIT and sync.Pool, shown with real runs.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "runtime", "scheduler", "gc", "performance"]
cover = { image = "/images/covers/go-scheduler-gc-internals.png", alt = "The Go scheduler and garbage collector", hiddenInSingle = true }
+++

Start 100 goroutines that all wait on a channel, and the program does not get a single new thread. Start 100 goroutines that all wait inside a raw blocking system call, and the program creates about 98 new threads. Put a goroutine in an empty `for {}` loop, and the rest of the program keeps running anyway. Fill the heap with garbage, and a collector cleans it up while your code is still serving requests.

None of these is magic. They are what the Go runtime does behind `go f()` and `make([]byte, n)`, and knowing the outline helps when a service shows odd thread counts, memory that grows in steps, or a latency spike that no handler explains. This post looks at the two parts of the runtime that matter most: the **scheduler**, which decides which goroutine runs where, and the **garbage collector** (GC), which frees memory nobody uses.

The method is small experiments. Each one is a tiny program that prints something you can check, and I say what it proves and what it does not. The post builds on [goroutines and channels](/posts/go-goroutines-channels/), [profiling with pprof](/posts/go-profiling-pprof/) and [escape analysis and the heap](/posts/go-pointers-memory/), and it follows [Docker, CI and deploying a Go service](/posts/go-docker-ci-deploy/): the service we shipped runs on this runtime.

> Go 1.27, macOS arm64, 8 CPUs. The load average was between 2 and 3.5 during my runs, so I show **no timings**, only counts and approximate sizes. Counts such as the number of GC cycles can vary a little from run to run, so I give ranges. Where I describe how the runtime works beyond what a program prints, I say it is from the documentation and I did not verify it myself. The code is a local example, not a published repo.

## The G-M-P model in plain words

The documentation and conference talks describe the scheduler with three letters:

- A **G** is a goroutine: a function that runs concurrently, with its own small stack.
- An **M** is a "machine": an operating-system thread.
- A **P** is a "processor": a token that a thread must hold to run Go code. There are exactly `GOMAXPROCS` of them, by default one per CPU.

Each P has a **local run queue**: the goroutines that are ready to run and are waiting for their turn on that P. There is also one **global queue**. A P that runs out of work looks in the global queue and then steals half of another P's queue, so the work spreads out by itself. This is called work stealing. As a picture:

```
global queue:  G  G  G  G  ...

   P0            P1            P2      ...    (GOMAXPROCS of them)
   local: G G    local: G      local: -
     |             |             |
     M0            M1            M2           (threads, one per busy P)
   running G     running G     running G
```

A goroutine runs only when an M holds a P and picks it. Why so many layers? A goroutine is cheap because it is only a G, a few kilobytes of stack and some bookkeeping. Threads are expensive, so the runtime keeps their number close to the number of CPUs and moves goroutines onto them.

First, some numbers about the machine, from `go run ./info`:

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

The machine has 8 CPUs, and the runtime made 8 Ps. At the start there is 1 goroutine (`main`). After starting 50 sleeping goroutines there are 51. The last line changes `GOMAXPROCS` to 2 and shows that the call returns the previous value, 8.

## Watching the scheduler: schedtrace

The runtime can print its own state. `GODEBUG=schedtrace=1000` prints one line per second. The program in `sched/` starts 200 goroutines, and each of them spins on the CPU for 2.5 seconds, so there is far more work than Ps. Here are two lines (I cut the `schedticks` part at the end of each):

```
SCHED 0ms: gomaxprocs=8 idleprocs=6 threads=3 spinningthreads=1 ... runqueue=0 [ 0 0 0 0 0 0 0 0 ]
SCHED 1011ms: gomaxprocs=8 idleprocs=0 threads=9 spinningthreads=0 ... runqueue=84 [ 8 9 6 6 32 7 8 32 ]
```

How to read them:

- `gomaxprocs=8` is the number of Ps.
- `idleprocs` is how many Ps have nothing to do. At 0 ms it is 6, because the program has just started. At 1011 ms it is 0: every P is busy.
- `threads=9` is how many Ms (threads) exist. Eight busy Ps need eight threads; I did not look into what the ninth one does.
- `runqueue=84` is the **global** queue. The numbers in brackets are the **local** queues of the 8 Ps.

You can check the second line with simple arithmetic. The 200 goroutines are all still alive at that moment: 8 are running (one per P), 8+9+6+6+32+7+8+32 = 108 wait in local queues, and 84 wait in the global queue. 8 + 108 + 84 = 200. Nothing is lost.

When the work ended (the last trace line), the output showed `idleprocs=8` and `threads=9`: all Ps idle, but the threads were still there: idle threads are not destroyed at once. The exact numbers in the brackets change from run to run; the total does not.

## Threads: blocking in a syscall or blocking in Go

Does a blocked goroutine cost a thread? It depends on *how* it is blocked. The experiment starts 100 goroutines in one of three ways and then counts the threads the process has created so far, using `pprof.Lookup("threadcreate").Count()`:

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

In `syscall` mode every goroutine calls the raw {{< term "syscall" "system call" >}} `read` on a pipe that nobody writes to, so it blocks inside the operating system. In `sleep` mode it sleeps on a Go timer, and in `chan` mode it waits for a value on a channel nobody sends to. The three runs printed:

```
syscall  threadcreate before=5 after=103
sleep    threadcreate before=5 after=5
chan     threadcreate before=5 after=5
```

In `syscall` mode the process created about 98 new threads, one for each stuck goroutine. In the other two modes it created none (in the original run of this post, `sleep` showed 6, so a difference of one between runs is noise).

The reason, according to the scheduler's documented design: a thread that is blocked inside a system call cannot run Go code, so the runtime hands its P to another thread (creating one if necessary) so the other goroutines keep running. A goroutine that waits on a channel or a timer is different. It is simply parked by the scheduler, with no thread involved, and it costs no thread. One caveat about this experiment: I called the raw system call on the file descriptor myself, which bypasses the runtime's own I/O handling. Ordinary file and network reads in Go are normally handled differently; I did not test that here.

The takeaway: thousands of goroutines waiting on channels, timers or the network are cheap. Thousands of goroutines inside blocking system calls (or cgo calls, as in [Calling Rust from Go over FFI](/posts/go-calls-rust-ffi/)) can cost thousands of threads.

## Preemption: why a busy loop does not freeze everything

Here is a worry: what if one goroutine never gives up its P? The experiment sets `GOMAXPROCS(1)`, so there is only one P. One goroutine runs `for {}`, a loop with no function calls and no channel operations. The main goroutine waits on a 100 ms ticker and prints a line for each tick:

```
tick 1
tick 2
tick 3
tick 4
tick 5
```

All five ticks arrived. The busy loop did not starve main, even with one P. The reason is **{{< term "preemption" "asynchronous preemption" >}}**: the runtime can interrupt a running goroutine from outside, with a signal, and give the P to another one. According to the Go release notes this exists since Go 1.14. Before that, preemption was only **cooperative**: a goroutine could be switched only at certain points, such as function calls, so a loop without any could block everything else. I did not run old Go versions, so that part is documented history and not something I measured.

## The garbage collector

In Go you allocate memory with `make`, `new` or by taking the address of something, and you never free it. The {{< term "garbage-collector" "garbage collector" >}} finds objects that nothing can reach any more and reclaims them. According to the Go documentation, Go's collector is **concurrent** (it works while your code runs), **non-generational** (it does not treat young objects differently), and uses a **tri-color mark-and-sweep** algorithm: it *marks* every object reachable from the roots (global variables, stacks), and then *sweeps* the unmarked ones away. Only short phases, called {{< term "stop-the-world" "stop-the-world" >}} phases, stop all goroutines.

`GODEBUG=gctrace=1` prints one line per GC cycle. This is the third one from `gcdemo`:

```
gc 3 @0.003s 2%: 0.006+0.091+0.011 ms clock, 0.049+0.011/0.071/0.011+0.094 ms cpu, 15->16->8 MB, 16 MB goal, 0 MB stacks, 0 MB globals, 8 P
```

Field by field, following the runtime documentation for `GODEBUG`:

- `gc 3 @0.003s 2%`: this is cycle number 3, it started 0.003 s after the program started, and about 2% of the time so far has gone to GC.
- `0.006+0.091+0.011 ms clock`: three phases in wall-clock time. First a stop-the-world pause at the start (sweep termination), then the concurrent mark (your code runs during this), then a stop-the-world pause at the end (mark termination). The pauses are the first and third numbers.
- `0.049+0.011/0.071/0.011+0.094 ms cpu`: the same work counted in CPU time and split by role, summed over all CPUs.
- `15->16->8 MB`: the heap size when the cycle started, when it ended, and how much was still live (reachable) afterwards. Here the heap was 15 MB when the cycle began, 16 MB at its end, and only 8 MB turned out to be alive.
- `16 MB goal`: the heap size at which the next cycle is planned to start.
- `8 P`: `GOMAXPROCS`.

I draw no conclusions from the times, since the machine was busy. If you need the same numbers inside your program, `runtime.ReadMemStats` gives `NumGC` and `HeapAlloc` (the experiments below use both).

## GOGC and GOMEMLIMIT: trading memory for GC work

Why was the goal 16 MB when 8 MB were live? The main setting is **GOGC**, which defaults to 100. According to the GC guide, the next cycle starts when the heap reaches about the live heap plus `GOGC` percent of it. With 8 MB live and `GOGC=100`, that is about 8 + 8 = 16 MB, which is exactly the goal in the line above. So a higher `GOGC` means fewer cycles and a bigger heap, and a lower one means the opposite.

To test it, `gcdemo` allocates 200,000 slices of 4 KiB each (about 780 MiB in total) but keeps only a rolling window of 2,000 of them alive, about 8 MiB. Only `GOGC` changes between runs. The counts differ slightly between runs, so these are ranges over three runs each:

| GOGC | GC cycles | peak HeapAlloc (sampled) |
|---|---|---|
| 50 | 185-187 | ~14-15 MiB |
| 100 | ~90-92 | ~18-19 MiB |
| 200 | ~44-45 | ~29-30 MiB |
| 400 | ~22 | ~46-50 MiB |
| off | 0 | ~777 MiB |

The peak is a sampled value (the program reads it once every 1,000 allocations), so it is approximate. The pattern matches the formula: doubling `GOGC` roughly halves the cycles, and the peak follows 8 MiB × (1 + GOGC/100) plus some slack. With the collector turned off (`GOGC=off`), nothing is freed and the peak is every byte ever allocated, about 777 MiB.

**GOMEMLIMIT** is a different knob: a soft memory limit. The GC works harder when the total memory approaches it. With `GOGC=off GOMEMLIMIT=24MiB`, the program ran about 108-111 cycles with a peak near 17-18 MiB, instead of 777 MiB. That is how you can run with a memory ceiling in a container.

A limit that is too close to the live heap is dangerous. With `GOMEMLIMIT=12MiB`, where about 8 MiB is always live, the same program ran 1,369 and 1,556 cycles: the collector was running almost constantly. The limit is **soft**: the runtime cannot go below what is live, and it does not guarantee that you stay under the limit.

## sync.Pool: allocating less in the first place

The cheapest garbage is the garbage you never create. A **sync.Pool** keeps temporary objects for reuse. The benchmark renders a small text into a `bytes.Buffer`, once with a fresh buffer each time and once with a pooled one (`-benchmem`, 20,000 iterations):

```
BenchmarkNoPool-8   20000   1984 B/op   5 allocs/op
BenchmarkPool-8     20000      0 B/op   0 allocs/op
```

Without the pool, each iteration allocates about 2 KB in 5 allocations. With it, none (after warm-up). Fewer allocations mean fewer GC cycles. But a pool is a cache, not storage: the runtime may drop pooled items at any GC, so never rely on an item still being there.

## Runtime tuning traps

- **`NumGoroutine` and the thread count answer different questions.** One counts Gs, the other Ms. Watch both in production: many goroutines is normal, but a thread count that keeps growing points to blocking system calls.
- **Do not tune `GOGC` first.** Profile first (see [profiling with pprof](/posts/go-profiling-pprof/)) and reduce allocations; tuning only moves the trade-off.
- **Avoid `runtime.SetFinalizer`.** Finalizers run at an unpredictable time, or never.
- **Reset pooled objects before reuse, and never touch one after `Put`.** Another goroutine may already have it.
- **Do not trust one trace line.** `schedtrace` and `gctrace` are debugging output; their format may change between Go versions.

## Exercise

1. Run the threads program with 1,000 goroutines in `syscall` mode and compare the thread count. Does it grow in proportion?
2. Predict the number of GC cycles for `GOGC=800` from the formula, then run `gcdemo` with it and compare.

## What's next

This is the last post of the Go Backend series. Next on the calendar is "Observability in Rust with tracing", which goes from runtime internals to traces and logs. A recap of the Go series follows later in March.
