+++
date = '2027-02-20T10:00:00+03:30'
draft = false
title = 'Profiling Go with pprof'
description = 'Find a Go hot spot with pprof: CPU, heap and goroutine profiles on a live service, a fix verified with benchstat and allocs/op, and profiling inside tests.'
contentType = 'tutorial'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "pprof", "profiling", "performance", "benchmark"]
cover = { image = "/images/covers/go-profiling-pprof.png", alt = "Profiling Go with pprof", hiddenInSingle = true }
+++

Somebody says "the service is slow", and now you have to decide what to change. The honest answer is usually "I don't know yet", and guessing is exactly how people spend a week making the wrong line faster. A **profiler** removes the guessing: it watches the running program and tells you where the time or the memory actually went.

Go has one built in, called {{< term "pprof" "pprof" >}}. In this post I use it on a tiny `net/http` service that I made slow on purpose, read its output line by line, fix what it points at, and check the fix with numbers. It builds on [benchmarks](/posts/go-testing-basics/) and the [memory basics](/posts/go-pointers-memory/), and it comes right after [rate limiting and caching in Go](/posts/go-rate-limiting-caching/): a limiter and a cache are guesses about where the load is, and a profile is how you find out if the guess was right.

> I re-ran everything with Go 1.27 on macOS (arm64). This machine is shared, and the load average was around 4 during the runs, so I do **not** publish `ns/op` or any speedup ratio. What I rely on is allocation counts (`allocs/op`, bytes) and *where* a profile puts the cost. Profile numbers such as milliseconds and percentages change from run to run, and I say so where it matters. The code is a local example, not a published repo.

## The slow service

One handler makes three classic mistakes on purpose:

- it compiles a **regular expression** on every request, although the pattern never changes;
- it builds a string with `+=` in a loop, which copies the whole string on every iteration;
- it turns 500 structs into JSON on every request, although the data never changes.

```go
func Handler(w http.ResponseWriter, r *http.Request) {
	q := r.URL.Query().Get("q")
	re := regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
	if !re.MatchString(q) { http.Error(w, "bad q", 400); return }
	s := ""
	for i := 0; i < 200; i++ {
		s += fmt.Sprintf("%s-%d,", q, i)
	}
	body, _ := json.Marshal(catalog[:500])
	w.Header().Set("X-Len", fmt.Sprint(len(s)))
	w.Write(body)
}
```

pprof lives on a **separate admin port**, bound to loopback (`127.0.0.1`), so it is reachable only from the same machine:

```go
admin := http.NewServeMux()
admin.HandleFunc("/debug/pprof/", pprof.Index)
admin.HandleFunc("/debug/pprof/profile", pprof.Profile)
admin.HandleFunc("/debug/pprof/trace", pprof.Trace)
admin.HandleFunc("/debug/pprof/symbol", pprof.Symbol)
log.Fatal(http.ListenAndServe("127.0.0.1:6060", admin))
```

There is a reason for registering the handlers by hand. If you simply import `net/http/pprof` for its side effect, it registers its handlers on `http.DefaultServeMux`. If your public server uses the default mux, you have just published heap contents and goroutine stacks to the internet. A private mux on a private port avoids that. (In my runs the ports were different free ports; the numbers in the snippets are the usual ones.)

To make the service busy we need traffic. The load generator is a small Go program: N goroutines share an atomic counter and keep sending requests until a fixed total is reached:

```
$ ./load -c 8 -n 30000
requests=30000 ok=30000
```

That is 8 concurrent clients and 30,000 requests, all answered with 200.

## A CPU profile: what it is and how to read it

A CPU profile is a **sample**, not a recording. While it runs, the Go runtime interrupts the program about 100 times a second and writes down which function is running and who called it (this is from the Go documentation of `runtime/pprof`). After a few seconds you have a thousand or so such snapshots, and the functions that show up in many of them are where the CPU time goes. This is cheap enough to do on a live service, and it also means that very short events can be missed.

I started `curl 'http://127.0.0.1:6060/debug/pprof/profile?seconds=12'` and the load run together, so the 12-second window overlapped the load. Then I read the file with `go tool pprof`. I used text output only, since there is no graphviz here. First the `-top` view:

