+++
date = '2027-04-13T10:00:00+03:30'
draft = false
title = 'Node.js or Go? When to use which'
description = 'Node.js or Go for a backend service? The same HTTP service built twice and compared on size, memory and crash behaviour, plus a decision table.'
categories = ["Node.js"]
series = ["Node.js"]
tags = ["nodejs", "go", "comparison", "backend"]
cover = { image = "/images/covers/node-vs-go-when-to-use.png", alt = "Node.js or Go? When to use which", hiddenInSingle = true }
+++

This is the last post of the Node.js series. The [previous one](/posts/node-profiling-memory-shutdown/) was about profiling, memory and shutdown. Now the question I get most: Node.js or Go? I use both at work, so this is one person's view with some evidence. I built the same small service twice, with no frameworks, in Node 20.13.1 and Go 1.26, following my posts on [`node:http`](/posts/node-http-server/) and [`net/http`](/posts/go-http-api-stdlib/). The code is a local demo.

## The same service twice

Three endpoints: `POST /echo` returns the JSON it received, `GET /primes?n=200000` sums the primes below n with a sieve (a {{< term "cpu-bound" "CPU-bound" >}} job), and `GET /slow` calls a tiny upstream on loopback that always waits 20 ms (an {{< term "io-bound" "I/O-bound" >}} job). A bad body returns 400. The same upstream served both.

```js
const r = await fetch(upstream);
send(200, await r.json());
```

```go
resp, err := http.Get(upstream)
```

Both returned identical answers (`{"n":200000,"sum":1709600813}`), and the 3,000 mixed requests I sent to each (20 at a time) all returned 200.

## What I counted

| Measured here | Node | Go |
|---|---|---|
| Lines of code | 41 | 75 (gofmt style) |
| Dependencies | 0 (no `node_modules`) | 0 (no `go.sum`) |
| Shipped artifact | the app plus a Node runtime (the `node` binary here is 94,112,064 bytes) | one binary, 9,058,098 bytes |
| RSS at start | 87,872 KB | 11,872 KB |
| RSS after 3,000 requests | 108,832 KB | 17,968 KB |

The lines are not a fair contest: my Node file is dense and Go's formatter spreads code out. RSS came from `ps -o rss` on my own processes only. A tuned or real service will differ. I did not measure throughput or latency: the machine's load average was above 6 when I checked, so any number would be noise. If you need them, measure on a quiet machine with your own workload.

## What happens when it breaks

I added `GET /boom` to each. In Go it writes to a nil map. In Node it throws inside a timer callback after replying.

```text
http: panic serving 127.0.0.1:52808: assignment to entry in nil map
goroutine 3837 [running]:
```

Go's server recovered the panic inside that connection, logged a stack trace, and the next request worked. The client of `/boom` got no reply. In Node:

```text
Error: boom in a callback
    at Timeout._onTimeout (server.mjs:35:30)
Node.js v20.13.1
```

The client got its 200, then the whole process exited. I did not test a panic in a goroutine you started yourself; that one is not recovered by `net/http` and would crash Go too. Node's rule is covered in [errors and unhandled rejections](/posts/node-errors-unhandled-rejections/): handle it or let a supervisor restart you.

## Concurrency, briefly

Node runs your JavaScript on one thread, and the [event loop](/posts/node-event-loop/) interleaves waiting work. That suits `/slow` well. A long `/primes` call blocks everything, and the answer is [worker threads or cluster](/posts/node-worker-threads-cluster/). Go starts a {{< term "goroutine" "goroutine" >}} per request on all cores, so a CPU-heavy handler only occupies its own ([channels and goroutines](/posts/go-goroutines-channels/)). I did not benchmark that difference here.

## Decision guide (in my experience)

| Factor | I lean toward |
|---|---|
| Team already knows JavaScript or TypeScript | Node.js |
| Ecosystem breadth (SDKs, tooling, front-end sharing) | Node.js |
| Static types out of the box | Go (TypeScript gives Node this too) |
| Deployment simplicity | Go, a single binary |
| CPU-bound work | Go |
| Streaming and proxying | both are good; Node streams need care with [backpressure](/posts/node-streams-backpressure/) |
| Many long-lived connections | both work; Go is simpler to reason about |

## A few things to watch

- My table is opinion. The numbers above come from one machine and one tiny service.
- Memory at startup is not memory under your real load.
- Language choice rarely beats database, network and design quality.
- Team skill usually decides faster than any benchmark.
- Pin the Node and Go versions in your own comparison.

## Exercise

Add a `GET /sum?n=...` endpoint that does the work in a worker thread in Node. Then compare its behaviour with the Go version while a `/primes` request is running, using counts or response order, not guesses.

## What's next

The Node.js series ends here. Next come the Software Engineering, Algorithms and Distributed Systems series.
