+++
date = '2027-02-20T10:00:00+03:30'
draft = false
title = 'Profiling Go with pprof'
description = 'Find a Go hot spot with pprof: CPU, heap and goroutine profiles on a live service, a fix verified with benchstat and allocs/op, and profiling inside tests.'
categories = ["Go"]
series = ["Go Backend"]
tags = ["go", "backend", "pprof", "profiling", "performance", "benchmark"]
cover = { image = "/images/covers/go-profiling-pprof.png", alt = "Profiling Go with pprof", hiddenInSingle = true }
+++

The [previous post](/posts/go-rate-limiting-caching/) was about rate limiting and caching. Now a different question: the service is slow, so what do you change? Guessing is how people end up optimizing the wrong line. **pprof** is Go's built-in **profiler**, and this post uses it on a tiny `net/http` service that I made slow on purpose. It builds on [benchmarks](/posts/go-testing-basics/) and the [memory basics](/posts/go-pointers-memory/) from earlier.

> Go 1.26, macOS arm64. This machine is shared and the load average was between 3 and 10 during my runs, so I show **no ns/op** and claim no speedup ratio. I rely on allocs/op, B/op and profile attribution, which do not depend on load.

## The slow service

One handler does three classic mistakes: it compiles a **regexp** on every request, builds a string with `+=` in a loop, and marshals 500 structs to JSON.

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

pprof goes on a **separate admin port**, bound to loopback:

```go
admin := http.NewServeMux()
admin.HandleFunc("/debug/pprof/", pprof.Index)
admin.HandleFunc("/debug/pprof/profile", pprof.Profile)
admin.HandleFunc("/debug/pprof/trace", pprof.Trace)
log.Fatal(http.ListenAndServe("127.0.0.1:6060", admin))
```

Importing `net/http/pprof` for its side effect registers handlers on `http.DefaultServeMux`, so if your public server uses the default mux, you have just exposed heap contents and goroutine stacks to the internet. Register handlers explicitly on a private mux, as above, and never expose this port publicly.

The load generator is a small Go program: N goroutines share an atomic counter and send requests until a fixed total is reached.

```
$ ./load -c 8 -n 30000
requests=30000 ok=30000
```

## A CPU profile

I started `curl 'http://127.0.0.1:6060/debug/pprof/profile?seconds=12'` and the load run together, then used text output only (no graphviz here):

```
$ go tool pprof -top -nodecount=4 svc slow.prof
Duration: 12.12s, Total samples = 15.14s (124.90%)
      flat  flat%   sum%        cum   cum%
    2650ms 17.50% 17.50%     2650ms 17.50%  runtime.usleep
    2230ms 14.73% 32.23%     2230ms 14.73%  syscall.rawsyscalln
    1400ms  9.25% 41.48%     1400ms  9.25%  runtime.madvise
    1140ms  7.53% 49.01%     1140ms  7.53%  runtime.pthread_kill
```

The flat view is mostly runtime and syscalls: GC and scheduling noise, which is itself a hint about allocation. The useful tool is `-list`, which shows cost per source line of your own function:

```
$ go tool pprof -list='app.Handler' svc slow.prof
         .      680ms     31:	re := regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
         .      1.26s     39:		s += fmt.Sprintf("%s-%d,", q, i)
         .      2.03s     42:	body, _ := json.Marshal(catalog[:500])
         .      1.55s     44:	w.Write(body)
```

`app.Handler` is 5.60s cumulative, 36.99% of all samples. The three suspects are all there. (`w.Write` is socket I/O.)

## Fix and compare

```go
var validQ = regexp.MustCompile(`^[a-z0-9-]{1,32}$`)
var catalogJSON, _ = json.Marshal(catalog[:500]) // catalog is static
// in the handler:
var sb strings.Builder
for i := 0; i < 200; i++ { fmt.Fprintf(&sb, "%s-%d,", q, i) }
```

Caching the JSON is only valid because the catalog never changes; otherwise you would encode into a pooled buffer. I ran `go test -bench . -benchmem -count 10` before and after, then used `benchstat` (`golang.org/x/perf/cmd/benchstat`, installed into a private GOBIN), filtering out the time unit because of the load:

```
Handler-8   249.80Ki ± 0%   41.81Ki ± 0%  -83.26% (p=0.000 n=10)   B/op
Handler-8   998.0 ± 0%      226.0 ± 0%    -77.35% (p=0.000 n=10)   allocs/op
```

Same 30000-request load against the fixed service: 2.94s of CPU samples instead of 15.14s, and `-list` now shows `w.Write` as the biggest line at 1.17s, so what remains is mostly the network. I do not quote a speedup because of the load.

## Heap and goroutine profiles

A heap profile has two views of the same data. A `/cache` handler allocates 16 KB per request and keeps every 16th buffer; after 20000 requests:

```
$ go tool pprof -sample_index=inuse_space -top -nodecount=1 svc heap.prof
16121.29kB 83.91%  main.cache
$ go tool pprof -sample_index=alloc_space -top -nodecount=1 svc heap.prof
  294.46MB 89.10%  main.cache
```

`inuse_space` answers "what is held right now", which finds leaks and retention. `alloc_space` answers "what was allocated in total", which finds GC pressure even when nothing is retained. Both are sampled estimates.

For goroutines, a `/leak` handler starts a goroutine waiting on a channel nobody writes to. After 500 requests, `?debug=1` prints text you can read in a terminal:

```
$ curl 'http://127.0.0.1:6060/debug/pprof/goroutine?debug=1'
goroutine profile: total 504
500 @ 0x102341aac ...
#	0x102508de3	main.leak.func1+0x23	.../cmd/svc/main.go:52
```

500 goroutines stuck on one line is the signature of a leak.

## Profiling in tests, and tracing

```
go test ./app -bench . -benchmem -cpuprofile cpu.prof -memprofile mem.prof
go tool pprof -sample_index=alloc_space -top app.test mem.prof
```

The same `-list` works there, and on the slow code it showed 1.83 GB of allocations on the `regexp.MustCompile` line and 11.02 GB on the `+=` line for the whole run. The last command needs the `app.test` binary, which the test run leaves behind. `/debug/pprof/trace` and `go tool trace` use `runtime/trace` to show a timeline of goroutines, GC and scheduling, which answers "why is nothing running" questions that sampling cannot. I only checked that the endpoint returns a trace; I did not open the UI.

## A few things to watch

- CPU profiling samples (about 100 times per second), so it adds overhead and misses short events. Profile realistic load, not an idle process.
- Profile before and after, with the same load, and change one thing at a time.
- Total samples can exceed the wall time (124.90% above) because several CPUs are busy.
- Never expose the pprof port publicly; bind it to loopback or protect it.
- Benchmarks with `httptest.NewRecorder` include the recorder's own allocations.

## What's next

Next is Docker, CI and deploying a Go service.