```
$ go tool pprof -top -nodecount=6 svc slow.prof
Duration: 12.09s, Total samples = 17950ms (148.51%)
      flat  flat%   sum%        cum   cum%
    3030ms 16.88% 16.88%     3030ms 16.88%  runtime.usleep
    2080ms 11.59% 28.47%     2080ms 11.59%  syscall.rawsyscalln
    1360ms  7.58% 36.04%     1360ms  7.58%  runtime.pthread_kill
    1150ms  6.41% 42.45%     1150ms  6.41%  runtime.madvise
    1150ms  6.41% 48.86%     1150ms  6.41%  runtime.pthread_cond_wait
     670ms  3.73% 52.59%      680ms  3.79%  runtime.kevent
```

Let me read the header and the columns first, because this is where people get lost.

- `Duration: 12.09s, Total samples = 17950ms (148.51%)`: the profile covered 12 seconds of wall-clock time but holds almost 18 seconds of CPU samples. That is possible because the machine has several cores and more than one was busy at the same time, so the total can be above 100%.
- **flat** is the time spent in the function's own lines.
- **cum** (cumulative) is flat plus the time spent in everything the function called. If `A` takes 10 ms in its own code and calls `B`, which takes 90 ms, then `A` has flat 10 ms and cum 100 ms.
- `flat%` and `cum%` are the same numbers as a share of the total. `sum%` is a running total of `flat%` down the list.

Now the content. The top of the flat view is all runtime and operating-system functions: sleeping, signalling threads, system calls, returning memory to the OS, waiting for network events. None of them is my code. That by itself is a hint: when a flat profile is dominated by the runtime, the program is probably busy with memory allocation, garbage collection (GC) and scheduling more than with its own logic, but I would not conclude more than that from this list. To find *my* code, I need the cumulative view and `-list`, which prints the source of one function with the cost of every line:

```
$ go tool pprof -list='app.Handler' svc slow.prof
      20ms      7.39s (flat, cum) 41.17% of Total
         .       20ms     29:	q := r.URL.Query().Get("q")
         .      420ms     31:	re := regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
         .       10ms     32:	if !re.MatchString(q) {
      20ms      1.27s     39:		s += fmt.Sprintf("%s-%d,", q, i)
         .      4.26s     42:	body, _ := json.Marshal(catalog[:500])
         .      1.38s     44:	w.Write(body)
```

(I removed the lines with no cost, and the file path in the header.) The first number on a line is flat, the second is cum. Now the picture is clear: `app.Handler` alone is 7.39 s, 41% of everything the profile sampled. Inside it, all three suspects show up: the regexp compile (0.42 s), the `+=` loop (1.27 s) and, the biggest, `json.Marshal` (4.26 s). `w.Write` is writing to the socket, which is network I/O and not something to fix here.

The absolute numbers differ from run to run. In the original run of this post, the regexp line was bigger than here and `json.Marshal` smaller. The *ranking* of the suspects is what to take away, not the milliseconds.

## Fixing it, and checking the fix

Each mistake has a plain fix:

```go
var validQ = regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
var catalogJSON, _ = json.Marshal(catalog[:500]) // catalog is static
// in the handler:
var sb strings.Builder
for i := 0; i < 200; i++ { fmt.Fprintf(&sb, "%s-%d,", q, i) }
```

The regexp is compiled once when the program starts. The `strings.Builder` appends in place instead of copying the whole string each time. Caching the JSON is only correct because this catalog never changes; if it could change, you would encode into a pooled buffer on each request instead.

How do I know it worked, without trusting my machine's timing? The benchmark in `app_test.go` calls the handler with an `httptest.NewRecorder`, and `-benchmem` reports allocations. These two numbers do not depend on the load of the machine. Before and after, from `go test ./app -bench . -benchmem -count 3`:

```
slow:   ~257,000 B/op   998 allocs/op
fixed:    42,810 B/op   226 allocs/op
```

(The slow version's bytes vary by a few hundred between runs; `allocs/op` was 998 every time.) So each request now makes 226 allocations instead of 998, and allocates about a sixth of the memory. Fewer allocations also means less work for the garbage collector. In the original run of this post I compared ten runs of each version with `benchstat` (`golang.org/x/perf/cmd/benchstat`), and it reported -83.26% bytes and -77.35% allocations (`p=0.000`). I did not re-run benchstat here; the raw numbers above agree with it.

I then ran the same 30,000-request load against the fixed service. `app.Handler` is now 1.42 s in total (against 7.39 s), and the `-list` view shows the biggest line is `w.Write(catalogJSON)` at 1.11 s, which is socket I/O. What is left is mostly the network. I do not quote a speedup ratio: the two profile windows were not the same length, and the machine was busy.

## Heap and goroutine profiles

CPU is not the only thing to profile. A **heap profile** shows who allocated memory, and it has two views of the same data. To see the difference I added a `/cache` handler that allocates 16 KB per request and keeps every 16th buffer forever. After 20,000 requests:

```
$ go tool pprof -sample_index=inuse_space -top -nodecount=1 svc heap.prof
   18.07MB 87.83%  main.cache
$ go tool pprof -sample_index=alloc_space -top -nodecount=1 svc heap.prof
  275.21MB 89.14%  main.cache
```

You can check these against simple arithmetic. 20,000 requests of 16 KiB make about 312 MiB allocated in total. Keeping every 16th buffer is 1,250 buffers, about 19.5 MiB still held. The profile is a sampled *estimate*, so it lands near these numbers and not exactly on them (and the details of which moment it describes are in the `runtime/pprof` documentation).

- `inuse_space` answers "what is held in memory right now". It finds leaks and things that are kept too long.
- `alloc_space` answers "how much was allocated in total, kept or not". It finds code that creates a lot of short-lived garbage and so puts pressure on the GC, even when nothing is retained.

For **goroutines**, a `/leak` handler starts a goroutine that waits on a channel nobody writes to, which is a {{< term "goroutine-leak" "goroutine leak" >}}. After 500 requests, the URL with `?debug=1` prints a text report you can read in a terminal:

```
$ curl 'http://127.0.0.1:6060/debug/pprof/goroutine?debug=1'
goroutine profile: total 504
500 @ 0x1006f4aa8 0x1006867c0 0x100686344 0x100908a34 0x1006fbae4
#	0x100908a33	main.leak.func1+0x23	.../cmd/svc/main.go:52
```

The report groups goroutines by their stack. The first line says there are 504 in total, 500 of them with the same stack, stuck on line 52 of `main.go`, which is `<-ch` in the leaking handler. (The other four belong to the program itself, such as the server. The hex addresses change on every run.) 500 goroutines parked on one line, and the count growing with every request, is the typical signature of a leak.

## Profiling in tests, and tracing

You do not need a running service to profile. `go test` can write the profiles itself:

```
go test ./app -bench . -benchmem -cpuprofile cpu.prof -memprofile mem.prof
go tool pprof -sample_index=alloc_space -top app.test mem.prof
```

The same `-list` works. For the slow handler in a short benchmark run, the allocation total was 1.42 GB, and the `s += ...` line alone was 880 MB of it: each `+=` allocates a new, longer string, so the cost grows with every iteration. The regexp compile line was 137 MB. The last command needs the `app.test` binary, which `go test` leaves in the directory when you ask for a profile, because `pprof` needs it to turn addresses into function names.

pprof also has `/debug/pprof/trace`, and `go tool trace` opens its output. It uses `runtime/trace` to record a timeline of goroutines, GC and scheduling, which can answer "why is nothing running?" questions that sampling cannot. I only checked that the endpoint returns a trace (HTTP 200 and a non-empty body); I did not open the viewer.

## Profiling mistakes

- **Profiling an idle process.** A CPU profile records what the CPU was doing. Without realistic load there is nothing to see. Send traffic while it samples.
- **Changing many things at once.** Profile before and after with the same load, and change one thing at a time. Otherwise you cannot tell which change helped.
- **Reading the percentages naively.** Total samples can be above 100% of the wall time (148.51% above) when several cores are busy, and a flat profile full of `runtime.*` functions needs the cumulative view before it points to your code.
- **Exposing the pprof port.** Heap contents and stacks can reveal data and code paths. Keep it on loopback or protect it.
- **Trusting the benchmark's own noise.** A benchmark using `httptest.NewRecorder` also counts the recorder's allocations, so the absolute numbers are a little higher than the handler alone. Compare before and after, not against zero.

## What's next

The next post in this series is "Docker, CI and deploying a Go service". We now know where the time goes, but a service that is fast on a laptop still has to be built, tested and shipped somewhere else.
